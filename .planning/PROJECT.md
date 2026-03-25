# Live Meeting Agent

## What This Is

A real-time meeting agent that autonomously executes actions from what is said and agreed in meetings. It sees (Cloud Vision: facial sentiment), hears (Cloud STT: real-time transcription), and understands (Gemini Flash: intent extraction) — then acts without a human gate: calendar events created, tasks logged, and document revisions uploaded to Slack the moment a commitment, meeting request, agreement, or doc revision is detected.

Built for the **Multimodal Frontier Hackathon** (March 28, 2026, San Francisco). Sponsored by Google DeepMind + DigitalOcean. $45k+ prize pool.

## Core Value

Three autonomous actions fire in ~5 seconds from live voice + camera input — no human gate, no post-meeting processing.

## Requirements

### Validated

- ✓ Voice pipeline (Cloud STT v1 streaming, 16kHz, no silence gating) — Phase 0
- ✓ Understanding pipeline (Gemini Flash: commitments, agreements, meeting_requests, doc_revisions) — Phase 0
- ✓ Action pipeline (Calendar, task log, Slack doc upload, sentiment gating) — Phase 0
- ✓ Vision pipeline (Cloud Vision face sentiment, 2s debounce, normalized 0–1) — Phase 0
- ✓ FastAPI server + WebSocket handler + per-session state — Phase 0
- ✓ Browser UI (dark theme, live transcript, action cards, sentiment pill) — Phase 0
- ✓ Architecture diagram (Mermaid, see+hear+understand+act layers) — Phase 0
- ✓ Regression test suite — Phase 0

### Active

- [ ] Google Calendar OAuth2 pre-auth token in `.env` (Phase 1)
- [ ] Cloud Run deploy with public URL (Phase 1)
- [ ] Demo video ≤4min, opens with 3-action moment (Phase 2)
- [ ] Hackathon submission submitted at luma.com/multimodalhack (Phase 3)
- ✓ Voice-driven GCP infrastructure provisioning (Terraform HCL generation + dispatch) — Phase 2 (2026-03-25)

### Out of Scope

- Chrome extension — complexity, not core to demo
- Post-meeting summary / storybook / memory video — "No memorabilia" rule
- Multi-language / multi-speaker STT — English-only MVP
- External Tasks API — in-memory `_task_log` only for MVP
- DigitalOcean inference — optional stretch goal only
- WorkOS auth — enterprise integration, not needed for demo

## Context

- Brownfield project: all backend and frontend code is done (Wave 0 complete)
- Previously targeting Gemini Live Agent Challenge (Mar 16 deadline, passed); now targeting Multimodal Frontier (Mar 28)
- STT was migrated from Gemini Live API to Google Cloud Speech-to-Text v1 for lower latency (~200ms interim vs ~1s)
- Sentiment gating: `negative` text → blocked; `uncertain` + negative face (anger/sadness) → blocked; otherwise fires
- Meeting summary email sent at end of session via `backend/email_summary.py` (uses Gmail OAuth2, shared with Calendar creds)
- GSD workflow adopted Mar 22 2026

## Constraints

- **Timeline**: Hackathon in-person March 28, 2026 9:30 AM PST — hard deadline
- **Stack**: Google Cloud Run (deploy target); `google.cloud.speech_v1` (STT); `google-genai` (Gemini); no Claude/Anthropic
- **Auth**: Google Calendar + Gmail require OAuth2 pre-auth token (not API key)
- **Demo**: ≤4min video; must open with 3-action autonomous moment in ~5s

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Cloud STT v1 over Gemini Live | Lower latency (~200ms interim), proven streaming reconnect | ✓ Good |
| Fire-and-forget dispatch | Slack/Calendar (~1s) must not block STT receive loop | ✓ Good |
| Per-session TranscriptBuffer + ActionSession | No state bleed across concurrent WebSocket connections | ✓ Good |
| Sentiment gates actions (blocks negative) | "No" means no — don't create calendar event someone rejected | ✓ Good |
| In-memory task log only | External Tasks API not needed for demo | — Pending |
| Gemini stack (not Claude) | Google DeepMind is lead sponsor; strategic alignment with judges | ✓ Good |

---
*Last updated: 2026-03-25 — Phase 02 complete (voice-driven GCP infra provisioning)*
