from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, abort
from flask_login import login_required, current_user
from app import db
from app.models import Scan, ScanResult
from app.utils import format_duration
from pathlib import Path
import os
import shutil

bp = Blueprint('scans', __name__, url_prefix='/scans')


def check_scan_access(scan):
    """Check if current user can access this scan"""
    if current_user.is_admin:
        return True
    return scan.user_id == current_user.id


@bp.route('/')
@login_required
def list():
    """List scans with pagination (filtered by user unless admin)"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get filter parameters
    status_filter = request.args.get('status', '')
    target_filter = request.args.get('target', '')
    
    # Build query - filter by user unless admin
    if current_user.is_admin:
        query = Scan.query
    else:
        query = Scan.query.filter_by(user_id=current_user.id)
    
    if status_filter:
        query = query.filter(Scan.status == status_filter)
    
    if target_filter:
        query = query.filter(Scan.target.contains(target_filter))
    
    # Order by most recent first
    query = query.order_by(Scan.started_at.desc())
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    scans = pagination.items
    
    return render_template(
        'scan_history.html',
        scans=scans,
        pagination=pagination,
        status_filter=status_filter,
        target_filter=target_filter,
        format_duration=format_duration
    )

@bp.route('/<int:scan_id>')
@login_required
def detail(scan_id):
    """View scan details"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Check access permission
    if not check_scan_access(scan):
        flash('You do not have permission to view this scan', 'danger')
        return redirect(url_for('scans.list'))
    
    # Get scan results from database
    db_results = {result.plugin_name: result for result in scan.results.all()}
    
    # Build plugin status list based on file existence
    plugin_statuses = []
    output_dir = Path(scan.output_dir) if scan.output_dir else None
    
    # Determine which plugins to check
    if scan.plugins:
        # Specific plugins were selected
        plugin_list = scan.plugin_list
    elif output_dir and output_dir.exists():
        # No specific plugins - scan all files in output directory
        # Only look for files matching the pattern: plugin.json or plugin_processed.json
        plugin_set = set()
        for json_file in output_dir.glob("*.json"):
            filename = json_file.name
            # Skip non-plugin files
            if filename == 'kast_report.json':
                continue
            # Only consider files ending with .json or _processed.json
            if filename.endswith('_processed.json'):
                plugin_name = filename[:-len('_processed.json')]
            elif filename.endswith('.json') and not '_' in filename[:-5]:
                # Only accept simple plugin.json files (no underscores before .json)
                plugin_name = filename[:-len('.json')]
            else:
                # Skip files with other patterns (like subfinder_tmp.json)
                continue
            plugin_set.add(plugin_name)
        plugin_list = sorted(plugin_set)
    else:
        # No plugins specified and no output directory yet
        plugin_list = []
    
    # Check status for each plugin
    for plugin in plugin_list:
        plugin_data = {
            'plugin_name': plugin,
            'status': 'pending',
            'findings_count': 0,
            'executed_at': None
        }
        
        # Check file existence to determine status
        if output_dir and output_dir.exists():
            processed_file = output_dir / f"{plugin}_processed.json"
            raw_file = output_dir / f"{plugin}.json"
            
            if processed_file.exists():
                # Plugin completed
                plugin_data['status'] = 'completed'
                # Get data from database if available
                if plugin in db_results:
                    plugin_data['findings_count'] = db_results[plugin].findings_count
                    plugin_data['executed_at'] = db_results[plugin].executed_at
            elif raw_file.exists():
                # Plugin in progress
                plugin_data['status'] = 'in_progress'
            # else: status remains 'pending'
        
        plugin_statuses.append(plugin_data)
    
    # Check if HTML report exists
    report_path = None
    if scan.output_dir:
        potential_report = Path(scan.output_dir) / 'kast_report.html'
        if potential_report.exists():
            report_path = str(potential_report)
    
    return render_template(
        'scan_detail.html',
        scan=scan,
        results=plugin_statuses,
        report_path=report_path,
        format_duration=format_duration
    )

