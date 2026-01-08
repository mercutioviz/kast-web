# ZAP Real-Time Progress Feedback Feature

## Overview

This feature provides real-time progress feedback for ZAP (OWASP ZAP) scans, allowing users to monitor the scan's progress, view live statistics, and track findings as they are discovered. Unlike other plugins, ZAP scans generate a `zap_scan_progress.json` file that is continuously updated during execution, providing rich progress data.

## Implementation Date

**Implemented:** January 8, 2026

## Feature Components

### 1. Backend - API Enhancement (`app/routes/api.py`)

**GET `/api/scans/<scan_id>/status`** endpoint has been enhanced to:

- Detect when ZAP plugin is included in a scan
- Look for `zap_scan_progress.json` (active scan) or `zap_scan_final_progress.json` (completed scan)
- Parse the progress file and include ZAP-specific data in the API response
- Return structured progress data including phases, percentages, and findings

**Response Structure:**
```json
{
  "scan_id": 123,
  "status": "running",
  "results": [...],
  "zap_progress": {
    "available": true,
    "scan_started": "2026-01-08T18:59:29.592Z",
    "last_updated": "2026-01-08T19:08:02.688",
    "elapsed_seconds": 507,
    "status": "running",
    "progress": {
      "spider_percent": 100,
      "active_scan_percent": 16,
      "passive_scan_queue": 0
    },
    "alerts": {
      "total": 1501,
      "High": 3,
      "Medium": 267,
      "Low": 533,
      "Informational": 698
    },
    "job_updates": [
      "Job spiderClient started",
      "Job spiderClient finished, time taken: 00:00:25",
      "Job activeScan started"
    ],
    "current_phase": "Active Scan",
    "warnings": [],
    "errors": []
  }
}
```

### 2. Frontend - UI Enhancement (`app/templates/scan_detail.html`)

#### Interactive Progress Badge

When ZAP scan is in progress, the "In Progress" badge becomes:
- **Clickable** - Opens the progress modal
- **Animated** - Shows a pulsing spinner to indicate active scanning
- **Styled** - Cursor changes to pointer on hover

#### Progress Modal

A Bootstrap modal displays:

**Timing Information:**
- Elapsed time since scan start
- Current phase indicator

**Progress Bars:**
- Spider phase (0-100%) with visual progress bar
- Active scan phase (0-100%) with animated progress bar
- Passive scan queue status (if applicable)

**Live Findings:**
- Total alerts discovered (updating in real-time)
- Risk breakdown with color-coded badges:
  - 🔴 High (red)
  - 🟠 Medium (orange)
  - 🟡 Low (yellow/light blue)
  - 🔵 Informational (gray/blue)

**Job History:**
- Chronological list of completed phases
- Visual indicators (✓ complete, ⏳ in progress)
- Duration for completed jobs

**Warnings & Errors:**
- Alert boxes for any warnings encountered
- Error messages if issues occur

#### Auto-Refresh

- Modal content updates automatically every 3 seconds
- Updates stop when modal is closed
- Leverages existing 3-second polling mechanism

### 3. Backend - Progress Preservation (`app/tasks.py`)

**Function: `preserve_zap_final_progress(output_dir)`**

When a ZAP scan completes:
1. Copies `zap_scan_progress.json` to `zap_scan_final_progress.json`
2. Preserves the final state for historical reference and audit purposes
3. The API endpoint will continue to serve this data even after scan completion

**Integration:**
- Called automatically after successful scan completion
- Only runs when ZAP plugin is detected
- Logs preservation action for debugging

## User Experience

### Before Enhancement

Users saw:
```
ZAP: In Progress [badge]
```

With no visibility into:
- What phase ZAP was executing
- How much progress had been made
- Whether any findings were discovered
- If the scan was actually running or frozen

### After Enhancement

Users click the animated "In Progress" badge and see:

```
┌──────────────────────────────────────┐
│ ZAP Scan Progress                     │
├──────────────────────────────────────┤
│ Elapsed Time: 8m 27s                  │
│ Current Phase: Active Scan            │
│                                        │
│ Spider Phase: ████████████ 100%      │
│   └─ Completed in 25s                 │
│                                        │
│ Active Scan: ██░░░░░░░░░░ 16%       │
│   └─ In progress...                   │
│                                        │
│ Findings Discovered:                  │
│   Total: 1,501 alerts                 │
│   🔴 High: 3                          │
│   🟠 Medium: 267                      │
│   🟡 Low: 533                         │
│   🔵 Info: 698                        │
│                                        │
│ Job History:                          │
│ ✓ Spider started                     │
│ ✓ Spider finished (25s)              │
│ ✓ Passive scan configured            │
│ ⏳ Active scan in progress...         │
└──────────────────────────────────────┘
```

## Benefits

✅ **Confidence** - Users know the scan is actively running, not frozen
✅ **Progress Visibility** - Clear indication of completion percentage
✅ **Early Findings** - See discovered vulnerabilities before scan completes
✅ **Phase Awareness** - Understand which stage is currently executing
✅ **Time Estimation** - Elapsed time helps estimate remaining duration
✅ **Historical Data** - Final progress state preserved for audit trail

## Technical Details

### ZAP Progress File Format

The `zap_scan_progress.json` file is created by the KAST ZAP plugin and contains:

