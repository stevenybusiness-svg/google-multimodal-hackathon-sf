# Requirements: Live Meeting Agent

**Defined:** 2026-03-22
**Core Value:** Three autonomous actions fire in ~5 seconds from live voice + camera input — no human gate.

## v1 Requirements

### Voice (Hear)

- [x] **VOICE-01**: Mic PCM captured at 16kHz, streamed continuously with no silence gating
- [x] **VOICE-02**: Cloud STT v1 transcribes in real-time with interim results (~200ms) and final results (~1s)
- [x] **VOICE-03**: STT stream reconnects proactively at 4 min before 5-min hard limit

### Vision (See)

- [x] **VISION-01**: Camera frames POSTed as JPEG to `/api/frame`; processed by Cloud Vision Face Detection
- [x] **VISION-02**: Face emotion likelihoods normalized to 0–1 via `_norm()` (VERY_LIKELY→1.0, threshold 0.4 for emotion declaration)
- [x] **VISION-03**: No crash on empty face/object annotations; always guarded before index

### Understanding (Understand)

- [x] **UNDER-01**: Gemini Flash (`gemini-3-flash-preview`) extracts commitments, agreements, meeting_requests, document_revisions, sentiment per transcript flush
- [x] **UNDER-02**: Face sentiment feeds into understanding context
- [x] **UNDER-03**: TranscriptBuffer flushes at 600 chars (hard) or 2s cooldown after last segment (min 30 chars)

### Actions (Act)

- [x] **ACT-01**: Commitment → task logged in-memory (`_task_log`); no Slack message
- [x] **ACT-02**: Meeting request → Google Calendar event created via OAuth2; `⚠️ Sentiment flagged` added to description on negative/uncertain
- [x] **ACT-03**: Document revision → brief revised via Gemini + uploaded to Slack (`files_upload_v2`, fallback to code-block)
- [x] **ACT-04**: Sentiment gates: `negative` text → blocked; `uncertain` + angry/sad face → blocked; positive/neutral → proceed
- [x] **ACT-05**: All dispatch fire-and-forget (`asyncio.create_task`); Slack/Calendar never block STT loop

### UI

- [x] **UI-01**: Live transcript displayed in real-time (interim + final)
- [x] **UI-02**: Action cards appear as each action fires
- [x] **UI-03**: Sentiment pill shown (face emotion context)
- [x] **UI-04**: No `innerHTML` (XSS); `textContent` used throughout

### Deploy

- [x] **DEPLOY-01**: Backend deployed to Cloud Run; public URL captured for submission proof
- [ ] **DEPLOY-02**: `GOOGLE_CALENDAR_TOKEN_JSON` in env (from `scripts/get_calendar_token.py`)

### Submission

- [ ] **SUBMIT-01**: Demo video ≤4min, opens with 3-action autonomous moment in ~5s
- [ ] **SUBMIT-02**: Public GitHub repo confirmed
- [ ] **SUBMIT-03**: Submitted at luma.com/multimodalhack before March 28 9:30 AM PST

## v2 Requirements

### Stretch (post-submission)

- **STRETCH-01**: DigitalOcean inference endpoint as alternative model backend
- **STRETCH-02**: WorkOS enterprise auth integration
- **STRETCH-03**: External Tasks API (replace in-memory log)
- **STRETCH-04**: Multi-language / multi-speaker STT

## Out of Scope

| Feature | Reason |
|---------|--------|
| Chrome extension | Complexity; browser UI sufficient for demo |
| Post-meeting storybook / memory video | Explicitly excluded ("No memorabilia") |
| Claude/Anthropic LLM | Google DeepMind is lead sponsor; Gemini only |
| Silence gating | Causes STT to miss utterance endings — never do this |
| Gradium | Removed entirely; no GRADIUM_API_KEY |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| VOICE-01 | Phase 0 | Complete |
| VOICE-02 | Phase 0 | Complete |
| VOICE-03 | Phase 0 | Complete |
| VISION-01 | Phase 0 | Complete |
| VISION-02 | Phase 0 | Complete |
| VISION-03 | Phase 0 | Complete |
| UNDER-01 | Phase 0 | Complete |
| UNDER-02 | Phase 0 | Complete |
| UNDER-03 | Phase 0 | Complete |
| ACT-01 | Phase 0 | Complete |
| ACT-02 | Phase 0 | Complete |
| ACT-03 | Phase 0 | Complete |
| ACT-04 | Phase 0 | Complete |
| ACT-05 | Phase 0 | Complete |
| UI-01 | Phase 0 | Complete |
| UI-02 | Phase 0 | Complete |
| UI-03 | Phase 0 | Complete |
| UI-04 | Phase 0 | Complete |
| DEPLOY-01 | Phase 1 | Complete |
| DEPLOY-02 | Phase 1 | Pending |
| SUBMIT-01 | Phase 2 | Pending |
| SUBMIT-02 | Phase 2 | Pending |
| SUBMIT-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-22*
*Last updated: 2026-03-22 after GSD adoption*
