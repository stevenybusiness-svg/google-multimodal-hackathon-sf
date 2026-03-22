---
phase: 01-deploy-auth
verified: 2026-03-22T23:30:00Z
status: human_needed
score: 5/6 must-haves verified
re_verification: false
human_verification:
  - test: "Trigger a meeting request in the live demo and verify a Google Calendar event is created"
    expected: "A calendar event appears in the authenticated Google account's calendar within ~5 seconds of the meeting request being spoken"
    why_human: "Cannot invoke the WebSocket STT loop or trigger Gemini understanding from a static code check; requires live browser session against the Cloud Run URL with microphone input"
---

# Phase 1: Deploy + Auth Verification Report

**Phase Goal:** Live Cloud Run deployment with Calendar OAuth2 working; public URL captured.
**Verified:** 2026-03-22T23:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | `python scripts/get_calendar_token.py` produces valid token; added to `.env` | VERIFIED | `.env` contains `GOOGLE_CALENDAR_TOKEN_JSON` with valid JSON: keys `[token, refresh_token, token_uri, client_id, client_secret, scopes]`; `refresh_token` present |
| 2 | `gcloud run deploy` succeeds; public URL accessible | VERIFIED | `cloud-run-url.txt` contains `https://meeting-agent-31043195041.us-central1.run.app`; matches `*.run.app` pattern |
| 3 | `/health` endpoint returns `{"status": "ok"}` at Cloud Run URL | VERIFIED | Live HTTP check: `curl https://meeting-agent-31043195041.us-central1.run.app/health` returned `{"status":"ok"}`; root `/` returned HTTP 200 |
| 4 | Calendar event fires correctly in end-to-end test against live deploy | ? UNCERTAIN | Code path fully wired (see Key Links); requires live microphone input + Gemini response to trigger — cannot verify programmatically |
| 5 | `GOOGLE_CALENDAR_TOKEN_JSON` in `.env` is valid JSON with token + refresh_token | VERIFIED | `json.loads()` succeeds; `token` and `refresh_token` fields confirmed present |
| 6 | `get_calendar_service()` initializes without error | VERIFIED (code path) | `backend/main.py` line 75: `calendar_service = get_calendar_service(json.loads(_token_json))` — wired at startup; `get_calendar_service` calls `Credentials(**token_dict)` + `build("calendar", "v3", ...)` — no stub; full `googleapiclient` available on Cloud Run via `requirements.txt` |

