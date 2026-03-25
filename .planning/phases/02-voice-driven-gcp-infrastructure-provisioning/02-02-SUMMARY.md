---
phase: 02-voice-driven-gcp-infrastructure-provisioning
plan: "02"
subsystem: infra
tags: [terraform, docker, gcp, compute-engine, ui]

# Dependency graph
requires: []
provides:
  - terraform/provider.tf with hashicorp/google ~> 6.0 and project_id variable
  - Dockerfile installs Terraform 1.11.4 CLI and bakes terraform init
  - UI infra action type with orange badge and VM detail rendering
affects:
  - 02-01 (backend infra.py generates resources.tf into terraform/ directory)
  - future plans that render infra actions

# Tech tracking
tech-stack:
  added: [terraform-cli-1.11.4]
  patterns:
    - Bake terraform init into Docker image to eliminate 30-60s cold-start on first apply
    - TF_VAR_project_id pattern — backend sets env var, provider.tf reads via variable
    - Orange color scheme for infra action badges to visually distinguish compute actions

key-files:
  created:
    - terraform/provider.tf
    - terraform/.gitignore
  modified:
    - Dockerfile
    - static/app/core.js
    - static/app/render.js

key-decisions:
  - "Bake terraform init into Docker image (not at runtime) — eliminates 30-60s cold start per research Pitfall 1"
  - "Use project_id variable with TF_VAR_project_id env var — avoids GOOGLE_PROJECT vs GOOGLE_CLOUD_PROJECT confusion (Pitfall 6)"
  - "Orange color scheme for infra badge — visually distinct from slack (blue), calendar (green), task (purple), document (amber)"
  - "resources.tf excluded from .gitignore — generated at runtime by infra.py, not committed"

patterns-established:
  - "Terraform provider config is static and committed; generated HCL (resources.tf) is gitignored"
  - "Infra action card shows VM name, machine_type, zone, status in payload text"

requirements-completed: [INFRA-01, INFRA-04]

# Metrics
duration: 2min
completed: 2026-03-25
---

# Phase 02 Plan 02: Terraform + Docker + UI Infra Support Summary

**Terraform provider.tf with hashicorp/google ~> 6.0, Terraform 1.11.4 CLI baked into Docker with pre-initialized provider, and infra action cards with orange badge and VM detail display in browser UI**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-25T19:34:45Z
- **Completed:** 2026-03-25T19:36:10Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created `terraform/provider.tf` with Google provider ~> 6.0 and project_id variable (used by Plan 01's infra.py via TF_VAR_project_id)
- Created `terraform/.gitignore` to exclude state files and generated resources.tf
- Updated Dockerfile to install Terraform 1.11.4 binary and bake `terraform init` during image build
- Added `'infra'` to `contracts.actionTypes` and `actionBadge` in core.js with orange color scheme
- Added infra icon mapping (`cloud`) and VM detail payload rendering in render.js

## Task Commits

Each task was committed atomically:

1. **Task 1: Create terraform/provider.tf and update Dockerfile with Terraform CLI** - `6e2a8c8` (feat)
2. **Task 2: Add infra action type to UI contracts, badge config, and render handling** - `3c88f0b` (feat)

## Files Created/Modified
- `terraform/provider.tf` - Static Terraform provider config; Google ~> 6.0, us-central1, project_id variable
- `terraform/.gitignore` - Excludes .terraform/, state files, lock info, resources.tf
- `Dockerfile` - Installs Terraform 1.11.4 via binary download and bakes terraform init
- `static/app/core.js` - Added 'infra' to actionTypes Set; added infra badge (orange) to actionBadge
- `static/app/render.js` - Added infra icon ('cloud') in buildSummary; added infra payload branch in createActionCard

## Decisions Made
- Baked terraform init into Docker image (not at runtime) to avoid 30-60s provider download on first apply
- Used TF_VAR_project_id env var pattern to pass project ID; avoids naming confusion between GOOGLE_PROJECT and GOOGLE_CLOUD_PROJECT
- Orange color scheme for infra badge visually distinguishes infrastructure provisioning from other action types

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

**External IAM configuration required.** See plan frontmatter user_setup for:
- Grant `roles/compute.admin` to Cloud Run service account
  - Location: GCP Console -> IAM & Admin -> IAM -> Edit principal for Cloud Run SA
- Grant `roles/compute.securityAdmin` to Cloud Run service account
  - Location: GCP Console -> IAM & Admin -> IAM -> Edit principal for Cloud Run SA

These permissions are needed for the Terraform Google provider to create Compute Engine VMs and firewall rules at runtime.

## Next Phase Readiness
- terraform/provider.tf is ready for Plan 01's infra.py to write resources.tf alongside it
- Docker image build will include Terraform CLI with pre-initialized provider cache
- UI renders infra action cards with distinct orange badge and VM detail text
- IAM permissions need to be granted manually before end-to-end provisioning works

---
*Phase: 02-voice-driven-gcp-infrastructure-provisioning*
*Completed: 2026-03-25*
