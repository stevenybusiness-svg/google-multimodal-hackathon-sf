import asyncio
import json
import logging
import os
import re
from collections.abc import Callable
from datetime import datetime, timezone
from google import genai

from backend.contracts import UnderstandingResult, empty_understanding

logger = logging.getLogger(__name__)

_client: genai.Client | None = None

def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _client

UNDERSTANDING_MODEL = "gemini-3-flash-preview"
_gemini_sem = asyncio.Semaphore(4)

UNDERSTAND_PROMPT = """You are a meeting assistant. The current date/time is {now_iso} (user timezone: America/New_York, i.e. US Eastern Time).

Given a transcript segment and optional face sentiment, extract:
- commitments: things someone said they will do ("I will X by Y")
- agreements: things the group decided ("We agreed X")
- meeting_requests: explicit requests to schedule a meeting ("Let's meet Tuesday", "Can we sync?")
- document_revisions: specific changes to a marketing document being discussed ("change the budget to 75K", "update the target audience", "revise the timeline", "add social media to channels")
- sentiment: combined text + face sentiment (positive / neutral / negative / uncertain)

DATE/TIME RULES (CRITICAL):
- ALWAYS resolve relative dates to absolute ISO 8601. "Tuesday" = next Tuesday. "tomorrow" = the day after {now_iso}. "at 1pm" = 13:00 in Eastern Time.
- Use the timezone offset -04:00 for EDT or -05:00 for EST.
- Example: if today is Monday 2026-03-16 and someone says "Tuesday at 1pm", the when should be "2026-03-17T13:00:00-04:00".
- NEVER return null for "when" if any time or day reference was spoken. Make your best guess.

BREVITY RULES (CRITICAL — judges will see these):
- "what" fields: max 12 words, action-verb form ("Send deck to Sarah", not "I will send the updated deck over to Sarah by end of day")
- "summary" fields: max 15 words
- "change" fields: max 10 words ("Update budget to $75K")
- Strip filler, hedging, and redundancy

SENTIMENT RULES (CRITICAL — used to gate whether actions are taken):
- Confident, affirmative statements ("sounds amazing", "let's do it", "add it to calendar") → "positive"
- Neutral/factual statements, no explicit direction given → "neutral"
- Speaker explicitly cancels or opposes ("let's not", "don't do that", "actually skip it") → "negative"
- Speaker is genuinely unsure without resolving ("not sure", "maybe", "I guess") → "uncertain"
- IMPORTANT: Each meeting_request / commitment gets its OWN sentiment — don't let one item's tone bleed into another
- If speaker says "yes to 1pm, no to 4pm" → 1pm sentiment "positive", 4pm sentiment "negative"
- text/face conflict → document in "note"

Return ONLY valid JSON (no markdown fences):
{{
  "commitments": [{{"owner": "name or speaker", "what": "...", "by_when": "ISO 8601 datetime or null", "sentiment": "...", "note": "..."}}],
  "agreements": [{{"summary": "...", "sentiment": "..."}}],
  "meeting_requests": [{{"summary": "...", "attendees": [], "when": "ISO 8601 datetime — ALWAYS resolve relative dates", "sentiment": "..."}}],
  "document_revisions": [{{"change": "specific change to apply", "section": "which section of the document to change"}}],
  "sentiment": "positive|neutral|negative|uncertain"
}}

If nothing found: {{"commitments": [], "agreements": [], "meeting_requests": [], "document_revisions": [], "sentiment": "neutral"}}

TRANSCRIPT:
{transcript}

FACE SENTIMENT:
{face_context}
"""

def _strip_json_fences(text: str) -> str:
    fence = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return text


def _empty() -> UnderstandingResult:
    """Fresh empty result — never return a shared mutable object."""
    return empty_understanding()

# Public alias for import compat (read-only reference only)
EMPTY = _empty()


