# ZAP Plugin Debug Fix - January 8, 2026

## Problem Summary

The ZAP plugin was failing immediately when launched from kast-web due to a **hardcoded remote mode override** in the scan execution logic. This caused the following issues:

1. **User's configuration ignored**: When users selected local mode with default quick passive scan, the system forced remote mode instead
2. **Automation plan not loaded**: The ZAP automation plan file was created but never used because the file upload to remote ZAP failed
3. **Silent failure**: Scans completed with "success" status but did nothing useful

## Root Cause Analysis

### Issue Location
File: `app/tasks.py`, lines 227-233 (now removed)

### The Hardcoded Override
```python
# OVERRIDE: Always use remote mode to connect to pre-started container
# This works around KAST's local provider limitations with Docker port mapping
cmd.extend(['--set', 'zap.execution_mode=remote'])
cmd.extend(['--set', 'zap.remote.api_url=http://localhost:8080'])
cmd.extend(['--set', 'zap.remote.api_key=kast-local'])
cmd.extend(['--set', 'zap.remote.verify_ssl=false'])
```

This override **completely ignored** the user's ZapConfiguration selection and always forced remote mode, attempting to connect to localhost:8080.

### Failure Cascade

From the execution log (`/home/kali/kast_results/waas.cudalabx.net-20260108-055233/kast_execution.log`):

1. **Plan file created**: `/tmp/zap_automation_w711z76y.yaml` - ✓ Success
2. **Tried to upload to remote ZAP**: Failed with "Bad Other" error from ZAP API
3. **Upload response missing 'Uploaded' path**: File upload failed
4. **Scan ended immediately**: Without automation plan loaded, ZAP had nothing to scan

```
[2026-01-08 05:52:35.25] [DEBUG] [zap]: Upload response missing 'Uploaded' path
[2026-01-08 05:52:35.25] [DEBUG] [zap]: ERROR: Failed to upload/execute automation plan
[2026-01-08 05:52:35.25] [DEBUG] [zap]: Remote mode: No cleanup needed
```

## Solution Implemented

### 1. Removed Hardcoded Override
**Change**: Deleted lines 227-233 that forced remote mode
**Result**: Now respects user's actual ZapConfiguration settings

### 2. Always Use a ZAP Configuration
**Change**: Added logic to auto-select default ZapConfiguration if none specified
**Implementation**:
```python
# If no config specified or config not found, auto-select default
if not zap_config_to_use:
    zap_config_to_use = ZapConfiguration.query.filter_by(
        is_default=True,
        is_active=True
    ).first()
    
    if zap_config_to_use:
        current_app.logger.info(f"Auto-selected default ZAP config: {zap_config_to_use.name}")
        scan.zap_config_id = zap_config_to_use.id
```

### 3. Copy ZAP Plan File to Output Directory
**Change**: Automation plan file now copied to scan output directory for permanent reference
**Implementation**:
```python
# Copy plan file to output directory for permanent reference
output_plan_path = output_dir / 'zap_automation_plan.yaml'
shutil.copy(zap_plan_file, output_plan_path)
current_app.logger.info(f"Copied ZAP plan to output directory: {output_plan_path}")
```

### 4. Enhanced Logging
**Change**: Added comprehensive logging for ZAP configuration tracking
**Logs**:
- Selected ZapConfiguration (name, ID, mode)
- ZAP automation plan (name, ID, or "default")
- All `--set` parameters being passed to KAST
- Whether default config was auto-selected
- Final KAST command before execution

**Example Enhanced Logging Output**:
```
================================================================================
ZAP PLUGIN CONFIGURATION
================================================================================
Custom ZAP plan: Quick Passive Scan (ID: 1)
Created temp ZAP plan file: /tmp/zap_automation_abc123.yaml
Copied ZAP plan to output directory: /path/to/scan/zap_automation_plan.yaml
Using specified ZAP config: Local Docker ZAP (ID: 1)
ZAP Execution Mode: local
ZAP Plan: Quick Passive Scan
ZAP Plan File: /tmp/zap_automation_abc123.yaml
================================================================================
APPLYING ZAP CONFIGURATION TO KAST COMMAND
================================================================================
--set zap.zap_config.automation_plan=/tmp/zap_automation_abc123.yaml
--set zap.execution_mode=local
--set zap.local.docker_image=ghcr.io/zaproxy/zaproxy:stable
--set zap.local.api_port=8080
--set zap.local.cleanup_on_completion=true
Applied ZAP local Docker configuration
================================================================================
```

## Files Modified

### app/tasks.py
**Lines Changed**: ~140-270
**Changes**:
1. Removed hardcoded remote mode override (lines 227-233)
2. Added auto-selection of default ZapConfiguration
3. Added plan file copy to output directory
4. Enhanced logging throughout ZAP configuration section
5. Properly applied local vs remote configuration based on user selection

## Testing Required

After these changes, the following should be tested:

### 1. Local Mode with Default Plan
- Select ZAP plugin
- Choose local mode configuration
- Use default ZAP automation plan
- **Expected**: Docker container starts, plan loads, scan executes

### 2. Local Mode with Custom Plan
- Select ZAP plugin
- Choose local mode configuration
- Select custom ZAP automation plan
- **Expected**: Custom plan is used and copied to output directory

### 3. Remote Mode with Pre-started ZAP
- Pre-start ZAP container on localhost:8080
- Select ZAP plugin
- Choose remote mode configuration
- **Expected**: Connects to existing ZAP, plan uploads and executes

### 4. Auto-selection of Default Config
- Select ZAP plugin without specifying config
- **Expected**: Default active ZapConfiguration is auto-selected and logged

### 5. Plan File Persistence
- Run any ZAP scan
- **Expected**: `zap_automation_plan.yaml` appears in scan output directory

## Verification Steps

1. **Check Celery logs**: Enhanced logging should show exact configuration being used
2. **Check output directory**: `zap_automation_plan.yaml` should exist
3. **Check scan execution log**: Should show correct mode (local vs remote)
4. **Check ZAP results**: Should contain actual findings, not immediate exit

## Benefits of This Fix

1. **User configuration respected**: Local/remote mode selection now works as intended
2. **Transparency**: Enhanced logging makes it clear what configuration is being used
3. **Debugging**: Plan file in output directory allows post-mortem analysis
4. **Automatic fallback**: Auto-selects default configuration if none specified
5. **No breaking changes**: Existing ZAP configurations continue to work

## Related Documentation

- `docs/ZAP_INTEGRATION_PHASE1.md` - Original ZAP integration design
- `docs/ZAP_INTEGRATION_PHASE2.md` - Configuration and plan management
- `docs/ZAP_MIGRATION_FIX.md` - Database schema fixes
- `genai-instructions.md` - Overall project guidelines

## Next Steps

1. **Test local mode**: Verify Docker-based ZAP execution works correctly
2. **Test remote mode**: Verify connection to pre-started ZAP instance
3. **Monitor logs**: Check Celery worker logs for enhanced ZAP configuration output
4. **Review plan files**: Check output directories for saved automation plans
5. **Document findings**: Update this file with test results

## Rollback Instructions

If issues arise, the changes can be rolled back by:

1. Restoring `app/tasks.py` from git: `git checkout HEAD -- app/tasks.py`
2. Restarting Celery worker: `sudo systemctl restart kast-celery`

However, note that the old code had the hardcoded override bug, so rollback is not recommended unless a new critical issue is discovered.
