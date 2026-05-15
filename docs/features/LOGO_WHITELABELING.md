# Logo White-Labeling Feature

## Overview

The Logo White-Labeling feature allows KAST Web administrators and users to customize the logo that appears on generated security scan reports. This enables managed service providers (MSPs) and organizations to brand reports with their own logo or their clients' logos.

## Key Features

- **Multiple Logo Support**: Upload and manage multiple logos for different clients or purposes
- **System Default Logo**: Set a system-wide default logo that applies to all scans unless overridden
- **Per-Scan Logo Selection**: Override the default logo for specific scans
- **Logo Management Interface**: Web-based UI for uploading, viewing, and managing logos
- **Automatic Integration**: Logos are automatically passed to the KAST CLI during scan execution and report regeneration

## Architecture

### Database Schema

#### ReportLogo Table
Stores logo file metadata:
- `id`: Primary key
- `name`: Display name for the logo
- `description`: Optional description
- `filename`: Original filename
- `file_path`: Absolute path to the stored file
- `mime_type`: Image MIME type (image/png, image/jpeg)
- `file_size`: File size in bytes
- `uploaded_by`: Foreign key to User
- `uploaded_at`: Upload timestamp

#### Scan Table Updates
- `logo_id`: Foreign key to ReportLogo (nullable - NULL means use system default)

#### System Settings
- `default_logo_id`: System-wide default logo ID

### File Storage

Logos are stored in: `app/static/uploads/logos/`

Files are stored with UUID-prefixed filenames to prevent conflicts:
```
{uuid}-{original_filename}
```

### Logo Resolution Priority

When a scan is executed or a report is regenerated, the system resolves which logo to use in this order:

1. **Scan-specific logo** (if `scan.logo_id` is set)
2. **System default logo** (from SystemSettings.default_logo_id)
3. **Fallback logo** (`app/static/images/kast-logo.png`)

## Installation & Setup

### 1. Run Database Migration

Execute the migration script to create the necessary database tables and setup:

```bash
python utils/migrate_logo_feature.py
```

This script will:
- Create the `report_logos` table
- Add the `logo_id` column to the `scans` table
- Create the uploads directory structure
- Copy the current KAST logo as the default logo
- Set up the system default logo setting

### 2. Update KAST CLI

**IMPORTANT**: The KAST CLI tool must support the `--logo` parameter for this feature to work. 

If your KAST CLI doesn't support this parameter yet, you need to update it to accept:
```bash
kast -t example.com --logo /path/to/logo.png
```

The logo path should be passed when:
- Running scans: `kast -t <target> --logo <path>`
- Regenerating reports: `kast --report-only <output_dir> --logo <path>`

### 3. Restart Application

After running the migration, restart the KAST Web application:

```bash
# If using systemd
sudo systemctl restart kast-web

# Or if running manually
python run.py
```

## Usage Guide

### For Administrators

#### Accessing Logo Management

1. Log in as an administrator
2. Click on **Admin** dropdown in the navigation bar
3. Select **Manage Logos**

#### Uploading a New Logo

1. On the Logo Management page, click **Upload New Logo**
2. Fill in the form:
   - **Logo Name**: A descriptive name (e.g., "Client ABC Logo", "MSP Logo")
   - **Description**: Optional notes about the logo
   - **Logo File**: Select a PNG, JPG, or JPEG file (max 2MB)
3. Click **Upload Logo**

**Best Practices**:
- Use PNG format with transparent background
- Recommended dimensions: ~200x60 pixels
- Keep file size under 500KB for best performance

#### Setting System Default Logo

1. Find the logo you want to set as default
2. Click **Set Default** button on that logo card
3. The logo will be marked with a "System Default" badge

The system default logo will be used for all scans that don't have a specific logo selected.

#### Deleting a Logo

1. Find the logo you want to delete
2. Click **Delete** button
3. Confirm the deletion

**Note**: You cannot delete the system default logo. Set a different default first if you need to delete the current default.

### For Users

#### Viewing Available Logos

All authenticated users can view the logos available in the system by visiting the Manage Logos page.

#### Selecting Logo for a Scan

