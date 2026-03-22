---
phase: 01-deploy-auth
plan: 01
subsystem: auth
tags: [google-calendar, oauth2, credentials, env-vars]

requires: []
provides:
  - "Verified credentials.json present for OAuth2 client secrets"
  - "Confirmed get_calendar_token.py script is ready to execute"
  - "GOOGLE_CALENDAR_TOKEN_JSON env var pattern documented in .env.example"
affects: [deploy, calendar-actions]

tech-stack:
  added: []
  patterns:
    - "OAuth2 pre-auth: run get_calendar_token.py to generate GOOGLE_CALENDAR_TOKEN_JSON once before deploy"

key-files:
  created: []
  modified: []

key-decisions:
  - "credentials.json is present at project root (GCP Desktop app OAuth2 client) — no action needed"
  - "get_calendar_token.py requests both calendar.events and gmail.send scopes in one flow"

patterns-established:
  - "GOOGLE_CALENDAR_TOKEN_JSON: full JSON token dict inline in .env (not a file path)"

requirements-completed: []

duration: 3min
completed: 2026-03-22
---

# Phase 01 Plan 01: Google Calendar OAuth2 Pre-Auth Summary

**credentials.json verified present; get_calendar_token.py confirmed ready for OAuth2 browser flow — paused at human-action checkpoint awaiting token generation**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-22T22:58:26Z
- **Completed:** 2026-03-22T22:58:26Z (partial — checkpoint reached)
- **Tasks:** 1 of 2 completed (Task 2 pending after human action)
- **Files modified:** 0

## Accomplishments

- Confirmed `credentials.json` exists at project root (required for OAuth2 client config)
- Verified `scripts/get_calendar_token.py` reads credentials.json, imports google_auth_oauthlib, and requests calendar.events + gmail.send scopes
- Confirmed `.env.example` documents GOOGLE_CALENDAR_TOKEN_JSON format correctly
- Confirmed `backend/actions.py` get_calendar_service() accepts a dict and constructs Credentials from it — will initialize cleanly once token is in .env

## Task Commits

Each task committed atomically:

1. **Task 1: Verify get_calendar_token.py is ready to run** - no-commit (verification only, no file changes)

Note: Task 2 (Validate token and calendar service init) is pending human action at checkpoint.

## Files Created/Modified

None — Task 1 was a verification-only task with no file modifications.

## Decisions Made

- `get_calendar_token.py` requests both `calendar.events` AND `gmail.send` scopes in a single OAuth2 flow — token covers both Calendar and email summary features
- Token shape: `{"token": ..., "refresh_token": ..., "token_uri": ..., "client_id": ..., "client_secret": ..., "scopes": [...]}` — matches what `get_calendar_service()` expects via `Credentials(**token_dict)`

## Deviations from Plan

None — plan executed exactly as written through Task 1. Stopped at checkpoint:human-action as required.

## Issues Encountered

None.

## User Setup Required

**External service requires manual configuration.**

Run the OAuth2 script to generate the calendar token:

```bash
python scripts/get_calendar_token.py
```

A browser will open. Sign in with your Google account and grant Calendar + Gmail access.
Copy the printed JSON and add to `.env`:

```
GOOGLE_CALENDAR_TOKEN_JSON={"token": "...", "refresh_token": "...", "token_uri": "...", "client_id": "...", "client_secret": "...", "scopes": [...]}
```

After adding to `.env`, signal completion so Task 2 (validation) can run.

## Next Phase Readiness

- Blocked until `GOOGLE_CALENDAR_TOKEN_JSON` is in `.env`
- Once token is added, Task 2 will validate it and confirm calendar service initializes
- After plan 01-01 completes, plan 01-02 (Cloud Run deploy) can proceed

---
*Phase: 01-deploy-auth*
*Completed: 2026-03-22 (partial — checkpoint)*
