# Roadmap: Live Meeting Agent

## Overview

All core code is done (Phase 0 complete). Remaining work is deploy, auth, demo, and submission for the Multimodal Frontier Hackathon on March 28, 2026. Phase 1 runs two tasks in parallel (Calendar OAuth2 + Cloud Run deploy). Phase 2 records the demo video once the live deploy is confirmed. Phase 3 submits.

## Milestones

- ✅ **v0.1 Core Implementation** — Phase 0 (complete)
- 🚧 **v1.0 Hackathon Submission** — Phases 1–3 (in progress)

## Phases

<details>
<summary>✅ Phase 0: Core Implementation — COMPLETE</summary>

### Phase 0: Core Implementation
**Goal**: All backend pipelines and frontend UI built and tested.
**Depends on**: Nothing
**Requirements**: VOICE-01–03, VISION-01–03, UNDER-01–03, ACT-01–05, UI-01–04
**Success Criteria**:
  1. Cloud STT streams real-time transcript with interim results
  2. Gemini Flash extracts commitments/agreements/meeting_requests/doc_revisions
  3. Actions fire autonomously (Calendar, task log, Slack doc upload)
  4. Vision pipeline normalizes face sentiment without crashing on empty annotations
  5. Regression tests pass
**Plans**: Complete

Plans:
- [x] 00-01: Voice pipeline (Cloud STT v1 streaming)
- [x] 00-02: Understanding pipeline (Gemini Flash)
- [x] 00-03: Action pipeline (Calendar, Slack, task log)
- [x] 00-04: Vision pipeline (Cloud Vision face sentiment)
- [x] 00-05: FastAPI server + WebSocket + per-session state
- [x] 00-06: Browser UI + regression tests

</details>

### 🚧 Phase 1: Deploy + Auth
**Goal**: Live Cloud Run deployment with Calendar OAuth2 working; public URL captured.
**Depends on**: Phase 0
**Requirements**: DEPLOY-01, DEPLOY-02
**Success Criteria**:
  1. `python scripts/get_calendar_token.py` produces valid token; added to `.env`
  2. `gcloud run deploy` succeeds; public URL accessible
  3. `/health` endpoint returns `{"status": "ok"}` at the Cloud Run URL
  4. Calendar event fires correctly in end-to-end test against live deploy
**Plans**: 2 plans (parallel)

Plans:
- [x] 01-01: Calendar OAuth2 pre-auth (`scripts/get_calendar_token.py` → `.env`)
- [x] 01-02: Cloud Run deploy (gcloud + env vars + URL screenshot)

### Phase 2: Demo Video
**Goal**: ≤4min demo video recorded and edited, leading with the 3-action moment.
**Depends on**: Phase 1
**Requirements**: SUBMIT-01, SUBMIT-02
**Success Criteria**:
  1. Video opens with 3 action cards firing in ~5s (Calendar + task + doc revision)
  2. Facial sentiment + action gating shown on camera
  3. Architecture diagram (See → Hear → Understand → Act) narrated
  4. Cloud Run URL shown live
  5. Video is ≤4 min, exported and ready to upload
**Plans**: 1 plan

Plans:
- [ ] 02-01: Record, edit, and export demo video per ROADMAP script

### Phase 3: Submit
**Goal**: Hackathon submission complete before March 28, 2026 9:30 AM PST.
**Depends on**: Phase 2
**Requirements**: SUBMIT-03
**Success Criteria**:
  1. Public GitHub repo confirmed (no secrets in `.env`, `.gitignore` guards it)
  2. Demo video uploaded
  3. Cloud Run URL screenshot attached
  4. Architecture diagram attached
  5. Submission confirmed at luma.com/multimodalhack
**Plans**: 1 plan

Plans:
- [ ] 03-01: Final submission checklist + submit

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Core Implementation | 6/6 | Complete | 2026-03-22 |
| 1. Deploy + Auth | 2/2 | Complete   | 2026-03-22 |
| 2. Demo Video | 0/1 | Not started | - |
| 3. Submit | 0/1 | Not started | - |
