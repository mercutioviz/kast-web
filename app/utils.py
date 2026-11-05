import subprocess
import json
import os
from pathlib import Path
from datetime import datetime
from functools import wraps
from flask import current_app, flash, redirect, url_for
from flask_login import current_user

def get_available_plugins():
    """
    Get list of available KAST plugins by calling kast --list-plugins
    Returns list of tuples: [(plugin_name, description, plugin_type), ...]
    where plugin_type is 'passive' or 'active'
    """
    try:
        kast_cli = current_app.config['KAST_CLI_PATH']
        result = subprocess.run(
            [kast_cli, '--list-plugins'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            current_app.logger.error(f"Failed to get plugins: {result.stderr}")
            return []
        
        # Parse the output to extract plugin names and types
        # The output format from kast is:
        # ✓ plugin_name (priority: X, type: passive/active)
        #   Description
        plugins = []
        lines = result.stdout.strip().split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('✓') or line.startswith('✗'):
                # Extract plugin name and type from line like: "✓ subfinder (priority: 1, type: passive)"
                parts = line.split('(')
                plugin_name = parts[0].strip().split()[-1]  # Get the last word (plugin name)
                
                # Extract plugin type from the parentheses
                plugin_type = 'passive'  # default
                if len(parts) > 1:
                    paren_content = parts[1]
                    if 'type:' in paren_content:
                        type_part = paren_content.split('type:')[1].split(')')[0].strip()
                        plugin_type = type_part
                
                # Get description from next line if available
                description = ''
                if i + 1 < len(lines) and not lines[i + 1].strip().startswith(('✓', '✗', 'Available')):
                    description = lines[i + 1].strip()
                
                full_description = f"{plugin_name} - {description}" if description else plugin_name
                plugins.append((plugin_name, full_description, plugin_type))
            i += 1
        
        return plugins
    except Exception as e:
        current_app.logger.error(f"Error getting plugins: {str(e)}")
        return []


def filter_plugins_by_mode(plugins, scan_mode):
    """
    Filter plugins based on scan mode
    
    Args:
        plugins: List of tuples [(plugin_name, description, plugin_type), ...]
        scan_mode: 'passive' or 'active'
    
    Returns:
        Filtered list of tuples [(plugin_name, description), ...] for form choices
    """
    if scan_mode == 'active':
        # Active scans can use both passive and active plugins
        return [(name, desc) for name, desc, _ in plugins]
    else:
        # Passive scans can only use passive plugins
        return [(name, desc) for name, desc, ptype in plugins if ptype == 'passive']

def execute_kast_scan(scan_id, target, scan_mode, plugins=None, parallel=False, verbose=False, dry_run=False):
    """
    Execute a KAST scan by calling the CLI
    
    Args:
        scan_id: Database scan ID
        target: Target domain
        scan_mode: 'active' or 'passive'
        plugins: List of plugin names to run (None = all)
        parallel: Run plugins in parallel
        verbose: Enable verbose output
        dry_run: Dry run mode
    
    Returns:
        dict with 'success', 'output_dir', 'error' keys
    """
    from app import db
    from app.models import Scan
    
    try:
        # Get scan from database
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return {'success': False, 'error': 'Scan not found'}
        
        # Update scan status
        scan.status = 'running'
        db.session.commit()
        
        # Build command
        kast_cli = current_app.config['KAST_CLI_PATH']
        cmd = [kast_cli, '-t', target, '-m', scan_mode, '--format', 'both']
        
        if plugins:
            cmd.extend(['--run-only', ','.join(plugins)])
        
        if parallel:
            cmd.append('-p')
        
        if verbose:
            cmd.append('-v')
        
        if dry_run:
            cmd.append('--dry-run')
        
        # Generate output directory name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = Path(current_app.config['KAST_RESULTS_DIR']) / f"{target}-{timestamp}"
        cmd.extend(['-o', str(output_dir)])
        
        current_app.logger.info(f"Executing KAST command: {' '.join(cmd)}")
        
        # Execute scan
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        # Update scan with results
        scan.output_dir = str(output_dir)
        scan.completed_at = datetime.utcnow()
        
        if result.returncode == 0:
            scan.status = 'completed'
            db.session.commit()
            
            # Parse results if available
            parse_scan_results(scan_id, output_dir)
            
            return {
                'success': True,
                'output_dir': str(output_dir),
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        else:
            scan.status = 'failed'
            scan.error_message = result.stderr or 'Scan failed with no error message'
            db.session.commit()
            
            return {
                'success': False,
                'error': result.stderr or 'Unknown error',
                'stdout': result.stdout
            }
    
    except subprocess.TimeoutExpired:
        scan.status = 'failed'
        scan.error_message = 'Scan timed out after 1 hour'
        scan.completed_at = datetime.utcnow()
        db.session.commit()
        return {'success': False, 'error': 'Scan timed out'}
    
    except Exception as e:
        current_app.logger.exception(f"Error executing scan: {str(e)}")
        scan.status = 'failed'
        scan.error_message = str(e)
        scan.completed_at = datetime.utcnow()
        db.session.commit()
        return {'success': False, 'error': str(e)}

def extract_plugin_error(plugin_data, disposition):
    """Extract error message from plugin JSON data for failed plugins."""
    if disposition != 'fail':
        return None

    error_msg = None
    for key in ('error', 'message', 'error_message'):
        if key in plugin_data:
            error_msg = str(plugin_data[key])
            break

    if error_msg is None and 'findings' in plugin_data:
        findings = plugin_data['findings']
        if isinstance(findings, dict):
            for key in ('error', 'message'):
                if key in findings:
                    error_msg = str(findings[key])
                    break

    if error_msg is None:
        for key in ('details', 'reason'):
            if key in plugin_data:
                error_msg = str(plugin_data[key])
                break

    if error_msg and len(error_msg) > 1000:
        error_msg = error_msg[:997] + '...'

    return error_msg


def parse_scan_results(scan_id, output_dir):
    """Parse *_processed.json files from output_dir and upsert into scan_results table."""
    from app import db
    from app.models import ScanResult

    try:
        output_path = Path(output_dir)
        if not output_path.exists():
            current_app.logger.warning(f"Output directory does not exist: {output_dir}")
            return

        for json_file in output_path.glob("*_processed.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)

                plugin_name = extract_plugin_name_from_file(json_file)
                disposition = data.get('disposition', 'unknown')
                findings_count = data.get('findings_count', 0)
                error_message = extract_plugin_error(data, disposition)
                file_mtime = datetime.fromtimestamp(json_file.stat().st_mtime)

                existing = ScanResult.query.filter_by(
                    scan_id=scan_id, plugin_name=plugin_name
                ).first()

                if existing:
                    existing.status = disposition
                    existing.findings_count = findings_count
                    existing.processed_output_path = str(json_file)
                    existing.executed_at = file_mtime
                    existing.error_message = error_message
                else:
                    db.session.add(ScanResult(
                        scan_id=scan_id,
                        plugin_name=plugin_name,
                        status=disposition,
                        findings_count=findings_count,
                        processed_output_path=str(json_file),
                        executed_at=file_mtime,
                        error_message=error_message,
                    ))

            except Exception as e:
                current_app.logger.error(f"Error parsing {json_file}: {e}")

        db.session.commit()

    except Exception as e:
        current_app.logger.exception(f"Error parsing scan results: {e}")

def format_duration(seconds):
    """Format duration in seconds to human-readable string"""
    if seconds is None:
        return 'N/A'
    
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


# ============================================================================
# LOGO WHITE-LABELING UTILITIES
# ============================================================================

def get_logo_max_upload_bytes():
    """Maximum accepted logo upload size, in bytes."""
    from app.logo_media import DEFAULT_MAX_UPLOAD_BYTES
    return current_app.config.get('LOGO_MAX_UPLOAD_BYTES', DEFAULT_MAX_UPLOAD_BYTES)


def get_logo_max_dimension():
    """Longest-edge cap, in pixels, applied to normalized raster logos."""
    from app.logo_media import DEFAULT_MAX_DIMENSION
    return current_app.config.get('LOGO_MAX_DIMENSION', DEFAULT_MAX_DIMENSION)


def validate_logo_file(file):
    """
    Validate uploaded logo file (name, extension and size)

    Content verification (magic bytes, decodability, SVG sanitization) happens
    in save_logo_file, which has the full file bytes.

    Args:
        file: FileStorage object from Flask request

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    from app.logo_media import extension_of, format_for_extension, format_list_text

    # Check if file was actually uploaded
    if not file or file.filename == '':
        return (False, 'No file provided')

    # Check file extension against the supported-format registry
    ext = extension_of(file.filename)
    if not ext or format_for_extension(ext) is None:
        return (False, f'Invalid file type. Supported formats: {format_list_text()}.')

    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer

    max_size = get_logo_max_upload_bytes()
    if file_size > max_size:
        return (False, f'File too large. Maximum size is {max_size // (1024 * 1024)}MB.')

    if file_size == 0:
        return (False, 'File is empty.')

    return (True, None)


def sanitize_filename(filename):
    """
    Sanitize filename to remove dangerous characters
    
    Args:
        filename: Original filename
    
    Returns:
        str: Sanitized filename
    """
    import re
    import unicodedata
    
    # Normalize unicode characters
    filename = unicodedata.normalize('NFKD', filename)
    filename = filename.encode('ascii', 'ignore').decode('ascii')
    
    # Remove any characters that aren't alphanumerics, dots, hyphens, or underscores
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Remove any leading/trailing dots or spaces
    filename = filename.strip('. ')
    
    # Limit filename length (keep extension)
    name_part, ext = os.path.splitext(filename)
    if len(name_part) > 100:
        name_part = name_part[:100]
    
    return name_part + ext


def get_logo_uploads_dir():
    """Directory holding uploaded logo originals."""
    return Path(current_app.root_path) / 'static' / 'uploads' / 'logos'


def get_logo_render_dir():
    """Directory holding the render derivative handed to the kast CLI."""
    return get_logo_uploads_dir() / 'render'


def save_logo_file(file, uploader_id):
    """
    Save an uploaded logo and its render derivative to the uploads directory

    The original is stored for provenance and re-download; the derivative is
    always a format the kast report renderer embeds correctly (PNG or sanitized
    SVG) and is what gets passed to the CLI via --logo.

    Args:
        file: FileStorage object from Flask request
        uploader_id: User ID who uploaded the file

    Returns:
        tuple: (success: bool, result: dict or error_message: str)
               result dict contains: file_path, filename, file_size, mime_type,
               render_path, render_mime, width, height, format_label
    """
    import uuid

    from app.logo_media import prepare_logo

    # Validate file (name / extension / size)
    is_valid, error = validate_logo_file(file)
    if not is_valid:
        return (False, error)

    written = []
    try:
        data = file.read()
        file.seek(0)

        # Content verification, SVG sanitization, raster normalization
        try:
            prepared = prepare_logo(
                data,
                file.filename,
                max_dimension=get_logo_max_dimension(),
            )
        except ValueError as exc:
            return (False, str(exc))

        uploads_dir = get_logo_uploads_dir()
        render_dir = get_logo_render_dir()
        uploads_dir.mkdir(parents=True, exist_ok=True)
        render_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename, forcing the extension to the stored format
        # (SVGZ is stored decompressed and sanitized, so it becomes .svg)
        original_filename = sanitize_filename(file.filename)
        stem = os.path.splitext(original_filename)[0] or 'logo'
        original_filename = f"{stem}.{prepared['original_extension']}"

        unique_id = uuid.uuid4()
        file_path = uploads_dir / f"{unique_id}-{original_filename}"
        file_path.write_bytes(prepared['original_bytes'])
        written.append(file_path)

        if prepared['render_bytes'] is prepared['original_bytes']:
            render_path = file_path
        else:
            render_path = render_dir / f"{unique_id}.{prepared['render_extension']}"
            render_path.write_bytes(prepared['render_bytes'])
            written.append(render_path)

        return (True, {
            'file_path': str(file_path),
            'filename': original_filename,
            'file_size': file_path.stat().st_size,
            'mime_type': prepared['mime'],
            'render_path': str(render_path),
            'render_mime': prepared['render_mime'],
            'width': prepared['width'],
            'height': prepared['height'],
            'format_label': prepared['label'],
        })

    except Exception as e:
        # Never leave half-written files behind
        for path in written:
            try:
                path.unlink()
            except OSError:
                pass
        current_app.logger.exception(f"Error saving logo file: {str(e)}")
        return (False, f"Error saving file: {str(e)}")


def delete_logo_file(*file_paths):
    """
    Delete logo files from the filesystem

    Args:
        *file_paths: one or more paths (the original and, when distinct, its
                     render derivative). None values are ignored.

    Returns:
        bool: True if at least one file was deleted
    """
    deleted = False
    seen = set()

    for file_path in file_paths:
        if not file_path or str(file_path) in seen:
            continue
        seen.add(str(file_path))
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                deleted = True
        except Exception as e:
            current_app.logger.exception(
                f"Error deleting logo file {file_path}: {str(e)}"
            )

    return deleted


def get_render_path_for_logo(logo):
    """
    Path to the file that should be handed to the kast CLI for a logo

    Prefers the render derivative (always PNG or sanitized SVG, both of which
    kast embeds correctly) and falls back to the original for rows predating
    the derivative columns.

    Args:
        logo: ReportLogo object

    Returns:
        str: Absolute path, or None if nothing on disk
    """
    if logo is None:
        return None

    for candidate in (getattr(logo, 'render_path', None), logo.file_path):
        if candidate and Path(candidate).exists():
            return candidate

    return None


def get_logo_for_scan(scan):
    """
    Get the logo path for a scan - either custom or system default

    Args:
        scan: Scan object

    Returns:
        str: Absolute path to logo file, or None if no logo found
    """
    from app.models import ReportLogo, SystemSettings

    # First, try scan's custom logo
    if scan.logo_id:
        logo = ReportLogo.query.get(scan.logo_id)
        render_path = get_render_path_for_logo(logo)
        if render_path:
            return render_path

    # Fall back to system default logo
    default_logo_id = SystemSettings.get_setting('default_logo_id')
    if default_logo_id:
        default_logo = ReportLogo.query.get(int(default_logo_id))
        render_path = get_render_path_for_logo(default_logo)
        if render_path:
            return render_path

    # Last resort: use hardcoded default logo
    fallback_path = Path(current_app.root_path) / 'static' / 'images' / 'kast-logo.png'
    if fallback_path.exists():
        return str(fallback_path)
    
    current_app.logger.warning(f"No logo found for scan {scan.id}")
    return None


def get_scan_logo_usage_count(logo_id):
    """
    Get the number of scans using a specific logo
    
    Args:
        logo_id: Logo ID
    
    Returns:
        int: Number of scans using this logo
    """
    from app.models import Scan
    return Scan.query.filter_by(logo_id=logo_id).count()


# ============================================================================
# PLUGIN NAME EXTRACTION
# ============================================================================

def extract_plugin_name_from_file(json_file_path):
    """
    Extract plugin name from a JSON file (processed or raw)
    
    Ensures consistent plugin name extraction across the application.
    Used by both database population and scan detail page.
    
    Args:
        json_file_path: Path object or string path to JSON file
    
    Returns:
        str: Plugin name extracted from filename
    
    Example:
        katana_processed.json -> katana
        subfinder.json -> subfinder
    """
    from pathlib import Path
    
    file_path = Path(json_file_path)
    filename = file_path.name
    
    # Remove _processed.json or .json extension
    if filename.endswith('_processed.json'):
        return filename[:-len('_processed.json')]
    elif filename.endswith('.json'):
        return filename[:-len('.json')]
    else:
        # Fallback: use stem
        return file_path.stem


# ============================================================================
# KAST RESULTS DIRECTORY MANAGEMENT
# ============================================================================

def get_kast_results_dir():
    """
    Get the absolute path to the kast_results directory based on SystemSettings
    
    Returns:
        Path: Absolute path to kast_results directory
    """
    from app.models import SystemSettings
    
    # Get configured root directory from settings
    root_dir = SystemSettings.get_setting('kast_results_root')
    
    # If not configured, use default (/opt/kast-web)
    if not root_dir:
        root_dir = '/opt/kast-web'
        current_app.logger.info(f"No kast_results_root configured, using default: {root_dir}")
    
    # Build full path to kast_results directory
    results_dir = Path(root_dir).resolve() / 'kast_results'
    
    # Ensure directory exists
    try:
        results_dir.mkdir(parents=True, exist_ok=True)
        current_app.logger.debug(f"Using kast_results directory: {results_dir}")
    except Exception as e:
        current_app.logger.error(f"Failed to create kast_results directory {results_dir}: {e}")
    
    return results_dir


def verify_kast_results_permissions(root_path):
    """
    Verify that the Flask app can create and write to kast_results directory
    
    Args:
        root_path: Root directory path (string) where kast_results will be created
    
    Returns:
        tuple: (success: bool, message: str)
    """
    import tempfile
    import pwd
    
    try:
        # Validate path is absolute
        if not os.path.isabs(root_path):
            return (False, "Path must be absolute (e.g., /opt/kast-web, not ./kast-web)")
        
        # Resolve path
        root = Path(root_path).resolve()
        results_dir = root / 'kast_results'
        
        # Check if root directory exists
        if not root.exists():
            return (False, f"Root directory '{root}' does not exist")
        
        # Try to create kast_results directory if it doesn't exist
        try:
            results_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Get current user for helpful error message
            try:
                current_username = pwd.getpwuid(os.getuid()).pw_name
            except:
                current_username = 'www-data'
            
            return (False, f"Permission denied: Cannot create directory '{results_dir}'. "
                          f"Flask runs as user '{current_username}'. "
                          f"Please run: sudo chown -R {current_username}:{current_username} {root_path}")
        except Exception as e:
            return (False, f"Cannot create directory '{results_dir}': {str(e)}")
        
        # Test write permissions by creating a temporary file
        try:
            with tempfile.NamedTemporaryFile(dir=results_dir, delete=True, mode='w') as f:
                f.write('test')
                f.flush()
            
            return (True, f"✓ Permissions verified: {results_dir} is writable")
        
        except PermissionError:
            # Get current user for helpful error message
            try:
                current_username = pwd.getpwuid(os.getuid()).pw_name
            except:
                current_username = 'www-data'
            
            return (False, f"Permission denied: Directory '{results_dir}' exists but is not writable. "
                          f"Flask runs as user '{current_username}'. "
                          f"Please run: sudo chown -R {current_username}:{current_username} {results_dir}")
        
        except Exception as e:
            return (False, f"Cannot write to directory '{results_dir}': {str(e)}")
    
    except Exception as e:
        current_app.logger.exception(f"Error verifying permissions for {root_path}: {str(e)}")
        return (False, f"Error checking permissions: {str(e)}")


# ============================================================================
# AUTHORIZATION DECORATORS
# ============================================================================

def admin_required(f):
    """
    Decorator to require admin role for a route
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin:
            flash('You do not have permission to access this page. Admin role required.', 'danger')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def power_user_required(f):
    """
    Decorator to require power_user or admin role for a route
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not (current_user.is_power_user or current_user.is_admin):
            flash('You do not have permission to access this page. Power user or admin role required.', 'danger')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function
