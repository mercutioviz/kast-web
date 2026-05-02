"""
app/cloud/orchestrator — top-level cloud lifecycle entry points.

The orchestrator is the only module app/tasks.py talks to for cloud scans.
It resolves credentials, selects the right provider, delegates to
TerraformManager/SshExecutor/ZapApiClient, and maintains CloudScan state.

Callers (D4 — app/tasks.py):
    from app.cloud.orchestrator import provision_for_scan, teardown_for_scan
    from app.cloud.orchestrator import cleanup_orphans  # called via Celery Beat (D5)

Exceptions raised here bubble up to the Celery task, which marks the Scan
as failed and ensures teardown is still scheduled.
"""

from datetime import datetime, timedelta
from typing import TypedDict

from flask import current_app

from app import db


# ---------------------------------------------------------------------------
# Timeouts for orphan detection
# ---------------------------------------------------------------------------

_PROVISION_TIMEOUT = timedelta(minutes=45)
_SCAN_TIMEOUT = timedelta(hours=4)
_TEARDOWN_TIMEOUT = timedelta(hours=1)


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

    The CloudScan row will be marked 'orphaned' so cleanup can retry.
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
# Provider registry
# ---------------------------------------------------------------------------

def _get_provider(provider_name: str):
    """Return the concrete CloudProvider instance for a provider name."""
    name = provider_name.lower()
    if name == "aws":
        from app.cloud.providers.aws import AwsProvider
        return AwsProvider()
    if name == "azure":
        from app.cloud.providers.azure import AzureProvider
        return AzureProvider()
    if name == "gcp":
        from app.cloud.providers.gcp import GcpProvider
        return GcpProvider()
    raise ValueError(f"Unknown cloud provider: {provider_name!r}")


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def provision_for_scan(scan_id: int) -> ProvisionResult:
    """Provision cloud infrastructure to run a ZAP scan.

    Resolves the Scan → ZapConfiguration → CloudCredential chain,
    decrypts credentials, calls the appropriate provider, waits for ZAP
    to be reachable, creates a CloudScan row, and returns connection info.

    The caller (execute_scan_task) uses the returned dict to build:
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
    from app.models import Scan, ZapConfiguration, CloudCredential, CloudScan, AuditLog

    scan = db.session.get(Scan, scan_id)
    if not scan:
        raise ValueError(f"Scan {scan_id} not found")

    zap_config = db.session.get(ZapConfiguration, scan.zap_config_id) if scan.zap_config_id else None
    if not zap_config:
        raise ValueError(f"Scan {scan_id} has no ZAP configuration")
    if zap_config.execution_mode != "cloud":
        raise ValueError(
            f"Scan {scan_id} ZapConfiguration execution_mode is "
            f"{zap_config.execution_mode!r}, expected 'cloud'"
        )

    if not zap_config.cloud_credential_id:
        raise CredentialError(
            f"ZapConfiguration {zap_config.id} has no cloud_credential_id"
        )
    credential = db.session.get(CloudCredential, zap_config.cloud_credential_id)
    if not credential:
        raise CredentialError(
            f"CloudCredential {zap_config.cloud_credential_id} not found"
        )
    if not credential.is_active:
        raise CredentialError(
            f"CloudCredential {credential.id} ({credential.name!r}) is inactive"
        )

    try:
        credentials = credential.credentials
    except Exception as exc:
        raise CredentialError(f"Cannot decrypt CloudCredential {credential.id}: {exc}") from exc

    if not credentials:
        raise CredentialError(f"CloudCredential {credential.id} decrypted to empty dict")

    provider_name = credential.provider
    cloud_config = zap_config.cloud_config or {}

    deployment_config = dict(cloud_config)
    deployment_config["scan_id"] = scan_id

    current_app.logger.info(
        "[orchestrator] provisioning scan %d via %s", scan_id, provider_name
    )

    # Create the CloudScan row before calling provider so teardown can find it on failure
    cloud_scan = CloudScan(
        scan_id=scan_id,
        cloud_credential_id=credential.id,
        provider=provider_name,
        status="provisioning",
    )
    db.session.add(cloud_scan)
    db.session.commit()
    cloud_scan_id = cloud_scan.id

    try:
        provider = _get_provider(provider_name)
        result = provider.provision(credentials, deployment_config)
    except Exception as exc:
        cloud_scan.status = "failed"
        cloud_scan.error_message = str(exc)
        db.session.commit()
        raise CloudProvisionError(str(exc), cloud_scan_id=cloud_scan_id) from exc

    cloud_scan.status = "scanning"
    cloud_scan.zap_url = result["zap_url"]
    cloud_scan.zap_api_key = result["zap_api_key"]
    cloud_scan.terraform_state_path = result["terraform_state_path"]
    cloud_scan.provisioned_at = datetime.utcnow()
    db.session.commit()

    AuditLog.log(
        user_id=scan.user_id,
        action="cloud_provision",
        resource_type="cloud_scan",
        resource_id=cloud_scan_id,
        details=(
            f"scan_id={scan_id} provider={provider_name} "
            f"instance_id={result['instance_id']!r}"
        ),
    )

    current_app.logger.info(
        "[orchestrator] scan %d provisioned: cloud_scan=%d zap_url=%s",
        scan_id, cloud_scan_id, result["zap_url"],
    )

    return ProvisionResult(
        cloud_scan_id=cloud_scan_id,
        zap_url=result["zap_url"],
        zap_api_key=result["zap_api_key"],
        instance_id=result["instance_id"],
    )


def teardown_for_scan(cloud_scan_id: int) -> None:
    """Tear down cloud infrastructure for a completed or failed scan.

    Idempotent: safe to call multiple times or if provisioning never finished.
    Updates CloudScan.status to 'tearing_down', runs provider.teardown(),
    then marks status 'torn_down'. Writes an AuditLog entry on completion.

    Args:
        cloud_scan_id: ID of the CloudScan row created by provision_for_scan.

    Raises:
        CloudTeardownError: teardown failed; the CloudScan row is marked
            'orphaned' so cleanup can retry on the next Beat cycle.
    """
    from app.models import CloudScan, AuditLog

    cloud_scan = db.session.get(CloudScan, cloud_scan_id)
    if not cloud_scan:
        raise CloudTeardownError(f"CloudScan {cloud_scan_id} not found")

    if cloud_scan.status == "torn_down":
        current_app.logger.info(
            "[orchestrator] cloud_scan %d already torn down, skipping", cloud_scan_id
        )
        return

    current_app.logger.info(
        "[orchestrator] tearing down cloud_scan %d (provider=%s)",
        cloud_scan_id, cloud_scan.provider,
    )

    cloud_scan.status = "tearing_down"
    db.session.commit()

    if not cloud_scan.terraform_state_path:
        # Provisioning failed before Terraform ran — nothing to destroy
        cloud_scan.status = "torn_down"
        cloud_scan.torn_down_at = datetime.utcnow()
        db.session.commit()
        return

    try:
        provider = _get_provider(cloud_scan.provider)
        provider.teardown(
            instance_id=cloud_scan.terraform_state_path,
            state_path=cloud_scan.terraform_state_path,
        )
    except Exception as exc:
        cloud_scan.status = "orphaned"
        cloud_scan.error_message = str(exc)
        db.session.commit()
        raise CloudTeardownError(str(exc)) from exc

    cloud_scan.status = "torn_down"
    cloud_scan.torn_down_at = datetime.utcnow()
    cloud_scan.error_message = None
    db.session.commit()

    scan = cloud_scan.scan
    AuditLog.log(
        user_id=scan.user_id if scan else 1,
        action="cloud_teardown",
        resource_type="cloud_scan",
        resource_id=cloud_scan_id,
        details=f"scan_id={cloud_scan.scan_id} provider={cloud_scan.provider}",
    )

    current_app.logger.info(
        "[orchestrator] cloud_scan %d torn down successfully", cloud_scan_id
    )


def cleanup_orphans() -> dict:
    """Walk CloudScan rows, detect orphans, and schedule cleanup.

    Called every 15 minutes by Celery Beat.
    Queries CloudScan rows stuck in 'provisioning', 'scanning', or
    'tearing_down' beyond their expected maximum duration, and rows
    in 'orphaned' status. For each, marks the row 'orphaned' and
    dispatches cloud_teardown_task.

    Returns:
        dict with keys:
            detected (int): number of orphaned resources found.
            scheduled (int): number of teardown tasks dispatched.
            errors (list[str]): any exceptions encountered per resource.
    """
    from app.models import CloudScan

    now = datetime.utcnow()
    detected = 0
    scheduled = 0
    errors = []

    stuck_filters = [
        # stuck in provisioning longer than PROVISION_TIMEOUT
        db.and_(
            CloudScan.status == "provisioning",
            CloudScan.created_at < now - _PROVISION_TIMEOUT,
        ),
        # stuck in scanning longer than SCAN_TIMEOUT
        db.and_(
            CloudScan.status == "scanning",
            db.or_(
                CloudScan.provisioned_at < now - _SCAN_TIMEOUT,
                db.and_(
                    CloudScan.provisioned_at.is_(None),
                    CloudScan.created_at < now - _SCAN_TIMEOUT,
                ),
            ),
        ),
        # stuck in tearing_down longer than TEARDOWN_TIMEOUT
        db.and_(
            CloudScan.status == "tearing_down",
            CloudScan.created_at < now - _TEARDOWN_TIMEOUT,
        ),
        # already orphaned — retry teardown
        CloudScan.status == "orphaned",
    ]

    to_process = CloudScan.query.filter(db.or_(*stuck_filters)).all()
    detected = len(to_process)

    for cloud_scan in to_process:
        try:
            if cloud_scan.status != "orphaned":
                current_app.logger.warning(
                    "[cleanup_orphans] marking cloud_scan %d orphaned (was %s)",
                    cloud_scan.id, cloud_scan.status,
                )
                cloud_scan.status = "orphaned"
                db.session.commit()

            # Late import to avoid module-level circular dependency with tasks.py
            from app.tasks import cloud_teardown_task  # noqa: PLC0415
            cloud_teardown_task.delay(cloud_scan.id)
            scheduled += 1
        except Exception as exc:
            errors.append(f"cloud_scan {cloud_scan.id}: {exc}")
            current_app.logger.error(
                "[cleanup_orphans] error scheduling teardown for cloud_scan %d: %s",
                cloud_scan.id, exc,
            )

    current_app.logger.info(
        "[cleanup_orphans] detected=%d scheduled=%d errors=%d",
        detected, scheduled, len(errors),
    )
    return {"detected": detected, "scheduled": scheduled, "errors": errors}
