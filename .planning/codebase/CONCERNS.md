# Codebase Concerns

**Analysis Date:** 2026-03-22

## Tech Debt

**Global mutable state in action dispatch:**
- Issue: `_calendar_creds`, `_slack`, `_gmail_creds` are module-level globals initialized at startup and shared across all sessions. Credential refresh happens in-place, risking race conditions if multiple WebSocket sessions make concurrent Calendar/Gmail calls.
- Files: `backend/actions.py:40-46`, `backend/email_summary.py:17-27`, `backend/understanding.py:14-20`
- Impact: Concurrent meetings using Calendar/Gmail APIs could interfere with each other's credential state. Token refresh in one session (line 217 of `backend/actions.py`) may invalidate another session's concurrent request.
- Fix approach: Move credentials into per-session `ActionSession` instance or add a lock around credential refresh/use. Calendar service rebuild per-call already mitigates (line 220), but Gmail does not.

**HTML injection in document display:**
- Issue: `simpleMarkdown()` function output is rendered via `.innerHTML` in `static/app/documents.js`. If markdown parsing is naive or Gemini-generated document revisions contain unescaped HTML, XSS is possible.
- Files: `static/app/documents.js:83`, `static/app/documents.js:115`, `static/app/render.js` (multiple innerHTML assignments)
- Impact: Malicious document revisions uploaded by Slack or crafted via Gemini prompt injection could execute arbitrary JavaScript in the client.
- Fix approach: Ensure `simpleMarkdown()` strictly escapes all HTML tags. Audit or replace with a trusted markdown library (e.g., `marked` with sanitization). Validate Gemini response schema.

**Hardcoded email recipients in production:**
- Issue: `RECIPIENTS = ["temuj627@gmail.com", "stevenybusiness@gmail.com"]` is hardcoded in `backend/email_summary.py:15`. No way to override per-deployment; meeting summaries always go to these addresses.
- Files: `backend/email_summary.py:15`
- Impact: Demonstrates presence in source code. At scale, should be config-driven or user-settable.
- Fix approach: Move to environment variable `SUMMARY_EMAIL_RECIPIENTS` or per-session configuration.

**Vision state shared across sessions:**
- Issue: Global `_latest_result` in previous implementation (now per-session in `VisionState` dataclass), but `vision_client` remains global at module level (`backend/vision.py:16`). Concurrent analyze_frame calls share semaphore and client; should be fine but no per-session isolation.
- Files: `backend/vision.py:10`, `backend/session_state.py:10-27`
- Impact: Medium. Semaphore (3 concurrent) and Vision API quotas are global, so one session can starve others during heavy frame analysis. Not a blocker but should monitor in production.
- Fix approach: Track per-session Vision quota or implement backpressure. Current approach is acceptable for MVP.

## Known Bugs

**Document revision deduplication logic vulnerability:**
- Symptoms: Fuzzy deduplication in `ActionSession._is_duplicate_change()` (lines 335–345) uses word set overlap heuristic. If speaker says "change budget to 75K" twice with slight rephrasing ("update budget to 75K"), it may be incorrectly flagged as duplicate and ignored.
- Files: `backend/actions.py:335-345`
- Trigger: Restate a revision with synonyms (e.g., "change" vs "update", "budget" vs "spending").
- Workaround: Wait >10s (cooldown in line 231) between similar revisions or use exact phrasing.

**Transcript buffer cooldown race condition:**
- Symptoms: If multiple transcript segments arrive in rapid succession (< 2s), the cooldown sleep in `_cooldown_flush()` is cancelled and restarted. If a segment arrives exactly when an independent flush task (`_execute_flush()`) spawned by a previous cooldown fires, the buffer may be flushed twice, losing segments.
- Files: `backend/understanding.py:162-184`
- Trigger: Fast speech with segments <2s apart.
- Workaround: Increase `_COOLDOWN_S` or batch-flush threshold. Design is defensive (using `_flush_tasks` set and `_pending_task` cancellation), but edge case exists if timing aligns.

**Calendar event attendees validation too loose:**
- Symptoms: Attendees are filtered to email-like patterns (line 201 of `backend/actions.py`), but Gemini may return names instead of emails. Non-email attendees are silently dropped. Event is created with no attendees, no log warning.
- Files: `backend/actions.py:199-210`
- Trigger: Speak "invite john" or "meet with the team" — Gemini extracts names only.
- Workaround: Speak full email addresses or attendee list explicitly in meeting request.

