# Live Meeting Agent — Project + RCA

**Canonical doc:** project goal, contract, RCA learnings, and checklists. Other markdown files are lightweight references back to this one.

---

## For Claude (paste as system prompt or project context)

You are working on a **live meeting agent** that autonomously executes actions from what is said and agreed in meetings — Slack sent, calendar event created, task logged, and document updated — the moment a commitment, meeting request, agreement, or document revision is detected. No human gate. Sentiment informs *how* actions are taken (e.g. stressed face = buffer deadline, add risk flag) not *whether* they fire. Input: real-time voice + optional video. **Primary STT: Gemini Live API (only STT).** All AI calls must use Gemini — no Claude/Anthropic. Backend on Google Cloud Run. Submitted to the **Gemini Live Agent Challenge** (deadline March 16 2026); category: Live Agents.

**Contract:** transcript (text, speaker?, ts) → understanding → commitment (owner, what, by_when?, sentiment?) or agreement (summary, sentiment?) or meeting_request (summary, attendees?, when?, sentiment?) or document_revision (change, section?) → action_request (type, payload) → Slack/tasks/calendar/document upload. Define commitment vs agreement in one place; action router consumes only these shapes.

**Non-negotiable rules:** (1) Voice: never silence-gate audio sent to STT; send continuous stream; use RMS only for UI; Gemini Live API is the only STT. (2) Vision: always guard len(face_annotations) and object lists before indexing; normalize likelihood enums to 0–1 or high/medium/low in one place; face = pixel coords, object = normalized. (3) Structure: split backend by pipeline (voice, understanding, actions); no single 2k+ line server file. (4) One project doc (this file); no separate CONTRACT or per-pipeline flow docs.

When editing code, follow the checklists in §7 and the reuse vs avoid table in §8. Reference the full doc for contract details (§2), flows (§3), and RCA tables (§4–6).

---

## 1. Goal and Scope

- **Product:** Live meeting agent that **takes action** from what is said and agreed (Slack follow-ups, tasks, calendar, document updates). Sentiment used for prioritization and tone. **No memorabilia** (no storybook, memory video, Veo, image gen). No Chrome extension, no Tableau, no Claude/Anthropic.
- **Input:** Real-time voice via Gemini Live API (+ optional video via Cloud Vision). **Output:** Autonomous actions — Slack messages, Google Calendar events, tasks, and document updates — fired the moment commitments, meeting requests, agreements, or document revisions are detected.
- **Key differentiator:** Every other meeting tool transcribes; this one acts. Agent executes autonomously with no human gate. Sentiment is the intelligence layer: stressed face + commitment = Slack flagged as at-risk + deadline buffered 1 day. The demo moment: 3 actions fire in 5 seconds while a meeting is live.

---

## 2. Contract (Message / Event Shapes)

| Name | Direction | Key fields | Purpose |
|------|-----------|------------|---------|
| transcript | voice → understanding | `text`, `speaker?`, `ts` | STT output segment |
| meeting_request | understanding → actions | `summary`, `attendees?`, `when?`, `sentiment?` | "Let's meet Tuesday" |
| commitment | understanding → actions | `owner`, `what`, `by_when?`, `sentiment?` | "I will X by Y" |
| agreement | understanding → actions | `summary`, `sentiment?` | "We agreed X" |
| document_revision | understanding → actions | `change`, `section?` | "Change the budget to 75K" |
| action_request | actions → Slack/etc. | `type`, `payload` | One API call per item |

Define **commitment** vs **agreement** in one place (e.g. one module or README); action router consumes that shape only.

---

## 3. Flows (Compact)

| Flow | In | Out |
|------|----|-----|
| Voice | Mic PCM (all audio, no silence gating) | Transcript — **Gemini Live API** (`gemini-2.5-flash-native-audio-preview-12-2025` with built-in input transcription) |
| Understanding | Transcript segments + face sentiment | Commitments + agreements + meeting_requests + document_revisions + sentiment via `gemini-3-flash-preview` |
| Actions | Commitments / agreements / meeting-requests / document-revisions | Slack + Google Calendar + Tasks + document upload (autonomous; sentiment adjusts content/timing, not whether to fire) |
| Vision | Frames (debounced every ~5s in the current app) | Face emotion; guarded, normalized; fed into Understanding |

