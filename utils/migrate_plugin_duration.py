"""Migration: add started_at column to scan_results table (plugin duration tracking)."""
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
    dest = DB_PATH.with_suffix(f'.pre_plugin_duration_{ts}.bak')
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
        print('PLUGIN DURATION MIGRATION (migrate_plugin_duration)')
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
        print('Step 2: Adding started_at column to scan_results table...')
        with db.engine.connect() as conn:
            if _column_exists(conn, 'scan_results', 'started_at'):
                print('  Column already exists — skipping.')
            else:
                conn.execute(text('ALTER TABLE scan_results ADD COLUMN started_at DATETIME'))
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
