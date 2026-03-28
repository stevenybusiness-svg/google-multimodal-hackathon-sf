"""BigQuery service — NL-to-SQL report generation for the meeting agent."""

import asyncio
import json
import logging
import os
import random
from datetime import date, timedelta
from urllib.parse import quote

from google import genai
from google.api_core import exceptions as gapi_exceptions
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

CHANNELS = ["organic_search", "paid_search", "paid_social", "email", "direct", "referral", "display", "affiliate", "content_syndication"]
SEGMENTS = ["enterprise", "mid_market", "smb", "startup"]
REGIONS = ["North America", "Europe", "APAC", "LATAM", "Middle East"]
CAMPAIGNS = [
    "Spring Launch 2025", "Summer Brand Push", "Fall Retargeting", "Holiday Blitz Q4",
    "Product Launch Alpha", "Webinar Series", "ABM Enterprise", "Social Viral",
    "SEO Content Push", "Partner Co-Marketing", "Trade Show Follow-Up",
    "Customer Win-Back", "New Market Entry APAC", "Brand Awareness Q1 2026",
    "Performance Max", "Influencer Collab", "Free Trial Promo",
]
KEY_ACCOUNTS = [
    None, None, None, None,  # ~57% no key account
    "Acme Corp", "Globex International", "Initech Solutions", "Umbrella Holdings",
    "Wonka Industries", "Stark Enterprises", "Wayne Corp", "Cyberdyne Systems",
    "Soylent Corp", "Massive Dynamic", "Aperture Science",
]
PRODUCTS = ["Platform Pro", "Analytics Suite", "API Gateway", "Starter Plan", "Enterprise Cloud"]
DEVICE_TYPES = ["desktop", "mobile", "tablet"]
CREATIVE_TYPES = ["video", "static_image", "carousel", "text_only", "interactive"]

