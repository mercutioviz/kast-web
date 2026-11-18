#!/usr/bin/env python3
"""Report drift between the SQLAlchemy models and the test database schema.

Why this exists
---------------
test-env-up.sh builds the schema through db.create_all(), which creates
missing *tables* but never adds *columns* to tables that already exist, and
it does not run utils/migrate_*.py. A persistent test database therefore
freezes at whatever column set it had when it was created, while the models
move on. On 2026-11-17 the test DB was 11 columns behind across 5 tables and
the first symptom was an OperationalError deep inside the seed step:

    no such column: users.session_token_version

This turns that into an immediate, readable list.

Exit codes:
    0  no drift (or nothing to check yet -- fresh/empty database)
    1  drift found; the missing tables and columns are listed on stdout
    2  could not run the check

Refuses to run against a non-test DATABASE_URL, mirroring seed_test_admin.py.
"""
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def main():
    db_url = os.environ.get('DATABASE_URL', '')
    if 'kast-web-test' not in db_url:
        sys.exit(
            f"refusing to check: DATABASE_URL does not look like a test DB ({db_url!r})."
        )
    if not db_url.startswith('sqlite:///'):
        sys.exit(f"only SQLite is supported; got {db_url!r}")

    db_path = Path(db_url.replace('sqlite:///', ''))
    if not db_path.exists() or db_path.stat().st_size == 0:
        # Fresh database: create_all() will build it correctly from the models.
        return 0

    from app import db
    import app.models  # noqa: F401  -- registers every table on db.metadata

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    have_tables = {r[0] for r in cur.fetchall()}
    if not have_tables:
        return 0  # tables not created yet

    missing_tables = []
    missing_columns = []
    for tname, tbl in sorted(db.metadata.tables.items()):
        if tname not in have_tables:
            missing_tables.append(tname)
            continue
        cur.execute(f'PRAGMA table_info("{tname}")')
        have_cols = {r[1] for r in cur.fetchall()}
        for col in tbl.columns:
            if col.name not in have_cols:
                missing_columns.append((tname, col.name, str(col.type)))
    con.close()

    if not missing_tables and not missing_columns:
        return 0

    print(f"Schema drift in {db_path}:")
    print()
    if missing_tables:
        # create_all() will add these on the next startup, so they are only
        # worth reporting, not blocking on.
        print("  Missing tables (db.create_all() will create these):")
        for t in missing_tables:
            print(f"    {t}")
        print()
    if missing_columns:
        print("  Missing columns (db.create_all() will NOT add these):")
        width = max(len(f"{t}.{c}") for t, c, _ in missing_columns)
        for t, c, ty in missing_columns:
            print(f"    {f'{t}.{c}':<{width}}  {ty}")
        print()
        print("  The models expect columns this database does not have, so the app")
        print("  will fail at the first query touching one of them. Either:")
        print()
        print("    - recreate the test database from the current models:")
        print("        scripts/test-env-down.sh --wipe && scripts/test-env-up.sh")
        print("      (fastest; discards test data, which test-env-up re-seeds)")
        print()
        print("    - or apply the matching utils/migrate_*.py against the test DB:")
        print(f"        DATABASE_URL='{db_url}' venv/bin/python3 utils/migrate_<name>.py")
        print()
    return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"schema check failed to run: {exc}", file=sys.stderr)
        sys.exit(2)
