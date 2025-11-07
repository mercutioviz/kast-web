# Plugin Status Real-Time Updates Fix

## Summary
Fixed the plugin results display on the scan details page to show real-time status updates for each plugin during scan execution.

## Problem
Previously, the plugin results section was completely blank while a scan was running. It would only populate after the entire scan completed, making it impossible to track individual plugin progress.

## Solution
Implemented a file-based status detection system that checks for plugin output files to determine the current status of each plugin:

### Status Detection Logic
For each plugin (e.g., `whatweb`):
- **Pending**: Neither `whatweb.json` nor `whatweb_processed.json` exists
- **In Progress**: `whatweb.json` exists but `whatweb_processed.json` does not
- **Completed**: `whatweb_processed.json` exists

## Changes Made

### 1. Backend API (`app/routes/api.py`)
- Updated `/api/scans/<scan_id>/status` endpoint to check file existence
- Returns plugin status based on file presence in the output directory
- Provides real-time status for all configured plugins

### 2. Backend Route (`app/routes/scans.py`)
- Updated `detail()` function to use the same file-based status detection
- Ensures plugin results are displayed immediately when the page loads
- Returns plugin status as dictionaries with status, findings_count, and executed_at

### 3. Frontend Template (`app/templates/scan_detail.html`)
- Removed conditional hiding of plugin results section
- Updated `updatePluginResults()` to handle new status values:
  - `pending` → "Pending" (gray badge)
  - `in_progress` → "In Progress" (blue badge)
  - `completed` → "Completed" (green badge)
- Updated Jinja2 template to handle dictionary-based plugin data
- Added proper status badge rendering for all states

## Benefits
1. **Immediate Visibility**: Plugin results table is visible from the moment the scan details page loads
2. **Real-Time Updates**: Plugin status updates every 3 seconds during scan execution
3. **Clear Progress Tracking**: Users can see which plugins are pending, running, or completed
4. **Better UX**: No more blank screen while waiting for scan completion

## Testing
To test the feature:
1. Start a new scan with multiple plugins
2. Navigate to the scan details page immediately
3. Observe that all plugins are listed with "Pending" status
4. Watch as plugins transition to "In Progress" and then "Completed"
5. Verify that findings count updates when plugins complete

## Technical Notes
- The status detection is based on file existence in the scan's output directory
- The polling interval is 3 seconds for active scans
- The page automatically reloads when a scan completes or fails
- Status detection works for both initial page load and polling updates
- **Important**: When no specific plugins are selected, the system discovers plugins by scanning the output directory for JSON files
- This allows the feature to work whether plugins are explicitly specified or all plugins are run by default

## Bug Fix Applied
**Issue**: The initial implementation only checked for plugins when `scan.plugins` was set. However, when no specific plugins are selected (the default behavior), KAST runs all available plugins but the `plugins` field in the database is NULL/empty.

**Solution**: Modified both the API endpoint and the detail route to:
1. First check if specific plugins were selected (`scan.plugins`)
2. If not, scan the output directory for all JSON files to discover which plugins are running
3. Extract plugin names from filenames (removing `.json` and `_processed.json` suffixes)
4. Filter out non-plugin files like `kast_report.json`

This ensures plugin status is displayed correctly regardless of whether specific plugins were selected or all plugins are running by default.
