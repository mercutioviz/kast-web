"""
app/cloud/providers/azure — Azure VM ZAP provisioning.

Ported from kast/kast/scripts/zap_providers.py (Azure sections).
Uses TerraformManager with kast-web/app/cloud/terraform/azure/ configs.

Credential keys expected in CloudCredential.credentials_encrypted:
    subscription_id, tenant_id, client_id, client_secret
"""

from app.cloud.providers.base import CloudProvider


class AzureProvider(CloudProvider):
    """Provisions ZAP on Azure VM via Terraform."""

    def provision(self, credentials: dict, deployment_config: dict) -> dict:
        """Launch an Azure VM and wait for ZAP to become reachable.

        Args:
            credentials: {subscription_id, tenant_id, client_id, client_secret}
            deployment_config: {region, vm_size, [resource_group_prefix]}

        Returns:
            {instance_id, zap_url, zap_api_key, terraform_state_path}

        Raises:
            CloudProvisionError
        """
        raise NotImplementedError("Will be implemented in D2 (Azure provider port)")

    def get_zap_endpoint(self, instance_id: str, state_path: str) -> str:
        raise NotImplementedError("Will be implemented in D2 (Azure provider port)")

    def teardown(self, instance_id: str, state_path: str) -> None:
        raise NotImplementedError("Will be implemented in D2 (Azure provider port)")

    def get_status(self, instance_id: str) -> str:
        raise NotImplementedError("Will be implemented in D2 (Azure provider port)")
