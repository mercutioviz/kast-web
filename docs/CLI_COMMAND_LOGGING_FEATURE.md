# CLI Command Logging Feature

## Overview

This feature adds proper logging and display of the actual CLI command executed for each scan, including all dynamically generated `--set` arguments for ZAP plugin configuration. It also preserves important configuration files in the scan output directory.

## Problem Statement

Previously, the CLI command displayed on the scan details page was generated using the `Scan.get_cli_command()` method, which:
- Only showed basic scan parameters
- **Did NOT include ZAP-specific `--set` arguments** that were dynamically added during scan execution
- Made debugging ZAP plugin issues difficult because the displayed command didn't match what was actually executed

## Solution

### 1. Database Schema Change

Added new column to `Scan` model:
- `actual_cli_command` (Text) - Stores the complete command that was executed, including all `--set` arguments

### 2. Command Logging in app/tasks.py

Modified `execute_scan_task()` to:
- Store the actual command string after building it completely (line ~311)
- This happens BEFORE execution, so we capture exactly what will be run

```python
# Store the actual command that was executed for display/debugging
scan.actual_cli_command = ' '.join(cmd)
db.session.commit()
```

### 3. Configuration File Preservation

Enhanced temp file handling to preserve copies in output directory:

**For KAST Config Files:**
- When a config profile is used, the temp config file is now copied to `{output_dir}/kast_config.yaml`
- This allows users to see exactly what configuration was used

**For ZAP Plan Files:**
- When a custom ZAP plan is used, it's already being copied to `{output_dir}/zap_automation_plan.yaml`
- This was working correctly already

### 4. Display Logic in app/routes/scans.py

Updated the `detail()` route to:
- Check if `scan.actual_cli_command` exists (populated for new scans)
- If yes, use the actual command (includes all --set args)
- If no, fall back to `scan.get_cli_command()` for backward compatibility with old scans

```python
# Use actual command if available (includes all --set args), otherwise generate it
if scan.actual_cli_command:
    cli_command = scan.actual_cli_command
else:
    cli_command = scan.get_cli_command(current_app.config['KAST_CLI_PATH'])
```

## Migration

Run the migration script:
```bash
python3 utils/migrate_cli_command_logging.py
```

This adds the `actual_cli_command` column to existing installations.

## Benefits

### For Debugging
- Users can see the **exact command** that was executed
- All ZAP `--set` arguments are visible (execution mode, API URLs, ports, etc.)
- Easier to reproduce issues by copying the exact command

### For Transparency
- Complete visibility into how kast-web configured the KAST CLI
- Users can understand what parameters were passed to ZAP plugin

### For Reproducibility
- The output directory now contains:
  - `kast_execution.log` - Full execution log
  - `kast_config.yaml` - The config file used (if any)
  - `zap_automation_plan.yaml` - The ZAP plan used (if custom plan)
  - Users can re-run with identical settings

## Example

### Before (Incomplete Command)
```bash
/usr/local/bin/kast \
  -t example.com \
  -m passive \
  --format both \
  --run-only zap \
  -o /home/kali/kast_results/example.com-20260108-120000
```

### After (Complete Command with ZAP Config)
```bash
/usr/local/bin/kast \
  -t example.com \
  -m passive \
  --format both \
  --config /tmp/kast_config_abc123.yaml \
  --set zap.zap_config.automation_plan=/tmp/zap_automation_xyz789.yaml \
  --set zap.execution_mode=local \
  --set zap.local.docker_image=ghcr.io/zaproxy/zaproxy:stable \
  --set zap.local.api_port=8090 \
  --set zap.local.cleanup_on_completion=true \
  --run-only zap \
  -o /home/kali/kast_results/example.com-20260108-120000
```

## Files Modified

1. **utils/migrate_cli_command_logging.py** (new)
   - Migration script to add `actual_cli_command` column

2. **app/models.py**
   - Added `actual_cli_command` column to Scan model

3. **app/tasks.py**
   - Store actual CLI command after building it
   - Copy config file to output directory for preservation

4. **app/routes/scans.py**
   - Use actual command if available, otherwise fall back to generated command

## Backward Compatibility

- Old scans without `actual_cli_command` will continue to work
- The display logic falls back to `get_cli_command()` for these scans
- No data loss or breaking changes

## Testing

To test this feature:

1. Run migration: `python3 utils/migrate_cli_command_logging.py`
2. Create a new scan with ZAP plugin selected
3. Configure ZAP to use local mode or remote mode
4. After scan completes, view the scan details page
5. Check that the CLI command shows all ZAP `--set` arguments
6. Check output directory for:
   - `kast_config.yaml` (if config profile was used)
   - `zap_automation_plan.yaml` (if custom plan was used)

## Related Issues

This feature helps debug issues like:
- ZAP plugin ending immediately (wrong execution mode)
- ZAP automation plan not being used
- API key or URL configuration problems
- Any mismatch between GUI settings and what KAST actually executed
