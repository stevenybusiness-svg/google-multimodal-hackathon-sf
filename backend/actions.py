import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.contracts import (
    ActionResult,
    UnderstandingResult,
    make_action_result,
)
from backend.documents import MARKETING_BRIEF, revise_document

logger = logging.getLogger(__name__)

# Lazy-init — don't crash at import if env var is missing
_slack: AsyncWebClient | None = None


def _get_slack() -> AsyncWebClient | None:
    global _slack
    if _slack is None:
        token = os.getenv("SLACK_BOT_TOKEN")
        if token:
            _slack = AsyncWebClient(token=token)
        else:
            logger.warning("SLACK_BOT_TOKEN not set — Slack actions will be skipped.")
    return _slack


SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#meeting-actions")
_RISK = {"negative", "uncertain"}
_NEGATIVE_FACES = {"anger", "sadness"}


_calendar_creds: Credentials | None = None


def get_calendar_service(token_dict: dict):
    global _calendar_creds
    _calendar_creds = Credentials(**token_dict)
    # Return a service to verify credentials are valid at startup
    return build("calendar", "v3", credentials=_calendar_creds)


def _build_calendar_service():
    """Build a fresh service per call — googleapiclient Resource is not thread-safe."""
    return build("calendar", "v3", credentials=_calendar_creds)


