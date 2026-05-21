"""Migration: add indexes on scans.status and scans.tags."""
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

DB_PATH = Path('/var/lib/kast-web/kast.db')


def _backup_db():
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    dest = DB_PATH.with_suffix(f'.pre_scan_indexes_{ts}.bak')
    shutil.copy2(DB_PATH, dest)
    print(f'  Backup created: {dest}')


def _index_exists(conn, index_name):
    result = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='index' AND name=:name"),
        {'name': index_name}
    ).fetchone()
    return result is not None


def migrate(app=None, no_backup=False):
    if app is None:
        from app import create_app
        app = create_app()

    with app.app_context():
        from app import db

        if not no_backup and DB_PATH.exists():
            _backup_db()

        with db.engine.connect() as conn:
            created = []

            if not _index_exists(conn, 'ix_scans_status'):
                conn.execute(text('CREATE INDEX ix_scans_status ON scans (status)'))
                created.append('ix_scans_status')
                print('  Created index: ix_scans_status')
            else:
                print('  Index ix_scans_status already exists, skipping')

            if not _index_exists(conn, 'ix_scans_tags'):
                conn.execute(text('CREATE INDEX ix_scans_tags ON scans (tags)'))
                created.append('ix_scans_tags')
                print('  Created index: ix_scans_tags')
            else:
                print('  Index ix_scans_tags already exists, skipping')

            conn.commit()

        from utils.migration_tracker import open_db, ensure_table, has_run, record
        mconn = open_db()
        ensure_table(mconn)
        if not has_run(mconn, 'migrate_scan_indexes.py'):
            record(mconn, 'migrate_scan_indexes.py')
        mconn.close()

        if created:
            print(f'  Migration complete: {len(created)} index(es) created.')
        else:
            print('  Migration complete: nothing to do.')


if __name__ == '__main__':
    import os
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    no_backup = '--no-backup' in sys.argv
    migrate(no_backup=no_backup)
