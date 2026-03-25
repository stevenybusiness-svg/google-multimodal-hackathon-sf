# Research: Stack + Ecosystem

**Generated:** 2026-03-22

## Voice (Hear)

- **Google Cloud Speech-to-Text v1** (`google.cloud.speech_v1`)
  - `SpeechAsyncClient.streaming_recognize()` for async streaming
  - 5-minute hard stream limit → reconnect at 4 min (`_MAX_STREAM_DURATION_S = 240`)
  - `model=latest_long` for continuous meeting recognition
  - `interim_results=True` → ~200ms display latency
  - Audio format: PCM mono 16-bit 16000Hz LINEAR16

## Understanding (Understand)

- **Gemini Flash** (`google-genai` SDK, `genai.Client`)
  - Model: `gemini-3-flash-preview`
  - `client.aio.models.generate_content()` for async
  - Semaphore: `asyncio.Semaphore(4)` to cap concurrent calls
  - Rate limit handling: exponential backoff on 429/RESOURCE_EXHAUSTED
  - Validated at startup via `client.aio.models.get(model=name)`

## Vision (See)

- **Google Cloud Vision** (`google.cloud.vision`)
  - `ImageAnnotatorClient.batch_annotate_images()` (sync, wrapped in `asyncio.to_thread`)
  - Features: `FACE_DETECTION` (max 1), `LABEL_DETECTION` (max 5)
  - Likelihood enum: 0=UNKNOWN, 1=VERY_UNLIKELY, 2=UNLIKELY, 3=POSSIBLE, 4=LIKELY, 5=VERY_LIKELY
  - `_norm()` map: {0:0.0, 1:0.1, 2:0.4, 3:0.7, 4:0.9, 5:1.0}
  - Debounce: `DEBOUNCE_SECONDS = 2`, semaphore: `asyncio.Semaphore(3)`

## Actions (Act)

- **Slack** (`slack_sdk.web.async_client.AsyncWebClient`)
  - `chat_postMessage()` for text messages
  - `files_upload_v2()` for document uploads; fallback to code-block message
  - Auto-join channel on `not_in_channel` error
- **Google Calendar** (`googleapiclient.discovery.build("calendar", "v3")`)
  - OAuth2 via `google.oauth2.credentials.Credentials`
  - `events().insert(calendarId="primary", body=event).execute` (sync, wrapped in `asyncio.to_thread`)
  - Credentials refresh: `_calendar_creds.refresh(google.auth.transport.requests.Request())`

## Backend Framework

- **FastAPI** with `python-dotenv`
- WebSocket: `/ws/audio` (binary=PCM audio, text=JSON commands)
- REST: `/api/frame` (POST JPEG), `/api/document` (GET), `/api/tasks` (GET), `/health` (GET)
- Per-session state: `TranscriptBuffer`, `ActionSession`, `VisionState` via `session_registry`

## Deploy

- **Google Cloud Run** (`gcloud run deploy --source . --allow-unauthenticated`)
- Container: `python:3.12-slim`, port 8080
- Source-based deploy (no manual Docker build needed)

## Known Pitfalls

- Calendar SDK is sync-only → always wrap in `asyncio.to_thread()`
- `GOOGLE_CALENDAR_TOKEN_JSON` must be valid JSON (not base64); `json.loads()` called at startup
- Cloud Vision `face_annotations[0]` will crash if list is empty → always guard with `if response.face_annotations:`
- `gemini-3-flash-preview` must be validated at startup; wrong name = SystemExit
- Silence gating breaks STT — send ALL audio, always
