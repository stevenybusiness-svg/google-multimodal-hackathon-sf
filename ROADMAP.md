# Roadmap — Multimodal Frontier Hackathon (Mar 28, 2026)

> GSD wave-based execution plan. Independent tasks within a wave run in parallel.
> Status: ✅ done · 🔄 in progress · ⬜ todo

## Wave 0 — Core Implementation (COMPLETE)
All backend and frontend code is done.

| Task | File | Status |
|------|------|--------|
| Voice pipeline (Google Cloud STT v1, streaming + interim) | `backend/voice.py` | ✅ |
| Understanding pipeline (Gemini Flash) | `backend/understanding.py` | ✅ |
| Action pipeline (Slack, Calendar, Tasks, Doc) | `backend/actions.py` | ✅ |
| Vision pipeline (Cloud Vision sentiment) | `backend/vision.py` | ✅ |
| FastAPI server + WebSocket handler | `backend/main.py` | ✅ |
| Browser UI (dark theme, live transcript, action cards) | `static/index.html`, `static/app.js` | ✅ |
| Architecture diagram (Mermaid) | `architecture.md` | ✅ |
| Regression tests | `tests/` | ✅ |

---

## Wave 1 — Deploy + Auth (Parallel, both needed before demo)

### W1-A: Google Calendar OAuth2 pre-auth
```bash
python scripts/get_calendar_token.py
# paste output into .env as GOOGLE_CALENDAR_TOKEN_JSON
```
Status: ⬜

### W1-B: Cloud Run deploy
```bash
gcloud run deploy meeting-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY=...,SLACK_BOT_TOKEN=...,SLACK_CHANNEL=...,GOOGLE_CLOUD_PROJECT=...,GOOGLE_CALENDAR_TOKEN_JSON=...
```
Status: ⬜
Deliverable: public URL screenshot for submission proof

---

## Wave 2 — Demo Video (depends on Wave 1)

**Script (≤3 min):**
1. Hook — 0:00–0:20: Split-screen view. Say a commitment + meeting request while camera on. Three action cards fire: Slack + Calendar + task in ~5s. "This agent sees, hears, understands — and acts."
2. Multimodal story — 0:20–1:00: Show facial sentiment pulsing into pipeline. Stressed face → risk flag fires in Slack. The pipeline makes multi-signal fusion visible.
3. Architecture + sponsors — 1:00–2:00: Show live pipeline with sponsor integrations: Railtracks orchestrating the agent flow, Unkey managing API keys + rate limiting, DigitalOcean inference as alternative model backend. Point to thick vs thin edges (text = primary, face = informing).
4. Live deploy — 2:00–2:30: Show Cloud Run URL. Toggle `LLM_PROVIDER=digitalocean` to show DO inference working.
5. Close — 2:30–3:00: "3 sponsor tools. 3 AI models. 3 autonomous actions in 5 seconds. No human gate."

Status: ⬜

---

## Wave 3 — Submission (depends on Wave 2 + Wave 4B)

- [ ] Submit at https://multimodal-frontier-hackathon.devpost.com/
- [ ] Public GitHub repo confirmed
- [ ] Cloud Run URL screenshot attached
- [ ] Demo video uploaded (≤3min)
- [ ] Architecture diagram in submission (shows 3 sponsor integrations)
- [ ] 3+ sponsor tools integrated (DigitalOcean + Unkey + Railtracks)
- [ ] Publish skill to shipables.dev
- [ ] Submit before March 28, 2026 deadline

Status: ⬜

---

## Wave 1.5 — Live Architecture Visualization (parallel with Wave 1)

**Goal:** Split-screen "living pipeline" view that shows data flowing through the multimodal architecture in real-time, side-by-side with action outputs. Visual proof of autonomous decision-making for judges.

### Layout
Left panel: interactive node graph showing the pipeline. Right panel: action output cards as they fire.

### Nodes
| Node | Role | Live stats |
|------|------|-----------|
| Microphone | Audio input | streaming indicator |
| Cloud STT | Speech-to-text | transcript count |
| Camera | Video input | frame indicator |
| Cloud Vision | Facial sentiment | sentiment score (0–1) |
| Gemini Flash | **Central brain** — text agreement is primary signal, weighted by voice tone + facial sentiment | understanding count |
| Action Dispatcher | Routes decisions to outputs | actions fired |
| Slack | Sends messages | message count |
| Calendar | Creates events | event count |
| Task Log | Records commitments | task count |

### Animated edges
- Thicker edges from STT → Gemini (primary signal: text agreement)
- Thinner edges from Vision → Gemini (informing signal: facial expression)
- Particles/pulses flow along edges when data passes through
- Nodes glow/pulse when active; Gemini node pulses brightest when signals converge and action fires

### Tech approach
- SVG or Canvas overlay/tab in existing `index.html`
- Fed by real WebSocket events from backend (same `/ws/audio` connection or new `/ws/pipeline` event stream)
- CSS animations for edge particles and node glow

Status: ⬜

---

## Wave 4A — Sponsor Integration: Scaffolding (parallel with Wave 1)

**Goal:** Install SDKs, create integration stubs with novel architectures. No API keys required yet.

**Devpost:** https://multimodal-frontier-hackathon.devpost.com/
**Requirement:** Integrate at least **3 sponsor tools** (20% of judging = "Tool Use" criterion).

### Selected Sponsors

