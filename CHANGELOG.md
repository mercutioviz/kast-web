# Changelog

All notable changes to kast-web are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.9] — 2026-05-26

### Fixed

- **Admin POST forms missed by v2.0.8 global CSRF rollout** — adding `CSRFProtect` to the app factory in v2.0.8 broke any raw `<form method="POST">` that wasn't using WTForms' `{{ form.hidden_tag() }}`. Symptom: clicking the affected button returned 400 Bad Request ("The CSRF token is missing"). Added `<input type="hidden" name="csrf_token">` to: toggle-active / reset-failed-attempts / delete-user on `/auth/users`, share-with-user and generate-public-link on the scan detail page, set-default / delete / upload on `/logos`, the `/admin/settings` save form, and the `/admin/audit-log` clear form. All `fetch()`-based AJAX calls were already passing `X-CSRFToken` and are unaffected.

---

## [2.0.8] — 2026-05-26

### Added

- **Batch scan (v1)** — admin/power_user-only `/scan/batch` page. Submit one textarea of targets (one per line, up to 50) and the same scan settings are applied to every target. Each target becomes its own `Scan` row, all sharing a `batch_id` UUID. The scan history page recognises `?batch_id=<uuid>` and renders an aggregate header (total / pending / running / completed / failed). Active-mode submissions show a Bootstrap confirmation modal listing every target before dispatch. Active and cloud-ZAP batches are staggered with `apply_async(countdown=i*8)` to avoid thundering-herd provisioning.
- **`utils/migrate_batch_id.py`** — idempotent migration adding the `batch_id VARCHAR(36)` column and index to `scans`.

### Security

- **Global CSRF protection** — `flask-wtf` `CSRFProtect` is now registered on the app factory; all state-changing fetch/AJAX calls include `X-CSRFToken`. Previously WTForms-rendered forms had CSRF tokens, but raw `fetch()` calls bypassed protection.

### Fixed

- **Target validation accepts `host:port`** — the new-scan and batch-scan forms now accept hostnames with an optional `:<port>` suffix (e.g. `127.0.0.1:8080`), matching what the kast CLI has accepted since 2.14. Previously the regex rejected port suffixes despite the backend handling them.

---

## [2.0.2] — 2026-05-15

Requires **kast 3.0+**.

### Added

- **Bulk scan operations** — select multiple scans in history, delete or re-run in one action.
- **Scan notes** — per-scan free-text annotation field; auto-saves on blur via AJAX.
- **Scan tags** — comma-separated tags on scans; tag filter on history page; badges in table.
- **Clone scan** — "Clone" button on scan detail pre-fills the new-scan form with all settings from an existing scan.
- **CSV export** — export the filtered scan history to a CSV file from the history page.
- **Execution log search** — client-side keyword highlight with Prev/Next navigation in the execution log viewer.
- **Profile description preview** — selecting a config profile on the new-scan page shows the profile description inline.
- **Dashboard scan trend chart** — 30-day daily scan activity chart on the admin dashboard (Chart.js).
- **Config profile import/export** — export profiles as YAML; import YAML files via an upload modal.
- **Password complexity enforcement** — registration and change-password forms now require at least one uppercase letter, one lowercase letter, and one digit.
- **Docker image** — `Dockerfile`, `docker-entrypoint.sh`, and `.dockerignore` for containerised deployment. Single image handles web and worker roles via CMD override (`serve` / `worker`).
- **pipx packaging** — `pyproject.toml` and `kast-web` CLI entry point (`kast-web serve`, `kast-web worker`, `kast-web dev`).
- **ZAP top-level nav dropdown** — dedicated ZAP menu in the main navbar linking to Plans and Configurations.
- **Split ZAP admin nav pills** — separate "ZAP Plans" and "ZAP Configs" pills in the admin panel navigation.
- **`docs/UPGRADING.md`** — step-by-step upgrade guide from kast 2.x + kast-web 1.x to the 3.0/2.0 coordinated release.

### Fixed