async def understand_transcript(transcript: str, face_sentiment: dict | None = None) -> UnderstandingResult:
    if not transcript.strip():
        return _empty()
    face_context = "None"
    if face_sentiment:
        face_context = (
            f"Face emotion: {face_sentiment.get('sentiment', 'neutral')}, "
            f"Engagement: {face_sentiment.get('engagement', 0):.2f}"
        )
    text = ""
    for attempt in range(3):
        try:
            async with _gemini_sem:
                now_iso = datetime.now(timezone.utc).isoformat()
                response = await _get_client().aio.models.generate_content(
                    model=UNDERSTANDING_MODEL,
                    contents=UNDERSTAND_PROMPT.format(
                        transcript=transcript,
                        face_context=face_context,
                        now_iso=now_iso,
                    ),
                )
            text = _strip_json_fences((response.text or "").strip())
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("GEMINI_JSON_FAIL: %s | full_raw: %s", e, text)
            return _empty()
        except Exception as e:
            is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if is_rate_limit and attempt < 2:
                # Parse retryDelay from error if available, otherwise use exponential backoff
                err_str = str(e)
                wait = 2 ** (attempt + 1)  # 2s, 4s default
                import re as _re
                delay_match = _re.search(r"retryDelay.*?(\d+)", err_str)
                if delay_match:
                    wait = min(int(delay_match.group(1)), 35)  # cap at 35s
                logger.warning("GEMINI_RATE_LIMIT (attempt %d/3): retrying in %ds", attempt + 1, wait)
                await asyncio.sleep(wait)
                continue
            logger.error("GEMINI_CALL_FAIL: %s (model=%s, transcript_len=%d, attempt=%d)", e, UNDERSTANDING_MODEL, len(transcript), attempt + 1)
            return _empty()


class TranscriptBuffer:
    """Per-session buffer that accumulates transcript segments and flushes to understanding.

    Batches aggressively to minimize Gemini API calls:
    - Waits 8s after last segment before flushing (coalesces related speech)
    - Won't flush unless buffer has >= 80 chars (avoids wasting calls on "okay" / "sure")
    - Hard flush at 600 chars (don't let buffer grow unbounded)
    - End-of-meeting flush() ignores minimums
    """

    _COOLDOWN_S = 2.0   # wait 2s of silence before flushing (real-time feel)
    _MIN_FLUSH_CHARS = 30  # flush even short segments for responsiveness

    def __init__(self) -> None:
        self._buf = ""
        self._pending_task: asyncio.Task | None = None
        self._flush_tasks: set[asyncio.Task] = set()
        self._face: dict | None = None
        self._on_result: Callable | None = None

    async def process(self, text: str, face_sentiment: dict | None = None,
                      on_result: Callable | None = None) -> UnderstandingResult | None:
        self._buf += " " + text if self._buf else text
        self._face = face_sentiment
        self._on_result = on_result

        # Hard flush at 600 chars to avoid unbounded growth
        if len(self._buf.strip()) > 600:
            return await self._do_flush()

        # Cancel the cooldown sleep and start a new one.
        # Only the sleep is cancellable — once a flush starts, it runs independently.
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
        self._pending_task = asyncio.create_task(self._cooldown_flush())
        return None

    async def _cooldown_flush(self) -> None:
        """Wait for cooldown, then spawn an independent flush task."""
        try:
            await asyncio.sleep(self._COOLDOWN_S)
        except asyncio.CancelledError:
            return  # new segment arrived, cooldown restarted

        if len(self._buf.strip()) < self._MIN_FLUSH_CHARS:
            logger.debug("Cooldown fired but buffer too short (%d chars) — holding", len(self._buf.strip()))
            return

        # Spawn flush as independent task so it survives cancellation
        # when new segments arrive or meeting ends
        t = asyncio.create_task(self._execute_flush())
        self._flush_tasks.add(t)
        t.add_done_callback(self._flush_tasks.discard)

    async def _execute_flush(self) -> None:
        """Run flush + deliver result via callback. Independent of cooldown lifecycle."""
        try:
            result = await self._do_flush()
            if result is not None and self._on_result:
                await self._on_result(result)
        except Exception as exc:
            logger.error("Background flush failed: %s", exc)

    async def _do_flush(self) -> UnderstandingResult | None:
        if not self._buf.strip():
            return None
        segment, self._buf = self._buf, ""
        logger.info("Flushing buffer (%d chars)", len(segment))
        return await understand_transcript(segment, self._face)

    async def flush(self, face_sentiment: dict | None = None) -> UnderstandingResult | None:
        """Force-flush any remaining buffered text (e.g. at end of meeting)."""
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()

        # Wait for any in-progress Gemini calls from cooldown flushes
        if self._flush_tasks:
            logger.info("Waiting for %d in-progress flush task(s)...", len(self._flush_tasks))
            await asyncio.gather(*self._flush_tasks, return_exceptions=True)

        if not self._buf.strip():
            return None
        segment, self._buf = self._buf, ""
        logger.info("Force-flushing buffer (%d chars)", len(segment))
        return await understand_transcript(segment, face_sentiment)

    def reset(self) -> None:
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
        self._buf = ""
        logger.debug("TranscriptBuffer reset")