**Cloud STT reconnection at 4 min hardcoded:**
- Symptoms: `_MAX_STREAM_DURATION_S = 240` (4 min, line 21 of `backend/voice.py`). Proactive reconnect happens even in mid-sentence if meeting goes exactly 4 min. During reconnect (1–5s gap), audio is queued but not transcribed.
- Files: `backend/voice.py:21`, `backend/voice.py:92-109`
- Trigger: Any meeting that runs 4 min or longer.
- Workaround: None. Design is correct (reconnect before 5-min hard limit), but users may notice lag in transcript during reconnect. Logged but not visible in UI.

## Security Considerations

**No input validation on WebSocket text commands:**
- Risk: `/ws/audio` endpoint accepts arbitrary JSON text messages (line 204–206 of `backend/main.py`). If `cmd.get("type") == "stop"`, meeting stops. No authentication; any client with WS URL can close others' meetings.
- Files: `backend/main.py:204-211`
- Current mitigation: WebSocket URL is generated per-session with UUID; URL not guessable. Browser must already be open to access `/ws/audio`.
- Recommendations: Add per-session token validation; rate-limit stop commands; log stop events with client IP.

**Slack token stored in plaintext env var:**
- Risk: `SLACK_BOT_TOKEN` is a Slack API token with full scope. If `.env` is leaked (e.g., via git, backup, or log dump), attacker can post/delete messages, read channel history, manage files in any channel the bot has access to.
- Files: `backend/actions.py:27` (reads from env)
- Current mitigation: `.env` should be in `.gitignore` and never committed. Cloud Run env vars are encrypted at rest in Google's system.
- Recommendations: Use Slack OAuth scopes restricted to `chat:write`, `files:upload`; rotate token quarterly; audit Slack API logs for anomalous posts.

**Gemini API key in plaintext env var:**
- Risk: `GOOGLE_API_KEY` is readable in environment. If Cloud Run logs are exposed, key is visible.
- Files: `backend/main.py:57`, `backend/understanding.py:19`, `backend/documents.py:21`
- Current mitigation: Only Cloud Run startup validation and Gemini API calls include key; key is never logged.
- Recommendations: Use Cloud Key Management Service (KMS) for production; rotate API key monthly; monitor usage for unusual spikes.

**No CORS headers set explicitly — relies on browser origin check:**
- Risk: FastAPI `CORSMiddleware` is not configured. Static frontend is served from same origin (Cloud Run root), so same-origin policy is enforced by browser. But if frontend is ever served from a CDN or third-party domain, API calls will fail with CORS errors or succeed with overpermissive settings.
- Files: `backend/main.py:9` (import but no `add_middleware(CORSMiddleware(...))`), `static/index.html` (no explicit CORS origin)
- Current mitigation: Same-origin policy in browser prevents cross-site requests.
- Recommendations: Add explicit `CORSMiddleware` config if frontend moves to CDN; set `allow_origins=["https://your-domain"]` only.

**Document content stored in memory, not persisted:**
- Risk: Session document revisions (line 377 of `backend/actions.py`: `self._current_doc = revised`) are in-memory only. If Cloud Run instance crashes or is redeployed, all revisions are lost.
- Files: `backend/actions.py:236-277`, `backend/session_state.py:30-35`
- Current mitigation: Revised documents are uploaded to Slack (line 383), so a record exists. But in-session intermediate revisions are lost.
- Recommendations: For production, use Firestore or BigTable to persist session documents; add audit trail of revisions.

**Vision API cost unbounded:**
- Risk: Each frame upload triggers a Cloud Vision API call (debounced 2s). High-frequency video (60fps client + debounce overhead) could trigger 30 Vision calls/min = 1800/hour. At $.15/image, that's $270/hour.
- Files: `backend/vision.py:22-46`
- Current mitigation: Debounce set to 2s, semaphore max 3 concurrent. But no hard cap on frames/session.
- Recommendations: Add per-session frame budget (e.g., max 100 frames/session); disable Vision by default or add UI toggle; monitor Cloud Vision spend.

