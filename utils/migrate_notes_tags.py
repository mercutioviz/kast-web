"""Migration: add notes and tags TEXT columns to scans table."""
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)

DB_PATH = Path('/var/lib/kast-web/kast.db')


def _backup_db():
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    dest = DB_PATH.with_suffix(f'.pre_notes_tags_{ts}.bak')
    shutil.copy2(DB_PATH, dest)
    print(f'  Backup created: {dest}')


def _column_exists(conn, table, column):
    result = conn.execute(text(f'PRAGMA table_info({table})')).fetchall()
    return any(row[1] == column for row in result)


def migrate(app=None, no_backup=False):
    if app is None:
        from app import create_app
        app = create_app()

    with app.app_context():
        from app import db

        print('=' * 60)
        print('NOTES AND TAGS MIGRATION (migrate_notes_tags)')
        print('=' * 60)
        print()

        if not no_backup and DB_PATH.exists():
            print('Step 1: Backing up database...')
            try:
                _backup_db()
            except Exception as exc:
                print(f'  ERROR during backup: {exc}')
                return False
        else:
            print('Step 1: Backup skipped.')

        print()
        print('Step 2: Adding notes column to scans table...')
        with db.engine.connect() as conn:
            if _column_exists(conn, 'scans', 'notes'):
                print('  Column already exists — skipping.')
            else:
                conn.execute(text('ALTER TABLE scans ADD COLUMN notes TEXT'))
                conn.commit()
                print('  Column added.')

        print()
        print('Step 3: Adding tags column to scans table...')
        with db.engine.connect() as conn:
            if _column_exists(conn, 'scans', 'tags'):
                print('  Column already exists — skipping.')
            else:
                conn.execute(text('ALTER TABLE scans ADD COLUMN tags TEXT'))
                conn.commit()
                print('  Column added.')

        print()
        print('Migration complete.')
        return True


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent))
    logging.basicConfig(level=logging.WARNING)
    success = migrate()
    sys.exit(0 if success else 1)
