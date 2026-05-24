# Case catalog

Single source of truth for the test harness. Each case has an ID, tier, role(s),
preconditions, steps, expected behaviour, and the kind of evidence to capture.

Tiers are cumulative: `regression` runs smoke first; `full` runs regression first.

> **Where to scan against:** only `http://127.0.0.1:3000` (Juice Shop) or
> `http://127.0.0.1:8888` (WebGoat). Never any other target.

---

## Groups

| Prefix | Group |
|---|---|
| TC-AUTH | Authentication & session |
| TC-AUTHZ | Authorization matrix |
| TC-SCAN | Scan lifecycle |
| TC-POLL | Live polling (v2.0.5) |
| TC-REPORT | Reports |
| TC-SHARE | Sharing & transfer |
| TC-CFG | Config profiles |
| TC-ZAP | ZAP plans + configs |
| TC-LOGO | Logos / whitelabeling |
| TC-CLOUD | Cloud admin |
| TC-AI | AI plumbing |
| TC-ADM | Admin dashboard & system |
| TC-REG | Recently-shipped regression watch |
| TC-XCUT | Cross-cutting (CSRF, audit, errors) |
| TC-DARK | Dark mode (v2.0.4) |

---

# Smoke tier (~10 min, ~20 cases)

Must pass before any release. Aborts on first blocker.

### TC-AUTH-001 — admin login happy path
- **Tier:** smoke
- **Role:** t_admin
- **Pre:** env up, t_admin seeded
- **Steps:** GET /auth/login (200); POST /auth/login with `TEST_ADMIN_USERNAME` and password from .env.test
- **Expect:** 302 to /; session cookie set; subsequent GET / has 200 and renders "Dashboard"
- **Evidence:** HTTP status codes; screenshot of dashboard

### TC-AUTH-002 — logout clears session
- **Tier:** smoke
- **Role:** t_admin
- **Steps:** logged in as t_admin → GET /auth/logout → GET /
- **Expect:** /auth/logout 302 to /auth/login; GET / now 302 to /auth/login
- **Evidence:** HTTP statuses

### TC-AUTH-003 — wrong password rejected
- **Tier:** smoke
- **Role:** anonymous
- **Steps:** POST /auth/login with `t_admin` + wrong password
- **Expect:** stays on /auth/login (no 302 to /); flash contains "Invalid"; `failed_login_attempts` incremented in DB
- **Evidence:** flash text; sqlite query `select failed_login_attempts from users where username='t_admin'`

### TC-AUTH-010 — create the other test users via UI
- **Tier:** smoke (gates everything downstream)
- **Role:** t_admin
- **Pre:** t_admin logged in; only t_admin exists in DB
- **Steps:** for each row in config.md test-accounts table (excluding t_admin): GET /auth/register → fill username/email/password/first/last/role → POST → expect redirect with success flash; verify DB row created with correct role
- **Expect:** 4 users created (t_power, t_user, t_viewer, t_user2); each shows on /auth/users list with correct role badge
- **Evidence:** DB rows; screenshot of /auth/users list
- **Notes:** if users already exist (re-run), case **passes** without recreating

### TC-AUTH-020 — each non-admin role can log in
- **Tier:** smoke
- **Role:** t_power, t_user, t_viewer (3 sub-cases)
- **Pre:** TC-AUTH-010 passed
- **Steps:** log out; log in as each role
- **Expect:** dashboard renders; navbar shows correct role; admin-only nav items absent for t_user and t_viewer
- **Evidence:** screenshot per role

### TC-DARK-001 — dark mode toggle persists (v2.0.4)
- **Tier:** smoke
- **Role:** t_admin
- **Steps:** login → click dark-mode toggle in navbar → reload → log out → log back in
- **Expect:** `<html data-bs-theme="dark">` after toggle; localStorage `kw-theme` === `dark`; persists across reload and re-login; no FOUC flash on cold load
- **Evidence:** screenshot dark dashboard; `evaluate` localStorage value

### TC-SCAN-001 — passive scan happy path
- **Tier:** smoke
- **Role:** t_user
- **Pre:** WebGoat container up at 127.0.0.1:8888
- **Steps:** login as t_user → / → target `http://127.0.0.1:8888/WebGoat` → mode `passive` → submit
- **Expect:** redirect to scan detail; status goes pending → running → complete within 5 min (poll /scans/api/statuses); at least one plugin result row in DB
- **Evidence:** final status; sqlite row from `scans` and `scan_results`

