# Codebase Structure

**Analysis Date:** 2026-03-22

## Directory Layout

```
meeting-agent/
├── backend/                          # Python FastAPI backend
│   ├── __init__.py                  # Empty package marker
│   ├── main.py                      # FastAPI app, WebSocket handler, session lifecycle
│   ├── voice.py                     # VoicePipeline: Cloud STT v1 streaming
│   ├── understanding.py             # TranscriptBuffer + Gemini intent extraction
│   ├── actions.py                   # ActionSession: Slack, Calendar dispatch
│   ├── documents.py                 # Marketing brief + Gemini revision
│   ├── vision.py                    # Cloud Vision face detection + sentiment
│   ├── email_summary.py             # Gmail meeting summary sender
│   ├── contracts.py                 # TypedDict message schemas
│   └── session_state.py             # Per-session state registry + dataclasses
├── static/                          # Frontend (HTML/JS)
│   ├── index.html                  # Dark theme UI (Tailwind CSS), screen containers
│   ├── app.js                       # App entry point, module loader, sidebar toggle
│   └── app/                         # Modular JavaScript
│       ├── core.js                  # DOM refs, state object, sentiment/action config
│       ├── render.js                # UI rendering (transcript, actions, sentiment)
│       ├── media.js                 # Audio capture (16kHz), video stream, frame encoder
│       ├── session.js               # WebSocket lifecycle, startMeeting(), stopMeeting()
│       └── documents.js             # Document widget, modal, revision UI
├── scripts/                         # Utilities and testing
│   ├── get_calendar_token.py       # OAuth2 Calendar + Gmail token generator
│   └── smoke_test.py                # Import + instantiation smoke test
├── tests/                           # Pytest regression tests
│   ├── conftest.py                 # Pytest fixtures
│   └── regressions/
│       ├── test_smoke.py            # Import + instantiation tests
│       ├── test_understanding.py    # Gemini extraction mock tests
│       ├── test_vision.py           # Vision normalization tests
│       ├── test_actions.py          # Slack/Calendar dispatch tests
│       └── test_app_integration.py  # End-to-end WebSocket mock tests
├── submission-materials/            # Hackathon materials (optional, not deployed)
│   ├── architecture-diagram.md      # Mermaid system flow diagram
│   ├── google-cloud-deployment.md   # Complete Google API call catalog
│   └── blog-post.md                 # Development blog post
├── .planning/                       # GSD codebase analysis (generated)
│   └── codebase/
│       ├── ARCHITECTURE.md
│       ├── STRUCTURE.md
│       ├── CONVENTIONS.md (optional)
│       └── TESTING.md (optional)
├── .claude/                         # Claude Code setup files (generated)
│   ├── agents/
│   ├── commands/
│   ├── hooks/
│   ├── get-shit-done/
│   ├── settings.json
│   └── package.json
├── .github/                         # GitHub workflows (optional)
├── .env.example                     # Environment variable template
├── .dockerignore                    # Docker build exclusions
├── Dockerfile                       # Cloud Run deployment container
├── requirements.txt                 # Python dependencies (FastAPI, Slack SDK, etc.)
├── PROJECT.md                       # Authoritative spec + RCA (do not duplicate)
├── REQUIREMENTS.md                  # Functional + non-functional requirements
├── ROADMAP.md                       # Wave-based execution plan
├── STATE.md                         # Current blockers + next actions
├── architecture.md                  # System flow + design decisions (legacy reference)
├── README.md                        # Quick start, deployment, project overview
├── meeting_agent.mdc                # Cursor/Claude rule file pointer
└── credentials.json                 # GCP OAuth2 credentials (git-ignored)
```

## Directory Purposes

**backend/:**
- Purpose: Python FastAPI application and core business logic
- Contains: WebSocket handler, voice/vision/understanding pipelines, action dispatch, session state
- Key files: `main.py` (entry point), `voice.py` (STT), `understanding.py` (Gemini), `actions.py` (Slack/Calendar)

