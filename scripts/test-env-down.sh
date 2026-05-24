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

WIPE=no
if [[ "${1:-}" == "--wipe" ]]; then WIPE=yes; fi

log() { printf '[test-env-down] %s\n' "$*"; }

stop_pid() {
    local pidfile=$1 label=$2
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            log "stopping $label (pid $pid)"
            kill "$pid" 2>/dev/null || true
            for _ in 1 2 3 4 5; do
                kill -0 "$pid" 2>/dev/null || break
                sleep 1
            done
            kill -9 "$pid" 2>/dev/null || true
        else
            log "$label not running (stale pidfile)"
        fi
        rm -f "$pidfile"
    else
        log "$label has no pidfile"
    fi
}

stop_pid "$FLASK_PID_FILE" gunicorn
stop_pid "$CELERY_PID_FILE" celery

for name in kw-test-juiceshop kw-test-hackazon; do
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
