"""
Migration: expanded logo format support

Adds to report_logos:
  render_path VARCHAR(500)  - PNG / sanitized SVG derivative handed to kast
  render_mime VARCHAR(100)  - MIME type of that derivative
  width       INTEGER       - pixel width (display only)
  height      INTEGER       - pixel height (display only)

Backfills existing rows so their derivative points at the original file
(every pre-existing logo is PNG or JPEG, both of which kast embeds directly),
and creates the uploads/logos/render/ directory.

Idempotent: safe to run multiple times.

Usage:
  python3 utils/migrate_logo_formats.py [--non-interactive]
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load .env before importing the app so DATABASE_URL and other config resolve
# the same way they do under run.py / celery_worker.py. Without this, the app
# falls back to a relative sqlite path and errors with "unable to open
# database file" on a production install.
from dotenv import load_dotenv
load_dotenv(REPO_ROOT / '.env')

from app import create_app, db

NEW_COLUMNS = [
    ('render_path', 'VARCHAR(500)'),
    ('render_mime', 'VARCHAR(100)'),
    ('width', 'INTEGER'),
    ('height', 'INTEGER'),
]


def migrate():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("MIGRATION: report_logos expanded format support")
        print("=" * 60)

        conn = db.engine.raw_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(report_logos)")
            columns = [row[1] for row in cursor.fetchall()]

            added = 0
            for name, column_type in NEW_COLUMNS:
                if name in columns:
                    print(f"Column '{name}' already exists - skipping.")
                    continue
                print(f"Adding column '{name}' to report_logos...")
                cursor.execute(
                    f"ALTER TABLE report_logos ADD COLUMN {name} {column_type}"
                )
                added += 1

            if added:
                conn.commit()
                print(f"✓ {added} column(s) added.")

            # Backfill: existing logos are PNG/JPEG, usable by kast as-is
            cursor.execute(
                "UPDATE report_logos "
                "SET render_path = file_path, render_mime = mime_type "
                "WHERE render_path IS NULL"
            )
            backfilled = cursor.rowcount
            conn.commit()
            print(f"✓ {backfilled} existing logo(s) backfilled to use the original file.")

            cursor.execute("SELECT COUNT(*) FROM report_logos")
            total = cursor.fetchone()[0]
            print(f"✓ {total} logo row(s) total.")

        finally:
            conn.close()

        render_dir = Path(app.root_path) / 'static' / 'uploads' / 'logos' / 'render'
        render_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Render directory ready: {render_dir}")

        print()
        print("Migration complete.")
        print("Note: Pillow and defusedxml are now required "
              "(pip install -r requirements.txt).")
        return True


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
