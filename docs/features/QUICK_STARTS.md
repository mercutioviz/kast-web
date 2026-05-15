# Quick-Start Guides

Practical how-to guides for specific kast-web features. Each section is self-contained.

---

## Table of Contents

1. [Celery Worker](#1-celery-worker)
2. [Config Profiles](#2-config-profiles)
3. [Logo White-Labeling](#3-logo-white-labeling)
4. [Email Notifications](#4-email-notifications)
5. [Execution Logs and Plugin Debugging](#5-execution-logs-and-plugin-debugging)
6. [Importing CLI Scans](#6-importing-cli-scans)

---

## 1. Celery Worker

The Celery worker is required for all scan execution. Scans will stay in "pending" indefinitely if the worker is not running.

### Production (systemd)

```bash
sudo systemctl status kast-celery     # check status
sudo systemctl start kast-celery      # start
sudo systemctl enable kast-celery     # start on boot
sudo journalctl -u kast-celery -f     # live logs
```

### Development (manual)

```bash
# Terminal 1 — start the worker
source venv/bin/activate
kast-web worker --loglevel debug

# Terminal 2 — start the web server
kast-web dev
```

Or with the packaged CLI from any directory:

```bash
kast-web worker          # uses default loglevel=info
kast-web serve           # production web server (port 8000)
```

### Verify the worker is responding

```bash
source venv/bin/activate
celery -A celery_worker.celery inspect ping
# Expected: -> celery@hostname: OK  pong
```

### Check registered tasks

```bash
celery -A celery_worker.celery inspect registered
# Should include: app.tasks.execute_scan_task
```

### Check active / in-progress tasks

```bash
celery -A celery_worker.celery inspect active
```

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Scans stuck on "pending" | Worker not running | Start `kast-celery` service or `kast-web worker` |
| "Connection refused" on startup | Redis not running | `sudo systemctl start redis-server` |
| Worker starts, tasks don't execute | Tasks not registered | Confirm `app.tasks.execute_scan_task` appears in `inspect registered` |
| Worker crashes on import | Wrong working directory | Ensure you're running from the repo root or using the `kast-web` CLI |

---

## 2. Config Profiles

Config profiles let you save named scan configurations (plugin rate limits, timeouts, concurrency) and reuse them across scans. Power users and admins can create profiles; standard users can use profiles that have been marked as available to them.

### Access control by role

| Role | View profiles | Create / edit | Use in scans |
|---|---|---|---|
| Viewer | No | No | No |
| User | Standard-only | No | Standard-only |
| Power User | All | Yes | All |
| Admin | All | Yes | All |

### Creating a profile

1. Navigate to **Config Profiles** in the top navigation.
2. Click **Create New Profile**.
3. Fill in name, description, and YAML configuration.
4. Click **Validate YAML** — fix any errors before saving.
5. Set **Allow Standard Users** if the profile should be available to all users.
6. Click **Create Profile**.

### YAML configuration examples

**Balanced (general purpose):**
```yaml
global:
  timeout: 300
  retry_count: 2

plugins:
  subfinder:
    rate_limit: 150
    timeout: 30
    max_time: 10
    concurrent_goroutines: 10
  katana:
    concurrency: 10
    rate_limit: 150
    delay: 0
  ftap:
    concurrency: 10
    rate_limit: 100
```

**Stealth (low detection, production targets):**
```yaml
global:
  timeout: 600
  retry_count: 1

plugins:
  subfinder:
    rate_limit: 5
    timeout: 60
    max_time: 20
    concurrent_goroutines: 3
  katana:
    concurrency: 3
    rate_limit: 5
    delay: 2
  ftap:
    concurrency: 3
    rate_limit: 5
    delay: 2
```

**Aggressive (dev/test/UAT environments only):**
```yaml
global:
  timeout: 180
  retry_count: 3

plugins:
  subfinder:
    rate_limit: 300
    timeout: 20
    max_time: 5
    concurrent_goroutines: 20
  katana:
    concurrency: 20
    rate_limit: 500
    delay: 0
  ftap:
    concurrency: 15
    rate_limit: 300
```

To see all configurable plugin settings: `kast --config-schema`

### Selecting a profile on a scan

On the new-scan page, select a profile from the **Config Profile** dropdown. A description preview appears below the dropdown. Profile settings are passed to kast at runtime; they can be overridden per-scan by power users and admins using the config overrides field.

### Importing and exporting profiles

- **Export**: open a profile's detail page and click **Export** to download a YAML file.
- **Import**: on the profile list page, click **Import Profile**, choose a YAML file, and submit. Conflicting names are resolved by appending " (Imported)".

### Troubleshooting

**Profile not visible to a user** — check the "Allow Standard Users" flag and the user's role.

**Cannot delete a profile** — the profile is referenced by one or more scans. The usage count is shown on the profile detail page.

**YAML validation errors** — use spaces (not tabs) for indentation; verify plugin names against `kast --list-plugins`.

---

## 3. Logo White-Labeling

Upload logos to brand scan reports for different clients or organizations.

### Upload a logo

1. Log in as admin.
2. Navigate to **Admin > Manage Logos**.
3. Click **Upload New Logo**.
4. Enter a name and optional description; choose a PNG or JPG file (max 2 MB).
5. Click **Upload Logo**.

### Set the system default

On the logo list, click **Set Default** on the logo you want used for all new scans. The default applies to reports unless overridden at the scan level.

### Assign a logo to a specific scan

On the new-scan form, select a logo from the **Logo** dropdown. Leaving it at "Use System Default" uses whatever logo is set as the default at the time the report is generated.

### Tips for multiple clients

Create one logo entry per client. When starting a scan for a specific client, select their logo from the dropdown. For most scans, set your standard logo as the system default.

### Troubleshooting

**Logo not appearing in report** — verify the logo file exists: `ls -la app/static/uploads/logos/`. Check the application log for any logo rendering errors.

**Upload fails** — confirm the file is under 2 MB and is PNG, JPG, or JPEG format. Verify the uploads directory is writable: `ls -ld app/static/uploads/logos/`.

---

## 4. Email Notifications

Send completed scan reports to recipients as email attachments.

### Configure SMTP (admin only)

1. Go to **Admin > Settings > Email Settings**.
2. Enable email functionality.
3. Enter your SMTP details and click **Test SMTP Connection** before saving.

Common provider settings:

| Provider | Host | Port | TLS |
|---|---|---|---|
| Gmail | smtp.gmail.com | 587 | Yes |
| Microsoft 365 | smtp.office365.com | 587 | Yes |
| SendGrid | smtp.sendgrid.net | 587 | Yes (username: `apikey`) |

For Gmail, generate an app-specific password at `myaccount.google.com/apppasswords` — do not use your regular account password.

### Send a report by email

1. Open a completed scan's detail page.
2. Click **Send via Email**.
3. Enter one or more recipient addresses (up to 10, comma-separated).
4. Click **Send Email**.

Email is delivered asynchronously via Celery. The UI shows "Email queued for delivery" on success.

### Troubleshooting

**"Email functionality is disabled"** — enable it in Admin > Settings > Email Settings.

**"Authentication failed"** — verify credentials; for Gmail use an app password, not your account password.

**Email queued but never delivered** — the Celery worker is not running. Check `sudo systemctl status kast-celery` and review logs with `sudo journalctl -u kast-celery -f`.

**"Connection timeout"** — verify your firewall allows outbound SMTP on the configured port. Try 587, 465, or 25 if one is blocked.

---

## 5. Execution Logs and Plugin Debugging

kast-web captures the full execution log from every scan and splits it into per-plugin log files automatically.

### Viewing the execution log

On a scan's detail page, click **View Execution Log** in the action sidebar. The log opens in the browser with a search bar for navigating to specific terms.

To download the log for offline analysis or sharing: click **Download Log** in the log viewer.

### Per-plugin log files

After each scan, the system creates individual `<plugin>_plugin.log` files alongside the main execution log:

```
/var/lib/kast-web/results/example.com-20250112-143000/
  kast_execution.log          full combined log
  subfinder_plugin.log        subfinder output only
  katana_plugin.log           katana output only
  nuclei_plugin.log           nuclei output only
```

Access them via the web UI: on the scan detail page, click **View Output Files**, then open any `*_plugin.log` file.

Or directly on the filesystem:

```bash
# View a specific plugin's log
cat /var/lib/kast-web/results/<scan-dir>/subfinder_plugin.log

# Search for errors across all plugin logs in a scan
grep -i "error\|failed" /var/lib/kast-web/results/<scan-dir>/*_plugin.log

# Compare the same plugin across two scans
diff scan1/subfinder_plugin.log scan2/subfinder_plugin.log
```

### Common plugin failure patterns

| Symptom | What to look for in the log | Resolution |
|---|---|---|
| Plugin shows "Failed", no details | `[!]` or `Error:` lines in `<plugin>_plugin.log` | Open the per-plugin log |
| Timeout | `Execution timeout after N seconds` | Run with fewer plugins or increase timeout in config profile |
| Missing tool | `Required command 'X' not found` | `sudo apt install <tool>` on the kast-web host |
| API rate limit | `API rate limit exceeded. Retry in Ns` | Wait and re-run; use a stealth config profile |

### Troubleshooting

**No per-plugin logs created** — confirm `kast_execution.log` exists; if it is missing the scan did not start. Check that the Celery worker is running.

**Execution log viewer slow** — the log is large (> 10 MB). Use the Download button and open the file locally.

**"No execution log available"** — the scan predates the logging feature, or the output directory was cleaned up.

---

## 6. Importing CLI Scans

Bring results from a kast CLI run into kast-web as a managed scan, making them visible in scan history, shareable, and reportable.

### Requirements

- Admin account.
- The CLI results directory must be readable by the web server user (`www-data` for systemd installs; the container user for Docker).
- Results must contain `*_processed.json` files (produced by kast's normal output pipeline).

### Import steps

1. Run a kast scan from the CLI and note the output directory:
   ```bash
   kast -t example.com -o ~/kast_results
   ls ~/kast_results/
   # example.com-20250112-143000/
   ```

2. Make the directory readable by the web server:
   ```bash
   sudo chmod -R o+rX /home/youruser/kast_results/example.com-20250112-143000
   ```

3. In kast-web, go to **Admin Dashboard** and click **Import Scan**.

4. Enter the **absolute path** to the results directory (e.g., `/home/youruser/kast_results/example.com-20250112-143000`).

5. Select the user to assign the scan to and click **Import Scan**.

### What gets imported

| Field | Source |
|---|---|
| Target | Directory name |
| Scan mode | Inferred from plugin set (active vs. passive) |
| Plugins | Filenames of `*_processed.json` files |
| Results | Existing JSON output files |
| Report | Existing HTML report if present |
| Timestamps | File modification times |

### Common paths

- Default CLI output: `~/kast_results/`
- System-wide results: `/var/lib/kast/results/`
- Custom output (`-o` flag): wherever you specified

### Troubleshooting

**"Directory not found"** — use an absolute path, not `~/...`. Verify with `ls /absolute/path/to/dir`.

**"No KAST result files found"** — confirm the directory contains files ending in `_processed.json`. The kast scan must have completed successfully.

**"Directory is not readable"** — run `sudo chmod -R o+rX /path/to/results`, or copy the results to a location the web server can reach.

**Duplicate import** — the importer checks for existing scans pointing to the same directory and will reject a second import of the same path.
