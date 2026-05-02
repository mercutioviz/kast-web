#!/usr/bin/env bash
# Roll /opt/kast-web2 back to its previous deployed commit (HEAD@{1}).
# Useful when the latest deploy broke something.
set -euo pipefail

PROD_DIR="/opt/kast-web2"

if [[ ! -d "$PROD_DIR/.git" ]]; then
    echo "ERROR: $PROD_DIR is not a git checkout." >&2
    exit 1
fi

cd "$PROD_DIR"

CURRENT=$(git rev-parse HEAD)
PREVIOUS=$(git rev-parse 'HEAD@{1}' 2>/dev/null || true)

if [[ -z "$PREVIOUS" || "$PREVIOUS" == "$CURRENT" ]]; then
    echo "ERROR: no previous reflog entry to roll back to."
    exit 1
fi

echo "Current:  $CURRENT"
echo "Rollback: $PREVIOUS"
read -rp "Reset --hard to $PREVIOUS and restart services? [y/N] " ans
[[ "$ans" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }

git reset --hard "$PREVIOUS"
sudo systemctl restart kast-web2 kast-celery2
sleep 2

if curl -fsS -o /dev/null "http://127.0.0.1:8001/"; then
    echo "Rolled back to $PREVIOUS."
else
    echo "Health check failed after rollback. Investigate."
    exit 1
fi
