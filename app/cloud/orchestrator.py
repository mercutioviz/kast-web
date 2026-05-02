"""
app/cloud/orchestrator — top-level cloud lifecycle entry points.

The orchestrator is the only module app/tasks.py talks to for cloud scans.
It resolves credentials, selects the right provider, delegates to
TerraformManager/SshExecutor/ZapApiClient, and maintains CloudScan state.

Callers (D4 — app/tasks.py:execute_scan_task):
    from app.cloud.orchestrator import provision_for_scan, teardown_for_scan
    from app.cloud.cleanup import detect_orphans  # called via Celery Beat (D5)

Exceptions raised here bubble up to the Celery task, which marks the Scan
as failed and ensures teardown is still scheduled.
"""

from typing import TypedDict


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CloudProvisionError(Exception):
    """Raised when provisioning fails at any stage.

    Attributes:
        cloud_scan_id: The CloudScan row ID if one was created before failure,
            so the caller can still schedule teardown on the partial state.
            None if provisioning failed before any CloudScan row was written.
    """
    def __init__(self, message: str, cloud_scan_id: int | None = None):
        super().__init__(message)
        self.cloud_scan_id = cloud_scan_id


class CloudTeardownError(Exception):
    """Raised when teardown cannot complete cleanly.

    The CloudScan row will be marked 'orphaned' so cleanup.py can retry.
    """


class CredentialError(Exception):
    """Raised when a CloudCredential cannot be decrypted or is missing required keys."""


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

class ProvisionResult(TypedDict):
    """Returned by provision_for_scan on success."""
    cloud_scan_id: int    # ID of the new CloudScan row
    zap_url: str          # e.g. 'http://1.2.3.4:8080'
    zap_api_key: str      # ZAP API key for --set zap.remote.api_key=
    instance_id: str      # cloud-side identifier (EC2 instance ID, etc.)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def provision_for_scan(scan_id: int) -> ProvisionResult:
    """Provision cloud infrastructure to run a ZAP scan.

    Resolves the Scan → ZapConfiguration → CloudCredential chain,
    decrypts credentials, calls the appropriate provider, waits for ZAP
    to be reachable, creates a CloudScan row, and returns connection info.

    The caller (execute_scan_task in D4) uses the returned dict to build:
        kast --target X --set zap.execution_mode=remote
                        --set zap.remote.url=<zap_url>
                        --set zap.remote.api_key=<zap_api_key> ...

    Args:
        scan_id: ID of the Scan row being provisioned for.

    Returns:
        ProvisionResult with cloud_scan_id, zap_url, zap_api_key, instance_id.

    Raises:
        ValueError: scan_id not found, or ZapConfiguration.execution_mode != 'cloud'.
        CredentialError: CloudCredential missing or cannot be decrypted.
        CloudProvisionError: provider failed to provision; .cloud_scan_id is set
            if a partial CloudScan row was created (so teardown can still run).
    """
    raise NotImplementedError("Will be implemented in D4 (orchestrator wiring)")


def teardown_for_scan(cloud_scan_id: int) -> None:
    """Tear down cloud infrastructure for a completed or failed scan.

    Idempotent: safe to call multiple times or if provisioning never finished.
    Updates CloudScan.status to 'tearing_down', runs provider.teardown(),
    then marks status 'torn_down'. Writes an AuditLog entry on completion.

    Args:
        cloud_scan_id: ID of the CloudScan row created by provision_for_scan.

    Raises:
        CloudTeardownError: teardown failed; the CloudScan row is marked
            'orphaned' so cleanup.py can retry on the next Beat cycle.
    """
    raise NotImplementedError("Will be implemented in D4 (orchestrator wiring)")


def cleanup_orphans() -> dict:
    """Walk CloudScan rows, detect orphans, and schedule cleanup.

    Called every 15 minutes by Celery Beat (wired in D5).
    Queries CloudScan rows stuck in 'provisioning', 'scanning', or
    'tearing_down' beyond their expected maximum duration, and rows
    in 'orphaned' status. For each, calls provider.get_status() to
    confirm the resource is still live, then schedules teardown.

    Returns:
        dict with keys:
            detected (int): number of orphaned resources found.
            scheduled (int): number of teardown tasks dispatched.
            errors (list[str]): any exceptions encountered per resource.
    """
    raise NotImplementedError("Will be implemented in D5 (orphan cleanup)")
