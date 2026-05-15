# Status Endpoint Debugging Guide

## Overview

Enhanced debugging has been added to the `/api/scans/<id>/status` endpoint to help troubleshoot plugin status issues, particularly when plugins don't show "In Progress" status correctly.

## What Was Added

### 1. Comprehensive Logging in `app/routes/api.py`

The status endpoint now logs detailed information every time it's called (every 3 seconds during active scans):

#### Scan Information
- **Scan ID** and basic details (status, target)
- **Output directory** path
- Whether the output directory exists

#### File Discovery
- **All files** in the output directory (complete listing)
- File-by-file examination showing which files match plugin patterns
- Clear indication of which files are skipped and why

#### Plugin Detection
- Whether specific plugins were configured or auto-discovered
- **Complete list of plugins** being tracked
- For auto-discovery: shows the logic for each JSON file

#### Plugin Status Determination
For each plugin, the logs show:
- Processed file check: `{plugin}_processed.json` - exists or not
- Raw file check: `{plugin}.json` - exists or not  
- **Status determination logic**: 
  - `COMPLETED` - processed file exists
  - `IN_PROGRESS` - raw file exists, no processed file
  - `PENDING` - no files found
- Database lookup results (findings count, execution time)

#### Summary Information
- Total plugin count
- Breakdown by status (e.g., 3 in_progress, 2 completed, 5 pending)

## How to Use

### Starting the Server with Debug Logging

```bash
python run.py
```

The server will start with DEBUG level logging enabled. You'll see a banner:
```
============================================================
KAST Web - Development Server
Logging configured at DEBUG level
Status endpoint debugging is ENABLED
============================================================
```

### Reading the Logs

When a client polls `/api/scans/<id>/status`, you'll see output like this:

```
2025-11-14 06:20:15 [INFO] app.routes.api: ========== STATUS CHECK: Scan ID 123 ==========
2025-11-14 06:20:15 [INFO] app.routes.api: Scan status: running, target: example.com
2025-11-14 06:20:15 [INFO] app.routes.api: Output directory: /home/user/kast_results/example.com-20251114-062010
2025-11-14 06:20:15 [DEBUG] app.routes.api: Checking output directory: /home/user/kast_results/example.com-20251114-062010
2025-11-14 06:20:15 [DEBUG] app.routes.api: Output directory EXISTS
2025-11-14 06:20:15 [DEBUG] app.routes.api: Files in output directory (8): ['amass.json', 'dnsx.json', 'dnsx_processed.json', 'httpx.json', 'kast_report.json', 'subfinder.json', 'subfinder_processed.json', 'waybackurls.json']
2025-11-14 06:20:15 [INFO] app.routes.api: Using SPECIFIC plugins from scan config: ['subfinder', 'amass', 'dnsx', 'httpx', 'waybackurls']
2025-11-14 06:20:15 [INFO] app.routes.api: Checking status for 5 plugins...
2025-11-14 06:20:15 [DEBUG] app.routes.api: --- Plugin: subfinder ---
2025-11-14 06:20:15 [DEBUG] app.routes.api:   Checking processed file: subfinder_processed.json -> exists=True
2025-11-14 06:20:15 [DEBUG] app.routes.api:   Checking raw file: subfinder.json -> exists=True
2025-11-14 06:20:15 [DEBUG] app.routes.api:   Status: COMPLETED (processed file exists)
2025-11-14 06:20:15 [DEBUG] app.routes.api:   Database data: 42 findings
2025-11-14 06:20:15 [DEBUG] app.routes.api:   Final status: completed
2025-11-14 06:20:15 [DEBUG] app.routes.api: --- Plugin: amass ---
2025-11-14 06:20:15 [DEBUG] app.routes.api:   Checking processed file: amass_processed.json -> exists=False
2025-11-14 06:20:15 [DEBUG] app.routes.api:   Checking raw file: amass.json -> exists=True
2025-11-14 06:20:15 [DEBUG] app.routes.api:   Status: IN_PROGRESS (raw file exists, no processed file)
2025-11-14 06:20:15 [DEBUG] app.routes.api:   Final status: in_progress
...
2025-11-14 06:20:15 [INFO] app.routes.api: Response summary: 5 total plugins - {'completed': 2, 'in_progress': 2, 'pending': 1}
2025-11-14 06:20:15 [INFO] app.routes.api: ========== END STATUS CHECK ==========
```

## Troubleshooting Plugin Status Issues

### Problem: Plugins Stay "Pending"

**Check the logs for:**
1. Is the output directory created and accessible?
   - Look for: `Output directory EXISTS` or `Output directory DOES NOT EXIST yet`
2. Are plugin files being created?
   - Look at the file listing: `Files in output directory (X): [...]`
3. Are the filenames correct?
   - Raw files should be: `{plugin}.json`
   - Processed files should be: `{plugin}_processed.json`

### Problem: Plugins Don't Show "In Progress"

**Check the logs for:**
1. Is the raw file created?
   - Look for: `Checking raw file: {plugin}.json -> exists=True`
2. Is the processed file already there?
   - If processed file exists, status will be "completed" not "in_progress"
   - Look for: `Checking processed file: {plugin}_processed.json -> exists=True`

**Expected behavior for "In Progress":**
- Raw file (`{plugin}.json`) EXISTS
- Processed file (`{plugin}_processed.json`) DOES NOT EXIST

### Problem: Plugins Skip Straight to "Completed"

This happens when the processed file is created very quickly. Check the logs:
- You may see the plugin go from pending → in_progress → completed in consecutive status checks
- Or KAST might generate the processed file so fast it skips the in_progress phase entirely

### Problem: Wrong Plugins Being Tracked

**Check the logs for:**
1. If specific plugins configured:
   - Look for: `Using SPECIFIC plugins from scan config: [...]`
2. If auto-discovering:
   - Look for: `No specific plugins configured - discovering from output directory`
   - Check which files are being examined and why some are skipped

## Log Levels

The debugging uses these log levels:

- **INFO**: High-level flow (scan start, plugin list, summary)
- **DEBUG**: Detailed information (file checks, status logic)
- **WARNING**: Issues that don't prevent operation (missing output dir)
- **ERROR**: Problems that affect functionality

## Production Deployment

For production with Gunicorn, you'll need to configure logging differently. Add to your Gunicorn config:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

Or use a logging configuration file and pass it to Gunicorn with `--log-config`.

## Disabling Debug Logging

To reduce verbosity in production:

1. In `run.py` or your app factory, change:
   ```python
   logging.basicConfig(level=logging.INFO)  # Instead of DEBUG
   ```

2. Or set environment variable:
   ```bash
   export FLASK_ENV=production
   ```

The detailed logging will still be available but won't output DEBUG level messages.
