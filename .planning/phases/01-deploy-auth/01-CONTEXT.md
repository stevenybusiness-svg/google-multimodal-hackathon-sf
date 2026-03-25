# Phase 1: Deploy + Auth — Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Get the live meeting agent running on Google Cloud Run with a public URL, and get Google Calendar OAuth2 working so calendar events fire in the demo. These two tasks are independent and run in parallel. Phase is done when: Cloud Run URL is live, `/health` returns OK, and a calendar event can be created end-to-end.

</domain>

<decisions>
## Implementation Decisions

### Calendar OAuth2 (Plan 01-01)
- **D-01:** Run `python scripts/get_calendar_token.py` — this script already exists and handles the OAuth2 flow
- **D-02:** Output is the full JSON token; paste into `.env` as `GOOGLE_CALENDAR_TOKEN_JSON`
- **D-03:** Verify by checking that `actions.py:get_calendar_service()` initializes without error

### Cloud Run Deploy (Plan 01-02)
- **D-04:** Use `gcloud run deploy meeting-agent --source . --region us-central1 --allow-unauthenticated`
- **D-05:** Pass all 5 env vars: `GOOGLE_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_CHANNEL`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CALENDAR_TOKEN_JSON`
- **D-06:** Capture public URL from deploy output — screenshot or save to a file for submission proof
- **D-07:** Verify with `curl <URL>/health` → `{"status": "ok"}`

### Parallelization
- **D-08:** Both plans run in parallel (they're independent — OAuth2 doesn't block deploy)

### Claude's Discretion
- Order of env var flags in gcloud command
- Whether to use `--set-env-vars` or `--env-vars-file`
- Whether to verify Calendar end-to-end after deploy or just token init

</decisions>

<specifics>
## Specific Ideas

- Calendar token must be base64-or-JSON safe for env var; the existing script handles this
- Cloud Run must be `--allow-unauthenticated` for demo (judges need to access the URL)
- Region: `us-central1` (lowest latency for SF in-person demo)

</specifics>

<canonical_refs>
## Canonical References

### Deploy
- `.planning/PROJECT.md` §Constraints — stack and auth constraints
- `scripts/get_calendar_token.py` — OAuth2 pre-auth script (read before running)
- `README.md` — local run + deploy instructions (if exists)
- `Dockerfile` — container spec (Cloud Run uses this)

### Environment
- `.env.example` — required env vars reference
- `backend/main.py` lines 71–81 — Calendar service init at startup (validates token at boot)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/get_calendar_token.py`: Complete OAuth2 flow; just run it and paste output
- `Dockerfile`: Already configured for port 8080, python:3.12-slim
- `backend/main.py:_validate_models()`: Validates Gemini models at startup — will fail fast if `GOOGLE_API_KEY` is wrong

### Established Patterns
- Env vars loaded via `python-dotenv` (`load_dotenv()` in `main.py`)
- Calendar creds initialized once at startup from `GOOGLE_CALENDAR_TOKEN_JSON` env var

### Integration Points
- Token from OAuth2 script → `GOOGLE_CALENDAR_TOKEN_JSON` env var → `main.py` line 72 → `get_calendar_service()` → `actions.py:_calendar_creds`

</code_context>

<deferred>
## Deferred Ideas

- DigitalOcean inference endpoint — stretch goal, post-submission
- WorkOS auth — stretch goal, post-submission

</deferred>

---
*Phase: 01-deploy-auth*
*Context gathered: 2026-03-22*
