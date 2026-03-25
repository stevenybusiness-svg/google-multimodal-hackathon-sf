# Phase 2: Voice-Driven GCP Infrastructure Provisioning — Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

User speaks infrastructure requirements during a meeting → agent extracts them via Gemini → generates Terraform HCL → runs `terraform apply` to provision real GCP resources (Compute Engine VMs + firewall rules) autonomously in the background. Phase is done when: a spoken VM request triggers real resource creation in GCP without any human gate.

</domain>

<decisions>
## Implementation Decisions

### Provisioning Backend
- **D-01:** Use Terraform as the provisioning backend — Gemini generates HCL, subprocess runs `terraform init` + `terraform apply`
- **D-02:** HCL is written to a `terraform/` directory in the repo root (persistent state file — idempotent re-applies, Terraform tracks what's provisioned)
- **D-03:** Terraform CLI is installed in the Dockerfile so provisioning works inside Cloud Run (adds ~50MB to image)

### Confirmation Model
- **D-04:** Auto-provision immediately — no human approval gate. Voice request fires `terraform apply` via asyncio.create_task, matching the existing fire-and-forget dispatch pattern in `main.py`

### Trigger Detection
- **D-05:** Add `infrastructure_requests` as a new extraction type in `understand_transcript()` (alongside `commitments`, `agreements`, `meeting_requests`, `document_revisions`) — same Gemini pass, natural language detection
- **D-06:** Gemini extracts structured fields per infra request: `name`, `machine_type`, `zone`, `disk_size_gb`, `ports` (list), `description`, `sentiment`. Gemini fills in sensible defaults for unspecified fields (e.g. `zone: "us-central1-a"`, `machine_type: "e2-medium"`, `disk_size_gb: 20`). Provisioning only fires when `sentiment == "positive"`

### Resource Scope
- **D-07:** V1 scope is Compute Engine instances (`google_compute_instance`) + firewall rules (`google_compute_firewall`) only. No Cloud Storage, Cloud SQL, or other resources in this phase.

### UI Feedback
- **D-08:** Provisioning status appears as action cards in the existing pipeline canvas — consistent with Slack/Calendar cards. Card shows: resource name, machine type, zone, and terraform apply status (pending → success/failure)

### GCP Authentication
- **D-09:** Terraform uses Application Default Credentials from the Cloud Run service account. No extra env vars needed — service account must have `roles/compute.admin` + `roles/compute.securityAdmin` roles. Planner must include IAM grant steps.

### Claude's Discretion
- Exact Terraform template structure (variable blocks, provider version, resource naming convention)
- How to stream terraform output back to the UI during apply
- Whether to use `terraform workspace` per-session or single workspace
- Error card format if terraform apply fails

</decisions>

<specifics>
## Specific Ideas

- The original phase spec states: "spoken infra requirements → Terraform HCL generate + apply → real Compute Engine VMs + firewall rules provisioned in GCP autonomously"
- Demo hook: someone says "spin up a 4-core VM with port 80 open" during the meeting → action card appears → VM exists in GCP console ~30s later

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing understanding pipeline
- `backend/understanding.py` — `understand_transcript()` function and `UNDERSTAND_PROMPT` to extend with `infrastructure_requests`. Also see `contracts.py` for `UnderstandingResult` type definition.
- `backend/contracts.py` — `UnderstandingResult` typed dict — new `infrastructure_requests` field must be added here

### Existing action dispatch pattern
- `backend/actions.py` — `ActionSession` class: fire-and-forget dispatch pattern. New `provision_infrastructure()` function should follow the same async pattern
- `backend/main.py` — `_dispatch()` function: how `understanding` results map to action calls. `infrastructure_requests` provisioning dispatch must be added here.

### Deployment
- `Dockerfile` — where terraform CLI installation steps go (before `CMD`)
- `README.md` — service account IAM role requirements must be documented here

### Phase planning reference
- `.planning/phases/01-deploy-auth/01-CONTEXT.md` — Prior decisions on Cloud Run deploy approach and GCP project config

### No external infra specs
- No external Terraform modules or ADRs exist yet — requirements are fully captured in decisions above

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/understanding.py:understand_transcript()` — extend the prompt + JSON schema, add infra_requests parsing to result
- `backend/actions.py:ActionSession` — add `provision_infrastructure(infra_req)` method following the existing `create_calendar_event()` pattern
- `backend/main.py:_dispatch()` — add `infrastructure_requests` dispatch block parallel to the existing `meeting_requests` → `create_calendar_event()` block

### Established Patterns
- Fire-and-forget: `asyncio.create_task(_dispatch())` with `_bg_tasks` set (prevents GC) — provisioning subprocess must use this same pattern
- Per-session ActionSession: provisioning can be instance method on ActionSession or a module-level function since Terraform state is global
- `if understanding is None:` not `if not understanding:` — EMPTY dict truthy check (applies to infra_requests list check too)
- UnderstandingResult contracts in `backend/contracts.py` — must add `infrastructure_requests` field to the typed dict

### Integration Points
- `understanding.py` UNDERSTAND_PROMPT — add `infrastructure_requests` extraction rules
- `contracts.py` UnderstandingResult — add `infrastructure_requests: list[InfraRequest]`
- `actions.py` ActionSession — add `provision_infrastructure()` async method
- `main.py _dispatch()` — dispatch infra requests to `provision_infrastructure()`
- `Dockerfile` — install terraform CLI
- `terraform/` directory — new, create with `main.tf` + `variables.tf`

</code_context>

<deferred>
## Deferred Ideas

- Cloud Storage bucket provisioning — out of scope for v1 (keep scope tight for demo)
- Confirmation UI with countdown before apply — could be a v2 UX improvement
- `terraform destroy` command triggered by voice ("tear down the VM") — not in this phase
- Terraform workspace isolation per meeting session — Claude's discretion whether to implement

</deferred>

---

*Phase: 02-voice-driven-gcp-infrastructure-provisioning*
*Context gathered: 2026-03-25*
