"""
Migration: create ai_model_presets and ai_endpoint_presets tables.

Safe to re-run; idempotent via CREATE TABLE IF NOT EXISTS.
"""
import logging
import sys
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)


def migrate(app=None):
    """Create preset tables.

    Args:
        app: Flask app instance. If None, create_app() is called.
    """
    if app is None:
        from app import create_app
        app = create_app()

    with app.app_context():
        from app import db

        print('=' * 60)
        print('AI PRESETS MIGRATION (migrate_ai_presets)')
        print('=' * 60)
        print()

        with db.engine.connect() as conn:
            print('Step 1: Creating ai_model_presets table...')
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_model_presets (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id   TEXT NOT NULL,
                    label      TEXT NOT NULL,
                    is_active  BOOLEAN NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
            print('  Done.')

            print('Step 2: Creating ai_endpoint_presets table...')
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_endpoint_presets (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT NOT NULL,
                    url        TEXT NOT NULL,
                    is_active  BOOLEAN NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
            print('  Done.')

        print()
        print('Migration complete.')
        return True


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent))
    logging.basicConfig(level=logging.WARNING)
    success = migrate()
    sys.exit(0 if success else 1)