**Hackathon compliance (Gemini Live Agent Challenge — deadline Mar 16 2026):**
- Gemini Live API = primary real-time audio (required for "Live Agents" category)
- All LLM calls = Gemini only (`google-genai` SDK); no Claude/Anthropic
- At least one GCP service: Cloud Vision ✅ + Cloud Run (deploy before submission)
- Submission needs: public repo + Cloud Run proof + system architecture diagram + ≤4min demo video
- Win angle: 3 actions fire autonomously in 5s while meeting is live (Slack + Calendar + task). Sentiment = intelligence, not gate.

---

## 4. RCA — Voice

| Issue | Cause | Fix |
|-------|--------|-----|
| No captions | Silence gate: only non-silent chunks sent; VAD never saw end-of-turn | **Send all audio**; use RMS only for UI |
| Garbled / no STT | Sample rate mismatch (e.g. 48k sent as 16k) | Log `AudioContext.sampleRate`; verify once |
| Solo / same-language | Prompt assumed two languages; model stayed silent | Define a strict transcribe-only mode |

**Rules:** No client-side silence gating. Validate sample rate. Gemini Live API is the only STT. Current voice prompt is English-only transcription.

---

## 5. RCA — Vision

| Issue | Cause | Fix |
|-------|--------|-----|
| Crashes / no sentiment | `face_annotations[0]` with empty list | **Guard:** `len(face_annotations) > 0` (and objects) before index |
| Bad thresholds | Raw enum vs int (e.g. `>= 4`) across lib versions | **Normalize** likelihoods to 0–1 or high/medium/low in one place |
| Wrong boxes | Face = pixel, object = normalized; mixed in frontend | Document and enforce per-annotation coordinate system |

**Rules:** Always guard face/object lists. Normalize likelihoods before branching. Test path without trigger (e.g. one frame).

---

## 6. RCA — Context and Structure

| Issue | Fix |
|-------|-----|
| Monolithic server | Split by pipeline: voice, understanding, actions (and optional vision); keep files &lt; ~500 lines |
| Many markdown files | **One project doc** (this file); short rules; no separate CONTRACT/flow docs |
| Long rules | Principles only; no code snippets in rules; model names in code/README |
| Unclear primary path | Single line in README or this doc: "STT: Gemini Live API" |

---

## 7. Checklists (Do Not Skip)

**Voice:** [ ] No silence gating  [ ] Sample rate verified  [ ] Gemini Live API connected  [ ] Solo/same-language mode defined  [ ] Health: 5s speech → caption in 10s

**Vision:** [ ] Guard `face_annotations` / `localized_object_annotations`  [ ] Normalize likelihoods  [ ] Document face= pixel, object= normalized  [ ] Test route for one frame

**Context:** [ ] Backend split by pipeline  [ ] One project doc; rules &lt; ~40 lines each  [ ] STT: Gemini Live API noted in one place

**Hackathon:** [ ] Gemini Live API as primary STT  [ ] All LLM = Gemini (no Claude)  [ ] Google Calendar API integrated  [ ] Cloud Run deployed  [ ] Architecture diagram made  [ ] Demo video filmed (≤4min, leads with autonomous 3-action execution moment)  [ ] Devpost submission complete

**Process:** [ ] After first integration: 5 min test (speak + optional camera); captions + at least one action  [ ] If document revisions stay in scope: verify revised brief upload path  [ ] Before demo: re-run checklists

---

## 8. Reuse vs Avoid

| Reuse | Avoid |
|-------|--------|
| Send all audio; Gemini Live as the only STT | Silence gating; multiple STT switching logic |
| Guard vision lists; normalize sentiment | Raw enum compare; unguarded index |
| Small backend modules; one project doc | Giant server; many markdown files |
| Contract in one table (above) | Separate CONTRACT.md + multiple flow docs |

---

## 9. Success Criteria

1. **Voice:** Gemini Live API streaming → stable real-time transcript.
2. **Understanding:** Transcript + face sentiment → commitments/agreements; conflict detection flags uncertain.
3. **Actions:** Commitment → Slack sent + task logged autonomously; meeting request → Calendar event drafted; document revision → revised brief uploaded. Sentiment adjusts content (risk flag, deadline buffer). No human gate.
4. **Vision:** No crash on no face; normalized sentiment; stress/conflict surfaces as action modifier in UI, not blocker.
5. **Deploy:** Backend running on Cloud Run; screenshot or URL as submission proof.
6. **Demo:** ≤4min video opens with autonomous 3-action execution (Slack + Calendar + task fire in 5s). Sentiment shown as intelligence layer.
