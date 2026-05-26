"""
Migration: add batch_id column to scans table for the batch-scan feature.

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
        print('BATCH ID MIGRATION (migrate_batch_id)')
        print('=' * 60)
        print()

        with db.engine.connect() as conn:
            columns = {
                row[1]
                for row in conn.execute(text('PRAGMA table_info(scans)')).fetchall()
            }

            if 'batch_id' not in columns:
                print('Adding batch_id column to scans...')
                conn.execute(text(
                    'ALTER TABLE scans ADD COLUMN batch_id VARCHAR(36)'
                ))
                conn.commit()
                print('  Done.')
            else:
                print('batch_id column already exists — skipping.')

            index_exists = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='ix_scans_batch_id'"
            )).fetchone()

            if not index_exists:
                print('Creating index ix_scans_batch_id...')
                conn.execute(text(
                    'CREATE INDEX ix_scans_batch_id ON scans(batch_id)'
                ))
                conn.commit()
                print('  Done.')
            else:
                print('Index ix_scans_batch_id already exists — skipping.')

        print()
        print('Migration complete.')
        return True


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent))
    logging.basicConfig(level=logging.WARNING)
    success = migrate()
    sys.exit(0 if success else 1)
