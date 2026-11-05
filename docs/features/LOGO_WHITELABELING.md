# Logo White-Labeling Feature

## Overview

The Logo White-Labeling feature allows KAST Web administrators and users to customize the logo that appears on generated security scan reports. This enables managed service providers (MSPs) and organizations to brand reports with their own logo or their clients' logos.

## Key Features

- **Multiple Logo Support**: Upload and manage multiple logos for different clients or purposes
- **System Default Logo**: Set a system-wide default logo that applies to all scans unless overridden
- **Per-Scan Logo Selection**: Override the default logo for specific scans
- **Logo Management Interface**: Web-based UI for uploading, viewing, and managing logos
- **Automatic Integration**: Logos are automatically passed to the KAST CLI during scan execution and report regeneration
- **Broad Format Support**: Vector (SVG, SVGZ) and raster (PNG, JPEG, WebP, AVIF, GIF, BMP, TIFF, ICO) uploads

## Architecture

### Database Schema

#### ReportLogo Table
Stores logo file metadata:
- `id`: Primary key
- `name`: Display name for the logo
- `description`: Optional description
- `filename`: Original filename
- `file_path`: Absolute path to the stored file
- `mime_type`: MIME type of the stored original
- `file_size`: File size in bytes
- `render_path`: Absolute path to the render derivative handed to the KAST CLI
- `render_mime`: MIME type of that derivative (`image/png` or `image/svg+xml`)
- `width` / `height`: Pixel dimensions, for display only (NULL when an SVG declares neither a size nor a viewBox)
- `uploaded_by`: Foreign key to User
- `uploaded_at`: Upload timestamp

`render_path` and `render_mime` are NULL for rows created before multi-format
support; the code falls back to `file_path` in that case.

#### Scan Table Updates
- `logo_id`: Foreign key to ReportLogo (nullable - NULL means use system default)

#### System Settings
- `default_logo_id`: System-wide default logo ID

### File Storage

Originals are stored in: `app/static/uploads/logos/`
Render derivatives are stored in: `app/static/uploads/logos/render/`

Originals use UUID-prefixed filenames to prevent conflicts; the derivative
reuses the same UUID:
```
logos/{uuid}-{original_filename}
logos/render/{uuid}.png     (or .svg)
```

When the upload needs no conversion (PNG, JPEG, SVG, SVGZ), `render_path`
points at the original file and no second copy is written.

### Supported Upload Formats

| Format | Extensions | Type | What reports use |
|---|---|---|---|
| PNG | `.png` | raster | the original file |
| JPEG | `.jpg`, `.jpeg` | raster | the original file |
| SVG | `.svg` | vector | the sanitized SVG |
| SVGZ | `.svgz` | vector | the sanitized SVG (decompressed) |
| WebP | `.webp` | raster | a generated PNG |
| AVIF | `.avif` | raster | a generated PNG |
| GIF | `.gif` | raster | a generated PNG (first frame) |
| BMP | `.bmp` | raster | a generated PNG |
| TIFF | `.tif`, `.tiff` | raster | a generated PNG (first page) |
| ICO | `.ico` | raster | a generated PNG (largest frame) |

Deliberately not supported: HEIC/HEIF (needs `pillow-heif`), PDF, EPS and AI
(decoding shells out to Ghostscript, an unnecessary code-execution surface),
JPEG XL, EMF and WMF.

The registry lives in `app/logo_media.py` (`LOGO_FORMATS`); adding a raster
format is a matter of adding an entry plus its magic-byte signature in
`sniff_format`.

#### Why a render derivative exists

The KAST CLI base64-embeds the logo into the PDF and derives the MIME type
from the file extension, recognizing only png/jpg/jpeg/gif/svg. Handing it a
WebP or AVIF file would declare a false MIME type to WeasyPrint. KAST Web
therefore keeps the upload as-is for provenance and passes `--logo` a file the
CLI is guaranteed to embed correctly. Nothing on the kast side changes.

SVG is passed through as vector, so PDF logos stay sharp at any scale.

### Limits

Configurable in `config.py` or via environment variables:

- `LOGO_MAX_UPLOAD_BYTES` (default 5MB)
- `LOGO_MAX_DIMENSION` (default 2000px on the longest edge; larger raster
  uploads are downscaled during normalization)

### Dependencies

- `Pillow` - raster decoding, verification and PNG normalization
- `defusedxml` - hardened XML parsing for SVG uploads

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

For an existing installation, also run the multi-format migration:

```bash
pip install -r requirements.txt   # adds Pillow and defusedxml
python utils/migrate_logo_formats.py --non-interactive
```

This adds the `render_path`, `render_mime`, `width` and `height` columns,
points existing logos at their own file as the render derivative, and creates
`app/static/uploads/logos/render/`. It is idempotent.

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
   - **Logo File**: Select a file in any supported format (max 5MB)
