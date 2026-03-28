# Live Meeting Agent — Project + RCA

**Canonical doc:** project goal, contract, RCA learnings, and checklists. Other markdown files are lightweight references back to this one.

---

## For Claude (paste as system prompt or project context)

You are working on a **live meeting agent** that autonomously executes actions from what is said and agreed in meetings — calendar event created, task logged, and document updated — the moment a commitment, meeting request, agreement, or document revision is detected. Sentiment gates negative actions (explicit "no" or uncertain+negative face = blocked) and adjusts content on positive actions (risk flag, deadline buffer). Input: real-time voice + optional video. **Primary STT: Google Cloud Speech-to-Text v1 (streaming, interim results).** All understanding/revision AI calls use Gemini (Google DeepMind is lead sponsor; keep stack aligned). Backend on Google Cloud Run. Submitted to the **Multimodal Frontier Hackathon** (March 28, 2026, San Francisco — [Devpost](https://multimodal-frontier-hackathon.devpost.com/)); sponsored by Google DeepMind + DigitalOcean + Unkey + Railtracks + others; $45k+ prize pool. **Mandatory: integrate at least 3 sponsor tools** (20% of judging score). Our 3: **DigitalOcean** (inference), **Unkey** (API key mgmt), **Railtracks** (agentic framework).

**Contract:** transcript (text, speaker?, ts) → understanding → commitment (owner, what, by_when?, sentiment?) or agreement (summary, sentiment?) or meeting_request (summary, attendees?, when?, sentiment?) or document_revision (change, section?) → action_request (type, payload) → Slack/tasks/calendar/document upload. Define commitment vs agreement in one place; action router consumes only these shapes.

**Non-negotiable rules:** (1) Voice: never silence-gate audio sent to STT; send continuous stream; use RMS only for UI; Google Cloud Speech-to-Text v1 is the STT (streaming, reconnects every 4 min before 5-min hard limit). (2) Vision: always guard len(face_annotations) and object lists before indexing; normalize likelihood enums to 0–1 or high/medium/low in one place; face = pixel coords, object = normalized. (3) Structure: split backend by pipeline (voice, understanding, actions); no single 2k+ line server file. (4) One project doc (this file); no separate CONTRACT or per-pipeline flow docs.

When editing code, follow the checklists in §7 and the reuse vs avoid table in §8. Reference the full doc for contract details (§2), flows (§3), and RCA tables (§4–6).

---

## 1. Goal and Scope

- **Product:** Live meeting agent that **takes action** from what is said and agreed (Slack follow-ups, tasks, calendar, document updates). Sentiment used for prioritization and tone. **No memorabilia** (no storybook, memory video, Veo, image gen). No Chrome extension, no Tableau, no Claude/Anthropic.
- **Input:** Real-time voice via Gemini Live API (+ optional video via Cloud Vision). **Output:** Autonomous actions — Slack messages, Google Calendar events, tasks, and document updates — fired the moment commitments, meeting requests, agreements, or document revisions are detected.
- **Key differentiator:** Every other meeting tool transcribes; this one acts. The agent is fully multimodal — it **sees** (Cloud Vision: facial sentiment), **hears** (Cloud STT: real-time transcription with interim results), and **understands** (Gemini Flash: intent extraction) — then acts: calendar events created, tasks logged, doc revisions uploaded to Slack. Negative sentiment gates actions (won't fire if speaker says "no" or face+uncertainty conflict). The demo moment: calendar event + task + doc revision fire in ~5 seconds while a meeting is live.

---

## 2. Contract (Message / Event Shapes)

| Name | Direction | Key fields | Purpose |
|------|-----------|------------|---------|
| transcript | voice → understanding | `text`, `speaker?`, `ts` | STT output segment |
| meeting_request | understanding → actions | `summary`, `attendees?`, `when?`, `sentiment?` | "Let's meet Tuesday" |
| commitment | understanding → actions | `owner`, `what`, `by_when?`, `sentiment?` | "I will X by Y" |
| agreement | understanding → actions | `summary`, `sentiment?` | "We agreed X" |
| document_revision | understanding → actions | `change`, `section?` | "Change the budget to 75K" |
| report_request | understanding → actions | `query`, `metrics?`, `dimensions?`, `time_range?`, `sentiment?` | "Generate a report on CAC by channel" |
| action_request | actions → Slack/etc. | `type`, `payload` | One API call per item |

Define **commitment** vs **agreement** in one place (e.g. one module or README); action router consumes that shape only.

---

## 3. Flows (Compact)

| Flow | In | Out |
|------|----|-----|
| Voice | Mic PCM (all audio, no silence gating) | Transcript — **Google Cloud Speech-to-Text v1** (streaming, interim + final results, reconnects every 4 min) |
| Understanding | Transcript segments + face sentiment | Commitments + agreements + meeting_requests + document_revisions + report_requests + sentiment via `gemini-3-flash-preview` |
| Actions | Commitments / agreements / meeting-requests / document-revisions / report-requests | Google Calendar + task log + doc upload to Slack + BigQuery reports + Looker Studio links; **negative/uncertain sentiment gates (blocks) actions** |
| Reports | Report request (NL query) | Gemini NL→SQL → BigQuery query → results + Looker Studio URL → Slack post |
| Vision | Frames (debounced every 2s) | Face emotion; guarded, normalized; fed into Understanding and action gating |

**Hackathon compliance (Multimodal Frontier Hackathon — March 28, 2026):**
- Theme: agents that **see, hear, and understand** the world — our stack maps exactly: Cloud Vision (see) + Gemini Live (hear) + Gemini Flash (understand)
- Google DeepMind is lead sponsor; Gemini stack is strategic advantage with judges
- DigitalOcean is co-sponsor; use DO inference as alternative model backend (OpenAI-compatible endpoint at `inference.do-ai.run`)
- **Mandatory: integrate at least 3 sponsor tools** — our 3: DigitalOcean (inference), Unkey (API key mgmt + rate limiting), Railtracks (agentic framework)
- Submission needs: public repo + live deploy proof + system architecture diagram + ≤3min demo video + publish skill to shipables.dev
- Win angle: 3 autonomous actions fire in 5s triggered by multimodal input (voice + facial sentiment). No human gate. Real inputs from the real world.

---

## 4. RCA — Voice

| Issue | Cause | Fix |
|-------|--------|-----|
| No captions | Silence gate: only non-silent chunks sent; VAD never saw end-of-turn | **Send all audio**; use RMS only for UI |
| Garbled / no STT | Sample rate mismatch (e.g. 48k sent as 16k) | Log `AudioContext.sampleRate`; verify once |
| Solo / same-language | Prompt assumed two languages; model stayed silent | Define a strict transcribe-only mode |

**Rules:** No client-side silence gating. Validate sample rate. Google Cloud Speech-to-Text v1 is the STT (`model=latest_long`, `language_code=en-US`, `enable_automatic_punctuation=True`). Stream reconnects proactively at 4 min before the 5-min hard limit.

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

**Voice:** [ ] No silence gating  [ ] Sample rate verified (16kHz)  [ ] Cloud STT connected (`google.cloud.speech_v1`)  [ ] Stream reconnects at 4 min  [ ] Health: 5s speech → interim caption in <1s, final in ~1s

**Vision:** [ ] Guard `face_annotations` / `localized_object_annotations`  [ ] Normalize likelihoods  [ ] Document face= pixel, object= normalized  [ ] Test route for one frame

**Context:** [ ] Backend split by pipeline  [ ] One project doc; rules &lt; ~40 lines each  [ ] STT: Gemini Live API noted in one place

**Hackathon (Multimodal Frontier — Mar 28):** [ ] Gemini Live API as primary STT  [ ] All LLM = Gemini (aligned with Google DeepMind sponsor)  [ ] Google Calendar API integrated  [ ] Cloud Run deployed (screenshot/URL for proof)  [ ] Architecture diagram shows see+hear+understand layers  [ ] Demo video filmed (≤3min, opens with autonomous 3-action moment triggered by multimodal input)  [ ] 3 sponsor integrations: DigitalOcean inference + Unkey API key mgmt + Railtracks agentic framework  [ ] Publish skill to shipables.dev  [ ] Register + submit at https://multimodal-frontier-hackathon.devpost.com/

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

1. **Voice:** Google Cloud STT streaming → stable real-time transcript with interim results (~200ms).
2. **Understanding:** Transcript + face sentiment → commitments/agreements/meeting_requests/doc_revisions/report_requests; sentiment classified as positive/neutral/negative/uncertain.
3. **Actions:** Commitment → task logged; meeting request → Calendar event created; document revision → revised brief uploaded to Slack; report request → BigQuery NL→SQL query → results + Looker Studio link posted to Slack. Negative sentiment blocks action. Uncertain + negative face blocks action.
4. **Vision:** No crash on no face; normalized sentiment (0–1); face emotion feeds action gating (uncertain+angry/sad = blocked).
5. **Deploy:** Backend running on Cloud Run; screenshot or URL as submission proof.
6. **Demo:** ≤4min video opens with autonomous 3-action execution (Slack + Calendar + task fire in 5s). Sentiment shown as intelligence layer.

---

# Coding Development Playbook

## Core Principle

Write a spec. Enforce it with tests. Build in parallel. The spec is the source of truth. Playwright is the mechanical proof. Claude Code agents are the workforce.

## Spec-Driven Development

Every project starts with a spec — one file, one page, frozen before code begins.

The spec contains:
- **User flow** — the exact sequence someone walks through
- **API contracts** — routes, schemas, WebSocket events
- **Acceptance criteria** — observable outcomes per step

The spec lives in CLAUDE.md so every agent reads it automatically. Playwright tests are derived from acceptance criteria — one assertion per criterion, nothing more.

## Agents

Claude Code runs parallel agents via the Agent tool. Each agent gets a fresh context window and can work in an isolated git worktree.

| Agent | Role | Worktree? |
|-------|------|-----------|
| Orchestrator | Main session. Dispatches agents, tracks progress, makes phase decisions | No (main branch) |
| Backend | Builds API routes, business logic, database layer | Yes |
| Frontend | Builds UI components, state management, WebSocket client | Yes |
| Testing/QA | Runs Playwright, fixes integration bugs across frontend-backend boundary | Yes |
| Quick Fix | Copy, display, syntax, version issues — lightweight fixes | No |
| Researcher | Investigates libraries, APIs, approaches before planning | No |
| Retro | Runs between phases. Reviews failures, tightens CLAUDE.md for next phase | No |

The orchestrator decides which agents to dispatch and when. Agents read the spec from CLAUDE.md and report back when done.

## Skills

Skills are reusable prompt templates invoked with `/skill-name`. They standardize repeatable workflows so the orchestrator doesn't re-explain the same task each time.

Use skills for any operation that happens more than once across phases — spec updates, phase kickoffs, retros, deploys. Define project-specific skills in a SKILL.md file at the repo root. Claude Code loads them automatically.

Skills keep agents consistent. Instead of the orchestrator writing a different prompt each time it dispatches a testing agent, the skill encodes the exact workflow: what to test, how to report, what to fix. The agent invokes the skill and executes.

## Phased Execution

Phases are spec-driven. Each phase has its own acceptance criteria. Within a phase, agents run in parallel where possible.

```
Phase 1: Skeleton
  Backend:  API stubs returning mock data
  Frontend: UI shell hitting stubs
  Testing:  Smoke test written, wired as stop hook
  (all parallel)

Phase 2: Core Feature
  Backend:  Real logic behind stubs     ──┐
  Frontend: Real UI consuming real API  ──┤ parallel
  Testing:  Runs after both complete    ──┘

Phase 3+: Iterate
  Same pattern. Orchestrator decides what's parallel vs sequential.
```

Phases can overlap. The orchestrator judges dependencies — e.g., Phase 3 frontend can start while Phase 2 testing finishes. Timeline pressure determines how aggressive the overlap is.

## Context Management

| Mechanism | Purpose |
|-----------|---------|
| CLAUDE.md | Spec + project instructions. Every agent reads this on startup. |
| Agent tool | Fresh context per agent. No degradation over long builds. |
| Worktree isolation | Each agent works on its own branch. No merge conflicts during parallel work. |
| Tasks | Orchestrator tracks progress. Survives context compression. |
| Auto-memory | Facts that persist across conversations. |

No planning documents. The spec is in CLAUDE.md, progress is in tasks, everything else is in the code.

## Test Wiring

### Playwright MCP

```json
// .mcp.json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest", "--headless"]
    }
  }
}
```

### Stop Hook

A stop hook runs a shell command after every Claude Code response. Wire Playwright as a stop hook so tests run automatically and failures feed back into context.

```json
// .claude/settings.json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "npx playwright test tests/smoke.spec.ts --reporter=line 2>&1 | tail -30; exit 0"
      }]
    }]
  }
}
```

Flow: Claude writes code → stops → hook runs tests → output injected into conversation → Claude sees pass/fail → fixes if red → hook runs again → repeat until green.

## Rules

1. **Spec first** — if it's not in the spec, don't build it
2. **Tests enforce the spec** — every assertion traces to an acceptance criterion
3. **Parallel by default** — frontend, backend, testing run concurrently unless there's a real dependency
4. **Fresh context per agent** — no quality degradation across long builds
5. **Fix before feature** — red tests block all new work
6. **Deploy early** — skeleton on production URL before feature code