- HTML report CSS and logo assets not loading inside the sandboxed iframe viewer; assets are now inlined at render time.
- Execution log viewer: low-contrast yellow-on-dark text replaced with readable colour.
- ZAP configuration edit page returning 500 when stored credentials were encrypted with a rotated key; the page now shows a warning and allows re-entry.
- Cloud credential dropdown on ZAP config form showing only AWS credentials; all providers now appear regardless of selected execution mode.
- Admin pages (audit log, activity, settings, system info, users) not honouring the `admin-content` max-width layout.
- AI executive summary: Bearer token auth for LiteLLM-compatible proxy endpoints.
- AI executive summary: silent failure when decryption of stored API key fails; UI now restores correctly and surfaces the error.
- AI executive summary checkbox always rendered on new-scan form (previously hidden when AI was disabled org-wide).

### Security

- Application refuses to start in production when `SECRET_KEY` is the insecure built-in default.
- `ENCRYPTION_KEY` is now a separate environment variable from `SECRET_KEY`; cloud credential encryption no longer depends on the session signing key.
- Login lockout after 10 consecutive failed attempts; admin can unlock via the Users page.
- XSS fix in scan output rendering.

---

## [2.0.1] — 2026-04-10

### Fixed

- `upgrade_from_v115.py`: missing three Phase-E migration scripts in the delta list.
- `upgrade_from_v115.py`: `/var/lib/kast-web2` not chowned to `www-data` before service start.
- `install.sh`: non-interactive mode (`EXISTING_INSTALL_CHOICE` env var) for scripted deployments.

---

## [2.0.0] — 2026-03-01

Coordinated release with **kast 3.0**. Major new capabilities; not backwards-compatible with kast 2.x cloud mode (see `docs/MIGRATION_FROM_KAST_CLOUD.md`).

### Added

- **Cloud infrastructure module** (`app/cloud/`) — provision and tear down ephemeral ZAP instances on AWS, Azure, or GCP via Terraform and SSH. Replaces the cloud runtime that was previously inside the kast CLI.
  - Admin pages: `/admin/cloud/credentials`, `/admin/cloud/scans`, `/admin/cloud/orphans`.
  - Models: `CloudCredential` (encrypted per-provider credentials), `CloudScan` (lifecycle tracking), `CloudOrphan` (unreconciled resources).
  - Celery Beat job (`cloud_orphan_cleanup_task`) runs every 15 minutes to catch infrastructure that did not tear down cleanly.
- **AI executive summary** — Claude-powered narrative summary of scan findings displayed on the scan detail page. Configurable model and endpoint via admin settings; per-user BYOK Anthropic API key.
- **Admin-managed AI presets** — curated model and endpoint presets selectable from the AI settings admin page.
- **`utils/upgrade_from_v115.py`** — automated side-by-side migration script from kast-web 1.15.
- **`docs/MIGRATION_FROM_KAST_CLOUD.md`** — migration guide for kast 2.x cloud-mode users.

### Changed

- Cloud scan execution: kast CLI no longer manages cloud infrastructure. kast-web provisions the instance and passes a remote ZAP URL (`--set zap.execution_mode=remote`) to kast.
- `ENCRYPTION_KEY` environment variable introduced for encrypting cloud credentials at rest (separate from `SECRET_KEY`).

### Removed

- kast CLI cloud mode integration — kast 3.0 removes `--set zap.execution_mode=cloud`; kast-web handles provisioning end-to-end.

---

## [1.15] and earlier

Feature history before the v2.0 refactor:

- Multi-user authentication with roles (admin, power\_user, user, viewer).
- Scan ownership and per-user scan history.
- Report sharing with signed links.
- Admin dashboard, audit log, and user management panel.
- Logo upload and white-labelling for shared reports.
- Config profiles for saving and reusing scan settings.
- ZAP automation plan and configuration management.
- PDF report generation.
- Maintenance mode enforcement.
- Per-plugin execution logging.
- Scan result regeneration.
