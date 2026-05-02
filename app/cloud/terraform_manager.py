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

import os
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

    @property
    def state_path(self) -> str:
        """Absolute path to this scan's Terraform state directory.

        Returns:
            '/var/lib/kast-web2/cloud_state/<scan_id>/'
        """
        return os.path.join(_CLOUD_STATE_BASE, str(self.scan_id))

    @property
    def config_path(self) -> str:
        """Absolute path to the Terraform config directory for this provider.

        Returns:
            Path to app/cloud/terraform/<provider>/ inside the kast-web install.
        """
        raise NotImplementedError("Will be implemented in D2 (terraform_manager port)")

    def init(self) -> None:
        """Run 'terraform init' in the provider config directory.

        Creates self.state_path if it does not exist, copies provider
        Terraform configs there, then runs terraform init.

        Raises:
            RuntimeError: if 'terraform init' returns non-zero.
        """
        raise NotImplementedError("Will be implemented in D2 (terraform_manager port)")

    def apply(self, tfvars: dict) -> dict:
        """Run 'terraform apply' with the given variable values.

        Writes a terraform.tfvars.json from tfvars, then runs:
            terraform apply -auto-approve -var-file=terraform.tfvars.json

        Args:
            tfvars: dict of Terraform input variable names → values.
                Sensitive values (access keys, passwords) are written to the
                tfvars file and the file is chmod 600 before apply.

        Returns:
            dict of Terraform output values (from 'terraform output -json').

        Raises:
            RuntimeError: if apply returns non-zero.
        """
        raise NotImplementedError("Will be implemented in D2 (terraform_manager port)")

    def destroy(self) -> None:
        """Run 'terraform destroy' to tear down all provisioned resources.

        Idempotent: safe to call if apply never completed (no state file = no-op).

        Raises:
            RuntimeError: if destroy returns non-zero and there are known live
                resources (i.e. the state file is non-empty).
        """
        raise NotImplementedError("Will be implemented in D2 (terraform_manager port)")

    def get_outputs(self) -> dict:
        """Return current Terraform outputs from the state file.

        Returns:
            dict of output name → value, or {} if state file does not exist.
        """
        raise NotImplementedError("Will be implemented in D2 (terraform_manager port)")
