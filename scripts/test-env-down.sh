#!/usr/bin/env bash
#
# Stop the kast-web test environment.
#
# Usage:
#   scripts/test-env-down.sh              # stop processes and containers; keep DB
#   scripts/test-env-down.sh --wipe       # also delete /var/lib/kast-web-test/*
#                                         #   (next up will re-seed t_admin)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FLASK_PID_FILE="/tmp/kw-test-flask.pid"
CELERY_PID_FILE="/tmp/kw-test-celery.pid"
TEST_DB_DIR="/var/lib/kast-web-test"
VENV_DIR="$REPO_ROOT/venv"

WIPE=no
if [[ "${1:-}" == "--wipe" ]]; then WIPE=yes; fi

log() { printf '[test-env-down] %s\n' "$*"; }

# shellcheck source=scripts/test-env-common.sh
source "$REPO_ROOT/scripts/test-env-common.sh"

# Read the test port so gunicorn can be found by what it is bound to. Falls
# back to the documented default when .env.test is absent (e.g. tearing down
# after a wipe).
TEST_FLASK_PORT=8001
if [[ -f "$REPO_ROOT/.env.test" ]]; then
    # shellcheck disable=SC1091
    set -a; source "$REPO_ROOT/.env.test"; set +a
fi

# Find processes by signature rather than by pidfile: a cleared /tmp must not
# leave the environment running with no way to stop it. The union of the two
# catches both the normal case and a process whose pidfile went missing.
collect() {
    local pidfile=$1; shift
    local found=("$@")
    if [[ -f "$pidfile" ]]; then
        local pid; pid=$(cat "$pidfile" 2>/dev/null || true)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then found+=("$pid"); fi
    fi
    printf '%s\n' "${found[@]}" | grep -E '^[0-9]+$' | sort -un
}

mapfile -t gpids < <(collect "$FLASK_PID_FILE" $(find_test_gunicorn "$TEST_FLASK_PORT"))
mapfile -t cpids < <(collect "$CELERY_PID_FILE" $(find_test_celery))

if [[ ${#gpids[@]} -gt 0 ]]; then stop_pids gunicorn "${gpids[@]}"; else log "gunicorn not running"; fi
if [[ ${#cpids[@]} -gt 0 ]]; then stop_pids celery   "${cpids[@]}"; else log "celery not running"; fi
rm -f "$FLASK_PID_FILE" "$CELERY_PID_FILE"

if port_in_use "$TEST_FLASK_PORT"; then
    log "WARNING: port ${TEST_FLASK_PORT} is still in use by something this script does not own:"
    (ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep ":${TEST_FLASK_PORT}[[:space:]]" | head -1 | sed 's/^/           /'
fi

for name in kw-test-juiceshop kw-test-webgoat; do
    if docker ps --format '{{.Names}}' | grep -q "^${name}$"; then
        log "stopping container $name"
        docker stop "$name" >/dev/null
    fi
done

if [[ "$WIPE" == "yes" ]]; then
    if [[ -d "$TEST_DB_DIR" ]]; then
        log "wiping $TEST_DB_DIR/* (next up will re-seed)"
        # No sudo: test-env-up chowned the directory to the invoking user.
        find "$TEST_DB_DIR" -mindepth 1 -delete
    fi
fi

log "done"
