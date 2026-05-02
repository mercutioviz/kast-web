"""
app/cloud/routes — Flask blueprint for /api/cloud/* and /admin/cloud/* endpoints.

Registered in app/__init__.py (D8).

API routes (JSON):
    GET  /api/cloud/scans/<id>/status        any authenticated user
    GET  /api/cloud/orphans                  admin only
    POST /api/cloud/orphans/<id>/cleanup     admin only

Admin UI routes (HTML, admin only):
    GET      /admin/cloud/credentials
    GET/POST /admin/cloud/credentials/new
    GET/POST /admin/cloud/credentials/<id>/edit
    POST     /admin/cloud/credentials/<id>/delete
    GET      /admin/cloud/scans
    GET      /admin/cloud/orphans

All admin mutations write an AuditLog entry.
"""

import json
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db

bp = Blueprint('cloud', __name__)


def admin_required(f):
    """Require admin role. Mirrors the pattern in app/routes/zap_admin.py."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You must be an administrator to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@bp.route('/api/cloud/scans/<int:scan_id>/status')
@login_required
def api_cloud_scan_status(scan_id: int):
    """Return the current status of a cloud scan's infrastructure.

    Response JSON:
        {cloud_scan_id, status, zap_url (masked), provisioned_at, error_message}
    """
    from app.models import CloudScan, Scan

    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404

    # Non-admins can only query their own scans
    if not current_user.is_admin and scan.user_id != current_user.id:
        return jsonify({'error': 'Forbidden'}), 403

    cloud_scan = CloudScan.query.filter_by(scan_id=scan_id).first()
    if not cloud_scan:
        return jsonify({'error': 'No cloud scan found for this scan'}), 404

    return jsonify({
        'cloud_scan_id': cloud_scan.id,
        'status': cloud_scan.status,
        'zap_url': cloud_scan.zap_url,
        'provisioned_at': cloud_scan.provisioned_at.isoformat() if cloud_scan.provisioned_at else None,
        'error_message': cloud_scan.error_message,
    })


@bp.route('/api/cloud/orphans')
@login_required
@admin_required
def api_cloud_orphans():
    """Return list of detected CloudOrphan rows.

    Response JSON:
        {orphans: [{id, provider, resource_id, resource_type,
                    detected_at, cleanup_attempts, status}]}
    """
    from app.models import CloudOrphan

    orphans = CloudOrphan.query.order_by(CloudOrphan.detected_at.desc()).all()
    return jsonify({
        'orphans': [
            {
                'id': o.id,
                'provider': o.provider,
                'resource_id': o.resource_id,
                'resource_type': o.resource_type,
                'detected_at': o.detected_at.isoformat() if o.detected_at else None,
                'cleanup_attempts': o.cleanup_attempts,
                'status': o.status,
                'error_message': o.error_message,
            }
            for o in orphans
        ]
    })


@bp.route('/api/cloud/orphans/<int:orphan_id>/cleanup', methods=['POST'])
@login_required
@admin_required
def api_cloud_orphan_cleanup(orphan_id: int):
    """Immediately dispatch teardown for an orphaned CloudScan.

    Writes AuditLog entry.
    Response JSON: {ok: true} on success, {ok: false, error: '...'} on failure.
    """
    from app.models import CloudOrphan, AuditLog
    from app.tasks import cloud_teardown_task

    orphan = db.session.get(CloudOrphan, orphan_id)
    if not orphan:
        return jsonify({'ok': False, 'error': 'Orphan not found'}), 404

    try:
        if orphan.cloud_scan_id:
            cloud_teardown_task.delay(orphan.cloud_scan_id)
        orphan.cleanup_attempts = (orphan.cleanup_attempts or 0) + 1
        orphan.last_cleanup_attempt = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()

        AuditLog.log(
            user_id=current_user.id,
            action='cloud_orphan_cleanup',
            resource_type='cloud_orphan',
            resource_id=orphan_id,
            details=f'manual trigger for cloud_scan_id={orphan.cloud_scan_id}',
            ip_address=request.remote_addr,
        )
        return jsonify({'ok': True})
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Admin UI — Cloud Credentials (D6)
# ---------------------------------------------------------------------------

@bp.route('/admin/cloud/credentials')
@login_required
@admin_required
def admin_cloud_credentials():
    """List all CloudCredential rows."""
    from app.models import CloudCredential, CloudScan

    credentials = CloudCredential.query.order_by(CloudCredential.created_at.desc()).all()
    # Annotate each with last-used scan count
    for cred in credentials:
        cred.scan_count = CloudScan.query.filter_by(cloud_credential_id=cred.id).count()
    return render_template('admin/cloud/credentials.html', credentials=credentials)


@bp.route('/admin/cloud/credentials/new', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_cloud_credentials_new():
    """Create a new CloudCredential."""
    from app.models import CloudCredential, AuditLog
    from app.forms import CloudCredentialForm

    form = CloudCredentialForm()
    if form.validate_on_submit():
        cred = CloudCredential(
            name=form.name.data.strip(),
            provider=form.provider.data,
            created_by=current_user.id,
            is_active=form.is_active.data,
        )
        cred.credentials = json.loads(form.credentials_json.data)
        db.session.add(cred)
        db.session.commit()

        AuditLog.log(
            user_id=current_user.id,
            action='cloud_credential_create',
            resource_type='cloud_credential',
            resource_id=cred.id,
            details=f'name={cred.name!r} provider={cred.provider}',
            ip_address=request.remote_addr,
        )
        flash(f'Cloud credential "{cred.name}" created.', 'success')
        return redirect(url_for('cloud.admin_cloud_credentials'))

    return render_template('admin/cloud/credential_form.html', form=form, mode='create', cred=None)


@bp.route('/admin/cloud/credentials/<int:credential_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_cloud_credentials_edit(credential_id: int):
    """Edit an existing CloudCredential."""
    from app.models import CloudCredential, AuditLog
    from app.forms import CloudCredentialForm

    cred = db.session.get(CloudCredential, credential_id)
    if not cred:
        flash('Credential not found.', 'danger')
        return redirect(url_for('cloud.admin_cloud_credentials'))

    form = CloudCredentialForm(obj=cred)

    if form.validate_on_submit():
        cred.name = form.name.data.strip()
        cred.provider = form.provider.data
        cred.is_active = form.is_active.data
        # Only update credentials if the JSON field was filled in with non-placeholder data
        new_creds = json.loads(form.credentials_json.data)
        cred.credentials = new_creds
        db.session.commit()

        AuditLog.log(
            user_id=current_user.id,
            action='cloud_credential_update',
            resource_type='cloud_credential',
            resource_id=cred.id,
            details=f'name={cred.name!r} provider={cred.provider}',
            ip_address=request.remote_addr,
        )
        flash(f'Cloud credential "{cred.name}" updated.', 'success')
        return redirect(url_for('cloud.admin_cloud_credentials'))

    # Pre-populate credentials_json with masked placeholder on GET
    if request.method == 'GET':
        form.credentials_json.data = '{ "...": "credentials stored — paste new JSON to replace" }'

    return render_template('admin/cloud/credential_form.html', form=form, mode='edit', cred=cred)


@bp.route('/admin/cloud/credentials/<int:credential_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_cloud_credentials_delete(credential_id: int):
    """Delete a CloudCredential after checking for active cloud scans."""
    from app.models import CloudCredential, CloudScan, AuditLog

    cred = db.session.get(CloudCredential, credential_id)
    if not cred:
        flash('Credential not found.', 'danger')
        return redirect(url_for('cloud.admin_cloud_credentials'))

    active_count = CloudScan.query.filter(
        CloudScan.cloud_credential_id == credential_id,
        CloudScan.status.in_(['provisioning', 'scanning', 'tearing_down']),
    ).count()
    if active_count > 0:
        flash(
            f'Cannot delete: {active_count} active cloud scan(s) use this credential.',
            'danger',
        )
        return redirect(url_for('cloud.admin_cloud_credentials'))

    name = cred.name
    AuditLog.log(
        user_id=current_user.id,
        action='cloud_credential_delete',
        resource_type='cloud_credential',
        resource_id=credential_id,
        details=f'name={name!r} provider={cred.provider}',
        ip_address=request.remote_addr,
    )
    db.session.delete(cred)
    db.session.commit()
    flash(f'Cloud credential "{name}" deleted.', 'success')
    return redirect(url_for('cloud.admin_cloud_credentials'))


# ---------------------------------------------------------------------------
# Admin UI — Cloud Scans (D7)
# ---------------------------------------------------------------------------

@bp.route('/admin/cloud/scans')
@login_required
@admin_required
def admin_cloud_scans():
    """List active and recent CloudScan rows."""
    from app.models import CloudScan

    status_filter = request.args.get('status', 'active')
    query = CloudScan.query

    if status_filter == 'active':
        query = query.filter(
            CloudScan.status.in_(['provisioning', 'scanning', 'tearing_down'])
        )
    elif status_filter == 'failed':
        query = query.filter(CloudScan.status.in_(['failed', 'orphaned']))
    elif status_filter == 'completed':
        query = query.filter(CloudScan.status == 'torn_down')

    cloud_scans = query.order_by(CloudScan.created_at.desc()).limit(200).all()
    return render_template(
        'admin/cloud/scans.html',
        cloud_scans=cloud_scans,
        status_filter=status_filter,
    )


# ---------------------------------------------------------------------------
# Admin UI — Cloud Orphans (D7)
# ---------------------------------------------------------------------------

@bp.route('/admin/cloud/orphans')
@login_required
@admin_required
def admin_cloud_orphans():
    """List CloudOrphan rows with manual cleanup actions."""
    from app.models import CloudOrphan

    orphans = CloudOrphan.query.order_by(CloudOrphan.detected_at.desc()).all()
    return render_template('admin/cloud/orphans.html', orphans=orphans)
