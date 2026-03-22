# Architecture

**Analysis Date:** 2026-03-22

## Pattern Overview

**Overall:** Async event-driven pipeline architecture with fire-and-forget task dispatch

**Key Characteristics:**
- Per-session stateful WebSocket connection (one `VoicePipeline`, `TranscriptBuffer`, `ActionSession` per client)
- Three independent input streams: voice (Cloud STT), vision (Cloud Vision frames), and control messages
- Streaming text processing with buffered understanding extraction via Gemini
- Fire-and-forget async task dispatch for external API calls (Slack, Calendar, Gmail)
- Sentiment-gated action execution — negative/uncertain face sentiment can block actions

## Layers

**Presentation (Browser):**
- Purpose: Capture voice + video input, display real-time transcripts, action cards, sentiment pills
- Location: `static/index.html`, `static/app.js`, `static/app/*.js`
- Contains: DOM bindings (core.js), WebSocket session management (session.js), rendering logic (render.js), media capture (media.js), document UI (documents.js)
- Depends on: WebSocket API, Web Audio API, getUserMedia, Canvas for vision overlay
- Used by: End-user browser clients

**Input Layer (FastAPI):**
- Purpose: Accept and route WebSocket audio + frame POST requests; manage session lifecycle
- Location: `backend/main.py` (lines 101-302)
- Contains: WebSocket handler `/ws/audio`, frame endpoint `/api/frame`, static file serving, CORS middleware, session registry lookup
- Depends on: FastAPI, WebSocket, Starlette
- Used by: Browser clients via WebSocket + HTTP

**Voice Pipeline:**
- Purpose: Stream PCM audio to Google Cloud Speech-to-Text v1, emit interim + final transcripts
- Location: `backend/voice.py`
- Contains: `VoicePipeline` class managing async audio queue, connection lifecycle, 4-minute proactive reconnect logic, callback dispatch
- Depends on: `google.cloud.speech_v1`, `SpeechAsyncClient`
- Used by: `main.py` WebSocket handler, receives audio chunks via `send_audio()`, calls `on_transcript()` + `on_interim()` callbacks

**Vision Pipeline:**
- Purpose: Analyze JPEG frames for facial sentiment; normalize likelihoods to 0–1; debounce to 2-second intervals
- Location: `backend/vision.py`
- Contains: `analyze_frame()` async function, `VisionState` dataclass for debounce tracking, `_parse_vision_response()` for Cloud Vision response parsing, `_norm()` likelihood normalization map
- Depends on: `google.cloud.vision`, `ImageAnnotatorClient`
- Used by: `main.py` POST `/api/frame`, stores result in session state, passed to understanding + action gating

**Understanding Layer:**
- Purpose: Buffer transcript segments and emit structured intent extraction (commitments, agreements, meeting_requests, document_revisions) via Gemini Flash
- Location: `backend/understanding.py`
- Contains: `TranscriptBuffer` class (2-second cooldown flush, 30-char minimum, 600-char hard flush), `understand_transcript()` async function (Gemini API call with 3 retries + rate-limit handling), prompt template with date/sentiment rules
- Depends on: `google.genai` (Gemini Flash `gemini-3-flash-preview`), `asyncio.Semaphore(4)` for concurrency control
- Used by: `main.py` on_transcript callback (routes to `buf.process()`), emits understanding results via `_handle_understanding()` callback

**Action Dispatch Layer:**
- Purpose: Convert understanding results into API calls (Slack, Google Calendar, document revisions, task log, Gmail summaries); gate on sentiment
- Location: `backend/actions.py`, `backend/documents.py`, `backend/email_summary.py`
- Contains: `ActionSession` class (per-session), `dispatch()` method (sentiment gating: negative/uncertain blocks), Slack client (`_get_slack()` lazy-init), Calendar OAuth2 client (`get_calendar_service()`), Gemini document revision (`revise_document()`), Gmail summary sender (`send_meeting_summary()`)
- Depends on: `slack_sdk.web.async_client`, `googleapiclient.discovery`, `google.oauth2.credentials`, Gemini (revision calls)
- Used by: `main.py` `_dispatch()` fire-and-forget task, background tasks set (`_bg_tasks`)

