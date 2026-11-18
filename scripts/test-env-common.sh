#!/usr/bin/env bash
#
# Shared helpers for test-env-up.sh / test-env-down.sh.
# Source this after REPO_ROOT and VENV_DIR are set.
#
# Why this exists
# ---------------
# Both scripts used to track liveness purely through /tmp/kw-test-*.pid. When
# something clears /tmp underneath them (systemd-tmpfiles, a reboot) the
# pidfiles vanish while the processes survive, and the scripts lose the
# environment: `up` tries to bind a port that is already taken, and `down`
# reports "no pidfile" and leaves the processes running. That is exactly what
# happened between 2026-05-29 and 2026-11-17, when two orphaned gunicorn
# masters sat on the test port for six months serving stale code.
#
# So liveness is discovered from the process table by signature, with the
# pidfiles kept only as a hint. Every pattern is anchored with ^ and rooted at
# the repo's own venv path, so it can match ONLY processes started from this
# checkout -- never the production install under /opt/kast-web/venv, and never
# the shell that happens to mention the path on its command line.

# Processes started from this repo's venv. $1 is an extra pattern fragment.
_test_env_pgrep() {
    pgrep -f "^${VENV_DIR}/bin/python[0-9.]* ${VENV_DIR}/bin/$1" 2>/dev/null || true
}

# PIDs of test gunicorn masters/workers bound to $1 (port).
find_test_gunicorn() {
    _test_env_pgrep "gunicorn --bind 127\.0\.0\.1:${1}"
}

# PIDs of test celery master/workers.
find_test_celery() {
    _test_env_pgrep "celery -A celery_worker\.celery"
}

# Is anything at all listening on port $1?
port_in_use() {
    if command -v ss >/dev/null 2>&1; then
        ss -ltn 2>/dev/null | grep -q ":${1}[[:space:]]"
    else
        netstat -ltn 2>/dev/null | grep -q ":${1}[[:space:]]"
    fi
}

# Stop a set of PIDs politely, then firmly. $1 label, rest PIDs.
# gunicorn treats SIGQUIT as "quick shutdown" and can ignore SIGTERM while a
# worker is wedged, so escalate TERM -> QUIT -> KILL rather than TERM -> KILL.
stop_pids() {
    local label=$1; shift
    local pids=("$@")
    [[ ${#pids[@]} -eq 0 ]] && return 0

    log "stopping $label (pid ${pids[*]})"
    kill -TERM "${pids[@]}" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
        _any_alive "${pids[@]}" || return 0
        sleep 1
    done

    kill -QUIT "${pids[@]}" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
        _any_alive "${pids[@]}" || return 0
        sleep 1
    done

    log "$label did not stop; sending SIGKILL"
    kill -KILL "${pids[@]}" 2>/dev/null || true
    sleep 1
    _any_alive "${pids[@]}" && log "WARNING: $label still alive: $(_alive_of "${pids[@]}")"
    return 0
}

_any_alive() {
    local p
    for p in "$@"; do kill -0 "$p" 2>/dev/null && return 0; done
    return 1
}

_alive_of() {
    local p out=()
    for p in "$@"; do kill -0 "$p" 2>/dev/null && out+=("$p"); done
    printf '%s ' "${out[@]}"
}
