"""
app/cloud/providers/base — abstract base class for all cloud providers.

Concrete implementations live in aws.py, azure.py, gcp.py.
The orchestrator calls only this interface; provider-specific SDK code
stays inside the concrete classes.
"""

from abc import ABC, abstractmethod


class CloudProvider(ABC):
    """Abstract base for AWS, Azure, and GCP ZAP provisioning.

    Each provider is responsible for:
    - Running Terraform to launch a VM with ZAP pre-installed.
    - Reporting the ZAP endpoint URL and API key once the VM is live.
    - Tearing down the VM (and all associated resources) via Terraform destroy.
    - Reporting the live status of a running instance.

    Credentials and deployment config are passed explicitly on each call
    (decrypted by the orchestrator from CloudCredential and ZapConfiguration)
    so providers never touch the database directly.
    """

    @abstractmethod
    def provision(self, credentials: dict, deployment_config: dict) -> dict:
        """Launch a cloud VM and wait for ZAP to become reachable.

        Args:
            credentials: Decrypted credential dict from CloudCredential.
                AWS: {access_key_id, secret_access_key, [session_token]}
                Azure: {subscription_id, tenant_id, client_id, client_secret}
                GCP: {project_id, service_account_json}
            deployment_config: Deployment parameters from ZapConfiguration.cloud_config.
                All providers: {region, instance_type (or vm_size/machine_type)}
                AWS extras: {ami_id, spot_enabled, spot_max_price, allowed_cidrs}
                Azure extras: {resource_group_prefix, vm_size}
                GCP extras: {zone, machine_type, preemptible}

        Returns:
            dict with keys: instance_id, zap_url, zap_api_key, terraform_state_path.

        Raises:
            CloudProvisionError: if provisioning fails at any stage.
        """
        raise NotImplementedError("Will be implemented per-provider in D2")

    @abstractmethod
    def get_zap_endpoint(self, instance_id: str, state_path: str) -> str:
        """Return the current ZAP HTTP endpoint for a running instance.

        Args:
            instance_id: Cloud-side identifier returned by provision().
            state_path: Path to the Terraform state directory for this scan.

        Returns:
            URL string, e.g. 'http://1.2.3.4:8080'.

        Raises:
            CloudProvisionError: if the instance is not reachable.
        """
        raise NotImplementedError("Will be implemented per-provider in D2")

    @abstractmethod
    def teardown(self, instance_id: str, state_path: str) -> None:
        """Destroy cloud infrastructure for a scan.

        Idempotent: safe to call if provisioning never fully completed.

        Args:
            instance_id: Cloud-side identifier returned by provision().
            state_path: Path to the Terraform state directory for this scan.

        Raises:
            CloudTeardownError: if teardown cannot be completed. The caller
                should mark the resource as orphaned rather than retrying.
        """
        raise NotImplementedError("Will be implemented per-provider in D2")

    @abstractmethod
    def get_status(self, instance_id: str) -> str:
        """Return a one-word status of a cloud instance.

        Args:
            instance_id: Cloud-side identifier.

        Returns:
            One of: 'running', 'stopped', 'terminated', 'unknown'.
        """
        raise NotImplementedError("Will be implemented per-provider in D2")
