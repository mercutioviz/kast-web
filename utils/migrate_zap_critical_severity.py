"""
Migration: add critical_alerts column to zap_scan_progress table

Adds zap_scan_progress.critical_alerts INTEGER DEFAULT 0.
Existing rows default to 0 (no critical alerts recorded before kast
added the "critical" severity level).
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
        print("MIGRATION: zap_scan_progress.critical_alerts")
        print("=" * 60)

        conn = db.engine.raw_connection()
        try:
            cursor = conn.cursor()

            # Check if column already exists
            cursor.execute("PRAGMA table_info(zap_scan_progress)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'critical_alerts' in columns:
                print("Column 'critical_alerts' already exists — nothing to do.")
                return True

            print("Adding column 'critical_alerts' to zap_scan_progress...")
            cursor.execute(
                "ALTER TABLE zap_scan_progress "
                "ADD COLUMN critical_alerts INTEGER DEFAULT 0"
            )
            conn.commit()
            print("✓ Column added.")

            # Confirm
            cursor.execute(
                "SELECT COUNT(*) FROM zap_scan_progress WHERE critical_alerts = 0"
            )
            count = cursor.fetchone()[0]
            print(f"✓ {count} existing row(s) defaulted to 0.")

        finally:
            conn.close()

        print()
        print("Migration complete.")
        return True


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
