#!/usr/bin/env bash
# Deploy ~/kast-web @ refactor/v2.0 into /opt/kast-web2.
# Run from anywhere; script discovers paths itself.
set -euo pipefail

DEV_REPO="/home/mscollins/kast-web"
PROD_DIR="/opt/kast-web2"
BRANCH="refactor/v2.0"
HEALTH_URL="http://127.0.0.1:8001/"

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }

if [[ ! -d "$PROD_DIR/.git" ]]; then
    red "ERROR: $PROD_DIR is not a git checkout. Run the one-time provisioning steps first."
    exit 1
fi

# Refuse to deploy if the dev tree has uncommitted changes.
if [[ -n "$(git -C "$DEV_REPO" status --porcelain)" ]]; then
    red "ERROR: $DEV_REPO has uncommitted changes. Commit or stash before deploying."
    git -C "$DEV_REPO" status --short
    exit 1
fi

# Refuse to deploy if dev is not on the expected branch.
DEV_BRANCH=$(git -C "$DEV_REPO" rev-parse --abbrev-ref HEAD)
if [[ "$DEV_BRANCH" != "$BRANCH" ]]; then
    yellow "WARNING: $DEV_REPO is on '$DEV_BRANCH', not '$BRANCH'."
    read -rp "Deploy '$BRANCH' from $DEV_REPO anyway? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { red "Aborted."; exit 1; }
fi

cd "$PROD_DIR"

OLD_SHA=$(git rev-parse HEAD)
OLD_REQ=$(sha256sum requirements-production.txt | awk '{print $1}')
OLD_MIGS=$(ls utils/migrate_*.py 2>/dev/null | sort)

green "Fetching $BRANCH from dev remote..."
git fetch dev "$BRANCH"

NEW_SHA=$(git rev-parse "FETCH_HEAD")

if [[ "$OLD_SHA" == "$NEW_SHA" ]]; then
    yellow "Already at $NEW_SHA. Nothing to deploy."
    exit 0
fi

echo
green "Deploying:"
echo "  from $OLD_SHA"
echo "  to   $NEW_SHA"
echo
git --no-pager log --oneline "$OLD_SHA..$NEW_SHA"
echo

git reset --hard FETCH_HEAD

NEW_REQ=$(sha256sum requirements-production.txt | awk '{print $1}')
NEW_MIGS=$(ls utils/migrate_*.py 2>/dev/null | sort)

if [[ "$OLD_REQ" != "$NEW_REQ" ]]; then
    green "requirements-production.txt changed; running pip install..."
    venv/bin/pip install --quiet -r requirements-production.txt
fi

NEW_MIG_FILES=$(comm -13 <(echo "$OLD_MIGS") <(echo "$NEW_MIGS") || true)
if [[ -n "$NEW_MIG_FILES" ]]; then
    yellow "New migration scripts detected:"
    echo "$NEW_MIG_FILES"
    read -rp "Run them now? [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        for mig in $NEW_MIG_FILES; do
            green "Running $mig..."
            venv/bin/python "$mig"
        done
    else
        yellow "Skipped migrations. Run them manually before testing."
    fi
fi

green "Restarting services..."
sudo systemctl restart kast-web2 kast-celery2

sleep 2

green "Health check $HEALTH_URL ..."
if curl -fsS -o /dev/null -w "%{http_code}\n" "$HEALTH_URL"; then
    green "v2 is up. Old=$OLD_SHA New=$NEW_SHA"
else
    red "Health check failed. Check 'sudo journalctl -u kast-web2 -n 50' and 'sudo tail /var/log/kast-web2/error.log'."
    exit 1
fi
