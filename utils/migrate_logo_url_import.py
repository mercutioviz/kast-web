"""
Migration: logo URL import + move logo storage out of the public static tree

This migration:
1. Adds report_logos.source_url VARCHAR(2048) (NULL for uploaded logos)
2. Creates <LOGO_STORAGE_DIR>/{originals,render,staging}
3. Moves existing logo files out of app/static/uploads/logos/ into the new
   storage directory and rewrites file_path / render_path on every row

Why the move: nginx serves /static directly from disk (see
/etc/nginx/sites-available/kast-web), so every file under app/static/ is
publicly readable with no authentication and none of the security headers the
/logos/<id> route sets. Logo files are user-supplied content and must not live
there.

Set LOGO_STORAGE_DIR in .env before running on a production install, e.g.
  LOGO_STORAGE_DIR=/var/lib/kast-web/logos

Back up your database before running. Idempotent: safe to run multiple times.

Usage:
  python3 utils/migrate_logo_url_import.py [--non-interactive]
"""
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load .env before importing the app so DATABASE_URL and LOGO_STORAGE_DIR
# resolve the same way they do under run.py / celery_worker.py.
from dotenv import load_dotenv
load_dotenv(REPO_ROOT / '.env')

from app import create_app, db


def _add_source_url_column(cursor, conn):
    """Step 1: add the source_url column if it is not already there."""
    cursor.execute("PRAGMA table_info(report_logos)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'source_url' in columns:
        print("Column 'source_url' already exists - skipping.")
        return

    print("Adding column 'source_url' to report_logos...")
    cursor.execute(
        "ALTER TABLE report_logos ADD COLUMN source_url VARCHAR(2048)"
    )
    conn.commit()
    print("✓ Column added.")


def _relocate_files(cursor, conn, app):
    """Steps 2-3: create the new storage tree and move files into it."""
    from app.utils import (
        get_logo_render_dir,
        get_logo_staging_dir,
        get_logo_storage_dir,
        get_logo_uploads_dir,
    )

    storage_dir = get_logo_storage_dir()
    originals_dir = get_logo_uploads_dir()
    render_dir = get_logo_render_dir()
    staging_dir = get_logo_staging_dir()

    for directory in (originals_dir, render_dir, staging_dir):
        directory.mkdir(parents=True, exist_ok=True)
    print(f"✓ Storage tree ready under {storage_dir}")

    legacy_dir = Path(app.root_path) / 'static' / 'uploads' / 'logos'
    legacy_render_dir = legacy_dir / 'render'

    cursor.execute(
        "SELECT id, file_path, render_path FROM report_logos ORDER BY id"
    )
    rows = cursor.fetchall()

    counters = {'moved': 0}
    missing = []

    def relocate(current_path, target_dir, logo_id):
        """
        Move one file into the new tree.

        Returns:
            str: the new path when the row should be rewritten, else None
        """
        if not current_path:
            return None

        current = Path(current_path)

        # Already under the new storage root
        try:
            current.relative_to(storage_dir)
            return None
        except ValueError:
            pass

        # Only relocate things that actually came from the legacy tree
        if legacy_dir not in current.parents:
            return None

        target = target_dir / current.name

        if current.exists():
            if target.exists():
                current.unlink()        # already copied over on a prior run
            else:
                shutil.move(str(current), str(target))
                counters['moved'] += 1
            return str(target)

        if target.exists():
            return str(target)          # moved earlier, path not yet rewritten

        missing.append(f'logo {logo_id}: {current}')
        return None

    rewritten = 0

    for logo_id, file_path, render_path in rows:
        # file_path and render_path point at the same file when the upload
        # needed no conversion. Move it once and mirror the result, but only
        # if the move actually succeeded.
        shared = bool(file_path) and render_path == file_path

        new_file = relocate(file_path, originals_dir, logo_id)
        if shared:
            new_render = new_file
        else:
            new_render = relocate(render_path, render_dir, logo_id)

        updates = {}
        if new_file:
            updates['file_path'] = new_file
        if new_render:
            updates['render_path'] = new_render

        if updates:
            assignments = ', '.join(f'{col} = ?' for col in updates)
            cursor.execute(
                f"UPDATE report_logos SET {assignments} WHERE id = ?",
                (*updates.values(), logo_id),
            )
            rewritten += 1

    conn.commit()
    moved = counters['moved']

    print(f"✓ Moved {moved} file(s) out of the public static tree.")
    print(f"✓ Rewrote paths on {rewritten} logo row(s).")

    if missing:
        print(f"⚠ {len(missing)} file(s) referenced by the database were not found:")
        for item in missing[:10]:
            print(f"    {item}")
        print("  Those logos will fall back to the bundled default logo.")

    # Anything left in the legacy tree is unreferenced by the database, but it
    # is still user-uploaded content sitting in a publicly-served directory -
    # which is the exposure this migration exists to close. Move it somewhere
    # private rather than deleting it; the operator decides what to discard.
    leftovers = []
    for directory in (legacy_render_dir, legacy_dir):
        if directory.exists():
            leftovers += [p for p in directory.iterdir() if p.is_file()]

    if leftovers:
        orphan_dir = storage_dir / 'orphaned'
        orphan_dir.mkdir(parents=True, exist_ok=True)
        quarantined = 0
        for item in leftovers:
            target = orphan_dir / item.name
            if target.exists():
                item.unlink()
            else:
                shutil.move(str(item), str(target))
            quarantined += 1
        print(f"✓ Moved {quarantined} unreferenced file(s) out of the public")
        print(f"  directory into {orphan_dir}")
        print("  Nothing in the database points at them. Review and delete at")
        print("  your convenience.")

    if legacy_dir.exists():
        print(f"✓ Legacy directory is now empty: {legacy_dir}")
        print(f"  Safe to remove: rm -rf {legacy_dir}")


def migrate():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("MIGRATION: logo URL import + storage relocation")
        print("=" * 60)

        conn = db.engine.raw_connection()
        try:
            cursor = conn.cursor()
            _add_source_url_column(cursor, conn)
            print()
            _relocate_files(cursor, conn, app)
        finally:
            conn.close()

        print()
        print("Migration complete.")
        print("Reminder: logo files are now served only via /logos/<id>.")
        return True


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
