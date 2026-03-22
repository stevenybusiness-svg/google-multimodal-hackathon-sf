# External Integrations

**Analysis Date:** 2026-03-22

## APIs & External Services

**Google Gemini (LLM):**
- Gemini Flash API - Understanding (commitment/agreement extraction, sentiment classification)
  - SDK/Client: `google-genai` (async client)
  - Auth: `GOOGLE_API_KEY` environment variable
  - Models: `gemini-3-flash-preview`
  - Files: `backend/understanding.py`, `backend/documents.py`
  - Rate limiting: asyncio.Semaphore(4) across concurrent calls

**Google Cloud Speech-to-Text v1 (STT):**
- Real-time streaming voice transcription
  - SDK/Client: `google-cloud-speech` (SpeechAsyncClient)
  - Auth: Application default credentials (gcloud auth application-default login)
  - Config: 16kHz PCM, LINEAR16 encoding, en-US, model=latest_long, auto punctuation
  - Files: `backend/voice.py`
  - Stream reconnects proactively at 4 minutes (5-minute hard limit)

**Google Cloud Vision API:**
- Face detection and emotion analysis
  - SDK/Client: `google.cloud.vision` (ImageAnnotatorClient)
  - Auth: Application default credentials via GCP project
  - Features: FACE_DETECTION (1 result), LABEL_DETECTION (5 results)
  - Config: Quota project ID from `GOOGLE_CLOUD_PROJECT`
  - Files: `backend/vision.py`
  - Rate limiting: asyncio.Semaphore(3), debounced 2 seconds per session

**Google Calendar API:**
- Create calendar events from meeting requests
  - SDK/Client: `google-api-python-client` (googleapiclient.discovery.build)
  - Auth: OAuth2 credentials from `GOOGLE_CALENDAR_TOKEN_JSON`
  - Files: `backend/actions.py` (create_calendar_event, get_calendar_service)
  - Scope: Calendar events (calendar.v3)
  - Usage: Fire-and-forget dispatch; credentials refreshed on expiry

**Gmail API:**
- Send meeting summary emails at end of session
  - SDK/Client: `google-api-python-client` (googleapiclient.discovery.build)
  - Auth: OAuth2 credentials (shared with Calendar setup)
  - Files: `backend/email_summary.py`
  - Scope: Gmail send (gmail.v1)
  - Recipients: Hardcoded list in `RECIPIENTS` (temuj627@gmail.com, stevenybusiness@gmail.com)
  - Usage: Async email composed from meeting transcript and actions taken

## Data Storage

**Databases:**
- None - in-memory only (MVP)

**File Storage:**
- Slack workspace (document revisions uploaded as files)
- No external file storage (S3, GCS, etc.)

**Session Storage:**
- In-memory per WebSocket connection
- `TranscriptBuffer` (per session) - holds pending transcript segments
- `ActionSession` (per session) - holds task log and document revisions
- `SessionRegistry` (global) - dict of active sessions keyed by session_id
- Files: `backend/understanding.py`, `backend/actions.py`, `backend/session_state.py`

**Caching:**
- None - no Redis or caching layer
- In-memory Slack channel ID cache (`_channel_id_cache` in `backend/actions.py`)
- In-memory Gemini/Gmail client singletons (lazy-init pattern)

## Authentication & Identity

**Auth Provider:**
- Google OAuth2 (delegated, Calendar + Gmail)
- API Key auth (Gemini API)
- Application Default Credentials (Cloud STT, Vision)

**Implementation:**
- OAuth2: `google-auth-oauthlib` for credential generation via `scripts/get_calendar_token.py`
- API Key: Injected via `GOOGLE_API_KEY` environment variable
- ADC: User runs `gcloud auth application-default login` locally; Cloud Run uses service account

**Credentials Files:**
- `GOOGLE_CALENDAR_TOKEN_JSON` - OAuth2 token dict (Calendar + Gmail), injected as env var
- `credentials.json` - OAuth2 client config (OAuth flow only; not used at runtime)
- No session-level authentication (meeting agent is unauthenticated)

