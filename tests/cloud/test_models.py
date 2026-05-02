"""Unit tests for CloudCredential, CloudScan, CloudOrphan models."""
import pytest
from app.models import CloudCredential, CloudScan, CloudOrphan, ZapConfiguration, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(session):
    u = User(username='testuser', email='test@example.com', role='admin', is_active=True)
    u.set_password('pw')
    session.add(u)
    session.flush()
    return u


def _make_scan(session, user_id):
    from app.models import Scan
    s = Scan(user_id=user_id, target='http://example.com', scan_mode='passive')
    session.add(s)
    session.flush()
    return s


# ---------------------------------------------------------------------------
# CloudCredential
# ---------------------------------------------------------------------------

def test_cloud_credential_credentials_round_trip(db_session):
    user = _make_user(db_session)
    cred = CloudCredential(name='Test AWS', provider='aws', created_by=user.id)
    cred.credentials = {'access_key': 'AKIA123', 'secret_key': 'supersecret'}
    db_session.add(cred)
    db_session.commit()

    fetched = CloudCredential.query.get(cred.id)
    assert fetched.credentials['access_key'] == 'AKIA123'
    assert fetched.credentials['secret_key'] == 'supersecret'
    # stored ciphertext must not contain the plaintext key
    assert 'AKIA123' not in fetched.credentials_encrypted



def test_cloud_credential_defaults(db_session):
    user = _make_user(db_session)
    cred = CloudCredential(name='Azure cred', provider='azure', created_by=user.id)
    cred.credentials = {'tenant_id': 't1', 'client_id': 'c1',
                        'client_secret': 'cs', 'subscription_id': 'sub'}
    db_session.add(cred)
    db_session.commit()

    fetched = CloudCredential.query.get(cred.id)
    assert fetched.is_active is True
    assert fetched.created_at is not None


# ---------------------------------------------------------------------------
# CloudScan
# ---------------------------------------------------------------------------

def test_cloud_scan_zap_api_key_round_trip(db_session):
    user = _make_user(db_session)
    scan = _make_scan(db_session, user.id)
    cred = CloudCredential(name='c', provider='aws', created_by=user.id)
    cred.credentials = {'access_key': 'x', 'secret_key': 'y'}
    db_session.add(cred)
    db_session.flush()

    cs = CloudScan(scan_id=scan.id, cloud_credential_id=cred.id, provider='aws')
    cs.zap_api_key = 'my-secret-api-key'
    db_session.add(cs)
    db_session.commit()

    fetched = CloudScan.query.get(cs.id)
    assert fetched.zap_api_key == 'my-secret-api-key'
    assert 'my-secret-api-key' not in (fetched.zap_api_key_encrypted or '')


def test_cloud_scan_null_zap_api_key(db_session):
    user = _make_user(db_session)
    scan = _make_scan(db_session, user.id)
    cred = CloudCredential(name='c', provider='aws', created_by=user.id)
    cred.credentials = {'access_key': 'k', 'secret_key': 's'}
    db_session.add(cred)
    db_session.flush()

    cs = CloudScan(scan_id=scan.id, cloud_credential_id=cred.id, provider='aws')
    db_session.add(cs)
    db_session.commit()

    fetched = CloudScan.query.get(cs.id)
    assert fetched.zap_api_key is None


def test_cloud_scan_default_status(db_session):
    user = _make_user(db_session)
    scan = _make_scan(db_session, user.id)
    cred = CloudCredential(name='c', provider='gcp', created_by=user.id)
    cred.credentials = {'project_id': 'proj-1'}
    db_session.add(cred)
    db_session.flush()

    cs = CloudScan(scan_id=scan.id, cloud_credential_id=cred.id, provider='gcp')
    db_session.add(cs)
    db_session.commit()

    fetched = CloudScan.query.get(cs.id)
    assert fetched.status == 'provisioning'


# ---------------------------------------------------------------------------
# CloudOrphan
# ---------------------------------------------------------------------------

def test_cloud_orphan_defaults(db_session):
    orphan = CloudOrphan(
        provider='aws',
        resource_id='i-0abc1234',
        resource_type='ec2_instance',
    )
    db_session.add(orphan)
    db_session.commit()

    fetched = CloudOrphan.query.get(orphan.id)
    assert fetched.status == 'detected'
    assert fetched.cleanup_attempts == 0
    assert fetched.detected_at is not None


# ---------------------------------------------------------------------------
# ZapConfiguration → CloudCredential FK
# ---------------------------------------------------------------------------

def test_zap_configuration_cloud_credential_fk(db_session):
    user = _make_user(db_session)
    cred = CloudCredential(name='AWS prod', provider='aws', created_by=user.id)
    cred.credentials = {'access_key': 'k', 'secret_key': 's'}
    db_session.add(cred)
    db_session.flush()

    zc = ZapConfiguration(
        name='Cloud Scan Config',
        execution_mode='cloud',
        created_by=user.id,
        cloud_credential_id=cred.id,
    )
    db_session.add(zc)
    db_session.commit()

    fetched = ZapConfiguration.query.get(zc.id)
    assert fetched.cloud_credential_id == cred.id
    assert fetched.cloud_credential.provider == 'aws'
