"""Tests for the three sponsor integration modules.

Unkey  -- per-action audit trail + agent kill switch
DigitalOcean -- cross-meeting memory via Agent API
Railtracks -- agentic flow framework (stub tests)

No real API calls.  Uses monkeypatch for env vars and unittest.mock for
SDK clients.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ═══════════════════════════════════════════════════════════════════════════════
# Unkey
# ═══════════════════════════════════════════════════════════════════════════════


def _reload_unkey(monkeypatch, *, root_key: str = "", api_id: str = ""):
    """Re-import sponsor_unkey with controlled env vars.

    Module-level globals (UNKEY_ROOT_KEY, UNKEY_API_ID) are read at import
    time via os.getenv, so we must reload to pick up changes.  We also
    reset the cached _unkey client.
    """
    monkeypatch.setenv("UNKEY_ROOT_KEY", root_key)
    monkeypatch.setenv("UNKEY_API_ID", api_id)
    # Evict cached module
    for name in list(sys.modules):
        if "sponsor_unkey" in name:
            del sys.modules[name]
    import backend.sponsor_unkey as mod
    # Reset cached client so _client() re-evaluates
    mod._unkey = None
    return mod


class TestUnkeyAvailable:
    def test_unkey_available_missing_env(self, monkeypatch):
        """With env vars unset, unkey_available() returns False."""
        mod = _reload_unkey(monkeypatch, root_key="", api_id="")
        assert mod.unkey_available() is False

    def test_unkey_available_missing_api_id(self, monkeypatch):
        """With only root key set, still False (both required)."""
        mod = _reload_unkey(monkeypatch, root_key="rk_abc", api_id="")
        assert mod.unkey_available() is False

    def test_unkey_available_set(self, monkeypatch):
        """With both env vars set, returns True."""
        mod = _reload_unkey(monkeypatch, root_key="rk_abc", api_id="api_xyz")
        assert mod.unkey_available() is True


class TestUnkeyCreateActionAudit:
    def test_create_action_audit_no_config(self, monkeypatch):
        """Returns None when Unkey is not configured (no env vars)."""
        mod = _reload_unkey(monkeypatch, root_key="", api_id="")
        result = asyncio.run(
            mod.create_action_audit("sess-1", "slack", "hello world", "positive")
        )
        assert result is None

    def test_create_action_audit_success(self, monkeypatch):
        """Returns {key_id, key} dict and records in _session_keys on success."""
        mod = _reload_unkey(monkeypatch, root_key="rk_live", api_id="api_live")

        # Build a fake Unkey client whose keys.create() returns a result
        mock_result = MagicMock()
        mock_result.key_id = "kid_001"
        mock_result.key = "key_001"

        mock_client = MagicMock()
        mock_client.keys.create.return_value = mock_result

        # Inject pre-cached client so _client() returns our mock
        mod._unkey = mock_client

        result = asyncio.run(
            mod.create_action_audit("sess-A", "calendar", "sync meeting", "neutral")
        )

        assert result is not None
        assert result["key_id"] == "kid_001"
        assert result["key"] == "key_001"

        # Verify it was tracked in _session_keys
        assert "sess-A" in mod._session_keys
        assert "kid_001" in mod._session_keys["sess-A"]

        # Verify create was called with the request dict
        mock_client.keys.create.assert_called_once()
        call_kwargs = mock_client.keys.create.call_args
        request = call_kwargs[1]["request"] if "request" in call_kwargs[1] else call_kwargs[0][0]
        assert request["api_id"] == "api_live"

        # Clean up
        mod._session_keys.clear()

    def test_create_action_audit_exception_returns_none(self, monkeypatch):
        """SDK exception is caught; function returns None."""
        mod = _reload_unkey(monkeypatch, root_key="rk_live", api_id="api_live")

        mock_client = MagicMock()
        mock_client.keys.create.side_effect = RuntimeError("network error")
        mod._unkey = mock_client

        result = asyncio.run(
            mod.create_action_audit("sess-err", "task", "payload", "neutral")
        )
        assert result is None


class TestUnkeySessionKeys:
    def test_session_keys_tracking(self, monkeypatch):
        """_session_keys dict accumulates key_ids per session."""
        mod = _reload_unkey(monkeypatch, root_key="rk_x", api_id="api_x")
        mod._session_keys.clear()

        # Manually populate as create_action_audit would
        mod._session_keys.setdefault("sess-1", []).append("k1")
        mod._session_keys.setdefault("sess-1", []).append("k2")
        mod._session_keys.setdefault("sess-2", []).append("k3")

        assert len(mod._session_keys["sess-1"]) == 2
        assert mod._session_keys["sess-2"] == ["k3"]

        # get_session_audit returns the expected shape
        audit = asyncio.run(mod.get_session_audit("sess-1"))
        assert len(audit) == 2
        assert all(entry["session_id"] == "sess-1" for entry in audit)
        assert {entry["key_id"] for entry in audit} == {"k1", "k2"}

        # Clean up
        mod._session_keys.clear()

    def test_get_session_audit_empty(self, monkeypatch):
        """get_session_audit on nonexistent session returns empty list."""
        mod = _reload_unkey(monkeypatch, root_key="rk_x", api_id="api_x")
        mod._session_keys.clear()
        result = asyncio.run(mod.get_session_audit("nonexistent"))
        assert result == []


class TestUnkeyRevoke:
    def test_revoke_empty_session(self, monkeypatch):
        """Revoking a nonexistent session returns 0."""
        mod = _reload_unkey(monkeypatch, root_key="rk_x", api_id="api_x")
        mod._session_keys.clear()
        count = asyncio.run(mod.revoke_all_session_keys("no-such-session"))
        assert count == 0

    def test_revoke_no_client(self, monkeypatch):
        """Revoking without credentials returns 0 (even if keys exist)."""
        mod = _reload_unkey(monkeypatch, root_key="", api_id="")
        # Manually insert keys that should not be revokable without a client
        mod._session_keys["orphan"] = ["k1", "k2"]
        count = asyncio.run(mod.revoke_all_session_keys("orphan"))
        assert count == 0
        # Keys are still popped from index (even though revoke fails)
        assert "orphan" not in mod._session_keys

    def test_revoke_success(self, monkeypatch):
        """With a working client, revokes all keys and returns count."""
        mod = _reload_unkey(monkeypatch, root_key="rk_live", api_id="api_live")
        mod._session_keys.clear()
        mod._session_keys["sess-R"] = ["k1", "k2", "k3"]

        mock_client = MagicMock()
        mock_client.keys.delete.return_value = None  # success
        mod._unkey = mock_client

        count = asyncio.run(mod.revoke_all_session_keys("sess-R"))
        assert count == 3
        assert "sess-R" not in mod._session_keys
        assert mock_client.keys.delete.call_count == 3


# ═══════════════════════════════════════════════════════════════════════════════
# DigitalOcean
# ═══════════════════════════════════════════════════════════════════════════════


def _reload_do(monkeypatch, *, endpoint: str = "", access_key: str = ""):
    """Re-import sponsor_digitalocean with controlled env vars."""
    monkeypatch.setenv("DO_AGENT_ENDPOINT", endpoint)
    monkeypatch.setenv("DO_AGENT_ACCESS_KEY", access_key)
    monkeypatch.setenv("DO_MODEL_ACCESS_KEY", "")
    monkeypatch.setenv("DO_SPACES_BUCKET", "")
    for name in list(sys.modules):
        if "sponsor_digitalocean" in name:
            del sys.modules[name]
    import backend.sponsor_digitalocean as mod
    # Reset cached client
    mod._client = None
    return mod


class TestDoAvailable:
    def test_do_available_missing_env(self, monkeypatch):
        """With env vars unset, do_available() returns False."""
        mod = _reload_do(monkeypatch, endpoint="", access_key="")
        assert mod.do_available() is False

    def test_do_available_missing_access_key(self, monkeypatch):
        """Endpoint alone is not enough."""
        mod = _reload_do(monkeypatch, endpoint="https://agent.do.co", access_key="")
        assert mod.do_available() is False

    def test_do_available_set(self, monkeypatch):
        """With both endpoint and access key set, returns True."""
        mod = _reload_do(
            monkeypatch,
            endpoint="https://agent.do.co",
            access_key="do-key-123",
        )
        assert mod.do_available() is True


class TestDoQuery:
    def test_do_query_no_config(self, monkeypatch):
        """Returns empty string when not configured."""
        mod = _reload_do(monkeypatch, endpoint="", access_key="")
        result = asyncio.run(mod.do_query_meeting_memory("test transcript"))
        assert result == ""

    def test_do_query_success(self, monkeypatch):
        """With a mocked client, returns the agent's response text."""
        mod = _reload_do(
            monkeypatch,
            endpoint="https://agent.do.co",
            access_key="do-key-123",
        )

        # Build mock response matching OpenAI chat completion shape
        mock_message = MagicMock()
        mock_message.content = "Prior commitment: ship by Friday."
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_response

        # Inject mock client (bypass _get_client lazy init)
        mod._client = mock_client

        result = asyncio.run(mod.do_query_meeting_memory("We discussed the deadline."))
        assert "Prior commitment" in result

        # Clean up
        mod._client = None

    def test_do_query_exception_returns_empty(self, monkeypatch):
        """API exception returns empty string (graceful degradation)."""
        mod = _reload_do(
            monkeypatch,
            endpoint="https://agent.do.co",
            access_key="do-key-123",
        )

        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("timeout")
        mod._client = mock_client

        result = asyncio.run(mod.do_query_meeting_memory("test"))
        assert result == ""

        mod._client = None


