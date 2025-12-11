# Plugin Logging Feature

## Overview

The Plugin Logging feature enhances visibility into KAST scan execution by capturing and displaying detailed error information for failed plugins. This feature provides comprehensive logging of scan execution, making it easier to troubleshoot and understand why specific plugins may fail.

## Features

### 1. Full Execution Logs
- **Complete Command Output**: Every scan now creates a detailed execution log file (`kast_execution.log`) that captures:
  - The exact KAST command executed
  - All STDOUT output from KAST
  - All STDERR output including error messages
  - Return code and timing information
  - Scan metadata (ID, target, mode, start/completion times)

### 2. Per-Plugin Error Messages
- **Automatic Error Extraction**: When a plugin fails, the system automatically extracts error messages from the plugin's JSON output
- **Multiple Error Sources**: The system checks multiple locations in plugin output for error information:
  - Top-level `error` field
  - `message` field
  - `error_message` field
  - Nested error info within `findings` dict
  - `details` and `reason` fields

### 3. Enhanced UI Display
- **Inline Error Display**: Failed plugins now show their error messages directly in the scan detail page
- **Color-Coded Errors**: Failed plugins are highlighted in red with clear error indicators
- **Log Viewer**: New dedicated page for viewing full execution logs with:
  - Syntax-highlighted, monospaced display
  - Dark theme optimized for log reading
  - Scrollable view for long logs
  - Download capability

### 4. Easy Access
- **View Execution Log Button**: Direct link from scan detail page to view the full execution log
- **Download Log**: One-click download of the complete log file for offline analysis
- **Persistent Storage**: Logs are stored with scan results and preserved for historical analysis

## Database Changes

### New Field: `execution_log_path`
Added to the `Scan` model to store the path to the execution log file.

```python
execution_log_path = db.Column(db.String(500))  # Path to full KAST execution log
```

### Enhanced ScanResult Model
The `error_message` field in `ScanResult` is now automatically populated with extracted error information from failed plugins.

## Usage

### For End Users

#### Viewing Plugin Errors
1. Navigate to a completed scan's detail page
2. Scroll to the "Plugin Results" section
3. Failed plugins will show a red "Failed" badge
4. Error messages appear directly below each failed plugin in red highlight

#### Accessing Execution Logs
1. On the scan detail page, click **"View Execution Log"** in the Actions sidebar
2. The log viewer will open in a new tab showing the complete execution output
3. Use the **"Download Log"** button to save the log file locally

#### Understanding Log Contents
The execution log contains several sections:
- **Header**: Scan metadata and command information
- **STDOUT Section**: Normal output from KAST
- **STDERR Section**: Error messages and warnings
- **Footer**: Return code and completion timestamp

### For Administrators

#### Migration Required
To enable this feature on an existing installation:

```bash
# Run the migration script
python3 utils/migrate_plugin_logging.py
```

This adds the `execution_log_path` column to the scans table.

#### Disk Space Considerations
- Each scan now generates an additional log file
- Log files are typically small (a few KB to a few MB)
- Logs are stored in the scan's output directory
- Consider your retention policy for old scans

## Technical Implementation

### Log File Creation
When a scan starts, the system:
1. Creates the scan output directory
2. Creates `kast_execution.log` in that directory
3. Stores the log path in the database
4. Writes scan metadata and command information

### Real-Time Logging
During scan execution:
1. KAST command is executed via `subprocess.Popen`
2. STDOUT and STDERR are captured
3. After completion, all output is appended to the log file
4. Return code and timing information are recorded

### Error Extraction
After scan completion:
1. Parse all `*_processed.json` files
2. For each failed plugin (disposition == 'fail'):
   - Check multiple JSON fields for error messages
   - Extract and truncate if necessary (1000 char limit)
   - Store in `ScanResult.error_message`

### UI Routes
Two new routes were added:
- `/scans/<scan_id>/execution-log` - View log in browser
- `/scans/<scan_id>/execution-log/download` - Download log file

## Benefits

### For Security Analysts
- **Quick Troubleshooting**: Instantly see why a plugin failed without digging through files
- **Complete Context**: Full execution log provides all details needed for analysis
- **Historical Analysis**: Logs are preserved with scan results for future reference

### For System Administrators
- **Easier Debugging**: Comprehensive logs make it easier to identify configuration issues
- **Better Support**: Can provide detailed logs when requesting help
- **Audit Trail**: Complete record of what was executed and when

### For Development Teams
- **Plugin Development**: Clearer error messages help when developing new plugins
- **Integration Testing**: Logs make it easier to verify scan behavior
- **Issue Reporting**: Can attach logs when reporting bugs

## Example Use Cases

### Case 1: Plugin Timeout
```
Plugin: subdomain_enum
Status: Failed
Error: Connection timeout after 30 seconds
```
The execution log will show the exact timeout message and any partial results.

### Case 2: Missing Dependency
```
Plugin: ssl_analyzer
Status: Failed  
Error: Required tool 'openssl' not found in PATH
```
Error message clearly indicates the missing dependency.

### Case 3: API Rate Limit
```
Plugin: shodan_lookup
Status: Failed
Error: API rate limit exceeded. Try again in 3600 seconds.
```
Error explains exactly what went wrong and when to retry.

## Troubleshooting

### Log File Not Found
- Ensure the scan has started (status is not 'pending')
- Check that the output directory exists
- Verify file system permissions

### Empty or Incomplete Logs
- Log is written in stages; running scans may have partial logs
- If scan failed immediately, log may only contain header
- Check system logs for write permission errors

### Error Messages Not Showing
- Error extraction only works for failed plugins
- Plugin must write error info to JSON output
- Check the raw plugin JSON file for error data

### Performance Considerations
- Viewing large logs (>10MB) may be slow in browser
- Consider downloading large logs instead of viewing
- Log files do not impact scan execution performance

## Future Enhancements

Potential improvements for future versions:
- Real-time log streaming during scan execution
- Log search and filtering capabilities
- Aggregated error reports across multiple scans
- Plugin-specific error templates
- Integration with system monitoring/alerting

## Related Documentation

- [OUTPUT_FILES_FEATURE.md](OUTPUT_FILES_FEATURE.md) - Viewing scan output files
- [ASYNC_SETUP.md](ASYNC_SETUP.md) - Celery task execution
- [PLUGIN_RESULTS_FIX.md](PLUGIN_RESULTS_FIX.md) - Plugin status handling

## Version History

- **v1.0** (2025-12-11): Initial implementation
  - Added execution log file creation
  - Implemented error extraction from plugin JSON
  - Created log viewer UI
  - Added database migration

## Support

For questions or issues with the Plugin Logging feature:
1. Check the execution log for detailed error information
2. Review this documentation
3. Check system logs for any file permission issues
4. Report issues using the `/reportbug` command in the application
