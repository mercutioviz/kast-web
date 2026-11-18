# Open findings

Defects and inconsistencies found by test runs that are **not yet fixed**.

This file exists because `tests/runs/` is gitignored: the run reports that found
these live only on the machine that produced them. Anything here that is not
also captured in a `cases.md` case or a commit message would otherwise be lost.

**When you fix something here:** delete its entry, and make sure a case in
`.claude/skills/test-kast-web/cases.md` guards it. Several entries already have
a case; those are noted.

Last reviewed: 2026-11-18. The deploy-path contradiction that was item 1 is
resolved — kast-web 2.0 standardises on `/opt/kast-web` and `/var/lib/kast-web`
with no `2` variants.

Last reviewed: All entries re-verified against the working tree on
that date.

---

## Priority

1. `updateScanStatus` defined twice as a global (latent)
2. `allow_registration` gates nothing
3. System-info export is a stub
4. *(low priority — see below)* public-cloud items

Public-cloud fixes (AWS / Azure / GCP, `app/cloud/`) are **deliberately low
priority** per the project owner, 2026-11-18. They are recorded here for
completeness, not as release blockers.

---

## 1. `updateScanStatus` is defined twice as a global

Not a bug today — verified — but one refactor away from being one.

`app/static/js/main.js` defines `function updateScanStatus(scanId)`, a stub
marked "for future real-time updates" that logs to the console.
`app/templates/scan_detail.html` defines a different `function
updateScanStatus()` taking no arguments. Both are plain globals, so the second
to load wins.

It works only because of load ordering: the template's script sits in
`{% block content %}`, rendered at `base.html:189`, and calls `startPolling()`
at top level — capturing the correct reference into `setInterval` *before*
`main.js` loads at line 203 and overwrites the global.

Move that `startPolling()` call into `DOMContentLoaded` (which the same file
already uses elsewhere) and polling silently switches to `main.js`'s stub,
which fetches `/api/scans/undefined` and parses the 404's HTML as JSON. I
reproduced exactly that by calling `setInterval(updateScanStatus, 3000)` from
the console after page load.

Fix: rename or delete the `main.js` stub. It is dead code.

## 2. `allow_registration` is a setting that gates nothing

The admin settings page offers an "allow registration" checkbox. It persists
and round-trips correctly (`true` / `false` in `system_settings`), but it is
read in exactly two places:

- `app/routes/admin.py:134` — to render its own checkbox state
- `app/templates/admin/dashboard.html:313` — a status indicator

It gates no access path anywhere. `/auth/register` is `@login_required` and
admin-only — it is admin *user creation*, not public self-registration — so an
anonymous request is refused by `@login_required` regardless of the setting.

Either wire the setting to something or remove it; a toggle that implies
control over registration and has none is the same class of problem as the
public share links removed in `d8a6323`.

`TC-AUTH-130` currently fails on this. Its steps also assume `/auth/register`
is public self-registration, which is wrong and should be corrected when this
is addressed.

---

## 3. `/admin/system-info/export` is an unimplemented stub

`app/routes/admin.py`, `export_system_info()`:

```python
# This would call the same collection logic but return JSON
# For now, redirect to the main page
flash('Export functionality coming soon', 'info')
```

The system-info page itself renders fine. The export button leads to a flash
and a redirect. Either implement it or remove the control before the tag.

`TC-ADM-104` currently fails on this.

---

## 4. Smaller observations

- **`/favicon.ico` 404s on every page.** The file *does* exist, at
  `app/static/images/favicon.ico` — it simply is not served at the root path
  browsers request. Harmless, but it trips any "no console errors" assertion,
  `TC-SCAN-002` among them. (Corrected 2026-11-18: an earlier note here said
  the file was missing.)
- **`scan_results.status` is not maintained.** It holds `unknown` for most
  plugin rows while `/api/scans/<id>/status` derives completion from
  `executed_at`. Two sources of truth; the column looks authoritative and is not.
- **Test logos are written into the repo.** Uploads land in
  `instance/logos/originals/` inside the working tree rather than under
  `/var/lib/kast-web-test/`, so test runs leave artifacts in the checkout.
- **`testssl` dominates scan duration against plain-HTTP targets.** Four of five
  scans on 2026-11-17/18 took ~306s, of which ~300s was `testssl` waiting out
  its timeout against a target with no TLS listener; a fifth run with an
  identical configuration finished in 35s. Intermittent, not root-caused. Both
  harness targets (Juice Shop, WebGoat) are plain HTTP, so the suite pays this
  on most scans. A real HTTPS target would not hit it.

---

## 5. Public cloud — low priority

Found by the first-ever cloud tier run, 2026-11-18
(commit `0f4489f`). Deprioritised by the project owner.

### 5a. Editing a cloud credential destroys the stored secret

**Data loss.** `app/cloud/routes.py`, `admin_cloud_credentials_edit()`:

```python
# Only update credentials if the JSON field was filled in with non-placeholder data
new_creds = json.loads(form.credentials_json.data)
cred.credentials = new_creds
```

The comment describes a guard that was never written. The edit form deliberately
shows a placeholder — `{ "...": "credentials stored — paste new JSON to replace" }` —
and never re-displays the secret. Saving the form writes that placeholder over
the real credentials.

Verified: a credential holding
`{'access_key_id':'AKIATEST','secret_access_key':'CANARYvisible123'}` was edited
changing **only its name**. The POST returned 302 success and the stored value
became `{'...': 'credentials stored — paste new JSON to replace'}`. The secret
exists only in that column, so it is unrecoverable.

Fix: skip the assignment when the submitted JSON is empty or equals the
placeholder. Guarded by `TC-CLOUD-FULL-103`.

### 5b. Four CloudScan statuses are invisible in the admin UI

The code assigns ten statuses; `/admin/cloud/scans` filters cover six.

| Filter | Shows |
|---|---|
| `active` | `provisioning`, `scanning`, `tearing_down` |
| `failed` | `failed`, `orphaned` |
| `completed` | `torn_down` |

`scheduled`, `running`, `manual_review` and `completed` appear under no filter.
`running` and `manual_review` are the two an operator would most need to see.

Guarded by `TC-CLOUD-FULL-113`.

### 5c. Live cloud provisioning has never been tested

`terraform apply`, real instance provisioning, `cloud_provision_task` end to end
and teardown are all untested. The catalog defers them to a manual pre-release
gate. The non-destructive tier alone found a 500 and a credential-destroying
edit, so that gate is load-bearing.

---

## 6. Test coverage gaps

Not defects, but known holes:

- The regression-watch section of `cases.md` stops at **v2.0.7**; the project is
  on 2.0.15. No cases for 2.0.8–2.0.15 beyond the logo work.
- `TC-CFG-102` (apply profile to scan) has never been executed.
- The full-tier route×role authorization matrix has never been executed. This is
  the case class that concealed two defects in November 2026, so it is worth
  more than its position in the catalog suggests.
- `TC-LOGO-102/105/106/108/109` need image fixtures or external network access
  and were skipped.
