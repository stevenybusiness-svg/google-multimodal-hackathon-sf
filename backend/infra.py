import asyncio
import logging
import os
import uuid

from backend.contracts import ContainerRequest, InfraRequest, make_action_result

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

        # Set TF_VAR_project_id so terraform provider.tf picks up the project
        os.environ["TF_VAR_project_id"] = project
        logger.info("Provisioning infra: name=%s, project=%s, terraform_dir=%s",
                    req.get("name", "?"), project, TERRAFORM_DIR)

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


def generate_container_hcl(req: ContainerRequest, project: str) -> tuple[str, str]:
    """Generate Terraform HCL for a Cloud Run v2 service from a ContainerRequest.

    Returns (hcl_content, name_slug).
    """
    name_slug = f"{req.get('name', 'svc')}-{uuid.uuid4().hex[:6]}"
    region = req.get("region", "us-central1")
    image = req.get("image", f"us-docker.pkg.dev/cloudrun/container/hello")
    port = req.get("port", 8080)
    memory = req.get("memory", "512Mi")
    # Cloud Run requires >= 512Mi with cpu always allocated
    if memory.endswith("Mi"):
        mem_val = int(memory[:-2])
        if mem_val < 512:
            memory = "512Mi"
    cpu = req.get("cpu", "1")
    min_instances = req.get("min_instances", 0)
    max_instances = req.get("max_instances", 1)

    hcl = f"""resource "google_cloud_run_v2_service" "{name_slug}" {{
  name                = "{name_slug}"
  location            = "{region}"
  deletion_protection = false

  template {{
    scaling {{
      min_instance_count = {min_instances}
      max_instance_count = {max_instances}
    }}

    containers {{
      image = "{image}"

      ports {{
        container_port = {port}
      }}

      resources {{
        limits = {{
          memory = "{memory}"
          cpu    = "{cpu}"
        }}
      }}
    }}
  }}
}}

resource "google_cloud_run_v2_service_iam_member" "{name_slug}-public" {{
  project  = google_cloud_run_v2_service.{name_slug}.project
  location = google_cloud_run_v2_service.{name_slug}.location
  name     = google_cloud_run_v2_service.{name_slug}.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}}
"""
    return hcl, name_slug


async def provision_container(req: ContainerRequest, on_action=None) -> dict:
    """Provision a Cloud Run container service from a ContainerRequest.

    Generates HCL, writes to terraform/containers.tf, then runs terraform init + apply.
    Serialized by _tf_lock. Emits pending/success/failure action cards.
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not project:
        logger.error("GOOGLE_CLOUD_PROJECT not set — cannot provision container")
        return make_action_result(
            "infra",
            {"name": req.get("name", "unknown"), "resource_type": "container", "status": "failed"},
            "failed",
            error="GOOGLE_CLOUD_PROJECT env var not set",
        )

    try:
        logger.info("Generating container HCL for: %s", req.get("name", "svc"))
        hcl_content, name_slug = generate_container_hcl(req, project)

        pending_card = make_action_result(
            "infra",
            {
                "name": name_slug,
                "resource_type": "container",
                "image": req.get("image", "hello"),
                "region": req.get("region", "us-central1"),
                "status": "provisioning",
            },
            "sent",
        )
        if on_action:
            await on_action(pending_card)

        os.environ["TF_VAR_project_id"] = project
        logger.info("Provisioning container: name=%s, project=%s", name_slug, project)

        async with _tf_lock:
            containers_tf = os.path.join(TERRAFORM_DIR, "containers.tf")
            # Append to containers.tf so multiple containers coexist
            mode = "a" if os.path.exists(containers_tf) else "w"
            logger.info("Writing container HCL to %s (mode=%s, resource: %s)", containers_tf, mode, name_slug)
            with open(containers_tf, mode) as f:
                f.write(hcl_content)

            logger.info("Running terraform init in %s", TERRAFORM_DIR)
            rc, stdout, stderr = await _run_terraform(
                ["terraform", "init", "-no-color"], TERRAFORM_DIR
            )
            if rc != 0:
                logger.error("terraform init failed (rc=%d): %s", rc, stderr[:300])
                return make_action_result(
                    "infra",
                    {"name": name_slug, "resource_type": "container", "status": "failed"},
                    "failed",
                    error=f"terraform init failed: {stderr[:300]}",
                )

            logger.info("Running terraform apply for container %s", name_slug)
            rc, stdout, stderr = await _run_terraform(
                ["terraform", "apply", "-auto-approve", "-no-color"], TERRAFORM_DIR
            )
            if rc != 0:
                logger.error("terraform apply failed (rc=%d): %s", rc, stderr[:300])
                return make_action_result(
                    "infra",
                    {"name": name_slug, "resource_type": "container", "status": "failed"},
                    "failed",
                    error=f"terraform apply failed: {stderr[:300]}",
                )

        logger.info("Container provisioned successfully: %s", name_slug)
        return make_action_result(
            "infra",
            {
                "name": name_slug,
                "resource_type": "container",
                "image": req.get("image", "hello"),
                "region": req.get("region", "us-central1"),
                "status": "provisioned",
            },
            "sent",
        )

    except Exception as exc:
        logger.error("provision_container failed: %s", exc)
        return make_action_result(
            "infra",
            {"name": req.get("name", "unknown"), "resource_type": "container", "status": "failed"},
            "failed",
            error=str(exc),
        )
