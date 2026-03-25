---
phase: 2
slug: voice-driven-gcp-infrastructure-provisioning
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.0+ |
| **Config file** | `tests/conftest.py` (existing) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | Contracts extension | unit | `pytest tests/test_contracts.py -x -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | Understanding extraction | unit | `pytest tests/test_understanding.py -x -q` | ✅ | ⬜ pending |
| 02-01-03 | 01 | 2 | HCL generation | unit | `pytest tests/test_infra.py -x -q` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 2 | Terraform subprocess | integration | `pytest tests/test_infra.py::test_provision_dry_run -x -q` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 3 | Action dispatch | unit | `pytest tests/test_actions.py -x -q` | ✅ | ⬜ pending |
| 02-02-01 | 02 | 1 | Dockerfile build | manual | `docker build -t meeting-agent .` | N/A | ⬜ pending |
| 02-02-02 | 02 | 2 | Cloud Run IAM | manual | GCP Console verification | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_infra.py` — stubs for HCL generation, provision_infrastructure(), terraform subprocess dry-run
- [ ] `tests/test_contracts.py` — stub for InfraRequest typed dict validation (or extend existing contracts test if it exists)

*Existing `tests/test_understanding.py` and `tests/test_actions.py` already exist and will need new test cases.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Terraform applies to real GCP | D-01, D-03 | Requires live GCP project + ADC credentials | Run app, say "spin up a small VM with port 80 open", verify VM appears in GCP console |
| Action card appears after provision | D-08 | Requires running browser + WebSocket | Open app, trigger provision, confirm action card shows with resource name |
| Cloud Run service account permissions | D-09 | Requires GCP IAM console | Verify compute.admin + compute.securityAdmin roles attached to Cloud Run SA |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
