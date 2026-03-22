---
phase: 01-deploy-auth
plan: 02
subsystem: infra
tags: [cloud-run, gcloud, docker, artifact-registry, google-cloud]

# Dependency graph
requires: []
provides:
  - "Live Cloud Run deployment at https://meeting-agent-31043195041.us-central1.run.app"
  - "Public /health endpoint returning {\"status\": \"ok\"}"
  - "WebSocket-capable backend accessible from browser"
  - "cloud-run-url.txt artifact for submission proof"
affects: [02-demo, 03-submit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "gcloud run deploy --source . with --env-vars-file for JSON-containing env vars"
    - "Compute SA needs artifactregistry.writer on cloud-run-source-deploy repo"

key-files:
  created:
    - ".planning/phases/01-deploy-auth/cloud-run-url.txt"
  modified: []

key-decisions:
  - "Used --env-vars-file /tmp/gsd-env-vars.yaml instead of --set-env-vars because GOOGLE_CALENDAR_TOKEN_JSON contains commas inside the JSON value"
  - "Granted artifactregistry.writer to 31043195041-compute@developer.gserviceaccount.com (compute default SA used by Cloud Build source deploys)"

patterns-established:
  - "Cloud Build source deploys use compute default SA, not cloudbuild SA — grant Artifact Registry writer to compute SA"

requirements-completed: [DEPLOY-01]

# Metrics
duration: 10min
completed: 2026-03-22
---

# Phase 01 Plan 02: Cloud Run Deploy Summary

**Meeting agent deployed to Cloud Run at https://meeting-agent-31043195041.us-central1.run.app with /health returning {"status":"ok"}, submission proof URL captured**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-22T22:58:26Z
- **Completed:** 2026-03-22T23:07:46Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments
- Verified gcloud authenticated as stevenybusiness@gmail.com, project set to project-flash-490419
- Confirmed Cloud Run, Speech, and Vision APIs all enabled
- Deployed meeting-agent service to Cloud Run us-central1 with all required env vars
- Verified live deployment: /health returns {"status":"ok"}, / returns HTTP 200
- Saved public URL to cloud-run-url.txt for submission proof

## Task Commits

Each task was committed atomically:

1. **Task 1: Verify gcloud auth and project config** - no files changed (verification only)
2. **Task 2: Read env vars and deploy to Cloud Run** - `02324a6` (chore)
3. **Task 3: Verify live deployment** - verified inline, no additional commit needed

**Plan metadata:** included in final docs commit

## Files Created/Modified
- `.planning/phases/01-deploy-auth/cloud-run-url.txt` - Public Cloud Run URL for submission proof

## Decisions Made
- Used `--env-vars-file` with YAML format instead of `--set-env-vars` because `GOOGLE_CALENDAR_TOKEN_JSON` contains commas within the JSON value, which would break the comma-delimited `--set-env-vars` format
- Granted `roles/artifactregistry.writer` to `31043195041-compute@developer.gserviceaccount.com` (the service account Cloud Build uses for source deploys) — this was missing and caused 3 build failures before diagnosis

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Granted Artifact Registry write permission to compute SA**
- **Found during:** Task 2 (Deploy to Cloud Run)
- **Issue:** `gcloud run deploy --source .` uses the project's compute default SA (`31043195041-compute@developer.gserviceaccount.com`) to push the built Docker image to Artifact Registry. This SA lacked `roles/artifactregistry.writer` on the `cloud-run-source-deploy` repository, causing the build's PUSH phase to fail silently (build step showed SUCCESS, but overall build FAILURE)
- **Fix:** `gcloud artifacts repositories add-iam-policy-binding cloud-run-source-deploy --member="serviceAccount:31043195041-compute@developer.gserviceaccount.com" --role="roles/artifactregistry.writer"`
- **Files modified:** None (IAM policy change only)
- **Verification:** Subsequent `gcloud run deploy` succeeded and service is live
- **Committed in:** 02324a6 (Task 2 commit, included in same deploy flow)

---

**Total deviations:** 1 auto-fixed (missing critical IAM permission)
**Impact on plan:** Essential fix for the deploy to succeed. No scope creep.

## Issues Encountered
- First two deploy attempts failed with "Build failed; check build logs for details" — no useful error in CLI output. Had to use `gcloud builds describe` to find that the PUSH timing section existed but the build still failed, indicating a permissions issue on the Artifact Registry push step.
- Cloud Build with `--source .` uses the compute default SA (not the cloudbuild SA) — a counter-intuitive IAM assignment that required diagnosis via build metadata inspection.

## Next Phase Readiness
- Live URL available: https://meeting-agent-31043195041.us-central1.run.app
- Health check passing, root endpoint returning 200
- Ready for Phase 2 (demo video) and Phase 3 (submission)
- No blockers

## Self-Check: PASSED

- FOUND: .planning/phases/01-deploy-auth/cloud-run-url.txt
- FOUND: .planning/phases/01-deploy-auth/01-02-SUMMARY.md
- FOUND: commit 02324a6 (deploy task)
- FOUND: live URL verified: https://meeting-agent-31043195041.us-central1.run.app/health returns {"status":"ok"}

---
*Phase: 01-deploy-auth*
*Completed: 2026-03-22*