**static/:**
- Purpose: Frontend UI and client-side logic
- Contains: HTML (Tailwind CSS dark theme), JavaScript (WebSocket, audio capture, rendering)
- Key files: `index.html` (layout), `app.js` (loader), `app/core.js` (state)

**scripts/:**
- Purpose: Development utilities (token generation, smoke testing)
- Contains: OAuth2 setup, minimal import validation
- Key files: `get_calendar_token.py` (one-time Calendar + Gmail token generation)

**tests/:**
- Purpose: Regression testing (pytest)
- Contains: Mocked Gemini/Vision calls, WebSocket mock integration tests
- Key files: Organized in `regressions/` subdirectory by module

**submission-materials/:**
- Purpose: Hackathon documentation (architecture diagrams, API catalog, blog post)
- Contains: Markdown documentation for judges
- Not deployed to Cloud Run; for submission only

## Key File Locations

**Entry Points:**
- `backend/main.py`: FastAPI application definition, WebSocket handler, health check, frame endpoint
- `static/index.html`: HTML page structure (home, meeting, summary screens)
- `static/app.js`: JavaScript module loader + app initialization

**Configuration:**
- `.env.example`: Template for required environment variables
- `requirements.txt`: Python dependencies (FastAPI, Slack SDK, Google Cloud SDKs)
- `Dockerfile`: Cloud Run deployment configuration
- `meeting_agent.mdc`: Cursor rule file (pointers to PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md)

**Core Logic:**
- `backend/voice.py`: Cloud STT v1 streaming, reconnect logic
- `backend/understanding.py`: TranscriptBuffer, Gemini Flash extraction, prompt template
- `backend/actions.py`: Slack/Calendar/document dispatch, sentiment gating
- `backend/vision.py`: Cloud Vision face detection, sentiment normalization
- `backend/session_state.py`: Per-session state registry, VisionState dataclass

**Frontend Modules:**
- `static/app/core.js`: DOM bindings, state object, configuration constants
- `static/app/session.js`: WebSocket lifecycle, meeting start/stop
- `static/app/render.js`: Transcript rendering, action card rendering, sentiment pill
- `static/app/media.js`: Audio capture (16kHz), video stream, JPEG frame encoding
- `static/app/documents.js`: Marketing brief widget, revision display, modal

**Testing:**
- `tests/conftest.py`: Pytest configuration, fixtures
- `tests/regressions/test_understanding.py`: Gemini prompt mock tests
- `tests/regressions/test_vision.py`: Vision response normalization tests
- `tests/regressions/test_actions.py`: Slack/Calendar mock dispatch tests

## Naming Conventions

**Files:**
- Python modules: lowercase with underscores (e.g., `voice.py`, `understanding.py`, `session_state.py`)
- JavaScript modules: lowercase with underscores in `static/app/` (e.g., `core.js`, `render.js`)
- HTML: `index.html` (single root)
- Configuration: `.env`, `.dockerignore`, `Dockerfile`, `requirements.txt`
- Documentation: UPPERCASE.md (e.g., `PROJECT.md`, `REQUIREMENTS.md`, `README.md`)

**Classes:**
- PascalCase (e.g., `VoicePipeline`, `TranscriptBuffer`, `ActionSession`, `MeetingSessionState`)
- TypedDict contracts: PascalCase (e.g., `UnderstandingResult`, `Commitment`, `SentimentPayload`)

**Functions:**
- snake_case (e.g., `understand_transcript()`, `analyze_frame()`, `revise_document()`)
- Private functions: leading underscore (e.g., `_get_slack()`, `_dispatch()`, `_norm()`)

**Variables:**
- snake_case for locals (e.g., `_buf`, `face_sentiment`, `session_id`)
- UPPERCASE for module-level constants (e.g., `UNDERSTANDING_MODEL`, `SLACK_CHANNEL`, `DEBOUNCE_SECONDS`)
- Private globals: leading underscore (e.g., `_client`, `_calendar_creds`, `_slack`)

