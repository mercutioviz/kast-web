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
| Report sharing | Share a scan with specific users, with view or edit permission. Public (unauthenticated) links are **not available** in 2.0 — see the CHANGELOG. |
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

kast-web 2.0 lives at `/opt/kast-web` with its data under `/var/lib/kast-web`, served by the `kast-web` and `kast-celery` units — the same paths and service names 1.x used. There is no permanent second install.

To keep the upgrade reversible anyway, 2.0 is **staged** alongside the running 1.x, proved against a copy of your database, and only then swapped into place. Your 1.x install is parked intact rather than overwritten, so rolling back is a pair of renames.

An [in-place upgrade](#in-place-upgrade) is documented as an alternative for simpler setups.

---

## Staged upgrade (recommended)

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
sudo git clone <repo-url> /opt/kast-web-new
cd /opt/kast-web-new

# Install dependencies
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements-production.txt
sudo venv/bin/pip install --no-deps -e .
sudo chown -R www-data:www-data /opt/kast-web-new
```

### 3. Configure the environment

Copy your existing `.env` and add the new required variables:

```bash
sudo cp /opt/kast-web/.env /opt/kast-web-new/.env
sudo editor /opt/kast-web-new/.env
```

Add these lines if not already present:

```ini
# Required for encrypting cloud credentials at rest
ENCRYPTION_KEY=<32-byte hex string>

# Final paths — NOT the staging paths. See the note below.
DATABASE_URL=sqlite:////var/lib/kast-web/kast.db
KAST_RESULTS_DIR=/var/lib/kast-web/results
```

**These are the paths 2.0 will use after cutover, which is why they have no `-new` suffix.** During staging the upgrade script overrides `DATABASE_URL` on the command line so migrations and the health check run against the staging copy. That way nothing in `.env` has to be rewritten at cutover, and there is no window where the file is wrong.

Generate `ENCRYPTION_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Keep the same `SECRET_KEY` value from your 1.x `.env`. Changing it will invalidate existing sessions and (if any encrypted blobs exist in 1.x) break decryption.

### 4. Create data directories

```bash
sudo mkdir -p /var/lib/kast-web-new/results
sudo chown -R www-data:www-data /var/lib/kast-web-new
```

### 5. Run the automated upgrade script

`utils/upgrade_from_v115.py` stops the services, copies the database into staging, runs the delta migrations against the **copy**, boots the staged 2.0 on a temporary port to prove it, cuts over by renaming directories, restarts the services and health-checks again. Your 1.x database is never modified.

If anything fails before the cutover step, nothing has moved and 1.x restarts unchanged. If the post-cutover health check fails, the script prints the exact rollback commands.

```bash
# Dry run first — shows what will happen without making changes
sudo python3 /opt/kast-web-new/utils/upgrade_from_v115.py --dry-run

# Run for real
sudo python3 /opt/kast-web-new/utils/upgrade_from_v115.py
```

At cutover the directories are rearranged like this:

| Before | After |
|---|---|
| `/opt/kast-web` (1.x) | `/opt/kast-web-v115` |
| `/opt/kast-web-new` (2.0) | `/opt/kast-web` |
| `/var/lib/kast-web` (1.x data) | `/var/lib/kast-web-v115` |
| `/var/lib/kast-web-new` (migrated copy) | `/var/lib/kast-web` |

The script runs these migrations against the copied database, in order:

| Script | What it adds |
|---|---|
| `migrate_cloud_v2.py` | `cloud_credentials`, `cloud_scans`, `cloud_orphans` tables |
| `migrate_ai_v1.py` | `ai_settings`, `ai_summaries` tables |
| `migrate_ai_byok.py` | `users.anthropic_api_key_encrypted` column |
| `migrate_ai_user_config.py` | `users.ai_model_override`, `users.ai_base_url` columns |
| `migrate_ai_presets.py` | `ai_model_presets`, `ai_endpoint_presets` tables |
| `migrate_ai_scan_flag.py` | `scans.generate_ai_summary` column |

Each script is idempotent — safe to re-run if interrupted.

### 6. Service units

**Nothing to install.** 2.0 runs under the same `kast-web` and `kast-celery` units, from the same `/opt/kast-web`, on the same port 8000. The upgrade script restarts them for you in step 5.

If your units predate 2.0 and you want the shipped versions, refresh them *after* cutover:

```bash
sudo cp /opt/kast-web/deployment/systemd/kast-web.service /etc/systemd/system/
sudo cp /opt/kast-web/deployment/systemd/kast-celery.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart kast-web kast-celery
```

### 7. Verify

```bash
# Services are active
sudo systemctl status kast-web kast-celery

# Health endpoint responds
curl -sf http://127.0.0.1:8000/ | head -5

# Check the admin panel
# https://<your-server>/admin/
```

Submit a test scan and confirm it runs to completion.

### 8. Decommission 1.x

**Nginx needs no change.** 2.0 occupies the same path and port, so the existing site config keeps working.

Once you are satisfied 2.0 is healthy — log in, check your data is present, run a test scan — remove the parked 1.x tree:

```bash
sudo rm -rf /opt/kast-web-v115 /var/lib/kast-web-v115
```

Until you do, that tree is your rollback. Keep it for as long as you want the option.

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

If 2.0 has a problem and the parked 1.x tree is still present, roll back by reversing the renames:

```bash
sudo systemctl stop kast-web kast-celery
sudo mv /opt/kast-web /opt/kast-web-new
sudo mv /opt/kast-web-v115 /opt/kast-web
sudo mv /var/lib/kast-web /var/lib/kast-web-new
sudo mv /var/lib/kast-web-v115 /var/lib/kast-web
sudo systemctl start kast-web kast-celery
```

Nginx needs no change — the path and port are the same either way.

Your 1.x database was never modified: the upgrade copied it and migrated the copy. The migrated 2.0 database is left at `/var/lib/kast-web-new/kast.db` and can be discarded, or kept to investigate what went wrong.

---

## Troubleshooting

**kast-web fails to start with "ENCRYPTION_KEY not set"**

Add `ENCRYPTION_KEY=<hex string>` to the `.env` and restart. Before cutover that is `/opt/kast-web-new/.env`; afterwards it is `/opt/kast-web/.env`.

**"InvalidToken" error on ZAP configuration pages**

The `SECRET_KEY` in 2.0's `.env` differs from 1.x. Make sure both use the same value. If configs still fail to decrypt (they were encrypted with a now-lost key), re-enter them at `/admin/zap/configs/<id>/edit`.

**Scans stuck in "pending" after upgrade**

The Celery worker is not running or is not connected to Redis. Check:

```bash
sudo systemctl status kast-celery
sudo journalctl -u kast-celery -n 50
redis-cli ping
```

**Migration script fails partway through**

Each script is idempotent — re-run it. Check the `schema_migrations` table to see which scripts have already been recorded:

```bash
sqlite3 /var/lib/kast-web/kast.db \
  "SELECT script_name, applied_at FROM schema_migrations ORDER BY applied_at;"
```

**Cloud scans fail after upgrade**

The cloud infrastructure module requires Terraform >= 1.5 on the kast-web server. Verify:

```bash
terraform version
```

If Terraform is not installed, see [docs/ZAP_CLOUD_TOOLS_SETUP.md](ZAP_CLOUD_TOOLS_SETUP.md).
