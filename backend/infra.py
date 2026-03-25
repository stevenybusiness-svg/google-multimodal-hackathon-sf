import asyncio
import logging
import os
import uuid

from backend.contracts import InfraRequest, make_action_result

logger = logging.getLogger(__name__)

_tf_lock = asyncio.Lock()

TERRAFORM_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "terraform")


def generate_hcl(req: InfraRequest, project: str) -> tuple[str, str]:
    """Generate Terraform HCL resource blocks from a structured InfraRequest.

    Returns (hcl_content, name_slug) where hcl_content contains only resource blocks
    (provider block lives in the static provider.tf), and name_slug is the generated
    resource name with a UUID suffix to avoid naming collisions across sessions.
    """
    name_slug = f"{req.get('name', 'vm')}-{uuid.uuid4().hex[:6]}"
    machine_type = req.get("machine_type", "e2-medium")
    zone = req.get("zone", "us-central1-a")
    disk_size_gb = req.get("disk_size_gb", 20)

    hcl = f"""resource "google_compute_instance" "{name_slug}" {{
  name         = "{name_slug}"
  machine_type = "{machine_type}"
  zone         = "{zone}"
  tags         = ["{name_slug}"]

  boot_disk {{
    initialize_params {{
      image = "ubuntu-minimal-2210-kinetic-amd64-v20230126"
      size  = {disk_size_gb}
    }}
  }}

  network_interface {{
    network = "default"
    access_config {{}}
  }}
}}
"""

    ports = req.get("ports", [])
    if ports:
        ports_str = ", ".join(f'"{p}"' for p in ports)
        hcl += f"""
resource "google_compute_firewall" "{name_slug}-fw" {{
  name    = "{name_slug}-fw"
  network = "default"

  allow {{
    protocol = "tcp"
    ports    = [{ports_str}]
  }}

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["{name_slug}"]
}}
"""

    return hcl, name_slug


async def _run_terraform(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a terraform command non-blocking via asyncio subprocess.

    Returns (returncode, stdout, stderr).
    """
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


async def provision_infrastructure(req: InfraRequest, on_action=None) -> dict:
    """Provision a GCP Compute Engine VM (and optional firewall) from a voice-extracted InfraRequest.

    Generates HCL from structured fields, writes to terraform/resources.tf, then
    runs terraform init + apply. Serialized by _tf_lock to avoid concurrent state
    file corruption. Emits a pending action card before apply and a success/failure
    card after.
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not project:
        logger.error("GOOGLE_CLOUD_PROJECT not set — cannot provision infrastructure")
        return make_action_result(
            "infra",
            {"name": req.get("name", "unknown"), "status": "failed"},
            "failed",
            error="GOOGLE_CLOUD_PROJECT env var not set",
        )

    try:
        logger.info("Generating HCL for infrastructure request: %s", req.get("name", "vm"))
        hcl_content, name_slug = generate_hcl(req, project)

        pending_card = make_action_result(
            "infra",
            {
                "name": name_slug,
                "machine_type": req.get("machine_type", "e2-medium"),
                "zone": req.get("zone", "us-central1-a"),
                "status": "provisioning",
            },
            "sent",
        )
        if on_action:
            await on_action(pending_card)

        async with _tf_lock:
            resources_tf = os.path.join(TERRAFORM_DIR, "resources.tf")
            logger.info("Writing HCL to %s (resource: %s)", resources_tf, name_slug)
            with open(resources_tf, "w") as f:
                f.write(hcl_content)

            logger.info("Running terraform init in %s", TERRAFORM_DIR)
            rc, stdout, stderr = await _run_terraform(
                ["terraform", "init", "-no-color"], TERRAFORM_DIR
            )
            if rc != 0:
                logger.error("terraform init failed (rc=%d): %s", rc, stderr[:300])
                return make_action_result(
                    "infra",
                    {"name": name_slug, "status": "failed"},
                    "failed",
                    error=f"terraform init failed: {stderr[:300]}",
                )

            logger.info("Running terraform apply for %s", name_slug)
            rc, stdout, stderr = await _run_terraform(
                ["terraform", "apply", "-auto-approve", "-no-color"], TERRAFORM_DIR
            )
            if rc != 0:
                logger.error("terraform apply failed (rc=%d): %s", rc, stderr[:300])
                return make_action_result(
                    "infra",
                    {"name": name_slug, "status": "failed"},
                    "failed",
                    error=f"terraform apply failed: {stderr[:300]}",
                )

        logger.info("Infrastructure provisioned successfully: %s", name_slug)
        return make_action_result(
            "infra",
            {
                "name": name_slug,
                "machine_type": req.get("machine_type", "e2-medium"),
                "zone": req.get("zone", "us-central1-a"),
                "status": "provisioned",
            },
            "sent",
        )

    except Exception as exc:
        logger.error("provision_infrastructure failed: %s", exc)
        return make_action_result(
            "infra",
            {"name": req.get("name", "unknown"), "status": "failed"},
            "failed",
            error=str(exc),
        )