## Performance Bottlenecks

**Gemini understanding calls may block transcript display:**
- Problem: `understand_transcript()` makes a synchronous `asyncio.to_thread()` call to Gemini (actually async via `aio.models.generate_content`, but rate-limited by semaphore). If rate-limit happens (429 error), retry with exponential backoff up to 35s (line 124 of `backend/understanding.py`).
- Files: `backend/understanding.py:100-129`
- Cause: Gemini Flash inference time (~1–3s) + network latency. If semaphore (4 concurrent) is exhausted, new transcript segments queue.
- Improvement path: Increase semaphore cap (monitor latency); cache recent understanding results; batch short transcripts into fewer API calls; use regional inference endpoint if available.

**Transcript buffer flush heuristics are bursty:**
- Problem: Hard flush at 600 chars (line 159 of `backend/understanding.py`) means if speaker talks continuously, buffer can grow to near 600 before flushing, causing one large Gemini call for a paragraph instead of multiple smaller calls. Cooldown flush (2s, line 142) is too long for fast conversation.
- Files: `backend/understanding.py:142, 159`
- Cause: Tuning for agent responsiveness vs Gemini quota.
- Improvement path: Lower `_COOLDOWN_S` to 1.0s; lower hard flush threshold to 300 chars; or implement sentence-boundary detection to flush at natural breakpoints.

**Cloud Run cold start for first request:**
- Problem: First WebSocket connection to Cloud Run cold-starts the instance. VoicePipeline startup (line 187 of `backend/main.py`) waits up to 15s for Gemini Live session to connect (line 44 of `backend/voice.py`). If Cloud Run is cold, total latency could be 30–45s.
- Files: `backend/voice.py:35-50`, `backend/main.py:186-193`
- Cause: GCP cold-start (5–10s) + Gemini Live session handshake (5–15s).
- Improvement path: Keep Cloud Run warm via scheduled ping; pre-connect Gemini Live session at startup instead of per-WebSocket; use Cloud Run concurrency > 1.

**Calendar event creation blocks on Google API:**
- Problem: `create_calendar_event()` calls `asyncio.to_thread()` for sync googleapiclient (line 221–222 of `backend/actions.py`). If Calendar API is slow (network, quota), event creation can take 5–10s, blocking dispatch.
- Files: `backend/actions.py:183-225`
- Cause: Google's Python client is sync-only; `to_thread()` occupies a thread pool slot.
- Improvement path: Use Google API Python Client's async variant if available; batch calendar operations; use Google API async library (not yet stable for Calendar).

## Fragile Areas

**Vision sentiment normalization edge case:**
- Files: `backend/vision.py:83-87`
- Why fragile: `_norm()` maps Cloud Vision likelihood enums (0–5) to 0–1 via hardcoded dict. If Cloud Vision library updates enum values, mapping breaks silently (returns 0.0 for unknown).
- Safe modification: Add test for all 6 enum values; use `Vision.Likelihood` enum constants instead of raw ints; add logging if unmapped value encountered.
- Test coverage: No unit tests for `_norm()` — behavior not verified against actual API responses.

**Transcript buffer state transitions with cancellation:**
- Files: `backend/understanding.py:132-223`
- Why fragile: `_pending_task` (cooldown timer) and `_flush_tasks` (independent flushes) are managed manually with `.cancel()` and callbacks. If a segment arrives during flush, the pending task cancellation logic may race with flush completion.
- Safe modification: Add integration tests for rapid-fire segments (10/sec); test session close during in-flight Gemini call; verify no buffer loss.
- Test coverage: `tests/regressions/test_understanding.py` has basic tests but lacks concurrency/timing tests.

**ActionSession document revision dedup is lossy:**
- Files: `backend/actions.py:335-345`
- Why fragile: Word-set overlap heuristic (>50% overlap) is overly aggressive. Edge case: "change" (1 word) matched against "update budget" (2 words) = 0% overlap, but "change budget from 50K to 75K" vs "update budget to 75K" = 3/4 = 75% overlap → duplicate.
- Safe modification: Use edit distance (Levenshtein) instead of set overlap; add unit tests for common paraphrases; log dropped duplicates.
- Test coverage: `tests/regressions/test_actions.py` has basic tests but no dedup edge cases.

