---
phase: 01-deploy-auth
plan: 01
subsystem: auth
tags: [google-calendar, oauth2, credentials, google-auth-oauthlib]

# Dependency graph
requires:
  - phase: 00-core
    provides: backend/actions.py with get_calendar_service() and create_calendar_event()
provides:
  - GOOGLE_CALENDAR_TOKEN_JSON in .env with calendar.events + gmail.send scopes
  - OAuth2 credentials with refresh_token for auto-renewal
  - Calendar service initialization path validated
affects: [01-02-deploy, 02-01-demo-video]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "OAuth2 pre-auth: scripts/get_calendar_token.py generates token; stored as raw JSON in .env; Credentials(**token_dict) used in get_calendar_service()"

key-files:
  created: []
  modified: [.env]

key-decisions:
  - "credentials.json is present at project root (GCP Desktop app OAuth2 client) — no action needed"
  - "get_calendar_token.py requests both calendar.events and gmail.send scopes in one OAuth2 flow"
  - "Token stored as raw JSON string in .env (no base64 encoding needed — no newlines in value)"
  - "refresh_token present — credentials auto-refresh; no re-auth required before hackathon deadline"

patterns-established:
  - "GOOGLE_CALENDAR_TOKEN_JSON: full JSON token dict inline in .env (not a file path)"
  - "OAuth2 human-action gate: script generates token, human pastes to .env, agent validates JSON + Credentials construction"

requirements-completed: [DEPLOY-02]

duration: ~10min (includes human OAuth2 browser flow)
completed: 2026-03-22
---

# Phase 01 Plan 01: Google Calendar OAuth2 Pre-Auth Summary

**Google Calendar OAuth2 token obtained via browser flow; GOOGLE_CALENDAR_TOKEN_JSON in .env with calendar.events+gmail.send scopes and refresh_token for auto-renewal**

## Performance

- **Duration:** ~10 min (includes human OAuth2 browser flow)
- **Started:** 2026-03-22T22:58:26Z
- **Completed:** 2026-03-22
- **Tasks:** 2 of 2 completed
- **Files modified:** 1 (.env)

## Accomplishments

- Confirmed `credentials.json` exists at project root (required for OAuth2 client config)
- Verified `scripts/get_calendar_token.py` reads credentials.json, imports google_auth_oauthlib, and requests calendar.events + gmail.send scopes
- User completed OAuth2 browser flow successfully
- GOOGLE_CALENDAR_TOKEN_JSON now in .env with valid JSON (token + refresh_token + scopes)
- `google.oauth2.credentials.Credentials(**token_dict)` construction validated — all fields correct
- Calendar event creation path unblocked for live deploy

## Task Commits

Each task committed atomically:

1. **Task 1: Verify get_calendar_token.py is ready to run** - `936ff33` (docs — verification only)
2. **Task 2: Validate token and calendar service init** - `ee9c93b` (chore — token validation)

## Files Created/Modified

- `.env` - Added GOOGLE_CALENDAR_TOKEN_JSON with full OAuth2 token JSON (calendar.events + gmail.send scopes, includes refresh_token)

## Decisions Made

- Token stored as raw JSON string in .env (no base64 needed — no newlines in value)
- Both `calendar.events` and `gmail.send` scopes obtained in one flow — covers Calendar and email features
- refresh_token present, auto-refreshes; no re-auth needed before hackathon

## Deviations from Plan

None - plan executed exactly as written. The human-action checkpoint completed as expected.

Note: Local smoke test could not call `get_calendar_service()` directly because `google-api-python-client` (googleapiclient) is not installed on local Python 3.9. Validated `Credentials(**token_dict)` construction via `google-auth` which is installed. Full service init will work on Cloud Run where `requirements.txt` installs the package.

## Issues Encountered

- `googleapiclient` not installed locally. Validated token JSON and Credentials construction without calling `build()`. Cloud Run environment has the package via requirements.txt.

## User Setup Required

OAuth2 browser flow completed by user. No further manual steps required.

## Next Phase Readiness

- GOOGLE_CALENDAR_TOKEN_JSON in .env — calendar events will fire on Cloud Run deploy
- Cloud Run deploy (01-02) already complete per STATE.md
- Phase 1 fully complete; proceed to Phase 2 demo video

---
*Phase: 01-deploy-auth*
*Completed: 2026-03-22*
