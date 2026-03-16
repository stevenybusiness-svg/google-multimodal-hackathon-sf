# Google Meet Premium: AI Meeting Agent

An autonomous meeting agent that listens to conversations in real time, detects commitments, meeting requests, agreements, and document revisions, then **immediately acts** — creating Google Calendar events, sending Slack messages, revising shared documents, and emailing meeting summaries. No human gate. No post-meeting review.

**Built for:** [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/)

**Live Demo:** [https://meeting-agent-974516981471.us-central1.run.app](https://meeting-agent-974516981471.us-central1.run.app)

## Google Cloud Services Used

| Service | Purpose | Code Reference |
|---------|---------|----------------|
| **Gemini API** (`gemini-3-flash-preview`) | Transcript understanding + document revision | [`backend/understanding.py`](backend/understanding.py), [`backend/documents.py`](backend/documents.py) |
| **Cloud Speech-to-Text v1** | Real-time streaming voice transcription | [`backend/voice.py`](backend/voice.py) |
| **Cloud Vision API** | Face detection + emotion/sentiment analysis | [`backend/vision.py`](backend/vision.py) |
| **Google Calendar API** | Create calendar events from spoken meeting requests | [`backend/actions.py`](backend/actions.py) |
| **Gmail API** | Send meeting summary email to participants | [`backend/email_summary.py`](backend/email_summary.py) |
| **Cloud Run** | Production deployment (Docker, us-central1) | [`Dockerfile`](Dockerfile) |

## How It Works

1. **You speak** — browser captures 16kHz PCM audio via WebSocket
2. **Cloud STT** streams interim + final transcripts in ~300ms
3. **Gemini** extracts structured data: commitments, meeting requests, document changes, sentiment
4. **Cloud Vision** reads facial sentiment from your webcam
5. **Actions fire automatically** — Calendar events, Slack messages, document revisions
6. **Meeting ends** — Gmail sends a full summary email to all participants

Each action card in the UI is **linked to facial sentiment** at capture time — if someone commits to something while looking uncertain, the card flags it.

## Architecture

See [`submission-materials/architecture-diagram.md`](submission-materials/architecture-diagram.md) for the full Mermaid diagram and data flow timeline.

See [`submission-materials/google-cloud-deployment.md`](submission-materials/google-cloud-deployment.md) for a complete catalog of every Google API call with file/line references.

## Quick Start (Local)

### Prerequisites

- Python 3.12+
- A GCP project with Speech-to-Text, Vision, Calendar, and Gmail APIs enabled
- A Gemini API key (paid tier recommended — free tier caps at 20 req/day)
- A Slack workspace with a bot token

### 1. Clone and configure

```bash
git clone <repo-url>
cd meeting-agent
cp .env.example .env
```

Fill in `.env`:

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Gemini API key (paid tier) |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID for Vision + STT billing |
| `SLACK_BOT_TOKEN` | Slack bot token (`xoxb-...`) with `chat:write`, `files:write` scopes |
| `SLACK_CHANNEL` | Target Slack channel (e.g. `#product-launch`) |
| `GOOGLE_CALENDAR_TOKEN_JSON` | OAuth2 token JSON — see step 2 |

### 2. Generate Calendar + Gmail OAuth2 token (one-time)

```bash
# Download credentials.json from GCP Console → APIs & Services → Credentials → OAuth 2.0 Client IDs → Desktop app
python scripts/get_calendar_token.py
# Complete the browser auth flow (grant Calendar + Gmail permissions)
# Copy the printed JSON into .env as GOOGLE_CALENDAR_TOKEN_JSON=<paste here>
```

### 3. Authenticate for Cloud Vision + Speech-to-Text

```bash
gcloud auth application-default login
```

### 4. Install dependencies and run

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8080
# Open http://localhost:8080
```

## Deploy to Google Cloud Run

```bash
gcloud run deploy meeting-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars \
    GOOGLE_API_KEY=<your-key>,\
    GOOGLE_CLOUD_PROJECT=<your-project>,\
    SLACK_BOT_TOKEN=<your-token>,\
    SLACK_CHANNEL=<your-channel>,\
    GOOGLE_CALENDAR_TOKEN_JSON='<your-token-json>'
```

The service will be available at the URL printed by `gcloud run deploy`.

## Project Structure

```
backend/
  main.py              # FastAPI app: WebSocket handler, API endpoints, session lifecycle
  voice.py             # VoicePipeline: Cloud STT v1 streaming with auto-reconnect
  understanding.py     # TranscriptBuffer + Gemini understanding extraction
  actions.py           # ActionSession: Slack, Calendar, document dispatch
  documents.py         # Marketing brief + Gemini-powered revision
  vision.py            # Cloud Vision face detection + sentiment
  email_summary.py     # Gmail meeting summary sender
  contracts.py         # Shared types and message constructors
  session_state.py     # Per-session state registry
static/
  index.html           # Dark theme UI (Tailwind CSS)
  app.js               # App entry point
  app/                 # Modular JS: core, render, documents, media, session
scripts/
  get_calendar_token.py  # OAuth2 flow for Calendar + Gmail scopes
submission-materials/
  google-cloud-deployment.md  # Complete Google API call catalog
  architecture-diagram.md     # Mermaid architecture diagram
  blog-post.md                # Development blog post
```

## Submission Materials

- [Google Cloud Deployment Reference](submission-materials/google-cloud-deployment.md) — every Google API call with file and line numbers
- [Architecture Diagram](submission-materials/architecture-diagram.md) — Mermaid system flow + data flow timeline
- [Blog Post](submission-materials/blog-post.md) — development journey and technical deep dive