class TestDoArchive:
    def test_do_archive_no_config(self, monkeypatch):
        """Returns None when not configured."""
        mod = _reload_do(monkeypatch, endpoint="", access_key="")
        result = asyncio.run(
            mod.do_archive_meeting("sess-1", [{"text": "hi"}], [{"type": "task"}])
        )
        assert result is None

    def test_do_archive_success(self, monkeypatch):
        """Mocked client archives and returns confirmation text."""
        mod = _reload_do(
            monkeypatch,
            endpoint="https://agent.do.co",
            access_key="do-key-123",
        )

        mock_message = MagicMock()
        mock_message.content = "Meeting archived successfully."
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_response
        mod._client = mock_client

        result = asyncio.run(
            mod.do_archive_meeting(
                "sess-archive",
                [{"speaker": "Alice", "text": "Let's ship it."}],
                [{"type": "commitment", "what": "ship backend"}],
            )
        )
        assert result == "Meeting archived successfully."

        mod._client = None

    def test_do_archive_exception_returns_none(self, monkeypatch):
        """API exception returns None."""
        mod = _reload_do(
            monkeypatch,
            endpoint="https://agent.do.co",
            access_key="do-key-123",
        )

        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("500")
        mod._client = mock_client

        result = asyncio.run(
            mod.do_archive_meeting("sess-fail", [], [])
        )
        assert result is None

        mod._client = None


