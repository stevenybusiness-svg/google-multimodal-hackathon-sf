# Google Meet Premium: AI Meeting Agent — Architecture

## System Architecture

```mermaid
flowchart TD
    Browser["Browser Client\n(Chrome / Safari)\n16kHz PCM capture\nWebcam JPEG stream"]

    Browser -->|"PCM 16kHz audio\nWebSocket /ws/audio\nbinary frames"| WS
    Browser -->|"JPEG webcam frames\nPOST /api/frame\n~200ms capture interval"| FRAME

    subgraph GCP["Google Cloud Run · FastAPI · Async Python"]
        WS["WebSocket Handler\nbidirectional · binary mode\nper-connection session state"]
        FRAME["/api/frame Endpoint\nasync image ingestion"]

        WS --> Pipeline["VoicePipeline\nauto-reconnect at 4 min\n(Google 5-min hard limit)"]
        Pipeline -->|"interim transcripts\n(~300ms latency)\n+ final transcripts"| Buffer

        subgraph Concurrency["Async Concurrency Control"]
            Buffer["TranscriptBuffer\n2s cooldown timer\n30-char min · 600-char hard flush\nsentence-boundary detection"]
            Understanding["Gemini Understanding\ngemini-3-flash-preview\nSemaphore(4) rate limiter\nExponential backoff (2s, 4s)\nJSON schema extraction"]
            FlushTask["Independent Flush Tasks\nfire-and-forget · survives\ntimer cancellation"]
        end

        Buffer -->|"cooldown fires"| FlushTask
        FlushTask -->|"coalesced text\n+ face sentiment context"| Understanding

        FRAME --> Vision["Vision Analyzer\n5s debounce · Semaphore(3)\nasyncio.to_thread() wrapper"]
        Vision -->|"joy/sorrow/anger/surprise\nlikelihood → normalized score"| Buffer

        Understanding -->|"structured extraction:\ncommitments · agreements\nmeeting_requests\ndocument_revisions\nsentiment analysis"| Router{{"Action Router\nhas_action_items?"}}

        Router -->|"sentiment only"| SentimentWS["WebSocket → Browser\nsentiment pill update"]
        Router -->|"actionable items"| Dispatch["ActionSession\nper-session state\nin-memory task log\nfire-and-forget dispatch"]

        Dispatch -->|"commitments\nagreements"| SlackAction["Slack Dispatch\nchat:write + files_upload_v2"]
        Dispatch -->|"meeting_requests\ndate/time parsing"| CalendarAction["Calendar Dispatch\nOAuth2 token refresh\nevents.insert"]
        Dispatch -->|"document_revisions\nspoken → structured"| DocAction["Document Revision\nGemini rewrite pipeline\n+ Slack file upload"]

        SlackAction -->|"action card + sentiment"| ActionWS["WebSocket → Browser\nsentiment-linked cards\ncolored borders + icons"]
        CalendarAction -->|"action card + sentiment"| ActionWS
        DocAction -->|"action card + sentiment"| ActionWS
    end

    WS -->|"bidirectional\nPCM stream"| CloudSTT["Google Cloud\nSpeech-to-Text v1\nStreaming API\nmodel: latest_long\ninterim_results: true"]
    CloudSTT -->|"StreamingRecognizeResponse\nis_final flag"| Pipeline

    FRAME -->|"JPEG bytes\nbatch_annotate_images"| CloudVision["Google Cloud\nVision API\nFACE_DETECTION\n+ LABEL_DETECTION"]
    CloudVision -->|"FaceAnnotation\njoy/sorrow/anger/surprise\nLikelihood enum"| Vision

    Understanding -.->|"aio.models.generate_content\nJSON response_schema\nretry w/ backoff"| GeminiAPI["Gemini API\ngemini-3-flash-preview\n(understanding + revision)"]
    DocAction -.->|"document rewrite\nprompt + current doc"| GeminiAPI

    SlackAction -->|"chat:write\nfiles_upload_v2"| SlackAPI["Slack API"]
    CalendarAction -->|"events.insert\nOAuth2 w/ auto-refresh"| CalendarAPI["Google Calendar API"]

    subgraph PostMeeting["End-of-Meeting Pipeline"]
        Summary["Build Summary\ntranscript + actions\n+ commitments + sentiment"]
        EmailAction["Gmail API\nusers.messages.send\nMIME multipart email\nOAuth2 (shared creds)"]
        Summary --> EmailAction
    end

    WS -->|"connection close\ntriggers cleanup"| Summary
    EmailAction -->|"HTML summary email"| Recipients["All Participants\n(configured recipients)"]

    style GCP fill:#1a1a2e,stroke:#30363d,color:#c9d1d9
    style Concurrency fill:#12122a,stroke:#a855f7,color:#e9d5ff
    style Browser fill:#0d1117,stroke:#57abff,color:#c9d1d9
    style GeminiAPI fill:#1a0a2e,stroke:#a855f7,color:#e9d5ff
    style CloudSTT fill:#0a1a2e,stroke:#57abff,color:#bfdbfe
    style CloudVision fill:#0a1a2e,stroke:#57abff,color:#bfdbfe
    style SlackAPI fill:#1a0a0e,stroke:#e74c3c,color:#fecaca
    style CalendarAPI fill:#0a2e1a,stroke:#3fb950,color:#bbf7d0
    style PostMeeting fill:#1a1a0e,stroke:#e3b341,color:#fef3c7
    style Router fill:#1a1a2e,stroke:#f97316,color:#fed7aa
```

