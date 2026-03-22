# Technology Stack

**Analysis Date:** 2026-03-22

## Languages

**Primary:**
- Python 3.12+ - Backend server, voice pipeline, understanding, actions, document processing
- JavaScript (ES6+) - Frontend UI, WebSocket communication, audio capture, camera frames
- Markdown - Configuration, documentation, marketing brief template

**Secondary:**
- HTML5 - UI markup structure (`static/index.html`)
- CSS3 - Styling via Tailwind CSS classes in HTML

## Runtime

**Environment:**
- Python 3.12+ (local dev)
- Docker (containerized for Cloud Run)
- Node.js environment (frontend, no build step required)

**Package Manager:**
- pip (Python dependencies)
- Lockfile: `requirements.txt` present

## Frameworks

**Core:**
- FastAPI 0.115.0+ - Async HTTP server, WebSocket support, REST endpoints
- Uvicorn 0.30.0+ - ASGI server (async worker)

**Testing:**
- pytest 8.3.0+ - Test runner and framework
- Supports async tests via pytest fixtures (`conftest.py` in `tests/`)

**Build/Dev:**
- Docker (production deployment container)
- gcloud CLI (Google Cloud deployment)

## Key Dependencies

**Critical:**
- google-genai 1.14.0+ - Gemini API client (understanding, document revision)
- google-cloud-speech 2.27.0+ - Cloud STT streaming (real-time transcription)
- google-cloud-vision 3.7.0+ - Face detection and emotion analysis
- google-api-python-client 2.0.0+ - Google Calendar and Gmail APIs
- google-auth-oauthlib 1.0.0+ - OAuth2 credentials management

**Infrastructure:**
- slack-sdk 3.0.0+ - Slack API client (message posting, file upload)
- aiohttp 3.9.0+ - Async HTTP client (fallback/utility requests)
- httpx 0.28.0+ - Async HTTP client (alternative)
- python-dotenv 1.0.0+ - Environment variable loading from `.env`
- typing_extensions 4.12.0+ - Type hints for Python 3.12+

## Configuration

**Environment:**
- `.env` file required at project root
- Environment variables passed to Cloud Run via `--set-env-vars`

**Key configurations required:**
- `GOOGLE_API_KEY` - Gemini API key (paid tier)
- `GOOGLE_CLOUD_PROJECT` - GCP project ID for Vision, STT, Calendar billing
- `SLACK_BOT_TOKEN` - Slack bot token (xoxb-...)
- `SLACK_CHANNEL` - Target Slack channel name (e.g., #meeting-actions)
- `GOOGLE_CALENDAR_TOKEN_JSON` - OAuth2 token JSON (Google Calendar + Gmail)

**Build:**
- `Dockerfile` - Standard Python 3.12 image, pip install, uvicorn entrypoint
- No build config files (.eslintrc, tsconfig.json, etc.) - frontend is vanilla JS

## Platform Requirements

**Development:**
- Python 3.12+
- pip (Python package manager)
- gcloud CLI (for local auth: `gcloud auth application-default login`)
- Docker (optional, for testing container builds)

**Production:**
- Google Cloud Run (serverless container execution)
- Region: us-central1
- Unauthenticated access allowed (`--allow-unauthenticated`)
- Environment variables injected at deploy time

## Async Architecture

**Concurrency:**
- asyncio (Python async/await)
- asyncio.Queue (audio buffer, max 50 items)
- asyncio.Semaphore (rate limiting: Gemini sem=4, Vision sem=3)
- asyncio.Task (fire-and-forget dispatch for actions)
- WebSocket streaming (FastAPI WebSockets)

## API Models Used

**LLM:**
- `gemini-3-flash-preview` - Understanding (transcript → commitment/agreement/meeting_request/document_revision/sentiment)
- `gemini-3-flash-preview` - Document revision (apply changes to marketing brief)

**Speech-to-Text:**
- Google Cloud Speech-to-Text v1 (streaming recognition)
- Model: `latest_long`
- Language: en-US
- Sample rate: 16000 Hz (16kHz)
- Format: LINEAR16 (16-bit PCM mono)

**Vision:**
- Google Cloud Vision API (batch_annotate_images)
- Features: FACE_DETECTION (max 1 result), LABEL_DETECTION (max 5 results)

---

*Stack analysis: 2026-03-22*
