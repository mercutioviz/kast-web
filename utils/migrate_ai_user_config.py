"""
Migration: add ai_model_override and ai_base_url columns to users table.

Safe to re-run; idempotent via PRAGMA table_info check.
"""
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)

DB_PATH = Path('/var/lib/kast-web2/kast.db')


def _backup_db():
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    dest = DB_PATH.with_suffix(f'.pre_ai_user_config_{ts}.bak')
    shutil.copy2(DB_PATH, dest)
    print(f'  Backup created: {dest}')


def _column_exists(conn, table, column):
    result = conn.execute(text(f'PRAGMA table_info({table})')).fetchall()
    return any(row[1] == column for row in result)


def migrate(app=None, no_backup=False):
    """Add ai_model_override and ai_base_url to users table.

    Args:
        app: Flask app instance. If None, create_app() is called.
        no_backup: Skip DB file backup (use in tests against :memory:).
    """
    if app is None:
        from app import create_app
        app = create_app()

    with app.app_context():
        from app import db

        print('=' * 60)
        print('AI USER CONFIG MIGRATION (migrate_ai_user_config)')
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
        print('Step 2: Adding ai_model_override to users table...')
        with db.engine.connect() as conn:
            if _column_exists(conn, 'users', 'ai_model_override'):
                print('  Column already exists — skipping.')
            else:
                conn.execute(text(
                    'ALTER TABLE users ADD COLUMN ai_model_override TEXT'
                ))
                conn.commit()
                print('  Column added.')

        print()
        print('Step 3: Adding ai_base_url to users table...')
        with db.engine.connect() as conn:
            if _column_exists(conn, 'users', 'ai_base_url'):
                print('  Column already exists — skipping.')
            else:
                conn.execute(text(
                    'ALTER TABLE users ADD COLUMN ai_base_url TEXT'
                ))
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