**Global vision_client may be None silently:**
- Files: `backend/vision.py:12-19`
- Why fragile: If Vision API client init fails (line 17), `vision_client = None` (line 19). Subsequent `analyze_frame()` calls return None (line 28), but no error is logged to user. Meeting proceeds without sentiment data.
- Safe modification: Add fallback Vision provider or log a warning each time `analyze_frame()` is called with no client. Alert user that sentiment is unavailable.
- Test coverage: `tests/regressions/test_vision.py` has no test for `vision_client = None` path.

## Scaling Limits

**In-memory session registry with no eviction:**
- Current capacity: 1,000 sessions × ~10 KB per session = ~10 MB in memory.
- Limit: Cloud Run default memory is 512 MB. At 100 sessions, still <1% usage. But if session cleanup (line 273 of `backend/main.py`) fails (e.g., exception during finally block), sessions leak indefinitely.
- Scaling path: Implement session TTL (garbage collect after 30 min idle); use Firestore for session storage; monitor memory usage in Cloud Monitoring.

**Slack file upload size limit:**
- Current capacity: Documents up to ~2 MB can be uploaded via `files_upload_v2` (line 130–136 of `backend/actions.py`). Fallback to message (line 140–150) for failures.
- Limit: Slack message text blocks are limited to ~2000 chars. Document revisions are typically <1000 chars, so OK for MVP. But if revisions balloon to >2000 chars, fallback message is truncated.
- Scaling path: Check `len(content) > 2000` before fallback; split large revisions into multiple messages; use Slack thread to keep related updates together.

**Gemini understanding rate limit (4 concurrent):**
- Current capacity: 4 concurrent Gemini calls per instance. Each call ~2–3s.
- Limit: If >4 sessions simultaneously flush transcript buffers, requests queue at semaphore. At 10 sessions, one session's understanding call may wait 10–15s.
- Scaling path: Increase semaphore to 8 (test latency); implement request queue with priority (recent segments > old); shard Gemini calls across multiple API keys or projects.

**Google Calendar quota:**
- Current capacity: Google Calendar API has public quotas (1M queries/day per project for free tier; much higher for enterprise).
- Limit: Each meeting_request creates 1 calendar event. 1000 meetings/day × 1 event = 1000 queries. Safe for free tier.
- Scaling path: Switch to Calendar batch API for bulk operations; implement client-side queue if rate-limited (429); cache created event IDs to deduplicate retries.

## Dependencies at Risk

**Gemini Flash 3.5 preview vs stable release:**
- Risk: `gemini-3-flash-preview` is used for both understanding and document revision (lines 22, 14 of `backend/understanding.py` and `backend/documents.py`). Preview models are not stable — may be deprecated or change behavior without notice.
- Impact: Understanding or revision logic breaks if model is removed or changes output schema.
- Migration plan: When `gemini-3.5-flash` stable is available, update both modules. Test understanding output schema (JSON parsing) and revision output (markdown format) against new version. Set up automated regression tests for model updates.

**Google Cloud Speech-to-Text v1 vs v2:**
- Risk: Code uses `google.cloud.speech_v1` (line 14 of `backend/voice.py`). Google announced v2 (now in GA). v1 may be deprecated in 2–3 years.
- Impact: Transcription logic breaks if v1 is removed.
- Migration plan: When v1 deprecation notice arrives, upgrade to `google.cloud.speech_v2.SpeechAsyncClient`. Test streaming request/response format (may differ); update `RecognitionConfig` and `StreamingRecognitionConfig` types.

**google-genai SDK version pinning:**
- Risk: No version pinning in `requirements.txt` or `pyproject.toml`. `google-genai` SDK may release breaking changes without notice.
- Impact: Async API signature, exception types, or model availability could change unexpectedly.
- Migration plan: Add `google-genai>=0.4.0,<1.0.0` pin in requirements; run integration tests weekly against latest version; subscribe to google-genai release notes.

**Slack bot scopes fragile to breaking changes:**
- Risk: Bot uses scopes `chat:write`, `files:upload`, `conversations:join`. If Slack changes scope requirements or renames scopes (e.g., `files:write` supersedes `files:upload`), posting/uploading will fail with "missing_scope" (line 170 of `backend/actions.py`).
- Impact: Document uploads fail silently (fallback to message works, but limited to 2000 chars).
- Migration plan: Review Slack API changelog quarterly; test bot token scopes before deploying; add telemetry to track scope failures.

