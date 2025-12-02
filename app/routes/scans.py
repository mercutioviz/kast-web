from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, abort, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Scan, ScanResult, ScanShare, User, AuditLog
from app.forms import ShareWithUserForm, GeneratePublicLinkForm, TransferOwnershipForm
from app.utils import format_duration
from pathlib import Path
from datetime import datetime, timedelta
import os
import shutil

bp = Blueprint('scans', __name__, url_prefix='/scans')


def check_scan_access(scan, required_permission='view'):
    """
    Check if current user can access this scan
    
    Args:
        scan: Scan object
        required_permission: 'view' or 'edit'
    
    Returns:
        tuple: (has_access: bool, permission_level: str or None)
    """
    # Admin always has full access
    if current_user.is_authenticated and current_user.is_admin:
        return (True, 'edit')
    
    # Owner always has full access
    if current_user.is_authenticated and scan.user_id == current_user.id:
        return (True, 'edit')
    
    # Check if shared with current user
    if current_user.is_authenticated:
        share = ScanShare.query.filter_by(
            scan_id=scan.id,
            shared_with_user_id=current_user.id
        ).first()
        
        if share and not share.is_expired():
            # Check if user has required permission level
            if required_permission == 'view':
                return (True, share.permission_level)
            elif required_permission == 'edit' and share.permission_level == 'edit':
                return (True, 'edit')
            else:
                return (False, None)
    
    return (False, None)


