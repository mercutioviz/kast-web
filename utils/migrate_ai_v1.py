"""
Migration: add ai_settings and ai_summaries tables (Phase C).

Safe to re-run; idempotent via PRAGMA table_info checks.
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
    dest = DB_PATH.with_suffix(f'.pre_ai_v1_{ts}.bak')
    shutil.copy2(DB_PATH, dest)
    print(f'  Backup created: {dest}')


def _table_exists(conn, table):
    result = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {'t': table}
    ).fetchone()
    return result is not None


def migrate(app=None, no_backup=False):
    """Add AI tables to the database.

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
        print('PHASE C: AI TABLES MIGRATION (migrate_ai_v1)')
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
        print('Step 2: Creating ai_settings table...')
        with db.engine.connect() as conn:
            if _table_exists(conn, 'ai_settings'):
                print('  ai_settings already exists — skipping.')
            else:
                conn.execute(text("""
                    CREATE TABLE ai_settings (
                        id INTEGER PRIMARY KEY,
                        ai_enabled BOOLEAN NOT NULL DEFAULT 0,
                        default_mode VARCHAR(10) NOT NULL DEFAULT 'review',
                        monthly_budget_tokens INTEGER NOT NULL DEFAULT 100000,
                        current_period_tokens INTEGER NOT NULL DEFAULT 0,
                        period_reset_date DATETIME,
                        api_key_encrypted TEXT,
                        model_id VARCHAR(100) NOT NULL DEFAULT 'claude-sonnet-4-6',
                        updated_at DATETIME,
                        updated_by INTEGER REFERENCES users(id)
                    )
                """))
                conn.execute(text("""
                    INSERT INTO ai_settings (id, ai_enabled, default_mode,
                        monthly_budget_tokens, current_period_tokens, model_id)
                    VALUES (1, 0, 'review', 100000, 0, 'claude-sonnet-4-6')
                """))
                conn.commit()
                print('  ai_settings created and seeded with default row (id=1).')

        print()
        print('Step 3: Creating ai_summaries table...')
        with db.engine.connect() as conn:
            if _table_exists(conn, 'ai_summaries'):
                print('  ai_summaries already exists — skipping.')
            else:
                conn.execute(text("""
                    CREATE TABLE ai_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        scan_id INTEGER NOT NULL UNIQUE REFERENCES scans(id),
                        prompt_version VARCHAR(50) NOT NULL DEFAULT 'exec_summary_v1',
                        raw_text TEXT,
                        edited_text TEXT,
                        reviewed_by_user_id INTEGER REFERENCES users(id),
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        tokens_in INTEGER NOT NULL DEFAULT 0,
                        tokens_out INTEGER NOT NULL DEFAULT 0,
                        cost_usd REAL NOT NULL DEFAULT 0.0,
                        generated_at DATETIME,
                        error_message TEXT
                    )
                """))
                conn.execute(text(
                    "CREATE INDEX ix_ai_summaries_scan_id ON ai_summaries (scan_id)"
                ))
                conn.execute(text(
                    "CREATE INDEX ix_ai_summaries_status ON ai_summaries (status)"
                ))
                conn.commit()
                print('  ai_summaries created.')

        print()
        print('Migration complete.')
        return True


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent))
    logging.basicConfig(level=logging.WARNING)
    success = migrate()
    sys.exit(0 if success else 1)
