# Upgrading to kast 3.0 + kast-web 2.0

This guide is for installations running **kast 2.x** (any 2.x patch) and **kast-web 1.x** that are upgrading to the kast 3.0 + kast-web 2.0 coordinated release.

If you are upgrading kast-web alone (kast already at 3.0), skip to [kast-web upgrade steps](#kast-web-upgrade-steps).

---

## What changed

### kast CLI (2.x → 3.0)

| Area | Change |
|---|---|
| Cloud mode | `--set zap.execution_mode=cloud` removed. Cloud infrastructure is now managed by kast-web. See [Cloud migration](#cloud-mode-migration). |
| v2 argv compatibility | A translation wrapper preserves the `kast --target X --mode passive ...` v2 command shape. Existing kast-web subprocess invocations keep working unchanged. |
| Output file format | Unchanged. Same `{plugin}.json`, `{plugin}_processed.json`, `kast_info.json`, `zap_scan_progress.json` filenames and kebab-case key conventions. |
| Minimum Python | 3.11+ (was 3.8+) |

### kast-web (1.x → 2.0)

| Area | Change |
|---|---|
| Cloud infrastructure | Terraform / SSH / ZAP provisioning now runs inside kast-web. New admin pages at `/admin/cloud/credentials`, `/admin/cloud/scans`, `/admin/cloud/orphans`. |
| User management | Full multi-user system with roles (admin, power\_user, user, viewer), login lockout, and audit log. Replaces the single shared account. |
| ZAP management | Automation plan and configuration management at `/admin/zap/plans` and `/admin/zap/configs`. |
| AI executive summary | Claude-powered scan summary; shared org key or per-user BYOK Anthropic API key. |
| Config profiles | Save and reuse named scan configurations; import/export YAML. |
| Report sharing | Shareable links with optional expiry. |
| New required env vars | `ENCRYPTION_KEY` (for credential encryption at rest). See [Environment variables](#environment-variables). |
| Packaging | `kast-web` CLI entry point (pipx installable). Docker image available. |
| Database | Six additional migration scripts must run before the new release starts. |

---

## Prerequisites

- Root or sudo access on the kast-web server.
- Redis running (no change from 1.x).
- kast 3.0 binary available (see [Install kast 3.0](#1-install-kast-30)).
- Terraform >= 1.5 on the kast-web host (required only if you use cloud ZAP mode).
- At least 500 MB free disk space for the side-by-side install.

---

## Upgrade strategy

The recommended approach is a **side-by-side install**: deploy kast-web 2.0 alongside the running 1.x installation, migrate the database, verify, then cut over traffic. kast-web 1.x stays intact throughout and can be restarted if something goes wrong.

An [in-place upgrade](#in-place-upgrade) is documented as an alternative for simpler setups.

---

## Side-by-side upgrade (recommended)

### 1. Install kast 3.0

```bash
# Replace the existing kast binary
sudo pip install --upgrade kast   # or follow kast's own release notes
kast --version                    # confirm 3.0.x
```

kast 3.0 ships a v2 argv compatibility wrapper so kast-web's existing subprocess calls continue to work without changes.

### 2. Deploy kast-web 2.0

```bash
# Clone or download kast-web 2.0 to a new directory
sudo git clone <repo-url> /opt/kast-web2
cd /opt/kast-web2

# Install dependencies
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements-production.txt
sudo venv/bin/pip install --no-deps -e .
sudo chown -R www-data:www-data /opt/kast-web2
```

### 3. Configure the environment

Copy your existing `.env` and add the new required variables:

```bash
sudo cp /opt/kast-web/.env /opt/kast-web2/.env
sudo editor /opt/kast-web2/.env
```

Add these lines if not already present:

```ini
# Required for encrypting cloud credentials at rest
ENCRYPTION_KEY=<32-byte hex string>

# Point to new data directory
DATABASE_URL=sqlite:////var/lib/kast-web2/kast.db
KAST_RESULTS_DIR=/var/lib/kast-web2/results
```

Generate `ENCRYPTION_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Keep the same `SECRET_KEY` value from your 1.x `.env`. Changing it will invalidate existing sessions and (if any encrypted blobs exist in 1.x) break decryption.

### 4. Create data directories

```bash
sudo mkdir -p /var/lib/kast-web2/results
sudo chown -R www-data:www-data /var/lib/kast-web2
```

### 5. Run the automated upgrade script

`utils/upgrade_from_v115.py` stops 1.x services, copies the database, runs all delta migrations, starts 2.0 services, and performs a health check. The 1.x database is not modified.

```bash
# Dry run first — shows what will happen without making changes
sudo python3 /opt/kast-web2/utils/upgrade_from_v115.py --dry-run

# Run for real
sudo python3 /opt/kast-web2/utils/upgrade_from_v115.py
```

The script runs these migrations against the copied database, in order:

| Script | What it adds |
|---|---|
| `migrate_cloud_v2.py` | `cloud_credentials`, `cloud_scans`, `cloud_orphans` tables |
| `migrate_ai_v1.py` | `ai_settings`, `ai_summaries` tables |
| `migrate_ai_byok.py` | `users.anthropic_api_key_encrypted` column |
| `migrate_ai_user_config.py` | `users.ai_model_override`, `users.ai_base_url` columns |
| `migrate_ai_presets.py` | `ai_model_presets`, `ai_endpoint_presets` tables |
| `migrate_ai_scan_flag.py` | `scans.generate_ai_summary` column |
| `migrate_notes_tags.py` | `scans.notes`, `scans.tags` columns |

Each script is idempotent — safe to re-run if interrupted.

### 6. Install systemd units for kast-web 2.0

```bash
sudo cp /opt/kast-web2/deployment/systemd/kast-web2.service /etc/systemd/system/
sudo cp /opt/kast-web2/deployment/systemd/kast-celery2.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kast-web2 kast-celery2
```

kast-web 2.0 listens on port 8001 by default (the 2.x units use `--bind 127.0.0.1:8001`). Update Nginx to proxy to the new port, or adjust the service file to use 8000 once 1.x is decommissioned.

### 7. Verify

```bash
# Services are active
sudo systemctl status kast-web2 kast-celery2

# Health endpoint responds
curl -sf http://127.0.0.1:8001/ | head -5

# Check the admin panel
# https://<your-server>/admin/
```

Submit a test scan and confirm it runs to completion.

### 8. Cut over Nginx and decommission 1.x

Once 2.0 is confirmed healthy:

```bash
# Update Nginx upstream port (8001 → 8000) and reload
sudo editor /etc/nginx/sites-available/kast-web
sudo nginx -t && sudo systemctl reload nginx

# Stop and disable 1.x services (leave data intact)
sudo systemctl disable --now kast-web kast-celery
```

The 1.x install at `/opt/kast-web` and its database at `/var/lib/kast-web/kast.db` are left in place and can be restarted at any time for rollback.

---

## In-place upgrade

For single-server setups where downtime is acceptable:

```bash
cd /opt/kast-web

# Stop services
sudo systemctl stop kast-web kast-celery

# Backup database
sudo cp /var/lib/kast-web/kast.db /var/lib/kast-web/kast.db.bak-$(date +%Y%m%d)

# Pull 2.0
sudo git pull origin main

# Install updated dependencies
sudo venv/bin/pip install -r requirements-production.txt
sudo venv/bin/pip install --no-deps -e .

# Add ENCRYPTION_KEY to .env (see step 3 above)
sudo editor /opt/kast-web/.env

# Run delta migrations (set DATABASE_URL to match your .env)
export $(grep -v '^#' .env | xargs)
for script in \
    utils/migrate_cloud_v2.py \
    utils/migrate_ai_v1.py \
    utils/migrate_ai_byok.py \
    utils/migrate_ai_user_config.py \
    utils/migrate_ai_presets.py \
    utils/migrate_ai_scan_flag.py \
    utils/migrate_notes_tags.py; do
    sudo -E venv/bin/python3 $script
done

# Restart
sudo systemctl start kast-web kast-celery
```

---

## Cloud mode migration

If you used `--set zap.execution_mode=cloud` in kast 2.x, additional steps are required to configure cloud credentials in kast-web 2.0. See [docs/MIGRATION_FROM_KAST_CLOUD.md](MIGRATION_FROM_KAST_CLOUD.md) for the full walkthrough.

---

## Environment variables

Full reference for new and changed environment variables in kast-web 2.0:

| Variable | Required | Notes |
|---|---|---|
| `ENCRYPTION_KEY` | **yes** | New in 2.0. Fernet key for encrypting cloud credentials. Must be 32+ random bytes (hex or base64). |
| `SECRET_KEY` | **yes** | Unchanged from 1.x. Keep the same value — changing it breaks existing sessions and encrypted blobs. |
| `DATABASE_URL` | no | Default changed from `instance/kast-web.db` to `sqlite:////var/lib/kast-web/kast.db` in production. |
| `KAST_RESULTS_DIR` | no | Unchanged. |
| `CELERY_BROKER_URL` | no | Unchanged. |
| `CELERY_RESULT_BACKEND` | no | Unchanged. |

---

## Rollback

If 2.0 has a problem, restart the 1.x services (side-by-side upgrade only):

```bash
sudo systemctl stop kast-web2 kast-celery2
sudo systemctl start kast-web kast-celery
# Update Nginx upstream back to port 8000
sudo systemctl reload nginx
```

The 1.x database was not modified. The 2.0 copy at `/var/lib/kast-web2/kast.db` can be discarded.

---

## Troubleshooting

**kast-web2 fails to start with "ENCRYPTION_KEY not set"**

Add `ENCRYPTION_KEY=<hex string>` to `/opt/kast-web2/.env` and restart.

**"InvalidToken" error on ZAP configuration pages**

The `SECRET_KEY` in 2.0's `.env` differs from 1.x. Make sure both use the same value. If configs still fail to decrypt (they were encrypted with a now-lost key), re-enter them at `/admin/zap/configs/<id>/edit`.

**Scans stuck in "pending" after upgrade**

The Celery worker is not running or is not connected to Redis. Check:

```bash
sudo systemctl status kast-celery2
sudo journalctl -u kast-celery2 -n 50
redis-cli ping
```

**Migration script fails partway through**

Each script is idempotent — re-run it. Check the `schema_migrations` table to see which scripts have already been recorded:

```bash
sqlite3 /var/lib/kast-web2/kast.db \
  "SELECT script_name, applied_at FROM schema_migrations ORDER BY applied_at;"
```

**Cloud scans fail after upgrade**

The cloud infrastructure module requires Terraform >= 1.5 on the kast-web server. Verify:

```bash
terraform version
```

If Terraform is not installed, see [docs/ZAP_CLOUD_TOOLS_SETUP.md](ZAP_CLOUD_TOOLS_SETUP.md).