**Session State Registry:**
- Purpose: Track per-WebSocket session state (document content, vision sentiment, meeting metadata)
- Location: `backend/session_state.py`
- Contains: `MeetingSessionState` dataclass, `VisionState` dataclass, `SessionRegistry` dictionary-backed registry
- Depends on: None (pure data classes)
- Used by: `main.py` session lookup, vision frame analysis storage, document widget state

**Type Contracts:**
- Purpose: Define TypedDict schemas for all message shapes (transcript, understanding, action results)
- Location: `backend/contracts.py`
- Contains: `UnderstandingResult`, `Commitment`, `Agreement`, `MeetingRequest`, `DocumentRevision`, `ActionResult`, `TranscriptPayload`, `SentimentPayload`, message constructors `make_ws_message()`, `has_action_items()`
- Depends on: `typing.TypedDict`, `typing.Literal`
- Used by: All backend modules for type hints; frontend contracts validation

## Data Flow

**Main Meeting Flow:**

1. Browser connects WebSocket → `main.py` `/ws/audio` handler instantiates `VoicePipeline`, `TranscriptBuffer`, `ActionSession`
2. Browser sends 16kHz PCM chunks via binary WebSocket frames → `pipeline.send_audio(chunk)`
3. VoicePipeline streams to Cloud STT, receives interim + final transcripts → `on_interim(text)` + `on_transcript(text)` callbacks
4. `on_interim()` sends `{"type": "interim", "data": {"text": "..."}}` to browser for low-latency display
5. `on_transcript(text)` appends to transcript segments, calls `buf.process(text, face_sentiment, on_result=_handle_understanding)`
6. TranscriptBuffer waits 2 seconds of silence, flushes ≥30 chars or ≥600 chars hard limit → `understand_transcript(segment, face)`
7. Gemini Flash extracts commitments/agreements/meeting_requests/document_revisions + sentiment → returns `UnderstandingResult` TypedDict
8. If `has_action_items(understanding)`, spawn `_dispatch(understanding)` as fire-and-forget `asyncio.create_task()`
9. Dispatch checks `face_sentiment.latest_sentiment()` (negative/uncertain blocks action), calls:
   - `_post_slack()` for commitments + agreements → `{"type": "slack", "status": "sent", ...}`
   - `create_calendar_event()` for meeting_requests → `{"type": "calendar", "status": "sent", ...}`
   - `revise_document()` + `_upload_slack_file()` for document_revisions → `{"type": "document", "status": "sent", ...}`
   - Appends to `session.task_log` for task tracking
10. Each action result sent to browser via `make_ws_message("action", action)` → rendered as action card on `#actions-feed`
11. Browser optionally sends JPEG frame via POST `/api/frame` → Vision analyzes, updates session state, next understanding call includes face sentiment
12. Client sends `{"type": "stop"}` or disconnects → `finally:` block flushes buffer, waits for pending `_bg_tasks`, sends meeting summary email, emits `{"type": "done"}`

**State Management:**

- Per-session: `TranscriptBuffer._buf`, `ActionSession._task_log`, `MeetingSessionState.document_content`
- Cross-session: `VisionState.latest_result` (shared vision analyzer, debounced)
- Async lifecycle: pending tasks held in `_bg_tasks` set to prevent GC; background flushes in `_execute_flush()` survive cooldown cancellations

## Key Abstractions

**VoicePipeline:**
- Purpose: Encapsulate Cloud STT v1 streaming lifecycle
- Examples: `backend/voice.py` lines 24–163
- Pattern: Async queue-fed generator pattern; proactive reconnect at 4 min; self-healing loop

