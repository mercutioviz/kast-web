"""
app/cloud/routes — Flask blueprint for /api/cloud/* and /admin/cloud/* endpoints.

THIS BLUEPRINT IS NOT REGISTERED IN app/__init__.py UNTIL D8.
It is defined here so the URL surface and handler signatures are visible
during D1–D7 development.

API routes (JSON, any authenticated user can read status):
    GET  /api/cloud/scans/<id>/status
    GET  /api/cloud/orphans              (admin only)
    POST /api/cloud/orphans/<id>/cleanup (admin only)

Admin UI routes (HTML, admin only):
    GET      /admin/cloud/credentials
    GET/POST /admin/cloud/credentials/new
    GET/POST /admin/cloud/credentials/<id>/edit
    POST     /admin/cloud/credentials/<id>/delete
    GET      /admin/cloud/scans
    GET      /admin/cloud/orphans

All admin mutations write an AuditLog entry.
"""

from functools import wraps

from flask import Blueprint, jsonify, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

bp = Blueprint('cloud', __name__)


def admin_required(f):
    """Require admin role. Mirrors the pattern in app/routes/zap_admin.py."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You must be an administrator to access this page', 'danger')
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
    raise NotImplementedError("Will be implemented in D8 (routes)")


@bp.route('/api/cloud/orphans')
@login_required
@admin_required
def api_cloud_orphans():
    """Return list of detected CloudOrphan rows.

    Response JSON:
        {orphans: [{id, provider, resource_id, resource_type,
                    detected_at, cleanup_attempts, status}]}
    """
    raise NotImplementedError("Will be implemented in D8 (routes)")


@bp.route('/api/cloud/orphans/<int:orphan_id>/cleanup', methods=['POST'])
@login_required
@admin_required
def api_cloud_orphan_cleanup(orphan_id: int):
    """Immediately trigger teardown of a specific orphaned resource.

    Calls cleanup.force_cleanup(orphan_id). Writes AuditLog entry.

    Response JSON:
        {ok: true} on success, {ok: false, error: '...'} on failure.
    """
    raise NotImplementedError("Will be implemented in D8 (routes)")


# ---------------------------------------------------------------------------
# Admin UI routes — Cloud Credentials
# ---------------------------------------------------------------------------

@bp.route('/admin/cloud/credentials')
@login_required
@admin_required
def admin_cloud_credentials():
    """List all CloudCredential rows.

    Template: app/templates/admin/cloud/credentials.html (D6)
    """
    raise NotImplementedError("Will be implemented in D6 (credentials admin UI)")


@bp.route('/admin/cloud/credentials/new', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_cloud_credentials_new():
    """Create a new CloudCredential. Writes AuditLog entry on POST.

    Template: app/templates/admin/cloud/credential_form.html (D6)
    """
    raise NotImplementedError("Will be implemented in D6 (credentials admin UI)")


@bp.route('/admin/cloud/credentials/<int:credential_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_cloud_credentials_edit(credential_id: int):
    """Edit an existing CloudCredential. Writes AuditLog entry on POST.

    Template: app/templates/admin/cloud/credential_form.html (D6)
    """
    raise NotImplementedError("Will be implemented in D6 (credentials admin UI)")


@bp.route('/admin/cloud/credentials/<int:credential_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_cloud_credentials_delete(credential_id: int):
    """Delete a CloudCredential. Writes AuditLog entry. Redirects to list."""
    raise NotImplementedError("Will be implemented in D6 (credentials admin UI)")


# ---------------------------------------------------------------------------
# Admin UI routes — Cloud Scans
# ---------------------------------------------------------------------------

@bp.route('/admin/cloud/scans')
@login_required
@admin_required
def admin_cloud_scans():
    """List active and recent CloudScan rows with status and age.

    Template: app/templates/admin/cloud/scans.html (D7)
    """
    raise NotImplementedError("Will be implemented in D7 (scans + orphans admin UI)")


# ---------------------------------------------------------------------------
# Admin UI routes — Cloud Orphans
# ---------------------------------------------------------------------------

@bp.route('/admin/cloud/orphans')
@login_required
@admin_required
def admin_cloud_orphans():
    """List CloudOrphan rows and provide manual cleanup actions.

    Template: app/templates/admin/cloud/orphans.html (D7)
    """
    raise NotImplementedError("Will be implemented in D7 (scans + orphans admin UI)")
