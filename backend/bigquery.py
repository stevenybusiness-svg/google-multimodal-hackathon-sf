"""BigQuery service — NL-to-SQL report generation for the meeting agent."""

import asyncio
import logging
import os
import random
from datetime import date, timedelta
from urllib.parse import quote

from google import genai
from google.cloud import bigquery

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

_bq: bigquery.Client | None = None
_genai: genai.Client | None = None


def _get_bq() -> bigquery.Client:
    global _bq
    if _bq is None:
        _bq = bigquery.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
    return _bq


def _get_genai() -> genai.Client:
    global _genai
    if _genai is None:
        _genai = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _genai


def bq_available() -> bool:
    """Check if BigQuery is configured."""
    return bool(os.getenv("GOOGLE_CLOUD_PROJECT"))


NL_TO_SQL_MODEL = "gemini-3-flash-preview"
DATASET_ID = "marketing_data"
TABLE_ID = "campaigns"

CHANNELS = ["organic_search", "paid_search", "paid_social", "email", "direct", "referral"]
SEGMENTS = ["enterprise", "mid_market", "smb", "startup"]
KEY_ACCOUNTS = [None, None, "Acme Corp", "Globex", "Initech", "Umbrella", "Wonka Industries"]

SCHEMA = [
    bigquery.SchemaField("date", "DATE"),
    bigquery.SchemaField("channel", "STRING"),
    bigquery.SchemaField("segment", "STRING"),
    bigquery.SchemaField("key_account", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("spend", "FLOAT"),
    bigquery.SchemaField("conversions", "INTEGER"),
    bigquery.SchemaField("revenue", "FLOAT"),
    bigquery.SchemaField("cac", "FLOAT"),
    bigquery.SchemaField("impression_count", "INTEGER"),
    bigquery.SchemaField("click_count", "INTEGER"),
    bigquery.SchemaField("roi", "FLOAT"),
]

SCHEMA_DDL = """Table: `{project}.marketing_data.campaigns`
Columns:
  date           DATE          -- campaign date
  channel        STRING        -- one of: organic_search, paid_search, paid_social, email, direct, referral
  segment        STRING        -- one of: enterprise, mid_market, smb, startup
  key_account    STRING (NULL) -- named account or NULL
  spend          FLOAT         -- dollars spent
  conversions    INTEGER       -- number of conversions
  revenue        FLOAT         -- dollars earned
  cac            FLOAT         -- customer acquisition cost (spend / conversions)
  impression_count INTEGER     -- ad impressions
  click_count    INTEGER       -- ad clicks
  roi            FLOAT         -- return on investment ((revenue - spend) / spend)
"""

# ---------------------------------------------------------------------------
# Sample data generator
# ---------------------------------------------------------------------------


def _generate_sample_rows(num_days: int = 90) -> list[dict]:
    """Generate realistic-looking marketing data for seeding."""
    rows = []
    base = date.today() - timedelta(days=num_days)
    rng = random.Random(42)  # deterministic seed for reproducibility

    for day_offset in range(num_days):
        d = base + timedelta(days=day_offset)
        for channel in CHANNELS:
            segment = rng.choice(SEGMENTS)
            key_account = rng.choice(KEY_ACCOUNTS)

            # Channel-specific spend ranges
            spend_base = {
                "paid_search": 800, "paid_social": 600, "email": 100,
                "organic_search": 50, "direct": 30, "referral": 40,
            }[channel]
            spend = round(spend_base * rng.uniform(0.5, 1.8), 2)

            impressions = int(spend * rng.uniform(80, 200))
            clicks = int(impressions * rng.uniform(0.01, 0.08))
            conversions = max(1, int(clicks * rng.uniform(0.02, 0.15)))
            revenue = round(conversions * rng.uniform(50, 500), 2)
            cac = round(spend / conversions, 2)
            roi = round((revenue - spend) / spend, 4) if spend > 0 else 0.0

            rows.append({
                "date": d.isoformat(),
                "channel": channel,
                "segment": segment,
                "key_account": key_account,
                "spend": spend,
                "conversions": conversions,
                "revenue": revenue,
                "cac": cac,
                "impression_count": impressions,
                "click_count": clicks,
                "roi": roi,
            })
    return rows


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def setup_dataset() -> str:
    """Create dataset + table if needed, seed sample data if empty. Returns status."""
    def _sync_setup() -> str:
        client = _get_bq()
        project = client.project
        dataset_ref = f"{project}.{DATASET_ID}"

        # Create dataset
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset, exists_ok=True)
        logger.info("Dataset %s ready", dataset_ref)

        # Create table
        table_ref = f"{dataset_ref}.{TABLE_ID}"
        table = bigquery.Table(table_ref, schema=SCHEMA)
        client.create_table(table, exists_ok=True)

        # Check if empty
        count_query = f"SELECT COUNT(*) as cnt FROM `{table_ref}`"
        result = list(client.query(count_query).result())
        if result[0].cnt == 0:
            rows = _generate_sample_rows()
            errors = client.insert_rows_json(table_ref, rows)
            if errors:
                logger.error("BigQuery insert errors: %s", errors)
                return f"Seeded with errors: {errors}"
            logger.info("Seeded %d rows into %s", len(rows), table_ref)
            return f"Created and seeded {len(rows)} rows"
        return f"Table already has {result[0].cnt} rows"

    return await asyncio.to_thread(_sync_setup)


