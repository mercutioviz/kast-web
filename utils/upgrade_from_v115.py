"""
upgrade_from_v115.py — Migrate a kast-web 1.15 installation to v2.0.

kast-web 2.0 installs **in place** at /opt/kast-web with data under
/var/lib/kast-web, using the kast-web / kast-celery services. There is no
permanent second install path. To keep the upgrade reversible anyway, 2.0 is
staged alongside the running 1.15 and only swapped in once it has been proved
to work:

  1. Verifies the live 1.15 install and the staged 2.0 tree
  2. Stops the 1.15 services so the database is quiescent
  3. COPIES /var/lib/kast-web/kast.db -> /var/lib/kast-web-new/kast.db
  4. Runs the six 2.0-only delta migrations against the COPY:
       migrate_cloud_v2.py       (cloud_credentials / cloud_scans / cloud_orphans)
       migrate_ai_v1.py          (ai_settings / ai_summaries)
       migrate_ai_byok.py        (users.anthropic_api_key_encrypted)
       migrate_ai_user_config.py (users.ai_model_override, ai_base_url)
       migrate_ai_presets.py     (ai_model_presets, ai_endpoint_presets)
       migrate_ai_scan_flag.py   (scans.generate_ai_summary)
  5. Boots the staged 2.0 on a temporary port and health-checks it, WITHOUT
     installing a second systemd unit
  6. Cuts over by renaming directories: the 1.15 install is parked at
     /opt/kast-web-v115 and /var/lib/kast-web-v115, and the staged tree takes
     its place
  7. Starts the kast-web / kast-celery services and health-checks again
  8. Reports a summary, including how to roll back

The 1.15 database is never modified — it is copied, and after cutover the
original is parked intact at /var/lib/kast-web-v115/kast.db. Rolling back is
renaming the two pairs of directories back and restarting the services; the
script prints the exact commands.

The staged .env must contain the FINAL configuration (DATABASE_URL pointing at
/var/lib/kast-web/kast.db). During staging this script overrides DATABASE_URL
on the command line so migrations and the health check run against the copy,
which means nothing in .env needs rewriting at cutover.

Requirements:
  - Run as a user with sudo privileges (needed for systemctl, mv and chown)
  - /opt/kast-web must exist and hold the running 1.15
  - /opt/kast-web-new must hold the unpacked 2.0 with its venv and .env
  - /var/lib/kast-web/kast.db must exist and be readable
  - /opt/kast-web-v115 and /var/lib/kast-web-v115 must NOT already exist

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

# Live 1.15 install — also the final home of 2.0 after cutover.
LIVE_APPDIR  = Path('/opt/kast-web')
LIVE_DATADIR = Path('/var/lib/kast-web')
LIVE_DB      = LIVE_DATADIR / 'kast.db'

# Where 2.0 is unpacked and proved before it is swapped in.
STAGE_APPDIR  = Path('/opt/kast-web-new')
STAGE_DATADIR = Path('/var/lib/kast-web-new')
STAGE_DB      = STAGE_DATADIR / 'kast.db'

# Where 1.15 is parked at cutover, so a rollback is two renames.
PARKED_APPDIR  = Path('/opt/kast-web-v115')
PARKED_DATADIR = Path('/var/lib/kast-web-v115')

# One set of services; 2.0 inherits the names 1.15 used.
SERVICES = ['kast-web', 'kast-celery']

# Temporary port for proving the staged tree before cutover. Nothing listens
# here afterwards; no systemd unit is installed for it.
STAGE_PORT = 8001
STAGE_HEALTH_URL = f'http://127.0.0.1:{STAGE_PORT}/'
HEALTH_URL = 'http://127.0.0.1:8000/'

DELTA_MIGRATIONS = [
    # Phase D — cloud subsystem
    'utils/migrate_cloud_v2.py',
    # Phase C / Phase E — AI feature, in dependency order
    'utils/migrate_ai_v1.py',          # ai_settings, ai_summaries tables
    'utils/migrate_ai_byok.py',        # users.anthropic_api_key_encrypted
    'utils/migrate_ai_user_config.py', # users.ai_model_override, ai_base_url
    'utils/migrate_ai_presets.py',     # ai_model_presets, ai_endpoint_presets tables
    'utils/migrate_ai_scan_flag.py',   # scans.generate_ai_summary
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


def run_migration(script_path, appdir, db_path, dry_run):
    """Run a migration script from the staged 2.0 venv against db_path.

    DATABASE_URL is set AFTER sourcing .env so it overrides it. The staged
    .env already holds the final configuration, so pointing migrations at the
    staging copy here means nothing in .env has to be rewritten at cutover.
    Every utils/migrate_*.py resolves its target from DATABASE_URL.
    """
    full_path = appdir / script_path
    if not full_path.exists():
        red(f'  Migration script not found: {full_path}')
        return False

    cmd = [
        'sudo', '-u', 'www-data', 'bash', '-c',
        f'cd {appdir} && set -a && source .env && set +a && '
        f'DATABASE_URL=sqlite:///{db_path} venv/bin/python {script_path}'
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


def verify_staged(appdir, db_path, port, dry_run):
    """Boot the staged tree on a temporary port and health-check it.

    Deliberately runs gunicorn directly rather than installing a second
    systemd unit — the whole point of the staging layout is that only one
    pair of service names ever exists.
    """
    if dry_run:
        yellow(f'  [dry-run] would boot {appdir} on port {port} and probe it')
        return True

    cmd = (
        f'cd {appdir} && set -a && source .env && set +a && '
        f'DATABASE_URL=sqlite:///{db_path} '
        f'venv/bin/gunicorn --bind 127.0.0.1:{port} --workers 1 '
        f'--timeout 60 wsgi:app'
    )
    proc = subprocess.Popen(
        ['sudo', '-u', 'www-data', 'bash', '-c', cmd],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        ok = health_check(f'http://127.0.0.1:{port}/', retries=6, delay=3)
        if not ok:
            red('  Staged 2.0 did not respond. Output:')
            proc.terminate()
            try:
                out, _ = proc.communicate(timeout=10)
                for line in (out or '').splitlines()[-25:]:
                    red(f'    {line}')
            except subprocess.TimeoutExpired:
                proc.kill()
        return ok
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def cutover(dry_run):
    """Park 1.15 and move the staged tree into its place.

    Four renames on the same filesystem, so each is atomic and the window
    where neither tree is in place is as small as it can be.
    """
    moves = [
        (LIVE_DATADIR, PARKED_DATADIR),
        (STAGE_DATADIR, LIVE_DATADIR),
        (LIVE_APPDIR, PARKED_APPDIR),
        (STAGE_APPDIR, LIVE_APPDIR),
    ]
    for src, dst in moves:
        if dry_run:
            yellow(f'  [dry-run] would move {src} -> {dst}')
            continue
        run(['sudo', 'mv', str(src), str(dst)])
        green(f'  {src} -> {dst}')


def rollback_commands():
    """The exact commands to undo a cutover, printed on success and failure."""
    return [
        f'sudo systemctl stop {" ".join(SERVICES)}',
        f'sudo mv {LIVE_APPDIR} {STAGE_APPDIR}',
        f'sudo mv {PARKED_APPDIR} {LIVE_APPDIR}',
        f'sudo mv {LIVE_DATADIR} {STAGE_DATADIR}',
        f'sudo mv {PARKED_DATADIR} {LIVE_DATADIR}',
        f'sudo systemctl start {" ".join(SERVICES)}',
    ]


# ------------------------------------------------------------------ main

def main():
    parser = argparse.ArgumentParser(description='Upgrade kast-web 1.15 -> 2.0')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print what would happen without making changes')
    parser.add_argument('--skip-service-stop', action='store_true',
                        help='Do not stop 1.15 services (for testing only - risk of DB corruption)')
    args = parser.parse_args()

    if args.dry_run:
        yellow('DRY-RUN MODE - no changes will be made\n')

    # ---------------------------------------------------------------- preflight

    header('STEP 1: Preflight checks')

    errors = []

    if not LIVE_APPDIR.exists():
        errors.append(f'1.15 app directory not found: {LIVE_APPDIR}')
    if not STAGE_APPDIR.exists():
        errors.append(f'Staged 2.0 app directory not found: {STAGE_APPDIR}')
    if not LIVE_DB.exists():
        errors.append(f'1.15 database not found: {LIVE_DB}')
    if not (STAGE_APPDIR / '.env').exists():
        errors.append(f'Staged install has no .env: {STAGE_APPDIR / ".env"}')
    if not (STAGE_APPDIR / 'venv' / 'bin' / 'gunicorn').exists():
        errors.append(f'Staged install has no venv/bin/gunicorn: {STAGE_APPDIR}')

    # Cutover parks 1.15 at these paths; refuse rather than clobber a previous run.
    for parked in (PARKED_APPDIR, PARKED_DATADIR):
        if parked.exists():
            errors.append(
                f'{parked} already exists - a previous upgrade was not cleaned up. '
                f'Move or remove it before re-running.'
            )

    for mig in DELTA_MIGRATIONS:
        if not (STAGE_APPDIR / mig).exists():
            errors.append(f'Missing migration script: {STAGE_APPDIR / mig}')

    if errors:
        for e in errors:
            red(f'  ERROR: {e}')
        sys.exit(1)

    green(f'  1.15 app:       {LIVE_APPDIR}')
    green(f'  1.15 database:  {LIVE_DB}  ({LIVE_DB.stat().st_size:,} bytes)')
    green(f'  staged 2.0 app: {STAGE_APPDIR}')
    green(f'  staging copy:   {STAGE_DB}')
    green(f'  will park 1.15: {PARKED_APPDIR}, {PARKED_DATADIR}')
    print()
    for mig in DELTA_MIGRATIONS:
        green(f'  Migration: {mig}')

    # ---------------------------------------------------------------- stop services

    header('STEP 2: Stop the 1.15 services')

    if args.skip_service_stop:
        yellow('  --skip-service-stop specified; skipping (risk: DB may be written during copy)')
    else:
        stop_services(SERVICES, args.dry_run)
        green('  Services stopped. The 1.15 database is now quiescent.')

    # ---------------------------------------------------------------- copy db

    header('STEP 3: Copy the 1.15 database into staging')

    if not args.dry_run:
        if STAGE_DB.exists():
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_path = STAGE_DB.with_suffix(f'.pre_upgrade_{ts}.bak')
            shutil.copy2(STAGE_DB, backup_path)
            yellow(f'  Existing staging DB backed up to {backup_path}')
        STAGE_DB.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LIVE_DB, STAGE_DB)
        # Migrations run as www-data and write .bak files alongside the DB,
        # so the directory must be writable by that user too.
        run(['sudo', 'chown', 'www-data:www-data', str(STAGE_DB.parent)])
        run(['sudo', 'chmod', '750', str(STAGE_DB.parent)])
        run(['sudo', 'chown', 'www-data:www-data', str(STAGE_DB)])
        run(['sudo', 'chmod', '660', str(STAGE_DB)])
        green(f'  Copied {LIVE_DB} -> {STAGE_DB}')
        green(f'  Size: {STAGE_DB.stat().st_size:,} bytes')
        green(f'  {LIVE_DB} is untouched.')
    else:
        yellow(f'  [dry-run] would copy {LIVE_DB} -> {STAGE_DB}')

    # ---------------------------------------------------------------- migrations

    header('STEP 4: Run delta migrations against the copy')

    for mig in DELTA_MIGRATIONS:
        if not run_migration(mig, STAGE_APPDIR, STAGE_DB, args.dry_run):
            red(f'\nMigration failed: {mig}')
            red('Nothing has been cut over. The 1.15 install is untouched.')
            red(f'Restart it with: sudo systemctl start {" ".join(SERVICES)}')
            sys.exit(1)

    green('  All migrations completed.')

    # ---------------------------------------------------------------- verify

    header('STEP 5: Prove the staged 2.0 before cutting over')

    if not verify_staged(STAGE_APPDIR, STAGE_DB, STAGE_PORT, args.dry_run):
        red(f'\n  Staged 2.0 failed its health check on port {STAGE_PORT}.')
        red('  Nothing has been cut over. The 1.15 install is untouched.')
        red(f'  Restart it with: sudo systemctl start {" ".join(SERVICES)}')
        sys.exit(1)
    green(f'  Staged 2.0 responded on port {STAGE_PORT} with the migrated database.')

    # ---------------------------------------------------------------- cutover

    header('STEP 6: Cut over')

    cutover(args.dry_run)
    green('  2.0 now occupies /opt/kast-web and /var/lib/kast-web.')
    green(f'  1.15 is parked at {PARKED_APPDIR} and {PARKED_DATADIR}.')

    # ---------------------------------------------------------------- start

    header('STEP 7: Start the services')

    start_services(SERVICES, args.dry_run)
    if not args.dry_run:
        print('  Waiting for 2.0 to come up...')
        time.sleep(3)

    # ---------------------------------------------------------------- health

    header('STEP 8: Health check')

    if args.dry_run:
        yellow(f'  [dry-run] would check {HEALTH_URL}')
    else:
        if health_check(HEALTH_URL):
            green(f'  2.0 is responding at {HEALTH_URL}')
        else:
            red(f'  Health check failed - {HEALTH_URL} did not respond.')
            red('  Check: sudo journalctl -u kast-web -n 50')
            red('  Check: sudo tail /var/log/kast-web/error.log')
            print()
            red('  To roll back to 1.15:')
            for c in rollback_commands():
                red(f'    {c}')
            sys.exit(1)

    # ---------------------------------------------------------------- summary

    header('UPGRADE COMPLETE')
    green('  The 1.15 database was copied, migrated and cut over.')
    green('  kast-web 2.0 is running from /opt/kast-web.')
    print()
    yellow(f'  1.15 is parked intact at {PARKED_APPDIR} and {PARKED_DATADIR}.')
    yellow('  Its database was never modified.')
    print()
    print('  To roll back:')
    for c in rollback_commands():
        print(f'    {c}')
    print()
    print('  Next steps:')
    print('    1. Log into kast-web 2.0 and verify your data is present.')
    print('    2. Review /admin/cloud/credentials if you used ZAP cloud mode.')
    print(f'    3. Once satisfied, remove the parked 1.15 tree:')
    print(f'       sudo rm -rf {PARKED_APPDIR} {PARKED_DATADIR}')


if __name__ == '__main__':
    main()
