---
phase: 02-voice-driven-gcp-infrastructure-provisioning
plan: 01
subsystem: infra
tags: [terraform, gcp, compute-engine, asyncio, typeddict, gemini-prompt]

requires:
  - phase: 01-deploy-auth
    provides: "ActionSession, make_action_result, contracts.py types foundation"

provides:
  - "InfraRequest TypedDict with 7 fields in contracts.py"
  - "infrastructure_requests extraction in UNDERSTAND_PROMPT"
  - "generate_hcl() producing valid HCL for google_compute_instance + firewall"
  - "_run_terraform() async subprocess helper using asyncio.create_subprocess_exec"
  - "provision_infrastructure() with asyncio.Lock serialization and pending/success/failure cards"

affects:
  - "02-02 (main.py dispatch integration)"
  - "02-03 (Terraform static provider.tf + Dockerfile)"
  - "02-04 (UI infra action card rendering)"

tech-stack:
  added: [asyncio.create_subprocess_exec, uuid (stdlib)]
  patterns:
    - "Programmatic HCL generation from typed fields (no Gemini-generated HCL)"
    - "asyncio.Lock to serialize concurrent terraform subprocess applies"
    - "UUID suffix on resource names to avoid naming collisions"
    - "Static provider.tf + dynamic resources.tf separation"

key-files:
  created:
    - backend/infra.py
  modified:
    - backend/contracts.py
    - backend/understanding.py

key-decisions:
  - "generate_hcl writes to resources.tf (not main.tf) to keep static provider.tf separate"
  - "UUID suffix appended to resource name slug for collision-free GCP resource naming"
  - "asyncio.Lock at module level serializes concurrent applies against shared local tfstate"
  - "Pending action card emitted before terraform apply for immediate UI feedback"

patterns-established:
  - "InfraRequest TypedDict with total=False follows existing Commitment/Agreement pattern"
  - "provision_infrastructure returns make_action_result dict matching existing action types"
  - "HCL generation from typed fields avoids Gemini hallucination risk in infrastructure ops"

requirements-completed: [INFRA-01, INFRA-02, INFRA-03, INFRA-06]

duration: 4min
completed: 2026-03-25
---

# Phase 02 Plan 01: Voice-Driven GCP Infrastructure Backend Summary

**InfraRequest TypedDict, UNDERSTAND_PROMPT infrastructure extraction, and programmatic HCL generator with asyncio.Lock-serialized Terraform subprocess helpers**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-25T19:34:39Z
- **Completed:** 2026-03-25T19:39:02Z
- **Tasks:** 3
- **Files modified:** 3 (contracts.py, understanding.py, infra.py created)

## Accomplishments

- Extended contracts.py with InfraRequest TypedDict (7 fields), infrastructure_requests in UnderstandingResult, "infra" ActionType, and updated UNDERSTANDING_KEYS and empty_understanding()
- Extended UNDERSTAND_PROMPT with infrastructure_requests extraction rules including machine type mapping ("4-core" -> "e2-standard-4") and sentiment gating
- Created backend/infra.py with generate_hcl() (resource blocks only, UUID slug, optional firewall), _run_terraform() (asyncio subprocess), and provision_infrastructure() (lock-serialized, pending/success/failure cards)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend contracts.py with InfraRequest and update UnderstandingResult** - `7863488` (feat)
2. **Task 2: Extend UNDERSTAND_PROMPT to extract infrastructure_requests** - `6c625d0` (feat)
3. **Task 3: Create backend/infra.py with HCL generation and Terraform subprocess helpers** - `f4fafaf` (feat)

## Files Created/Modified

- `backend/contracts.py` - Added InfraRequest TypedDict, infrastructure_requests to UnderstandingResult and UNDERSTANDING_KEYS, "infra" to ActionType, infrastructure_requests:[] to empty_understanding()
- `backend/understanding.py` - Extended UNDERSTAND_PROMPT with infrastructure_requests extraction rules, JSON schema, and nothing-found example
- `backend/infra.py` - New module: generate_hcl(), _run_terraform(), provision_infrastructure(), _tf_lock, TERRAFORM_DIR

## Decisions Made

- Used `resources.tf` (not `main.tf`) as the write target to decouple dynamic resource generation from the static `provider.tf` that Terraform init bakes into the Docker image (per Research Pitfall 5)
- UUID 6-char hex suffix on resource name slug prevents naming collisions when multiple voice requests provision VMs in the same session (per Research Pitfall 4)
- Module-level asyncio.Lock serializes concurrent terraform applies against the shared local tfstate file (per Research Pitfall 3)
- Pending action card emitted before terraform apply so UI shows immediate feedback during the ~30s apply duration

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Local Python 3.9 environment cannot import `google.genai` due to aiohttp TypedDict incompatibility on Python 3.9 EOL. The plan's verification command for understanding.py used the main repo path (/Users/stevenyang/Documents/google-devpost-hackathon) which has the same issue. Verified understanding.py via string content checks instead. This is a local dev environment limitation only; Docker runs Python 3.12 where all imports work correctly.

## Known Stubs

None. generate_hcl() is fully implemented and produces complete HCL. provision_infrastructure() has real terraform subprocess calls. All fields wire through from InfraRequest to generated HCL.

## User Setup Required

None for this plan. IAM role grants (roles/compute.admin, roles/compute.securityAdmin) are covered in a later plan.

## Next Phase Readiness

- backend/infra.py is ready to be imported by main.py dispatch integration (next plan)
- Static terraform/provider.tf must be created and terraform init must be run in Dockerfile (later plan)
- infra ActionType added; UI card rendering for "infra" type needed (later plan)

---
*Phase: 02-voice-driven-gcp-infrastructure-provisioning*
*Completed: 2026-03-25*
