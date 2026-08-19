"""
Migration: add spider_type column to zap_configurations table (kast v3.0.35)

Adds zap_configurations.spider_type VARCHAR(20) NOT NULL DEFAULT 'traditional'.
Existing rows are set to 'traditional' (the safe default for local Docker).
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
        print("MIGRATION: zap_configurations.spider_type (kast v3.0.35)")
        print("=" * 60)

        conn = db.engine.raw_connection()
        try:
            cursor = conn.cursor()

            # Check if column already exists
            cursor.execute("PRAGMA table_info(zap_configurations)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'spider_type' in columns:
                print("Column 'spider_type' already exists — nothing to do.")
                return True

            print("Adding column 'spider_type' to zap_configurations...")
            cursor.execute(
                "ALTER TABLE zap_configurations "
                "ADD COLUMN spider_type VARCHAR(20) NOT NULL DEFAULT 'traditional'"
            )
            conn.commit()
            print("✓ Column added.")

            # Confirm
            cursor.execute(
                "SELECT COUNT(*) FROM zap_configurations WHERE spider_type = 'traditional'"
            )
            count = cursor.fetchone()[0]
            print(f"✓ {count} existing row(s) defaulted to 'traditional'.")

        finally:
            conn.close()

        print()
        print("Migration complete.")
        return True


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
