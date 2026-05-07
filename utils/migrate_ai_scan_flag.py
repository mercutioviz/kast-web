"""
Migration: add generate_ai_summary column to scans table.

Safe to re-run; idempotent via PRAGMA table_info check.
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
        print('AI SCAN FLAG MIGRATION (migrate_ai_scan_flag)')
        print('=' * 60)
        print()

        with db.engine.connect() as conn:
            columns = {
                row[1]
                for row in conn.execute(text('PRAGMA table_info(scans)')).fetchall()
            }

            if 'generate_ai_summary' not in columns:
                print('Adding generate_ai_summary column to scans...')
                conn.execute(text(
                    'ALTER TABLE scans ADD COLUMN generate_ai_summary BOOLEAN NOT NULL DEFAULT 0'
                ))
                conn.commit()
                print('  Done.')
            else:
                print('generate_ai_summary column already exists — skipping.')

        print()
        print('Migration complete.')
        return True


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent))
    logging.basicConfig(level=logging.WARNING)
    success = migrate()
    sys.exit(0 if success else 1)
