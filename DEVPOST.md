## Inspiration

Every meeting tool transcribes. None of them *act*. We've all left meetings with a list of "action items" that rot in a shared doc. The insight was simple: if an AI can understand what was said, why does a human still need to press "Create Event" or "Send Message"? We built an agent that closes the loop — from spoken word to executed action — in real time, with no human gate.

The second insight was that **what people say and what they mean aren't always the same**. Someone might agree to a Friday deadline while frowning. A commitment made with uncertainty in the voice deserves a flag, not blind execution. We wanted sentiment to be an intelligence layer — not a gimmick, but a real-time signal that determines whether actions proceed or get blocked.

## What it does

AI Meeting Autopilot is an autonomous meeting agent that **sees, hears, understands, and acts**:

1. **Hears** — Captures 16kHz PCM audio via WebSocket and streams it to Google Cloud Speech-to-Text v1 for real-time transcription with ~300ms latency. No silence gating — continuous audio stream with proactive 4-minute reconnects before the 5-minute hard limit.
2. **Understands** — Sends transcript segments to Gemini (`gemini-3-flash-preview`) to extract structured data: commitments ("I'll send the deck by Friday"), meeting requests ("Let's sync Tuesday at 1pm"), agreements ("We agreed to cut the budget"), and document revisions ("Reallocate $5K from content to digital").
3. **Sees** — Captures webcam frames every 2 seconds and sends them to Cloud Vision API for face detection and emotion analysis (joy, anger, sadness, surprise). Colored bounding boxes overlay the face in real time — green for positive, red for negative, gray for neutral.
4. **Decides** — Combines text sentiment and facial sentiment to gate actions. Positive/neutral sentiment = action proceeds (green glow). Explicit verbal opposition ("no", "cancel", "don't") = action blocked (red glow). Multimodal intelligence determines what gets executed.
5. **Acts** — Autonomously creates Google Calendar events, posts to Slack, revises documents via Gemini, logs tasks, generates **live Google Looker Studio reports on the fly**, and emails a full meeting summary via Gmail. No human confirmation. Actions fire within seconds of detection.

**Demo moments:**
- Say "Generate a report on customer acquisition cost by channel" → Gemini converts natural language to SQL, BigQuery executes the query, and a full **interactive Looker Studio report** with Chart.js visualizations is generated and posted to Slack — all in under 15 seconds, mid-meeting, without anyone leaving the call
- Say "Let's reallocate $5,000 from content creation to digital marketing" → the agent revises the marketing brief in real time, recalculates the budget table, and posts the updated document to Slack
- Say "Let's schedule a follow-up Friday at 1pm" with a smile → calendar event created, green glow
- Say "Maybe Friday at 4pm?" while frowning → action flagged, red warning arrows on video feed

## Technical Depth

### Real-Time Streaming Pipeline (< 5 second end-to-end latency)

The core architecture is a 4-stage async pipeline running on a single FastAPI/uvicorn worker:

```
Browser PCM Audio → WebSocket → Cloud STT v1 Streaming → TranscriptBuffer
    → Gemini Understanding → Sentiment Gating → ActionSession.dispatch()
        ├─ Slack (async)
        ├─ Google Calendar (async)
        ├─ Document Revision via Gemini (async)
        ├─ BigQuery NL-to-SQL Report (async)
        └─ Gmail Summary (at meeting end)
```

