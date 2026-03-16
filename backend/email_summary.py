"""Send a meeting summary email via Gmail API at end of meeting."""

import asyncio
import base64
import logging
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.contracts import ActionResult, make_action_result

logger = logging.getLogger(__name__)

RECIPIENTS = ["temuj627@gmail.com", "stevenybusiness@gmail.com"]

_gmail_creds: Credentials | None = None


def init_gmail_creds(creds: Credentials) -> None:
    """Share credentials object initialized by Calendar setup."""
    global _gmail_creds
    _gmail_creds = creds


def _build_gmail_service():
    return build("gmail", "v1", credentials=_gmail_creds)


def _format_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _build_email_body(
    duration_s: float,
    transcript_segments: list[str],
    task_log: list[dict],
    action_results: list[dict],
) -> str:
    lines = ["Meeting Summary", "=" * 40, ""]
    lines.append(f"Duration: {_format_duration(duration_s)}")
    lines.append("")

    if transcript_segments:
        lines.append("--- Transcript ---")
        for seg in transcript_segments[:20]:
            lines.append(f"  {seg.strip()}")
        if len(transcript_segments) > 20:
            lines.append(f"  ... and {len(transcript_segments) - 20} more segments")
        lines.append("")

    if action_results:
        lines.append("--- Actions Taken ---")
        for ar in action_results:
            status = ar.get("status", "?")
            atype = ar.get("type", "?")
            payload = ar.get("payload", {})
            if atype == "calendar":
                desc = payload.get("summary", str(payload)[:80])
            elif atype == "document":
                desc = payload.get("title", payload.get("filename", ""))
            elif atype == "slack":
                desc = (payload.get("text", "") or "")[:80]
            else:
                desc = str(payload)[:80]
            lines.append(f"  [{atype}] {desc} -- {status}")
        lines.append("")

    if task_log:
        lines.append("--- Commitments ---")
        for t in task_log:
            owner = t.get("owner", "?")
            what = t.get("what", "")
            by_when = t.get("by_when", "")
            line = f"  {owner}: {what}"
            if by_when:
                line += f" (by {by_when})"
            lines.append(line)
        lines.append("")

    lines.append("--\nSent automatically by Meeting Agent")
    return "\n".join(lines)


async def send_meeting_summary(
    duration_s: float,
    transcript_segments: list[str],
    task_log: list[dict],
    action_results: list[dict],
) -> ActionResult:
    if _gmail_creds is None:
        logger.warning("Gmail not configured -- skipping summary email")
        return make_action_result("email", {}, "skipped", "Gmail not configured")

    body = _build_email_body(duration_s, transcript_segments, task_log, action_results)

    msg = MIMEText(body)
    msg["To"] = ", ".join(RECIPIENTS)
    msg["Subject"] = f"Meeting Summary ({_format_duration(duration_s)})"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        import google.auth.transport.requests
        # Always refresh if we have a refresh_token — token may be expired or near-expiry
        if _gmail_creds.refresh_token:
            logger.info("Refreshing Gmail credentials (scopes: %s)...", _gmail_creds.scopes)
            _gmail_creds.refresh(google.auth.transport.requests.Request())
            logger.info("Gmail credentials refreshed OK, token valid: %s", not _gmail_creds.expired)

        svc = _build_gmail_service()
        result = await asyncio.to_thread(
            svc.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute
        )
        logger.info("Summary email sent to %s: id=%s", RECIPIENTS, result.get("id", "?"))
        return make_action_result("email", {"to": ", ".join(RECIPIENTS), "message_id": result.get("id")}, "sent")
    except Exception as exc:
        logger.error("Gmail send failed: %s (type=%s)", exc, type(exc).__name__)
        return make_action_result("email", {"to": ", ".join(RECIPIENTS)}, "failed", str(exc))
