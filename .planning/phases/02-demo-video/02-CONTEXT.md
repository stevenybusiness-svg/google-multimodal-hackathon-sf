# Phase 2: Demo Video - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning
**Source:** Direct discussion with user

<domain>
## Phase Boundary

Record, edit, and export a ≤4min demo video using Loom that opens with all 4 action types firing in ~5 seconds, shows facial sentiment gating, narrates the architecture, and shows the live Cloud Run URL.

</domain>

<decisions>
## Implementation Decisions

### Recording Tool
- Use **Loom** for both recording and editing (no separate editor needed)
- Single-window recording: browser tab showing the live Cloud Run URL + camera overlay

### Actions to Demo (all 4 must fire)
- **Calendar event** — confirmed working (Phase 1 UAT passed)
- **Slack message** — bot posts to channel
- **Task logged** — appears in the Detected Actions panel
- **Doc revision** — commitment/doc change detected by Gemini

### Demo Script Structure
1. **Open (~5s)**: Speak a single sentence that triggers all 4 action types simultaneously — e.g., "Let's schedule a follow-up with Alex on Friday at 2pm, I'll take a note to review the proposal, and we should update the project doc." Watch 4 action cards fire in the Detected Actions panel.
2. **Show facial sentiment** (~30s): Point camera at face, show POSITIVE/NEGATIVE badge updating in real-time as expression changes. Explain: "The agent can see — facial sentiment gates action confidence."
3. **Architecture narration** (~60s): Walk through the See → Hear → Understand → Act diagram. Show the UI components: live transcript, action cards, camera feed.
4. **Live URL** (~15s): Show the Cloud Run URL `https://meeting-agent-31043195041.us-central1.run.app` in the browser address bar. Emphasize: fully deployed, no localhost.
5. **Close** (~10s): Brief pitch — autonomous meeting intelligence, no human gate required.

### Video Constraints
- Total length: ≤4 minutes
- Loom handles export — upload link generated automatically
- No external editing software needed

### Claude's Discretion
- Exact script wording
- Order of architecture diagram narration
- Whether to use Loom's drawing/annotation tools during recording

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `architecture.md` — Multimodal stack diagram and design decisions
- `.planning/ROADMAP.md` — Demo script success criteria (Phase 2 section)

### Live System
- `.planning/phases/01-deploy-auth/cloud-run-url.txt` — Live Cloud Run URL for demo

### Requirements
- `.planning/REQUIREMENTS.md` — SUBMIT-01, SUBMIT-02

</canonical_refs>

<specifics>
## Specific Ideas

- The 3-action (now 4-action) opening moment is the hook — lead with it, don't explain first
- Show `POSITIVE` sentiment badge live — it's visually compelling
- The architecture is "See → Hear → Understand → Act" — use this exact framing
- Loom auto-generates a shareable link after recording — save it as the submission artifact

</specifics>

<deferred>
## Deferred Ideas

- Professional video editing / B-roll
- Multiple takes with editing
- Separate voiceover track

</deferred>

---

*Phase: 02-demo-video*
*Context gathered: 2026-03-22 via direct discussion*
