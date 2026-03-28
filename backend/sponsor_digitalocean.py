"""DigitalOcean Gradient AI integration — cross-meeting memory.

Uses DO Serverless Inference (OpenAI-compatible) for chat/query and
in-memory transcript store for Knowledge Base functionality.
Sample meeting data is loaded from sample_data/ at startup.

Env vars: DO_MODEL_ACCESS_KEY (required), DO_SPACES_BUCKET (optional).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# -- Configuration ----------------------------------------------------------

_DO_MODEL_ACCESS_KEY = os.getenv("DO_MODEL_ACCESS_KEY", "")
_DO_SPACES_BUCKET = os.getenv("DO_SPACES_BUCKET", "")

_client: AsyncOpenAI | None = None

# In-memory knowledge base: list of meeting documents
_knowledge_base: list[str] = []


def do_available() -> bool:
    """Return True if DO inference is configured."""
    return bool(_DO_MODEL_ACCESS_KEY)


def _get_client() -> AsyncOpenAI | None:
    """Lazy-init AsyncOpenAI client pointed at DO Serverless Inference."""
    global _client
    if _client is not None:
        return _client
    if not _DO_MODEL_ACCESS_KEY:
        logger.warning("DO_MODEL_ACCESS_KEY not set — DigitalOcean disabled.")
        return None
    _client = AsyncOpenAI(
        base_url="https://inference.do-ai.run/v1/",
        api_key=_DO_MODEL_ACCESS_KEY,
    )
    return _client


def _load_sample_data():
    """Load sample meeting transcripts from sample_data/ into the KB."""
    sample_dir = Path(__file__).parent.parent / "sample_data"
    if not sample_dir.exists():
        return
    for f in sorted(sample_dir.glob("*.md")):
        content = f.read_text()
        _knowledge_base.append(content)
        logger.info("KB loaded: %s (%d chars)", f.name, len(content))
    logger.info("Knowledge base: %d documents loaded", len(_knowledge_base))


# Load sample data on import
_load_sample_data()


def kb_stats() -> dict:
    """Return KB stats for the UI."""
    return {"documents": len(_knowledge_base), "available": len(_knowledge_base) > 0}


# -- Archive: store meeting transcript in KB --------------------------------

def _format_meeting_document(
    session_id: str,
    transcript_segments: list[dict],
    actions: list[dict],
) -> str:
    """Build a structured text document for KB ingestion."""
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Meeting Record — {session_id}",
        f"Archived: {ts}",
        "",
        "## Transcript",
    ]
    for seg in transcript_segments:
        speaker = seg.get("speaker", "Unknown")
        text = seg.get("text", "")
        lines.append(f"- [{speaker}] {text}")

    lines.append("")
    lines.append("## Extracted Actions")
    for action in actions:
        lines.append(f"- {json.dumps(action, default=str)}")

    return "\n".join(lines)


async def do_archive_meeting(
    session_id: str,
    transcript_segments: list[dict],
    actions: list[dict],
) -> str | None:
    """Archive transcript + actions to in-memory Knowledge Base.

    Returns confirmation text, or None on failure.
    """
    document = _format_meeting_document(session_id, transcript_segments, actions)
    _knowledge_base.append(document)
    logger.info("KB archived: session %s (%d chars, total %d docs)",
                session_id, len(document), len(_knowledge_base))
    return f"Archived meeting {session_id} ({len(document)} chars)"


async def do_archive_report(report: dict) -> str | None:
    """Archive a generated report to the Knowledge Base."""
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Report — {report.get('report_id', 'unknown')}",
        f"Generated: {ts}",
        f"Query: {report.get('query', '')}",
        "",
        f"## SQL\n{report.get('sql', '')}",
        "",
        f"## Summary\n{report.get('summary', '')}",
        "",
        f"## Results ({report.get('row_count', 0)} rows)",
    ]
    for row in (report.get("results") or [])[:20]:
        lines.append(f"- {json.dumps(row, default=str)}")
    document = "\n".join(lines)
    _knowledge_base.append(document)
    logger.info("KB archived report: %s (%d chars, total %d docs)",
                report.get("report_id"), len(document), len(_knowledge_base))
    return f"Archived report {report.get('report_id')} ({len(document)} chars)"


# -- Chat: query KB via DO inference ----------------------------------------

def _build_kb_context(limit: int = 5) -> str:
    """Build a context string from the most recent KB documents."""
    recent = _knowledge_base[-limit:]
    if not recent:
        return "No meeting data available in the knowledge base."
    return "\n\n---\n\n".join(recent)


async def do_chat(message: str) -> str:
    """Chat with the Knowledge Base using DO Serverless Inference."""
    client = _get_client()
    if client is None:
        return "DigitalOcean inference not configured."

    kb_context = _build_kb_context()

    try:
        response = await client.chat.completions.create(
            model="llama3.3-70b-instruct",
            messages=[
                {"role": "system", "content": (
                    "You are a meeting knowledge base assistant. Answer questions "
                    "based on the meeting records below. Be concise and specific. "
                    "If the answer isn't in the records, say so.\n\n"
                    f"MEETING RECORDS:\n{kb_context}"
                )},
                {"role": "user", "content": message},
            ],
        )
        result = response.choices[0].message.content or ""
        logger.info("DO chat: %d chars response for: %.80s", len(result), message)
        return result
    except Exception:
        logger.exception("DO chat failed")
        return "Sorry, I couldn't process that query. Please try again."


async def do_query_meeting_memory(transcript: str) -> str:
    """Query KB for relevant past meeting context (injected into Gemini prompt)."""
    if not _knowledge_base:
        return ""

    client = _get_client()
    if client is None:
        return ""

    kb_context = _build_kb_context(limit=3)

    try:
        response = await client.chat.completions.create(
            model="llama3.3-70b-instruct",
            messages=[
                {"role": "system", "content": (
                    "Given these past meeting records, extract any open commitments, "
                    "prior decisions, or unresolved items relevant to the current "
                    "transcript. Be concise (3-5 bullet points max). If nothing "
                    "relevant, say 'No prior context.'\n\n"
                    f"PAST MEETINGS:\n{kb_context}"
                )},
                {"role": "user", "content": f"Current transcript:\n{transcript}"},
            ],
        )
        result = response.choices[0].message.content or ""
        logger.info("DO memory query: %d chars", len(result))
        return result
    except Exception:
        logger.exception("DO memory query failed")
        return ""