@bp.route('/<int:scan_id>/delete', methods=['POST'])
@login_required
def delete(scan_id):
    """Delete a scan (owner or admin only)"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Check permission to delete
    if not check_scan_access(scan):
        flash('You do not have permission to delete this scan', 'danger')
        return redirect(url_for('scans.list'))
    
    target = scan.target
    output_dir = scan.output_dir
    
    # Delete from database (cascade will delete results)
    db.session.delete(scan)
    db.session.commit()
    
    # Delete output directory from disk if it exists
    if output_dir:
        output_path = Path(output_dir)
        if output_path.exists() and output_path.is_dir():
            try:
                shutil.rmtree(output_path)
                flash(f'Scan for {target} and its output directory deleted successfully', 'success')
            except Exception as e:
                flash(f'Scan for {target} deleted from database, but failed to delete output directory: {str(e)}', 'warning')
        else:
            flash(f'Scan for {target} deleted successfully', 'success')
    else:
        flash(f'Scan for {target} deleted successfully', 'success')
    
    return redirect(url_for('scans.list'))

@bp.route('/<int:scan_id>/report')
@login_required
def view_report(scan_id):
    """View HTML report"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Check access permission
    if not check_scan_access(scan):
        flash('You do not have permission to view this report', 'danger')
        return redirect(url_for('scans.list'))
    
    if not scan.output_dir:
        flash('No output directory found for this scan', 'warning')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    report_path = Path(scan.output_dir) / 'kast_report.html'
    
    if not report_path.exists():
        flash('Report file not found', 'warning')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    # Read and display report
    with open(report_path, 'r') as f:
        report_html = f.read()
    
    # Fix relative paths in the HTML to work with Flask routes
    # Replace asset paths to use Flask's static folder
    import re
    
    # Map of asset filenames to their location in Flask's static folder
    # For now, we're primarily handling the logo
    def replace_asset_path(match):
        attr = match.group(1)  # 'src' or 'href'
        filename = match.group(2)  # e.g., 'kast-logo.png'
        
        # Map known assets to Flask static paths
        if 'logo' in filename.lower() and filename.endswith('.png'):
            return f'{attr}="{url_for("static", filename="images/kast-logo.png")}"'
        
        # For other assets, try to serve from scan directory first
        return f'{attr}="{url_for("scans.serve_scan_file", scan_id=scan_id, filename="assets/" + filename)}"'
    
    # Pattern to match src="../assets/..." or href="../assets/..."
    report_html = re.sub(r'(src|href)=["\']\.\.\/assets\/([^"\']+)["\']', replace_asset_path, report_html)
    
    # Also handle src="./assets/..." or href="./assets/..."
    report_html = re.sub(r'(src|href)=["\']\.\/assets\/([^"\']+)["\']', replace_asset_path, report_html)
    
    # Also handle src="assets/..." or href="assets/..." (no relative prefix)
    report_html = re.sub(r'(src|href)=["\']assets\/([^"\']+)["\']', replace_asset_path, report_html)
    
    return render_template('report_viewer.html', scan=scan, report_html=report_html)

@bp.route('/<int:scan_id>/download')
@login_required
def download_report(scan_id):
    """Download HTML report"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        abort(404)
    
    # Check access permission
    if not check_scan_access(scan):
        abort(403)
    
    if not scan.output_dir:
        abort(404)
    
    report_path = Path(scan.output_dir) / 'kast_report.html'
    
    if not report_path.exists():
        abort(404)
    
    return send_file(
        report_path,
        as_attachment=True,
        download_name=f'kast_report_{scan.target}_{scan.id}.html'
    )

@bp.route('/<int:scan_id>/<path:filename>')
@login_required
def serve_scan_file(scan_id, filename):
    """Serve static files from scan output directory (e.g., kast_style.css)"""
    scan = db.session.get(Scan, scan_id)
    if not scan or not scan.output_dir:
        abort(404)
    
    # Check access permission
    if not check_scan_access(scan):
        abort(403)
    
    # Security: only allow specific file types
    allowed_extensions = {'.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg'}
    file_path = Path(scan.output_dir) / filename
    
    # Check file extension
    if file_path.suffix.lower() not in allowed_extensions:
        abort(403)
    
    # Prevent directory traversal
    try:
        file_path = file_path.resolve()
        output_dir = Path(scan.output_dir).resolve()
        if not str(file_path).startswith(str(output_dir)):
            abort(403)
    except Exception:
        abort(403)
    
    if not file_path.exists() or not file_path.is_file():
        abort(404)
    
    return send_file(file_path)

@bp.route('/<int:scan_id>/files')
@login_required
def list_files(scan_id):
    """Display directory listing of scan output files"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Check access permission
    if not check_scan_access(scan):
        flash('You do not have permission to view this scan\'s files', 'danger')
        return redirect(url_for('scans.list'))
    
    if not scan.output_dir:
        flash('No output directory found for this scan', 'warning')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    output_path = Path(scan.output_dir)
    
    if not output_path.exists():
        flash('Output directory does not exist', 'warning')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    # Collect all files and directories
    files = []
    directories = []
    
    try:
        for item in sorted(output_path.iterdir()):
            item_stat = item.stat()
            item_info = {
                'name': item.name,
                'size': item_stat.st_size if item.is_file() else 0,
                'modified': item_stat.st_mtime,
                'is_dir': item.is_dir()
            }
            
            if item.is_dir():
                directories.append(item_info)
            else:
                files.append(item_info)
    except Exception as e:
        flash(f'Error reading directory: {str(e)}', 'danger')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    return render_template(
        'scan_files.html',
        scan=scan,
        files=files,
        directories=directories,
        output_dir=scan.output_dir
    )