| Sponsor | Prize | Novel Integration | SDK | Env Vars |
|---------|-------|-------------------|-----|----------|
| **Unkey** | Up to $25,000/yr | Ephemeral meeting keys + cost-aware rate limiting | `unkey.py` | `UNKEY_ROOT_KEY`, `UNKEY_API_ID` |
| **DigitalOcean** | $1,000 + credits | Gradient Knowledge Base — cross-meeting memory via RAG | `openai` + DO API | `DO_MODEL_ACCESS_KEY`, `DO_AGENT_ENDPOINT`, `DO_AGENT_ACCESS_KEY` |
| **Railtracks** | $1,300 cash | Multi-agent specialists + visualizer as demo UI | `railtracks` | `GOOGLE_API_KEY` (already have) |

### W4A Tasks (no keys required)

| Task | Description | Status |
|------|-------------|--------|
| Install SDKs | `pip install unkey.py railtracks 'railtracks[cli]'` | ⬜ |
| Unkey stub | `backend/sponsor_unkey.py` — ephemeral keys, cost-weighted rate limiting, tier-based RBAC | ⬜ |
| DO stub | `backend/sponsor_digitalocean.py` — Knowledge Base client, meeting archive, cross-session RAG | ⬜ |
| Railtracks stub | `backend/sponsor_railtracks.py` — 4-agent specialist team, sentiment-gated routing, visualizer | ⬜ |

### Integration Design (Novel)

**Unkey** — Ephemeral meeting keys + cost-aware rate limiting:
- On meeting start: create a **self-destructing API key** (expires when meeting ends) with metadata (participants, room, tier)
- **Cost-weighted rate limiting**: transcript extraction = cost 1, action dispatch = cost 5. When budget exhausted → graceful degradation (transcript-only mode)
- **Tier gating via key metadata**: free = read transcript, premium = autonomous actions
- Demo moment: "Watch the system auto-degrade to transcript-only when Gemini budget hits zero"

**DigitalOcean** — Gradient Knowledge Base as meeting memory:
- After each meeting: upload transcript + actions to **Gradient Knowledge Base** (auto-chunks, auto-embeds, indexes in OpenSearch)
- At meeting start: query KB for **open commitments, prior decisions** by participants → feed into Gemini understanding prompt
- **Agent API** (`agents.do-ai.run`): persistent meeting assistant with attached KB, returns relevant context automatically
- Demo moment: "Sarah committed to Q3 report 3 meetings ago — the agent remembers and flags it"

**Railtracks** — Multi-agent specialists + live visualizer:
- 4 specialist agents: **TranscriptAnalyzer**, **SentimentMonitor**, **ActionExecutor**, **MeetingMemory**
- Sentiment-gated routing: positive → auto-execute, negative → block, uncertain + negative face → review queue
- **Visualizer as demo interface**: judges watch agent nodes light up, data flow along edges, routing decisions happen in real-time
- Demo moment: "Watch the visualizer — sentiment came back negative — routing redirects to review queue"

---

## Wave 4B — Sponsor Integration: Build (requires API keys)

**Prerequisite:** You must provide these API keys before this wave can execute.

### API Keys Required

```
# --- UNKEY (get from https://app.unkey.com) ---
# 1. Create workspace → Create API → copy API ID
# 2. Settings → Root Keys → Create root key (needs: keys.*.verify, ratelimit.*.limit)
UNKEY_ROOT_KEY=unkey_xxxxxxxxxx
UNKEY_API_ID=api_xxxxxxxxxx

# --- DIGITALOCEAN (get from https://cloud.digitalocean.com) ---
# 1. Gradient AI Platform → Serverless Inference → Create API Key
DO_MODEL_ACCESS_KEY=sk-xxxxxxxxxx
# 2. Gradient → Agents → Create Agent → attach Knowledge Base → copy endpoint + key
DO_AGENT_ENDPOINT=https://agents.do-ai.run/v1/your-agent-id
DO_AGENT_ACCESS_KEY=xxxxxxxxxx

# --- RAILTRACKS (no additional key needed) ---
# Uses existing GOOGLE_API_KEY for Gemini provider
```

### W4B Tasks (keys required)

| Task | Description | Depends On | Status |
|------|-------------|------------|--------|
| Unkey meeting keys | Create ephemeral keys on meeting start, expire on stop | `UNKEY_ROOT_KEY` + `UNKEY_API_ID` | ⬜ |
| Unkey cost limiting | Wire cost-weighted rate limiting into understand + dispatch | Unkey meeting keys | ⬜ |
| DO Knowledge Base | Create KB in console, upload test transcript, verify retrieval | `DO_AGENT_*` keys | ⬜ |
| DO meeting archive | Auto-upload transcript + actions to KB on meeting end | DO Knowledge Base | ⬜ |
| DO context retrieval | Query KB at meeting start for open commitments by participants | DO meeting archive | ⬜ |
| Railtracks agents | Wire 4-agent flow with sentiment-gated routing | Wave 4A stub | ⬜ |
| Railtracks visualizer | Run `railtracks visualize` as demo interface | Railtracks agents | ⬜ |
| Integration test | 5-min live test: all 3 sponsors active, actions fire | All above | ⬜ |

---

## Stretch (post-submission if time permits)

- Senso.ai integration ($3k credits — AI/ML services)
- assistant-ui integration ($800 cash — UI component library for transcript/action cards)
- Nexla integration ($900 cash + $5k credits — data pipeline for meeting transcripts)
- Augment Code usage ($3,500 cash — document AI-assisted development workflow)
