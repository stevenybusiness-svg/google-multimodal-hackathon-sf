"""
Document management — tracks a living marketing brief and applies revisions
using Gemini. Uploads to Slack as a file.
"""
import asyncio
import logging
import os
import re

from google import genai

logger = logging.getLogger(__name__)

REVISION_MODEL = "gemini-3-flash-preview"
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _client


MARKETING_BRIEF = """\
# Product Launch Marketing Brief

## Campaign: Q2 2026 Product Launch

**Product:** AI Meeting Intelligence Platform
**Launch Date:** April 15, 2026
**Status:** DRAFT — Pending team review

---

## Target Audience
- Enterprise teams (50+ employees)
- Remote-first companies
- Product and engineering teams

## Key Messages
1. "Never miss an action item again"
2. "AI that works during your meetings so you can focus on the conversation"
3. "From discussion to action in real-time"

## Marketing Channels
- LinkedIn (primary B2B channel)
- Product Hunt launch
- Tech blog partnerships
- Email campaign to existing waitlist

## Budget Breakdown
| Category | Amount |
|---|---|
| Digital advertising | $25,000 |
| Content creation | $10,000 |
| Event sponsorship | $15,000 |
| **Total** | **$50,000** |

## Timeline
- **Week 1-2:** Teaser campaign
- **Week 3:** Product Hunt launch
- **Week 4:** Full marketing push
- **Week 5-8:** Sustained campaign

## Success Metrics
- 1,000 sign-ups in first month
- 50 enterprise trials
- 15 press mentions
"""


def _strip_markdown_fences(text: str) -> str:
    fence = re.search(r"```(?:markdown)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return text


async def revise_document(original: str, revisions: list[dict]) -> str:
    """Apply revisions to the marketing brief using Gemini."""
    changes = "\n".join(
        f"- {r.get('change', r.get('summary', str(r)))}" for r in revisions
    )
    prompt = (
        "You are a document editor. Apply the following revisions to this "
        "marketing brief. Make the changes directly. Keep the same markdown "
        "format and structure. Only change what the revisions specify. "
        "Return ONLY the updated document with no commentary.\n\n"
        "CRITICAL MATH RULES:\n"
        "- Match category names loosely: 'digital marketing' and 'digital advertising' both refer to the 'Digital advertising' row.\n"
        "- When reallocating between categories, subtract from source AND add to destination.\n"
        "- Example: reallocate $5,000 from Content creation to Digital advertising → Content creation $10,000−$5,000=$5,000; Digital advertising $25,000+$5,000=$30,000.\n"
        "- ALWAYS recalculate the Total row. Do NOT change any values not mentioned in the revisions.\n\n"
        f"REVISIONS:\n{changes}\n\n"
        f"DOCUMENT:\n{original}"
    )
    for attempt in range(3):
        try:
            resp = await _get_client().aio.models.generate_content(
                model=REVISION_MODEL,
                contents=prompt,
            )
            text = _strip_markdown_fences((resp.text or "").strip())
            return text if text else original
        except Exception as exc:
            is_rate_limit = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
            if is_rate_limit and attempt < 2:
                err_str = str(exc)
                wait = 2 ** (attempt + 1)  # 2s, 4s default
                delay_match = re.search(r"retryDelay.*?(\d+)", err_str)
                if delay_match:
                    wait = min(int(delay_match.group(1)), 35)
                logger.warning("Document revision rate-limited (attempt %d/3) — retrying in %ds", attempt + 1, wait)
                await asyncio.sleep(wait)
                continue
            logger.error("Document revision failed: %s (attempt %d)", exc, attempt + 1)
            return original
