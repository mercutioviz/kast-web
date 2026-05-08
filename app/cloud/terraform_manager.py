"""
app/cloud/terraform_manager — Terraform subprocess wrapper for cloud provisioning.

Ported from kast/kast/scripts/terraform_manager.py with these adaptations:
  - kast.config imports replaced; Flask current_app.logger used for all logging.
  - Terraform state files live under /var/lib/kast-web2/cloud_state/<scan_id>/
    (owned by www-data, survives /opt git resets).
  - tfvars injected from the CloudCredential + ZapConfiguration.cloud_config
    rather than from kast's ZAP cloud config YAML.

Used exclusively by the per-provider CloudProvider.provision() implementations.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from flask import current_app


_CLOUD_STATE_BASE = "/var/lib/kast-web2/cloud_state"


class TerraformManager:
    """Wraps Terraform CLI commands for a single scan's infrastructure lifecycle.

    Args:
        provider: One of 'aws', 'azure', 'gcp'.
        scan_id: ID of the Scan being provisioned; used to isolate state files.
    """

    def __init__(self, provider: str, scan_id: int):
        self.provider = provider
        self.scan_id = scan_id
        self._last_stderr = ""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state_path(self) -> str:
        """Absolute path to this scan's Terraform state directory."""
        return os.path.join(_CLOUD_STATE_BASE, str(self.scan_id))

    @property
    def config_path(self) -> str:
        """Absolute path to the Terraform config directory for this provider."""
        return str(Path(__file__).parent / "terraform" / self.provider)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        current_app.logger.info("[TerraformManager scan=%s] %s", self.scan_id, msg)

    def _run(self, cmd: list, timeout: int = 600) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=self.state_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Create state directory, copy provider TF files, run terraform init.

        Raises:
            RuntimeError: if terraform init returns non-zero.
        """
        state_dir = Path(self.state_path)
        state_dir.mkdir(parents=True, exist_ok=True)

        config_dir = Path(self.config_path)
        for tf_file in config_dir.glob("*.tf"):
            dest = state_dir / tf_file.name
            if not dest.exists():
                shutil.copy2(tf_file, dest)

        self._log(f"Running terraform init in {self.state_path}")
        result = self._run(["terraform", "init", "-input=false"], timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"terraform init failed:\n{result.stderr}")
        self._log("terraform init succeeded")

    def apply(self, tfvars: dict) -> dict:
        """Write tfvars, run terraform apply, return output values.

        Args:
            tfvars: Terraform input variables dict.

        Returns:
            dict of output name → value from terraform output -json.

        Raises:
            RuntimeError: if apply returns non-zero.
        """
        state_dir = Path(self.state_path)
        tfvars_path = state_dir / "terraform.tfvars.json"

        with open(tfvars_path, "w") as f:
            json.dump(tfvars, f)
        os.chmod(tfvars_path, 0o600)

        self._log("Running terraform apply")
        result = self._run([
            "terraform", "apply",
            "-auto-approve",
            "-input=false",
            "-var-file=terraform.tfvars.json",
        ])
        self._last_stderr = result.stderr

        if result.returncode != 0:
            raise RuntimeError(f"terraform apply failed:\n{result.stderr}")

        self._log("terraform apply succeeded")
        return self.get_outputs()

    def destroy(self) -> None:
        """Run terraform destroy. No-op if state directory does not exist.

        Raises:
            RuntimeError: if destroy returns non-zero with a non-empty state file.
        """
        state_dir = Path(self.state_path)
        if not state_dir.exists():
            self._log("State directory absent; nothing to destroy")
            return

        state_file = state_dir / "terraform.tfstate"
        if not state_file.exists() or state_file.stat().st_size < 10:
            self._log("State file absent or empty; nothing to destroy")
            return

        self._log("Running terraform destroy")
        result = self._run([
            "terraform", "destroy",
            "-auto-approve",
            "-input=false",
        ])
        if result.returncode != 0:
            raise RuntimeError(f"terraform destroy failed:\n{result.stderr}")
        self._log("terraform destroy succeeded")

    def get_outputs(self) -> dict:
        """Return current terraform outputs, or {} if state does not exist."""
        state_dir = Path(self.state_path)
        if not state_dir.exists():
            return {}

        result = self._run(["terraform", "output", "-json"], timeout=30)
        if result.returncode != 0:
            self._log(f"terraform output failed: {result.stderr}")
            return {}

        try:
            raw = json.loads(result.stdout)
            return {k: v.get("value") for k, v in raw.items()}
        except (json.JSONDecodeError, AttributeError):
            return {}

    def is_capacity_error(self) -> bool:
        """Return True if the last apply/destroy failure was a spot capacity issue."""
        if not self._last_stderr:
            return False
        lower = self._last_stderr.lower()
        capacity_markers = [
            # AWS
            "insufficientinstancecapacity", "max spot instance count exceeded",
            "capacity-not-available", "spotmaxpricetoolow",
            # Azure
            "skunotavailable", "allocationfailed", "capacity not available",
            # GCP
            "zone_resource_pool_exhausted", "insufficient resources",
            "preemptible_quota_exceeded",
        ]
        return any(m in lower for m in capacity_markers)
