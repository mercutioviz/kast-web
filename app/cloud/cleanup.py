"""
app/cloud/cleanup — orphan detection and cleanup for cloud resources.

Ported from kast/kast/scripts/cleanup_orphaned_resources.py with these
adaptations:
  - Hooks into the CloudScan DB table (created in D2) rather than scanning
    kast's local Terraform state directories.
  - Scheduled via Celery Beat every 15 minutes (wired in D5).
  - Manual trigger available via POST /api/cloud/orphans/<id>/cleanup (D8).

An orphan is a cloud resource that:
  - Has a CloudScan row stuck in 'provisioning', 'scanning', or 'tearing_down'
    beyond its expected maximum duration, OR
  - Was detected as live by the cloud provider but has no matching CloudScan row.
"""

from flask import current_app


def detect_orphans() -> list[dict]:
    """Scan CloudScan table and live cloud resources for orphaned infrastructure.

    Checks:
    1. CloudScan rows in terminal states ('provisioning', 'scanning',
       'tearing_down') older than their expected maximum age.
    2. CloudScan rows already in 'orphaned' status that have not yet been
       cleaned up.

    For each found resource, calls provider.get_status() to confirm it is
    still live before creating or updating a CloudOrphan row.

    Returns:
        List of dicts, one per detected orphan:
            {orphan_id, provider, resource_id, resource_type,
             cloud_scan_id (or None), detected_at}
    """
    raise NotImplementedError("Will be implemented in D5 (orphan cleanup)")


def schedule_cleanup(orphan_id: int) -> None:
    """Mark a CloudOrphan row as scheduled and enqueue teardown.

    Sets CloudOrphan.status = 'scheduled' and CloudOrphan.cleanup_scheduled_for
    to now + a short grace period, then dispatches cloud_teardown_task (D4).

    Args:
        orphan_id: ID of the CloudOrphan row to schedule.
    """
    raise NotImplementedError("Will be implemented in D5 (orphan cleanup)")


def force_cleanup(orphan_id: int) -> None:
    """Immediately attempt teardown of an orphaned resource.

    Bypasses the grace period used by schedule_cleanup(). Called from
    POST /api/cloud/orphans/<id>/cleanup (D8) for manual admin intervention.

    Increments CloudOrphan.cleanup_attempts on each call.
    On failure, sets status = 'manual_review' if attempts >= 3.

    Args:
        orphan_id: ID of the CloudOrphan row.

    Raises:
        CloudTeardownError: if teardown fails. The CloudOrphan row is updated
            with the error and status set appropriately.
    """
    raise NotImplementedError("Will be implemented in D5 (orphan cleanup)")
