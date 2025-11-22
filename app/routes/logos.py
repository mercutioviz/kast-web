"""
Logo Management Routes for White-Labeling Feature
Allows users to upload, view, and manage report logos
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, abort, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import ReportLogo, SystemSettings, AuditLog
from app.utils import save_logo_file, delete_logo_file, get_scan_logo_usage_count
from pathlib import Path

bp = Blueprint('logos', __name__, url_prefix='/logos')


@bp.route('/manage')
@login_required
def manage():
    """Logo management page - list all logos"""
    # Get all logos ordered by upload date (newest first)
    logos = ReportLogo.query.order_by(ReportLogo.uploaded_at.desc()).all()
    
    # Get default logo ID
    default_logo_id = SystemSettings.get_setting('default_logo_id')
    
    # Add usage count to each logo
    logo_data = []
    for logo in logos:
        usage_count = get_scan_logo_usage_count(logo.id)
        logo_dict = logo.to_dict()
        logo_dict['usage_count'] = usage_count
        logo_dict['is_default'] = (logo.id == int(default_logo_id)) if default_logo_id else False
        logo_dict['can_delete'] = current_user.is_admin or logo.uploaded_by == current_user.id
        logo_data.append(logo_dict)
    
    return render_template('logos/manage.html', logos=logo_data)


@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    """Upload a new logo"""
    # Check if file was uploaded
    if 'logo_file' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('logos.manage'))
    
    file = request.files['logo_file']
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    
    if not name:
        flash('Logo name is required', 'danger')
        return redirect(url_for('logos.manage'))
    
    # Save file
    success, result = save_logo_file(file, current_user.id)
    
    if not success:
        flash(f'Failed to upload logo: {result}', 'danger')
        return redirect(url_for('logos.manage'))
    
    # Create database entry
    logo = ReportLogo(
        name=name,
        description=description,
        filename=result['filename'],
        file_path=result['file_path'],
        mime_type=result['mime_type'],
        file_size=result['file_size'],
        uploaded_by=current_user.id
    )
    db.session.add(logo)
    db.session.commit()
    
    # Log the action
    AuditLog.log(
        user_id=current_user.id,
        action='logo_uploaded',
        resource_type='logo',
        resource_id=logo.id,
        details=f'Uploaded logo: {name}'
    )
    
    flash(f'Logo "{name}" uploaded successfully', 'success')
    return redirect(url_for('logos.manage'))


@bp.route('/<int:logo_id>')
@login_required
def view(logo_id):
    """View/download a logo file"""
    logo = db.session.get(ReportLogo, logo_id)
    if not logo:
        abort(404)
    
    file_path = Path(logo.file_path)
    if not file_path.exists():
        abort(404)
    
    return send_file(file_path, mimetype=logo.mime_type)


@bp.route('/<int:logo_id>/delete', methods=['POST'])
@login_required
def delete(logo_id):
    """Delete a logo"""
    logo = db.session.get(ReportLogo, logo_id)
    if not logo:
        flash('Logo not found', 'danger')
        return redirect(url_for('logos.manage'))
    
    # Check permission: admin can delete any, users can only delete their own
    if not current_user.is_admin and logo.uploaded_by != current_user.id:
        flash('You do not have permission to delete this logo', 'danger')
        return redirect(url_for('logos.manage'))
    
    # Check if it's the system default
    default_logo_id = SystemSettings.get_setting('default_logo_id')
    if default_logo_id and logo.id == int(default_logo_id):
        flash('Cannot delete the system default logo. Please set a different default first.', 'warning')
        return redirect(url_for('logos.manage'))
    
    # Check if any scans are using this logo
    usage_count = get_scan_logo_usage_count(logo.id)
    if usage_count > 0:
        flash(f'Cannot delete logo. It is currently used by {usage_count} scan(s). Those scans will use the system default if you delete this logo.', 'warning')
        # Allow deletion but warn user - scans will fall back to default
    
    logo_name = logo.name
    file_path = logo.file_path
    
    # Delete from database first
    db.session.delete(logo)
    db.session.commit()
    
    # Then delete file from filesystem
    delete_logo_file(file_path)
    
    # Log the action
    AuditLog.log(
        user_id=current_user.id,
        action='logo_deleted',
        resource_type='logo',
        resource_id=logo_id,
        details=f'Deleted logo: {logo_name}'
    )
    
    flash(f'Logo "{logo_name}" deleted successfully', 'success')
    return redirect(url_for('logos.manage'))


@bp.route('/<int:logo_id>/set-default', methods=['POST'])
@login_required
def set_default(logo_id):
    """Set a logo as the system default (admin only)"""
    if not current_user.is_admin:
        flash('Only administrators can set the default logo', 'danger')
        return redirect(url_for('logos.manage'))
    
    logo = db.session.get(ReportLogo, logo_id)
    if not logo:
        flash('Logo not found', 'danger')
        return redirect(url_for('logos.manage'))
    
    # Update system setting
    SystemSettings.set_setting(
        key='default_logo_id',
        value=str(logo_id),
        value_type='int',
        description='Default logo for reports',
        user_id=current_user.id
    )
    
    # Log the action
    AuditLog.log(
        user_id=current_user.id,
        action='default_logo_changed',
        resource_type='system',
        details=f'Set default logo to: {logo.name} (ID: {logo_id})'
    )
    
    flash(f'"{logo.name}" is now the system default logo', 'success')
    return redirect(url_for('logos.manage'))


@bp.route('/api/list')
@login_required
def api_list():
    """API endpoint to list all logos (for AJAX/dropdowns)"""
    logos = ReportLogo.query.order_by(ReportLogo.name).all()
    default_logo_id = SystemSettings.get_setting('default_logo_id')
    
    logo_list = []
    for logo in logos:
        logo_dict = {
            'id': logo.id,
            'name': logo.name,
            'description': logo.description,
            'uploaded_by': logo.uploader.username if logo.uploader else 'Unknown',
            'is_default': (logo.id == int(default_logo_id)) if default_logo_id else False
        }
        logo_list.append(logo_dict)
    
    return jsonify({'logos': logo_list})


@bp.route('/api/<int:logo_id>/info')
@login_required
def api_info(logo_id):
    """API endpoint to get logo information"""
    logo = db.session.get(ReportLogo, logo_id)
    if not logo:
        return jsonify({'error': 'Logo not found'}), 404
    
    default_logo_id = SystemSettings.get_setting('default_logo_id')
    usage_count = get_scan_logo_usage_count(logo.id)
    
    logo_info = logo.to_dict()
    logo_info['usage_count'] = usage_count
    logo_info['is_default'] = (logo.id == int(default_logo_id)) if default_logo_id else False
    
    return jsonify(logo_info)
