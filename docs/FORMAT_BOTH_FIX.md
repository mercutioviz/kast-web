# Fix: --format both Argument Implementation

This document describes the fix for ensuring KAST generates both HTML and JSON outputs.

## Problem

The `--format both` CLI argument was not being passed to KAST in all execution paths, resulting in incomplete output formats (either HTML or JSON only, depending on KAST's default behavior).

## Solution

Added `--format both` to all KAST CLI command constructions that generate scan outputs.

## Files Modified

### 1. app/tasks.py

**Line 51 - execute_scan_task():**
```python
# Build command
kast_cli = current_app.config['KAST_CLI_PATH']
cmd = [kast_cli, '-t', target, '-m', scan_mode, '--format', 'both']  # ← Added --format both
```

**Purpose:** Ensures async scans via Celery generate both formats.

**Line 239 - regenerate_report_task():**
```python
# Build command with --report-only flag and format both
kast_cli = current_app.config['KAST_CLI_PATH']
cmd = [kast_cli, '--report-only', str(output_dir), '--format', 'both']  # ← Added --format both (after directory)
```

**Purpose:** Ensures report regeneration produces both HTML and JSON outputs.

### 2. app/utils.py

**Line 85 - execute_kast_scan():**
```python
# Build command
kast_cli = current_app.config['KAST_CLI_PATH']
cmd = [kast_cli, '-t', target, '-m', scan_mode, '--format', 'both']  # ← Already present
```

**Purpose:** Ensures synchronous scans generate both formats (though primarily async scans are used).

## Commands Not Modified

### app/utils.py - get_available_plugins()

**Line 16:**
```python
[kast_cli, '--list-plugins']
```

**Why not modified:** This command only lists available plugins and doesn't generate scan output files. The `--format` flag is not applicable here.

## Verification

### All KAST CLI Command Locations

Verified all locations where KAST CLI is invoked:

```bash
grep -n "kast_cli" app/tasks.py app/utils.py
```

**Results:**
1. ✅ `app/tasks.py:51` - execute_scan_task() - HAS `--format both`
2. ✅ `app/tasks.py:237` - regenerate_report_task() - HAS `--format both`
3. ✅ `app/utils.py:85` - execute_kast_scan() - HAS `--format both`
4. ⏭️ `app/utils.py:16` - get_available_plugins() - N/A (doesn't generate outputs)

## Testing

### Verification Script

Created `verify_format_both.py` to automatically check if both formats are present:

```bash
python verify_format_both.py
```

**What it checks:**
- Finds most recent completed scan
- Verifies `report.html` exists (HTML format)
- Verifies `*_processed.json` files exist (JSON format)
- Reports file sizes and details

### Manual Verification

**1. Check logs for command:**
```bash
# View Celery logs
tail -f /path/to/celery_worker.log

# Look for:
# "Executing KAST command: /usr/local/bin/kast -t example.com -m passive --format both ..."
```

**2. Check scan output directory:**
```bash
cd /opt/kast-results
cd $(ls -t | head -1)  # Go to most recent scan
ls -la

# Expected files:
# report.html              ← HTML format
# subfinder_processed.json ← JSON format (per plugin)
# nmap_processed.json
# ...other plugin JSON files
```

### Test Scenarios

#### Scenario 1: New Scan
1. **Restart Celery worker** (critical!)
   ```bash
   pkill -f "celery -A celery_worker.celery worker"
   celery -A celery_worker.celery worker --loglevel=info
   ```
2. Create new scan via web interface
3. Check logs for `--format both`
4. Verify output directory has both formats

#### Scenario 2: Report Regeneration
1. Go to completed scan detail page
2. Click "Regenerate Report" button
3. Check logs for regeneration command with `--format both`
4. Verify both HTML and JSON are updated in output directory

## Expected Behavior

### New Scans (execute_scan_task)

**Command logged:**
```
Executing KAST command: /usr/local/bin/kast -t example.com -m passive --format both -o /opt/kast-results/example.com-20251120-001234
```

**Output directory structure:**
```
example.com-20251120-001234/
├── report.html                    ← HTML report
├── subfinder_processed.json       ← JSON outputs (one per plugin)
├── nmap_processed.json
├── nuclei_processed.json
└── ...
```

### Report Regeneration (regenerate_report_task)

**Command logged:**
```
Executing KAST report regeneration: /usr/local/bin/kast --report-only --format both /opt/kast-results/example.com-20251120-001234
```

**Result:**
- Regenerates `report.html` from existing JSON data
- Ensures JSON files are also regenerated/validated
- Both formats updated in the same directory

## Important Notes

### 1. Celery Worker Restart Required

⚠️ **After updating `app/tasks.py`, you MUST restart the Celery worker:**

```bash
# Using systemd
sudo systemctl restart kast-celery

# Or manually
pkill -f "celery -A celery_worker.celery worker"
celery -A celery_worker.celery worker --loglevel=info
```

The code changes won't take effect until the worker is restarted.

### 2. Both Formats Required

The application expects **both formats** to function properly:

- **HTML (`report.html`):** User-facing visual report
- **JSON (`*_processed.json`):** Machine-readable data for:
  - Plugin results display in web interface
  - Database storage of findings
  - Programmatic access to scan data

### 3. KAST Version Compatibility

Verify your KAST version supports `--format both`:

```bash
kast --help | grep format
```

Should show something like:
```
--format {json,html,both}  Output format (default: both)
```

If not supported, upgrade KAST to latest version.

## Troubleshooting

### Issue: Only HTML Generated

**Symptoms:** `report.html` exists but no `*_processed.json` files

**Causes:**
- KAST version doesn't support `--format both`
- JSON generation failed during scan
- Celery worker not restarted after code change

**Solution:**
1. Check KAST version: `kast --version`
2. Check logs for errors during JSON generation
3. Restart Celery worker
4. Run new test scan

### Issue: Only JSON Generated

**Symptoms:** `*_processed.json` files exist but no `report.html`

**Causes:**
- HTML generation disabled in KAST
- Report generation failed
- KAST configuration issue

**Solution:**
1. Check KAST configuration
2. Look for HTML generation errors in logs
3. Test with `kast --report-only --format both /path/to/scan/dir`

### Issue: Neither Format Generated

**Symptoms:** Scan completes but output directory empty

**Causes:**
- Scan failed but status not updated
- Output directory path incorrect
- Permission issues writing files

**Solution:**
1. Check scan status in database
2. Verify output directory path in scan record
3. Check file system permissions
4. Review full Celery logs for errors

### Issue: Regenerate Report Doesn't Update Files

**Symptoms:** Click "Regenerate Report" but files unchanged

**Causes:**
- Celery worker not restarted
- Regeneration task failed silently
- JSON files missing for regeneration

**Solution:**
1. Restart Celery worker
2. Check Celery logs during regeneration
3. Verify JSON files exist in output directory
4. Try manual regeneration: `kast --report-only --format both /path/to/scan`

## Summary of Changes

### Files Modified
- ✅ `app/tasks.py` - Added `--format both` to execute_scan_task() (line 51)
- ✅ `app/tasks.py` - Added `--format both` to regenerate_report_task() (line 237)
- ✅ `app/utils.py` - Already had `--format both` in execute_kast_scan() (line 85)

### Files Created
- ✅ `verify_format_both.py` - Verification script
- ✅ `docs/FORMAT_BOTH_FIX.md` - This documentation

### Action Items
1. ✅ Update all KAST command constructions
2. ✅ Create verification script
3. ✅ Document changes
4. ⏳ **Restart Celery worker** (user action required)
5. ⏳ **Test with new scan** (user action required)
6. ⏳ **Test report regeneration** (user action required)

## Next Steps

1. **Restart Celery Worker:**
   ```bash
   sudo systemctl restart kast-celery
   # or
   pkill -f celery && celery -A celery_worker.celery worker --loglevel=info
   ```

2. **Run Verification:**
   ```bash
   python verify_format_both.py
   ```

3. **Test New Scan:**
   - Create scan via web interface
   - Monitor logs for `--format both`
   - Verify both HTML and JSON in output directory

4. **Test Regeneration:**
   - Go to completed scan
   - Click "Regenerate Report"
   - Verify both formats updated

## Impact

### Before Fix
- Inconsistent output formats
- Either HTML or JSON missing
- Manual workarounds needed
- Plugin results not properly displayed

### After Fix
- ✅ Consistent dual-format output
- ✅ HTML reports for human review
- ✅ JSON data for web interface and database
- ✅ Report regeneration preserves both formats
- ✅ Complete plugin results display

## Related Documentation

- `docs/ASYNC_SETUP.md` - Celery configuration
- `docs/REGENERATE_REPORT_FEATURE.md` - Report regeneration feature
- `README.md` - General setup and usage

---

**Last Updated:** 2025-11-20  
**Issue Fixed:** Missing --format both argument  
**Status:** Complete - Awaiting testing
