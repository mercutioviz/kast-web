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

**Active phase: D — cloud migration.** Move the cloud-deployment subsystem from kast to kast-web. Deliverables D1–D8 + D11 land here. D9 (deprecation warning in kast) and D10 (deletion in kast) land in the kast repo.

## Critical: contracts frozen for v3.0

Do not change these surfaces without explicit, coordinated planning:

- **The kast↔kast-web contract** documented in `/home/mscollins/kast/docs/web-integration.md`. Atomic writes (`.tmp` + `rename(2)`), frozen filenames (`{plugin}.json`, `{plugin}_processed.json`, `kast_info.json`, `zap_scan_progress.json`, `missing_issue_ids.json`), file-presence state machine, polling channel.
- **The v2 CLI argv contract** (the `kast --target X --mode passive ...` shape). kast preserves this via a v2-argv translation wrapper, so kast-web's existing `subprocess.Popen([...])` invocations keep working unchanged.
- **The `_processed.json` per-plugin output format**, including kebab-case keys.
- **The issue registry data format** in `kast/data/issue_registry.json`.

Internal kast-web refactoring is free as long as these surfaces stay stable.

## Phase D re-architecture (important)

Kast-web today already stores cloud credentials and passes them to the kast CLI as env vars; the kast CLI then runs Terraform / SSH / ZAP-API itself. Phase D **inverts** this:

- kast-web takes over Terraform / SSH / ZAP provisioning (new module: `kast-web/app/cloud/`).
- kast-web spawns the kast CLI in **remote mode** (pointing at the provisioned ZAP URL + API key) instead of cloud mode.
- Cloud mode goes away from kast entirely (D10 in the kast repo).

See `/home/mscollins/kast/docs/v3-planning/04-kast-web-cloud-migration.md` for the file-by-file plan, DB migration design, Celery task layout, and admin UI surface.

## What's already in kast-web that's relevant to Phase D

- `app/models.py:ZapConfiguration` — currently stores encrypted local/remote/cloud configs in a single record. Phase D refactors this to reference a separate `CloudCredential` table.
- `app/cloud_provider_data.py` — static AWS/Azure/GCP region+instance-type lists used by ZAP admin forms. Stays as-is; reused by the new cloud-credentials UI.
- `app/zap_utils.py` — ZAP automation plan validation + Docker container helpers. Not cloud-specific; stays as-is.
- `app/encryption.py` — Fernet-based `encrypt_value`, `decrypt_value`, `encrypt_json`, `decrypt_json`. Used by all encrypted-credential storage; reused for `CloudCredential.credentials_encrypted`.
- `app/tasks.py:execute_scan_task` — the main scan-runner Celery task. Phase D adds the cloud-provision-then-remote flow before `subprocess.Popen([kast ...])`.
- `app/admin_db.py` — Flask-Admin database explorer at `/admin/db`. Backup-before-use. Not part of Phase D but present.

## Phase D file structure (target)

```
kast-web/app/cloud/
├── __init__.py
├── orchestrator.py             # provision / scan / teardown
├── providers/{aws,azure,gcp}.py
├── terraform_manager.py
├── ssh_executor.py
├── zap_api_client.py
├── cleanup.py                  # orphan detection + Celery Beat cleanup
├── diagnostics.py
├── routes.py                   # /api/cloud/* and /admin/cloud/*
└── terraform/{aws,azure,gcp}/  # ported from kast/terraform/
```

New DB tables (via `utils/migrate_cloud_v2.py`): `CloudCredential`, `CloudScan`, `CloudOrphan`.

New Celery tasks (in `app/tasks.py`): `cloud_provision_task`, `cloud_teardown_task`, `cloud_orphan_cleanup_task`. The last is scheduled by Celery Beat every 15 minutes.

New admin pages: `/admin/cloud/credentials`, `/admin/cloud/scans`, `/admin/cloud/orphans`. All protected by `@admin_required`, log to `AuditLog`, follow the existing Bootstrap 5 form pattern.

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
