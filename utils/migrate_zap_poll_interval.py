"""
Migration: add poll_interval_seconds column to zap_configurations table

Adds zap_configurations.poll_interval_seconds INTEGER NOT NULL DEFAULT 30.
Existing rows are set to 30 (the previous hardcoded kast default).
Idempotent: safe to run multiple times.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, db


def migrate():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("MIGRATION: zap_configurations.poll_interval_seconds")
        print("=" * 60)

        conn = db.engine.raw_connection()
        try:
            cursor = conn.cursor()

            # Check if column already exists
            cursor.execute("PRAGMA table_info(zap_configurations)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'poll_interval_seconds' in columns:
                print("Column 'poll_interval_seconds' already exists — nothing to do.")
                return True

            print("Adding column 'poll_interval_seconds' to zap_configurations...")
            cursor.execute(
                "ALTER TABLE zap_configurations "
                "ADD COLUMN poll_interval_seconds INTEGER NOT NULL DEFAULT 30"
            )
            conn.commit()
            print("✓ Column added.")

            # Confirm
            cursor.execute(
                "SELECT COUNT(*) FROM zap_configurations WHERE poll_interval_seconds = 30"
            )
            count = cursor.fetchone()[0]
            print(f"✓ {count} existing row(s) defaulted to 30 seconds.")

        finally:
            conn.close()

        print()
        print("Migration complete.")
        return True


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
