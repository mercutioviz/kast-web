"""
Migration: add zap_profile column to zap_configurations table

Adds zap_configurations.zap_profile VARCHAR(20), nullable.
NULL means "kast default" (no --zap-profile flag passed).
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
        print("MIGRATION: zap_configurations.zap_profile")
        print("=" * 60)

        conn = db.engine.raw_connection()
        try:
            cursor = conn.cursor()

            # Check if column already exists
            cursor.execute("PRAGMA table_info(zap_configurations)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'zap_profile' in columns:
                print("Column 'zap_profile' already exists — nothing to do.")
                return True

            print("Adding column 'zap_profile' to zap_configurations...")
            cursor.execute(
                "ALTER TABLE zap_configurations "
                "ADD COLUMN zap_profile VARCHAR(20)"
            )
            conn.commit()
            print("✓ Column added.")

            # Confirm
            cursor.execute(
                "SELECT COUNT(*) FROM zap_configurations WHERE zap_profile IS NULL"
            )
            count = cursor.fetchone()[0]
            print(f"✓ {count} existing row(s) defaulted to NULL (kast default profile).")

        finally:
            conn.close()

        print()
        print("Migration complete.")
        return True


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
