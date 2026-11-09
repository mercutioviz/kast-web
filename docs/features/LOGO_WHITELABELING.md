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

Logo files live under `LOGO_STORAGE_DIR`:

```
<LOGO_STORAGE_DIR>/originals/{uuid}-{filename}
<LOGO_STORAGE_DIR>/render/{uuid}.png        (or .svg)
<LOGO_STORAGE_DIR>/staging/{token}-*        (unconfirmed URL imports)
```

Defaults to `instance/logos` in a dev checkout. Production sets it in `.env`:

```
LOGO_STORAGE_DIR=/var/lib/kast-web/logos
```

**This directory must stay outside `app/static/`.** nginx serves `/static`
straight off disk (`alias /opt/kast-web/app/static`), so anything under it is
readable by anyone on the internet with no authentication and none of the
security headers the `/logos/<id>` route sets. Logo files are user-supplied
content - including SVG, which is an active document format - so they are
served only through the authenticated routes. Logos uploaded before v2.0.15
lived under `app/static/uploads/logos/` and are relocated by
`utils/migrate_logo_url_import.py`.

Originals use UUID-prefixed filenames to prevent conflicts; the derivative
reuses the same UUID. When the upload needs no conversion (PNG, JPEG, SVG,
SVGZ), `render_path` points at the original file and no second copy is
written.

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

- `LOGO_STORAGE_DIR` (see File Storage above)
- `LOGO_MAX_UPLOAD_BYTES` (default 5MB; applies to URL imports too)
- `LOGO_MAX_DIMENSION` (default 2000px on the longest edge; larger raster
  uploads are downscaled during normalization)
- `LOGO_STAGING_TTL_SECONDS` (default 1800) - how long a fetched-but-
  unconfirmed URL import is kept
- `LOGO_IMPORT_ALLOWED_PORTS` (default `80,443`)
- `LOGO_IMPORT_MAX_REDIRECTS` (default 3)
- `LOGO_IMPORT_CONNECT_TIMEOUT` / `LOGO_IMPORT_READ_TIMEOUT` /
  `LOGO_IMPORT_TOTAL_DEADLINE` (default 5 / 10 / 15 seconds)
- `LOGO_IMPORT_RATE_LIMIT` (default 10 fetches per minute per user; 0 disables)

### Dependencies

- `Pillow` - raster decoding, verification and PNG normalization
- `defusedxml` - hardened XML parsing for SVG uploads

### Importing from a URL

Instead of uploading a file, a user can paste the URL of an image. The server
fetches it, shows a preview, and only stores it once the user confirms.

The flow is deliberately two-step:

1. `POST /logos/import/fetch` - the server fetches the URL under the SSRF
   guard below, runs the bytes through the same `prepare_logo()` used for
   uploads, and writes the result to the staging area
2. The modal previews the staged render derivative - exactly what reports
   would embed - alongside the detected format, dimensions and the final URL
   after any redirects
3. `POST /logos/import/confirm` - the staged files are promoted to permanent
   storage and the `ReportLogo` row is created with `source_url` set

Staging rather than re-fetching on confirm is the point: the bytes the user
approved in the preview are the bytes that get stored. A second fetch could be
served different content.

Abandoned previews are removed by a TTL sweep that runs at the start of each
fetch, and the browser discards its staged import when the dialog is closed.

The file extension for an import is taken from the fetched bytes, not the URL:
asset URLs frequently carry no extension, and content negotiation routinely
serves WebP from a `.png` URL. `prepare_logo()` still verifies magic bytes, so
unrecognized content is still refused.

#### SSRF policy

A user-supplied URL fetched by the server is a server-side request forgery
primitive, so `app/url_fetch.py` constrains every request:

- `http` and `https` only, on `LOGO_IMPORT_ALLOWED_PORTS` (80/443 by default)
- no credentials in the URL
- the hostname is resolved up front and **every** address it returns must be
  public: loopback, RFC1918 private, link-local (including the cloud metadata
  address `169.254.169.254`), CGNAT, reserved, multicast, IPv4-mapped and
  6to4-wrapped addresses are all refused