**TypeScript / JavaScript:**
- camelCase for functions and variables (e.g., `startMeeting()`, `handleWsMessage()`, `sendAudio()`)
- PascalCase for component/class-like objects (e.g., `MeetingAgent.core`, `MeetingAgent.render`)
- DOM IDs: kebab-case with semantic prefixes (e.g., `#screen-home`, `#status-text`, `#actions-feed`)

## Where to Add New Code

**New Feature (end-to-end):**
- Backend: Add module under `backend/` (e.g., `backend/new_feature.py`), import in `backend/main.py`
- Frontend: Add to `static/app/` (e.g., `static/app/new_feature.js`), load in `static/app.js` before initialization
- Tests: Add test file under `tests/regressions/test_new_feature.py`
- Update PROJECT.md if feature affects contract or RCA

**New Backend Pipeline/Module:**
- Location: `backend/module_name.py`
- Pattern: Define classes/functions, lazy-init globals (e.g., `_client = None`, `def _get_client(): global _client...`)
- Import in `main.py`, add error handling in try/except at startup
- Add async wrappers for sync SDKs (e.g., `asyncio.to_thread()` for googleapiclient)

**New Frontend Component:**
- Location: `static/app/component.js`
- Pattern: Wrap in IIFE, attach to `window.MeetingAgent` namespace (e.g., `window.MeetingAgent.newComponent = ...`)
- Load in `static/app.js` before initialization
- Use DOM ID refs from `static/app/core.js` or define local refs

**New API Endpoint:**
- Location: `backend/main.py` (add `@app.get()` or `@app.post()`)
- Pattern: Accept `Request`, use `session_registry.get(session_id)` for state lookup
- Return `JSONResponse` with `{"status": "...", "data": ...}` shape
- Add error handling with HTTP status codes

**Utilities:**
- Shared helpers: `backend/utils.py` or module-specific (e.g., `_norm()` in `vision.py`)
- No single utilities file; keep helpers close to consumers

## Special Directories

**backend/__pycache__/:**
- Purpose: Python bytecode cache (generated)
- Committed: No (in `.gitignore`)

**.env, credentials.json:**
- Purpose: Runtime configuration and OAuth2 credentials
- Committed: No (in `.gitignore`; use `.env.example` as template)
- Generated: Via `scripts/get_calendar_token.py` (interactive OAuth2 flow) and manual configuration

**.planning/codebase/:**
- Purpose: GSD (get-shit-done) codebase analysis documents
- Generated: By `/gsd:map-codebase` command
- Committed: Yes (reference docs for future planning phases)

**.claude/:**
- Purpose: Claude Code setup, hooks, commands
- Generated: By Claude Code initialization
- Committed: Yes (project-specific configurations)

**tests/__pycache__/:**
- Purpose: Pytest bytecode cache
- Committed: No (in `.gitignore`)

**submission-materials/:**
- Purpose: Hackathon submission artifacts (not deployed)
- Committed: Yes (for judges/reference)
- Generated: Manually authored during submission phase

## Code Organization Principles

1. **No monolithic server files** — Split by pipeline (voice, understanding, actions, vision, documents, email)
2. **Per-session state isolation** — Each WebSocket gets its own `TranscriptBuffer`, `ActionSession`, no global state bleed
3. **TypedDict contracts in one place** — `backend/contracts.py` defines all message shapes; reused across modules
4. **Lazy-init globals** — Avoid import-time side effects (SDKs initialized on first use with `if _client is None:` pattern)
5. **Fire-and-forget task dispatch** — Background Slack/Calendar calls don't block WebSocket receive loop; `_bg_tasks` set prevents GC
6. **Async/thread safety** — `asyncio.to_thread()` for sync SDK calls (Vision, Calendar); Semaphores for API rate limiting
7. **One project doc** — PROJECT.md is authoritative; other .md files are lightweight references

---

*Structure analysis: 2026-03-22*