3. Click **Upload Logo**

Each logo card shows a format badge, the pixel dimensions, and - when the
upload was converted - a note naming the original format with a link to it.

**Best Practices**:
- Prefer SVG: it stays vector all the way into the PDF and scales cleanly
- For raster logos, use PNG with a transparent background, ~200x60 pixels
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
Returns the original uploaded file, with `Content-Security-Policy`,
`X-Content-Type-Options: nosniff` and `Content-Disposition: inline` headers.

### View Render Derivative
```
GET /logos/<logo_id>/render
```
Returns the exact file reports embed (PNG or sanitized SVG). Redirects to
`/logos/<logo_id>` for rows predating multi-format support. This is what the
management page previews.

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
Cheap up-front checks: a filename is present, the extension is in the registry,
and the size is within `LOGO_MAX_UPLOAD_BYTES`.

```python
app.logo_media.prepare_logo(data, filename) -> dict
```
The real gate. Verifies magic bytes against the declared extension, sanitizes
SVG, decodes and normalizes raster data, and returns both artifacts. Raises
`ValueError` with a user-facing message on anything it rejects.

#### Logo Storage
```python
save_logo_file(file, uploader_id) -> (bool, dict)
```
Runs `prepare_logo`, then writes the original and (when distinct) the render
derivative with UUID-based naming. Cleans up partial writes on failure.

#### Logo Retrieval
```python
get_logo_for_scan(scan) -> str
get_render_path_for_logo(logo) -> str
```
Resolves which logo to use for a scan following the priority order, returning
the render derivative when one exists.

### Security Considerations

1. **Content Verification**: The extension is never trusted on its own. Magic
   bytes must agree with it, and raster uploads must decode cleanly under
   Pillow (`verify()`), so a renamed archive or a corrupt file is rejected.
2. **SVG Sanitization**: Uploaded SVG is parsed with `defusedxml` (blocking
   XXE, entity expansion and external DTDs), then filtered through an element
   allowlist. Scripting (`<script>`, `<foreignObject>`, `on*` attributes),
   animation elements, external `href`/`xlink:href` targets, `javascript:`
   URLs, `@import` and non-`data:` CSS `url()` references are all removed.
   **Only the sanitized document is written to disk** - the raw upload is
   never stored.
3. **Hardened Serving**: `/logos/<id>` and `/logos/<id>/render` send
   `Content-Security-Policy: default-src 'none'; ... sandbox`,
   `X-Content-Type-Options: nosniff` and `Content-Disposition: inline`, so an
   SVG opened by direct navigation cannot execute or phone home even if
   sanitization were bypassed.
4. **Decompression Bomb Guard**: `Image.MAX_IMAGE_PIXELS` is capped and
   oversized images are downscaled to `LOGO_MAX_DIMENSION`.
5. **File Size Limits**: Maximum 5MB per logo (`LOGO_MAX_UPLOAD_BYTES`)
6. **Filename Sanitization**: Filenames are sanitized to prevent path traversal
7. **UUID Prefixing**: Files are stored with UUID prefixes to prevent conflicts
8. **Permission Checks**: Users can only delete their own logos; admins can delete any
9. **Audit Logging**: All logo operations are logged in the audit log, including
   the uploaded format and the format reports will use

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

1. **File Too Large**: Ensure the file is under 5MB
2. **Invalid Format**: See the supported-format table above
3. **"File contents do not match the extension"**: The file was renamed rather
   than converted. Re-export it in its real format.
4. **"Not a valid SVG document"**: The SVG contains a DOCTYPE/entity
   declaration (blocked outright) or is malformed. Re-export from the design
   tool with "no DOCTYPE" / plain SVG output.
5. **Missing Dependency**: `Pillow` and `defusedxml` must be installed
   (`pip install -r requirements.txt`)
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
8. **HEIC/HEIF Support**: Would require the `pillow-heif` dependency
9. **Vector Import from PDF/EPS/AI**: Requires a Ghostscript-class dependency

## Support

For issues or questions about this feature:

1. Check the application logs
2. Review this documentation
3. Contact your system administrator
4. File an issue in the project repository

## Version History

- **v2.0** (Current): Expanded format support
  - SVG and SVGZ vector uploads, sanitized and kept vector through to PDF
  - WebP, AVIF, GIF, BMP, TIFF and ICO uploads, normalized to PNG for reports
  - Magic-byte content verification replacing the extension-only check
  - Hardened serving headers on logo responses
  - New columns `render_path`, `render_mime`, `width`, `height`
    (migration: `utils/migrate_logo_formats.py`)
  - Upload limit raised from 2MB to 5MB

- **v1.0**: Initial implementation
  - Multiple logo support
  - System default logo
  - Upload/delete/manage interface
  - Integration with scan execution
  - Integration with report regeneration