- the validated IP is **pinned** for the connection, so DNS cannot be rebound
  between the check and the connect. TLS SNI and certificate verification
  still use the real hostname
- redirects are followed manually and **every hop is re-validated**, so a
  public URL cannot bounce the server to an internal one
- the body is streamed with a hard byte cap and a wall-clock deadline
- proxy and netrc environment settings are ignored for these requests
- refusal messages never name a resolved address, so the endpoint cannot be
  used to map the network

The `Content-Type` a remote server reports is recorded but never trusted -
magic-byte sniffing decides what the file actually is.

Rate limiting is per-user per-minute via the Celery Redis instance. It is an
abuse throttle, not an authorization control, so a Redis outage fails open
with a logged warning rather than blocking the feature.

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

For an existing installation, also run the follow-up migrations:

```bash
pip install -r requirements.txt   # adds Pillow and defusedxml

python utils/migrate_logo_formats.py --non-interactive
python utils/migrate_logo_url_import.py --non-interactive
```

`migrate_logo_formats.py` adds the `render_path`, `render_mime`, `width` and
`height` columns and points existing logos at their own file as the render
derivative.

`migrate_logo_url_import.py` adds `source_url` and moves logo files out of
`app/static/uploads/logos/` into `LOGO_STORAGE_DIR`, rewriting the stored
paths. Set `LOGO_STORAGE_DIR` in `.env` first on a production install, and
back up the database. Both are idempotent.

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

### Import from URL
```
POST /logos/import/fetch         {"url": "..."}  -> preview metadata + token
GET  /logos/import/<token>/preview               -> staged render derivative
POST /logos/import/confirm       {"token", "name", "description"}
POST /logos/import/<token>/discard
```
All owner-scoped: a staging token is usable only by the user who created it,
and only until it expires.

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
9. **Audit Logging**: All logo operations are logged in the audit log,
   including the uploaded format, the format reports will use, and - for URL
   imports - the final URL fetched
10. **Storage Outside the Web Root**: Logo files live under
    `LOGO_STORAGE_DIR`, never under `app/static/`, because nginx serves
    `/static` directly from disk with no authentication. See File Storage.
11. **SSRF Guard on URL Import**: See the SSRF policy section above.

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

### URL Import Errors

1. **"That URL points to a private or internal address"**: the hostname
   resolves to a loopback, private, link-local or otherwise non-public
   address. This is refused by design; download the file and upload it
   instead.
2. **"Only ports 80, 443 can be imported from"**: adjust
   `LOGO_IMPORT_ALLOWED_PORTS` if you genuinely need another port.
3. **"That URL does not point to a supported image"**: the response was not
   an image the format registry recognizes - often an HTML error or login
   page returned instead of the file.
4. **"The HTTPS certificate for that site could not be verified"**: the
   remote certificate failed validation. Certificate checking is not
   bypassable here.
5. **"That preview has expired"**: more than `LOGO_STAGING_TTL_SECONDS`
   elapsed between fetching and confirming. Fetch again.
6. **"Too many import attempts"**: the per-user rate limit
   (`LOGO_IMPORT_RATE_LIMIT`) kicked in. Wait a minute.

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
10. **Re-fetch**: Refresh an imported logo from its `source_url` on demand
11. **Pick from a page**: Import a page and choose among the images on it

## Support

For issues or questions about this feature:

1. Check the application logs
2. Review this documentation
3. Contact your system administrator
4. File an issue in the project repository

## Version History

- **v2.1** (Current): Import from URL
  - Paste an image URL; the server fetches it, previews it, and adds it on
    confirmation
  - SSRF-guarded fetcher in `app/url_fetch.py`
  - Logo storage moved out of `app/static/` so files are no longer publicly
    readable (migration: `utils/migrate_logo_url_import.py`)
  - New column `source_url` recording where an imported logo came from

- **v2.0**: Expanded format support
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
