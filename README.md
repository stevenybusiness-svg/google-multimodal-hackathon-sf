# AI Meeting Autopilot

**Your autonomous assistant that immediately executes action items you say in a meeting. Informed by real-time voice and video sentiment analysis.**

An AI meeting agent that **sees** (Cloud Vision facial sentiment), **hears** (Cloud STT real-time transcription), **understands** (Gemini intent extraction), and **acts** (Slack + Calendar + tasks + docs + Looker Studio reports + email) — autonomously, with no human gate. Actions fire within 5 seconds of detection. Say "Generate a report on CAC by channel" mid-meeting and a full **Google Looker Studio report** with interactive Chart.js visualizations is generated live, queried from BigQuery via Gemini NL-to-SQL, and posted to Slack — all before the next sentence.

**Built for:** [Multimodal Frontier Hackathon](https://multimodal-frontier-hackathon.devpost.com/) (March 28, 2026, San Francisco)

**Live Demo:** [https://meeting-agent-ynzg64zhoa-uc.a.run.app/](https://meeting-agent-ynzg64zhoa-uc.a.run.app/)

Powered by Google Cloud & Gemini

---

## Technical Depth

### Real-Time Streaming Pipeline (< 5s end-to-end)

```
Browser PCM (16kHz) → WebSocket → Cloud STT v1 Streaming → TranscriptBuffer
    → Gemini Understanding → Sentiment Gating → ActionSession.dispatch()
        ├─ Slack post (async)
        ├─ Google Calendar event (async)
        ├─ Document revision via Gemini → Slack upload (async)
        ├─ BigQuery NL-to-SQL report (async)
        └─ Gmail meeting summary (at meeting end)
```

| Component | Implementation | Why |
|-----------|---------------|-----|
| **TranscriptBuffer** | 2s cooldown batching, flush on sentence boundary or 500 chars | Coalesces speech segments, minimizes Gemini API calls |
| **Action dispatch** | `asyncio.create_task()` + `set` for GC prevention | Fire-and-forget: Slack/Calendar/docs execute without blocking audio pipeline |
| **Session isolation** | `SessionState` dataclass registry per WebSocket | Zero cross-session bleed in concurrent meetings |
| **STT reconnect** | Proactive at 4 min (before 5-min hard limit), 50-frame audio queue | Seamless continuous transcription |
| **Sentiment gating** | Deterministic: only explicit verbal opposition blocks. Face sentiment = supplementary | No false positives from a momentary frown |
| **Vision pipeline** | 2s debounce, asyncio.Semaphore(3), emotion normalization 0-1 | Rate-limited, near-real-time face state |

### Per-Session Architecture

Each WebSocket connection instantiates its own `TranscriptBuffer`, `ActionSession`, and `VisionState`. A single uvicorn worker handles multiple concurrent meetings. Background tasks (`_bg_tasks` set) prevent garbage collection of in-flight API calls. At meeting end, all pending tasks are awaited before the session is torn down.

---

## Sponsor Integrations

### 1. DigitalOcean — Knowledge Base + Inference

Cross-meeting memory powered by DO Serverless Inference (`inference.do-ai.run/v1/`, `llama3.3-70b-instruct`).

- **Meeting archival** — Full transcript + extracted actions archived to Knowledge Base at meeting end
- **Chat interface** — Natural language queries against past meetings ("What did we commit to last week?")
- **Context injection** — Prior commitments and decisions injected into Gemini's understanding prompt for meeting continuity
- **Live status** — KB availability, document count, and archive confirmations displayed in real time

**Code:** [`backend/sponsor_digitalocean.py`](backend/sponsor_digitalocean.py) | [`static/chat.html`](static/chat.html)

### 2. Railtracks — Agentic Framework

Multi-agent orchestration with sentiment-gated routing across 4 specialist nodes.

- **TranscriptAnalyzer** — Extracts structured commitments, agreements, meeting requests
- **SentimentMonitor** — Evaluates combined face + text sentiment before routing to execution
- **ActionExecutor** — Dispatches to Slack, Calendar, tasks, documents
- **MeetingMemory** — Stores commitments + agreements for cross-meeting recall
- **Flow visualization** — Real-time agent status (idle/running/blocked) in the UI

**Code:** [`backend/sponsor_railtracks.py`](backend/sponsor_railtracks.py)

### 3. assistant-ui — Chat Interface

Conversational UI for querying the DigitalOcean Knowledge Base during and after meetings.

- **Real-time chat** — Ask natural language questions about past meetings ("What did we commit to last week?") and get instant answers from the KB
- **Meeting context** — Chat is scoped to archived meeting data, providing relevant prior decisions and open commitments
- **Branded integration** — assistant-ui badge in the KB panel links directly to the chat interface
- **Seamless UX** — Chat opens in a dedicated view with dark theme styling consistent with the main app

**Code:** [`static/chat.html`](static/chat.html)

---

## Google Cloud Services

| Service | Purpose | Code |
|---------|---------|------|
| **Gemini API** (`gemini-3-flash-preview`) | Transcript understanding, document revision, NL-to-SQL | [`understanding.py`](backend/understanding.py), [`documents.py`](backend/documents.py), [`bigquery.py`](backend/bigquery.py) |
| **Cloud Speech-to-Text v1** | Real-time streaming transcription (interim + final) | [`voice.py`](backend/voice.py) |
| **Cloud Vision API** | Face detection + emotion analysis | [`vision.py`](backend/vision.py) |
| **Google Calendar API** | Create events from spoken meeting requests | [`actions.py`](backend/actions.py) |
| **Gmail API** | Send meeting summary emails | [`email_summary.py`](backend/email_summary.py) |
| **BigQuery** | NL-to-SQL report generation | [`bigquery.py`](backend/bigquery.py) |
| **Cloud Run** | Production deployment | [`Dockerfile`](Dockerfile) |

---

## How It Works

1. **You speak** — browser captures 16kHz PCM audio via WebSocket
2. **Cloud STT** streams interim + final transcripts in ~300ms
3. **Gemini** extracts structured data: commitments, meeting requests, document changes
4. **Cloud Vision** reads facial sentiment from your webcam (green/red/gray overlay)
5. **Actions fire automatically** — Calendar events, Slack messages, document revisions, and **live Looker Studio reports** (Gemini converts natural language → SQL → BigQuery query → interactive HTML report with Chart.js charts + Looker Studio link, posted to Slack in seconds)
6. **Sponsor pipeline** — Railtracks routes through specialist agents, Unkey generates audit keys, DigitalOcean archives to Knowledge Base
7. **Meeting ends** — Gmail sends a full summary email; transcript archived to DO Knowledge Base

---

## Quick Start

### Prerequisites

- Python 3.12+
- GCP project with Speech-to-Text, Vision, Calendar, Gmail, and BigQuery APIs enabled
- Gemini API key
- Slack workspace with a bot token

### 1. Clone and configure

```bash
git clone <repo-url>
cd meeting-agent
cp .env.example .env
```

### 2. Environment variables

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Gemini API key |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `SLACK_BOT_TOKEN` | Slack bot token (`xoxb-...`) |
| `SLACK_CHANNEL` | Target Slack channel |
| `GOOGLE_CALENDAR_TOKEN_JSON` | OAuth2 token JSON (see below) |
| `DO_MODEL_ACCESS_KEY` | DigitalOcean inference API key |

### 3. Generate Calendar + Gmail OAuth2 token

```bash
python scripts/get_calendar_token.py
# Complete browser auth flow → copy JSON into .env
```

### 4. Authenticate for Cloud Vision + Speech-to-Text

```bash
gcloud auth application-default login
```

### 5. Install and run

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8080
# Open http://localhost:8080
```

## Deploy to Cloud Run

```bash
gcloud run deploy meeting-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars \
    GOOGLE_API_KEY=<key>,\
    GOOGLE_CLOUD_PROJECT=<project>,\
    SLACK_BOT_TOKEN=<token>,\
    SLACK_CHANNEL=<channel>,\
    GOOGLE_CALENDAR_TOKEN_JSON='<json>',\
    DO_MODEL_ACCESS_KEY=<key>,\
```

---

## Project Structure

```
backend/
  main.py                 # FastAPI app, WebSocket handler, session lifecycle
  voice.py                # Cloud STT v1 streaming with 4-min auto-reconnect
  understanding.py        # Gemini understanding + TranscriptBuffer
  actions.py              # Slack, Calendar, document, task dispatch
  documents.py            # Marketing brief + Gemini-powered revision
  vision.py               # Cloud Vision face detection + sentiment
  bigquery.py             # NL-to-SQL report generation
  email_summary.py        # Gmail meeting summary
  sponsor_digitalocean.py # DO Knowledge Base + inference
  sponsor_railtracks.py   # Railtracks multi-agent orchestration
  sponsor_unkey.py        # Unkey audit trail + kill switch
  contracts.py            # Shared types and message constructors
  session_state.py        # Per-session state registry
static/
  index.html              # Dark theme UI (Tailwind CSS)
  chat.html               # DO Knowledge Base chat interface
  app.js                  # App entry point
  app/                    # Modular JS: core, render, media, session, sponsors
scripts/
  get_calendar_token.py   # OAuth2 flow for Calendar + Gmail
```

## Built With

**Languages:** Python 3.12, JavaScript (ES2020+), HTML5, CSS (Tailwind)

**Google Cloud:** Gemini API, Cloud Speech-to-Text v1, Cloud Vision API, Calendar API, Gmail API, BigQuery, Cloud Run

**Sponsors:** DigitalOcean (Knowledge Base + Inference), Railtracks (Agentic Framework), assistant-ui (Chat Interface)

**Libraries:** FastAPI, Uvicorn, Slack SDK, OpenAI SDK, WebSocket, Docker, Terraform
