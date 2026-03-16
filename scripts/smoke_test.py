"""
Smoke test — verifies all imports and basic class instantiation without making API calls.

Usage:
    python scripts/smoke_test.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Dummy env vars so lazy-init clients don't crash on missing keys
os.environ.setdefault("GOOGLE_API_KEY", "dummy-key-smoke")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "dummy-project-smoke")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-dummy-smoke")
os.environ.setdefault("SLACK_CHANNEL", "#smoke-test")

errors: list[str] = []


def check(label: str, fn) -> None:
    try:
        fn()
        print(f"  \u2713 {label}")
    except Exception as exc:
        print(f"  \u2717 {label}: {exc}")
        errors.append(label)


print("=== Meeting Agent smoke test ===\n")

# --- Module imports ---
print("Imports:")
check("backend.voice", lambda: __import__("backend.voice"))
check("backend.understanding", lambda: __import__("backend.understanding"))
check("backend.actions", lambda: __import__("backend.actions"))
check("backend.vision", lambda: __import__("backend.vision"))
check("backend.main", lambda: __import__("backend.main"))
check("backend.contracts", lambda: __import__("backend.contracts"))
check("backend.session_state", lambda: __import__("backend.session_state"))

# --- Instantiation ---
print("\nInstantiation:")
from backend.voice import VoicePipeline
from backend.understanding import TranscriptBuffer, EMPTY
from backend.actions import ActionSession

check("VoicePipeline()", lambda: VoicePipeline())
check("TranscriptBuffer()", lambda: TranscriptBuffer())
check("ActionSession()", lambda: ActionSession())

# --- Constants ---
print("\nConstants:")
_EXPECTED_EMPTY_KEYS = ("commitments", "agreements", "meeting_requests", "document_revisions", "sentiment")

def _assert_empty_shape(e) -> None:
    assert isinstance(e, dict), f"Expected dict, got {type(e).__name__}"
    for key in _EXPECTED_EMPTY_KEYS:
        assert key in e, f"EMPTY missing key: {key!r}"
        assert isinstance(e[key], list) or isinstance(e[key], str), \
            f"EMPTY[{key!r}] has unexpected type {type(e[key]).__name__}"

check("EMPTY shape and keys", lambda: _assert_empty_shape(EMPTY))

# --- Result ---
print()
if errors:
    print(f"FAILED: {len(errors)} check(s) — {errors}")
    sys.exit(1)
else:
    print("All checks passed.")