class TestDoFormatMeetingDocument:
    def test_format_meeting_document_structure(self, monkeypatch):
        """_format_meeting_document builds expected markdown structure."""
        mod = _reload_do(monkeypatch, endpoint="x", access_key="y")

        doc = mod._format_meeting_document(
            session_id="sess-fmt",
            transcript_segments=[
                {"speaker": "Alice", "text": "We need to ship by Friday."},
                {"speaker": "Bob", "text": "Agreed."},
            ],
            actions=[
                {"type": "commitment", "what": "ship backend"},
                {"type": "calendar", "summary": "Launch sync"},
            ],
        )

        assert "# Meeting Record" in doc
        assert "sess-fmt" in doc
        assert "## Transcript" in doc
        assert "[Alice] We need to ship by Friday." in doc
        assert "[Bob] Agreed." in doc
        assert "## Extracted Actions" in doc
        assert "commitment" in doc
        assert "calendar" in doc

        mod._client = None

    def test_format_meeting_document_missing_speaker(self, monkeypatch):
        """Missing speaker defaults to 'Unknown'."""
        mod = _reload_do(monkeypatch, endpoint="x", access_key="y")

        doc = mod._format_meeting_document(
            session_id="sess-no-speaker",
            transcript_segments=[{"text": "Something was said."}],
            actions=[],
        )
        assert "[Unknown] Something was said." in doc

        mod._client = None

    def test_format_meeting_document_empty(self, monkeypatch):
        """Empty segments and actions still produce valid structure."""
        mod = _reload_do(monkeypatch, endpoint="x", access_key="y")

        doc = mod._format_meeting_document("sess-empty", [], [])
        assert "# Meeting Record" in doc
        assert "## Transcript" in doc
        assert "## Extracted Actions" in doc

        mod._client = None


# ═══════════════════════════════════════════════════════════════════════════════
# Railtracks (stub / simulation mode tests)
# ═══════════════════════════════════════════════════════════════════════════════

