# ZAP Remote Mode - Syntax Verification & Enhanced Logging

## Overview

This document describes the updates made to ensure kast-web generates the exact CLI syntax that was proven to work for ZAP remote mode execution.

## Working CLI Syntax (Verified)

The following command was confirmed to work successfully:

```bash
kast -t waas.cudalabx.net -v --run-only zap -m active \
  --set zap.execution_mode=remote \
  --set zap.remote.api_url=http://localhost:8080 \
  --set zap.remote.api_key=kast01 \
  --set zap.zap_config.automation_plan=/home/kali/kast_results/waas.cudalabx.net-20260108-171000/zap_automation_plan.yaml
```

**Results:**
- ✅ Plan uploaded successfully
- ✅ Spider executed (100% complete)
- ✅ 1356 alerts found
- ✅ JSON report downloaded
- ⏱️ Completed in ~68 seconds

## Enhanced Logging Implementation

### Changes Made to app/tasks.py

1. **Numbered Logging** - Each `--set` argument is now logged with a number for easy verification:
   ```
   [1] --set zap.execution_mode=remote
   [2] --set zap.remote.api_url=http://localhost:8080
   [3] --set zap.remote.api_key=***hidden***
   [4] --set zap.zap_config.automation_plan=/tmp/...
   ```

2. **Argument Order** - Matches proven working syntax:
   - execution_mode (first)
   - mode-specific settings (remote/local)
   - automation_plan (last)

3. **Summary Section** - After all arguments added, logs complete summary:
   ```
   ================================================================================
   SUMMARY: Added 4 ZAP --set argument(s):
     [1] --set zap.execution_mode=remote
     [2] --set zap.remote.api_url=http://localhost:8080
     [3] --set zap.remote.api_key=***hidden***
     [4] --set zap.zap_config.automation_plan=/tmp/...
   ================================================================================
   ```

4. **Argument Tracking** - Internal list `zap_set_args` tracks all arguments for verification

## How to Verify

### Step 1: Check Celery Worker Logs

After starting a ZAP scan, check the Celery worker logs:

```bash
# If running in foreground:
tail -f /var/log/kast-web/celery-worker.log

# Or check journalctl if running as service:
sudo journalctl -u kast-celery -f
```

### Step 2: Look for ZAP Configuration Section

Find this section in the logs:

```
================================================================================
APPLYING ZAP CONFIGURATION TO KAST COMMAND
================================================================================
[1] --set zap.execution_mode=remote
[2] --set zap.remote.api_url=http://localhost:8080
[3] --set zap.remote.api_key=***hidden***
[4] --set zap.zap_config.automation_plan=/tmp/zap_automation_xyz789.yaml
================================================================================
SUMMARY: Added 4 ZAP --set argument(s):
  [1] --set zap.execution_mode=remote
  [2] --set zap.remote.api_url=http://localhost:8080
  [3] --set zap.remote.api_key=***hidden***
  [4] --set zap.zap_config.automation_plan=/tmp/zap_automation_xyz789.yaml
================================================================================
```

### Step 3: Verify Execution

After the summary, you should see:

```
Full command to execute: /usr/local/bin/kast -t example.com ...
Stored actual CLI command in database
```

### Step 4: Check Scan Details Page

After the scan completes:
1. Go to the scan details page
2. Look at the "CLI Command" section
3. You should now see the **actual command executed** with all `--set` arguments

## Configuration Fields Mapping

### Remote Mode
| GUI Field | CLI Argument | Example |
|-----------|--------------|---------|
| Execution Mode | `zap.execution_mode` | `remote` |
| ZAP URL | `zap.remote.api_url` | `http://localhost:8080` |
| API Key | `zap.remote.api_key` | `kast01` |
| Timeout | `zap.remote.timeout_seconds` | `300` |
| Verify SSL | `zap.remote.verify_ssl` | `true`/`false` |

### Local Mode
| GUI Field | CLI Argument | Example |
|-----------|--------------|---------|
| Execution Mode | `zap.execution_mode` | `local` |
| Docker Image | `zap.local.docker_image` | `ghcr.io/zaproxy/zaproxy:stable` |
| API Port | `zap.local.api_port` | `8090` |
| Auto Remove | `zap.local.cleanup_on_completion` | `true`/`false` |

### Automation Plan
| GUI Field | CLI Argument | Example |
|-----------|--------------|---------|
| Custom Plan | `zap.zap_config.automation_plan` | `/tmp/zap_automation_abc123.yaml` |

## Troubleshooting

### Issue: Wrong execution mode used

**Symptom:** Logs show `local` but you selected `remote`

**Check:**
1. Verify ZAP configuration is marked as default in admin panel
2. Check if scan has `zap_config_id` set
3. Look for "Auto-selected default ZAP config" message in logs

### Issue: API key showing as ${ZAP_API_KEY}

**Symptom:** API key appears as literal `${ZAP_API_KEY}` in KAST debug output

**Solution:**
- This means the value was not decrypted properly
- Check that the ZAP configuration's `remote_config_encrypted` field contains encrypted JSON
- Verify encryption key in environment

### Issue: Automation plan not being used

**Symptom:** KAST uses default plan instead of custom plan

**Check:**
1. Look for `[4] --set zap.zap_config.automation_plan=/tmp/...` in logs
2. Verify temp file was created (should see "Created temp ZAP plan file" message)
3. Check scan has `zap_plan_id` set

### Issue: --set arguments not appearing in logs

**Symptom:** No ZAP configuration section in Celery logs

**Possible Causes:**
1. ZAP not selected in plugins list
2. No ZAP configuration found (neither specified nor default)
3. Celery worker not restarted after code changes

**Solution:**
```bash
# Restart Celery worker
sudo systemctl restart kast-celery

# Or if running in foreground:
# Ctrl+C then restart: celery -A celery_worker worker --loglevel=info
```

## Security Notes

- API keys are always hidden in logs (shown as `***hidden***`)
- The actual value is still passed to KAST CLI
- Full command with API key is stored in database in `actual_cli_command` field
- Database admins can see the full command including API keys

## Testing Checklist

After making these changes, test the following scenarios:

- [ ] Remote mode with custom plan
- [ ] Remote mode with default plan
- [ ] Local mode with Docker
- [ ] Verify all 4 `--set` arguments appear in logs for remote mode
- [ ] Verify automation plan temp file is created
- [ ] Verify actual command stored in database
- [ ] Verify scan details page shows actual command
- [ ] Verify API key is hidden in logs but present in command
- [ ] Check scan completes successfully
- [ ] Verify ZAP report is downloaded

## Related Documentation

- `docs/CLI_COMMAND_LOGGING_FEATURE.md` - Complete command logging feature
- `docs/ZAP_INTEGRATION_PHASE1.md` - ZAP integration basics
- `docs/ZAP_INTEGRATION_PHASE2.md` - Admin configuration
- `docs/ZAP_PLUGIN_DEBUG_FIX.md` - Original debugging work

## Summary

With these changes, you now have:
1. ✅ Full visibility into all `--set` arguments being generated
2. ✅ Numbered list for easy verification
3. ✅ Summary section showing all arguments together
4. ✅ Verification that syntax matches working command
5. ✅ Actual command stored in database for future reference
6. ✅ Better debugging capabilities for ZAP issues
