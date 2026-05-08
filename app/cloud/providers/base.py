"""
app/cloud/providers/base — abstract base class for all cloud providers.

Concrete implementations live in aws.py, azure.py, gcp.py.
The orchestrator calls only this interface; provider-specific SDK code
stays inside the concrete classes.
"""

import os
import secrets
import time
from abc import ABC, abstractmethod
from pathlib import Path

from flask import current_app


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

    # ------------------------------------------------------------------
    # Shared helpers used by all concrete providers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_ssh_keypair(state_path: str) -> tuple[str, str]:
        """Generate an ephemeral RSA keypair and write the private key to state_path.

        Args:
            state_path: Directory where the private key file will be written.

        Returns:
            Tuple of (private_key_path, public_key_openssh_string).
        """
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_openssh = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        )

        key_path = Path(state_path) / "zap_key.pem"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(private_pem)
        os.chmod(key_path, 0o600)

        return str(key_path), public_openssh.decode("utf-8")

    @staticmethod
    def generate_zap_api_key() -> str:
        """Return a 32-character random hex string for use as a ZAP API key."""
        return secrets.token_hex(16)

    @staticmethod
    def bootstrap_zap(instance_ip: str, key_path: str, ssh_user: str,
                      zap_api_key: str, state_path: str,
                      docker_image: str = "ghcr.io/zaproxy/zaproxy:stable",
                      ssh_timeout: int = 300,
                      zap_timeout: int = 300) -> str:
        """Wait for SSH, start ZAP container, wait for ZAP API to respond.

        Args:
            instance_ip: Public IP of the provisioned VM.
            key_path: Path to SSH private key.
            ssh_user: SSH username.
            zap_api_key: API key to configure ZAP with.
            state_path: Terraform state directory (used to derive key_path if needed).
            docker_image: ZAP Docker image tag.
            ssh_timeout: Seconds to wait for SSH port 22 to open.
            zap_timeout: Seconds to wait for ZAP HTTP port 8080 to open.

        Returns:
            ZAP base URL, e.g. 'http://1.2.3.4:8080'.

        Raises:
            RuntimeError: if any bootstrap step fails.
        """
        from app.cloud.ssh_executor import SshExecutor
        from app.cloud.zap_api_client import ZapApiClient

        logger = current_app.logger

        # Wait for SSH port
        exe = SshExecutor(host=instance_ip, key_path=key_path, user=ssh_user)
        logger.info("[bootstrap] waiting for SSH on %s", instance_ip)
        exe.wait_for_port(22, timeout=ssh_timeout)

        # Retry SSH connect (instance may accept TCP before sshd is ready)
        connected = False
        for attempt in range(1, 11):
            try:
                exe.connect(timeout=30)
                connected = True
                break
            except ConnectionError as exc:
                logger.info("[bootstrap] SSH attempt %d failed: %s", attempt, exc)
                if attempt < 10:
                    time.sleep(15)
        if not connected:
            raise RuntimeError(f"Could not SSH to {instance_ip} after 10 attempts")

        try:
            # Wait for Docker to be installed (user-data script runs on boot)
            logger.info("[bootstrap] waiting for Docker on %s", instance_ip)
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                rc, stdout, _ = exe.run_command("docker --version", timeout=10)
                if rc == 0:
                    logger.info("[bootstrap] Docker ready: %s", stdout.strip())
                    break
                time.sleep(10)
            else:
                raise RuntimeError("Docker did not become ready within 300s")

            # Create ZAP working directories
            exe.run_command("mkdir -p /home/{u}/zap_reports".format(u=ssh_user))

            # Start ZAP container
            zap_cmd = (
                "docker run -d --name zap-scanner "
                "-p 8080:8080 "
                "-v /home/{u}/zap_reports:/zap/reports "
                "{img} "
                "zap.sh -daemon -port 8080 "
                "-config api.key={key} "
                "-config api.addrs.addr.name=.* "
                "-config api.addrs.addr.regex=true "
                "-config api.filexfer=true"
            ).format(u=ssh_user, img=docker_image, key=zap_api_key)

            rc, stdout, stderr = exe.run_command(zap_cmd, timeout=60)
            if rc != 0:
                raise RuntimeError(f"Failed to start ZAP container: {stderr}")
            logger.info("[bootstrap] ZAP container started")
        finally:
            exe.close()

        # Wait for ZAP API to respond
        zap_url = f"http://{instance_ip}:8080"
        logger.info("[bootstrap] waiting for ZAP API at %s", zap_url)
        zap_client = ZapApiClient(url=zap_url, api_key=zap_api_key)
        zap_client.wait_until_ready(timeout=zap_timeout)
        logger.info("[bootstrap] ZAP ready at %s", zap_url)

        return zap_url

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

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
