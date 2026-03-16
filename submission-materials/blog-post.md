# Building Google Meet Premium: An AI Meeting Agent That Actually Does Things

*How I built an autonomous meeting agent that listens, understands, and acts — in real time — using Gemini and Google Cloud.*

---

## The Problem Every Meeting Has

We've all been there. You're in a meeting, someone says "I'll send that report by Friday," another person suggests "let's sync Tuesday at 2pm," and someone else asks to "update the budget numbers in the marketing brief." By the time the meeting ends, half of those commitments are forgotten. The other half get captured in notes nobody reads.

What if your meeting tool didn't just transcribe — what if it *acted*?

## What I Built

**Google Meet Premium: AI Meeting Agent** is an autonomous assistant that runs during your meeting and:

- **Transcribes in real time** using Google Cloud Speech-to-Text streaming
- **Understands context** using Gemini 3 Flash to extract commitments, agreements, meeting requests, and document revisions
- **Reads the room** using Google Cloud Vision to detect facial sentiment from your webcam
- **Acts immediately** — creates Google Calendar events, sends Slack messages, revises shared documents, and uploads files — all while the meeting is still happening
- **Sends a summary email** via Gmail API when the meeting ends, with transcript, actions taken, and commitments logged

No human gate. No "review and approve" step. The agent hears "let's meet Tuesday at 2pm" and the calendar invite is sent before the sentence is finished.

## The Architecture

The system is a FastAPI WebSocket server deployed on Google Cloud Run. Here's the flow:

1. **Browser** captures 16kHz PCM audio and webcam frames
2. **Cloud Speech-to-Text** streams interim and final transcripts back in ~300ms
3. **TranscriptBuffer** coalesces segments with a 2-second cooldown to batch related speech
4. **Gemini 3 Flash** extracts structured data: who committed to what, what meetings were requested, what document changes were spoken
5. **ActionSession** dispatches to Slack, Google Calendar, and Gmail in parallel
6. **Sentiment analysis** from Cloud Vision face detection is linked to each action card — if someone commits to something while looking uncertain, the card flags it

All six Google Cloud services (Gemini, Cloud STT, Cloud Vision, Calendar, Gmail, Cloud Run) work together in a single real-time pipeline.

## The Hard Parts

### Making It Feel Real-Time

The biggest challenge was latency. Users expect actions to appear as they speak, not 10 seconds later. The pipeline has inherent delays: STT processing (~300ms), transcript buffering (originally 8 seconds), Gemini understanding (~2 seconds), and action dispatch (~1 second).

I solved this with three techniques:
- **Aggressive buffering**: Reduced cooldown from 8s to 2s and minimum buffer from 80 to 30 characters
- **Instant visual feedback**: A pulsing "Analyzing transcript..." indicator appears in the actions panel the moment speech is detected
- **Independent flush tasks**: When the buffer timer fires and sends text to Gemini, that task runs independently — it can't be cancelled by new audio arriving

### The Cancellation Race Condition

This was the most subtle bug. `TranscriptBuffer` uses an `asyncio.Task` for the cooldown timer. When new speech arrives, the old timer is cancelled. But if the timer had already fired and was mid-way through a Gemini API call, `task.cancel()` would kill the API call too — silently. The meeting would end with "0 Actions Detected" despite perfect transcription.

The fix: separate the cancellable sleep from the non-cancellable flush. The cooldown task now spawns an independent `_execute_flush` task that survives cancellation.

### Making Sentiment Meaningful

Face sentiment analysis on its own is "bells and whistles" — a pill that says "NEUTRAL" isn't actionable. I made it meaningful by linking sentiment to actions. Each action card now carries the speaker's facial sentiment at the moment it was captured:

- **Green border + "Confident"** — speaker was positive/happy
- **Amber border + "Review — uncertain"** — speaker showed uncertainty
- **Red border + "Review — negative tone"** — negative expression detected

Now if someone says "sure, I'll handle the budget review" while looking uncertain, the action card flags it. That's actionable intelligence.

## The Tech Stack

- **Frontend**: Vanilla JS + Tailwind CSS (no framework — keeps the bundle fast)
- **Backend**: Python FastAPI with async WebSocket handling
- **Voice**: Google Cloud Speech-to-Text v1 streaming (16kHz PCM, `latest_long` model)
- **Intelligence**: Gemini `gemini-3-flash-preview` for understanding and document revision
- **Vision**: Google Cloud Vision API face detection with emotion analysis
- **Actions**: Slack SDK, Google Calendar API, Gmail API
- **Hosting**: Google Cloud Run (Docker container, us-central1)

## What I Learned

1. **Gemini's rate limits are real.** The free tier caps at 20 requests/day for newer models. I burned through that in one test session. Paid tier is essential for real-time applications.

2. **Python's `from module import variable` is a trap.** It copies the value at import time. If another function modifies the module-level variable later, your imported reference stays stale. This caused Gmail credentials to silently remain `None` even after Calendar init set them.

3. **Cloud STT has a 5-minute streaming limit.** You need proactive reconnection at ~4 minutes or your transcription silently dies mid-meeting.

4. **Users don't care about latency numbers — they care about perceived latency.** Showing a pulsing "Analyzing..." indicator that appears instantly makes a 4-second pipeline feel real-time.

## Try It

The live demo is at: **https://meeting-agent-974516981471.us-central1.run.app**

Start a meeting, talk about scheduling follow-ups and updating documents, and watch the agent create calendar events, send Slack messages, and revise documents — all before you stop talking.

---

*Built for the [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/) on Devpost.*

*#GeminiLiveAgentChallenge #GoogleCloud #Gemini #AI #MeetingIntelligence*