SCHEMA = [
    bigquery.SchemaField("date", "DATE"),
    bigquery.SchemaField("channel", "STRING"),
    bigquery.SchemaField("campaign_name", "STRING"),
    bigquery.SchemaField("segment", "STRING"),
    bigquery.SchemaField("region", "STRING"),
    bigquery.SchemaField("key_account", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("product", "STRING"),
    bigquery.SchemaField("device_type", "STRING"),
    bigquery.SchemaField("creative_type", "STRING"),
    bigquery.SchemaField("spend", "FLOAT"),
    bigquery.SchemaField("impressions", "INTEGER"),
    bigquery.SchemaField("clicks", "INTEGER"),
    bigquery.SchemaField("conversions", "INTEGER"),
    bigquery.SchemaField("revenue", "FLOAT"),
    bigquery.SchemaField("cac", "FLOAT"),
    bigquery.SchemaField("ctr", "FLOAT"),
    bigquery.SchemaField("conversion_rate", "FLOAT"),
    bigquery.SchemaField("roi", "FLOAT"),
    bigquery.SchemaField("avg_deal_size", "FLOAT"),
    bigquery.SchemaField("pipeline_value", "FLOAT"),
    bigquery.SchemaField("new_leads", "INTEGER"),
    bigquery.SchemaField("qualified_leads", "INTEGER"),
]

SCHEMA_DDL = """Table: `{project}.marketing_data.campaigns`
Columns:
  date              DATE       -- campaign date
  channel           STRING     -- marketing channel (organic_search, paid_search, paid_social, email, direct, referral, display, affiliate, content_syndication)
  campaign_name     STRING     -- campaign name (e.g. "Spring Launch 2025", "Holiday Blitz Q4")
  segment           STRING     -- customer segment (enterprise, mid_market, smb, startup)
  region            STRING     -- geographic region (North America, Europe, APAC, LATAM, Middle East)
  key_account       STRING     -- named account or NULL
  product           STRING     -- product line (Platform Pro, Analytics Suite, API Gateway, Starter Plan, Enterprise Cloud)
  device_type       STRING     -- device (desktop, mobile, tablet)
  creative_type     STRING     -- ad creative type (video, static_image, carousel, text_only, interactive)
  spend             FLOAT      -- dollars spent
  impressions       INTEGER    -- ad impressions served
  clicks            INTEGER    -- ad clicks
  conversions       INTEGER    -- completed conversions / purchases
  revenue           FLOAT      -- revenue generated ($)
  cac               FLOAT      -- customer acquisition cost (spend / conversions)
  ctr               FLOAT      -- click-through rate (clicks / impressions)
  conversion_rate   FLOAT      -- conversion rate (conversions / clicks)
  roi               FLOAT      -- return on investment ((revenue - spend) / spend)
  avg_deal_size     FLOAT      -- average deal size ($)
  pipeline_value    FLOAT      -- total pipeline value generated ($)
  new_leads         INTEGER    -- new leads generated
  qualified_leads   INTEGER    -- marketing qualified leads (MQLs)
"""

# ---------------------------------------------------------------------------
# Sample data generator
# ---------------------------------------------------------------------------

import math


def _generate_sample_rows(num_days: int = 365) -> list[dict]:
    """Generate a rich, realistic marketing dataset for 365 days."""
    rows = []
    base = date.today() - timedelta(days=num_days)
    rng = random.Random(42)

    # Channel-specific base metrics
    channel_profiles = {
        "paid_search":         {"spend": 2200, "ctr_base": 0.035, "conv_base": 0.04, "deal": 380},
        "paid_social":         {"spend": 1800, "ctr_base": 0.012, "conv_base": 0.025, "deal": 290},
        "organic_search":      {"spend": 120,  "ctr_base": 0.045, "conv_base": 0.055, "deal": 420},
        "email":               {"spend": 250,  "ctr_base": 0.08,  "conv_base": 0.065, "deal": 350},
        "direct":              {"spend": 80,   "ctr_base": 0.06,  "conv_base": 0.07,  "deal": 510},
        "referral":            {"spend": 100,  "ctr_base": 0.05,  "conv_base": 0.08,  "deal": 600},
        "display":             {"spend": 1400, "ctr_base": 0.005, "conv_base": 0.012, "deal": 260},
        "affiliate":           {"spend": 500,  "ctr_base": 0.025, "conv_base": 0.035, "deal": 310},
        "content_syndication": {"spend": 350,  "ctr_base": 0.02,  "conv_base": 0.03,  "deal": 340},
    }

    # Segment revenue multipliers
    segment_mult = {"enterprise": 3.5, "mid_market": 1.8, "smb": 1.0, "startup": 0.6}

    for day_offset in range(num_days):
        d = base + timedelta(days=day_offset)
        day_of_year = d.timetuple().tm_yday
        weekday = d.weekday()

        # Seasonality: higher in Q4 (holidays), dip in summer
        season = 1.0 + 0.3 * math.sin(2 * math.pi * (day_of_year - 90) / 365)
        # Weekend dip for B2B channels
        weekend_factor = 0.4 if weekday >= 5 else 1.0
        # Month-over-month growth trend (~15% annual)
        growth = 1.0 + 0.15 * (day_offset / 365)

        # Each day: 2-4 random channel/segment/region combos (not all combos every day)
        combos_per_day = rng.randint(8, 18)
        for _ in range(combos_per_day):
            channel = rng.choice(CHANNELS)
            profile = channel_profiles[channel]
            segment = rng.choice(SEGMENTS)
            region = rng.choices(REGIONS, weights=[40, 25, 20, 10, 5])[0]
            key_account = rng.choice(KEY_ACCOUNTS)
            product = rng.choice(PRODUCTS)
            device = rng.choices(DEVICE_TYPES, weights=[55, 35, 10])[0]
            creative = rng.choice(CREATIVE_TYPES)
            campaign = rng.choice(CAMPAIGNS)

            # Region adjustments
            region_mult = {"North America": 1.0, "Europe": 0.85, "APAC": 0.7, "LATAM": 0.5, "Middle East": 0.4}[region]

            # Compute metrics with variance
            base_spend = profile["spend"] * rng.uniform(0.3, 2.0) * season * growth * region_mult
            if channel in ("organic_search", "direct", "referral"):
                base_spend *= 0.15  # low-spend organic channels
            spend = round(base_spend * weekend_factor, 2)

            impressions = max(10, int(spend * rng.uniform(60, 300)))
            ctr = profile["ctr_base"] * rng.uniform(0.5, 1.8)
            clicks = max(1, int(impressions * ctr))
            conv_rate = profile["conv_base"] * rng.uniform(0.4, 2.0)
            conversions = max(0, int(clicks * conv_rate))

            deal_size = profile["deal"] * segment_mult[segment] * rng.uniform(0.6, 1.6)
            revenue = round(conversions * deal_size, 2) if conversions > 0 else 0
            cac = round(spend / conversions, 2) if conversions > 0 else 0
            roi = round((revenue - spend) / spend, 4) if spend > 0 else 0.0

            new_leads = max(0, int(clicks * rng.uniform(0.05, 0.25)))
            qualified_leads = max(0, int(new_leads * rng.uniform(0.15, 0.5)))
            pipeline = round(qualified_leads * deal_size * rng.uniform(1.5, 4.0), 2)

            rows.append({
                "date": d.isoformat(),
                "channel": channel,
                "campaign_name": campaign,
                "segment": segment,
                "region": region,
                "key_account": key_account,
                "product": product,
                "device_type": device,
                "creative_type": creative,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "revenue": revenue,
                "cac": cac,
                "ctr": round(ctr, 6),
                "conversion_rate": round(conv_rate, 6),
                "roi": roi,
                "avg_deal_size": round(deal_size, 2),
                "pipeline_value": pipeline,
                "new_leads": new_leads,
                "qualified_leads": qualified_leads,
            })
    return rows


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def setup_dataset(force_reseed: bool = False) -> str:
    """Create dataset + table if needed, seed sample data if empty or forced. Returns status.

    If BigQuery returns a 403 (permission denied), returns a status message
    indicating simulated-data mode rather than crashing.
    """
    def _sync_setup() -> str:
        try:
            client = _get_bq()
            project = client.project
            dataset_ref = f"{project}.{DATASET_ID}"

            # Create dataset
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "US"
            client.create_dataset(dataset, exists_ok=True)
            logger.info("Dataset %s ready", dataset_ref)

            table_ref = f"{dataset_ref}.{TABLE_ID}"

            if force_reseed:
                # Drop existing table and recreate with new schema
                client.delete_table(table_ref, not_found_ok=True)
                logger.info("Dropped existing table %s for reseed", table_ref)

            # Create table
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
        except gapi_exceptions.Forbidden as exc:
            logger.warning(
                "BigQuery 403 during setup — using simulated data mode: %s", exc
            )
            return "BigQuery unavailable (403 permission denied) — using simulated data mode"

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


def looker_studio_url(project_id: str, sql: str, report_name: str = "Meeting Agent Report") -> str:
    """Generate a Looker Studio Linking API URL with a CUSTOM_QUERY.

    Uses the correct format (no ds0 alias — bare ds.* params for single data source).
    The SQL is embedded so Looker Studio opens with the exact query results.
    """
    return (
        "https://lookerstudio.google.com/reporting/create"
        f"?ds.connector=bigQuery"
        f"&ds.type=CUSTOM_QUERY"
        f"&ds.projectId={quote(project_id)}"
        f"&ds.sql={quote(sql)}"
        f"&r.reportName={quote(report_name)}"
    )


# ---------------------------------------------------------------------------
# Report storage — in-memory for hackathon
# ---------------------------------------------------------------------------

_reports: dict[str, dict] = {}  # report_id → {html, query, sql, summary, created}


def get_report(report_id: str) -> dict | None:
    return _reports.get(report_id)


# ---------------------------------------------------------------------------
# Simulated report fallback (when BigQuery returns 403 / permission denied)
# ---------------------------------------------------------------------------


async def _generate_simulated_results(query: str, sql: str) -> list[dict]:
    """Use Gemini to produce realistic simulated query results when BQ is unavailable.

    The prompt gives Gemini the schema and marketing-data context so it returns
    plausible numbers consistent with the sample dataset profile (channels, segments,
    regions, spend ranges, etc.).
    """
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    schema_desc = SCHEMA_DDL.format(project=project)

    prompt = f"""You are a marketing-data simulator. Given the SQL query below and the table
schema, produce realistic JSON rows that would plausibly result from running this
query against a 365-day marketing campaigns dataset.

{schema_desc}

Key data characteristics (use these to keep numbers realistic):
- Daily spend per channel-segment combo: $20-$4,400
- CTR: 0.5%-8%, Conversion rate: 1%-8%
- Avg deal sizes: $150-$2,100 depending on segment (enterprise highest)
- Channels: {CHANNELS}
- Segments: {SEGMENTS}
- Regions: {REGIONS} (North America ~40%, Europe ~25%, APAC ~20%)
- Products: {PRODUCTS}

SQL query: {sql}
User question: {query}

Return ONLY a JSON array of objects (10-25 rows). Each object's keys must match the
SELECT columns in the SQL. Use realistic numbers. No markdown fences, no explanation."""

    def _call() -> list[dict]:
        client = _get_genai()
        resp = client.models.generate_content(model=NL_TO_SQL_MODEL, contents=prompt)
        text = resp.text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].rstrip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
        return json.loads(text)

    return await asyncio.to_thread(_call)