**During Scan Creation** (Feature requires UI update):
- When creating a new scan, select a logo from the dropdown
- If no logo is selected, the system default will be used

**Changing Logo for Existing Scan** (Feature requires UI update):
- Navigate to the scan detail page
- Click "Change Logo"
- Select a new logo from the available options

## API Endpoints

### List All Logos
```
GET /logos/api/list
```
Returns JSON array of all available logos.

### Get Logo Information
```
GET /logos/api/<logo_id>/info
```
Returns detailed information about a specific logo.

### View/Download Logo
```
GET /logos/<logo_id>
```
Returns the logo image file.

### Upload Logo
```
POST /logos/upload
```
Form data:
- `logo_file`: File upload
- `name`: Logo name
- `description`: Optional description

### Delete Logo
```
POST /logos/<logo_id>/delete
```
Deletes the specified logo (admin or owner only).

### Set Default Logo
```
POST /logos/<logo_id>/set-default
```
Sets the specified logo as system default (admin only).

## Technical Details

### Utilities

#### Logo Validation
```python
validate_logo_file(file) -> (bool, str)
```
Validates uploaded files for:
- File extension (png, jpg, jpeg only)
- File size (max 2MB)
- File integrity

#### Logo Storage
```python
save_logo_file(file, uploader_id) -> (bool, dict)
```
Handles secure file storage with UUID-based naming.

#### Logo Retrieval
```python
get_logo_for_scan(scan) -> str
```
Resolves which logo to use for a scan following the priority order.

### Security Considerations

1. **File Validation**: Only image files (PNG, JPG, JPEG) are accepted
2. **File Size Limits**: Maximum 2MB per logo
3. **Filename Sanitization**: Filenames are sanitized to prevent path traversal
4. **UUID Prefixing**: Files are stored with UUID prefixes to prevent conflicts
5. **Permission Checks**: Users can only delete their own logos; admins can delete any
6. **Audit Logging**: All logo operations are logged in the audit log

### Integration with KAST CLI

The logo path is passed to KAST CLI using the `--logo` parameter:

```python
# During scan execution
cmd = [kast_cli, '-t', target, '--logo', logo_path, ...]

# During report regeneration  
cmd = [kast_cli, '--report-only', output_dir, '--logo', logo_path, ...]
```

If no logo is found or the file doesn't exist, the command proceeds without the `--logo` parameter.

## Troubleshooting

### Logo Not Appearing in Report

1. **Check KAST CLI Support**: Ensure your KAST CLI version supports the `--logo` parameter
   ```bash
   kast --help | grep logo
   ```

2. **Verify Logo File Exists**: Check that the logo file is present on the filesystem
   ```bash
   ls -la app/static/uploads/logos/
   ```

3. **Check Logs**: Review application logs for logo-related messages
   ```bash
   tail -f logs/kast-web.log | grep -i logo
   ```

### Upload Errors

1. **File Too Large**: Ensure the file is under 2MB
2. **Invalid Format**: Only PNG, JPG, and JPEG are accepted
3. **Permissions**: Check that the uploads directory is writable
   ```bash
   chmod 755 app/static/uploads/logos/
   ```

### Cannot Delete Logo

1. **System Default**: You cannot delete the system default logo. Set a different default first.
2. **Permissions**: Regular users can only delete their own uploads; contact an admin.

## Future Enhancements

Potential improvements for this feature:

1. **Scan Form Integration**: Add logo selection dropdown to scan creation form
2. **Scan Detail UI**: Add logo change interface on scan detail page
3. **Logo Preview**: Show logo preview before upload
4. **Bulk Operations**: Allow bulk logo management operations
5. **Logo Versioning**: Track logo version history
6. **Organization Logos**: Support for organization-level logos in multi-tenant setup
7. **Logo Dimensions Validation**: Validate optimal dimensions for reports
8. **Image Optimization**: Automatically optimize/resize uploaded logos

## Support

For issues or questions about this feature:

1. Check the application logs
2. Review this documentation
3. Contact your system administrator
4. File an issue in the project repository

## Version History

- **v1.0** (Current): Initial implementation
  - Multiple logo support
  - System default logo
  - Upload/delete/manage interface
  - Integration with scan execution
  - Integration with report regeneration
