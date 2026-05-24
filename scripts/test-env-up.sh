#!/usr/bin/env bash
#
# Start the kast-web test environment. Idempotent.
#
# What this does:
#   - On first run, generates .env.test from .env.test.example with fresh
#     SECRET_KEY, ENCRYPTION_KEY, and TEST_ADMIN_PASSWORD.
#   - Ensures /var/lib/kast-web-test/ exists (uses sudo on first run).
#   - Creates a Python venv at ./venv if missing and installs requirements.
#   - Pulls + starts juice-shop and hackazon Docker containers on loopback.
#   - Seeds the t_admin user in the test DB.
#   - Starts gunicorn on TEST_FLASK_PORT and a Celery worker against test redis.
#   - Waits for the server to respond.
#
# Files written:
#   /tmp/kw-test-flask.pid
#   /tmp/kw-test-celery.pid
#   /tmp/kw-test-flask.log
#   /tmp/kw-test-celery.log

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ENV_FILE=".env.test"
ENV_TEMPLATE=".env.test.example"
TEST_DB_DIR="/var/lib/kast-web-test"
VENV_DIR="$REPO_ROOT/venv"
FLASK_PID_FILE="/tmp/kw-test-flask.pid"
CELERY_PID_FILE="/tmp/kw-test-celery.pid"
FLASK_LOG="/tmp/kw-test-flask.log"
CELERY_LOG="/tmp/kw-test-celery.log"

log()  { printf '[test-env-up] %s\n' "$*"; }
die()  { printf '[test-env-up] ERROR: %s\n' "$*" >&2; exit 1; }

# 1. Generate .env.test on first run -----------------------------------------
if [[ ! -f "$ENV_FILE" ]]; then
    [[ -f "$ENV_TEMPLATE" ]] || die "$ENV_TEMPLATE missing"
    log "first run: generating $ENV_FILE with fresh secrets"
    SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
    FERNET=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' 2>/dev/null \
        || python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')
    PASS=$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    # Substitute placeholders. Using ~ as the sed delimiter because the values are urlsafe (no ~).
    sed -i "s~^SECRET_KEY=__GENERATE__~SECRET_KEY=$SECRET~" "$ENV_FILE"
    sed -i "s~^ENCRYPTION_KEY=__GENERATE__~ENCRYPTION_KEY=$FERNET~" "$ENV_FILE"
    sed -i "s~^TEST_ADMIN_PASSWORD=__GENERATE__~TEST_ADMIN_PASSWORD=$PASS~" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    log "wrote $ENV_FILE (admin password recorded inside)"
fi

# 2. Load env -----------------------------------------------------------------
set -a; source "$ENV_FILE"; set +a
: "${DATABASE_URL:?DATABASE_URL not set}"
: "${TEST_FLASK_PORT:?TEST_FLASK_PORT not set}"
: "${TEST_ADMIN_USERNAME:?TEST_ADMIN_USERNAME not set}"
[[ "$DATABASE_URL" == *kast-web-test* ]] \
    || die "DATABASE_URL must point at the test DB ($DATABASE_URL)"

# 3. Test DB directory --------------------------------------------------------
if [[ ! -d "$TEST_DB_DIR" ]]; then
    log "creating $TEST_DB_DIR (requires sudo)"
    sudo mkdir -p "$TEST_DB_DIR/results"
    sudo chown -R "$USER":"$USER" "$TEST_DB_DIR"
fi

# 4. Virtualenv + dependencies ------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    log "creating venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip >/dev/null
    log "installing requirements (one-time, slow)"
    "$VENV_DIR/bin/pip" install -r requirements.txt
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# 5. Redis check --------------------------------------------------------------
redis-cli ping >/dev/null 2>&1 || die "redis is not reachable on localhost:6379"

# 6. Throwaway scan targets (juice-shop, hackazon) ----------------------------
start_container() {
    local name=$1 image=$2 host_port=$3 container_port=$4
    if docker ps --format '{{.Names}}' | grep -q "^${name}$"; then
        log "$name already running"
        return
    fi
    if ! docker image inspect "$image" >/dev/null 2>&1; then
        log "pulling $image (one-time)"
        docker pull "$image"
    fi
    log "starting $name -> 127.0.0.1:${host_port}"
    docker run -d --rm --name "$name" \
        -p "127.0.0.1:${host_port}:${container_port}" "$image" >/dev/null
}
start_container kw-test-juiceshop bkimminich/juice-shop "$TEST_JUICESHOP_PORT" 3000
start_container kw-test-hackazon  mutzel/all-in-one-hackazon "$TEST_HACKAZON_PORT" 80

# 7. Seed admin (db.create_all happens inside seed via create_app) ------------
log "seeding $TEST_ADMIN_USERNAME"
python3 utils/seed_test_admin.py

# 8. Start Celery worker ------------------------------------------------------
if [[ -f "$CELERY_PID_FILE" ]] && kill -0 "$(cat "$CELERY_PID_FILE")" 2>/dev/null; then
    log "celery already running (pid $(cat "$CELERY_PID_FILE"))"
else
    log "starting celery worker -> $CELERY_LOG"
    nohup celery -A celery_worker.celery worker --loglevel=info \
        >"$CELERY_LOG" 2>&1 &
    echo $! >"$CELERY_PID_FILE"
fi

# 9. Start gunicorn -----------------------------------------------------------
if [[ -f "$FLASK_PID_FILE" ]] && kill -0 "$(cat "$FLASK_PID_FILE")" 2>/dev/null; then
    log "gunicorn already running (pid $(cat "$FLASK_PID_FILE"))"
else
    log "starting gunicorn on 127.0.0.1:${TEST_FLASK_PORT} -> $FLASK_LOG"
    nohup gunicorn --bind "127.0.0.1:${TEST_FLASK_PORT}" \
        --workers 2 --timeout 120 wsgi:app \
        >"$FLASK_LOG" 2>&1 &
    echo $! >"$FLASK_PID_FILE"
fi

# 10. Health check ------------------------------------------------------------
log "waiting for server to come up"
for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${TEST_FLASK_PORT}/auth/login" >/dev/null; then
        log "test env ready at ${TEST_BASE_URL:-http://127.0.0.1:${TEST_FLASK_PORT}}"
        log "admin: $TEST_ADMIN_USERNAME (password in $ENV_FILE)"
        exit 0
    fi
    sleep 1
done
die "server did not become reachable in 30s; see $FLASK_LOG"