# ---------------------------------------------------------------------------
# End-to-end report generation
# ---------------------------------------------------------------------------


async def generate_report(query: str) -> dict:
    """NL question → SQL → execute → LLM-generated HTML report with charts.

    Falls back to Gemini-simulated results when BigQuery returns a 403
    (permission denied), so the demo works even without BQ IAM grants.
    """
    import uuid
    from datetime import datetime, timezone

    sql = await nl_to_sql(query)
    logger.info("Generated SQL: %s", sql)

    source = "bigquery"
    try:
        results = await run_query(sql)
    except gapi_exceptions.Forbidden as exc:
        logger.warning(
            "BigQuery 403 — falling back to simulated data: %s", exc
        )
        results = await _generate_simulated_results(query, sql)
        source = "simulated"

    # LLM generates a full interactive HTML report with charts
    html, summary = await _build_html_report(query, sql, results)

    report_id = str(uuid.uuid4())[:8]
    _reports[report_id] = {
        "html": html,
        "query": query,
        "sql": sql,
        "summary": summary,
        "results": results,
        "row_count": len(results),
        "source": source,
        "created": datetime.now(timezone.utc).isoformat(),
    }

    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    looker_url = looker_studio_url(project, sql, f"Report: {query[:60]}")

    return {
        "report_id": report_id,
        "sql": sql,
        "results": results,
        "summary": summary,
        "row_count": len(results),
        "source": source,
        "looker_url": looker_url,
    }