**Key engineering decisions:**
- **TranscriptBuffer with cooldown-based batching** — coalesces related speech segments with a 2-second cooldown, reducing Gemini API calls while maintaining real-time responsiveness. Flushes on sentence boundaries (`.`, `?`, `!`) or when buffer exceeds 500 characters.
- **Fire-and-forget action dispatch** — `asyncio.create_task()` with a `set` for GC prevention. Actions execute concurrently without blocking the audio pipeline. A single meeting can have Slack posts, Calendar events, and document revisions all in-flight simultaneously.
- **Per-session state isolation** — `SessionState` dataclass registry ensures zero cross-session bleed. Each WebSocket connection gets its own `TranscriptBuffer`, `ActionSession`, and `VisionState`.
- **Cloud STT v1 auto-reconnect** — proactive stream cycling at 4 minutes (before Google's 5-minute hard limit). Audio queue with 50-frame capacity and frame dropping on overflow to prevent backpressure.
- **Multimodal sentiment gating** — `_should_block()` uses deterministic blocking: only explicit verbal opposition ("no", "cancel", "don't do that") gates actions. Face sentiment from Cloud Vision (joy, anger, sadness, surprise normalized to 0-1) provides supplementary context — flagging uncertain actions without independently blocking them.

### Vision Pipeline

Cloud Vision API face detection runs on a 2-second debounce with asyncio semaphore rate limiting (max 3 concurrent requests). Emotion likelihoods (0-5 enum) are normalized to continuous 0.0-1.0 scores. A threshold of 0.4 prevents noise from registering as real emotion. Face bounding boxes are returned in pixel coordinates and rendered as colored overlays on a canvas element positioned above the video feed.

### Document Revision

When the agent detects "Change the budget to $75K" or "Reallocate $5K from content to digital," Gemini rewrites the relevant document section with correct arithmetic. The revised document is uploaded to Slack as a file. Prompt engineering includes explicit math rules with worked examples to ensure budget tables calculate correctly.

## Sponsor Integrations

We integrated **3 sponsor tools** deeply into the agent's core functionality:

### 1. DigitalOcean — Knowledge Base + Inference ($1K cash + credits prize)

**Integration:** Cross-meeting memory via DO Serverless Inference (OpenAI-compatible API at `inference.do-ai.run/v1/`) + in-memory Knowledge Base.

- **Meeting archival** — At meeting end, the full transcript + all extracted actions are archived as structured documents in the Knowledge Base. Each subsequent meeting has access to prior context.
- **Chat interface** — Users can query past meetings via natural language ("What commitments did we make last week?"). Powered by DO's `llama3.3-70b-instruct` model.
- **Context injection** — Before Gemini processes a new transcript, the agent queries the KB for relevant prior commitments and decisions, injecting them into the understanding prompt. This creates continuity across meetings.
- **Live status** — KB availability and document count are displayed in the UI with real-time status indicators.

**Files:** [`backend/sponsor_digitalocean.py`](backend/sponsor_digitalocean.py), [`static/chat.html`](static/chat.html)

### 2. Railtracks — Agentic Framework ($1.3K cash prize)

**Integration:** Multi-agent orchestration with specialist nodes and sentiment-gated routing.

- **4 specialist agents** — TranscriptAnalyzer (extracts structured data), SentimentMonitor (gates actions by combined face+text sentiment), ActionExecutor (dispatches to Slack/Calendar/tasks), MeetingMemory (stores commitments + agreements for cross-meeting recall).
- **Sentiment-gated routing** — The SentimentMonitor node evaluates combined face and text sentiment before routing to ActionExecutor. Positive/neutral = proceed. Negative/uncertain = risk-flag or block.
- **Flow visualization** — Real-time agent status (idle/running/blocked) displayed in the UI with colored dot indicators.
- **Decision logging** — Last 50 routing decisions are tracked for debugging and audit.

**Files:** [`backend/sponsor_railtracks.py`](backend/sponsor_railtracks.py)

### 3. Unkey — API Key Management + Audit Trail

**Integration:** Per-action audit trail with ephemeral API keys and session-scoped kill switches.

- **Ephemeral key generation** — Every autonomous action (Slack post, Calendar event, document revision) generates a unique API key with 24-hour expiry and metadata (action type, session, timestamp).
- **Audit trail** — Complete traceability for every action the agent takes. Each key ID maps to exactly one action.
- **Kill switch** — Revoke all API keys for a session in one call, instantly disabling all actions taken during that meeting.
- **Session isolation** — Keys are tracked per-session in an in-memory index for fast lookup.

**Files:** [`backend/sponsor_unkey.py`](backend/sponsor_unkey.py)

## How we built it

**Backend (Python 3.12 / FastAPI):** The server is split into clean pipeline modules — `voice.py` (Cloud STT streaming with 4-minute auto-reconnect), `understanding.py` (Gemini extraction with cooldown-based transcript batching), `actions.py` (action dispatch with sentiment gating), `vision.py` (Cloud Vision with emotion normalization), `documents.py` (Gemini-powered document revision), and `bigquery.py` (NL-to-SQL report generation). Each module is under 350 lines. State is per-session via dataclass registry.

**Frontend (Vanilla JS + Tailwind CSS):** Modular JS architecture — `core.js` (state/DOM), `render.js` (UI rendering with sentiment glow effects), `media.js` (audio/video capture with local face tracking), `session.js` (WebSocket lifecycle), `sponsors.js` (sponsor integration UI). Action cards show green glow for proceeded actions and red glow for blocked ones. No framework — just fast, direct DOM manipulation.

**Deployment:** Docker container on Google Cloud Run (us-central1), with environment variables for all API keys.

## Challenges we ran into

- **Cloud Vision under-reports negative emotions.** A clear frown returns `VERY_UNLIKELY` for anger. We solved this with boosted normalization maps that amplify negative signals, plus text sentiment as a second channel.
- **Gemini returns non-email strings as attendees.** "Let's meet with Sarah" extracts `["Sarah"]` — not an email. Google Calendar API rejects this. We added regex filtering to strip invalid attendees.
- **Budget math in document revisions.** "Reallocate $5K from content to digital" should add and subtract correctly. Gemini sometimes gets arithmetic wrong. We added explicit math rules with worked examples in the revision prompt.
- **Cloud STT 5-minute stream limit.** Google enforces a hard 5-minute limit on streaming connections. We implemented proactive reconnection at 4 minutes with seamless audio continuity.
- **Balancing sentiment sensitivity.** Too sensitive = every neutral face blocks actions. Not sensitive enough = genuine frowns don't register. We landed on deterministic verbal-opposition blocking with face sentiment as a supplementary signal.

## Accomplishments that we're proud of

- **3 autonomous actions fire in under 5 seconds** from spoken input — Slack post + Calendar event + task log, all triggered by multimodal input (voice + facial sentiment).
- **Zero post-meeting friction** — no review step, no confirmation dialog. The agent acts as you speak.
- **Multimodal sentiment as an intelligence layer** — not just transcription, but understanding *how* something was said (face) alongside *what* was said (voice).
- **Production-deployed on Cloud Run** with real Google Calendar events being created, real Slack messages being posted, and real emails being sent.
- **Clean modular architecture** — 15 backend modules, each under 350 lines, all fully async.
- **Deep sponsor integration** — DigitalOcean (cross-meeting memory), Railtracks (multi-agent orchestration), and Unkey (per-action audit trail) are woven into the core pipeline, not bolted on.

## What we learned

- **Multimodal sentiment is harder than it sounds.** Text says one thing, face says another. The conflict is the most interesting signal — and the hardest to act on reliably.
- **Gemini is remarkably good at structured extraction** from natural speech, but needs very explicit prompt engineering for math and brevity.
- **Fire-and-forget async patterns** are essential for real-time agents. You can't block the audio pipeline while waiting for a Calendar API call.
- **Debounce everything.** Vision API, transcript flushing, action dispatch — without careful debouncing, you hit rate limits instantly and waste API calls on partial data.
- **Sponsor tools add real value when deeply integrated.** Cross-meeting memory (DO), multi-agent routing (Railtracks), and action audit trails (Unkey) each solve a genuine problem in the agent's pipeline.

## What's next for AI Meeting Autopilot

- **Speaker diarization** — attribute commitments to specific speakers ("Sarah said she'll send the deck")
- **Multi-meeting continuity** — "Last week you committed to X — any update?" with automatic follow-up actions
- **Richer integrations** — Jira ticket creation, Notion page updates, Google Docs real-time editing
- **Fine-tuned sentiment model** — train on meeting-specific facial expressions instead of relying on Cloud Vision's general-purpose emotion detection
- **Voice cloning for summaries** — generate audio summaries in the meeting participants' voices

## Built With

**Languages:**
- Python 3.12
- JavaScript (ES2020+)
- HTML5
- CSS (Tailwind CSS)

**Google Cloud Services:**
- Gemini API (gemini-3-flash-preview)
- Cloud Speech-to-Text v1
- Cloud Vision API
- Google Calendar API
- Gmail API
- BigQuery
- Cloud Run

**Sponsor Tools:**
- DigitalOcean Serverless Inference + Knowledge Base
- Railtracks Agentic Framework
- Unkey API Key Management

**Infrastructure & Libraries:**
- FastAPI + Uvicorn (async web server)
- WebSocket (real-time audio streaming)
- Slack SDK (async)
- OpenAI SDK (for DO inference endpoint)
- Docker
- Terraform (infrastructure provisioning)
