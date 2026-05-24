# Case catalog

Single source of truth for the test harness. Each case has an ID, tier, role(s),
preconditions, steps, expected behaviour, and the kind of evidence to capture.

Tiers are cumulative: `regression` runs smoke first; `full` runs regression first.

> **Where to scan against:** only `http://127.0.0.1:3000` (Juice Shop) or
> `http://127.0.0.1:8888` (Hackazon). Never any other target.

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
- **Pre:** hackazon container up at 127.0.0.1:8888
- **Steps:** login as t_user → / → target `http://127.0.0.1:8888` → mode `passive` → submit
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
- **Steps:** POST / with valid scan form (target hackazon, mode passive)
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

> Populated in a follow-up commit. Includes:
> - Full authz matrix (~94 routes × 4 roles)
> - Active scans against juice-shop
> - ZAP container start/stop/logs/status/remove
> - Cloud admin (credential CRUD + encryption round-trip; scans / orphans page; check-cloud-tools). No live terraform apply.
> - AI plumbing (settings + preset CRUD + no-key error states)
> - All API endpoints (statuses, stats, scan-trend, logos/api/list, etc.)
> - 404/403/500 error templates
> - File browser deep paths
> - Backup restore round trip
> - Audit log clear
