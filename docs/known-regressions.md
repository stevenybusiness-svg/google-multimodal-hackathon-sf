# Known Regressions

Short list of bugs that previously repeated during AI-assisted feature work. Each entry should map to a regression test before the bug is considered closed.

| Symptom | Root cause | Guard |
|---|---|---|
| Smoke test failed from repo root | `backend` package was not added to `sys.path` in `scripts/smoke_test.py` | `tests/regressions/test_smoke.py` |
| Final utterance was lost when stopping a meeting | Transcript buffer was reset before a final flush | `tests/regressions/test_understanding.py` and `tests/regressions/test_app_integration.py` |
| No-face vision frames could break behavior | Vision parsing assumed face annotations existed | `tests/regressions/test_vision.py` |
| Calendar/date parsing was brittle | Natural-language or invalid dates reached `datetime.fromisoformat()` | `tests/regressions/test_actions.py` |
| Document update flow drifted from live UI state | Document actions were emitted without stable payload expectations | `tests/regressions/test_actions.py` |
| Payload shapes drifted between backend and frontend | Action and WebSocket envelopes were built ad hoc | Contract checks in `backend/contracts.py` plus regression tests |
