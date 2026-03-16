## Inspiration

Every meeting tool transcribes. None of them *act*. We've all left meetings with a list of "action items" that rot in a shared doc. The insight was simple: if an AI can understand what was said, why does a human still need to press "Create Event" or "Send Message"? We built an agent that closes the loop — from spoken word to executed action — in real time, with no human gate.

The second insight was that **what people say and what they mean aren't always the same**. Someone might agree to a Friday deadline while frowning. A commitment made with uncertainty in the voice deserves a flag, not blind execution. We wanted sentiment to be an intelligence layer — not a gimmick, but a real-time signal that determines whether actions proceed or get blocked.

## What it does

Google Meet Premium is an autonomous AI meeting agent that:

1. **Listens** — Captures 16kHz PCM audio via WebSocket and streams it to Cloud Speech-to-Text for real-time transcription with ~300ms latency
2. **Understands** — Sends transcript segments to Gemini (`gemini-3-flash-preview`) to extract structured data: commitments ("I'll send the deck by Friday"), meeting requests ("Let's sync Tuesday at 1pm"), agreements ("We agreed to cut the budget"), and document revisions ("Reallocate $5K from content to digital")
3. **Sees** — Captures webcam frames every 2 seconds and sends them to Cloud Vision API for face detection and emotion analysis (joy, anger, sadness, surprise)
4. **Decides** — Combines text sentiment and facial sentiment to gate actions. Positive/neutral sentiment → action proceeds (green glow). Negative/uncertain sentiment → action blocked (red glow). This isn't rules-based filtering — it's real-time multimodal intelligence where the *emotional pulse* of the conversation determines what gets executed
5. **Acts** — Autonomously creates Google Calendar events, revises a living marketing document via Gemini and posts it to Slack, and emails a full meeting summary via Gmail at the end. No human confirmation step. Actions fire within seconds of detection. When someone says "reallocate $5K from content to digital," the agent rewrites the budget table with correct math and uploads it to Slack — all in real time

The demo moments:
- Say "Let's reallocate $5,000 from content creation to digital marketing" → the agent revises the marketing brief in real time, recalculates the budget table, and posts the updated document to Slack — all while you're still talking
- Say "Let's schedule a follow-up Friday at 1pm" with a smile → calendar event created, green glow
- Say "Maybe Friday at 4pm?" with a frown → action blocked, red glow with warning arrows on the video feed, no event created

## How we built it

**Backend (Python/FastAPI):** The server is split into clean pipeline modules — `voice.py` (Cloud STT streaming with 4-minute auto-reconnect), `understanding.py` (Gemini extraction with cooldown-based transcript batching), `actions.py` (action dispatch with sentiment gating), `vision.py` (Cloud Vision with boosted negative emotion detection), and `documents.py` (Gemini-powered document revision). Each module is under 350 lines. State is per-session via dataclass registry — no cross-session bleed.

**Real-time pipeline:** Audio flows over WebSocket → Cloud STT streams interim + final transcripts → `TranscriptBuffer` batches segments with a 2-second cooldown (coalesces related speech, minimizes Gemini API calls) → Gemini extracts structured understanding → `ActionSession` dispatches to external APIs via fire-and-forget `asyncio.create_task`. Background tasks are tracked in a `set` to prevent GC before completion. All async — a single uvicorn worker handles multiple concurrent meetings.

**Sentiment gating:** The `_should_block()` method requires *both* facial sentiment (frown/anger/sadness from Cloud Vision) *and* text sentiment (negative/uncertain from Gemini) to agree before blocking an action. Neither signal alone is enough — this prevents false positives from a momentary frown or ambiguous phrasing. When both channels confirm negativity, red warning arrows appear on the video overlay and the action card glows red. This is the key innovation: multimodal sentiment as an intelligence layer, not decoration.

**Vision sensitivity:** Cloud Vision's emotion detection is conservative — it under-reports negative emotions. We use boosted normalization maps for anger/sadness (`VERY_UNLIKELY → 0.3` instead of `0.1`) and a lowered threshold (`0.25`) to make frowns register. The debounce is 2 seconds for near-real-time face state.

**Frontend (Vanilla JS + Tailwind):** Modular JS architecture — `core.js` (state/DOM), `render.js` (UI rendering with glow effects), `media.js` (audio/video capture), `session.js` (WebSocket lifecycle), `documents.js` (live document widget). Action cards show green glow ring for proceeded actions and red glow ring for blocked ones. No framework — just fast, direct DOM manipulation.

**Deployment:** Docker container on Google Cloud Run (us-central1), with env vars for API keys. Cache-busting headers prevent stale static files after deploys.

## Challenges we ran into

- **Cloud Vision under-reports negative emotions.** A clear frown returns `VERY_UNLIKELY` for anger. We solved this with boosted normalization maps that amplify negative signals, plus falling back to text sentiment analysis as a second channel
- **Gemini returns non-email strings as attendees.** When someone says "Let's meet with Sarah," Gemini extracts `["Sarah"]` — not an email. Google Calendar API rejects this. We added regex filtering to strip invalid attendees before API calls
- **Budget math in document revisions.** "Reallocate $5K from content to digital" should add and subtract correctly. Gemini sometimes gets the arithmetic wrong. We added explicit math rules with worked examples in the revision prompt
- **Browser cache serving stale code.** After Cloud Run deploys, browsers served cached JavaScript. Fixed with `Cache-Control: no-cache` middleware + cache-busting query strings on all script tags
- **Cloud Build service account deleted.** The default compute SA was deleted from the GCP project, causing 404s on `gcloud run deploy`. Worked around with a custom service account for builds
- **Balancing sensitivity and false positives.** Too sensitive = every neutral face blocks actions. Not sensitive enough = frowns don't register. We landed on boosted norms for negative emotions only, so happiness detection stays normal while anger/sadness gets amplified

## What we learned

- **Multimodal sentiment is harder than it sounds.** Text says one thing, face says another. The conflict is the most interesting signal — and the hardest to act on reliably
- **Gemini is remarkably good at structured extraction** from natural speech, but needs very explicit prompt engineering for math and brevity
- **Fire-and-forget async patterns** are essential for real-time agents. You can't block the audio pipeline while waiting for a Calendar API call. `asyncio.create_task` with a `set` for GC prevention was the pattern that worked
- **Debounce everything.** Vision API, transcript flushing, action dispatch — without careful debouncing, you hit rate limits instantly and waste API calls on partial data

## What's next

- **Speaker diarization** — attribute commitments to specific speakers ("Sarah said she'll send the deck")
- **Multi-meeting memory** — carry context across meetings ("Last week you committed to X — any update?")
- **Richer integrations** — Jira ticket creation, Notion page updates, Google Docs real-time editing
- **Fine-tuned sentiment model** — train on meeting-specific facial expressions instead of relying on Cloud Vision's general-purpose emotion detection