## Real-Time Data Flow

```
 T+0.0s   User speaks: "Let's schedule a follow-up Tuesday at 2pm"
 │
 T+0.1s   Browser MediaRecorder captures PCM chunk → WebSocket binary frame
 │
 T+0.3s   Cloud STT returns interim transcript (is_final=false)
 │         → Browser renders italicized preview text
 │         → Actions panel: pulsing "Analyzing transcript..." indicator
 │
 T+1.0s   Cloud STT returns final transcript (is_final=true)
 │         → Browser commits text to transcript log
 │         → TranscriptBuffer appends segment, resets 2s cooldown timer
 │
 T+1.2s   Webcam frame captured → Vision API face detection
 │         → joy_likelihood: VERY_LIKELY → normalized to "positive"
 │         → Cached in buffer as current face sentiment
 │
 T+3.0s   Cooldown fires (2s since last segment)
 │         → Spawns independent _execute_flush task (survives cancellation)
 │         → Sends coalesced text + sentiment to Gemini understanding
 │
 T+3.1s   Gemini gemini-3-flash-preview extracts structured JSON:
 │         {
 │           "meeting_requests": [{"when": "Tuesday 2pm", "who": ["team"]}],
 │           "sentiment": "positive",
 │           "commitments": [],
 │           "document_revisions": []
 │         }
 │
 T+3.5s   ActionSession dispatches (fire-and-forget):
 │         → Calendar: events.insert (OAuth2, auto-refresh if expired)
 │         → Sentiment pill updated via WebSocket
 │
 T+4.0s   Action card appears in Browser UI:
 │         → "Calendar · Confident" with green left border
 │         → Linked to facial sentiment at T+1.2s capture time
 │
 T+End    WebSocket closes → meeting cleanup triggers:
 │         → Build HTML summary (transcript + all actions + sentiment log)
 │         → Gmail: users.messages.send (MIME email, shared OAuth2 creds)
 │         → Session state garbage collected
```

## Concurrency Architecture