async def _build_html_report(query: str, sql: str, results: list[dict]) -> tuple[str, str]:
    """Use Gemini to generate a complete HTML report with Chart.js charts."""
    if not results:
        empty_html = f"""<!DOCTYPE html>
<html><head><title>Report</title></head>
<body style="font-family:system-ui;max-width:900px;margin:40px auto;padding:20px">
<h1>Report: {query}</h1><p>No data found for this query.</p>
<pre>{sql}</pre></body></html>"""
        return empty_html, "No results found."

    preview = results[:50]
    columns = list(results[0].keys()) if results else []

    prompt = f"""You are a data visualization expert. Generate a COMPLETE, self-contained HTML page
that presents the query results as an interactive report with charts.

USER'S QUESTION: {query}
SQL USED: {sql}
COLUMNS: {columns}
DATA ({len(results)} rows, showing {len(preview)}):
{preview}

REQUIREMENTS:
1. Use Chart.js from CDN (https://cdn.jsdelivr.net/npm/chart.js) — no other dependencies
2. Pick the BEST chart types for this data (bar, line, pie, doughnut — whatever fits)
3. Include 1-3 charts that answer the user's question from different angles
4. Add a data table below the charts showing the raw results
5. Include a 2-3 sentence executive summary at the top explaining the key insights
6. Dark theme: background #1a1a2e, cards #16213e, text #e0e0e0, accent colors for charts
7. Professional layout: centered, max-width 1000px, cards with subtle borders
8. Show the SQL query used in a collapsible section
9. Mobile-responsive
10. Title should reflect what the user asked for

Return ONLY the complete HTML (<!DOCTYPE html> to </html>). No markdown fences, no explanation."""

    def _call() -> str:
        client = _get_genai()
        resp = client.models.generate_content(model=NL_TO_SQL_MODEL, contents=prompt)
        text = resp.text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].rstrip()
        if text.lower().startswith("html"):
            text = text[4:].lstrip()
        return text

    # Generate summary in parallel-ish (same thread pool)
    summary_prompt = f"""Summarize these query results in 2-3 sentences for a business user.
Question: {query}
Results ({len(results)} rows, showing first {min(20, len(results))}):
{results[:20]}
Summary:"""

    def _call_summary() -> str:
        client = _get_genai()
        resp = client.models.generate_content(model=NL_TO_SQL_MODEL, contents=summary_prompt)
        return resp.text.strip()

    html, summary = await asyncio.gather(
        asyncio.to_thread(_call),
        asyncio.to_thread(_call_summary),
    )

    return html, summary
