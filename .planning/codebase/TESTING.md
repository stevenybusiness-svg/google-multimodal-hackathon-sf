# Testing Patterns

**Analysis Date:** 2026-03-22

## Test Framework

**Runner:**
- pytest (v8.3.0+)
- Config: No explicit `pytest.ini` or `[tool:pytest]` in `pyproject.toml` (not found)
- Default discovery: `tests/` directory with `test_*.py` files

**Assertion Library:**
- Python `assert` statements (standard library)
- No external assertion library (pytest's built-in)

**Run Commands:**
```bash
pytest                          # Run all tests
pytest tests/                   # Run tests directory
pytest tests/regressions/       # Run regression test suite
pytest -v                       # Verbose output
pytest --tb=short               # Short traceback on failure
```

## Test File Organization

**Location:**
- Co-located with module code: NO
- Separate test directory: YES — `tests/regressions/`
- Test setup: `tests/conftest.py` (pytest configuration file)

**Naming:**
- Test files: `test_*.py` (e.g., `test_understanding.py`, `test_actions.py`, `test_smoke.py`)
- Test functions: `test_*` (e.g., `test_strip_json_fences_handles_wrapped_payload()`)
- Test class grouping: None observed; flat function-based tests

**Structure:**
```
tests/
├── conftest.py                 # pytest configuration + path setup
└── regressions/
    ├── test_understanding.py   # TranscriptBuffer, _strip_json_fences tests
    ├── test_actions.py         # ActionSession, calendar, Slack tests
    ├── test_smoke.py           # Integration: smoke_test.py script verification
    └── test_vision.py          # (exists, not examined)
```

## Test Structure

**Suite Organization:**
```python
# tests/conftest.py sets up sys.path
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

**Patterns:**
- No pytest fixtures defined; uses pytest built-in fixtures (`monkeypatch`)
- Test setup: Direct instantiation or mocking (no setup/teardown methods)
- Async test pattern: `asyncio.run()` wrapper for running async functions in sync tests

**Example Test Structure:**
```python
def test_transcript_buffer_force_flush_preserves_final_utterance(monkeypatch) -> None:
    # Setup: Define fake/mock function
    async def fake_understand(transcript: str, face_sentiment=None):
        result = empty_understanding()
        result["commitments"] = [{"owner": "sam", "what": transcript}]
        return result

    # Monkeypatch: Replace real function with mock
    monkeypatch.setattr(understanding, "understand_transcript", fake_understand)

    # Execute: Create instance and call methods
    buffer = TranscriptBuffer()
    first = asyncio.run(buffer.process("I will send the update", None))
    final = asyncio.run(buffer.flush(None))

    # Assert: Verify behavior
    assert first is None
    assert final is not None
    assert final["commitments"][0]["what"] == "I will send the update"
```

## Mocking

**Framework:** pytest `monkeypatch` fixture (built-in)

**Patterns:**
```python
# Module-level function mocking
monkeypatch.setattr(understanding, "understand_transcript", fake_understand)

# Global variable mocking
monkeypatch.setattr(actions, "_calendar_creds", object())

# Method replacement in class
monkeypatch.setattr(actions, "_post_slack", fake_post_slack)
monkeypatch.setattr(actions, "create_calendar_event", fake_create_calendar_event)
```

**What to Mock:**
- External API calls (Gemini, Google Calendar, Slack SDK)
- Google Cloud clients (Speech-to-Text, Vision)
- I/O operations (file reads, network calls)
- Time-dependent behavior (for testing cooldown/debounce)

**What NOT to Mock:**
- Core business logic: `TranscriptBuffer` flow, `ActionSession` dispatch logic
- Type definitions and contracts
- Utility functions (`_strip_json_fences()`, `_norm()`)

**Mock Implementation Pattern:**
```python
# Minimal mock function that returns expected shape
async def fake_understand(transcript: str, face_sentiment=None):
    result = empty_understanding()
    result["commitments"] = [{"owner": "alice", "what": "ship backend", "sentiment": "neutral"}]
    return result

# Nested class mock for complex objects
class DummyService:
    def events(self):
        return DummyEvents()

class DummyEvents:
    def insert(self, calendarId: str, body: dict):
        return DummyExecute()
```

## Fixtures and Factories

**Test Data:**
```python
# Helper function for creating empty base
def empty_understanding() -> UnderstandingResult:
    return {
        "commitments": [],
        "agreements": [],
        "meeting_requests": [],
        "document_revisions": [],
        "sentiment": "neutral",
    }

# Used in tests
understanding = empty_understanding()
understanding["commitments"] = [{"owner": "alice", "what": "ship backend", "sentiment": "neutral"}]
```

**Location:**
- Shared test utilities: `backend/contracts.py` exports `empty_understanding()`
- Test-only functions: `_strip_json_fences()` imported from implementation, tested directly
- Factories: None observed; factories inline in test setup

## Coverage

**Requirements:** Not enforced
- No pytest coverage config found
- No `.coveragerc` or coverage settings in CI
- Tests exist but no coverage gates

**View Coverage:**
```bash
pytest --cov=backend --cov-report=html   # Generate HTML report
# Output: htmlcov/index.html
```

## Test Types

**Unit Tests:**
- Scope: Single function or class method in isolation
- Approach: Monkeypatch external dependencies, assert on return value
- Examples:
  - `test_strip_json_fences_handles_wrapped_payload()` — pure function
  - `test_transcript_buffer_force_flush_preserves_final_utterance()` — isolated class
  - `test_calendar_event_invalid_datetime_falls_back_to_now()` — method with mocked service

**Integration Tests:**
- Scope: Multiple components interacting
- Approach: Mock only external APIs (Google Cloud, Slack), use real business logic
- Examples:
  - `test_action_dispatch_returns_stable_shapes()` — ActionSession.dispatch() with all action types
  - Tests verify correct `ActionResult` shape is returned across all action paths

**Smoke Tests:**
- Scope: Verify imports and instantiation without API calls
- Approach: Subprocess execution of `scripts/smoke_test.py`
- Example: `test_repo_root_smoke_script_runs_cleanly()` — validates all imports work, no syntax errors

**E2E Tests:**
- Framework: Not used
- No end-to-end tests (WebSocket integration, live API calls) in test suite
- Manual testing via live demo environment

## Common Patterns

**Async Testing:**
```python
# Pattern: Wrap async function in asyncio.run()
first = asyncio.run(buffer.process("I will send the update", None))
final = asyncio.run(buffer.flush(None))

# Pattern: Mock async function with async def
async def fake_understand(transcript: str, face_sentiment=None):
    result = empty_understanding()
    result["commitments"] = [{"owner": "sam", "what": transcript}]
    return result

monkeypatch.setattr(understanding, "understand_transcript", fake_understand)
```

**Error Testing:**
```python
# Pattern: Test fallback behavior on invalid input
result = asyncio.run(
    actions.create_calendar_event("Sync", "not-a-date", attendees=["a@example.com"], sentiment="negative")
)
# Assertion verifies fallback to `datetime.now()`
start = datetime.fromisoformat(result["start"]["dateTime"])
assert start.tzinfo is not None
```

**JSON/Type Testing:**
```python
# Pattern: Test parsing and fence stripping
def test_strip_json_fences_handles_wrapped_payload() -> None:
    wrapped = "```json\n{\"sentiment\": \"neutral\"}\n```"
    assert _strip_json_fences(wrapped) == '{"sentiment": "neutral"}'

# Pattern: Test TypedDict shapes and contracts
def test_action_dispatch_returns_stable_shapes(monkeypatch) -> None:
    result = asyncio.run(actions.ActionSession().dispatch(understanding, has_calendar=True))
    assert {item["type"] for item in result} == {"slack", "task", "calendar", "document"}
    assert all("status" in item for item in result)
```

## Test Execution Context

**Imports (conftest.py):**
- Adds project root to `sys.path` so `backend` package is importable from test files
- Pattern: `sys.path.insert(0, str(ROOT))`

**Monkeypatch Scope:**
- Function scope: Monkeypatched values reset after each test automatically
- Module-level state: Can be patched, persists only for test function duration

**Execution Model:**
- Synchronous test runner (pytest) with async support via `asyncio.run()`
- No pytest-asyncio plugin detected; tests manually run async code
- Tests can call `asyncio.run()` multiple times within single test function

---

*Testing analysis: 2026-03-22*
