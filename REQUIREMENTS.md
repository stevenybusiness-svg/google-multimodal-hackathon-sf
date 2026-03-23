# Requirements — Live Meeting Agent

> GSD-style requirements doc. Functional requirements are frozen; implementation notes are in PROJECT.md.

## Functional Requirements

### F1 — Multimodal Input
- F1.1 Capture continuous PCM audio at 16kHz from browser mic; no silence gating
- F1.2 Optionally capture video frames from browser camera; POST as JPEG to `/api/frame`
- F1.3 Audio and video inputs are independent streams; agent works with audio-only

### F2 — Real-Time Transcription (Hear)
- F2.1 Google Cloud Speech-to-Text v1 is the STT; no fallback STT (`model=latest_long`, `language_code=en-US`, interim results enabled)
- F2.2 Interim captions appear within ~200ms; final transcripts within ~1s
- F2.3 Transcript buffer hard-flushes to understanding at 600 chars; cooldown flush at 2s after last segment (min 30 chars)

### F3 — Visual Sentiment (See)
- F3.1 Cloud Vision analyzes facial emotion from frames, debounced 2s (`DEBOUNCE_SECONDS = 2`, semaphore max 3 concurrent)
- F3.2 Likelihood enums normalized to 0–1 or high/medium/low in one place (`vision.py:_norm`)
- F3.3 No crash on empty face/object annotation lists; always guard before index

### F4 — Understanding (Understand)
- F4.1 Gemini Flash extracts: `commitment`, `agreement`, `meeting_request`, `document_revision`, `sentiment`
- F4.2 Sentiment from face (F3) feeds into understanding context
- F4.3 Outputs match contract shapes defined in PROJECT.md §2

### F5 — Autonomous Actions (Act)
- F5.1 Commitment → task logged (in-memory `_task_log`); no Slack message for commitments
- F5.2 Meeting request → Google Calendar event created (OAuth2); description flagged ⚠️ if sentiment is negative/uncertain
- F5.3 Document revision → revised brief generated + uploaded via Slack file (`files_upload_v2`, fallback to code-block message)
- F5.4 Sentiment gates actions: `negative` text sentiment → blocked; `uncertain` text + negative face emotion (anger/sadness) → blocked; `positive`/`neutral` → proceed
- F5.5 All action dispatch is fire-and-forget (`asyncio.create_task`); Calendar/Slack must not block Cloud STT receive loop

### F6 — UI Feedback
- F6.1 Live transcript displayed in real-time
- F6.2 Action cards appear as each action fires
- F6.3 Sentiment pill shown (face emotion context)
- F6.4 Mic level indicator (RMS, for UI only — never affects audio sent to STT)

## Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NF1 | Backend split by pipeline: `voice.py`, `understanding.py`, `actions.py`, `vision.py` — no file > ~500 lines |
| NF2 | Per-session state: `TranscriptBuffer` + `ActionSession` instantiated per WebSocket connection |
| NF3 | STT via `google.cloud.speech_v1`; Understanding + doc revision via `google-genai` SDK (Gemini); no Claude/Anthropic |
| NF4 | Deployed on Google Cloud Run; public URL required for submission proof |
| NF5 | Public GitHub repo |
| NF6 | No client-side `innerHTML` (XSS); use `textContent` |

## Out of Scope (MVP)

- External Tasks API (in-memory `_task_log` only)
- Chrome extension
- Post-meeting summary / storybook / memory video
- Multi-language / multi-speaker STT
- DigitalOcean inference (optional demo upside only)
