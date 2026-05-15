# Per-Plugin Logging - Quick Start

## What You Get

After implementing this feature, every scan automatically creates individual log files for each plugin that runs. This makes debugging plugin failures much easier.

## How It Works

**Automatically!** No setup required beyond restarting Celery (already done).

### For Every Scan

When a scan completes, the system:
1. ✅ Reads the main execution log
2. ✅ Identifies each plugin's output
3. ✅ Creates `<plugin_name>_plugin.log` files
4. ✅ Stores them in the scan's output directory

## Quick Example

**Before:** One big log file with all plugins mixed together  
**After:** Individual files for each plugin:

```
/opt/kast-results/example.com-20251211/
  ├── kast_execution.log        ← Full log
  ├── subfinder_plugin.log      ← Just subfinder output
  ├── katana_plugin.log         ← Just katana output
  └── nuclei_plugin.log         ← Just nuclei output
```

## Viewing Plugin Logs

### Method 1: Via Web Interface
1. Go to a scan's detail page
2. Click **"View Output Files"**
3. Look for files ending in `_plugin.log`
4. Click to view the content

### Method 2: Command Line
```bash
# Navigate to scan output directory
cd /opt/kast-results/example.com-20251211/

# View a specific plugin's log
cat subfinder_plugin.log

# Or search for errors
grep -i error *_plugin.log
```

## Common Use Cases

### Scenario 1: Plugin Shows "Failed" but No Details
**Solution:** Open the plugin's log file to see the actual error

```bash
cat /opt/kast-results/scan-dir/subfinder_plugin.log
```

Look for lines with:
- `[!]` (error marker)
- `Error:`
- `Failed:`
- Exception messages

### Scenario 2: Need to Debug Multiple Failing Plugins
**Solution:** Check each plugin's log individually

```bash
# Quick check which plugins had errors
grep -l "Error\|Failed" *_plugin.log

# View each one
for log in *_plugin.log; do
  echo "=== $log ==="
  tail -20 "$log"
  echo
done
```

### Scenario 3: Compare Same Plugin Across Scans
**Solution:** Compare plugin logs from different scan runs

```bash
# Compare subfinder from two scans
diff scan1/subfinder_plugin.log scan2/subfinder_plugin.log
```

## What Each Log Contains

Each `<plugin>_plugin.log` file includes:

```
================================================================================
Plugin: subfinder
================================================================================

[+] Running plugin: subfinder
[*] Target: example.com
[*] Mode: passive
[*] Options: --verbose --timeout 300
... (plugin execution output) ...
[!] Error: Connection timeout after 30 seconds
[x] Plugin subfinder failed

================================================================================
```

## Troubleshooting

### No Plugin Logs Created

**Check 1:** Is there a `kast_execution.log`?
```bash
ls -lh /opt/kast-results/scan-dir/kast_execution.log
```

**Check 2:** Did Celery restart successfully?
```bash
ps aux | grep celery
```

**Check 3:** Any parsing errors in logs?
```bash
tail -50 /tmp/celery.log | grep -i error
```

### Plugin Log Is Empty or Incomplete

This can happen if:
- Plugin didn't produce output
- KAST's output format doesn't match expected patterns

**Solution:** Check the main execution log:
```bash
grep -A 20 "plugin.*subfinder" kast_execution.log
```

### Need to Adjust Pattern Matching

If KAST uses different output formatting, edit patterns in `app/tasks.py`:

```python
plugin_patterns = [
    r'\[[\+\-\*]\]\s*(?:Running|Executing)\s+plugin[:\s]+(\w+)',
    # Add your custom pattern here
]
```

Then restart Celery.

## Testing

Run a test scan with plugins that you know fail:

```bash
# Example: Run scan with a plugin that will timeout
# Check the output directory afterwards for plugin logs
ls -lh /opt/kast-results/*/subfinder_plugin.log
```

## Benefits Summary

✅ **Immediate debugging** - See exactly what each plugin did  
✅ **No manual work** - Logs created automatically  
✅ **Always available** - Works even when plugins crash  
✅ **Easy access** - Available via web UI and command line  
✅ **Historical analysis** - Logs persist with scan results  

## Next Steps

1. **Run a new scan** - Plugin logs will be created automatically
2. **Check "View Output Files"** - See the new `*_plugin.log` files
3. **Open a failed plugin's log** - See detailed error information
4. **Compare with main log** - Verify plugin logs match execution log

## Full Documentation

For complete technical details, see:
- [PER_PLUGIN_LOGGING.md](PER_PLUGIN_LOGGING.md) - Complete feature documentation
- [PLUGIN_LOGGING_FEATURE.md](PLUGIN_LOGGING_FEATURE.md) - Execution log feature
- [OUTPUT_FILES_FEATURE.md](OUTPUT_FILES_FEATURE.md) - Viewing output files

## Support

If you encounter issues:
1. Check the main execution log exists
2. Verify Celery is running with new code
3. Review system logs for errors
4. Use `/reportbug` in the application
