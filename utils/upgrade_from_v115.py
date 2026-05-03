"""
upgrade_from_v115.py — Migrate a kast-web 1.15 installation to v2.0.

What this script does:
  1. Verifies both installations exist and are healthy
  2. Stops the v1.15 services (kast-web, kast-celery)
  3. Backs up the v2.0 database (if one already exists)
  4. Copies /var/lib/kast-web/kast.db  →  /var/lib/kast-web2/kast.db
  5. Runs the three v2.0-only delta migrations against the copied DB:
       migrate_cloud_v2.py  (cloud_credentials / cloud_scans / cloud_orphans tables)
       migrate_ai_v1.py     (ai_settings / ai_summaries tables)
       migrate_ai_byok.py   (anthropic_api_key_encrypted column on users)
  6. Restarts the v2.0 services (kast-web2, kast-celery2)
  7. Runs a basic health check against http://127.0.0.1:8001/
  8. Reports a summary

The v1.15 database and services are LEFT INTACT throughout — this is a
copy, not a move. v1.15 can be re-started manually if anything goes wrong.

Requirements:
  - Run as a user with sudo privileges (needed for systemctl and file copy)
  - Both /opt/kast-web and /opt/kast-web2 must exist
  - /var/lib/kast-web/kast.db must exist and be readable

Usage:
  sudo python3 utils/upgrade_from_v115.py [--dry-run] [--skip-service-stop]
"""
import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ------------------------------------------------------------------ constants

V115_DB     = Path('/var/lib/kast-web/kast.db')
V2_DB       = Path('/var/lib/kast-web2/kast.db')
V115_APPDIR = Path('/opt/kast-web')
V2_APPDIR   = Path('/opt/kast-web2')

V115_SERVICES = ['kast-web', 'kast-celery']
V2_SERVICES   = ['kast-web2', 'kast-celery2']

HEALTH_URL = 'http://127.0.0.1:8001/'

DELTA_MIGRATIONS = [
    'utils/migrate_cloud_v2.py',
    'utils/migrate_ai_v1.py',
    'utils/migrate_ai_byok.py',
]

# ------------------------------------------------------------------ helpers

def red(msg):    print(f'\033[31m{msg}\033[0m')
def green(msg):  print(f'\033[32m{msg}\033[0m')
def yellow(msg): print(f'\033[33m{msg}\033[0m')
def header(msg): print(f'\n{"=" * 60}\n{msg}\n{"=" * 60}')


