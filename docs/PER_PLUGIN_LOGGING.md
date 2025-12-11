# Per-Plugin Logging Feature

## Overview

The Per-Plugin Logging feature automatically extracts individual plugin output from the KAST execution log and creates separate log files for each plugin. This makes it much easier to debug plugin failures by providing isolated, focused logs for each plugin that ran.

## What It Does

After every KAST scan completes, the system:
1. Reads the complete execution log (`kast_execution.log`)
2. Identifies each plugin's output section using pattern matching
3. Creates a separate log file for each plugin: `<plugin_name>_plugin.log`
4. Stores these files in the scan's output directory alongside other results

## Benefits

### Quick Plugin Debugging
- See exactly what each plugin did without scrolling through the entire scan log
- Identify which plugins failed and why
- Compare successful vs failed plugin outputs easily

### Always Available
- Works even when plugins crash before writing JSON output
- Captures STDOUT and STDERR for each plugin
- Persists with scan results for historical analysis

### Seamless Integration
- Automatically appears in "View Output Files"
- No manual parsing required
- Works for both successful and failed scans

## File Structure

After a scan completes, your output directory will contain:

```
/opt/kast-results/example.com-20251211-033000/
  ├── kast_execution.log           # Complete execution log
  ├── subfinder_plugin.log         # Subfinder's output only
  ├── katana_plugin.log            # Katana's output only
  ├── nuclei_plugin.log            # Nuclei's output only
  ├── subdomain_processed.json     # Plugin results (if generated)
  ├── katana_processed.json        
  └── report.pdf
```

## Per-Plugin Log Format

Each plugin log file contains:

```
================================================================================
Plugin: subfinder
================================================================================

[+] Running plugin: subfinder
[*] Target: example.com
[*] Mode: passive
... (all plugin-specific output) ...
[!] Error: Connection timeout after 30 seconds
[x] Plugin subfinder failed

================================================================================
```

## How to Use

### Viewing Plugin Logs

1. Navigate to a scan's detail page
2. Click **"View Output Files"**
3. Look for files ending in `_plugin.log`
4. Click on any plugin log to view its contents

### Common Use Cases

#### Case 1: Plugin Failed with No JSON Output
**Problem**: Plugin shows "Failed" but no error message in the UI  
**Solution**: Open `<plugin_name>_plugin.log` to see the actual error output

#### Case 2: Plugin Timeout
**Problem**: Plugin took too long and was killed  
**Solution**: Check the plugin log to see what it was doing when it timed out

#### Case 3: Comparing Plugin Runs
**Problem**: Plugin works sometimes but fails other times  
**Solution**: Compare the plugin logs from successful and failed scans

## Pattern Matching

The system identifies plugins using these patterns in the execution log:

- `[+] Running plugin: <name>`
- `[*] Plugin: <name>`
- `Starting <name>`
- `<name> plugin`

If your KAST installation uses different output formatting, the patterns may need adjustment.

## Technical Details

### Parsing Logic

The parser (`parse_plugin_logs` in `app/tasks.py`):
1. Reads the entire execution log
2. Scans line-by-line for plugin start patterns
3. Associates subsequent lines with the current plugin
4. Continues until the next plugin starts
5. Writes accumulated lines to individual files

### Integration Points

The feature integrates at two points in the scan workflow:
- **After successful scans**: Creates plugin logs before parsing results
- **After failed scans**: Creates plugin logs even if scan failed

### Error Handling

If log parsing fails:
- The error is logged but doesn't affect scan completion
- The main execution log is still available
- Plugin results are still processed normally

## Limitations

### Pattern Dependency
- Relies on KAST's output format remaining consistent
- Custom or modified KAST versions may need pattern adjustments

### Log Size
- Each plugin log adds a small file to the output directory
- For scans with many plugins, this increases storage slightly
- Typical size: 1-50 KB per plugin log

### Parsing Accuracy
- Parser uses heuristics to identify plugin boundaries
- In rare cases, plugin sections may overlap or be incomplete
- Always check the main execution log if plugin logs seem incorrect

## Troubleshooting

### No Plugin Logs Generated

**Possible Causes:**
- Execution log doesn't exist or is empty
- Log parsing failed (check application logs)
- KAST output format doesn't match expected patterns

**Solutions:**
- Verify `kast_execution.log` exists in output directory
- Check system logs for parsing errors
- Review execution log to see actual KAST output format

### Plugin Log Is Empty

**Possible Causes:**
- Plugin didn't produce any output
- Plugin output didn't match recognition patterns

**Solutions:**
- Check the main execution log for plugin output
- Verify plugin actually ran
- Consider adjusting pattern matching if needed

### Plugin Log Contains Multiple Plugins

**Possible Causes:**
- Plugins have similar names
- Pattern matching is too broad

**Solutions:**
- Review the plugin log to identify overlap
- Check main execution log for actual plugin boundaries
- May need pattern refinement for specific plugins

## Configuration

No configuration is required - the feature works automatically for all scans.

To modify the pattern matching:
1. Edit `app/tasks.py`
2. Find the `parse_plugin_logs` function
3. Modify the `plugin_patterns` list
4. Restart the Celery worker

## Future Enhancements

Potential improvements:
- Real-time plugin log streaming during scans
- Plugin-specific log filtering and search
- Automatic error highlighting in plugin logs
- Plugin execution timeline visualization
- Per-plugin resource usage metrics

## Related Features

- **Execution Logs**: See [PLUGIN_LOGGING_FEATURE.md](PLUGIN_LOGGING_FEATURE.md)
- **Output Files**: See [OUTPUT_FILES_FEATURE.md](OUTPUT_FILES_FEATURE.md)
- **Plugin Results**: See [PLUGIN_RESULTS_FIX.md](PLUGIN_RESULTS_FIX.md)

## Support

For issues with per-plugin logging:
1. Check the main execution log exists
2. Review system logs for parsing errors
3. Compare plugin log with main execution log
4. Report issues using `/reportbug` in the application

## Version History

- **v1.0** (2025-12-11): Initial implementation
  - Automatic plugin log extraction
  - Pattern-based plugin identification
  - Integration with scan workflow