async def _resolve_channel_id(client: AsyncWebClient, channel_name: str) -> str | None:
    """Resolve a channel name (e.g. '#product-launch') to its Slack channel ID."""
    name = channel_name.lstrip("#")
    try:
        cursor = None
        while True:
            kwargs: dict = {"types": "public_channel", "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            resp = await client.conversations_list(**kwargs)
            for ch in resp["channels"]:
                if ch["name"] == name:
                    return ch["id"]
            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
    except Exception as exc:
        logger.error("conversations_list failed: %s", exc)
    return None


async def _post_slack(text: str) -> ActionResult:
    client = _get_slack()
    if client is None:
        logger.warning("Slack not configured — skipping: %.80s", text)
        return make_action_result("slack", {"text": text}, "skipped", "Slack not configured")
    try:
        await client.chat_postMessage(channel=SLACK_CHANNEL, text=text)
        logger.info("Slack posted: %s", text[:80])
        return make_action_result("slack", {"text": text}, "sent")
    except SlackApiError as exc:
        error_code = exc.response.get("error", "") if exc.response else ""
        if error_code == "not_in_channel":
            # Auto-join the channel and retry
            try:
                channel_id = await _resolve_channel_id(client, SLACK_CHANNEL)
                if channel_id:
                    await client.conversations_join(channel=channel_id)
                    logger.info("Auto-joined Slack channel: %s (%s)", SLACK_CHANNEL, channel_id)
                    await client.chat_postMessage(channel=SLACK_CHANNEL, text=text)
                    logger.info("Slack posted (after join): %s", text[:80])
                    return {"type": "slack", "payload": {"text": text}, "status": "sent"}
                else:
                    logger.error("Could not resolve channel: %s", SLACK_CHANNEL)
            except Exception as join_exc:
                logger.error("Slack auto-join + retry failed: %s", join_exc)
                return make_action_result("slack", {"text": text}, "failed", str(join_exc))
        logger.error("Slack post failed: %s", exc)
        return make_action_result("slack", {"text": text}, "failed", str(exc))
    except Exception as exc:
        logger.error("Slack post failed: %s", exc)
        return make_action_result("slack", {"text": text}, "failed", str(exc))


_channel_id_cache: dict[str, str] = {}


async def _get_channel_id(client: AsyncWebClient, channel_name: str) -> str | None:
    """Resolve and cache the channel ID for a channel name."""
    if channel_name in _channel_id_cache:
        return _channel_id_cache[channel_name]
    channel_id = await _resolve_channel_id(client, channel_name)
    if channel_id:
        _channel_id_cache[channel_name] = channel_id
    return channel_id


async def _post_slack_document(content: str, filename: str, title: str, comment: str) -> ActionResult:
    """Upload a document to Slack as a file attachment, falling back to message if upload fails."""
    client = _get_slack()
    if client is None:
        logger.warning("Slack not configured — skipping document post: %s", filename)
        return make_action_result("document", {"filename": filename}, "skipped", "Slack not configured")

    async def _try_upload(channel: str) -> ActionResult:
        await client.files_upload_v2(
            channel=channel,
            content=content,
            filename=filename,
            title=title,
            initial_comment=comment,
        )
        logger.info("Slack document uploaded: %s to %s", filename, SLACK_CHANNEL)
        return make_action_result("document", {"filename": filename, "title": title}, "sent")

    async def _fallback_message() -> ActionResult:
        """Post document as a code block message when file upload is unavailable."""
        preview = content[:2000] + ("\n...(truncated)" if len(content) > 2000 else "")
        text = f"{comment}\n```\n{preview}\n```"
        try:
            await client.chat_postMessage(channel=SLACK_CHANNEL, text=text)
            logger.info("Slack document posted as message (fallback): %s", filename)
            return make_action_result("document", {"filename": filename, "title": title}, "sent")
        except Exception as msg_exc:
            logger.error("Slack fallback message also failed: %s", msg_exc)
            return make_action_result("document", {"filename": filename}, "failed", str(msg_exc))

    try:
        channel_id = await _get_channel_id(client, SLACK_CHANNEL)
        if not channel_id:
            logger.warning("Could not resolve channel ID for %s — trying message fallback", SLACK_CHANNEL)
            return await _fallback_message()
        return await _try_upload(channel_id)
    except SlackApiError as exc:
        error_code = exc.response.get("error", "") if exc.response else ""
        if error_code == "not_in_channel":
            try:
                channel_id = await _get_channel_id(client, SLACK_CHANNEL)
                if channel_id:
                    await client.conversations_join(channel=channel_id)
                    logger.info("Auto-joined Slack channel: %s", SLACK_CHANNEL)
                    return await _try_upload(channel_id)
            except Exception as join_exc:
                logger.error("Document upload after join failed: %s — trying fallback", join_exc)
                return await _fallback_message()
        if error_code in ("missing_scope", "not_allowed_token_type"):
            logger.warning("File upload scope missing — falling back to message: %s", error_code)
            return await _fallback_message()
        logger.error("Slack document upload failed: %s", exc)
        return make_action_result("document", {"filename": filename}, "failed", str(exc))
    except Exception as exc:
        logger.error("Slack document upload failed: %s — trying fallback", exc)
        return await _fallback_message()


_MEETING_DURATION = timedelta(hours=1)


async def create_calendar_event(
    summary: str, when: str | None,
    attendees: list[str] | None = None, sentiment: str = "neutral"
) -> dict:
    description = "Created automatically by meeting agent."
    if sentiment in _RISK:
        description += " ⚠️ Sentiment flagged — confirm this meeting."

    try:
        start_dt = datetime.fromisoformat(when) if when else datetime.now(timezone.utc)
    except ValueError:
        logger.warning("Cannot parse when=%r as ISO 8601, using now", when)
        start_dt = datetime.now(timezone.utc)

    end_dt = start_dt + _MEETING_DURATION

    # Filter attendees to valid email addresses only (Gemini may return names, not emails)
    import re as _re
    valid_emails = [e for e in (attendees or []) if _re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', e)]

    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/New_York"},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "America/New_York"},
    }
    if valid_emails:
        event["attendees"] = [{"email": e} for e in valid_emails]
    logger.info("Creating calendar event: %s at %s", summary, start_dt.isoformat())

    # Refresh credentials proactively — expired tokens cause hangs in to_thread
    import google.auth.transport.requests
    if _calendar_creds and _calendar_creds.expired and _calendar_creds.refresh_token:
        logger.info("Refreshing expired calendar credentials...")
        _calendar_creds.refresh(google.auth.transport.requests.Request())
        logger.info("Calendar credentials refreshed successfully.")

    svc = _build_calendar_service()
    result = await asyncio.to_thread(
        svc.events().insert(calendarId="primary", body=event).execute
    )
    logger.info("Calendar event created: %s (id=%s)", summary, result.get("id", "?"))
    return result


class ActionSession:
    """Per-session action dispatcher. Holds the task log for one meeting session."""

    _DOC_REVISION_COOLDOWN_S = 10.0  # ignore duplicate-ish revisions within this window

    def __init__(self, session_id: str = "") -> None:
        self._session_id = session_id
        self._task_log: list[dict] = []
        self._current_doc: str = MARKETING_BRIEF
        self._doc_version: int = 0
        self._applied_changes: set[str] = set()  # dedup by change text
        self._last_revision_time: float = 0.0
        self._doc_lock = asyncio.Lock()

    @property
    def task_log(self) -> list[dict]:
        return list(self._task_log)

    @staticmethod
    def _face_is_negative(face_sentiment: dict | None) -> bool:
        if not face_sentiment:
            return False
        return face_sentiment.get("sentiment") in _NEGATIVE_FACES

    @staticmethod
    def _should_block(text_sentiment: str, face_sentiment: dict | None) -> bool:
        """Primary gate: text sentiment. Face is supplemental signal for uncertain cases.
        - "negative" (explicit verbal opposition / cancellation) → always block
        - "uncertain" + face frowning → block (face breaks the tie)
        - "positive" / "neutral" → always proceed (even if face frowns)
        """
        if text_sentiment == "negative":
            return True
        if text_sentiment == "uncertain":
            return bool(face_sentiment and face_sentiment.get("sentiment") in _NEGATIVE_FACES)
        return False

    async def dispatch(self, understanding: UnderstandingResult, has_calendar: bool = False,
                       face_sentiment: dict | None = None) -> list[ActionResult]:
        actions: list[ActionResult] = []
        for c in understanding.get("commitments", []):
            actions.extend(await self._commitment(c, face_sentiment))
        for a in understanding.get("agreements", []):
            actions.extend(await self._agreement(a, face_sentiment))
        for r in understanding.get("meeting_requests", []):
            actions.extend(await self._meeting_request(r, has_calendar, face_sentiment))
        revisions = understanding.get("document_revisions", [])
        if revisions:
            actions.extend(await self._document_revision(revisions))
        return actions

    async def _commitment(self, c: dict, face_sentiment: dict | None = None) -> list[ActionResult]:
        owner = c.get("owner", "Unknown")
        what  = c.get("what", "")
        when  = c.get("by_when")
        sent  = c.get("sentiment", "neutral")

        entry = {"type": "task", "owner": owner, "what": what, "by_when": when, "sentiment": sent}
        self._task_log.append(entry)

        if self._should_block(sent, face_sentiment):
            logger.info("Commitment BLOCKED (face=%s, text=%s): %s", face_sentiment, sent, what)
            return [make_action_result("task", entry, "blocked")]

        return [make_action_result("task", entry, "logged")]

    async def _agreement(self, a: dict, face_sentiment: dict | None = None) -> list[ActionResult]:
        summary = a.get("summary", "")
        sent    = a.get("sentiment", "neutral")

        if self._should_block(sent, face_sentiment):
            logger.info("Agreement BLOCKED (face=%s, text=%s): %s", face_sentiment, sent, summary)
            return [make_action_result("task", {"summary": summary, "sentiment": sent}, "blocked")]

        return [make_action_result("task", {"summary": summary, "sentiment": sent}, "logged")]

    async def _meeting_request(self, r: dict, has_calendar: bool = False,
                               face_sentiment: dict | None = None) -> list[ActionResult]:
        summary   = r.get("summary", "Meeting")
        attendees = r.get("attendees")
        when      = r.get("when")
        sent      = r.get("sentiment", "neutral")

        if self._should_block(sent, face_sentiment):
            logger.info("Meeting request BLOCKED (face=%s, text=%s): %s", face_sentiment, sent, summary)
            return [make_action_result("calendar", {"summary": summary, "when": when}, "blocked")]

        if has_calendar and _calendar_creds is not None:
            try:
                event = await create_calendar_event(summary, when, attendees, sent)
                return [make_action_result("calendar", event, "sent")]
            except Exception as exc:
                logger.error("Calendar event failed: %s", exc)
                return [make_action_result("calendar", {"summary": summary}, "failed", str(exc))]

        # No calendar configured — log only
        logger.info("Meeting requested (no calendar): %s", summary)
        return []

    async def _document_revision(self, revisions: list[dict]) -> list[ActionResult]:
        async with self._doc_lock:
            return await self._document_revision_locked(revisions)

    @staticmethod
    def _word_set(text: str) -> set[str]:
        return set(text.strip().lower().split())

    def _is_duplicate_change(self, candidate: str) -> bool:
        """Fuzzy dedup: if >50% of words overlap with any prior change, treat as duplicate."""
        words = self._word_set(candidate)
        if not words:
            return False
        for existing in self._applied_changes:
            existing_words = self._word_set(existing)
            overlap = len(words & existing_words)
            if overlap / max(len(words), 1) > 0.5 or overlap / max(len(existing_words), 1) > 0.5:
                return True
        return False

    async def _document_revision_locked(self, revisions: list[dict]) -> list[ActionResult]:
        import time
        now = time.monotonic()

        # Temporal cooldown: skip if we just applied a revision
        if self._last_revision_time and (now - self._last_revision_time) < self._DOC_REVISION_COOLDOWN_S:
            logger.info("Document revision skipped — cooldown (%.1fs since last)",
                        now - self._last_revision_time)
            return []

        # Deduplicate: skip revisions whose change text fuzzy-matches an already-applied change
        new_revisions = []
        for r in revisions:
            key = r.get("change", "").strip().lower()
            if key and not self._is_duplicate_change(key):
                self._applied_changes.add(key)
                new_revisions.append(r)
        if not new_revisions:
            logger.info("Document revision skipped — all changes already applied")
            return []
        revisions = new_revisions
        self._last_revision_time = now

        self._doc_version += 1
        version = self._doc_version

        changes_summary = ", ".join(r.get("change", "update") for r in revisions)
        logger.info("Applying document revisions (v%d): %s", version, changes_summary[:120])

        revised = await revise_document(self._current_doc, revisions)
        self._current_doc = revised

        filename = f"marketing_brief_v{version}.md"
        title = f"Marketing Brief v{version}"
        comment = f"Here is the updated Marketing Brief (v{version}), attached."

        upload_result = await _post_slack_document(revised, filename, title, comment)
        # Also send a UI-friendly action
        return [
            make_action_result(
                "document",
                {
                    "filename": filename,
                    "title": title,
                    "version": version,
                    "changes": changes_summary,
                    "content": revised,
                },
                upload_result["status"],
                upload_result.get("error"),
            )
        ]
