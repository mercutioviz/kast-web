# Changelog

All notable changes to kast-web are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.15] — 2026-11-09

### Added

- **Import a logo from a URL** — the Add Logo dialog now has two tabs: upload a file, or paste an image URL. The server fetches the image, shows a preview with the detected format, dimensions and the final URL after redirects, and only adds it once the user confirms. Fetched images go through exactly the same validation, SVG sanitization and PNG normalization as uploads. New routes `POST /logos/import/fetch`, `GET /logos/import/<token>/preview`, `POST /logos/import/confirm` and `POST /logos/import/<token>/discard`.
- **`app/url_fetch.py`** — SSRF-guarded outbound fetcher. http/https only on allowed ports, no credentials in the URL, every resolved address must be public (loopback, RFC1918, link-local including `169.254.169.254`, CGNAT, reserved, multicast, IPv4-mapped and 6to4-wrapped are all refused), the validated IP is pinned for the connection so DNS cannot rebind, redirects are followed manually with every hop re-validated, and the body is streamed under a hard byte cap and wall-clock deadline.
- `ReportLogo.source_url` records where an imported logo came from; the logo card shows "Imported from `<host>`".
- Per-user rate limit on URL imports (`LOGO_IMPORT_RATE_LIMIT`, default 10/min), backed by the existing Celery Redis instance.
- New idempotent migration `utils/migrate_logo_url_import.py`.

### Changed

- **Logo files moved out of `app/static/`** to `LOGO_STORAGE_DIR` (`instance/logos` by default; set `LOGO_STORAGE_DIR=/var/lib/kast-web/logos` in production `.env`). The migration relocates existing files and rewrites the stored paths.
- The file-upload and URL-import paths now share one persistence helper, `app.utils.persist_prepared_logo`.
- New config keys: `LOGO_STORAGE_DIR`, `LOGO_STAGING_TTL_SECONDS`, `LOGO_IMPORT_ALLOWED_PORTS`, `LOGO_IMPORT_MAX_REDIRECTS`, `LOGO_IMPORT_CONNECT_TIMEOUT`, `LOGO_IMPORT_READ_TIMEOUT`, `LOGO_IMPORT_TOTAL_DEADLINE`, `LOGO_IMPORT_RATE_LIMIT`.

### Security

- **Uploaded logos are no longer publicly readable.** nginx serves `/static` directly from disk, so every file under `app/static/uploads/logos/` was reachable at `https://<host>/static/uploads/logos/<name>` with no authentication, no CSP and no `nosniff` — bypassing the hardened headers on `/logos/<id>` added in 2.0.14. Logo storage now lives outside the static tree and is served only through the authenticated routes.
- URL-import staging is owner-scoped and expiring: a staging token is usable only by the user who created it, token shape is validated before any path join, and abandoned previews are swept after `LOGO_STAGING_TTL_SECONDS`.
- Remote `Content-Type` is recorded but never trusted; magic-byte sniffing decides the format. Import refusal messages never name a resolved address, so the endpoint cannot be used to map the network.

---

## [2.0.14] — 2026-11-05

### Added

- **Expanded report logo formats** — logo uploads now accept SVG, SVGZ, WebP, AVIF, GIF, BMP, TIFF and ICO alongside PNG and JPEG. Vector uploads stay vector all the way into the PDF (WeasyPrint renders SVG natively), so logos stay sharp at any scale; the other raster formats are normalized to PNG at upload time. The new `app/logo_media.py` owns the format registry, content sniffing, SVG sanitization and raster normalization.
- **Render derivative** — each logo now stores both the original upload and the file reports actually embed (`render_path` / `render_mime`), with the original kept for provenance and re-download. The kast CLI is handed only PNG or sanitized SVG via `--logo`, so nothing changes on the kast side. New route `GET /logos/<id>/render` serves that derivative and backs the management-page preview.
- New idempotent migration `utils/migrate_logo_formats.py` — adds `render_path`, `render_mime`, `width`, `height` to `report_logos`, backfills existing rows to use their original file, and creates `app/static/uploads/logos/render/`.
- Logo cards on `/logos/manage` now show a format badge, pixel dimensions, and a note (with a link to the original) when reports use a converted copy.

### Changed

- Logo upload limit raised from 2MB to 5MB, configurable via `LOGO_MAX_UPLOAD_BYTES`. Raster logos larger than `LOGO_MAX_DIMENSION` (default 2000px on the longest edge) are downscaled during normalization.
- New runtime dependencies: `Pillow` and `defusedxml`.

### Security

- Logo uploads are no longer trusted on their extension alone: magic bytes must agree with the declared extension, and raster uploads must decode cleanly under Pillow. A renamed archive or a corrupt image is now rejected instead of stored.
- Uploaded SVG is parsed with `defusedxml` (blocking XXE, entity expansion and external DTDs) and filtered through an element allowlist that strips scripting, animation elements, event handlers, external references, `javascript:` URLs and dangerous CSS. Only the sanitized document is written to disk.
- `/logos/<id>` and `/logos/<id>/render` now send `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and `Content-Disposition: inline`, so a logo opened by direct navigation cannot execute script.
- `Image.MAX_IMAGE_PIXELS` is capped to guard against decompression bombs.

---

## [2.0.13] — 2026-08-19

### Added

- **Server ZAP execution mode** — a new `server` `ZapConfiguration.execution_mode` alongside the renamed `local` ("Ephemeral Docker") and `remote` ("External ZAP") modes. kast-web manages a persistent ZAP Docker container that kast connects to as a remote API server; Start/Stop/Status/Logs container controls on the configs list now apply to Server ZAP configs instead of local ones. Configurable per-configuration `spider_type` (traditional/ajax/client), `poll_interval_seconds`, and `zap_profile`, all passed through to kast via `--set`/`--zap-profile`. New idempotent migrations: `utils/migrate_zap_spider_type.py`, `utils/migrate_zap_poll_interval.py`, `utils/migrate_zap_profile.py`.

---

## [2.0.12] — 2026-08-19

### Added

- **"Critical" severity support in ZAP live-progress tracking** — `ZapScanProgress` gained a `critical_alerts` column (`utils/migrate_zap_critical_severity.py`), and the live-progress polling API and scan-detail progress modal now surface a `Critical` alert count alongside High/Medium/Low/Informational, with a dedicated maroon badge (`.badge.bg-critical`). Prepares kast-web for kast 3.0.43+, which introduces a `Critical` severity level in its `Severity` enum.

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
