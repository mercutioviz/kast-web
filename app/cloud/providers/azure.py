"""
app/cloud/providers/azure — Azure VM ZAP provisioning.

Ported from kast/kast/scripts/zap_providers.py (CloudZapProvider Azure sections).
Uses TerraformManager with kast-web/app/cloud/terraform/azure/ configs.

Credential keys expected in CloudCredential.credentials (decrypted):
    subscription_id, tenant_id, client_id, client_secret
"""

from flask import current_app

from app.cloud.providers.base import CloudProvider
from app.cloud.terraform_manager import TerraformManager


class AzureProvider(CloudProvider):
    """Provisions ZAP on Azure VM via Terraform."""

    def provision(self, credentials: dict, deployment_config: dict) -> dict:
        """Launch an Azure VM and wait for ZAP to become reachable.

        Args:
            credentials: {subscription_id, tenant_id, client_id, client_secret}
            deployment_config: {
                scan_id,
                region / location (default eastus),
                vm_size (default Standard_B2s),
                spot_enabled (default True),
                spot_max_price (default -1),
                zap_docker_image (default zaproxy:stable),
                ssh_user (default azureuser),
                resource_group_prefix (optional),
            }

        Returns:
            {instance_id, zap_url, zap_api_key, terraform_state_path}
        """
        from app.cloud.orchestrator import CloudProvisionError

        scan_id = deployment_config["scan_id"]
        tm = TerraformManager(provider="azure", scan_id=scan_id)

        current_app.logger.info("[AzureProvider] provisioning scan %s", scan_id)

        tm.init()
        key_path, pub_key = self.generate_ssh_keypair(tm.state_path)
        zap_api_key = self.generate_zap_api_key()

        location = (
            deployment_config.get("location")
            or deployment_config.get("region", "eastus")
        )
        use_spot = deployment_config.get("spot_enabled", True)

        tfvars = {
            "ssh_public_key": pub_key,
            "location": location,
            "vm_size": deployment_config.get("vm_size", "Standard_B2s"),
            "use_spot_instance": use_spot,
            "spot_max_price": deployment_config.get("spot_max_price", -1),
            "zap_docker_image": deployment_config.get(
                "zap_docker_image", "ghcr.io/zaproxy/zaproxy:stable"
            ),
            "azure_subscription_id": credentials.get("subscription_id", ""),
            "azure_tenant_id": credentials.get("tenant_id", ""),
            "azure_client_id": credentials.get("client_id", ""),
            "azure_client_secret": credentials.get("client_secret", ""),
        }
        if deployment_config.get("resource_group_prefix"):
            tfvars["resource_group_prefix"] = deployment_config["resource_group_prefix"]

        try:
            outputs = tm.apply(tfvars)
        except RuntimeError as exc:
            if tm.is_capacity_error() and use_spot:
                current_app.logger.warning(
                    "[AzureProvider] spot capacity error; retrying on-demand"
                )
                tfvars["use_spot_instance"] = False
                try:
                    outputs = tm.apply(tfvars)
                except RuntimeError as exc2:
                    raise CloudProvisionError(
                        f"Azure on-demand apply failed: {exc2}"
                    ) from exc2
            else:
                raise CloudProvisionError(f"Azure apply failed: {exc}") from exc

        instance_ip = outputs.get("public_ip")
        instance_id = outputs.get("instance_id", instance_ip or "unknown")

        if not instance_ip:
            raise CloudProvisionError("Azure Terraform outputs missing 'public_ip'")

        ssh_user = deployment_config.get("ssh_user", "azureuser")
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
        tm = TerraformManager(provider="azure", scan_id=scan_id)
        outputs = tm.get_outputs()
        ip = outputs.get("public_ip")
        if not ip:
            raise CloudProvisionError("Cannot find public_ip in Terraform state")
        return f"http://{ip}:8080"

    def teardown(self, instance_id: str, state_path: str) -> None:
        from app.cloud.orchestrator import CloudTeardownError

        scan_id = _scan_id_from_state_path(state_path)
        tm = TerraformManager(provider="azure", scan_id=scan_id)
        try:
            tm.destroy()
        except RuntimeError as exc:
            raise CloudTeardownError(f"Azure teardown failed: {exc}") from exc

    def get_status(self, instance_id: str) -> str:
        """Return VM status using az CLI if available, else 'unknown'."""
        import subprocess
        try:
            result = subprocess.run(
                [
                    "az", "vm", "show",
                    "--ids", instance_id,
                    "--query", "powerState",
                    "-o", "tsv",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                state = result.stdout.strip().lower()
                if "running" in state:
                    return "running"
                if "stopped" in state or "deallocated" in state:
                    return "stopped"
        except Exception:
            pass
        return "unknown"


def _scan_id_from_state_path(state_path: str) -> int:
    return int(state_path.rstrip("/").rsplit("/", 1)[-1])
