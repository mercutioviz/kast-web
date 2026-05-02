"""
app/cloud/providers/aws — AWS EC2 ZAP provisioning.

Ported from kast/kast/scripts/zap_providers.py (AWS sections).
Uses TerraformManager with kast-web/app/cloud/terraform/aws/ configs.

Credential keys expected in CloudCredential.credentials_encrypted:
    access_key_id, secret_access_key, [session_token]
"""

from app.cloud.providers.base import CloudProvider


class AwsProvider(CloudProvider):
    """Provisions ZAP on AWS EC2 via Terraform."""

    def provision(self, credentials: dict, deployment_config: dict) -> dict:
        """Launch an EC2 instance and wait for ZAP to become reachable.

        Args:
            credentials: {access_key_id, secret_access_key, [session_token]}
            deployment_config: {region, instance_type, ami_id, spot_enabled,
                spot_max_price, allowed_cidrs}

        Returns:
            {instance_id, zap_url, zap_api_key, terraform_state_path}

        Raises:
            CloudProvisionError
        """
        raise NotImplementedError("Will be implemented in D2 (AWS provider port)")

    def get_zap_endpoint(self, instance_id: str, state_path: str) -> str:
        raise NotImplementedError("Will be implemented in D2 (AWS provider port)")

    def teardown(self, instance_id: str, state_path: str) -> None:
        raise NotImplementedError("Will be implemented in D2 (AWS provider port)")

    def get_status(self, instance_id: str) -> str:
        raise NotImplementedError("Will be implemented in D2 (AWS provider port)")
