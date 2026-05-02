"""Integration tests for utils/migrate_cloud_v2.py."""
import pytest
from app import db as _db
from app.models import CloudCredential, ZapConfiguration, User
import utils.migrate_cloud_v2 as migrate_cloud_v2


# ---------------------------------------------------------------------------
# Fixture: isolated DB per test (does NOT use db_session — that would drop
# tables between tests.  We manage setup/teardown ourselves.)
# ---------------------------------------------------------------------------

@pytest.fixture
def migration_db(app):
    """Create all tables, yield the Flask app, then drop all tables."""
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin(app):
    with app.app_context():
        u = User.query.filter_by(username='migadmin').first()
        if u:
            return u.id
        u = User(username='migadmin', email='migadmin@example.com',
                 role='admin', is_active=True)
        u.set_password('pw')
        _db.session.add(u)
        _db.session.commit()
        return u.id


def _make_zap_config(app, name, cloud_config_dict, admin_id):
    """Create a ZapConfiguration with encrypted cloud_config, return its id."""
    with app.app_context():
        zc = ZapConfiguration(
            name=name,
            execution_mode='cloud',
            created_by=admin_id,
        )
        zc.cloud_config = cloud_config_dict
        _db.session.add(zc)
        _db.session.commit()
        return zc.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_migrate_happy_path_aws(migration_db):
    app = migration_db
    admin_id = _admin(app)
    zc_id = _make_zap_config(app, 'AWS Prod', {
        'provider': 'aws',
        'region': 'us-east-1',
        'access_key': 'AKIA123',
        'secret_key': 'supersecret',
        'instance_type': 't3.medium',
    }, admin_id)

    result = migrate_cloud_v2.migrate(app=app, no_backup=True)
    assert result is True

    with app.app_context():
        cred = CloudCredential.query.filter_by(name='AWS Prod (migrated)').first()
        assert cred is not None
        assert cred.provider == 'aws'
        assert cred.credentials['access_key'] == 'AKIA123'
        assert cred.credentials['secret_key'] == 'supersecret'
        # region + instance_type must NOT be in credentials
        assert 'region' not in cred.credentials

        zc = ZapConfiguration.query.get(zc_id)
        assert zc.cloud_credential_id == cred.id
        # cred keys must be stripped from cloud_config
        remaining = zc.cloud_config
        assert 'access_key' not in remaining
        assert 'secret_key' not in remaining
        assert remaining.get('region') == 'us-east-1'


def test_migrate_happy_path_aws_seed_naming(migration_db):
    """Handles the seed-data naming convention (aws_access_key_id / aws_secret_access_key)."""
    app = migration_db
    admin_id = _admin(app)
    _make_zap_config(app, 'AWS Seed', {
        'provider': 'aws',
        'region': 'us-west-2',
        'aws_access_key_id': 'AKIASEED',
        'aws_secret_access_key': 'seedsecret',
    }, admin_id)

    result = migrate_cloud_v2.migrate(app=app, no_backup=True)
    assert result is True

    with app.app_context():
        cred = CloudCredential.query.filter_by(name='AWS Seed (migrated)').first()
        assert cred is not None
        assert cred.credentials['aws_access_key_id'] == 'AKIASEED'
        assert cred.credentials['aws_secret_access_key'] == 'seedsecret'


def test_migrate_happy_path_azure(migration_db):
    app = migration_db
    admin_id = _admin(app)
    _make_zap_config(app, 'Azure Dev', {
        'provider': 'azure',
        'region': 'eastus',
        'subscription_id': 'sub-123',
        'tenant_id': 'ten-456',
        'client_id': 'cli-789',
        'client_secret': 'sec-000',
    }, admin_id)

    result = migrate_cloud_v2.migrate(app=app, no_backup=True)
    assert result is True

    with app.app_context():
        cred = CloudCredential.query.filter_by(name='Azure Dev (migrated)').first()
        assert cred is not None
        assert cred.provider == 'azure'
        assert cred.credentials['subscription_id'] == 'sub-123'


def test_migrate_skips_missing_provider(migration_db):
    """ZapConfiguration with no 'provider' key in cloud_config is silently skipped."""
    app = migration_db
    admin_id = _admin(app)
    _make_zap_config(app, 'No Provider', {
        'region': 'us-east-1',
        'access_key': 'AKIA999',
    }, admin_id)

    result = migrate_cloud_v2.migrate(app=app, no_backup=True)
    assert result is True

    with app.app_context():
        assert CloudCredential.query.count() == 0


def test_migrate_skips_unknown_provider(migration_db):
    """ZapConfiguration with unrecognised provider is silently skipped."""
    app = migration_db
    admin_id = _admin(app)
    _make_zap_config(app, 'Weird Cloud', {
        'provider': 'digitalocean',
        'token': 'abc123',
    }, admin_id)

    result = migrate_cloud_v2.migrate(app=app, no_backup=True)
    assert result is True

    with app.app_context():
        assert CloudCredential.query.count() == 0


def test_migrate_skips_empty_cloud_config(migration_db):
    """ZapConfiguration with empty cloud_config produces no CloudCredential."""
    app = migration_db
    admin_id = _admin(app)
    _make_zap_config(app, 'Local Only', {}, admin_id)

    result = migrate_cloud_v2.migrate(app=app, no_backup=True)
    assert result is True

    with app.app_context():
        assert CloudCredential.query.count() == 0


def test_migrate_idempotent(migration_db):
    """Running migrate() twice produces no additional rows."""
    app = migration_db
    admin_id = _admin(app)
    _make_zap_config(app, 'AWS Idempotent', {
        'provider': 'aws',
        'access_key': 'AKIAIDEMP',
        'secret_key': 'idemsecret',
    }, admin_id)

    assert migrate_cloud_v2.migrate(app=app, no_backup=True) is True
    with app.app_context():
        count_after_first = CloudCredential.query.count()

    assert migrate_cloud_v2.migrate(app=app, no_backup=True) is True
    with app.app_context():
        count_after_second = CloudCredential.query.count()

    assert count_after_first == count_after_second
