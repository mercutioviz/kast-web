#!/usr/bin/env python3
"""Idempotent seed of the t_admin user for the test environment.

Reads TEST_ADMIN_USERNAME, TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD from env
(loaded by test-env-up.sh from .env.test). Creates the user if missing;
otherwise leaves it untouched. Triggers db.create_all() via create_app().

Refuses to run against a non-test DATABASE_URL to avoid accidentally
seeding prod.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    db_url = os.environ.get('DATABASE_URL', '')
    if 'kast-web-test' not in db_url:
        sys.exit(
            f"refusing to seed: DATABASE_URL does not look like a test DB ({db_url!r}). "
            "Set DATABASE_URL to a path under /var/lib/kast-web-test/."
        )

    username = os.environ.get('TEST_ADMIN_USERNAME')
    email = os.environ.get('TEST_ADMIN_EMAIL')
    password = os.environ.get('TEST_ADMIN_PASSWORD')
    if not (username and email and password):
        sys.exit("TEST_ADMIN_USERNAME / TEST_ADMIN_EMAIL / TEST_ADMIN_PASSWORD must be set.")

    from app import create_app, db
    from app.models import User

    app = create_app('development')
    with app.app_context():
        existing = User.query.filter_by(username=username).first()
        if existing:
            print(f"user {username!r} already exists (id={existing.id}, role={existing.role}); leaving untouched")
            return

        admin = User(
            username=username,
            email=email,
            first_name='Test',
            last_name='Admin',
            role='admin',
            is_active=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"created admin user {username!r} (id={admin.id})")


if __name__ == '__main__':
    main()