### TC-SCAN-002 — scan detail page renders
- **Tier:** smoke
- **Role:** t_user
- **Pre:** TC-SCAN-001 produced a completed scan
- **Steps:** GET /scans/<id> ; GET /scans/<id>/execution-log
- **Expect:** plugin tabs render; execution log shows kast CLI output; no JS console errors
- **Evidence:** screenshot; console messages

### TC-REPORT-001 — HTML report viewer renders
- **Tier:** smoke
- **Role:** t_user
- **Pre:** completed scan from TC-SCAN-001
- **Steps:** GET /scans/<id>/report-html
- **Expect:** 200; report body renders with logo and findings sections
- **Evidence:** screenshot

### TC-POLL-001 — live polling updates running scan (v2.0.5)
- **Tier:** smoke
- **Role:** t_user
- **Steps:** submit a new passive scan; while it is running, open /scans/ in a second tab; observe status badge update without manual reload
- **Expect:** badge transitions running → complete within 30s of actual completion; no page reload triggered
- **Evidence:** screenshot mid-run + after-run; network log showing only /scans/api/statuses XHRs

### TC-POLL-002 — polling pauses on tab hide (v2.0.5)
- **Tier:** smoke
- **Role:** t_user
- **Steps:** with a running scan visible on /scans/, switch browser focus / hide tab for 15s
- **Expect:** no /scans/api/statuses requests during the hidden interval (visibilitychange handler)
- **Evidence:** Playwright network log

### TC-ADM-001 — admin dashboard renders
- **Tier:** smoke
- **Role:** t_admin
- **Steps:** GET /admin/dashboard
- **Expect:** 200; cards for total scans / users / running / failed render with numeric values
- **Evidence:** screenshot

### TC-ADM-002 — backup quick-action writes to test backup dir (v2.0.7)
- **Tier:** smoke
- **Role:** t_admin
- **Steps:** POST /admin/quick-action/backup-database
- **Expect:** 200 JSON `{"success": true, ...}`; new file appears in `/var/lib/kast-web-test/backups/kast.db.backup-*` (DB-parent dir, not CWD)
- **Evidence:** JSON response; `ls /var/lib/kast-web-test/backups/`

### TC-AUTHZ-SMOKE-001 — t_user cannot reach admin pages
- **Tier:** smoke
- **Role:** t_user
- **Steps:** GET /admin/dashboard, /admin/settings, /admin/audit-log, /auth/users
- **Expect:** each returns 403 or 302 to /
- **Evidence:** HTTP status per URL

### TC-AUTHZ-SMOKE-002 — t_viewer cannot submit a scan
- **Tier:** smoke
- **Role:** t_viewer
- **Steps:** POST / with valid scan form (target WebGoat, mode passive)
- **Expect:** 403 or flash denial; no new row in `scans` table
- **Evidence:** HTTP status; sqlite count before/after

### TC-AUTHZ-SMOKE-003 — t_user cannot submit active scan
- **Tier:** smoke
- **Role:** t_user
- **Steps:** POST / with mode `active`
- **Expect:** flash "do not have permission"; no scan row created
- **Evidence:** flash text; sqlite count

### TC-XCUT-001 — CSRF token required on POST
- **Tier:** smoke
- **Role:** t_admin
- **Steps:** POST /admin/quick-action/backup-database without a CSRF token in the form
- **Expect:** 400 (bad request)
- **Evidence:** HTTP status

---

# Regression tier (~45 min, ~80 cases)

Smoke +:

## Auth & session

### TC-AUTH-100 — lockout after N failed logins
- **Role:** anonymous
- **Steps:** POST /auth/login with t_user + wrong password 5 times
- **Expect:** 5th attempt sets `is_active=False` OR locks (depends on settings); after lockout, even correct password rejected with lockout flash
- **Evidence:** DB `is_active` / `failed_login_attempts`; flash text

### TC-AUTH-101 — admin resets failed attempts
- **Role:** t_admin
- **Pre:** TC-AUTH-100 left t_user locked
- **Steps:** /auth/users → click "reset failed attempts" on t_user
- **Expect:** `failed_login_attempts` back to 0; t_user can log in again
- **Evidence:** DB row; login retry

### TC-AUTH-110 — change password
- **Role:** t_user
- **Steps:** /auth/change-password → submit old + new
- **Expect:** redirect with success flash; old password fails; new password succeeds
- **Evidence:** two login attempts

