# CLI Scan Import Feature

## Overview

The CLI Scan Import feature allows administrators to import KAST scan results that were executed from the command line into the KAST-Web GUI. This provides a convenient way to consolidate scan results from both CLI and web-executed scans in a single interface.

## Feature Highlights

- **Admin-only access**: Import functionality is restricted to the admin dashboard
- **Automatic metadata extraction**: Target, scan mode, and plugins are automatically detected
- **Dual-source tracking**: Imported scans are marked with `source='imported'` to distinguish them from web-executed scans
- **Full integration**: Imported scans support all viewing, sharing, and report features
- **Validation**: Built-in validation ensures only valid KAST results are imported
- **Audit logging**: All import actions are logged for security and tracking

## Use Cases

1. **Consolidating Results**: Users who run scans from both CLI and web interface can view all results in one place
2. **Historical Data**: Import older CLI scan results for long-term tracking and comparison
3. **Team Collaboration**: Import CLI scans performed by one team member for review by others
4. **Bulk Management**: Leverage the web GUI's search, filter, and management features for CLI scans

## How It Works

### Database Changes

A new `source` field was added to the `scans` table:
- `source='web'`: Scan was executed through KAST-Web GUI (default)
- `source='imported'`: Scan was imported from CLI results

### Import Process

1. **Validation**: 
   - Checks if directory exists and is readable
   - Verifies presence of `*_processed.json` files (KAST result files)
   - Ensures directory hasn't been imported before

2. **Metadata Extraction**:
   - **Target**: Extracted from directory name (format: `target-YYYYMMDD-HHMMSS`)
   - **Scan Mode**: Determined by analyzing plugins (active vs passive)
   - **Plugins**: List extracted from `*_processed.json` filenames
   - **Timestamps**: Extracted from file modification times
   - **Results**: Parsed using existing `parse_scan_results()` function

3. **Database Creation**:
   - Creates `Scan` record with `source='imported'`
   - Creates `ScanResult` records for each plugin
   - Assigns scan to specified user
   - Logs import action to audit log

## Usage Guide

### Prerequisites

- Admin user account
- CLI scan results directory accessible by web server
- Valid KAST scan results (with `*_processed.json` files)

### Step-by-Step Instructions

1. **Navigate to Admin Dashboard**
   - Log in as an admin user
   - Go to Admin Dashboard

2. **Click "Import Scan" Button**
   - Located in the top button bar of the admin dashboard

3. **Enter Scan Directory Path**
   - Provide the full path to the CLI scan results directory
   - Example: `/home/user/kast_results/example.com-20250101-120000`

4. **Select User Assignment**
   - Choose which user should own the imported scan
   - Default is the current admin user

5. **Preview (Optional)**
   - The system will show a preview of what will be imported
   - Verify target, scan mode, plugins, and file count

6. **Import**
   - Click "Import Scan" to complete the import
   - You'll be redirected to the scan detail page upon success

### Expected Directory Structure

```
target-YYYYMMDD-HHMMSS/
├── plugin1_processed.json
├── plugin2_processed.json
├── plugin3_processed.json
├── report.html (optional)
└── report.json (optional)
```

## Implementation Details

### Files Modified/Created

1. **Database Migration**: `utils/migrate_import_feature.py`
   - Adds `source` field to scans table
   - Sets existing scans to `source='web'`

2. **Models**: `app/models.py`
   - Added `source` field to `Scan` model
   - Updated `to_dict()` to include source field

3. **Forms**: `app/forms.py`
   - Created `ImportScanForm` with directory and user assignment fields

4. **Import Utilities**: `app/import_utils.py`
   - `validate_scan_directory()`: Validates directory and checks for KAST results
   - `extract_scan_metadata()`: Extracts target, mode, plugins, and timestamps
   - `import_cli_scan()`: Main import function
   - `get_import_preview()`: Generates preview without importing

5. **Routes**: `app/routes/admin.py`
   - Added `/admin/import-scan` route (admin-only)
   - Handles form submission and preview generation

6. **Templates**: `app/templates/admin/import_scan.html`
   - Import form with validation
   - Preview display
   - Help documentation
   - Instructions

7. **Dashboard**: `app/templates/admin/dashboard.html`
   - Added "Import Scan" button to admin dashboard

## Running the Migration

Before using the import feature, run the database migration:

```bash
cd /opt/kast-web
python3 utils/migrate_import_feature.py
```

The migration will:
- Add the `source` column to the scans table
- Set all existing scans to `source='web'`
- Display a summary of changes

