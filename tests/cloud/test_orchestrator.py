"""Unit tests for app/cloud/orchestrator.py — provision, teardown, cleanup."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.models import (
    AuditLog, CloudCredential, CloudOrphan, CloudScan, Scan, User,
    ZapConfiguration,
)
from app.cloud.orchestrator import (
    CloudProvisionError, CloudTeardownError, CredentialError,
    cleanup_orphans, provision_for_scan, teardown_for_scan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(session):
    u = User(username="orchtest", email="orch@example.com", role="admin", is_active=True)
    u.set_password("pw")
    session.add(u)
    session.flush()
    return u


def _make_credential(session, user_id, provider="aws"):
    cred = CloudCredential(name=f"{provider}-cred", provider=provider, created_by=user_id)
    cred.credentials = {"access_key": "AK123", "secret_key": "SK456"}
    session.add(cred)
    session.flush()
    return cred


def _make_zap_config(session, user_id, cred_id, mode="cloud"):
    zc = ZapConfiguration(
        name="cloud-cfg",
        execution_mode=mode,
        created_by=user_id,
        cloud_credential_id=cred_id,
    )
    session.add(zc)
    session.flush()
    return zc


def _make_scan(session, user_id, zap_config_id=None):
    s = Scan(
        user_id=user_id,
        target="http://example.com",
        scan_mode="passive",
        zap_config_id=zap_config_id,
    )
    session.add(s)
    session.flush()
    return s


def _make_cloud_scan(session, scan_id, cred_id, status="scanning", provider="aws"):
    cs = CloudScan(
        scan_id=scan_id,
        cloud_credential_id=cred_id,
        provider=provider,
        status=status,
        terraform_state_path="/tmp/tf/1",
    )
    session.add(cs)
    session.flush()
    return cs


# ---------------------------------------------------------------------------
# provision_for_scan — validation errors
# ---------------------------------------------------------------------------

def test_provision_scan_not_found(db_session):
    with pytest.raises(ValueError, match="Scan 99999 not found"):
        provision_for_scan(99999)


def test_provision_no_zap_config(db_session):
    user = _make_user(db_session)
    scan = _make_scan(db_session, user.id)  # no zap_config_id

    with pytest.raises(ValueError, match="no ZAP configuration"):
        provision_for_scan(scan.id)


def test_provision_wrong_execution_mode(db_session):
    user = _make_user(db_session)
    cred = _make_credential(db_session, user.id)
    zc = _make_zap_config(db_session, user.id, cred.id, mode="local")
    scan = _make_scan(db_session, user.id, zap_config_id=zc.id)

    with pytest.raises(ValueError, match="execution_mode is 'local'"):
        provision_for_scan(scan.id)


def test_provision_no_credential_id(db_session):
    user = _make_user(db_session)
    # ZapConfiguration without cloud_credential_id
    zc = ZapConfiguration(
        name="cloud-nocred", execution_mode="cloud", created_by=user.id
    )
    db_session.add(zc)
    db_session.flush()
    scan = _make_scan(db_session, user.id, zap_config_id=zc.id)

    with pytest.raises(CredentialError, match="no cloud_credential_id"):
        provision_for_scan(scan.id)


def test_provision_credential_not_found(db_session):
    user = _make_user(db_session)
    zc = ZapConfiguration(
        name="cloud-badcred", execution_mode="cloud",
        created_by=user.id, cloud_credential_id=99999,
    )
    db_session.add(zc)
    db_session.flush()
    scan = _make_scan(db_session, user.id, zap_config_id=zc.id)

    with pytest.raises(CredentialError, match="not found"):
        provision_for_scan(scan.id)


# ---------------------------------------------------------------------------
# provision_for_scan — success path
# ---------------------------------------------------------------------------

def test_provision_success(db_session):
    user = _make_user(db_session)
    cred = _make_credential(db_session, user.id)
    zc = _make_zap_config(db_session, user.id, cred.id)
    scan = _make_scan(db_session, user.id, zap_config_id=zc.id)

    mock_result = {
        "instance_id": "i-abc123",
        "zap_url": "http://1.2.3.4:8080",
        "zap_api_key": "testkey",
        "terraform_state_path": "/tmp/tf/state",
    }

    with patch("app.cloud.orchestrator._get_provider") as mock_get:
        mock_provider = MagicMock()
        mock_provider.provision.return_value = mock_result
        mock_get.return_value = mock_provider

        result = provision_for_scan(scan.id)

    assert result["zap_url"] == "http://1.2.3.4:8080"
    assert result["zap_api_key"] == "testkey"
    assert result["instance_id"] == "i-abc123"
    assert "cloud_scan_id" in result

    # CloudScan row created with correct status
    cs = db_session.get(CloudScan, result["cloud_scan_id"])
    assert cs.status == "scanning"
    assert cs.zap_url == "http://1.2.3.4:8080"
    assert cs.provisioned_at is not None

    # AuditLog entry written
    log = AuditLog.query.filter_by(action="cloud_provision").first()
    assert log is not None
    assert log.resource_id == result["cloud_scan_id"]


def test_provision_failure_creates_failed_scan_row(db_session):
    user = _make_user(db_session)
    cred = _make_credential(db_session, user.id)
    zc = _make_zap_config(db_session, user.id, cred.id)
    scan = _make_scan(db_session, user.id, zap_config_id=zc.id)

    with patch("app.cloud.orchestrator._get_provider") as mock_get:
        mock_provider = MagicMock()
        mock_provider.provision.side_effect = RuntimeError("terraform boom")
        mock_get.return_value = mock_provider

        with pytest.raises(CloudProvisionError) as exc_info:
            provision_for_scan(scan.id)

    exc = exc_info.value
    assert exc.cloud_scan_id is not None

    cs = db_session.get(CloudScan, exc.cloud_scan_id)
    assert cs.status == "failed"
    assert "terraform boom" in cs.error_message


# ---------------------------------------------------------------------------
# teardown_for_scan
# ---------------------------------------------------------------------------

def test_teardown_not_found(db_session):
    with pytest.raises(CloudTeardownError, match="not found"):
        teardown_for_scan(99999)


def test_teardown_already_torn_down(db_session):
    user = _make_user(db_session)
    cred = _make_credential(db_session, user.id)
    scan = _make_scan(db_session, user.id)
    cs = _make_cloud_scan(db_session, scan.id, cred.id, status="torn_down")

    # Should return without error (idempotent)
    teardown_for_scan(cs.id)
    db_session.refresh(cs)
    assert cs.status == "torn_down"


def test_teardown_success(db_session):
    user = _make_user(db_session)
    cred = _make_credential(db_session, user.id)
    scan = _make_scan(db_session, user.id)
    cs = _make_cloud_scan(db_session, scan.id, cred.id, status="scanning")

    with patch("app.cloud.orchestrator._get_provider") as mock_get:
        mock_provider = MagicMock()
        mock_get.return_value = mock_provider

        teardown_for_scan(cs.id)

    db_session.refresh(cs)
    assert cs.status == "torn_down"
    assert cs.torn_down_at is not None
    assert cs.error_message is None

    log = AuditLog.query.filter_by(action="cloud_teardown").first()
    assert log is not None


def test_teardown_failure_marks_orphaned(db_session):
    user = _make_user(db_session)
    cred = _make_credential(db_session, user.id)
    scan = _make_scan(db_session, user.id)
    cs = _make_cloud_scan(db_session, scan.id, cred.id, status="scanning")

    with patch("app.cloud.orchestrator._get_provider") as mock_get:
        mock_provider = MagicMock()
        mock_provider.teardown.side_effect = RuntimeError("aws destroy failed")
        mock_get.return_value = mock_provider

        with pytest.raises(CloudTeardownError, match="aws destroy failed"):
            teardown_for_scan(cs.id)

    db_session.refresh(cs)
    assert cs.status == "orphaned"
    assert "aws destroy failed" in cs.error_message


# ---------------------------------------------------------------------------
# cleanup_orphans
# ---------------------------------------------------------------------------

def test_cleanup_orphans_no_stuck(db_session):
    # Fresh DB — no cloud scans at all
    result = cleanup_orphans()
    assert result["detected"] == 0
    assert result["scheduled"] == 0
    assert result["errors"] == []


def test_cleanup_orphans_detects_stuck_provisioning(db_session):
    user = _make_user(db_session)
    cred = _make_credential(db_session, user.id)
    scan = _make_scan(db_session, user.id)

    cs = _make_cloud_scan(db_session, scan.id, cred.id, status="provisioning")
    # Back-date created_at beyond the 45-minute threshold
    cs.created_at = datetime.utcnow() - timedelta(hours=1)
    db_session.commit()

    # Late import in cleanup_orphans resolves from app.tasks, so patch there
    with patch("app.tasks.cloud_teardown_task") as mock_task:
        mock_task.delay = MagicMock()
        result = cleanup_orphans()

    assert result["detected"] == 1
    assert result["scheduled"] == 1
    db_session.refresh(cs)
    assert cs.status == "orphaned"


def test_cleanup_orphans_skips_recent_provisioning(db_session):
    user = _make_user(db_session)
    cred = _make_credential(db_session, user.id)
    scan = _make_scan(db_session, user.id)

    cs = _make_cloud_scan(db_session, scan.id, cred.id, status="provisioning")
    # created_at defaults to now — within threshold, should not be detected
    result = cleanup_orphans()

    assert result["detected"] == 0
    db_session.refresh(cs)
    assert cs.status == "provisioning"


def test_cleanup_orphans_already_orphaned(db_session):
    user = _make_user(db_session)
    cred = _make_credential(db_session, user.id)
    scan = _make_scan(db_session, user.id)

    cs = _make_cloud_scan(db_session, scan.id, cred.id, status="orphaned")

    with patch("app.tasks.cloud_teardown_task") as mock_task:
        mock_task.delay = MagicMock()
        result = cleanup_orphans()

    assert result["detected"] == 1
    assert result["scheduled"] == 1
    # Status stays 'orphaned' (no transition needed)
    db_session.refresh(cs)
    assert cs.status == "orphaned"
