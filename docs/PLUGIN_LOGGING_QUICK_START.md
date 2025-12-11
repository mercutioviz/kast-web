# Plugin Logging - Quick Start Guide

## What This Feature Does

The Plugin Logging feature helps you understand **why plugins fail** during KAST scans by:
- Showing error messages directly on the scan detail page
- Providing complete execution logs for detailed troubleshooting
- Making it easy to download and share logs for support

## Quick Setup (For Administrators)

### 1. Run the Migration
```bash
cd /opt/kast-web
source venv/bin/activate
python3 utils/migrate_plugin_logging.py
```

### 2. Restart Services
```bash
# Restart Flask app
sudo systemctl restart kast-web

# Restart Celery worker
sudo systemctl restart kast-celery
```

That's it! The feature is now active for all new scans.

## Using the Feature

### Viewing Plugin Errors

1. Navigate to any scan from **Scan History**
2. Scroll to the **Plugin Results** section
3. Look for plugins with a red "Failed" badge
4. Error messages appear directly below each failed plugin:
   ```
   Plugin: subdomain_enum
   Status: Failed
   ⚠️ Error: Connection timeout after 30 seconds
   ```

### Viewing Full Execution Logs

1. On the scan detail page, look for the **Actions** sidebar
2. Click **"View Execution Log"**
3. The log opens in a new tab showing:
   - Command executed
   - All KAST output
   - Error messages
   - Timing information

### Downloading Logs

1. In the execution log viewer, click **"Download Log"**
2. The log is saved as: `kast_execution_log_[target]_[scan_id].log`
3. Share this file when requesting support

## Common Scenarios

### Scenario 1: Plugin Times Out
**What you see:**
```
Plugin: port_scanner
Status: Failed
Error: Execution timeout after 300 seconds
```

**What to do:**
- Check the execution log for partial results
- Consider running the scan with fewer plugins
- Check if the target is responsive

### Scenario 2: Missing Tool
**What you see:**
```
Plugin: ssl_check
Status: Failed
Error: Required command 'openssl' not found
```

**What to do:**
- Install the missing tool: `sudo apt install openssl`
- Re-run the scan
- Contact admin if you can't install tools

### Scenario 3: API Rate Limit
**What you see:**
```
Plugin: shodan_lookup
Status: Failed
Error: API rate limit exceeded. Retry in 3600s
```

**What to do:**
- Wait for the specified time
- Re-run the scan later
- Consider using fewer plugins per scan

## Tips & Best Practices

### For Analysts
- ✅ Always check plugin errors before reporting issues
- ✅ Download logs when requesting support
- ✅ Review execution logs to understand scan behavior
- ✅ Compare logs between successful and failed scans

### For Administrators
- ✅ Monitor disk space (logs are stored with scan results)
- ✅ Set up log rotation for old scans
- ✅ Review execution logs to identify systemic issues
- ✅ Use logs to optimize plugin configurations

## Troubleshooting

### "No execution log available"
- The scan hasn't started yet (still pending)
- The scan is very old (before this feature was added)
- The output directory was deleted

### Error message says "(no details available)"
- The plugin didn't write error info to its JSON output
- Check the full execution log for STDERR messages
- The plugin may have crashed before writing output

### Log viewer is slow
- Log file is very large (>10MB)
- Download the log instead of viewing in browser
- Large logs indicate verbose output - consider disabling verbose mode

## FAQ

**Q: Do old scans have execution logs?**  
A: No, only scans created after running the migration have execution logs.

**Q: How much disk space do logs use?**  
A: Typically 10-100KB per scan. Verbose scans may generate larger logs.

**Q: Can I disable this feature?**  
A: The logs are automatically created and don't impact performance. You can ignore them if not needed.

**Q: What if I don't see error messages for a failed plugin?**  
A: Check the full execution log - the error may be in STDERR rather than the plugin's JSON output.

**Q: Can I share execution logs?**  
A: Yes! Download the log and share it. It contains no sensitive credentials.

## Next Steps

- See [PLUGIN_LOGGING_FEATURE.md](PLUGIN_LOGGING_FEATURE.md) for complete technical documentation
- Check [OUTPUT_FILES_FEATURE.md](OUTPUT_FILES_FEATURE.md) for viewing all scan output files
- Review [PLUGIN_RESULTS_FIX.md](PLUGIN_RESULTS_FIX.md) for plugin status details

## Need Help?

1. Review the execution log for your scan
2. Check this guide for common scenarios
3. Read the full documentation in PLUGIN_LOGGING_FEATURE.md
4. Use `/reportbug` in the app to report issues
