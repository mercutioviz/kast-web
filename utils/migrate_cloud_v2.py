"""
Migration: add CloudCredential, CloudScan, CloudOrphan tables (Phase D).

Also adds cloud_credential_id FK column to zap_configurations and backfills
one CloudCredential row per ZapConfiguration that has a cloud_config with
recognised credential keys.

Safe to re-run; idempotent via PRAGMA table_info checks.
"""
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

logger = logging.getLogger(__name__)

CREDENTIAL_KEYS_BY_PROVIDER = {
    'aws': frozenset([
        'access_key', 'secret_key',
        'access_key_id', 'secret_access_key',
        'aws_access_key_id', 'aws_secret_access_key',
        'session_token',
    ]),
    'azure': frozenset([
        'subscription_id', 'tenant_id', 'client_id', 'client_secret',
    ]),
    'gcp': frozenset([
        'project_id', 'credentials', 'service_account_json',
        'service_account_key', 'credentials_json',
    ]),
}

DB_PATH = Path('/var/lib/kast-web2/kast.db')


def _backup_db():
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    dest = DB_PATH.with_suffix(f'.pre_cloud_v2_{ts}.bak')
    shutil.copy2(DB_PATH, dest)
    print(f'  Backup created: {dest}')


def _column_exists(conn, table, column):
    result = conn.execute(text(f'PRAGMA table_info({table})')).fetchall()
    return any(row[1] == column for row in result)


def migrate(app=None, no_backup=False):
    """Run the Phase D cloud migration.

    Args:
        app: Flask app instance. If None, create_app() is called.
        no_backup: Skip DB file backup (use in tests against :memory:).
    """
    if app is None:
        from app import create_app
        app = create_app()

    with app.app_context():
        from app import db
        from app.models import CloudCredential, ZapConfiguration

        print('=' * 60)
        print('PHASE D: CLOUD V2 MIGRATION')
        print('=' * 60)
        print()

        # Step 1 — backup
        if not no_backup and DB_PATH.exists():
            print('Step 1: Backing up database...')
            try:
                _backup_db()
            except Exception as exc:
                print(f'  ERROR during backup: {exc}')
                return False
        else:
            print('Step 1: Skipping backup (no_backup=True or :memory: DB).')
        print()

        # Step 2 — create new tables
        print('Step 2: Creating new tables...')
        try:
            db.create_all()
            print('  Tables created / verified.')
        except Exception as exc:
            print(f'  ERROR: {exc}')
            return False
        print()

        # Step 3 — ALTER TABLE zap_configurations (idempotent)
        print('Step 3: Adding cloud_credential_id column to zap_configurations...')
        try:
            engine = db.engine
            with engine.begin() as conn:
                if _column_exists(conn, 'zap_configurations', 'cloud_credential_id'):
                    print('  Column already exists, skipping.')
                else:
                    conn.execute(text(
                        'ALTER TABLE zap_configurations '
                        'ADD COLUMN cloud_credential_id INTEGER '
                        'REFERENCES cloud_credentials(id)'
                    ))
                    print('  Column added.')
        except Exception as exc:
            print(f'  ERROR: {exc}')
            return False
        print()

        # Step 4 — backfill CloudCredential from existing ZapConfigurations
        print('Step 4: Backfilling CloudCredential rows...')
        configs = ZapConfiguration.query.all()
        migrated = 0
        skipped = 0
        for config in configs:
            try:
                cloud_cfg = config.cloud_config
            except Exception as exc:
                logger.warning('Cannot decrypt cloud_config for ZapConfiguration %s: %s', config.id, exc)
                skipped += 1
                continue

            if not cloud_cfg:
                skipped += 1
                continue

            provider = cloud_cfg.get('provider', '').lower()
            if provider not in CREDENTIAL_KEYS_BY_PROVIDER:
                logger.warning(
                    'ZapConfiguration %s has unknown provider %r, skipping', config.id, provider
                )
                skipped += 1
                continue

            cred_keys = CREDENTIAL_KEYS_BY_PROVIDER[provider]
            extracted = {k: v for k, v in cloud_cfg.items() if k in cred_keys}

            if not extracted:
                skipped += 1
                continue

            try:
                cred = CloudCredential(
                    name=f'{config.name} (migrated)',
                    provider=provider,
                    created_by=config.created_by,
                )
                cred.credentials = extracted
                db.session.add(cred)
                db.session.flush()  # get cred.id

                # Rewrite cloud_config without credential keys
                remaining = {k: v for k, v in cloud_cfg.items() if k not in cred_keys}
                config.cloud_config = remaining
                config.cloud_credential_id = cred.id

                db.session.commit()
                migrated += 1
                print(f'  Migrated ZapConfiguration {config.id} ({config.name}) → CloudCredential {cred.id}')
            except Exception as exc:
                db.session.rollback()
                logger.warning(
                    'Error migrating ZapConfiguration %s: %s', config.id, exc
                )
                skipped += 1
                continue

        print()
        print('=' * 60)
        print('MIGRATION COMPLETED')
        print('=' * 60)
        print(f'  CloudCredential rows created: {migrated}')
        print(f'  ZapConfigurations skipped:    {skipped}')
        print(f'  Total ZapConfigurations:      {len(configs)}')
        print()
        return True


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
