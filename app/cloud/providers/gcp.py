"""
app/cloud/providers/gcp — GCP Compute Engine ZAP provisioning.

Ported from kast/kast/scripts/zap_providers.py (GCP sections).
Uses TerraformManager with kast-web/app/cloud/terraform/gcp/ configs.

Credential keys expected in CloudCredential.credentials_encrypted:
    project_id, service_account_json (full JSON key file contents as string)
"""

from app.cloud.providers.base import CloudProvider


class GcpProvider(CloudProvider):
    """Provisions ZAP on GCP Compute Engine via Terraform."""

    def provision(self, credentials: dict, deployment_config: dict) -> dict:
        """Launch a GCP instance and wait for ZAP to become reachable.

        Args:
            credentials: {project_id, service_account_json}
            deployment_config: {region, zone, machine_type, [preemptible]}

        Returns:
            {instance_id, zap_url, zap_api_key, terraform_state_path}

        Raises:
            CloudProvisionError
        """
        raise NotImplementedError("Will be implemented in D2 (GCP provider port)")

    def get_zap_endpoint(self, instance_id: str, state_path: str) -> str:
        raise NotImplementedError("Will be implemented in D2 (GCP provider port)")

    def teardown(self, instance_id: str, state_path: str) -> None:
        raise NotImplementedError("Will be implemented in D2 (GCP provider port)")

    def get_status(self, instance_id: str) -> str:
        raise NotImplementedError("Will be implemented in D2 (GCP provider port)")
