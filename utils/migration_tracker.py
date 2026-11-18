"""
Migration tracking helpers for kast-web schema migration scripts.

Usage inside a migrate_*.py script:

    from utils.migration_tracker import (
        open_db, ensure_table, has_run, record, resolve_db_path,
    )

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


def resolve_db_path(default_url='sqlite:///kast.db'):
    """Return the sqlite file Path that DATABASE_URL points at.

    Falls back to default_url when DATABASE_URL is unset or empty, so a caller
    can preserve its own historical default. Relative paths resolve against the
    repo root, so a script run from any working directory targets the same file
    the app would.

    Use this anywhere a migration needs the database file itself (to back it up,
    or to check it exists) rather than a connection. Hardcoding a path there
    means the script operates on a different database than the one its DDL goes
    to, which is how a backup ends up being taken of the wrong file.
    """
    database_url = os.environ.get('DATABASE_URL') or default_url
    if not database_url.startswith('sqlite:///'):
        raise ValueError(
            f"migration_tracker only supports SQLite; got DATABASE_URL={database_url!r}"
        )
    db_path = Path(database_url.replace('sqlite:///', ''))
    if not db_path.is_absolute():
        # Resolve relative to the repo root (one level up from this file).
        db_path = Path(__file__).parent.parent / db_path
    return db_path


def open_db():
    """Open and return a sqlite3 connection using DATABASE_URL from the environment."""
    return sqlite3.connect(resolve_db_path())


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
    """Record script_name as applied (no-op if already present).

    applied_at is supplied explicitly rather than left to a column default.
    When the table is created by db.create_all() from the SchemaMigration
    model it comes out as "applied_at DATETIME NOT NULL" with no DB-level
    default (the model's default=datetime.utcnow is applied Python-side by
    SQLAlchemy, not by SQLite), so an insert that omits the column violates
    NOT NULL -- and INSERT OR IGNORE swallows that silently, leaving the
    table permanently empty.
    """
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (script_name, applied_at) "
        "VALUES (?, datetime('now'))",
        (script_name,),
    )
    conn.commit()
