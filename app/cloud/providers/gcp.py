"""
app/cloud/providers/gcp — GCP Compute Engine ZAP provisioning.

Ported from kast/kast/scripts/zap_providers.py (CloudZapProvider GCP sections).
Uses TerraformManager with kast-web/app/cloud/terraform/gcp/ configs.

Credential keys expected in CloudCredential.credentials (decrypted):
    project_id
    service_account_json or credentials_json or credentials or service_account_key
      (the full JSON service-account key file as a string)
"""

import json
import os
import tempfile

from flask import current_app

from app.cloud.providers.base import CloudProvider
from app.cloud.terraform_manager import TerraformManager


_SA_KEY_ALIASES = [
    "service_account_json", "credentials_json", "credentials", "service_account_key",
]


def _resolve_sa_json(creds: dict) -> str:
    for alias in _SA_KEY_ALIASES:
        if creds.get(alias):
            return creds[alias]
    return ""


class GcpProvider(CloudProvider):
    """Provisions ZAP on GCP Compute Engine via Terraform."""

    def provision(self, credentials: dict, deployment_config: dict) -> dict:
        """Launch a GCP instance and wait for ZAP to become reachable.

        Args:
            credentials: {project_id, service_account_json}
            deployment_config: {
                scan_id,
                region (default us-central1),
                zone (default {region}-a),
                machine_type (default e2-medium),
                preemptible (default True),
                zap_docker_image (default zaproxy:stable),
                ssh_user (default ubuntu),
            }

        Returns:
            {instance_id, zap_url, zap_api_key, terraform_state_path}
        """
        from app.cloud.orchestrator import CloudProvisionError

        scan_id = deployment_config["scan_id"]
        tm = TerraformManager(provider="gcp", scan_id=scan_id)

        current_app.logger.info("[GcpProvider] provisioning scan %s", scan_id)

        tm.init()
        key_path, pub_key = self.generate_ssh_keypair(tm.state_path)
        zap_api_key = self.generate_zap_api_key()

        region = deployment_config.get("region", "us-central1")
        zone = deployment_config.get("zone", f"{region}-a")
        use_preemptible = deployment_config.get("preemptible", True)

        # Write service-account JSON to a temp file in state_path (chmod 600)
        sa_json_str = _resolve_sa_json(credentials)
        project_id = credentials.get("project_id", "")

        sa_key_file = os.path.join(tm.state_path, "gcp_sa_key.json")
        with open(sa_key_file, "w") as f:
            f.write(sa_json_str)
        os.chmod(sa_key_file, 0o600)

        tfvars = {
            "ssh_public_key": pub_key,
            "project_id": project_id,
            "region": region,
            "zone": zone,
            "machine_type": deployment_config.get("machine_type", "e2-medium"),
            "use_preemptible_instance": use_preemptible,
            "zap_docker_image": deployment_config.get(
                "zap_docker_image", "ghcr.io/zaproxy/zaproxy:stable"
            ),
            "gcp_credentials_file": sa_key_file,
        }

        try:
            outputs = tm.apply(tfvars)
        except RuntimeError as exc:
            if tm.is_capacity_error() and use_preemptible:
                current_app.logger.warning(
                    "[GcpProvider] preemptible capacity error; retrying on-demand"
                )
                tfvars["use_preemptible_instance"] = False
                try:
                    outputs = tm.apply(tfvars)
                except RuntimeError as exc2:
                    raise CloudProvisionError(
                        f"GCP on-demand apply failed: {exc2}"
                    ) from exc2
            else:
                raise CloudProvisionError(f"GCP apply failed: {exc}") from exc

        instance_ip = outputs.get("public_ip")
        instance_id = outputs.get("instance_id", instance_ip or "unknown")

        if not instance_ip:
            raise CloudProvisionError("GCP Terraform outputs missing 'public_ip'")

        ssh_user = deployment_config.get("ssh_user", "ubuntu")
        zap_url = self.bootstrap_zap(
            instance_ip=instance_ip,
            key_path=key_path,
            ssh_user=ssh_user,
            zap_api_key=zap_api_key,
            state_path=tm.state_path,
        )

        return {
            "instance_id": instance_id,
            "zap_url": zap_url,
            "zap_api_key": zap_api_key,
            "terraform_state_path": tm.state_path,
        }

    def get_zap_endpoint(self, instance_id: str, state_path: str) -> str:
        from app.cloud.orchestrator import CloudProvisionError

        scan_id = _scan_id_from_state_path(state_path)
        tm = TerraformManager(provider="gcp", scan_id=scan_id)
        outputs = tm.get_outputs()
        ip = outputs.get("public_ip")
        if not ip:
            raise CloudProvisionError("Cannot find public_ip in Terraform state")
        return f"http://{ip}:8080"

    def teardown(self, instance_id: str, state_path: str) -> None:
        from app.cloud.orchestrator import CloudTeardownError

        scan_id = _scan_id_from_state_path(state_path)
        tm = TerraformManager(provider="gcp", scan_id=scan_id)
        try:
            tm.destroy()
        except RuntimeError as exc:
            raise CloudTeardownError(f"GCP teardown failed: {exc}") from exc

    def get_status(self, instance_id: str) -> str:
        """Return instance status using gcloud CLI if available, else 'unknown'."""
        import subprocess
        try:
            result = subprocess.run(
                [
                    "gcloud", "compute", "instances", "describe",
                    instance_id,
                    "--format=value(status)",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                state = result.stdout.strip().upper()
                if state == "RUNNING":
                    return "running"
                if state in ("STOPPED", "TERMINATED"):
                    return "terminated"
        except Exception:
            pass
        return "unknown"


def _scan_id_from_state_path(state_path: str) -> int:
    return int(state_path.rstrip("/").rsplit("/", 1)[-1])