@bp.route('/<int:scan_id>/view-file/<path:filename>')
@login_required
def view_file(scan_id, filename):
    """View a file from the scan output directory"""
    scan = db.session.get(Scan, scan_id)
    if not scan or not scan.output_dir:
        abort(404)
    
    # Check access permission
    if not check_scan_access(scan):
        abort(403)
    
    file_path = Path(scan.output_dir) / filename
    
    # Prevent directory traversal
    try:
        file_path = file_path.resolve()
        output_dir = Path(scan.output_dir).resolve()
        if not str(file_path).startswith(str(output_dir)):
            abort(403)
    except Exception:
        abort(403)
    
    if not file_path.exists() or not file_path.is_file():
        abort(404)
    
    # Determine MIME type based on file extension
    mime_type = None
    extension = file_path.suffix.lower()
    
    if extension == '.json':
        mime_type = 'application/json'
    elif extension == '.html':
        mime_type = 'text/html'
    elif extension == '.txt':
        mime_type = 'text/plain'
    elif extension == '.css':
        mime_type = 'text/css'
    elif extension == '.js':
        mime_type = 'application/javascript'
    elif extension == '.xml':
        mime_type = 'application/xml'
    elif extension in ['.jpg', '.jpeg']:
        mime_type = 'image/jpeg'
    elif extension == '.png':
        mime_type = 'image/png'
    elif extension == '.gif':
        mime_type = 'image/gif'
    elif extension == '.svg':
        mime_type = 'image/svg+xml'
    else:
        # Default to plain text for unknown types
        mime_type = 'text/plain'
    
    return send_file(file_path, mimetype=mime_type)

@bp.route('/<int:scan_id>/regenerate-report', methods=['POST'])
@login_required
def regenerate_report(scan_id):
    """Regenerate the HTML report for a completed scan"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Check access permission
    if not check_scan_access(scan):
        flash('You do not have permission to regenerate this report', 'danger')
        return redirect(url_for('scans.list'))
    
    if not scan.output_dir:
        flash('No output directory found for this scan', 'warning')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    # Check if output directory exists
    output_path = Path(scan.output_dir)
    if not output_path.exists():
        flash('Output directory does not exist', 'warning')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    # Call the regenerate report task
    from app.tasks import regenerate_report_task
    try:
        task = regenerate_report_task.delay(scan_id)
        flash(f'Report regeneration started for {scan.target}', 'info')
    except Exception as e:
        flash(f'Error starting report regeneration: {str(e)}', 'danger')
    
    return redirect(url_for('scans.detail', scan_id=scan_id))

@bp.route('/<int:scan_id>/rerun', methods=['POST'])
@login_required
def rerun(scan_id):
    """Re-run a scan with the same configuration"""
    original_scan = db.session.get(Scan, scan_id)
    if not original_scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Check access permission
    if not check_scan_access(original_scan):
        flash('You do not have permission to re-run this scan', 'danger')
        return redirect(url_for('scans.list'))
    
    # Create new scan with same configuration (assigned to current user)
    new_scan = Scan(
        user_id=current_user.id,
        target=original_scan.target,
        scan_mode=original_scan.scan_mode,
        plugins=original_scan.plugins,
        parallel=original_scan.parallel,
        verbose=original_scan.verbose,
        dry_run=original_scan.dry_run,
        status='pending',
        config_json=original_scan.config_json
    )
    
    db.session.add(new_scan)
    db.session.commit()
    
    flash(f'Re-running scan for {new_scan.target}', 'info')
    
    # Execute scan
    from app.utils import execute_kast_scan
    try:
        result = execute_kast_scan(
            new_scan.id,
            new_scan.target,
            new_scan.scan_mode,
            plugins=new_scan.plugin_list if new_scan.plugins else None,
            parallel=new_scan.parallel,
            verbose=new_scan.verbose,
            dry_run=new_scan.dry_run
        )
        
        if result['success']:
            flash(f'Scan completed successfully', 'success')
        else:
            flash(f'Scan failed: {result.get("error", "Unknown error")}', 'danger')
    
    except Exception as e:
        flash(f'Error executing scan: {str(e)}', 'danger')
    
    return redirect(url_for('scans.detail', scan_id=new_scan.id))