def run(cmd, check=True, capture=False):
    """Run a shell command list. Returns CompletedProcess."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )


def service_active(name):
    result = subprocess.run(
        ['systemctl', 'is-active', name],
        capture_output=True, text=True
    )
    return result.stdout.strip() == 'active'


def stop_services(names, dry_run):
    for name in names:
        if service_active(name):
            yellow(f'  Stopping {name}...')
            if not dry_run:
                run(['sudo', 'systemctl', 'stop', name])
            else:
                yellow(f'  [dry-run] would stop {name}')
        else:
            print(f'  {name} is not running — skipping stop.')


def start_services(names, dry_run):
    for name in names:
        yellow(f'  Starting {name}...')
        if not dry_run:
            run(['sudo', 'systemctl', 'start', name])
        else:
            yellow(f'  [dry-run] would start {name}')


def health_check(url, retries=6, delay=5):
    import urllib.request
    import urllib.error
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                # 200 or 302 (login redirect) both mean the app is up
                if resp.status in (200, 302):
                    return True
        except urllib.error.HTTPError as e:
            if e.code == 302:
                return True
        except Exception:
            pass
        if attempt < retries:
            print(f'  Health check attempt {attempt}/{retries} failed — retrying in {delay}s...')
            time.sleep(delay)
    return False


def run_migration(script_path, v2_appdir, dry_run):
    """Run a migration script inside the v2.0 venv."""
    full_path = v2_appdir / script_path
    if not full_path.exists():
        red(f'  Migration script not found: {full_path}')
        return False

    cmd = [
        'sudo', '-u', 'www-data', 'bash', '-c',
        f'cd {v2_appdir} && set -a && source .env && set +a && '
        f'venv/bin/python {script_path}'
    ]

    if dry_run:
        yellow(f'  [dry-run] would run: {script_path}')
        return True

    print(f'  Running {script_path}...')
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        red(f'  Migration {script_path} exited with code {result.returncode}')
        return False
    return True


# ------------------------------------------------------------------ main

def main():
    parser = argparse.ArgumentParser(description='Upgrade kast-web 1.15 → 2.0')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print what would happen without making changes')
    parser.add_argument('--skip-service-stop', action='store_true',
                        help='Do not stop v1.15 services (for testing only — risk of DB corruption)')
    args = parser.parse_args()

    if args.dry_run:
        yellow('DRY-RUN MODE — no changes will be made\n')

    # ---------------------------------------------------------------- preflight

    header('STEP 1: Preflight checks')

    errors = []

    if not V115_APPDIR.exists():
        errors.append(f'v1.15 app directory not found: {V115_APPDIR}')
    if not V2_APPDIR.exists():
        errors.append(f'v2.0 app directory not found: {V2_APPDIR}')
    if not V115_DB.exists():
        errors.append(f'v1.15 database not found: {V115_DB}')

    for mig in DELTA_MIGRATIONS:
        if not (V2_APPDIR / mig).exists():
            errors.append(f'Missing migration script: {V2_APPDIR / mig}')

    if errors:
        for e in errors:
            red(f'  ERROR: {e}')
        sys.exit(1)

    green(f'  v1.15 app:      {V115_APPDIR}')
    green(f'  v1.15 database: {V115_DB}  ({V115_DB.stat().st_size:,} bytes)')
    green(f'  v2.0 app:       {V2_APPDIR}')
    green(f'  v2.0 database:  {V2_DB}  (will be replaced)')
    print()
    for mig in DELTA_MIGRATIONS:
        green(f'  Migration: {mig}')

    # ---------------------------------------------------------------- stop v1.15

    header('STEP 2: Stop v1.15 services')

    if args.skip_service_stop:
        yellow('  --skip-service-stop specified; skipping (risk: DB may be written during copy)')
    else:
        stop_services(V115_SERVICES, args.dry_run)
        green('  v1.15 services stopped.')

    # ---------------------------------------------------------------- backup v2 db

    header('STEP 3: Back up existing v2.0 database (if present)')

    if V2_DB.exists():
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_path = V2_DB.with_suffix(f'.pre_upgrade_from_v115_{ts}.bak')
        if not args.dry_run:
            shutil.copy2(V2_DB, backup_path)
            green(f'  Backup created: {backup_path}')
        else:
            yellow(f'  [dry-run] would create backup: {backup_path}')
    else:
        print(f'  No existing v2.0 database found — nothing to back up.')

    # ---------------------------------------------------------------- copy db

    header('STEP 4: Copy v1.15 database → v2.0')

    if not args.dry_run:
        V2_DB.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(V115_DB, V2_DB)
        # Ensure www-data owns the file
        run(['sudo', 'chown', 'www-data:www-data', str(V2_DB)])
        run(['sudo', 'chmod', '660', str(V2_DB)])
        green(f'  Copied {V115_DB} → {V2_DB}')
        green(f'  Size: {V2_DB.stat().st_size:,} bytes')
    else:
        yellow(f'  [dry-run] would copy {V115_DB} → {V2_DB}')

    # ---------------------------------------------------------------- run migrations

    header('STEP 5: Run delta migrations')

    for mig in DELTA_MIGRATIONS:
        success = run_migration(mig, V2_APPDIR, args.dry_run)
        if not success:
            red(f'\nMigration failed: {mig}')
            red('v2.0 services were NOT started. Fix the issue and re-run.')
            red(f'v1.15 services ({", ".join(V115_SERVICES)}) remain stopped.')
            red(f'Restore v1.15 services with: sudo systemctl start {" ".join(V115_SERVICES)}')
            sys.exit(1)

    green('  All migrations completed.')

    # ---------------------------------------------------------------- start v2

    header('STEP 6: Start v2.0 services')

    start_services(V2_SERVICES, args.dry_run)

    if not args.dry_run:
        print(f'  Waiting for v2.0 to come up...')
        time.sleep(3)

    # ---------------------------------------------------------------- health check

    header('STEP 7: Health check')

    if args.dry_run:
        yellow(f'  [dry-run] would check {HEALTH_URL}')
    else:
        if health_check(HEALTH_URL):
            green(f'  v2.0 is responding at {HEALTH_URL}')
        else:
            red(f'  Health check failed — {HEALTH_URL} did not respond.')
            red('  Check: sudo journalctl -u kast-web2 -n 50')
            red('  Check: sudo tail /var/log/kast-web2/error.log')
            sys.exit(1)

    # ---------------------------------------------------------------- summary

    header('UPGRADE COMPLETE')
    green('  v1.15 database copied and migrated to v2.0.')
    green('  v2.0 services are running.')
    print()
    yellow('  NOTE: v1.15 services were stopped and remain stopped.')
    yellow(f'  To restore v1.15: sudo systemctl start {" ".join(V115_SERVICES)}')
    yellow('  v1.15 database was NOT modified — it is safe to roll back.')
    print()
    print('  Next steps:')
    print('    1. Log into kast-web 2.0 and verify your data is present.')
    print('    2. Review /admin/cloud/credentials if you used ZAP cloud mode.')
    print('    3. Once satisfied, disable v1.15 at boot:')
    for svc in V115_SERVICES:
        print(f'       sudo systemctl disable {svc}')


if __name__ == '__main__':
    main()
