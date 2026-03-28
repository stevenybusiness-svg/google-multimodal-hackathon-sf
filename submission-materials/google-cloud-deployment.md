# Google Cloud Deployment — API Integration Reference

This document catalogs every Google Cloud and Google API call in the Meeting Agent codebase, organized by service.

## Deployment Target

- **Platform:** Google Cloud Run (fully managed)
- **Region:** `us-central1`
- **Service URL:** `https://meeting-agent-31043195041.us-central1.run.app`
- **Container:** Python 3.12-slim, Dockerfile in project root

## Google APIs Used (6 Services)

### 1. Gemini API (Google GenAI SDK)

The core intelligence layer. All LLM calls use the `google-genai` Python SDK.

| File | Line(s) | Call | Purpose |
|------|---------|------|---------|
| `backend/understanding.py:19` | `genai.Client(api_key=...)` | Initialize Gemini client | Transcript understanding |
| `backend/understanding.py:92` | `client.aio.models.generate_content(model="gemini-3-flash-preview", ...)` | Extract commitments, agreements, meeting requests, document revisions, and sentiment from transcript segments | Core understanding pipeline |
| `backend/documents.py:21` | `genai.Client(api_key=...)` | Initialize Gemini client | Document revision |
| `backend/documents.py:101` | `client.aio.models.generate_content(model="gemini-3-flash-preview", ...)` | Apply spoken revisions to a living marketing brief | Real-time document editing |
| `backend/main.py:45-48` | `genai.Client(api_key=...)` + `client.aio.models.get(model=...)` | Validate models at startup | Fail-fast if Gemini is unreachable |

**Model used:** `gemini-3-flash-preview` (both understanding and revision)
**Concurrency:** Semaphore-limited to 4 concurrent Gemini calls (`understanding.py:23`)

### 2. Google Cloud Speech-to-Text v1 (Streaming)

Real-time voice transcription via bidirectional streaming.

| File | Line(s) | Call | Purpose |
|------|---------|------|---------|
| `backend/voice.py:58` | `SpeechAsyncClient()` | Initialize async STT client | Speech recognition |
| `backend/voice.py:60-70` | `RecognitionConfig(encoding=LINEAR16, sample_rate_hertz=16000, model="latest_long")` | Configure 16kHz PCM English recognition | Continuous meeting transcription |
| `backend/voice.py:81-83` | `StreamingRecognizeRequest(streaming_config=...)` | Initial config request | Start bidirectional STT stream |
| `backend/voice.py:101-103` | `StreamingRecognizeRequest(audio_content=chunk)` | Send audio chunks | Continuous audio ingestion |
| `backend/voice.py:111-130` | `client.streaming_recognize(requests=...)` | Open streaming session, process responses | Produces both interim and final transcripts |

**Reconnection:** Proactive reconnect at 4 minutes (Google's 5-minute hard limit on streaming sessions).

### 3. Google Cloud Vision API

Face detection and sentiment analysis from webcam frames.

| File | Line(s) | Call | Purpose |
|------|---------|------|---------|
| `backend/vision.py:13-16` | `vision.ImageAnnotatorClient(client_options=ClientOptions(quota_project_id=...))` | Initialize Vision client with billing project | Face detection |
| `backend/vision.py:30-36` | `vision.AnnotateImageRequest(features=[FACE_DETECTION, LABEL_DETECTION])` | Build annotation request | Detect faces and labels in webcam frame |
| `backend/vision.py:38-41` | `vision_client.batch_annotate_images(requests=[request])` | Execute face/label detection | Returns emotion likelihoods (joy, sorrow, anger, surprise) |

**Debouncing:** 5-second minimum between calls. Semaphore-limited to 3 concurrent requests.

### 4. Google Calendar API

Create calendar events from detected meeting requests.

| File | Line(s) | Call | Purpose |
|------|---------|------|---------|
| `backend/actions.py:42-46` | `Credentials(**token_dict)` + `build("calendar", "v3", ...)` | Initialize Calendar service with OAuth2 | Calendar event creation |
| `backend/actions.py:209-211` | `_calendar_creds.refresh(google.auth.transport.requests.Request())` | Refresh expired OAuth2 token | Keep credentials valid |
| `backend/actions.py:214-217` | `svc.events().insert(calendarId="primary", body=event).execute()` | Create calendar event | Schedule meetings detected in conversation |

**Auth:** OAuth2 with `calendar.events` scope. Token stored in `GOOGLE_CALENDAR_TOKEN_JSON` env var.

### 5. Gmail API

Send meeting summary email when meeting ends.

| File | Line(s) | Call | Purpose |
|------|---------|------|---------|
| `backend/email_summary.py:27` | `build("gmail", "v1", credentials=_gmail_creds)` | Build Gmail service | Email sending |
| `backend/email_summary.py:106-109` | `_gmail_creds.refresh(...)` | Refresh expired credentials | Keep credentials valid |
| `backend/email_summary.py:111-116` | `svc.users().messages().send(userId="me", body={"raw": raw}).execute()` | Send MIME email | Post-meeting summary to participants |

**Auth:** Shares OAuth2 credentials with Calendar (`gmail.send` scope). Recipients: `temuj627@gmail.com`, `stevenybusiness@gmail.com`.

### 6. Google Cloud Run (Deployment Target)

| Aspect | Detail |
|--------|--------|
| **Service name** | `meeting-agent` |
| **Region** | `us-central1` |
| **Container** | `python:3.12-slim` via Dockerfile |
| **Port** | 8080 |
| **Auth** | Unauthenticated (public) |
| **Service account** | `meeting-agent-sa@project-9c8caefd-92a5-4521-9eb.iam.gserviceaccount.com` |

## Environment Variables

| Variable | Service | Purpose |
|----------|---------|---------|
| `GOOGLE_API_KEY` | Gemini API | API key for all Gemini model calls |
| `GOOGLE_CLOUD_PROJECT` | Cloud Vision, Cloud STT | Billing/quota project ID |
| `GOOGLE_CALENDAR_TOKEN_JSON` | Calendar + Gmail | OAuth2 token JSON (both scopes) |
| `SLACK_BOT_TOKEN` | Slack | Bot token for message posting |
| `SLACK_CHANNEL` | Slack | Target channel for action messages |

## Error Handling & Resilience

- **Gemini rate limits:** Exponential backoff (2s, 4s) with retry budget of 3 attempts. Parses `retryDelay` from error response.
- **STT stream timeout:** Proactive reconnect at 4 minutes avoids Google's 5-minute hard cutoff.
- **Vision debounce:** 5-second minimum between API calls prevents quota exhaustion.
- **OAuth2 refresh:** Automatic credential refresh before Calendar/Gmail calls if token is expired.
- **Startup validation:** `main.py` calls `models.get()` at startup to fail fast if Gemini is unreachable.