**TranscriptBuffer:**
- Purpose: Accumulate short transcript segments into batches for efficient Gemini calls
- Examples: `backend/understanding.py` lines 132–223
- Pattern: Cooldown-triggered coalescing; hard flush at size threshold; independent flush task spawning

**ActionSession:**
- Purpose: Encapsulate per-session action dispatch and task logging
- Examples: `backend/actions.py` (class definition + `dispatch()` method)
- Pattern: Sentiment gating as boolean gate in dispatch logic; lazy Slack client initialization

**SessionRegistry:**
- Purpose: Map WebSocket session ID → mutable session state
- Examples: `backend/session_state.py` lines 38–57
- Pattern: Dictionary-backed registry with no cleanup signals (cleanup on WebSocket close via `session_registry.discard()`)

## Entry Points

**WebSocket Handler:**
- Location: `backend/main.py` lines 101–273
- Triggers: Client connects to `/ws/audio?session_id=...`
- Responsibilities: Instantiate pipelines, coordinate receive loop + voice pipeline, dispatch understanding, flush buffer on close, send summaries

**REST Endpoints:**
- `/health` — Liveness probe (line 84–86)
- `/api/frame` — Vision frame submission (line 290–301)
- `/api/document` — Document state query (line 279–287)
- `/` — Serve `index.html` with no-cache headers (line 89–98)

**Browser Entry Point:**
- Location: `static/index.html` + `static/app.js`
- Loads: `static/app/core.js`, `static/app/render.js`, `static/app/media.js`, `static/app/documents.js`, `static/app/session.js` (modular JS architecture)
- Initialization: `window.MeetingAgent` namespace, DOM binding, event listeners for start/stop buttons

## Error Handling

**Strategy:** Log first, fail gracefully or retry

**Patterns:**
- Voice pipeline: Connection errors trigger auto-reconnect loop; hard failure closes WebSocket with error message sent to client
- Gemini calls: Rate-limit retries (exponential backoff up to 35 seconds); JSON decode errors log full response, return empty understanding
- Slack/Calendar: Errors logged + returned as action result with `"status": "failed"` or `"skipped"`; Slack auto-join on channel-not-found error
- Vision: Any exception caught, logged, returns `None`; debounce continues
- Validation: No client-side silence gating (disabled by design); no blocking STT sample-rate checks (logged once at startup)

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module, INFO level baseline
- Pattern: Short session ID prefix `[sid]` for correlation; structured log messages with context (e.g., "STT final: %.80s")
- Locations: All modules use `logger = logging.getLogger(__name__)` at module level

**Validation:**
- Vision: Always guard `len(face_annotations) > 0` before indexing (line 52, `backend/vision.py`)
- Sentiment: `_norm()` map ensures enum→float normalization in one place (line 83–87, `backend/vision.py`)
- Understanding: JSON schema validation via TypedDict; malformed Gemini responses return empty dict
- WebSocket: Message type validation via `contracts.wsTypes` set; malformed JSON ignored

**Authentication:**
- Gemini: API key via env `GOOGLE_API_KEY`; shared global `genai.Client` instance
- Calendar: OAuth2 token JSON loaded at startup; shared `_calendar_creds` global used by `_build_calendar_service()`
- Slack: Bot token via env `SLACK_BOT_TOKEN`; lazy-init `AsyncWebClient`
- Vision/STT: Google Cloud Application Default Credentials (`gcloud auth application-default login`)

**Concurrency Control:**
- Vision: `asyncio.Semaphore(3)` — max 3 concurrent Vision API calls (line 10, `backend/vision.py`)
- Understanding: `asyncio.Semaphore(4)` — max 4 concurrent Gemini understanding calls (line 23, `backend/understanding.py`)
- WebSocket: Per-session independence; no global state contention (session registry is thread-safe dict lookup)
- Async/thread safety: `asyncio.to_thread()` wraps sync Vision + Calendar SDKs; no event loop blocking

---

*Architecture analysis: 2026-03-22*
