"""Migration: add self-service password reset support.

- Adds session_token_version column to users (default 0).
- Creates password_reset_tokens table.
- Creates password_reset_attempts table (rate-limit ledger).

Idempotent via PRAGMA / sqlite_master checks. Safe to re-run.
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

DB_PATH = Path('/var/lib/kast-web/kast.db')


def _backup_db():
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    dest = DB_PATH.with_suffix(f'.pre_password_reset_{ts}.bak')
    shutil.copy2(DB_PATH, dest)
    print(f'  Backup created: {dest}')


def _column_exists(conn, table, column):
    result = conn.execute(text(f'PRAGMA table_info({table})')).fetchall()
    return any(row[1] == column for row in result)


def _table_exists(conn, table):
    result = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
        {'name': table},
    ).fetchone()
    return result is not None


def _index_exists(conn, index_name):
    result = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='index' AND name=:name"),
        {'name': index_name},
    ).fetchone()
    return result is not None


def migrate(app=None, no_backup=False):
    if app is None:
        from app import create_app
        app = create_app()

    with app.app_context():
        from app import db

        print('=' * 60)
        print('PASSWORD RESET MIGRATION (migrate_password_reset)')
        print('=' * 60)

        if not no_backup and DB_PATH.exists():
            _backup_db()

        with db.engine.connect() as conn:
            # 1. users.session_token_version
            if _column_exists(conn, 'users', 'session_token_version'):
                print('  users.session_token_version already exists — skipping.')
            else:
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN session_token_version "
                    "INTEGER NOT NULL DEFAULT 0"
                ))
                print('  users.session_token_version added.')

            # 2. password_reset_tokens table
            if _table_exists(conn, 'password_reset_tokens'):
                print('  password_reset_tokens table already exists — skipping.')
            else:
                conn.execute(text("""
                    CREATE TABLE password_reset_tokens (
                        id            INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id       INTEGER NOT NULL REFERENCES users(id),
                        token_hash    VARCHAR(64) NOT NULL UNIQUE,
                        created_at    DATETIME NOT NULL DEFAULT (datetime('now')),
                        expires_at    DATETIME NOT NULL,
                        used_at       DATETIME,
                        requested_ip  VARCHAR(45)
                    )
                """))
                print('  password_reset_tokens table created.')

            for idx_sql, idx_name in [
                ('CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id)',
                 'ix_password_reset_tokens_user_id'),
                ('CREATE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash)',
                 'ix_password_reset_tokens_token_hash'),
                ('CREATE INDEX ix_password_reset_tokens_expires_at ON password_reset_tokens (expires_at)',
                 'ix_password_reset_tokens_expires_at'),
            ]:
                if _index_exists(conn, idx_name):
                    print(f'  Index {idx_name} already exists — skipping.')
                else:
                    conn.execute(text(idx_sql))
                    print(f'  Index {idx_name} created.')

            # 3. password_reset_attempts table
            if _table_exists(conn, 'password_reset_attempts'):
                print('  password_reset_attempts table already exists — skipping.')
            else:
                conn.execute(text("""
                    CREATE TABLE password_reset_attempts (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address  VARCHAR(45) NOT NULL,
                        email       VARCHAR(120) NOT NULL DEFAULT '',
                        created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
                    )
                """))
                print('  password_reset_attempts table created.')

            for idx_sql, idx_name in [
                ('CREATE INDEX ix_password_reset_attempts_ip_address ON password_reset_attempts (ip_address)',
                 'ix_password_reset_attempts_ip_address'),
                ('CREATE INDEX ix_password_reset_attempts_email ON password_reset_attempts (email)',
                 'ix_password_reset_attempts_email'),
                ('CREATE INDEX ix_password_reset_attempts_created_at ON password_reset_attempts (created_at)',
                 'ix_password_reset_attempts_created_at'),
            ]:
                if _index_exists(conn, idx_name):
                    print(f'  Index {idx_name} already exists — skipping.')
                else:
                    conn.execute(text(idx_sql))
                    print(f'  Index {idx_name} created.')

            conn.commit()

        from utils.migration_tracker import open_db, ensure_table, has_run, record
        mconn = open_db()
        ensure_table(mconn)
        if not has_run(mconn, 'migrate_password_reset.py'):
            record(mconn, 'migrate_password_reset.py')
        mconn.close()

        print('Migration complete.')
        return True


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent))
    no_backup = '--no-backup' in sys.argv
    success = migrate(no_backup=no_backup)
    sys.exit(0 if success else 1)