## Security Considerations

1. **Admin-Only Access**: Import functionality is restricted to admin users via `@admin_required` decorator

2. **Path Validation**: 
   - Directory existence and readability are checked
   - No arbitrary file system access allowed

3. **Audit Logging**: All import attempts (successful and failed) are logged to the audit log

4. **User Assignment**: Admins can assign imported scans to any user, allowing proper ownership tracking

## Limitations

1. **Read-Only Import**: Imported scans cannot be re-run from the web interface (they're already completed)

2. **No Celery Task ID**: Imported scans don't have an associated Celery task ID

3. **Manual Process**: Import is manual; no automated directory monitoring

4. **Single Import**: Each directory can only be imported once (prevents duplicates)

5. **File System Dependency**: Results must remain on the file system for viewing/downloading

## Error Handling

The import process includes comprehensive error handling:

- **Invalid Directory**: Clear error messages for missing or unreadable directories
- **No Results**: Warns if no `*_processed.json` files found
- **Already Imported**: Prevents duplicate imports with scan ID reference
- **Parse Errors**: Logs warnings for unparseable JSON files but continues import
- **Database Errors**: Rolls back changes and logs failures

## Future Enhancements

Potential improvements for future versions:

1. **Batch Import**: Import multiple scan directories at once
2. **Directory Monitoring**: Automatic import from watched directories
3. **CLI Tool**: Command-line utility for non-admin users to request imports
4. **Import History**: Dedicated page showing import history and statistics
5. **Preview Mode**: Import without committing to test validation
6. **File Copying**: Option to copy files to KAST-Web results directory

## Troubleshooting

### Common Issues

**Issue**: "Directory does not exist"
- **Solution**: Verify the full path is correct and accessible

**Issue**: "No KAST result files found"
- **Solution**: Ensure directory contains `*_processed.json` files from a KAST scan

**Issue**: "Directory is not readable"
- **Solution**: Check file permissions; web server user needs read access

**Issue**: "This directory has already been imported"
- **Solution**: This is expected behavior to prevent duplicates. Check existing scan ID in error message

**Issue**: Import succeeds but results don't display properly
- **Solution**: Ensure all result files remain in place and are readable

## API Reference

### ImportScanForm

Form for importing CLI scans.

**Fields:**
- `scan_directory`: Path to scan results directory (required, max 500 chars)
- `assign_to_user`: User ID to assign scan to (required, SelectField)
- `submit`: Submit button

### validate_scan_directory(scan_dir)

Validates that a directory contains valid KAST scan results.

**Parameters:**
- `scan_dir` (str): Path to scan results directory

**Returns:**
- `tuple`: (is_valid, error_message, result_files)

### extract_scan_metadata(scan_dir, result_files)

Extracts scan metadata from result files and directory structure.

**Parameters:**
- `scan_dir` (str): Path to scan results directory
- `result_files` (list): List of Path objects for result files

**Returns:**
- `dict`: Metadata dictionary with target, scan_mode, plugins, started_at, completed_at

### import_cli_scan(scan_dir, user_id, admin_user_id)

Imports a CLI scan into KAST-Web database.

**Parameters:**
- `scan_dir` (str): Path to scan results directory
- `user_id` (int): ID of user to assign scan to
- `admin_user_id` (int): ID of admin performing the import

**Returns:**
- `tuple`: (success, scan_id, error_message)

### get_import_preview(scan_dir)

Generates a preview of what would be imported without actually importing.

**Parameters:**
- `scan_dir` (str): Path to scan results directory

**Returns:**
- `dict`: Preview information including validation status, metadata, file count, and file list

## Testing

To test the import feature:

1. **Run a CLI scan**:
   ```bash
   kast -t example.com -o /tmp/test_import
   ```

2. **Access import page**: Navigate to Admin Dashboard → Import Scan

3. **Import the scan**: Enter `/tmp/test_import/example.com-YYYYMMDD-HHMMSS`

4. **Verify**: Check that scan appears in scan history with correct metadata

5. **Test validation**: Try importing the same directory again (should fail)

## Support

For issues or questions about the CLI Import feature:

1. Check this documentation first
2. Review the audit log for error details
3. Check KAST-Web application logs
4. Report issues using the `/reportbug` command

---

**Version**: 1.0  
**Last Updated**: December 11, 2025  
**Feature Added**: CLI Scan Import  
**Minimum KAST-Web Version**: Phase 4+