## Monitoring & Observability

**Error Tracking:**
- None - no dedicated error tracking (Sentry, Rollbar, etc.)

**Logs:**
- Python logging (stdlib) to stdout
- Format: `%(asctime)s %(name)s %(levelname)s %(message)s`
- Level: INFO
- Cloud Run captures stdout/stderr automatically
- Files: All `backend/` modules log via `logging.getLogger(__name__)`

**Debugging:**
- Request logging (FastAPI middleware implicit)
- WebSocket frame logging (binary/text type tracking)
- STT stream response count and latency
- Gemini API call timing and rate-limit retries
- Vision API per-emotion confidence scores

## CI/CD & Deployment

**Hosting:**
- Google Cloud Run (serverless containers)
- Region: us-central1
- Docker image built from `Dockerfile`

**CI Pipeline:**
- None currently (manual deployment)
- Deployment command: `gcloud run deploy meeting-agent --source . --region us-central1 --allow-unauthenticated --set-env-vars ...`

**Dockerfile:**
- Base: python:3.12
- Installs: pip dependencies from requirements.txt
- Entrypoint: uvicorn backend.main:app --host 0.0.0.0 --port 8080

**Version Control:**
- Git repository (public GitHub)
- No automated tests in CI (pytest config exists but not gated)

## Environment Configuration

**Required env vars:**
- `GOOGLE_API_KEY` - Gemini API key (critical, no fallback)
- `GOOGLE_CLOUD_PROJECT` - GCP project ID (critical for Vision/STT)
- `SLACK_BOT_TOKEN` - Slack bot token (optional; Slack actions skipped if missing)
- `SLACK_CHANNEL` - Target Slack channel name (default: #meeting-actions)
- `GOOGLE_CALENDAR_TOKEN_JSON` - OAuth2 token JSON (optional; Calendar events skipped if missing)

**Secrets location:**
- `.env` file (local development only, .gitignored)
- Cloud Run: injected via `--set-env-vars` flag during deploy
- No secrets manager (Secrets Manager, KMS, etc.)

**Example .env:**
```
GOOGLE_API_KEY=sk-...
GOOGLE_CLOUD_PROJECT=my-project-id
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL=#meeting-actions
GOOGLE_CALENDAR_TOKEN_JSON={"type":"authorized_user",...}
```

## Webhooks & Callbacks

**Incoming:**
- `/ws/audio` - WebSocket for live audio stream + text commands
- `/api/frame` - POST JPEG frames for vision analysis
- `/api/document` - GET meeting session document state
- `/health` - GET health check (no-op)
- `/` - GET index.html (UI)

**Outgoing:**
- Slack API: `chat_postMessage`, `files_upload_v2`, `conversations_list`, `conversations_join`
- Google Calendar API: `events().insert()`
- Gmail API: `users().messages().send()`
- No outbound webhooks to 3rd party services

## Rate Limiting & Quotas

**Gemini API:**
- No explicit rate limit handling code (relies on default tier)
- Rate limit retry: exponential backoff (2s, 4s, capped at 35s)
- Semaphore: max 4 concurrent calls (understanding + document revision)

**Cloud Speech-to-Text:**
- Streaming connection (billed per 15-second blocks)
- No per-request rate limiting
- Stream lifecycle: 4-minute proactive reconnect before 5-minute hard limit

**Cloud Vision:**
- Per-image charge; debounced 2 seconds per session
- Semaphore: max 3 concurrent batch_annotate_images calls
- Max results: 1 face, 5 labels per image

**Slack API:**
- Standard Slack rate limits apply
- No explicit backoff in code (relies on Slack SDK defaults)
- File upload: fallback to message if files_upload_v2 fails

**Google Calendar/Gmail:**
- Standard Google API quotas
- Credentials auto-refreshed on expiry in `create_calendar_event()`

---

*Integration audit: 2026-03-22*
