# Folder Browsing Feature

## Overview
Users can now browse subdirectories in scan output files, making it easy to navigate folder structures like `terraform_workspace` that appear in ZAP scan results.

## Changes Made

### 1. Updated Route (`app/routes/scans.py`)
- Modified `list_files` route to accept optional `subpath` parameter
- Added two route decorators:
  - `@bp.route('/<int:scan_id>/files')` - for root directory
  - `@bp.route('/<int:scan_id>/files/<path:subpath>')` - for subdirectories
- Implemented security validation to prevent directory traversal attacks
- Added breadcrumb navigation logic to track current location
- Enhanced file/directory metadata to include full relative paths

### 2. Updated Template (`app/templates/scan_files.html`)
- Made directory names clickable links that navigate into subdirectories
- Added breadcrumb navigation component showing current path
- Users can click breadcrumbs to navigate back up the directory tree
- Updated file links to use full relative paths from output directory

## Features

### Breadcrumb Navigation
- Displays the current location in the directory structure
- Example: `Output Directory / terraform_workspace / configs`
- Clickable breadcrumbs allow quick navigation back to parent directories
- Home icon links back to the root output directory

### Clickable Directories
- Directory names are now hyperlinks with folder icons
- Click a directory name to view its contents
- Maintains the same table layout for consistency

### Security
- Path traversal prevention using `Path.resolve()`
- Validates all paths stay within scan's output directory
- Prevents access to parent directories outside scan scope
- Returns error messages for invalid path attempts

### User Experience
- Consistent visual design with folder and file icons
- Responsive tables work on mobile devices
- Breadcrumb trail provides clear context
- "Back to Scan Details" button always available
- File counts update to show current directory contents

## Usage

1. Navigate to a scan's "View Output Files" page
2. Click on any folder name (e.g., `terraform_workspace`)
3. Browse the folder's contents
4. Click breadcrumb links to navigate back up
5. Click individual files to view/download them

## Technical Details

### Route Parameters
- `scan_id`: Integer identifying the scan
- `subpath`: Optional path string for subdirectory navigation

### Security Checks
```python
# Resolve paths to detect traversal attempts
current_path = current_path.resolve()
output_path_resolved = output_path.resolve()

# Ensure path is within output directory
if not str(current_path).startswith(str(output_path_resolved)):
    flash('Invalid path requested', 'danger')
    return redirect(...)
```

### Breadcrumb Generation
```python
# Build breadcrumbs from path parts
parts = Path(subpath).parts
for part in parts:
    breadcrumbs.append({
        'name': part,
        'path': breadcrumb_path
    })
```

## Related Files
- `app/routes/scans.py` - Route implementation
- `app/templates/scan_files.html` - UI template
- `app/routes/scans.py::view_file` - File viewing (already supports subdirectories)

## Testing Recommendations

1. Test basic folder navigation (click into folder, verify contents)
2. Test breadcrumb navigation (click each breadcrumb level)
3. Test deep nesting (multiple subdirectory levels)
4. Test security (attempt path traversal with `../` patterns)
5. Test edge cases (empty folders, special characters in names)
6. Test file access from subdirectories
7. Test permissions (ensure only authorized users can browse)

## Future Enhancements

Potential improvements for future versions:
- Add "parent directory" link for quick navigation up one level
- File/folder sorting options (name, date, size)
- Search/filter within current directory
- Download entire folder as ZIP
- Display folder sizes (total of all contents)
- Thumbnail previews for image files