```json
{
  "scan_started": "ISO timestamp",
  "last_updated": "ISO timestamp", 
  "elapsed_seconds": 507,
  "plan_id": "3",
  "status": "running|completed|failed",
  "finished": "",
  "progress": {
    "spider_percent": 0-100,
    "active_scan_percent": 0-100,
    "passive_scan_queue": 0
  },
  "alerts": {
    "total": 1501,
    "by_risk": {
      "alertsSummary": {
        "High": 3,
        "Medium": 267,
        "Low": 533,
        "Informational": 698
      }
    }
  },
  "job_updates": [
    "Job spiderClient started",
    "Job spiderClient finished, time taken: 00:00:25"
  ],
  "warnings": [],
  "errors": []
}
```

### Phase Detection Logic

The current phase is intelligently derived from `job_updates`:
- Last entry contains "spider" → "Spider" or "Spider Complete"
- Last entry contains "activescan" → "Active Scan" or "Active Scan Complete"
- Last entry contains "passivescan" → "Passive Scan" or "Passive Scan Complete"
- Otherwise → "Initializing"

### File Management

**Active Scan:**
- Progress file: `zap_scan_progress.json` (continuously updated by KAST)
- API reads this file during polling

**Completed Scan:**
- Original: `zap_scan_progress.json` (may be deleted by KAST)
- Preserved: `zap_scan_final_progress.json` (permanent copy)
- API prefers final version if both exist

## Code Files Modified

1. **app/routes/api.py** - Enhanced status endpoint to parse ZAP progress
2. **app/templates/scan_detail.html** - Added modal HTML and JavaScript
3. **app/tasks.py** - Added `preserve_zap_final_progress()` function

## Testing

### Manual Testing Steps

1. **Start a ZAP scan:**
   ```bash
   # Via UI or CLI with ZAP plugin selected
   ```

2. **Navigate to scan detail page** while scan is running

3. **Observe the ZAP row** in plugin results table:
   - Badge should show "In Progress" with animated spinner
   - Badge should be clickable (cursor changes to pointer)

4. **Click the badge** to open progress modal:
   - Modal should display immediately
   - Initial content may show "Loading..." briefly
   - Progress data should populate within 3 seconds

5. **Verify auto-refresh:**
   - Leave modal open
   - Watch progress bars and statistics update every 3 seconds
   - Percentages should increase
   - Alert counts should increase

6. **Close and reopen modal:**
   - Click X or click outside modal
   - Reopen by clicking badge again
   - Data should refresh immediately

7. **After scan completes:**
   - Check scan output directory for `zap_scan_final_progress.json`
   - Verify file contains final progress state
   - Open scan detail page
   - ZAP should show "Completed" badge (not clickable)

### Test with Example Scan

Use the existing scan data at:
```
/home/kali/kast_results/waas.cudalabx.net-20260108-185928/
```

This directory contains real ZAP progress data for testing.

## Future Enhancements

Potential improvements for future versions:

1. **Other Plugins** - Extend progress tracking to other plugins if they generate similar progress files
2. **Progress Chart** - Graph showing scan progress over time
3. **Notifications** - Alert when scan reaches certain milestones
4. **Export Progress** - Download progress data as JSON/CSV
5. **Comparison** - Compare progress between multiple scans

## Troubleshooting

### Modal shows "ZAP progress data is not yet available"

**Causes:**
- ZAP scan hasn't started yet (still pending)
- Progress file hasn't been created yet (< 5 seconds into scan)
- File system permissions prevent reading the file

**Resolution:**
- Wait a few more seconds and refresh
- Check file permissions on output directory
- Verify ZAP plugin is actually running

### Progress data not updating

**Causes:**
- Browser's JavaScript polling stopped
- KAST ZAP plugin not writing progress updates
- File system issues

**Resolution:**
- Close and reopen modal
- Check browser console for JavaScript errors
- Verify progress file is being updated: `ls -la /path/to/output/dir/zap_scan_progress.json`

### Scan completed but no final progress file

**Causes:**
- Scan failed before completion
- Progress preservation function failed
- File system issues during copy operation

**Resolution:**
- Check application logs for preservation errors
- Verify original progress file existed before completion
- Check file system space and permissions

## Security Considerations

- Progress data contains only statistical information (counts, percentages)
- No sensitive findings details are exposed in the progress file
- Progress modal requires user authentication (login_required)
- File access controlled by existing scan ownership/sharing permissions

## Performance Impact

- **Minimal** - Reuses existing 3-second polling mechanism
- No additional database queries
- Small JSON file parsing (< 10KB typically)
- Modal rendering is client-side only

## Backward Compatibility

- Feature is **fully backward compatible**
- Only activates when ZAP plugin is detected
- Other plugins unaffected
- Existing scans without progress files work normally
- No database migrations required

## Related Documentation

- [ZAP Integration Phase 1](ZAP_INTEGRATION_PHASE1.md)
- [ZAP Integration Phase 2](ZAP_INTEGRATION_PHASE2.md)
- [ZAP Remote Mode Verification](ZAP_REMOTE_MODE_VERIFICATION.md)
- [ZAP Plugin Debug Fix](ZAP_PLUGIN_DEBUG_FIX.md)

## Conclusion

The ZAP Real-Time Progress Feedback feature significantly enhances the user experience for ZAP scans by providing visibility into what would otherwise be an opaque "In Progress" state. Users gain confidence that scans are executing properly, can estimate completion times, and get early visibility into discovered findings.
