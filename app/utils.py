import subprocess
import json
import os
from pathlib import Path
from datetime import datetime
from flask import current_app

def get_available_plugins():
    """
    Get list of available KAST plugins by calling kast --list-plugins
    Returns list of tuples: [(plugin_name, description), ...]
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
        
        # Parse the output to extract plugin names
        # The output format from kast is:
        # ✓ plugin_name (priority: X, type: passive/active)
        #   Description
        plugins = []
        lines = result.stdout.strip().split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('✓') or line.startswith('✗'):
                # Extract plugin name from line like: "✓ subfinder (priority: 1, type: passive)"
                parts = line.split('(')[0].strip()
                plugin_name = parts.split()[-1]  # Get the last word (plugin name)
                
                # Get description from next line if available
                description = ''
                if i + 1 < len(lines) and not lines[i + 1].strip().startswith(('✓', '✗', 'Available')):
                    description = lines[i + 1].strip()
                
                plugins.append((plugin_name, f"{plugin_name} - {description}" if description else plugin_name))
            i += 1
        
        return plugins
    except Exception as e:
        current_app.logger.error(f"Error getting plugins: {str(e)}")
        return []

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

def parse_scan_results(scan_id, output_dir):
    """
    Parse scan results from output directory and store in database
    
    Args:
        scan_id: Database scan ID
        output_dir: Path to scan output directory
    """
    from app import db
    from app.models import ScanResult
    
    try:
        output_path = Path(output_dir)
        if not output_path.exists():
            current_app.logger.warning(f"Output directory does not exist: {output_dir}")
            return
        
        # Look for processed JSON files
        for json_file in output_path.glob("*_processed.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                plugin_name = data.get('plugin_name', json_file.stem.replace('_processed', ''))
                
                # Count findings correctly - look at results array within findings
                findings_data = data.get('findings', {})
                if isinstance(findings_data, dict):
                    # findings is a dict with a 'results' key containing the actual findings
                    findings_count = len(findings_data.get('results', []))
                else:
                    # fallback: findings is a list
                    findings_count = len(findings_data) if isinstance(findings_data, list) else 0
                
                # Get file modification time as executed_at
                file_mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                
                # Check if result already exists
                existing_result = ScanResult.query.filter_by(
                    scan_id=scan_id,
                    plugin_name=plugin_name
                ).first()
                
                if existing_result:
                    # Update existing result
                    existing_result.status = data.get('disposition', 'unknown')
                    existing_result.findings_count = findings_count
                    existing_result.processed_output_path = str(json_file)
                    existing_result.executed_at = file_mtime
                else:
                    # Create new scan result entry
                    result = ScanResult(
                        scan_id=scan_id,
                        plugin_name=plugin_name,
                        status=data.get('disposition', 'unknown'),
                        findings_count=findings_count,
                        processed_output_path=str(json_file),
                        executed_at=file_mtime
                    )
                    db.session.add(result)
            
            except Exception as e:
                current_app.logger.error(f"Error parsing {json_file}: {str(e)}")
        
        db.session.commit()
    
    except Exception as e:
        current_app.logger.exception(f"Error parsing scan results: {str(e)}")

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

def validate_logo_file(file):
    """
    Validate uploaded logo file
    
    Args:
        file: FileStorage object from Flask request
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    # Check if file was actually uploaded
    if not file or file.filename == '':
        return (False, 'No file provided')
    
    # Check file extension
    allowed_extensions = {'png', 'jpg', 'jpeg'}
    filename = file.filename.lower()
    if '.' not in filename or filename.rsplit('.', 1)[1] not in allowed_extensions:
        return (False, 'Invalid file type. Only PNG, JPG, and JPEG files are allowed.')
    
    # Check file size (max 2MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    max_size = 2 * 1024 * 1024  # 2MB
    if file_size > max_size:
        return (False, f'File too large. Maximum size is {max_size / (1024 * 1024)}MB.')
    
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


def save_logo_file(file, uploader_id):
    """
    Save uploaded logo file to the uploads directory
    
    Args:
        file: FileStorage object from Flask request
        uploader_id: User ID who uploaded the file
    
    Returns:
        tuple: (success: bool, result: dict or error_message: str)
               result dict contains: {'file_path': str, 'filename': str, 'file_size': int, 'mime_type': str}
    """
    import uuid
    
    # Validate file
    is_valid, error = validate_logo_file(file)
    if not is_valid:
        return (False, error)
    
    try:
        # Get uploads directory
        uploads_dir = Path(current_app.root_path) / 'static' / 'uploads' / 'logos'
        uploads_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        original_filename = sanitize_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}-{original_filename}"
        file_path = uploads_dir / unique_filename
        
        # Save file
        file.save(str(file_path))
        
        # Get file info
        file_size = file_path.stat().st_size
        
        # Determine MIME type from extension
        ext = original_filename.rsplit('.', 1)[1].lower()
        mime_type = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg'
        }.get(ext, 'image/png')
        
        return (True, {
            'file_path': str(file_path),
            'filename': original_filename,
            'file_size': file_size,
            'mime_type': mime_type
        })
    
    except Exception as e:
        current_app.logger.exception(f"Error saving logo file: {str(e)}")
        return (False, f"Error saving file: {str(e)}")


def delete_logo_file(file_path):
    """
    Delete logo file from filesystem
    
    Args:
        file_path: Path to logo file
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False
    except Exception as e:
        current_app.logger.exception(f"Error deleting logo file {file_path}: {str(e)}")
        return False


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
        if logo and Path(logo.file_path).exists():
            return logo.file_path
    
    # Fall back to system default logo
    default_logo_id = SystemSettings.get_setting('default_logo_id')
    if default_logo_id:
        default_logo = ReportLogo.query.get(int(default_logo_id))
        if default_logo and Path(default_logo.file_path).exists():
            return default_logo.file_path
    
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