**Score:** 5/6 truths verified (1 requires human)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.env` | Contains `GOOGLE_CALENDAR_TOKEN_JSON` | VERIFIED | Key present; value is valid JSON with all required OAuth2 fields including `refresh_token` |
| `.planning/phases/01-deploy-auth/cloud-run-url.txt` | Public Cloud Run URL (`*.run.app`) | VERIFIED | Contains `https://meeting-agent-31043195041.us-central1.run.app` |
| `Dockerfile` | Exposes port 8080; passes `PORT` env var to uvicorn | VERIFIED | Lines 10-13: `EXPOSE 8080`, `ENV PORT=8080`, `CMD exec uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| `backend/actions.py` | `get_calendar_service()` and `create_calendar_event()` are substantive | VERIFIED | `get_calendar_service` builds OAuth2 `Credentials` + `googleapiclient` service (line 43-47); `create_calendar_event` is a full async implementation with token refresh (lines 183-217) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `.env` | `backend/main.py` | `load_dotenv()` + `os.getenv('GOOGLE_CALENDAR_TOKEN_JSON')` | WIRED | `main.py` line 7: `from dotenv import load_dotenv`; line 14: `load_dotenv()`; line 72: `_token_json = os.getenv("GOOGLE_CALENDAR_TOKEN_JSON")` |
| `_token_json` | `get_calendar_service()` | `json.loads(_token_json)` at startup | WIRED | `main.py` line 73-75: guarded `if _token_json:` then `calendar_service = get_calendar_service(json.loads(_token_json))` |
| `calendar_service` | `session.dispatch()` | `has_calendar=calendar_service is not None` | WIRED | `main.py` line 128: `actions = await session.dispatch(understanding, has_calendar=calendar_service is not None, ...)` |
| `has_calendar` | `create_calendar_event()` | `_meeting_request()` call | WIRED | `actions.py` line 315: `if has_calendar and _calendar_creds is not None:` → `event = await create_calendar_event(...)` |
| `Dockerfile` | Cloud Run | `gcloud run deploy --source .` with `PORT=8080` | WIRED | `cloud-run-url.txt` confirms successful deploy; live `/health` returns `{"status":"ok"}` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `backend/actions.py` `create_calendar_event` | OAuth2 credentials | `.env` → `get_calendar_service()` → `_calendar_creds` | Yes — `Credentials(**token_dict)` from live token with `refresh_token` | FLOWING |
| `cloud-run-url.txt` | Cloud Run Service URL | `gcloud run deploy` output | Yes — confirmed live with HTTP 200 response | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `/health` returns `{"status":"ok"}` | `curl -s https://meeting-agent-31043195041.us-central1.run.app/health` | `{"status":"ok"}` | PASS |
| Root endpoint returns HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://meeting-agent-31043195041.us-central1.run.app/` | `200` | PASS |
| `cloud-run-url.txt` contains `run.app` URL | `grep -E "run\.app" cloud-run-url.txt` | `https://meeting-agent-31043195041.us-central1.run.app` | PASS |
| `.env` token is valid JSON | `python3 -c "import json,re; ..."` | Keys: `[token, refresh_token, token_uri, client_id, client_secret, scopes]` | PASS |
| End-to-end Calendar event creation | Requires live audio → STT → Gemini → dispatch | N/A (needs running session) | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| DEPLOY-01 | 01-02-PLAN.md | Backend deployed to Cloud Run; public URL captured for submission proof | SATISFIED | `cloud-run-url.txt` contains live `run.app` URL; `/health` confirmed `{"status":"ok"}` |
| DEPLOY-02 | 01-01-PLAN.md | `GOOGLE_CALENDAR_TOKEN_JSON` in env (from `scripts/get_calendar_token.py`) | SATISFIED | `.env` contains key with valid JSON; `token` + `refresh_token` confirmed; wired through `main.py` startup into `get_calendar_service()` |

No orphaned requirements detected. DEPLOY-01 and DEPLOY-02 are the only Phase 1 requirements in REQUIREMENTS.md, and both are claimed by the plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

No TODO/FIXME/placeholder comments, no empty return stubs, no hardcoded empty data arrays passed to rendering paths found in phase-modified files (`.env`, `cloud-run-url.txt`). `backend/actions.py` and `backend/main.py` contain full implementations.

### Human Verification Required

#### 1. End-to-End Calendar Event Creation

**Test:** Open `https://meeting-agent-31043195041.us-central1.run.app` in a browser. Start a session. Speak a clear meeting request such as "Let's schedule a follow-up with Alex on Friday at 2pm." Wait approximately 5 seconds.

**Expected:** A Google Calendar event appears in the authenticated Google account's calendar (stevenybusiness@gmail.com). The UI action card should show a "calendar" action with event details.

**Why human:** The calendar creation path requires: (1) live microphone audio streamed over WebSocket, (2) Cloud STT producing a final transcript, (3) Gemini Flash parsing a `meeting_request` intent from the transcript, (4) `dispatch()` calling `create_calendar_event()`. None of these stages can be invoked from a static code check. The code path is fully wired (Level 3 verified), but the OAuth2 token's validity against the live Google Calendar API can only be confirmed by an actual event creation.

### Gaps Summary

No blocking gaps found. All six success criteria from ROADMAP.md are either programmatically verified (5/6) or require a brief manual smoke test (1/6 — end-to-end Calendar event). Both phase requirements (DEPLOY-01, DEPLOY-02) are fully satisfied with evidence.

The one human-verification item is a confidence check on the live OAuth2 token against the Calendar API — the code path, credentials structure, and wiring are all confirmed correct. The most likely failure mode (expired token) is mitigated by the `refresh_token` being present and the auto-refresh logic in `actions.py` lines 215-217.

---

_Verified: 2026-03-22T23:30:00Z_
_Verifier: Claude (gsd-verifier)_
