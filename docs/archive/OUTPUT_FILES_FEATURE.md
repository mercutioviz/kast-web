# Output Files Directory Listing Feature

## Overview
Added a new feature to the scan details page that allows users to view a directory listing of all files in the scan's output directory. This feature opens in a new tab for easy reference while viewing scan details.

## Changes Made

### 1. New Route (`app/routes/scans.py`)
- Added `list_files(scan_id)` route at `/scans/<int:scan_id>/files`
- Retrieves scan information and validates output directory exists
- Collects all files and directories with metadata (name, size, modified time)
- Renders the `scan_files.html` template with the collected data

### 2. New Template (`app/templates/scan_files.html`)
- Displays directory information including scan ID, target, and output path
- Shows separate tables for directories and files
- Files table includes:
  - File type icons (JSON, HTML, CSS, TXT, generic)
  - File name in monospace font
  - Human-readable file size
  - Last modified timestamp
- Directories table includes:
  - Directory name with folder icon
  - Last modified timestamp
- Responsive design using Bootstrap cards and tables

### 3. Template Filters (`app/__init__.py`)
Added two custom Jinja2 template filters:
- `timestamp_to_datetime`: Converts Unix timestamps to formatted datetime strings (YYYY-MM-DD HH:MM:SS)
- `filesizeformat`: Formats file sizes in human-readable format (B, KB, MB, GB)

### 4. UI Button (`app/templates/scan_detail.html`)
- Added "View Output Files" button in the Actions section
- Button appears when `scan.output_dir` exists
- Opens in a new tab using `target="_blank"`
- Positioned between report actions and re-run/delete actions
- Uses Bootstrap outline-primary styling with folder icon

### 5. File Viewing Route (`app/routes/scans.py`)
- Added `view_file(scan_id, filename)` route at `/scans/<int:scan_id>/view-file/<path:filename>`
- Serves individual files from the scan output directory
- Automatically determines MIME type based on file extension
- Supports viewing of JSON, HTML, TXT, CSS, JS, XML, and image files
- Opens files directly in the browser for viewing
- Includes security measures to prevent directory traversal attacks

### 6. Clickable File Links (`app/templates/scan_files.html`)
- File names in the directory listing are now clickable links
- Each link opens the file in a new browser tab
- Links use the `view_file` route to serve the file content
- Maintains the file type icon for visual identification

## Usage

1. Navigate to any scan detail page
2. If the scan has an output directory, the "View Output Files" button will appear in the Actions sidebar
3. Click the button to open the directory listing in a new tab
4. The listing shows all files and directories with their metadata
5. Click on any file name to view the file contents in a new browser tab
6. Use the "Back to Scan Details" button to return to the scan detail page

## Technical Details

### Security Considerations
- All routes validate that the scan exists and has an output directory
- Directory traversal is prevented by using Path operations and path validation
- The `list_files` route only reads file metadata
- The `view_file` route serves files with appropriate MIME types
- Path resolution ensures files are only served from within the scan's output directory

### File Type Icons
The template uses Bootstrap Icons to display appropriate icons for:
- JSON files (`.json`)
- HTML files (`.html`)
- CSS files (`.css`)
- Text files (`.txt`)
- Generic files (fallback)

### Error Handling
- Displays flash messages if scan not found
- Displays flash messages if output directory doesn't exist
- Handles exceptions when reading directory contents
- Gracefully handles missing or invalid timestamps/file sizes

## Features

### File Viewing
- Click any file name in the directory listing to view it in the browser
- Supported file types are automatically displayed with correct formatting:
  - **JSON files**: Displayed as formatted JSON in the browser
  - **HTML files**: Rendered as HTML pages
  - **Text files**: Displayed as plain text
  - **CSS/JS files**: Displayed with appropriate syntax
  - **Images**: Displayed as images (JPG, PNG, GIF, SVG)
  - **Other files**: Displayed as plain text by default

### User Experience
- All file views open in new tabs, allowing easy comparison between files
- File type icons provide visual cues about file content
- Clean, responsive interface matches the existing KAST Web design
- Easy navigation back to scan details or directory listing

## Future Enhancements
Potential improvements could include:
- Download buttons for individual files
- Syntax highlighting for code files
- Sorting options (by name, size, date)
- Search/filter functionality
- Subdirectory navigation
- File type filtering
- Inline file preview without opening new tabs
