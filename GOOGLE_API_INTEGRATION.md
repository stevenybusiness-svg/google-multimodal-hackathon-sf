# Google API Integration — Meeting Agent (MVP)

> Implementation gotchas for the current codebase. Keep [PROJECT.md](PROJECT.md) as the contract/source-of-truth doc; use this file for runtime details only.

---

## 1. Gemini Live API — Primary STT

Model: `gemini-2.5-flash-native-audio-preview-12-2025`. Implementation: `VoicePipeline` in `backend/voice.py`.

| Rule | Why |
|------|-----|
| Audio format: `audio/pcm;rate=16000` | Must match `AudioContext.sampleRate` in browser |
| `response_modalities: ["AUDIO"]` + `input_audio_transcription` | Native audio model emits STT through built-in input transcription |
| `automatic_activity_detection.disabled = True` | Prevents silence gating; the app sends a continuous stream |
| English-only transcribe instruction | Current demo path skips non-English speech instead of trying to translate |
| Never silence-gate — send all PCM chunks | Silence gating causes Gemini to miss utterance endings |
| Lazy-init client (`_get_client()`) | Module-level `genai.Client(...)` crashes import if env var missing |
| Stall detector nudges with `ActivityEnd` / `ActivityStart` | Helps recover long sessions when input transcription stalls |

---

## 2. Gemini Text — Understanding

Model: `gemini-3-flash-preview`. Implementation: `understand_transcript` + `TranscriptBuffer` in `backend/understanding.py`.

| Rule | Why |
|------|-----|
| Return schema includes `meeting_requests` and `document_revisions` | Actions and document updates depend on these keys |
| Prompt: "ISO 8601 datetime if determinable, else null" | Natural language dates (`"next Tuesday"`) break `datetime.fromisoformat()` |
| Strip markdown fences before `json.loads` | Model adds ` ```json ` despite instructions ~30% of the time |
| Log the raw text on `JSONDecodeError` | Silent swallow makes prompt debugging impossible |
| `asyncio.Semaphore(4)` on Gemini calls | Prevents quota exhaustion under burst load |
| `TranscriptBuffer` is per-session (class instance) | Module-level buffer is shared across WebSocket sessions |

---

## 3. Google Cloud Vision API — Face Sentiment

Implementation: `analyze_frame` + `_parse_vision_response` in `backend/vision.py`.

| Rule | Why |
|------|-----|
| Guard `face_annotations` before `[0]` | Empty list (no face in frame) → IndexError crash |
| Normalize likelihood in `_norm()` — one place | Raw 0–5 enum varies across SDK versions; branching on raw ints breaks |
| Face bounding box = **pixel coords** | Do not mix with object bounding boxes which are normalized 0–1 |
| `asyncio.to_thread()` for the gRPC call | Vision client is synchronous; calling it directly blocks the event loop |
| Semaphore-gate concurrent calls (`Semaphore(3)`) | Vision API has per-project QPS limits |
| Debounce ~5s between frames in the current app | Keeps cost down while preserving near-live sentiment updates |

---

## 4. Google Calendar API

OAuth scope: `https://www.googleapis.com/auth/calendar.events`

Pre-auth for demo: `python scripts/get_calendar_token.py` → paste output into `.env` as `GOOGLE_CALENDAR_TOKEN_JSON`.

| Rule | Why |
|------|-----|
| OAuth2, not API key | Calendar API requires user identity; API keys don't work |
| `asyncio.to_thread()` for insert | Google API client is sync; don't block the event loop |
| Sentiment in event description | Shows judges sentiment is an intelligence layer, not a gate |
| Negative/uncertain sentiment → buffer +1 day | Only attempt `datetime.fromisoformat()` inside try/except |

---

## 5. Frontend Audio Capture

Implementation: `static/app.js`.

| Rule | Why |
|------|-----|
| `AudioContext({ sampleRate: 16000 })` | Must match what Gemini Live expects |
| `console.assert(ctx.sampleRate === 16000, ...)` | Browser may silently override the hint |
| Send ALL chunks via `ws.send(i16.buffer)` | No silence gating — ever |
| RMS → `micLevel.style.width` only | RMS is UI-only; never gates sending |
| Dynamic WS URL: `${proto}//${location.host}/ws/audio` | Hardcoded `localhost` breaks on Cloud Run |
| Inline start-error surface on the home screen | Permission and setup failures need a user-visible explanation |
| `<script src="/static/app.js">` | Mount is at `/static/`; relative `src="app.js"` 404s |

---

## 6. Document Revision Path

Implementation: `backend/documents.py` + `backend/actions.py`.

| Rule | Why |
|------|-----|
| Use Gemini `gemini-3.1-flash-lite-preview` to rewrite the brief | Keeps the feature on the same Gemini-only stack |
| Preserve markdown structure and return the document only | Slack upload and UI rendering expect plain markdown |
| Strip markdown fences before reuse | Models sometimes wrap output despite explicit instructions |
| Upload the revised brief as a Slack file | Makes the document change visible during the live demo |

---

## 7. Environment Variables

```
GOOGLE_API_KEY=...           # Gemini Live + Gemini text models
GOOGLE_CLOUD_PROJECT=...     # Cloud Vision billing + Cloud Run
SLACK_BOT_TOKEN=xoxb-...     # chat:write scope required
SLACK_CHANNEL=#meeting-actions
GOOGLE_CALENDAR_TOKEN_JSON=...  # JSON from scripts/get_calendar_token.py
```

Auth for Vision: `gcloud auth application-default login` (once, local dev only — Cloud Run uses service account).

---

## 8. Dependencies

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-dotenv>=1.0.0
google-genai>=1.14.0
google-cloud-vision>=3.7.0
google-api-python-client>=2.0.0
google-auth-oauthlib>=1.0.0
slack-sdk>=3.0.0
httpx>=0.28.0
```

---

## 9. Deliberately Dropped

| Dropped | Reason |
|---------|--------|
| Gradium STT | Removed — Gemini Live is the only STT; no fallback needed for demo |
| TTS (ElevenLabs, etc.) | No voice output in MVP |
| Chrome extension | Side-by-side browser windows give same demo effect |
| Claude / Anthropic SDK | **Disqualifying** — all LLM calls must use Gemini |
| Sentiment go/no-go gate | Replaced by autonomous execution; sentiment adjusts content, not whether to act |

**Deploy:**
```bash
gcloud run deploy meeting-agent --source . --region us-central1 --allow-unauthenticated
```
Screenshot the Cloud Run URL for Devpost submission proof.
