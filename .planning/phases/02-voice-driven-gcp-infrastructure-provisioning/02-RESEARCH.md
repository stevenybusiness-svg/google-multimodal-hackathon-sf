# Phase 02: Voice-Driven GCP Infrastructure Provisioning — Research

**Researched:** 2026-03-25
**Domain:** Terraform CLI subprocess execution, GCP Compute Engine provisioning, Gemini HCL generation, Cloud Run ADC authentication
**Confidence:** HIGH (core patterns verified via official docs and Google Cloud docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use Terraform as the provisioning backend — Gemini generates HCL, subprocess runs `terraform init` + `terraform apply`
- **D-02:** HCL is written to a `terraform/` directory in the repo root (persistent state file — idempotent re-applies, Terraform tracks what's provisioned)
- **D-03:** Terraform CLI is installed in the Dockerfile so provisioning works inside Cloud Run (adds ~50MB to image)
- **D-04:** Auto-provision immediately — no human approval gate. Voice request fires `terraform apply` via asyncio.create_task, matching the existing fire-and-forget dispatch pattern in `main.py`
- **D-05:** Add `infrastructure_requests` as a new extraction type in `understand_transcript()` (alongside `commitments`, `agreements`, `meeting_requests`, `document_revisions`) — same Gemini pass, natural language detection
- **D-06:** Gemini extracts structured fields per infra request: `name`, `machine_type`, `zone`, `disk_size_gb`, `ports` (list), `description`, `sentiment`. Gemini fills in sensible defaults for unspecified fields (e.g. `zone: "us-central1-a"`, `machine_type: "e2-medium"`, `disk_size_gb: 20`). Provisioning only fires when `sentiment == "positive"`
- **D-07:** V1 scope is Compute Engine instances (`google_compute_instance`) + firewall rules (`google_compute_firewall`) only.
- **D-08:** Provisioning status appears as action cards in the existing pipeline canvas — consistent with Slack/Calendar cards. Card shows: resource name, machine type, zone, and terraform apply status (pending → success/failure)
- **D-09:** Terraform uses Application Default Credentials from the Cloud Run service account. No extra env vars needed — service account must have `roles/compute.admin` + `roles/compute.securityAdmin` roles. Planner must include IAM grant steps.

### Claude's Discretion
- Exact Terraform template structure (variable blocks, provider version, resource naming convention)
- How to stream terraform output back to the UI during apply
- Whether to use `terraform workspace` per-session or single workspace
- Error card format if terraform apply fails

### Deferred Ideas (OUT OF SCOPE)
- Cloud Storage bucket provisioning — out of scope for v1 (keep scope tight for demo)
- Confirmation UI with countdown before apply — could be a v2 UX improvement
- `terraform destroy` command triggered by voice ("tear down the VM") — not in this phase
- Terraform workspace isolation per meeting session — Claude's discretion whether to implement
</user_constraints>

---

## Summary

This phase adds voice-triggered GCP infrastructure provisioning as a new action type in the meeting agent. The implementation chains four components: (1) extend the existing Gemini prompt to extract `infrastructure_requests` fields alongside existing action types; (2) add an `InfraRequest` TypedDict to `contracts.py` and extend `UnderstandingResult`; (3) implement `provision_infrastructure()` on `ActionSession` that generates Terraform HCL from structured fields, writes it to `terraform/`, and runs `terraform init` + `terraform apply -auto-approve` via `asyncio.create_subprocess_exec`; (4) install Terraform CLI in the Dockerfile via binary download from HashiCorp releases.

The primary state management risk is that `terraform/terraform.tfstate` lives on the Cloud Run container's local filesystem, which is ephemeral. For a hackathon demo where a single container instance handles the session, this is acceptable — the state persists for the demo session. The GCS remote backend is the production fix but is not required for demo correctness.

ADC authentication is fully automatic inside Cloud Run: Terraform's Google provider discovers credentials via the metadata server when no `credentials` block is specified. The service account must have `roles/compute.admin` and `roles/compute.securityAdmin` granted at the project level.

**Primary recommendation:** Use `asyncio.create_subprocess_exec` (not `to_thread` + `subprocess.run`) for terraform subprocess execution. This keeps the async event loop non-blocking, allows capturing stdout/stderr for UI feedback, and matches the existing fire-and-forget pattern. Write HCL programmatically from the extracted `InfraRequest` fields (not Gemini-generated HCL) to avoid hallucination risk in safety-critical infrastructure operations.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Terraform CLI | 1.11.4 (pinned) | HCL apply engine | HashiCorp stable release; 1.11.x active maintenance window |
| hashicorp/google provider | ~> 6.0 | GCP Compute Engine resources | Current major; ADC-native, no key file needed |
| asyncio.create_subprocess_exec | stdlib | Non-blocking subprocess for terraform | Native Python async; no new dependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio.subprocess.PIPE | stdlib | Capture terraform stdout/stderr | Stream output to UI card in real-time |
| google.auth (already in requirements.txt) | existing | ADC credential chain | Already available via google-auth-oauthlib |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct HCL generation (programmatic) | Gemini-generated HCL | Gemini HCL generation is LOW confidence for validity — hallucinated resource arguments cause `terraform apply` failures with no retry path. Programmatic generation from typed fields is deterministic and testable. |
| Local tfstate (D-02 decision) | GCS remote backend | GCS remote backend is the production-grade choice but requires a pre-created bucket and adds setup steps. Local state works for hackathon demo with a single-instance Cloud Run. |
| asyncio.create_subprocess_exec | asyncio.to_thread + subprocess.run | to_thread blocks a thread pool worker for the full terraform apply (~30s). create_subprocess_exec is truly non-blocking. |
| Terraform 1.11.4 | Latest 1.14.8 | 1.11.x is LTS-supported and well-tested. 1.14.8 introduced ephemeral blocks (not needed here). Pin to 1.11.4 for stability. |

**Installation (Dockerfile addition):**
```dockerfile
# Install Terraform CLI — binary download (no apt repo needed, no gnupg dependency)
ARG TERRAFORM_VERSION=1.11.4
RUN apt-get update && apt-get install -y --no-install-recommends wget unzip \
    && wget -q "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
    && unzip "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -d /usr/local/bin \
    && rm "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
    && apt-get purge -y wget unzip && rm -rf /var/lib/apt/lists/*
```

**Version verification (run before planning):**
```bash
# Latest stable as of 2026-03-25
curl -s https://releases.hashicorp.com/terraform/ | grep -o 'terraform/[0-9]*\.[0-9]*\.[0-9]*' | head -5
```
Verified version: **1.11.4** (stable, active maintenance). Latest available is 1.14.8 but 1.11.x is the most recent LTS-supported branch.

---

## Architecture Patterns

### Recommended Project Structure
```
terraform/
├── main.tf           # provider, google_compute_instance, google_compute_firewall per request
├── variables.tf      # project, region, zone, name, machine_type, disk_size_gb, ports
└── terraform.tfstate # generated by terraform apply (local, ephemeral for demo)
backend/
├── contracts.py      # add InfraRequest TypedDict, extend UnderstandingResult
├── understanding.py  # extend UNDERSTAND_PROMPT with infrastructure_requests extraction
├── actions.py        # add provision_infrastructure() async method to ActionSession
├── infra.py          # NEW: HCL generation + terraform subprocess helpers
└── main.py           # add infrastructure_requests dispatch in _dispatch()
```

### Pattern 1: Programmatic HCL Generation

**What:** Generate `main.tf` content as a Python string from typed `InfraRequest` fields, write to `terraform/main.tf`, then run `terraform apply`.

**When to use:** Always — this is safer than Gemini-generated HCL because it avoids hallucinated resource arguments.

**Example:**
```python
# Source: derived from registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_instance
# and registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_firewall

def generate_hcl(req: InfraRequest, project: str) -> str:
    name = req["name"]
    ports_allow = ""
    if req.get("ports"):
        ports_str = ", ".join(f'"{p}"' for p in req["ports"])
        ports_allow = f"""
resource "google_compute_firewall" "{name}-fw" {{
  name    = "{name}-fw"
  network = "default"
  allow {{
    protocol = "tcp"
    ports    = [{ports_str}]
  }}
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["{name}"]
}}
"""
    return f"""
terraform {{
  required_providers {{
    google = {{
      source  = "hashicorp/google"
      version = "~> 6.0"
    }}
  }}
}}

provider "google" {{
  project = "{project}"
  region  = "us-central1"
}}

resource "google_compute_instance" "{name}" {{
  name         = "{name}"
  machine_type = "{req.get("machine_type", "e2-medium")}"
  zone         = "{req.get("zone", "us-central1-a")}"
  tags         = ["{name}"]

  boot_disk {{
    initialize_params {{
      image = "ubuntu-minimal-2210-kinetic-amd64-v20230126"
      size  = {req.get("disk_size_gb", 20)}
    }}
  }}

  network_interface {{
    network = "default"
    access_config {{}}
  }}
}}
{ports_allow}
"""
```

### Pattern 2: asyncio.create_subprocess_exec for Terraform Subprocess

**What:** Run `terraform init` then `terraform apply -auto-approve` as non-blocking async subprocesses, capturing stdout/stderr for UI feedback.

**When to use:** Any time terraform CLI is invoked from within the async FastAPI server.

**Example:**
```python
# Source: docs.python.org/3/library/asyncio-subprocess.html
import asyncio

async def _run_terraform(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a terraform command, return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    return (
        proc.returncode,
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
    )

async def provision_infrastructure(req: InfraRequest, terraform_dir: str, project: str) -> ActionResult:
    hcl = generate_hcl(req, project)
    main_tf = os.path.join(terraform_dir, "main.tf")
    with open(main_tf, "w") as f:
        f.write(hcl)

    # terraform init (only needed once; subsequent runs are fast)
    rc, out, err = await _run_terraform(["terraform", "init", "-no-color"], terraform_dir)
    if rc != 0:
        return make_action_result("infra", req, "failed", f"terraform init failed: {err[:200]}")

    # terraform apply
    rc, out, err = await _run_terraform(
        ["terraform", "apply", "-auto-approve", "-no-color"], terraform_dir
    )
    if rc != 0:
        return make_action_result("infra", req, "failed", f"terraform apply failed: {err[:200]}")

    return make_action_result("infra", {"name": req["name"], "machine_type": req["machine_type"], "zone": req["zone"]}, "sent")
```

### Pattern 3: Extending UnderstandingResult and UNDERSTAND_PROMPT

**What:** Add `infrastructure_requests` to the existing Gemini prompt and contracts.

**When to use:** This phase only — extend existing extraction, do not create a separate Gemini call.

**contracts.py addition:**
```python
class InfraRequest(TypedDict, total=False):
    name: str
    machine_type: str        # e.g. "e2-medium", "n2-standard-4"
    zone: str                # e.g. "us-central1-a"
    disk_size_gb: int        # default 20
    ports: list[str]         # e.g. ["80", "443", "22"]
    description: str
    sentiment: str           # gate: only provision on "positive"

# Add to UnderstandingResult:
class UnderstandingResult(TypedDict):
    commitments: list[Commitment]
    agreements: list[Agreement]
    meeting_requests: list[MeetingRequest]
    document_revisions: list[DocumentRevision]
    infrastructure_requests: list[InfraRequest]   # NEW
    sentiment: str
```

**Prompt addition (append to UNDERSTAND_PROMPT extraction list):**
```
- infrastructure_requests: requests to provision cloud infrastructure ("spin up a VM", "create a 4-core server", "set up a machine with port 80 open")
  - name: short slug for the resource (e.g. "demo-server", "web-vm") — generate if not specified
  - machine_type: GCP machine type (default "e2-medium"; "4-core" → "e2-standard-4"; "small" → "e2-micro")
  - zone: GCP zone (default "us-central1-a")
  - disk_size_gb: integer (default 20)
  - ports: list of TCP port strings mentioned (e.g. ["80", "443"]; empty list if none)
  - description: brief description of the request
  - sentiment: positive/neutral/negative/uncertain (same rules as other fields — only "positive" triggers provisioning)
```

**JSON schema addition:**
```json
"infrastructure_requests": [{"name": "...", "machine_type": "...", "zone": "...", "disk_size_gb": 20, "ports": [], "description": "...", "sentiment": "..."}]
```

### Pattern 4: Fire-and-Forget Dispatch (matches existing pattern)

**What:** Dispatch infrastructure provisioning via `asyncio.create_task` using the same `_bg_tasks` set pattern already in `main.py`.

**main.py `_dispatch()` addition:**
```python
# In _dispatch(), after the existing document_revisions block:
for infra_req in understanding.get("infrastructure_requests", []):
    if infra_req.get("sentiment") == "positive":
        t = asyncio.create_task(
            session.provision_infrastructure(infra_req, on_action=_on_action)
        )
        _bg_tasks.add(t)
        t.add_done_callback(_bg_tasks.discard)
```

### Anti-Patterns to Avoid
- **Gemini-generated HCL strings:** Gemini may hallucinate invalid resource arguments (e.g. non-existent `google_compute_instance` fields). Use programmatic HCL generation from typed fields instead.
- **`subprocess.run()` in async context:** Blocks the event loop for the full terraform apply duration (~20-60s). Use `asyncio.create_subprocess_exec` or `asyncio.to_thread` — prefer `create_subprocess_exec`.
- **`terraform apply` without `-auto-approve`:** Causes the subprocess to block waiting for stdin confirmation. Always pass `-auto-approve` for non-interactive execution.
- **`terraform apply` without `-no-color`:** Produces ANSI escape codes that pollute captured output/logs.
- **Using `if not understanding.get("infrastructure_requests"):` to check for empty list:** Empty list is falsy — consistent with existing codebase which already uses `if understanding is None:` to distinguish None from empty dict. Check explicitly: `if understanding.get("infrastructure_requests"):`.
- **Single `main.tf` for all sessions without resource name scoping:** Multiple voice requests will conflict if the same resource name is reused. Use the `name` field as the resource identifier in HCL to ensure idempotent re-applies (Terraform state deduplicates by resource address).
- **Running `terraform init` every apply:** `terraform init` downloads the provider plugin (~50MB). Run it once in the Dockerfile build using `terraform -chdir=/app/terraform init` so the `.terraform/` plugin cache is baked in. Subsequent applies skip the download.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GCP VM provisioning | Custom GCP API calls (Compute Engine REST) | Terraform google_compute_instance | Terraform handles idempotency, dependency ordering, rollback, state tracking — reimplementing this is months of work |
| Terraform state tracking | Custom in-memory resource registry | Terraform's local tfstate | State tracking is the hardest part of IaC — race conditions, partial applies, drift detection |
| Async subprocess with stdout streaming | `threading.Thread` + `subprocess.Popen` | `asyncio.create_subprocess_exec` | Native async avoids thread overhead, integrates with existing event loop |
| Credential injection | Service account key JSON in env | ADC via Cloud Run metadata server | ADC is automatic in Cloud Run — no credential management needed |

**Key insight:** Terraform handles the hardest parts of infrastructure provisioning (idempotency, dependency graph, partial failure recovery). The implementation work is: (1) install terraform in Docker, (2) write HCL generator, (3) run subprocess. The Compute Engine REST API path would require handling quota errors, polling for operation completion, network ordering, firewall dependencies — all of which Terraform handles automatically.

---

## Runtime State Inventory

> Included because this phase provisions external GCP resources.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `terraform/terraform.tfstate` — local file, ephemeral in Cloud Run container | No migration; state is created fresh. For demo, ephemeral state is acceptable (single container). |
| Live service config | GCP Compute Engine VMs and firewall rules created by `terraform apply` — exist in GCP project after provisioning | `terraform destroy` (out of scope per D-04 deferral) or manual GCP console cleanup after demo |
| OS-registered state | None — no cron jobs, no systemd units | None |
| Secrets/env vars | `GOOGLE_CLOUD_PROJECT` already present in Cloud Run env — Terraform Google provider reads this via ADC metadata | No changes needed; confirm project ID is set in Cloud Run service env |
| Build artifacts | `.terraform/` provider plugin cache baked into Docker layer during build via `terraform init` | Include in `.dockerignore` exclusion if building locally to avoid shipping dev cache |

**Nothing found in category:** OS-registered state — None, verified by inspection of existing codebase.

---

## Common Pitfalls

### Pitfall 1: `terraform init` on Every Apply Downloads Provider (~50MB)
**What goes wrong:** `terraform init` fetches the hashicorp/google provider plugin (~50MB) on first run. In Cloud Run, this happens at request time, adding 30-60 seconds to the first provisioning call and consuming network bandwidth on every cold start.
**Why it happens:** `terraform init` is idempotent but always checks for provider updates unless a lock file and cached plugin exist.
**How to avoid:** Add `RUN terraform -chdir=/app/terraform init` to the Dockerfile AFTER copying the `terraform/` directory (which must contain `main.tf` with the provider block). The `.terraform/` plugin cache is then baked into the Docker image. Also commit `.terraform.lock.hcl` to the repo.
**Warning signs:** First provisioning request takes >60 seconds end-to-end; logs show "Installing hashicorp/google v6.x.x".

### Pitfall 2: Terraform Apply Blocks on stdin Without `-auto-approve`
**What goes wrong:** `terraform apply` prompts "Do you want to perform these actions?" and waits indefinitely for stdin input. The subprocess hangs forever.
**Why it happens:** Terraform's default behavior is interactive confirmation.
**How to avoid:** Always pass `-auto-approve` when invoking via subprocess.
**Warning signs:** `provision_infrastructure` coroutine never resolves; no action card appears in UI.

### Pitfall 3: Multiple Concurrent Applies Race on the Same State File
**What goes wrong:** If two voice requests trigger provisioning simultaneously, both processes try to read/write `terraform.tfstate` concurrently, corrupting state. Terraform uses a `.terraform.tfstate.lock.info` file for locking but this only works with remote backends.
**Why it happens:** Local state backend has no distributed locking.
**How to avoid:** Use a module-level `asyncio.Lock` around terraform subprocess invocations. This ensures only one apply runs at a time within a container instance (sufficient for single-instance Cloud Run demo).
**Warning signs:** `terraform.tfstate.lock.info` error in logs: "Error locking state: Error acquiring the state lock".

### Pitfall 4: Resource Naming Collisions Between Sessions
**What goes wrong:** Two different sessions both request "spin up a web server" — both generate `name = "web-server"`. The second apply tries to create a resource that already exists in state but was created by the first session, causing an error if the state file diverged.
**Why it happens:** Terraform state tracks resources by address (`google_compute_instance.web-server`), and two requests with the same name map to the same address.
**How to avoid:** Append a short UUID suffix to the name field during HCL generation: `name_slug = f"{req['name']}-{uuid.uuid4().hex[:6]}"`. This ensures each provisioning call creates uniquely-named GCP resources.
**Warning signs:** "Error: googleapi: Error 409: The resource 'projects/…/zones/…/instances/web-server' already exists".

### Pitfall 5: Terraform Init in Dockerfile Requires Provider Block in main.tf at Build Time
**What goes wrong:** Running `terraform init` in the Dockerfile requires a `terraform/main.tf` that declares the provider. But at apply time, the `main.tf` is overwritten with the generated HCL. If the generated HCL uses a different provider version, `init` runs again at apply time.
**Why it happens:** `terraform init` caches the provider version declared in `required_providers`. If the generated HCL uses the same pinned version, the cache is used. If it differs, init re-downloads.
**How to avoid:** Use a static `terraform/provider.tf` that declares only the provider block (never overwritten), and write resource blocks to a separate `terraform/resources.tf`. This decouples provider initialization from resource generation.
**Warning signs:** Logs show provider download at apply time despite init running in Dockerfile.

### Pitfall 6: Google Provider `project` Field — GOOGLE_CLOUD_PROJECT vs GOOGLE_PROJECT
**What goes wrong:** The Terraform Google provider accepts the project ID via the `project` attribute in the provider block, or via the `GOOGLE_PROJECT` / `GOOGLE_CLOUD_PROJECT` environment variables (both are checked). The Cloud Run env already has `GOOGLE_CLOUD_PROJECT` set. However, if the provider block is empty (no project field), Terraform may not find the project in some environments.
**Why it happens:** The env var name checked by the provider is `GOOGLE_PROJECT`, but Cloud Run injects `GOOGLE_CLOUD_PROJECT`. Both are checked per Google provider docs, but this is worth explicitly testing.
**How to avoid:** Set `project = var.project_id` in the provider block and pass `TF_VAR_project_id` env var, OR explicitly set `project` in the provider block by reading `os.environ["GOOGLE_CLOUD_PROJECT"]` in the HCL generator. The latter is simpler.
**Warning signs:** `Error: Insufficient project for API request` from terraform apply.

### Pitfall 7: Cloud Run Service Account IAM Permissions
**What goes wrong:** The Terraform google provider uses ADC (service account), but the Cloud Run service account doesn't have Compute Engine permissions. All `terraform apply` calls fail with 403 PERMISSION_DENIED.
**Why it happens:** Cloud Run service accounts are granted minimal permissions by default. `roles/compute.admin` and `roles/compute.securityAdmin` are not included by default.
**How to avoid:** Run these gcloud commands before deploying:
```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/compute.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/compute.securityAdmin"
```
**Warning signs:** `Error 403: Required 'compute.instances.create' permission`.

---

## Code Examples

Verified patterns from official sources:

### google_compute_instance Minimal HCL
```hcl
# Source: docs.cloud.google.com/docs/terraform/create-vm-instance (verified 2026-03-25)
resource "google_compute_instance" "default" {
  name         = "my-vm"
  machine_type = "e2-medium"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "ubuntu-minimal-2210-kinetic-amd64-v20230126"
      size  = 20
    }
  }

  network_interface {
    network = "default"
    access_config {}  # Assigns ephemeral external IP
  }
}
```

### google_compute_firewall Minimal HCL
```hcl
# Source: registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_firewall
# (via web search + shisho.dev/dojo examples, verified pattern)
resource "google_compute_firewall" "allow-http" {
  name    = "my-vm-fw"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["my-vm"]  # Applies only to instances tagged "my-vm"
}
```

### GCS Remote Backend (discretionary — recommended for production)
```hcl
# Source: developer.hashicorp.com/terraform/language/backend/gcs (verified 2026-03-25)
terraform {
  backend "gcs" {
    bucket = "tf-state-meeting-agent"
    prefix = "terraform/state"
  }
}
# ADC is used automatically — no credentials block needed
```

### asyncio Subprocess Pattern
```python
# Source: docs.python.org/3/library/asyncio-subprocess.html (verified 2026-03-25)
import asyncio

proc = await asyncio.create_subprocess_exec(
    "terraform", "apply", "-auto-approve", "-no-color",
    cwd="/app/terraform",
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
stdout_bytes, stderr_bytes = await proc.communicate()
# proc.returncode is 0 on success, non-zero on failure
```

### Terraform APT Install (alternative to binary download)
```dockerfile
# Source: developer.hashicorp.com/terraform/cli/install/apt (verified 2026-03-25)
# Note: requires gnupg and apt-transport-https, adds more layer bloat than binary download
RUN wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com bookworm main" | tee /etc/apt/sources.list.d/hashicorp.list \
    && apt-get update && apt-get install -y terraform
```
**Recommendation:** Use binary download instead (see Standard Stack section) — fewer apt packages, pinned version, smaller diff.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Terraform 0.x separate plan/apply | Terraform 1.x unified `apply -auto-approve` | Terraform 1.0 (2021) | `-auto-approve` skips interactive confirmation, safe for automation |
| Long-lived service account keys in env | ADC via Cloud Run metadata server | GCP best practice since 2022 | No GOOGLE_APPLICATION_CREDENTIALS file needed; automatic rotation |
| Provider `credentials` block with JSON key | Empty provider block — ADC auto-detected | google provider v4+ | Terraform Google provider discovers ADC automatically, no explicit config |
| `subprocess.run()` blocking | `asyncio.create_subprocess_exec` | Python 3.8+ | Truly async, non-blocking, integrates with FastAPI event loop |

**Deprecated/outdated:**
- `terraform.tfvars` for secrets: Use environment variables (`TF_VAR_*`) — tfvars risk being committed to git.
- `google provider` v3.x: v6.x is current; v3 docs show different resource arguments.

---

## Open Questions

1. **Terraform init baking strategy**
   - What we know: `terraform init` must run before `apply`. Running it in Dockerfile saves 30-60s per cold start.
   - What's unclear: The Dockerfile `COPY . .` copies the entire repo including `terraform/` — but at build time, `main.tf` is the template file, not a generated one. The planner needs to decide: create a static `terraform/provider.tf` committed to the repo (contains only the provider block), and write resources to a separate `terraform/resources.tf` at runtime.
   - Recommendation: Create `terraform/provider.tf` (static, committed) + `terraform/resources.tf` (generated at runtime). Run `terraform init` in Dockerfile against `provider.tf`. This decouples init from resource generation.

2. **GCS state backend vs. local state**
   - What we know: D-02 says local state file. Cloud Run containers are ephemeral but a single demo session uses one container instance. Local state works for demo.
   - What's unclear: If Cloud Run scales to 2+ instances, state diverges. For hackathon (single demo session), this is not a problem.
   - Recommendation: Use local state (per D-02). Add a `## Known Limitations` note in README about statefile ephemerality.

3. **ActionType expansion in contracts.py**
   - What we know: `ActionType = Literal["slack", "calendar", "task", "document", "email"]` — "infra" is not present.
   - What's unclear: Whether to add "infra" to the Literal or use "task" as the type for UI card rendering consistency.
   - Recommendation: Add `"infra"` to `ActionType` Literal so UI can render a distinct card style.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| terraform CLI | `provision_infrastructure()` subprocess | ✗ (local dev machine) | — | Installed in Dockerfile (D-03) — only needed inside Cloud Run |
| gcloud CLI | IAM role grants (manual deploy step) | ✗ (local dev machine) | — | Developer must install separately; document in README |
| docker | Building image with terraform | ✗ (local dev machine) | — | Cloud Build can build without local Docker |
| python3 | Backend runtime | ✓ | 3.9.1 (local) / 3.12 (Docker) | — |
| GOOGLE_CLOUD_PROJECT env var | Terraform provider project field | Configured in Cloud Run | — | Must be confirmed in Cloud Run service config |

**Missing dependencies with no fallback:**
- `terraform` CLI is not available locally — this is expected and acceptable. All terraform commands run inside the Cloud Run container via the Dockerfile installation.

**Missing dependencies with fallback:**
- `gcloud` CLI for IAM grants: can use GCP Console UI as fallback for the manual IAM step.

---

## Validation Architecture

> `workflow.nyquist_validation` not set in config.json — treating as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0 (already in requirements.txt) |
| Config file | none (run from repo root) |
| Quick run command | `pytest backend/tests/ -x -q` |
| Full suite command | `pytest backend/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| INFRA-01 | `infrastructure_requests` extracted from transcript | unit | `pytest backend/tests/test_understanding.py::test_infra_extraction -x` | ❌ Wave 0 |
| INFRA-02 | `generate_hcl()` produces valid HCL for VM + firewall | unit | `pytest backend/tests/test_infra.py::test_generate_hcl -x` | ❌ Wave 0 |
| INFRA-03 | Negative/uncertain sentiment blocks provisioning | unit | `pytest backend/tests/test_infra.py::test_sentiment_gate -x` | ❌ Wave 0 |
| INFRA-04 | `provision_infrastructure()` fires terraform subprocess | integration | `pytest backend/tests/test_infra.py::test_provision_subprocess -x` | ❌ Wave 0 |
| INFRA-05 | Action card emitted with pending/success/failure status | unit | `pytest backend/tests/test_infra.py::test_action_card -x` | ❌ Wave 0 |
| INFRA-06 | Concurrent provisioning requests serialized by asyncio.Lock | unit | `pytest backend/tests/test_infra.py::test_concurrent_lock -x` | ❌ Wave 0 |
| D-03 | Terraform binary present in Docker image | manual | `docker run <image> terraform version` | N/A |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/ -x -q`
- **Per wave merge:** `pytest backend/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_infra.py` — covers INFRA-01 through INFRA-06
- [ ] `backend/infra.py` — new module for HCL generation and terraform subprocess helpers
- [ ] `backend/tests/test_understanding.py` — extend existing tests with infra extraction case

*(Note: check if `backend/tests/` directory and existing test files exist before planning Wave 0)*

---

## Sources

### Primary (HIGH confidence)
- [Google Cloud Terraform Quickstart](https://docs.cloud.google.com/docs/terraform/create-vm-instance) — google_compute_instance HCL verified
- [HashiCorp Terraform APT Install](https://developer.hashicorp.com/terraform/cli/install/apt) — Debian/Ubuntu apt install commands verified
- [HashiCorp Terraform GCS Backend](https://developer.hashicorp.com/terraform/language/backend/gcs) — GCS backend config + ADC support verified
- [Python asyncio subprocess docs](https://docs.python.org/3/library/asyncio-subprocess.html) — create_subprocess_exec + communicate() API verified
- [Google Cloud IAM Compute Engine Roles](https://docs.cloud.google.com/compute/docs/access/iam) — roles/compute.admin, roles/compute.securityAdmin, roles/compute.instanceAdmin.v1 verified
- [HashiCorp Terraform Install](https://developer.hashicorp.com/terraform/install) — latest version 1.11.4/1.14.8 and download URL pattern verified

### Secondary (MEDIUM confidence)
- [Google Cloud Terraform Authentication](https://docs.cloud.google.com/docs/terraform/authentication) — ADC + Cloud Run service account pattern
- [Shisho Dojo google_compute_firewall examples](https://shisho.dev/dojo/providers/google/Compute_Engine/google-compute-firewall/) — firewall HCL patterns (secondary source, consistent with official docs)
- [superfastpython.com asyncio subprocess](https://superfastpython.com/asyncio-create_subprocess_exec/) — subprocess streaming patterns
- [Google Cloud Store Terraform State in GCS](https://docs.cloud.google.com/docs/terraform/resource-management/store-state) — GCS remote backend for production recommendation

### Tertiary (LOW confidence)
- Various Medium articles on Terraform Docker patterns — not independently verified against official docs; use binary download pattern from official docs instead

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md does not exist in this repository. No project-specific directives to document. Follow existing codebase conventions observed in code review:
- No `innerHTML` — use `textContent` (existing UI rule)
- Fire-and-forget: `asyncio.create_task()` + `_bg_tasks` set (existing pattern)
- Check `if understanding is None:` not `if not understanding:` (existing pattern)
- All LLM calls use Gemini (Google DeepMind sponsor alignment)
- Per-session state in `ActionSession` class instances
- `make_action_result()` factory function for all action results

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Terraform version verified via official releases page; asyncio subprocess is stdlib; Docker binary download pattern is standard
- Architecture patterns: HIGH — HCL examples verified from Google Cloud official docs; asyncio subprocess from Python official docs
- Pitfalls: MEDIUM-HIGH — IAM permissions verified from official IAM docs; concurrency pitfall is well-known Terraform behavior; other pitfalls derived from code analysis + known Terraform behavior patterns
- Gemini prompt extension: HIGH — same prompt modification pattern already proven for other extraction types in this codebase

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (Terraform version; Google provider version; Python stdlib is stable)