# ---------------------------------------------------------------------------
# NL → SQL
# ---------------------------------------------------------------------------


async def nl_to_sql(query: str) -> str:
    """Convert a natural-language question to BigQuery SQL using Gemini."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    schema_desc = SCHEMA_DDL.format(project=project)

    prompt = f"""You are a BigQuery SQL expert. Convert the user's natural-language question
into a single BigQuery Standard SQL query.

{schema_desc}

Rules:
- Use fully-qualified table name: `{project}.{DATASET_ID}.{TABLE_ID}`
- Return ONLY the SQL query, no markdown, no explanation, no code fences.
- Use Standard SQL (BigQuery dialect).
- Limit results to 100 rows unless the user asks for more.

User question: {query}

SQL:"""

    def _call_gemini() -> str:
        client = _get_genai()
        resp = client.models.generate_content(model=NL_TO_SQL_MODEL, contents=prompt)
        sql = resp.text.strip()
        # Strip markdown fences if model adds them anyway
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[1] if "\n" in sql else sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3].rstrip()
        if sql.lower().startswith("sql"):
            sql = sql[3:].lstrip()
        return sql

    return await asyncio.to_thread(_call_gemini)


# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------


async def run_query(sql: str) -> list[dict]:
    """Execute SQL against BigQuery and return rows as list of dicts."""
    def _exec() -> list[dict]:
        client = _get_bq()
        query_job = client.query(sql)
        results = query_job.result()
        return [dict(row.items()) for row in results]

    return await asyncio.to_thread(_exec)


# ---------------------------------------------------------------------------
# Looker Studio URL
# ---------------------------------------------------------------------------


def looker_studio_url(project_id: str, dataset_id: str, table_id: str) -> str:
    """Generate a Looker Studio explore URL pre-connected to a BigQuery table."""
    return (
        "https://lookerstudio.google.com/reporting/create"
        f"?c.mode=edit"
        f"&ds.ds0.connector=bigQuery"
        f"&ds.ds0.projectId={quote(project_id)}"
        f"&ds.ds0.type=TABLE"
        f"&ds.ds0.datasetId={quote(dataset_id)}"
        f"&ds.ds0.tableId={quote(table_id)}"
    )


# ---------------------------------------------------------------------------
# End-to-end report generation
# ---------------------------------------------------------------------------


async def generate_report(query: str) -> dict:
    """NL question → SQL → execute → formatted report dict."""
    sql = await nl_to_sql(query)
    logger.info("Generated SQL: %s", sql)

    results = await run_query(sql)

    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    explore_url = looker_studio_url(project, DATASET_ID, TABLE_ID)

    # Build a short summary via Gemini
    summary = await _summarize_results(query, results)

    return {
        "sql": sql,
        "results": results,
        "looker_url": explore_url,
        "summary": summary,
    }


async def _summarize_results(query: str, results: list[dict]) -> str:
    """Generate a short text summary of query results using Gemini."""
    if not results:
        return "No results found for your query."

    # Truncate for prompt — send first 20 rows max
    preview = results[:20]

    prompt = f"""Summarize these query results in 2-3 sentences for a business user.

Question: {query}
Results ({len(results)} rows, showing first {len(preview)}):
{preview}

Summary:"""

    def _call() -> str:
        client = _get_genai()
        resp = client.models.generate_content(model=NL_TO_SQL_MODEL, contents=prompt)
        return resp.text.strip()

    try:
        return await asyncio.to_thread(_call)
    except Exception as e:
        logger.warning("Summary generation failed: %s", e)
        return f"Query returned {len(results)} rows."
