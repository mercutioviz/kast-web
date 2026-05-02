# kast-web — Active Context for AI Assistants

This file is auto-loaded by Claude Code on every session in this repo. It is the lightweight "what's true *right now*" override for active-phase work. Comprehensive reference lives in `genai-instructions.md`; this file wins where the two conflict.

## Project at a glance

kast-web is the Flask + Celery + Redis web frontend for **kast**, the Kali Automated Scan Tool. It lets a Solutions Architect submit and manage web-application security scans through a browser, manage cloud infrastructure for ephemeral ZAP scanning, and share polished reports with prospects.

kast-web shells out to the kast CLI installed at `/usr/local/bin/kast`. The kast↔kast-web boundary is **frozen** for the v3-coordinated release — see `kast/docs/web-integration.md` (in the kast repo at `/home/mscollins/kast/`).

**Reliability and reputational safety are first-class concerns.** This tool runs in front of prospects (or produces artifacts that get sent to prospects). Active scans must never look like attacks against prospect infrastructure.

## Current status: v2.0 refactor in progress

We are on branch `refactor/v2.0`. The actual work plan is **driven from the kast repo's v3 design docs**, because Phase D of the kast v3 refactor is the cloud-subsystem migration into kast-web. The two repos have independent version histories (kast 2.14 → 3.0; kast-web 1.5 → 2.0) but release as a coordinated bundle.

Authoritative planning docs live in the kast repo at `/home/mscollins/kast/docs/v3-planning/`:

- **`01-audit.md`** — Phase 1 audit of v2.14
- **`02-ideation.md`** — Phase 2 capability menu
- **`03-design-and-migration.md`** — Phase 3 design and phased migration plan
- **`04-kast-web-cloud-migration.md`** — Phase D detailed kast-web design (the source of truth for cloud-module work in this repo)

**Phase D — cloud migration: COMPLETE.** All 11 deliverables shipped across both repos. The kast CLI no longer has cloud-mode code (D10 deleted ~6,425 lines in commit `af1610c` on the kast side); kast-web's `app/cloud/` module owns Terraform / SSH / ZAP-API provisioning end-to-end. Migration guide for v2.x cloud users is at `docs/MIGRATION_FROM_KAST_CLOUD.md`.

**Current focus: Phase E — release polish + tagging.** This is what stands between "code is done" and the coordinated kast 3.0 / kast-web 2.0 release. Items in flight: pyproject.toml + pipx packaging, Dockerfile, README rewrite, v2→v3 migration guide for kast users, CHANGELOG, coordinated release tagging.

## Critical: contracts frozen for v3.0

Do not change these surfaces without explicit, coordinated planning:

- **The kast↔kast-web contract** documented in `/home/mscollins/kast/docs/web-integration.md`. Atomic writes (`.tmp` + `rename(2)`), frozen filenames (`{plugin}.json`, `{plugin}_processed.json`, `kast_info.json`, `zap_scan_progress.json`, `missing_issue_ids.json`), file-presence state machine, polling channel.
- **The v2 CLI argv contract** (the `kast --target X --mode passive ...` shape). kast preserves this via a v2-argv translation wrapper, so kast-web's existing `subprocess.Popen([...])` invocations keep working unchanged.
- **The `_processed.json` per-plugin output format**, including kebab-case keys.
- **The issue registry data format** in `kast/data/issue_registry.json`.

Internal kast-web refactoring is free as long as these surfaces stay stable.

## Cloud-scan flow (post–Phase D)

The cloud-scan path now flows entirely through kast-web's own infrastructure:

1. `execute_scan_task` sees a scan with a cloud-mode `ZapConfiguration` and a referenced `CloudCredential`.
2. It calls `cloud_provision_task` (synchronous wait) — `app/cloud/orchestrator.py` invokes the appropriate provider (`app/cloud/providers/{aws,azure,gcp}.py`) which uses `terraform_manager.py` and `ssh_executor.py` to stand up an ephemeral ZAP instance.
3. The orchestrator returns `{zap_url, zap_api_key, instance_id}` and a `CloudScan` row tracks lifecycle state.
4. kast-web spawns the kast CLI with `--set zap.execution_mode=remote --set zap.remote.url=...` — kast connects to the already-running ZAP and runs the scan.
5. After the scan finishes (success or fail), `cloud_teardown_task` runs `terraform destroy` and updates the `CloudScan` row.
6. Celery Beat schedules `cloud_orphan_cleanup_task` every 15 minutes to detect and clean any infrastructure that didn't tear down cleanly.