def check_scan_access_simple(scan):
    """Simple access check for backward compatibility (returns bool)"""
    has_access, _ = check_scan_access(scan, 'view')
    return has_access


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
    if not check_scan_access_simple(scan):
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
    
    # Get plugin types to filter based on scan mode
    from app.utils import get_available_plugins
    all_plugins = get_available_plugins()
    plugin_types = {name: ptype for name, _, ptype in all_plugins}
    
    # Check status for each plugin
    for plugin in plugin_list:
        # Filter based on scan mode
        plugin_type = plugin_types.get(plugin, 'passive')  # Default to passive if unknown
        
        # Skip active plugins if this is a passive scan
        if scan.scan_mode == 'passive' and plugin_type == 'active':
            continue
        
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
    
    # Check permission to delete (need edit permission)
    has_access, permission = check_scan_access(scan, 'edit')
    if not has_access:
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
    if not check_scan_access_simple(scan):
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
    """Download report (PDF or HTML)"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        abort(404)
    
    # Check access permission
    if not check_scan_access_simple(scan):
        abort(403)
    
    if not scan.output_dir:
        abort(404)
    
    # Get format parameter (default to PDF)
    report_format = request.args.get('format', 'pdf').lower()
    
    # Determine file path and download name based on format
    if report_format == 'pdf':
        report_path = Path(scan.output_dir) / 'kast_report.pdf'
        download_name = f'kast_report_{scan.target}_{scan.id}.pdf'
    elif report_format == 'html':
        report_path = Path(scan.output_dir) / 'kast_report.html'
        download_name = f'kast_report_{scan.target}_{scan.id}.html'
    else:
        # Invalid format
        flash('Invalid report format requested', 'danger')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    if not report_path.exists():
        flash(f'{report_format.upper()} report not found. Please ensure the scan has completed and generated the report.', 'warning')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    return send_file(
        report_path,
        as_attachment=True,
        download_name=download_name
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
    if not check_scan_access_simple(scan):
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
    
    # Check access permission (need edit permission)
    has_access, permission = check_scan_access(scan, 'edit')
    if not has_access:
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
    
    # Check access permission (need edit permission)
    has_access, permission = check_scan_access(original_scan, 'edit')
    if not has_access:
        flash('You do not have permission to re-run this scan', 'danger')
        return redirect(url_for('scans.list'))
    
    # Check if user is allowed to run active scans if the original was active
    if original_scan.scan_mode == 'active' and not current_user.can_run_active_scans:
        flash('You do not have permission to run active scans. Only Power Users and Admins can run active scans.', 'danger')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
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


# ============================================================================
# PHASE 4: SHARING & COLLABORATION ROUTES
# ============================================================================

@bp.route('/<int:scan_id>/share/user', methods=['POST'])
@login_required
def share_with_user(scan_id):
    """Share scan with specific user"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Only owner or admin can share
    has_access, permission = check_scan_access(scan, 'edit')
    if not has_access:
        flash('You do not have permission to share this scan', 'danger')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    form = ShareWithUserForm()
    # Populate user choices (exclude owner and current shares)
    active_users = User.query.filter(
        User.id != scan.user_id,
        User.is_active == True
    ).all()
    form.user_id.choices = [(u.id, f"{u.username} ({u.email})") for u in active_users]
    
    if form.validate_on_submit():
        # Check if already shared
        existing = ScanShare.query.filter_by(
            scan_id=scan_id,
            shared_with_user_id=form.user_id.data
        ).first()
        
        if existing:
            # Update existing share
            existing.permission_level = form.permission_level.data
            if form.expires_in_days.data > 0:
                existing.expires_at = datetime.utcnow() + timedelta(days=form.expires_in_days.data)
            else:
                existing.expires_at = None
            db.session.commit()
            flash('Share updated successfully', 'success')
        else:
            # Calculate expiration
            expires_at = None
            if form.expires_in_days.data > 0:
                expires_at = datetime.utcnow() + timedelta(days=form.expires_in_days.data)
            
            # Create share
            share = ScanShare(
                scan_id=scan_id,
                shared_with_user_id=form.user_id.data,
                permission_level=form.permission_level.data,
                created_by=current_user.id,
                expires_at=expires_at
            )
            db.session.add(share)
            db.session.commit()
            
            # Log the action
            shared_user = db.session.get(User, form.user_id.data)
            AuditLog.log(
                user_id=current_user.id,
                action='share_scan',
                resource_type='scan',
                resource_id=scan_id,
                details=f'Shared with user {shared_user.username} ({form.permission_level.data})'
            )
            
            flash(f'Scan shared successfully with {shared_user.username}', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')
    
    return redirect(url_for('scans.detail', scan_id=scan_id))


@bp.route('/<int:scan_id>/share/public', methods=['POST'])
@login_required
def generate_public_link(scan_id):
    """Generate public sharing link"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Only owner or admin can create public links
    has_access, permission = check_scan_access(scan, 'edit')
    if not has_access:
        flash('You do not have permission to create public links for this scan', 'danger')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    form = GeneratePublicLinkForm()
    
    if form.validate_on_submit():
        # Check if public link already exists
        existing = ScanShare.query.filter_by(
            scan_id=scan_id,
            shared_with_user_id=None  # Public share
        ).first()
        
        if existing and not existing.is_expired():
            flash('A public link already exists for this scan', 'warning')
        else:
            # Calculate expiration
            expires_at = datetime.utcnow() + timedelta(days=form.expires_in_days.data)
            
            # Generate unique token
            token = ScanShare.generate_token()
            
            # Create public share
            share = ScanShare(
                scan_id=scan_id,
                shared_with_user_id=None,  # Public share
                permission_level='view',  # Public links are view-only
                share_token=token,
                created_by=current_user.id,
                expires_at=expires_at
            )
            db.session.add(share)
            db.session.commit()
            
            # Log the action
            AuditLog.log(
                user_id=current_user.id,
                action='create_public_link',
                resource_type='scan',
                resource_id=scan_id,
                details=f'Created public link (expires in {form.expires_in_days.data} days)'
            )
            
            flash('Public link generated successfully', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')
    
    return redirect(url_for('scans.detail', scan_id=scan_id))


@bp.route('/<int:scan_id>/share/<int:share_id>/revoke', methods=['POST'])
@login_required
def revoke_share(scan_id, share_id):
    """Revoke a share"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Only owner or admin can revoke shares
    has_access, permission = check_scan_access(scan, 'edit')
    if not has_access:
        flash('You do not have permission to revoke shares for this scan', 'danger')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    share = db.session.get(ScanShare, share_id)
    if not share or share.scan_id != scan_id:
        flash('Share not found', 'danger')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    # Log the action before deletion
    if share.is_public():
        details = 'Revoked public link'
    else:
        shared_user = share.shared_with_user
        details = f'Revoked share with user {shared_user.username if shared_user else "Unknown"}'
    
    AuditLog.log(
        user_id=current_user.id,
        action='revoke_share',
        resource_type='scan',
        resource_id=scan_id,
        details=details
    )
    
    # Delete the share
    db.session.delete(share)
    db.session.commit()
    
    flash('Share revoked successfully', 'success')
    return redirect(url_for('scans.detail', scan_id=scan_id))


@bp.route('/<int:scan_id>/shares')
@login_required
def list_shares(scan_id):
    """List all shares for a scan (API endpoint)"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    
    # Only owner or admin can list shares
    has_access, permission = check_scan_access(scan, 'edit')
    if not has_access:
        return jsonify({'error': 'Permission denied'}), 403
    
    shares = ScanShare.query.filter_by(scan_id=scan_id).all()
    
    return jsonify({
        'shares': [share.to_dict() for share in shares]
    })


@bp.route('/<int:scan_id>/transfer', methods=['POST'])
@login_required
def transfer_ownership(scan_id):
    """Transfer scan ownership to another user"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Only owner or admin can transfer ownership
    if not current_user.is_admin and scan.user_id != current_user.id:
        flash('You do not have permission to transfer ownership of this scan', 'danger')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    form = TransferOwnershipForm()
    # Populate user choices (exclude current owner)
    active_users = User.query.filter(
        User.id != scan.user_id,
        User.is_active == True
    ).all()
    form.new_owner_id.choices = [(u.id, f"{u.username} ({u.email})") for u in active_users]
    
    if form.validate_on_submit():
        old_owner_id = scan.user_id
        old_owner = db.session.get(User, old_owner_id)
        new_owner = db.session.get(User, form.new_owner_id.data)
        
        # Transfer ownership
        scan.user_id = form.new_owner_id.data
        db.session.commit()
        
        # Log the action
        AuditLog.log(
            user_id=current_user.id,
            action='transfer_ownership',
            resource_type='scan',
            resource_id=scan_id,
            details=f'Transferred from {old_owner.username if old_owner else "Unknown"} to {new_owner.username}'
        )
        
        flash(f'Scan ownership transferred to {new_owner.username}', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')
    
    return redirect(url_for('scans.detail', scan_id=scan_id))