## Missing Critical Features

**No request authentication — any client can trigger actions:**
- Problem: WebSocket endpoint `/ws/audio` accepts connections with only session UUID. No token, API key, or user identity required. Any client with the UUID can close a meeting or spam actions.
- Blocks: Multi-user deployments, shared URLs, public demos.
- Recommendation: Add per-session token (signed JWT or opaque token); validate on every WebSocket message; log auth failures.

**No audit trail of generated actions:**
- Problem: Actions (calendar, Slack posts, tasks) are logged to stdout but not persisted. If user disputes an action ("I didn't say that!"), no proof of what Gemini understood.
- Blocks: Enterprise use, compliance, debugging.
- Recommendation: Store `(session_id, timestamp, transcript, understanding, action)` in Firestore; expose audit UI.

**No abort/undo for in-flight actions:**
- Problem: Once Gemini outputs a commitment, calendar event is created synchronously (line 317 of `backend/actions.py`). No way to cancel if user says "never mind" 1s later.
- Blocks: High-stakes meetings, demo confidence.
- Recommendation: Add 5s undo window; queue actions, require confirmation in UI before posting to Slack/Calendar.

**Vision sentiment is unused in understanding context:**
- Problem: Facial sentiment is extracted and passed to `understand_transcript()` (line 163 of `backend/main.py`), but Gemini prompt in `backend/understanding.py:25-71` mentions face sentiment only as context. Gemini doesn't make decisions based on face; only text sentiment gates actions (line 259 of `backend/actions.py`).
- Blocks: Full multimodal understanding (judges expect face to influence action gating).
- Recommendation: Strengthen face sentiment in gating logic — e.g., "uncertain text + sad face → block action" is already done (line 261), but "negative text + happy face → proceed anyway?" is not tested. Add explicit UI showing face emotion influence.

## Test Coverage Gaps

**No tests for WebSocket session lifecycle:**
- What's not tested: Clean disconnect, network timeout, Gemini Live session dies unexpectedly (line 175–181 of `backend/main.py`). Does UI properly handle WS close?
- Files: `tests/regressions/test_app_integration.py` (basic smoke test only)
- Risk: Deployment uncovers race conditions or missing cleanup logic.
- Priority: High — integration test with real WebSocket needed.

**No tests for transcript buffer edge cases:**
- What's not tested: Hard flush at exactly 600 chars, cooldown cancellation during in-flight Gemini call, rapid-fire segments (<100ms apart).
- Files: `backend/understanding.py:132-223`
- Risk: Lost transcript segments or duplicate understanding calls in production.
- Priority: High — add timing/concurrency tests.

**No tests for Calendar event creation with missing/invalid attendees:**
- What's not tested: Gemini returns names instead of emails; event is created with empty attendees list; no warning logged.
- Files: `backend/actions.py:199-210`
- Risk: Silent failures in production; users think attendees were added.
- Priority: Medium — add test for non-email attendee handling.

**No tests for Slack token refresh or rate-limit handling:**
- What's not tested: Slack API returns 429; exponential backoff in `backend/actions.py:115–127` (similar to Gemini) not verified.
- Files: `backend/actions.py:76-107`
- Risk: Slack failures cascade in production.
- Priority: Medium — add mock Slack tests for rate limits.

**No load tests for concurrent sessions:**
- What's not tested: 10+ concurrent WebSocket connections; does semaphore (Gemini 4, Vision 3) handle contention?
- Files: `backend/understanding.py:23`, `backend/vision.py:10`
- Risk: Scaling assumptions unverified; latency degrades unexpectedly at 5+ users.
- Priority: Medium — run synthetic load test before large demo.

**No tests for Cloud Run deployment specifics:**
- What's not tested: Cold start latency, environment variable injection, Cloud Logging integration.
- Files: `backend/main.py:14` (dotenv load at startup), `backend/voice.py:44` (15s timeout).
- Risk: Deployment fails or timeouts are too short for Cloud Run cold start.
- Priority: Medium — smoke test on actual Cloud Run environment.

---

*Concerns audit: 2026-03-22*
