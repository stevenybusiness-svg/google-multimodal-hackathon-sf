# Slack Integration Reference

> This document is a reusable Slack API integration reference for general hackathon projects. Copy it into any project folder to quickly wire up Slack messaging, file uploads, and bot configuration.

## SDK & Dependencies

```
slack-sdk>=3.0.0
```

Uses `slack_sdk.web.async_client.AsyncWebClient` (async, not the legacy WebhookClient).

---

## Environment Variables

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_CHANNEL=#meeting-actions
```

---

## How It's Used

### Client initialization

```python
from slack_sdk.web.async_client import AsyncWebClient

_slack: AsyncWebClient | None = None

def _get_slack() -> AsyncWebClient | None:
    global _slack
    if _slack is None:
        token = os.getenv("SLACK_BOT_TOKEN")
        if token:
            _slack = AsyncWebClient(token=token)
    return _slack
```

Lazy-initialized on first use; silently skipped if `SLACK_BOT_TOKEN` is not set.

### Posting a message

```python
await client.chat_postMessage(channel=SLACK_CHANNEL, text=text)
```

Target channel is read from the `SLACK_CHANNEL` env var — set it to any channel name for your project.

### Auto-join on `not_in_channel`

If the bot isn't in the channel, it resolves the channel ID via `conversations_list` and calls `conversations_join` before retrying the post.

### File uploads (`files_upload_v2`)

```python
await client.files_upload_v2(
    channel=channel_id,
    content=content,
    filename=filename,
    title=title,
    initial_comment=comment,
)
```

Falls back to posting the document as a code-block message if the `files:write` scope is missing.

---

## Voice-to-Text → Slack Pipeline

This is how spoken audio automatically triggers Slack messages, end to end.

### 1. Audio capture (browser → WebSocket)

The browser captures microphone audio at **16 kHz PCM mono 16-bit** and streams raw bytes over a WebSocket to `/ws/audio`. No silence gating — all audio is forwarded continuously.

### 2. Speech-to-Text (Google Cloud STT v1)

`VoicePipeline` opens a **streaming recognize** session with Cloud STT:

```python
RecognitionConfig(
    encoding=LINEAR16,
    sample_rate_hertz=16000,
    language_code="en-US",
    enable_automatic_punctuation=True,
    model="latest_long",  # optimized for continuous meeting speech
)
StreamingRecognitionConfig(interim_results=True)
```

- **Interim results** stream back in ~200ms for live display
- **Final results** (~1s latency) are what trigger downstream processing
- The stream auto-reconnects every **4 minutes** (Cloud STT hard limit is 5 min)

### 3. Transcript buffering (`TranscriptBuffer`)

Final transcript segments feed into `TranscriptBuffer`, which batches before calling the LLM:

| Behavior | Value |
|---|---|
| Cooldown after last segment | 0.2s |
| Minimum chars to flush | 30 |
| Hard-flush threshold | 600 chars |
| End-of-meeting force-flush | always runs |

This prevents a Gemini API call on every word — segments are coalesced into meaningful chunks.

### 4. Understanding (Gemini Flash)

On flush, the buffer calls `understand_transcript()` which sends the transcript to Gemini with a structured prompt. The model extracts:

- `commitments` — "I will X by Y"
- `agreements` — "We agreed X"
- `meeting_requests` — "Let's meet Tuesday"
- `document_revisions` — "Change the budget to 75K"

Each item gets an individual `sentiment` field (`positive / neutral / negative / uncertain`) that gates whether an action fires.

### 5. Action dispatch → Slack

If `has_action_items(understanding)` is true, `ActionSession.dispatch()` runs as a fire-and-forget `asyncio.Task`:

- **Document revisions** → `_post_slack_document()` uploads the revised doc via `files_upload_v2`, falling back to a code-block message if file scope is unavailable
- **Commitments / agreements** → logged to in-memory task log (no Slack post for these by default)
- Any action with `sentiment == "negative"` is blocked and never posted

```
Browser mic
  └─► WebSocket /ws/audio (PCM bytes)
        └─► VoicePipeline → Cloud STT streaming
              └─► on_transcript(final_text)
                    └─► TranscriptBuffer.process()
                          └─► [cooldown 0.2s or 600-char hard flush]
                                └─► understand_transcript() → Gemini Flash
                                      └─► ActionSession.dispatch()
                                            └─► _post_slack_document() → Slack files_upload_v2
```

---

## Required Bot Token Scopes

| Scope | Purpose |
|---|---|
| `chat:write` | Post messages |
| `channels:read` | Resolve channel name → ID |
| `channels:join` | Auto-join public channels |
| `files:write` | Upload documents as file attachments |

