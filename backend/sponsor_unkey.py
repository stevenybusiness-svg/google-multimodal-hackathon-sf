"""Unkey integration — per-action audit trail + agent kill switch.

Every autonomous action the meeting agent takes (Slack message, Calendar
event, task log, document upload) gets an ephemeral Unkey key with metadata
for auditing.  Keys expire in 24 hours.  The kill switch revokes all keys
for a session, blocking further action verification.

Env vars: UNKEY_ROOT_KEY, UNKEY_API_ID
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from unkey_py import Unkey

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

UNKEY_ROOT_KEY: str | None = os.getenv("UNKEY_ROOT_KEY")
UNKEY_API_ID: str | None = os.getenv("UNKEY_API_ID")

_EXPIRY_MS = 24 * 60 * 60 * 1000  # 24 hours in milliseconds

# In-memory index: session_id -> list of key_ids created for that session.
_session_keys: dict[str, list[str]] = {}

_unkey: Unkey | None = None


def _client() -> Unkey | None:
    """Lazy-init Unkey client. Returns None when creds are missing."""
    global _unkey
    if _unkey is not None:
        return _unkey
    if not UNKEY_ROOT_KEY:
        return None
    _unkey = Unkey(bearer_auth=UNKEY_ROOT_KEY)
    return _unkey


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def unkey_available() -> bool:
    """Return True if both UNKEY_ROOT_KEY and UNKEY_API_ID are set."""
    return bool(UNKEY_ROOT_KEY and UNKEY_API_ID)


async def create_action_audit(
    session_id: str,
    action_type: str,
    payload: str,
    sentiment: str,
) -> dict | None:
    """Create an ephemeral Unkey key to audit a single agent action.

    Returns ``{"key_id": ..., "key": ...}`` on success, or ``None``.
    """
    client = _client()
    if client is None or not UNKEY_API_ID:
        logger.debug("Unkey not configured — skipping audit key creation.")
        return None

    now = datetime.now(timezone.utc)
    expires = int(now.timestamp() * 1000) + _EXPIRY_MS

    meta = {
        "session_id": session_id,
        "action_type": action_type,
        "payload_summary": payload[:100],
        "sentiment": sentiment,
        "timestamp": now.isoformat(),
    }

    try:
        result = await asyncio.to_thread(
            client.keys.create,
            request={
                "api_id": UNKEY_API_ID,
                "name": f"action_{session_id[:8]}_{action_type}",
                "expires": expires,
                "meta": meta,
            },
        )
        key_id = result.key_id
        _session_keys.setdefault(session_id, []).append(key_id)
        logger.info("Audit key created: session=%s type=%s key_id=%s", session_id, action_type, key_id)
        return {"key_id": key_id, "key": result.key}
    except Exception:
        logger.exception("Failed to create Unkey audit key for session=%s", session_id)
        return None


async def get_session_audit(session_id: str) -> list[dict]:
    """List all audit keys created for *session_id*."""
    key_ids = _session_keys.get(session_id, [])
    return [{"key_id": kid, "session_id": session_id} for kid in key_ids]


async def revoke_all_session_keys(session_id: str) -> int:
    """Kill switch — revoke every Unkey key created for *session_id*."""
    client = _client()
    key_ids = _session_keys.pop(session_id, [])
    if not client or not key_ids:
        return 0

    revoked = 0
    for kid in key_ids:
        try:
            await asyncio.to_thread(
                client.keys.delete,
                request={"key_id": kid},
            )
            revoked += 1
        except Exception:
            logger.exception("Failed to revoke key %s for session=%s", kid, session_id)
    logger.info("Revoked %d/%d keys for session=%s", revoked, len(key_ids), session_id)
    return revoked
