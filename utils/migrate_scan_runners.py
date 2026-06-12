"""
Migration: add scan_runners table and runner_id column on scans for the
"scan runner" feature (remote kast execution over SSH).

Safe to re-run; idempotent via PRAGMA table_info / sqlite_master checks.
"""
import logging
import sys
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)


def migrate(app=None):
    if app is None:
        from app import create_app
        app = create_app()

    with app.app_context():
        from app import db

        print('=' * 60)
        print('SCAN RUNNERS MIGRATION (migrate_scan_runners)')
        print('=' * 60)
        print()

        with db.engine.connect() as conn:
            table_exists = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='scan_runners'"
            )).fetchone()

            if not table_exists:
                print('Creating scan_runners table...')
                conn.execute(text("""
                    CREATE TABLE scan_runners (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(80) NOT NULL UNIQUE,
                        hostname VARCHAR(255) NOT NULL,
                        port INTEGER NOT NULL DEFAULT 22,
                        username VARCHAR(80) NOT NULL,
                        ssh_private_key_encrypted TEXT NOT NULL,
                        kast_binary_path VARCHAR(500) NOT NULL DEFAULT '/usr/local/bin/kast',
                        remote_output_root VARCHAR(500) NOT NULL DEFAULT '/tmp/kast-runs',
                        region_label VARCHAR(80),
                        enabled BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.commit()
                print('  Done.')
            else:
                print('scan_runners table already exists — skipping.')

            scans_columns = {
                row[1]
                for row in conn.execute(text('PRAGMA table_info(scans)')).fetchall()
            }

            if 'runner_id' not in scans_columns:
                print('Adding runner_id column to scans...')
                conn.execute(text(
                    'ALTER TABLE scans ADD COLUMN runner_id INTEGER REFERENCES scan_runners(id)'
                ))
                conn.commit()
                print('  Done.')
            else:
                print('runner_id column already exists — skipping.')

            index_exists = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='ix_scans_runner_id'"
            )).fetchone()

            if not index_exists:
                print('Creating index ix_scans_runner_id...')
                conn.execute(text(
                    'CREATE INDEX ix_scans_runner_id ON scans(runner_id)'
                ))
                conn.commit()
                print('  Done.')
            else:
                print('Index ix_scans_runner_id already exists — skipping.')

        print()
        print('Migration complete.')
        return True


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent))
    logging.basicConfig(level=logging.WARNING)
    success = migrate()
    sys.exit(0 if success else 1)