```
Main Event Loop (asyncio)
├── WebSocket /ws/audio (per connection)
│   ├── _recv_loop: binary frames → VoicePipeline.send_audio()
│   ├── VoicePipeline._run_stream: Cloud STT bidirectional streaming
│   │   ├── _request_gen: yields StreamingRecognizeRequest (audio chunks)
│   │   └── response handler: interim/final → TranscriptBuffer.add()
│   └── _watch_session: polls session for outbound messages → ws.send()
│
├── TranscriptBuffer (per session)
│   ├── Cooldown timer: asyncio.Task, cancelled + recreated on new speech
│   └── _execute_flush: independent task (not cancellable)
│       └── Gemini semaphore (4 concurrent) → understanding extraction
│           └── ActionSession.dispatch (fire-and-forget tasks)
│               ├── _bg_tasks set (prevents GC of fire-and-forget tasks)
│               └── Each action: Slack / Calendar / Doc revision
│
├── POST /api/frame (debounced)
│   └── asyncio.to_thread(vision_client.batch_annotate_images)
│       └── Result cached globally (5s debounce window)
│
└── Connection close handler
    ├── Drain _bg_tasks (wait for in-flight actions)
    ├── Build summary → Gmail send
    └── Cleanup session state
```

## Google Cloud Services (6 Services, 15+ API Calls)

| Service | SDK | Key API Calls | Concurrency Control | File |
|---------|-----|---------------|---------------------|------|
| **Gemini API** | `google-genai` | `aio.models.generate_content` (understanding), `aio.models.generate_content` (doc revision), `models.get` (startup validation) | Semaphore(4), exponential backoff 2s/4s, 3 retries | `understanding.py`, `documents.py`, `main.py` |
| **Cloud Speech-to-Text v1** | `google-cloud-speech` | `streaming_recognize` (bidirectional), `StreamingRecognizeRequest` (config + audio) | Auto-reconnect at 4 min (5-min Google limit), single stream per session | `voice.py` |
| **Cloud Vision API** | `google-cloud-vision` | `batch_annotate_images` (FACE_DETECTION + LABEL_DETECTION) | Semaphore(3), 5s debounce, `asyncio.to_thread` (sync SDK) | `vision.py` |
| **Google Calendar API** | `google-api-python-client` | `events().insert()`, `credentials.refresh()` | OAuth2 auto-refresh, `asyncio.to_thread` (sync SDK) | `actions.py` |
| **Gmail API** | `google-api-python-client` | `users().messages().send()`, `credentials.refresh()` | Shared OAuth2 creds with Calendar, MIME construction | `email_summary.py` |
| **Cloud Run** | Docker | Container hosting (python:3.12-slim, port 8080) | Unauthenticated, us-central1, custom SA | `Dockerfile` |

## Key Design Decisions

| Decision | Rationale | Technical Detail |
|----------|-----------|-----------------|
| Cloud STT v1 streaming (not batch) | ~300ms interim results enable real-time UX | Bidirectional streaming with `interim_results=true`, `latest_long` model |
| 2s transcript buffer cooldown | Balances API cost vs. perceived latency | Reduced from 8s after testing; 30-char min prevents empty flushes |
| Independent flush tasks | Prevents race condition: new audio cancelling in-flight Gemini calls | `_execute_flush` spawned as separate `asyncio.Task`, survives timer `cancel()` |
| Fire-and-forget action dispatch | Slack/Calendar (~1s each) must not block STT receive loop | `asyncio.create_task()` + `_bg_tasks` set prevents garbage collection |
| Per-session state isolation | No bleed across concurrent WebSocket connections | `TranscriptBuffer` + `ActionSession` instantiated per connection, cleaned up on close |
| Sentiment-linked action cards | Face sentiment at capture time gives context to commitments | Vision result cached globally, attached to understanding output, rendered as colored card borders |
| Shared OAuth2 token (Calendar + Gmail) | Single auth flow covers both scopes | `calendar.events` + `gmail.send` in one token; auto-refresh before each API call |
| `asyncio.to_thread()` for sync SDKs | Vision + Calendar SDKs are synchronous | Wrapping prevents blocking the async event loop |
| Proactive STT reconnect at 4 min | Google enforces 5-min streaming limit silently | Timer-based reconnect with seamless transcript continuity |
| Gemini JSON schema extraction | Structured output ensures reliable action parsing | `response_schema` parameter enforces typed JSON output from LLM |
