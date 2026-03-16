# Meeting Agent — Architecture

This file is the concise system-flow companion to [PROJECT.md](PROJECT.md). Contract, RCA, and product scope live there.

## System Flow

```mermaid
flowchart TD
    Browser["Browser\n(Chrome / Safari)"]

    Browser -->|"PCM 16kHz chunks\nWebSocket /ws/audio"| WS
    Browser -->|"JPEG frames\nPOST /api/frame"| FRAME

    subgraph CloudRun["FastAPI — Cloud Run"]
        WS["WebSocket handler"]
        FRAME["/api/frame"]
        WS --> Buffer["TranscriptBuffer\nflush on sentence boundary\nor >500 chars"]
        FRAME --> Vision["Vision result\ncached ~5s debounce"]
        Vision --> Buffer
    end

    WS -->|"PCM stream"| GeminiLive["Gemini Live API\ngemini-2.5-flash-native-audio-preview-12-2025\ninput_audio_transcription"]
    GeminiLive -->|"text transcript"| WS
    FRAME -->|"JPEG bytes"| CloudVision["Google Cloud Vision\nFace sentiment\n(VERY_LIKELY → 1.0)"]
    CloudVision --> Vision

    Buffer --> Understand["Gemini Flash\ngemini-2.5-flash\nExtract: commitments\nagreements · meeting_requests\ndocument_revisions · sentiment"]

    Understand -->|"has_actions"| ActionSession["ActionSession\n(per WebSocket session)"]

    ActionSession -->|"commitments\nagreements"| Slack["Slack\nchat:write"]
    ActionSession -->|"meeting_requests"| Calendar["Google Calendar\nOAuth2 events.insert"]
    ActionSession -->|"document_revisions"| Doc["Gemini revision + Slack file upload"]
    ActionSession --> TaskLog["In-memory task log"]

    Slack -->|"action card"| UI["Browser UI\nlive transcript · action cards\nsentiment pill · mic level"]
    Calendar -->|"action card"| UI
    Doc -->|"action card"| UI
    TaskLog --> UI
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Gemini Live as sole STT | Real-time bidirectional streaming with built-in input transcription |
| No silence gating | Gating causes Gemini to miss utterance endings |
| Fire-and-forget dispatch | Slack/Calendar (~1s) must not block Gemini receive loop |
| Per-session `TranscriptBuffer` + `ActionSession` | No state bleed across concurrent WebSocket connections |
| Document revision treated as an action | Keeps the demo focused on live execution, not post-meeting summary |
| Sentiment adjusts content, not gate | ⚠️ flag + 1-day buffer on negative/uncertain; action always fires |
| OAuth2, not API key | Calendar API requires user identity |
| `asyncio.to_thread()` for Vision + Calendar | Both SDKs are sync; wrapping prevents event loop blocking |

## Deploy

```bash
gcloud run deploy meeting-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY=...,SLACK_BOT_TOKEN=...,SLACK_CHANNEL=...,GOOGLE_CLOUD_PROJECT=...,GOOGLE_CALENDAR_TOKEN_JSON=...
```
