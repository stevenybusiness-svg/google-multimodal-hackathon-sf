"""DigitalOcean Gradient AI integration — cross-meeting memory.

Uses DO Agent API (OpenAI-compatible) backed by a Knowledge Base to archive
meeting transcripts+actions and retrieve relevant past context.  Env vars:
DO_AGENT_ENDPOINT, DO_AGENT_ACCESS_KEY, DO_MODEL_ACCESS_KEY, DO_SPACES_BUCKET.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# -- Configuration ----------------------------------------------------------

_DO_AGENT_ENDPOINT = os.getenv("DO_AGENT_ENDPOINT", "")
_DO_AGENT_ACCESS_KEY = os.getenv("DO_AGENT_ACCESS_KEY", "")
_DO_MODEL_ACCESS_KEY = os.getenv("DO_MODEL_ACCESS_KEY", "")
_DO_SPACES_BUCKET = os.getenv("DO_SPACES_BUCKET", "")

_client: AsyncOpenAI | None = None


def do_available() -> bool:
    """Return True if the required DO env vars are configured."""
    return bool(_DO_AGENT_ENDPOINT and _DO_AGENT_ACCESS_KEY)


def _get_client() -> AsyncOpenAI | None:
    """Lazy-init the AsyncOpenAI client pointed at the DO Agent endpoint."""
    global _client
    if _client is not None:
        return _client
    if not do_available():
        logger.warning(
            "DO_AGENT_ENDPOINT or DO_AGENT_ACCESS_KEY not set — "
            "DigitalOcean memory disabled."
        )
        return None
    _client = AsyncOpenAI(
        base_url=f"{_DO_AGENT_ENDPOINT.rstrip('/')}/api/v1",
        api_key=_DO_AGENT_ACCESS_KEY,
    )
    return _client


# -- Archive: push meeting data into the KB via the Agent ------------------

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
    """Archive transcript + actions to DO Knowledge Base via the Agent API.

    Returns the agent's confirmation text, or None on failure.
    """
    client = _get_client()
    if client is None:
        return None

    document = _format_meeting_document(session_id, transcript_segments, actions)
    prompt = (
        "Store the following meeting record in your knowledge base for future "
        "retrieval. Confirm once stored.\n\n"
        f"{document}"
    )

    try:
        response = await client.chat.completions.create(
            model="n/a",  # agent endpoint ignores model param
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.choices[0].message.content
        logger.info("DO archive OK for session %s (%d chars)", session_id, len(document))
        return result
    except Exception:
        logger.exception("DO archive failed for session %s", session_id)
        return None


# -- Query: retrieve relevant past-meeting context -------------------------

async def do_query_meeting_memory(transcript: str) -> str:
    """Query the DO Agent for relevant past meeting context.

    Returns a string suitable for injecting into the Gemini understanding
    prompt, or an empty string if unavailable.
    """
    client = _get_client()
    if client is None:
        return ""

    query = (
        "Based on the following live meeting transcript excerpt, what open "
        "commitments, prior decisions, or unresolved items exist from past "
        "meetings that are relevant? Be concise.\n\n"
        f"Transcript:\n{transcript}"
    )

    try:
        response = await client.chat.completions.create(
            model="n/a",
            messages=[{"role": "user", "content": query}],
        )
        result = response.choices[0].message.content or ""
        logger.info("DO memory query returned %d chars", len(result))
        return result
    except Exception:
        logger.exception("DO memory query failed")
        return ""
