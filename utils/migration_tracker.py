"""
Migration tracking helpers for kast-web schema migration scripts.

Usage inside a migrate_*.py script:

    from utils.migration_tracker import open_db, ensure_table, has_run, record

    conn = open_db()
    ensure_table(conn)

    SCRIPT = 'migrate_my_feature.py'
    if has_run(conn, SCRIPT):
        print(f"{SCRIPT}: already applied, skipping")
    else:
        # ... apply schema changes ...
        record(conn, SCRIPT)
        print(f"{SCRIPT}: applied")

    conn.close()

The schema_migrations table is also a SQLAlchemy model (app.models.SchemaMigration)
so it shows up in the Flask-Admin DB explorer and is created by db.create_all()
on first startup.
"""

import os
import sqlite3
from pathlib import Path


def open_db():
    """Open and return a sqlite3 connection using DATABASE_URL from the environment."""
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///kast.db')
    if not database_url.startswith('sqlite:///'):
        raise ValueError(
            f"migration_tracker only supports SQLite; got DATABASE_URL={database_url!r}"
        )
    db_path = Path(database_url.replace('sqlite:///', ''))
    if not db_path.is_absolute():
        # Resolve relative to the repo root (one level up from this file).
        db_path = Path(__file__).parent.parent / db_path
    return sqlite3.connect(db_path)


def ensure_table(conn):
    """Create the schema_migrations table if it does not already exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            script_name TEXT    UNIQUE NOT NULL,
            applied_at  TIMESTAMP DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def has_run(conn, script_name):
    """Return True if script_name has already been recorded in schema_migrations."""
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE script_name = ?", (script_name,)
    ).fetchone()
    return row is not None


def record(conn, script_name):
    """Record script_name as applied (no-op if already present)."""
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (script_name) VALUES (?)",
        (script_name,),
    )
    conn.commit()
