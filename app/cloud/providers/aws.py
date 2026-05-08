"""
app/cloud/providers/aws — AWS EC2 ZAP provisioning.

Ported from kast/kast/scripts/zap_providers.py (CloudZapProvider AWS sections).
Uses TerraformManager with kast-web/app/cloud/terraform/aws/ configs.

Credential keys expected in CloudCredential.credentials (decrypted):
    access_key_id or aws_access_key_id or access_key
    secret_access_key or aws_secret_access_key or secret_key
    session_token (optional)
"""

from flask import current_app

from app.cloud.providers.base import CloudProvider
from app.cloud.terraform_manager import TerraformManager


_CRED_ALIASES = {
    "access_key_id": ["access_key_id", "aws_access_key_id", "access_key"],
    "secret_access_key": ["secret_access_key", "aws_secret_access_key", "secret_key"],
}


def _resolve_cred(creds: dict, canonical: str) -> str:
    for alias in _CRED_ALIASES.get(canonical, [canonical]):
        if creds.get(alias):
            return creds[alias]
    return ""


class AwsProvider(CloudProvider):
    """Provisions ZAP on AWS EC2 via Terraform."""

    def provision(self, credentials: dict, deployment_config: dict) -> dict:
        """Launch an EC2 instance and wait for ZAP to become reachable.

        Args:
            credentials: {access_key_id, secret_access_key, [session_token]}
            deployment_config: {
                scan_id,
                region (default us-east-1),
                instance_type (default t3.medium),
                spot_enabled (default True),
                spot_max_price (default '0.05'),
                zap_docker_image (default zaproxy:stable),
                ssh_user (default ubuntu),
                ami_id (optional, uses TF default if absent),
                allowed_cidrs (optional list),
            }

        Returns:
            {instance_id, zap_url, zap_api_key, terraform_state_path}
        """
        from app.cloud.orchestrator import CloudProvisionError

        scan_id = deployment_config["scan_id"]
        tm = TerraformManager(provider="aws", scan_id=scan_id)

        current_app.logger.info("[AwsProvider] provisioning scan %s", scan_id)

        # Generate ephemeral SSH keypair
        tm.init()  # creates state_path
        key_path, pub_key = self.generate_ssh_keypair(tm.state_path)
        zap_api_key = self.generate_zap_api_key()

        # Build Terraform variables
        tfvars = {
            "ssh_public_key": pub_key,
            "region": deployment_config.get("region", "us-east-1"),
            "instance_type": deployment_config.get("instance_type", "t3.medium"),
            "use_spot_instance": deployment_config.get("spot_enabled", True),
            "spot_max_price": str(deployment_config.get("spot_max_price", "0.05")),
            "zap_docker_image": deployment_config.get(
                "zap_docker_image", "ghcr.io/zaproxy/zaproxy:stable"
            ),
            "aws_access_key_id": _resolve_cred(credentials, "access_key_id"),
            "aws_secret_access_key": _resolve_cred(credentials, "secret_access_key"),
        }
        if credentials.get("session_token"):
            tfvars["aws_session_token"] = credentials["session_token"]
        if deployment_config.get("ami_id"):
            tfvars["ami_id"] = deployment_config["ami_id"]
        if deployment_config.get("allowed_cidrs"):
            tfvars["allowed_cidrs"] = deployment_config["allowed_cidrs"]

        try:
            outputs = tm.apply(tfvars)
        except RuntimeError as exc:
            if tm.is_capacity_error() and deployment_config.get("spot_enabled", True):
                current_app.logger.warning(
                    "[AwsProvider] spot capacity error; retrying on-demand"
                )
                tfvars["use_spot_instance"] = False
                try:
                    outputs = tm.apply(tfvars)
                except RuntimeError as exc2:
                    raise CloudProvisionError(f"AWS on-demand apply failed: {exc2}") from exc2
            else:
                raise CloudProvisionError(f"AWS apply failed: {exc}") from exc

        instance_ip = outputs.get("public_ip")
        instance_id = outputs.get("instance_id", instance_ip or "unknown")

        if not instance_ip:
            raise CloudProvisionError("AWS Terraform outputs missing 'public_ip'")

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
        """Read ZAP URL from Terraform outputs stored in state_path."""
        from app.cloud.orchestrator import CloudProvisionError

        scan_id = _scan_id_from_state_path(state_path)
        tm = TerraformManager(provider="aws", scan_id=scan_id)
        outputs = tm.get_outputs()
        ip = outputs.get("public_ip")
        if not ip:
            raise CloudProvisionError("Cannot find public_ip in Terraform state")
        return f"http://{ip}:8080"

    def teardown(self, instance_id: str, state_path: str) -> None:
        """Destroy the EC2 instance via terraform destroy."""
        from app.cloud.orchestrator import CloudTeardownError

        scan_id = _scan_id_from_state_path(state_path)
        tm = TerraformManager(provider="aws", scan_id=scan_id)
        try:
            tm.destroy()
        except RuntimeError as exc:
            raise CloudTeardownError(f"AWS teardown failed: {exc}") from exc

    def get_status(self, instance_id: str) -> str:
        """Return instance status using AWS CLI if available, else 'unknown'."""
        import subprocess
        try:
            result = subprocess.run(
                [
                    "aws", "ec2", "describe-instances",
                    "--instance-ids", instance_id,
                    "--query", "Reservations[0].Instances[0].State.Name",
                    "--output", "text",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                state = result.stdout.strip().lower()
                if state == "running":
                    return "running"
                if state in ("stopped", "stopping"):
                    return "stopped"
                if state in ("terminated", "shutting-down"):
                    return "terminated"
        except Exception:
            pass
        return "unknown"


def _scan_id_from_state_path(state_path: str) -> int:
    """Extract scan_id integer from a state_path like .../cloud_state/<scan_id>."""
    return int(state_path.rstrip("/").rsplit("/", 1)[-1])