The kast CLI sees only `local` / `remote` / `auto` execution modes — `cloud` was removed in kast D10.

For original design context (now historical): `/home/mscollins/kast/docs/v3-planning/04-kast-web-cloud-migration.md`.

## kast-web modules relevant to cloud scans

- `app/cloud/` — the cloud module shipped in Phase D. `orchestrator.py` (provision / teardown / orphan-cleanup), `providers/{aws,azure,gcp}.py`, `terraform_manager.py`, `ssh_executor.py`, `zap_api_client.py`, `cleanup.py`, `diagnostics.py`, `routes.py`, plus the `terraform/{aws,azure,gcp}/` configs.
- `app/models.py` cloud tables: `CloudCredential` (encrypted per-org provider creds), `CloudScan` (per-scan infrastructure lifecycle), `CloudOrphan` (resources detected but not reconciled). Migration at `utils/migrate_cloud_v2.py`.
- `app/cloud_provider_data.py` — static AWS/Azure/GCP region+instance-type lists used by `/admin/cloud/credentials` and the ZAP admin form.
- `app/zap_utils.py` — ZAP automation plan validation + Docker container helpers. Not cloud-specific.
- `app/encryption.py` — Fernet-based `encrypt_value`, `decrypt_value`, `encrypt_json`, `decrypt_json`. Used for `CloudCredential.credentials_encrypted`.
- `app/tasks.py:execute_scan_task` — main scan-runner Celery task; cloud-provisioning branch lives here. `cloud_provision_task`, `cloud_teardown_task`, and `cloud_orphan_cleanup_task` (the last on a 15-min Celery Beat schedule) are also in this file.
- `app/admin_db.py` — Flask-Admin database explorer at `/admin/db`. Backup-before-use.
- Admin pages at `/admin/cloud/credentials`, `/admin/cloud/scans`, `/admin/cloud/orphans` (templates under `app/templates/admin/cloud/`). All protected by `@admin_required`, log to `AuditLog`, use the existing Bootstrap 5 form pattern.

## Working in this codebase

- **Run app locally:** see `genai-instructions.md` for the full setup; needs Redis + Celery worker.
- **Migrations:** Python scripts in `utils/migrate_*.py` that use `PRAGMA table_info` checks + `ALTER TABLE`. No Alembic. Idempotent re-runs are required.
- **Templates:** Bootstrap 5 + WTForms. Base template at `app/templates/base.html`. Admin pages extend the same base + use the `admin/` subfolder.
- **Encryption:** `from app.encryption import encrypt_json, decrypt_json` — never write plaintext credentials anywhere.
- **Audit logging:** every sensitive admin action writes to `AuditLog` via `AuditLog.log(user_id, action, resource_type, resource_id, details, ip_address)`.

## House style

- PEP 8, 4-space indent, snake_case functions, PascalCase classes.
- Always `@login_required`. Admin actions use `@admin_required`.
- No emojis in code or generated docs.
- Don't commit secrets or write them to logs in plaintext.
- Don't introduce raw `json.dump(...)` for files that kast also writes — atomic writes are part of the frozen contract.
- For any new admin page, include the audit-log call.

## Out of scope for v2.0

- Multi-cloud-per-org pricing comparisons
- VPC peering for private-target scanning (deferred to v2.1+)
- Self-service org-level credential rotation flows
- Auto-tuning of cloud spot pricing (keeps the existing config-driven max price)

## Lifecycle of this file

`CLAUDE.md` is the active-phase override. It will shrink to a thin pointer once kast 3.0 + kast-web 2.0 ship and `genai-instructions.md` is rewritten to describe the v2.0 patterns natively. Until then, treat this file as the source of truth for "what's actually being built right now."