### TC-AUTH-120 — maintenance mode blocks non-admin
- **Role:** t_admin then t_user
- **Steps:** as t_admin: /admin/settings → enable maintenance_mode → save; log out; try login as t_user
- **Expect:** t_user blocked with maintenance flash; t_admin still works; revert setting at end
- **Evidence:** flash text; settings round-trip

### TC-AUTH-130 — registration toggle
- **Role:** t_admin then anonymous
- **Steps:** /admin/settings → disable allow_registration → save; GET /auth/register as anonymous
- **Expect:** /auth/register 404 or redirect; revert setting at end
- **Evidence:** HTTP status

## Authorization (spot checks; full matrix lives in full tier)

### TC-AUTHZ-100 — t_user2 cannot see t_user's scans
- **Role:** t_user2
- **Pre:** t_user has a scan from TC-SCAN-001
- **Steps:** GET /scans/ as t_user2; GET /scans/<t_user_scan_id>
- **Expect:** scan absent from list; scan detail returns 403 or 404
- **Evidence:** HTTP status; DOM check

### TC-AUTHZ-101 — admin sees all scans
- **Role:** t_admin
- **Steps:** GET /scans/ (and /api/statuses)
- **Expect:** scans owned by all users visible
- **Evidence:** scan count vs DB total

### TC-AUTHZ-102 — config_overrides field gated to power_user+
- **Role:** t_user (negative), t_power (positive)
- **Steps:** submit scan form with `config_overrides` populated
- **Expect:** t_user: silently dropped or rejected; t_power: accepted and applied
- **Evidence:** DB scan row config

## Scan lifecycle

### TC-SCAN-100 — clone scan
- **Role:** t_user
- **Steps:** /scans/<id>/clone → submit
- **Expect:** new scan with same target/mode prefill; visible in history
- **Evidence:** DB row diff

### TC-SCAN-101 — rerun scan
- **Role:** t_user
- **Steps:** POST /scans/<id>/rerun
- **Expect:** new scan row with same config; original untouched
- **Evidence:** DB

