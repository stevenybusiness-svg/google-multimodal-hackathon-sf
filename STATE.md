# State — Live Meeting Agent

> Current project state snapshot. Updated at start of each session.
> Last updated: 2026-03-22

## Current Phase: Wave 1 — Deploy + Auth

## What's Done
- All backend pipelines: `voice.py`, `understanding.py`, `actions.py`, `vision.py`, `main.py`
- All frontend: `static/index.html`, `static/app.js`
- Architecture diagram: `architecture.md` (Mermaid + design decisions)
- Regression test suite: `tests/`
- Project retargeted from Gemini Live Agent Challenge → Multimodal Frontier Hackathon (Mar 28)

## What's Blocking
| Blocker | Owner | Notes |
|---------|-------|-------|
| `GOOGLE_CALENDAR_TOKEN_JSON` not in `.env` | You | Run `python scripts/get_calendar_token.py` |
| Cloud Run not deployed | You | Need `gcloud` CLI auth + project set |
| Hackathon registration | You | luma.com/multimodalhack — judging is invite-only; apply ASAP |

## Active Branch
`master` — clean, no uncommitted changes

## Env Vars Needed
```
GOOGLE_API_KEY
GOOGLE_CLOUD_PROJECT
SLACK_BOT_TOKEN
SLACK_CHANNEL
GOOGLE_CALENDAR_TOKEN_JSON   ← missing; run scripts/get_calendar_token.py
```

## Key Files
```
backend/voice.py         VoicePipeline: Cloud STT v1, send_audio(), active_stt="cloud_stt", reconnects at 4 min
backend/understanding.py TranscriptBuffer + understand_transcript()
backend/actions.py       ActionSession + create_calendar_event()
backend/vision.py        analyze_frame() debounced 2s, semaphore(3), _norm() maps likelihood→0-1
backend/main.py          FastAPI: /health, /, /ws/audio, /api/frame, /api/tasks
static/index.html        Dark UI
static/app.js            16kHz, no silence gate
scripts/get_calendar_token.py  OAuth2 pre-auth → prints GOOGLE_CALENDAR_TOKEN_JSON
```

## Next Actions (in order)
1. Apply for judging at luma.com/multimodalhack
2. Run `python scripts/get_calendar_token.py` → add token to `.env`
3. `gcloud run deploy meeting-agent ...` → get public URL
4. Record demo video (script in ROADMAP.md §Wave 2)
5. Submit
