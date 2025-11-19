# Regenerate Report Feature

## Overview
Added a "Regenerate Report" feature to kast-web that allows users to regenerate the HTML report without re-running all plugins using the `kast --report-only` command.

## Implementation Details

### 1. Backend Task (app/tasks.py)
- **New Function**: `regenerate_report_task(scan_id)`
- **Purpose**: Celery task that executes `kast --report-only <output_dir>`
- **Timeout**: 5 minutes (300 seconds)
- **Returns**: Success/failure status with error messages if applicable

### 2. Route Handler (app/routes/scans.py)
- **New Route**: `/scans/<scan_id>/regenerate-report` (POST)
- **Function**: `regenerate_report(scan_id)`
- **Validation**: Checks that scan exists and has a valid output directory
- **Action**: Triggers the Celery task asynchronously
- **Feedback**: Flash messages to inform user of status

### 3. User Interface

#### Scan History Page (app/templates/scan_history.html)
- **Location**: Button placed between "View Report" and "Re-run Scan" buttons
- **Visibility**: Only shown for completed scans with output directories
- **Icon**: `bi-arrow-repeat` (Bootstrap Icons)
- **Color**: Warning (orange/yellow) to distinguish from other actions
- **Confirmation**: Prompts user to confirm before regenerating

#### Scan Details Page (app/templates/scan_detail.html)
- **Location**: Button placed right above "Re-run Scan" button in Actions sidebar
- **Visibility**: Only shown for completed scans with output directories
- **Icon**: `bi-arrow-repeat` (Bootstrap Icons)
- **Color**: Warning (btn-warning)
- **Confirmation**: Prompts user to confirm before regenerating

## Usage

1. Navigate to a completed scan in either:
   - Scan History page
   - Scan Details page

2. Click the "Regenerate Report" button (with refresh icon)

3. Confirm the action when prompted

4. The system will execute `kast --report-only <output_dir>` in the background

5. The updated HTML report will be available once the task completes

## Benefits

- **Fast**: Only regenerates the report, doesn't re-run plugins
- **Testing**: Ideal for testing minor changes to the reporting system
- **Efficient**: Saves time compared to re-running the entire scan
- **Safe**: Doesn't affect existing scan data, only updates the HTML report

## Technical Notes

- Uses Celery for asynchronous execution
- 5-minute timeout prevents long-running processes
- Proper error handling and user feedback
- Security: Validates output directory exists and is accessible
- Only available for completed scans (not for running, failed, or pending scans)