### TC-SCAN-102 — delete scan
- **Role:** t_user (own scan), then t_user2 (other's scan — negative)
- **Expect:** owner delete succeeds; cross-user delete 403
- **Evidence:** HTTP status; DB row count

### TC-SCAN-103 — download zip
- **Role:** t_user
- **Steps:** GET /scans/<id>/download
- **Expect:** 200; content-type application/zip; body > 1 KB
- **Evidence:** response headers + size

### TC-SCAN-104 — CSV export
- **Role:** t_user
- **Steps:** GET /scans/export.csv
- **Expect:** 200; content-type text/csv; first row is header; row count matches user's scan count
- **Evidence:** CSV head

### TC-SCAN-105 — bulk delete
- **Role:** t_admin
- **Steps:** POST /scans/bulk with action=delete and ids of 2 scans
- **Expect:** rows removed; audit-log entries written
- **Evidence:** DB; AuditLog rows

### TC-SCAN-106 — notes + tags
- **Role:** t_user
- **Steps:** POST /scans/<id>/notes with note; POST /scans/<id>/tags with `tag1,tag2`
- **Expect:** notes and tags persist on reload
- **Evidence:** DB

### TC-SCAN-107 — failed scan path
- **Role:** t_user
- **Steps:** submit scan against `http://127.0.0.1:9` (unreachable)
- **Expect:** status transitions pending → running → failed; error message captured
- **Evidence:** DB row; execution log

## Sharing & transfer

### TC-SHARE-100 — share with internal user
- **Role:** t_user shares with t_user2
- **Steps:** /scans/<id>/share/user → select t_user2
- **Expect:** t_user2 sees the scan on their dashboard; t_user2 cannot delete it
- **Evidence:** dashboard render; DB ScanShare row

### TC-SHARE-101 — revoke user share
- **Role:** t_user
- **Steps:** /scans/<id>/shares → revoke
- **Expect:** t_user2 no longer sees the scan
- **Evidence:** dashboard render; ScanShare row deleted

### TC-SHARE-102 — public share token
- **Role:** t_user
- **Steps:** POST /scans/<id>/share/public; copy returned URL; open in fresh incognito context (no cookies)
- **Expect:** public URL renders report unauthenticated; revoke makes URL 404
- **Evidence:** screenshot unauth; HTTP status after revoke

### TC-SHARE-103 — transfer ownership (power_user+ only)
- **Role:** t_power
- **Steps:** /scans/<id>/transfer to t_user2
- **Expect:** scan.user_id updated to t_user2; t_user (original owner) no longer sees it
- **Evidence:** DB row; t_user's history

## Config profiles

### TC-CFG-100 — CRUD round trip
- **Role:** t_admin
- **Steps:** /scans/configs → create profile → edit → duplicate → set-default → delete
- **Expect:** each step succeeds with appropriate flashes; default flag exclusive (only one default at a time)
- **Evidence:** DB rows; default flag check

### TC-CFG-101 — YAML validate endpoint
- **Role:** t_admin
- **Steps:** POST /scans/configs/<id>/validate with good and bad payloads
- **Expect:** good → 200 ok; bad → 400 with errors array
- **Evidence:** JSON responses

### TC-CFG-102 — apply profile to scan
- **Role:** t_user
- **Steps:** submit scan selecting an existing profile
- **Expect:** scan row references profile id; profile settings applied
- **Evidence:** DB

## ZAP plans + configs (no container ops in this tier)

### TC-ZAP-100 — plan CRUD
- **Role:** t_admin
- **Steps:** /zap/plans → create → edit → preview → delete
- **Expect:** all steps 200/302; preview renders rendered YAML
- **Evidence:** DOM

### TC-ZAP-101 — plan YAML validate
- **Role:** t_admin
- **Steps:** POST /zap/plans/validate-yaml with valid and invalid payloads
- **Expect:** matches schema response
- **Evidence:** JSON

### TC-ZAP-102 — config CRUD
- **Role:** t_admin
- **Steps:** /zap/configs → create → edit → set-default → delete
- **Expect:** DB rows correct; default exclusive
- **Evidence:** DB

## Logos / whitelabeling

### TC-LOGO-100 — upload + set default + delete
- **Role:** t_admin
- **Steps:** /logos → upload PNG → /logos/<id>/set-default → /logos/<id>/delete
- **Expect:** file lands in uploads dir; set-default updates flag; delete removes both row and file
- **Evidence:** filesystem; DB

### TC-LOGO-101 — uploader-vs-admin delete permissions
- **Role:** t_user (uploader), t_user2 (other)
- **Steps:** t_user uploads; t_user2 attempts delete (negative); t_user deletes own (positive); t_admin deletes someone else's (positive)
- **Expect:** matches permission model
- **Evidence:** HTTP status

## Admin

### TC-ADM-100 — settings round trip
- **Role:** t_admin
- **Steps:** /admin/settings → toggle each top-level setting → save → revert
- **Expect:** settings persist; revert restores
- **Evidence:** DB SystemSettings rows

### TC-ADM-101 — audit log view
- **Role:** t_admin
- **Steps:** GET /admin/audit-log
- **Expect:** 200; recent actions visible (login, settings change, etc. from earlier cases)
- **Evidence:** DOM

### TC-ADM-102 — SMTP test
- **Role:** t_admin
- **Steps:** POST /admin/test-smtp (without configuring real SMTP)
- **Expect:** flash either success (if SMTP available) or graceful error (no 500)
- **Evidence:** HTTP status; flash text

### TC-ADM-103 — kast permissions test
- **Role:** t_admin
- **Steps:** POST /admin/test-kast-permissions
- **Expect:** 200 JSON with readable/writable booleans for results dir
- **Evidence:** JSON

### TC-ADM-104 — system info renders + exports
- **Role:** t_admin
- **Steps:** GET /admin/system-info; GET /admin/system-info/export
- **Expect:** page renders; export downloads JSON file
- **Evidence:** HTTP headers

## Recently-shipped regression watch (v2.0.3 → v2.0.7)

### TC-REG-204 — dark mode end-to-end (v2.0.4)
- Covered by TC-DARK-001 in smoke + reload + page-list check
- **Additional:** visit /, /scans/, /admin/dashboard, /admin/settings — all legible in dark; navbar contrast OK

### TC-REG-205 — live polling scoping (v2.0.5)
- **Role:** t_user, t_admin
- **Steps:** /scans/api/statuses as both
- **Expect:** t_user sees only own scan ids; t_admin sees all
- **Evidence:** JSON diff

### TC-REG-206 — non-ZAP scan detail loads without console error (v2.0.6)
- **Role:** t_user
- **Pre:** completed passive (non-ZAP) scan
- **Steps:** open /scans/<id>; capture console messages
- **Expect:** no TypeError on `zapProgressModal`
- **Evidence:** browser console log

### TC-REG-207 — backup writes to DB-parent dir (v2.0.7)
- Covered by TC-ADM-002 in smoke; just assert the path explicitly

## Cross-cutting

### TC-XCUT-100 — CSRF reject across POST routes
- **Role:** t_admin
- **Steps:** POST sample of state-changing routes without CSRF
- **Expect:** 400 for each
- **Evidence:** HTTP status table

### TC-XCUT-101 — audit-log entries for sensitive actions
- **Role:** t_admin
- **Steps:** perform: login, settings change, scan delete, user delete, audit-log clear; then GET /admin/audit-log
- **Expect:** one row per action with correct `action` and `user_id`
- **Evidence:** DB AuditLog rows

---

# Full tier (~2-3 hr, ~250 cases)

Regression + everything below.

## Authorization matrix — route × role

This is the bulk of the full tier. Rather than 94 routes × 4 roles enumerated
case-by-case, group routes by **access class** and assert one matrix per class.
Each class is a single test case; "pass" means every (route × role) cell matches
expected.

For each route in a class, log in as each role and issue the listed method.
"Expect" is the HTTP status the role should see. Treat 302 to /auth/login as
equivalent to 401 for anonymous.

### TC-AUTHZ-FULL-001 — public routes (anonymous OK)
- **Routes:**
  - `GET /auth/login`
  - `GET /auth/register` (when allow_registration on)
  - `GET /about`
- **Expect by role:** anonymous 200; all logged-in roles 200 or 302-to-/
- **Evidence:** status matrix

### TC-AUTHZ-FULL-002 — any-authenticated routes
- **Routes:**
  - `GET /`
  - `GET /scans/`
  - `GET /auth/profile`
  - `GET /auth/change-password`
  - `GET /scans/export.csv`
  - `GET /api/list` (logos)
  - `GET /api/stats`
  - `GET /api/scan-trend`
- **Expect:** anonymous 302 to /auth/login; all 4 logged-in roles 200
- **Evidence:** status matrix

### TC-AUTHZ-FULL-003 — power_user+ routes (scan submission with overrides, transfer)
- **Routes:**
  - `POST /` with `scan_mode=active`
  - `POST /` with `config_overrides=...`
  - `POST /scans/<id>/transfer`
- **Expect:** anonymous 302; t_viewer 403; t_user 403 or silent-drop; t_power 200/302; t_admin 200/302
- **Evidence:** status matrix; DB side-effect check

### TC-AUTHZ-FULL-004 — admin-only routes
- **Routes:** every route under `/admin/*`, `/auth/users*`, `/auth/users/<id>/*`, `/zap/configs*` write methods, `/zap/plans*` write methods, `/admin/cloud/credentials*`, `/admin/cloud/orphans*`, `/admin/cloud/scans*`, `/admin/import-scan`, `/admin/quick-action/*`, `/admin/clear-audit-log`, `/admin/test-smtp`, `/admin/test-kast-permissions`, `/admin/system-info*`
- **Expect:** anonymous 302; t_viewer / t_user / t_power 403; t_admin 200/302
- **Evidence:** status matrix

### TC-AUTHZ-FULL-005 — owner-or-admin routes (scan mutation)
- **Routes:** all `POST /scans/<id>/...` write methods (delete, notes, tags, rerun, share, transfer, regenerate-report, send-email)
- **Setup:** scan owned by t_user
- **Expect by accessor:** anonymous 302; t_viewer 403; t_user2 403; t_user 200/302; t_power 403 (not owner, not admin); t_admin 200/302
- **Evidence:** status matrix

### TC-AUTHZ-FULL-006 — viewer read-only
- **Role:** t_viewer
- **Setup:** scans owned by other users; shares granted to t_viewer
- **Expect:** can GET /scans/, /scans/<shared_id>, /scans/<shared_id>/report-html; cannot POST anything
- **Evidence:** status matrix

## Scan lifecycle — full

### TC-SCAN-FULL-200 — active scan against juice-shop
- **Role:** t_power
- **Pre:** kw-test-juiceshop container up
- **Steps:** submit scan target `http://127.0.0.1:3000` mode `active`; wait up to 10 min
- **Expect:** completes (not failed); produces ≥1 high/medium finding
- **Evidence:** DB scan_results rows; finding counts

### TC-SCAN-FULL-201 — active vs passive finding deltas
- **Role:** t_power
- **Pre:** completed passive + active scans against juice-shop
- **Expect:** active scan reports a superset of passive findings (or at least different plugin set)
- **Evidence:** finding count diff

### TC-SCAN-FULL-300 — files browser deep navigation
- **Role:** t_user
- **Steps:** /scans/<id>/files; click into nested subdirs via /scans/<id>/files/<subpath>; view individual files
- **Expect:** traversal stays inside scan dir (no `..` escapes); each file renders
- **Evidence:** path stability; spot-check a known file

### TC-SCAN-FULL-301 — regenerate-report
- **Role:** t_user
- **Steps:** POST /scans/<id>/regenerate-report
- **Expect:** 200; HTML report updated mtime; report still loads
- **Evidence:** filesystem mtime; report HTTP 200

## ZAP — container ops + IP detect

### TC-ZAP-FULL-200 — container lifecycle
- **Role:** t_admin
- **Pre:** local ZAP config with execution_mode=local
- **Steps:** /zap/configs/<id>/start-container → status (≤30s, expect "running") → logs (200 with output) → stop-container → status (stopped) → remove-container
- **Expect:** all transitions succeed; container removed at end
- **Evidence:** `docker ps -a` between steps

### TC-ZAP-FULL-300 — detect-ip endpoint
- **Role:** t_admin
- **Steps:** GET /zap/detect-ip
- **Expect:** JSON with at least one IP for host interface
- **Evidence:** JSON

### TC-ZAP-FULL-301 — check-cloud-tools
- **Role:** t_admin
- **Steps:** GET /zap/check-cloud-tools
- **Expect:** JSON with terraform / ssh availability booleans
- **Evidence:** JSON

## Cloud admin — non-destructive

### TC-CLOUD-FULL-100 — AWS credential CRUD + encryption round-trip
- **Role:** t_admin
- **Steps:** /admin/cloud/credentials/new → provider AWS → fill access_key/secret_key → save; check DB row's `credentials_encrypted` column is opaque (not plaintext); edit credential and verify decrypted form prepopulates; delete
- **Expect:** plaintext keys never appear in DB column; UI decrypts correctly
- **Evidence:** sqlite query on column; rendered form values

### TC-CLOUD-FULL-101 — Azure credential CRUD
- Same shape as 100, provider=Azure (subscription_id, tenant_id, client_id, client_secret)

### TC-CLOUD-FULL-102 — GCP credential CRUD
- Same shape, provider=GCP, service_account_json blob

### TC-CLOUD-FULL-110 — orphans page renders
- **Role:** t_admin
- **Steps:** GET /admin/cloud/orphans
- **Expect:** 200; renders even with empty table; no JS console errors
- **Evidence:** screenshot

### TC-CLOUD-FULL-111 — scans page renders
- **Role:** t_admin
- **Steps:** GET /admin/cloud/scans
- **Expect:** 200; empty-state messaging if no cloud scans
- **Evidence:** screenshot

> **Out of scope (live):** terraform apply, real instance provisioning,
> `cloud_provision_task` end-to-end. Cover those in a manual pre-release gate.

## AI plumbing — no live calls

### TC-AI-FULL-100 — settings page renders + saves
- **Role:** t_admin
- **Steps:** /admin/ai/settings → toggle enable flag → save → revert
- **Expect:** DB AISettings row reflects toggle
- **Evidence:** DB

### TC-AI-FULL-101 — model preset CRUD
- **Role:** t_admin
- **Steps:** add → toggle → delete a model preset
- **Expect:** DB AIModelPreset row created/toggled/deleted; UI matches
- **Evidence:** DB

### TC-AI-FULL-102 — endpoint preset CRUD
- **Role:** t_admin
- Same shape as 101 for AIEndpointPreset

### TC-AI-FULL-103 — summary endpoint with no key configured
- **Role:** t_user
- **Steps:** POST /api/ai/summary/<scan_id>/generate without saving an API key first
- **Expect:** 4xx response with a clear "no API key" error (no 500, no leaked stack trace)
- **Evidence:** JSON error body

### TC-AI-FULL-104 — per-user API key save
- **Role:** t_user
- **Steps:** /auth/save-api-key → POST a placeholder key
- **Expect:** DB users.anthropic_api_key_encrypted populated (opaque); revealing or clearing it works
- **Evidence:** DB; encryption opaque

## API endpoints (full)

### TC-API-FULL-100 — /api/stats shape
- **Role:** t_admin
- **Expect:** JSON keys cover total scans, users, running, failed; values numeric
- **Evidence:** JSON

### TC-API-FULL-101 — /api/scan-trend shape
- **Role:** t_admin
- **Expect:** JSON list of `{date, count}` for last N days
- **Evidence:** JSON

### TC-API-FULL-102 — /api/statuses scoping
- Covered by TC-REG-205 — re-run here for full

### TC-API-FULL-103 — /api/list (logos)
- **Role:** t_admin
- **Expect:** array of logo objects; only `can_delete=true` for admin or own uploads
- **Evidence:** JSON

### TC-API-FULL-104 — /api/<logo_id>/info
- **Role:** t_admin
- **Expect:** 200 for existing; 404 for missing
- **Evidence:** status

### TC-API-FULL-105 — /api/cloud/orphans
- **Role:** t_admin
- **Expect:** JSON list (possibly empty)
- **Evidence:** JSON

### TC-API-FULL-106 — /api/scans, /api/scans/<id>, /api/scans/<id>/status
- **Role:** t_admin
- **Expect:** shapes consistent; status endpoint matches scans table

### TC-API-FULL-107 — /api/plugins
- **Role:** t_admin
- **Expect:** list of plugin metadata

### TC-API-FULL-108 — /api/users/active
- **Role:** t_admin
- **Expect:** list of currently-active users (logged in within session-lifetime window)

## Admin — full

### TC-ADM-FULL-200 — backup → restore round trip
- **Role:** t_admin
- **Steps:** trigger backup; record file path; stop Flask; replace `kast.db` with the backup; restart; verify a known scan still present
- **Expect:** DB round-trips cleanly
- **Evidence:** DB row check
- **Notes:** invasive; only in full tier, and only with `--keep-env`

### TC-ADM-FULL-201 — clear audit log
- **Role:** t_admin
- **Steps:** /admin/audit-log → clear; observe the **clear action itself** logged as a new entry
- **Expect:** previous rows gone; one new row recording the clear
- **Evidence:** DB count before/after

### TC-ADM-FULL-202 — import-scan
- **Role:** t_admin
- **Pre:** export a completed scan as zip
- **Steps:** /admin/import-scan → upload the zip
- **Expect:** new scan row in DB with imported data; report renders
- **Evidence:** DB; rendered report

## Config profiles — full

### TC-CFG-FULL-200 — export / import round trip
- **Role:** t_admin
- **Steps:** create profile → /configs/<id>/export → save file → /configs/import → upload that file
- **Expect:** new profile matches exported one byte-for-byte (apart from id/timestamps)
- **Evidence:** DB row compare

## Sharing — full

### TC-SHARE-FULL-100 — shares index page
- **Role:** t_user
- **Steps:** GET /scans/<id>/shares
- **Expect:** rows for active shares; revoke buttons present
- **Evidence:** DOM

### TC-SHARE-FULL-101 — send-email on completed scan
- **Role:** t_user
- **Steps:** POST /scans/<id>/send-email with recipient
- **Expect:** if SMTP configured, success flash; if not, graceful error (no 500)
- **Evidence:** flash text; HTTP status

## Errors

### TC-ERR-100 — 404 template
- **Role:** anonymous
- **Steps:** GET /no-such-route
- **Expect:** 404; custom 404 template renders (not Flask default)
- **Evidence:** DOM contains app-specific text

### TC-ERR-101 — 403 template
- **Role:** t_user
- **Steps:** GET /admin/settings
- **Expect:** 403 or 302 with denial flash; if 403, template renders
- **Evidence:** DOM

### TC-ERR-102 — 500 template
- **Pre:** force a 500 (e.g. invalid scan id with malformed path that hits an unhandled branch); only feasible if you can reliably trigger one
- **Notes:** skip if you can't safely trigger; do not introduce a debug-only 500 route

## Cross-cutting — full

### TC-XCUT-FULL-100 — audit-log entry written for every sensitive action
- **Role:** t_admin
- **Steps:** exhaustive: for every route in TC-AUTHZ-FULL-004 plus owner-or-admin writes, perform the action, then query AuditLog for an entry with matching `action` and `user_id` within 5s
- **Expect:** every sensitive action produces an audit row
- **Evidence:** DB AuditLog full diff