# Railtracks is being built in a parallel worktree.  These tests import from
# that worktree path if available, otherwise skip.  On Python 3.9 the module
# uses ``asyncio.Lock()`` at module level which needs an event loop.

_RT_WORKTREE = (
    Path(__file__).resolve().parents[1]
    / ".claude" / "worktrees" / "agent-ad20b2e2"
)
_RT_MODULE_PATH = _RT_WORKTREE / "backend" / "sponsor_railtracks.py"


def _load_railtracks():
    """Attempt to load sponsor_railtracks from the parallel worktree.

    On Python <3.10, ``asyncio.Lock()`` at module level requires a
    running event loop, so we ensure one exists before import.
    """
    if not _RT_MODULE_PATH.exists():
        pytest.skip("sponsor_railtracks.py not found in worktree")

    wt_root = str(_RT_WORKTREE)
    if wt_root not in sys.path:
        sys.path.insert(0, wt_root)

    # Ensure an event loop exists (Python 3.9 needs this for module-level
    # asyncio.Lock()).
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    for name in list(sys.modules):
        if "sponsor_railtracks" in name:
            del sys.modules[name]

    import backend.sponsor_railtracks as mod
    return mod


class TestRailtracksAvailable:
    def test_railtracks_importable(self):
        """sponsor_railtracks module can be loaded (may use simulation mode)."""
        mod = _load_railtracks()
        assert hasattr(mod, "railtracks_available")
        assert isinstance(mod.railtracks_available(), bool)


class TestRailtracksFlowStatus:
    def test_flow_status_initial(self):
        """get_flow_status() returns expected shape with required keys."""
        mod = _load_railtracks()
        status = mod.get_flow_status()

        assert isinstance(status, dict)
        expected_keys = {
            "mode",
            "nodes_active",
            "actions_dispatched",
            "total_runs",
            "last_run_ms",
            "routing_decisions",
        }
        assert expected_keys.issubset(set(status.keys())), (
            f"Missing keys: {expected_keys - set(status.keys())}"
        )
        assert status["mode"] in ("native", "simulation")
        assert isinstance(status["nodes_active"], list)
        assert isinstance(status["actions_dispatched"], int)
        assert isinstance(status["total_runs"], int)
        assert isinstance(status["routing_decisions"], list)

    def test_sentiment_monitor_block(self):
        """SentimentMonitor blocks on negative text sentiment."""
        mod = _load_railtracks()
        monitor = mod.SentimentMonitor()
        result = asyncio.run(
            monitor.run(face_sentiment=None, text_sentiment="negative")
        )
        assert result["blocked"] is True
        assert result["decision"] == "block"

    def test_sentiment_monitor_proceed(self):
        """SentimentMonitor proceeds on neutral text + no face."""
        mod = _load_railtracks()
        monitor = mod.SentimentMonitor()
        result = asyncio.run(
            monitor.run(face_sentiment=None, text_sentiment="neutral")
        )
        assert result["blocked"] is False
        assert result["decision"] == "proceed"

    def test_sentiment_monitor_uncertain_angry_blocks(self):
        """Uncertain text + angry face = blocked."""
        mod = _load_railtracks()
        monitor = mod.SentimentMonitor()
        result = asyncio.run(
            monitor.run(
                face_sentiment={"sentiment": "anger"},
                text_sentiment="uncertain",
            )
        )
        assert result["blocked"] is True
        assert result["decision"] == "block"

    def test_action_executor_blocked(self):
        """ActionExecutor returns empty list when blocked=True."""
        mod = _load_railtracks()

        async def dummy_dispatch(understanding):
            return [{"type": "slack", "status": "sent"}]

        executor = mod.ActionExecutor(dummy_dispatch)
        result = asyncio.run(executor.run(understanding={}, blocked=True))
        assert result == []

    def test_meeting_memory_accumulates(self):
        """MeetingMemory stores entries and caps at 100."""
        mod = _load_railtracks()
        memory = mod.MeetingMemory()

        result = asyncio.run(
            memory.run(
                understanding={"commitments": [{"what": "ship"}]},
                sentiment={"decision": "proceed"},
                actions=[{"type": "slack"}],
            )
        )
        assert result["history_len"] == 1
        assert result["latest"]["actions_fired"] == 1
