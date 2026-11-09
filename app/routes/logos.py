"""
Logo Management Routes for White-Labeling Feature
Allows users to upload, view, and manage report logos
"""

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, send_file,
    abort, jsonify, current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from urllib.parse import unquote, urlsplit
from app import db
from app.logo_media import accept_attribute, format_list_text, prepare_logo
from app.models import ReportLogo, SystemSettings, AuditLog
from app.url_fetch import UrlFetchError, fetch_remote_image
from app.utils import (
    save_logo_file,
    delete_logo_file,
    get_scan_logo_usage_count,
    get_logo_max_upload_bytes,
    get_logo_max_dimension,
    persist_prepared_logo,
    stage_prepared_logo,
    load_staged_logo,
    discard_staged_logo,
    sweep_staged_logos,
    check_logo_import_rate_limit,
)
from pathlib import Path

bp = Blueprint('logos', __name__, url_prefix='/logos')

# Uploaded logos are served from our own origin and SVG is an active document
# format. Sanitization happens at upload time; this CSP is the second layer,
# neutering anything that reaches a browser by direct navigation.
LOGO_SECURITY_HEADERS = {
    'Content-Security-Policy': (
        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        "sandbox; base-uri 'none'; form-action 'none'"
    ),
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
}

# Matches the ReportLogo.source_url column width.
MAX_IMPORT_URL_LENGTH = 2048


def _send_logo(path, mime_type, download_name):
    """Send a logo file with hardened response headers."""
    response = send_file(
        path,
        mimetype=mime_type or 'application/octet-stream',
        download_name=download_name,
    )
    response.headers.update(LOGO_SECURITY_HEADERS)
    response.headers['Content-Disposition'] = f'inline; filename="{download_name}"'
    return response


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

    return render_template(
        'logos/manage.html',
        logos=logo_data,
        accept_attribute=accept_attribute(),
        supported_formats=format_list_text(),
        max_upload_mb=get_logo_max_upload_bytes() // (1024 * 1024),
    )


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
        render_path=result['render_path'],
        render_mime=result['render_mime'],
        width=result['width'],
        height=result['height'],
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
        details=(
            f'Uploaded logo: {name} '
            f'(format: {result["format_label"]}, reports use: {result["render_mime"]})'
        )
    )
    
    flash(f'Logo "{name}" uploaded successfully', 'success')
    return redirect(url_for('logos.manage'))


@bp.route('/<int:logo_id>')
@login_required
def view(logo_id):
    """View/download the original uploaded logo file"""
    logo = db.session.get(ReportLogo, logo_id)
    if not logo:
        abort(404)

    file_path = Path(logo.file_path)
    if not file_path.exists():
        abort(404)

    return _send_logo(file_path, logo.mime_type, logo.filename)


@bp.route('/<int:logo_id>/render')
@login_required
def view_render(logo_id):
    """
    View the render derivative - the exact file reports will embed.

    Falls back to the original for rows predating multi-format support.
    """
    logo = db.session.get(ReportLogo, logo_id)
    if not logo:
        abort(404)

    render_path = Path(logo.render_path) if logo.render_path else None
    if not render_path or not render_path.exists():
        return redirect(url_for('logos.view', logo_id=logo_id))

    return _send_logo(
        render_path,
        logo.render_mime or logo.mime_type,
        render_path.name,
    )


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
    render_path = logo.render_path

    # Delete from database first
    db.session.delete(logo)
    db.session.commit()

    # Then delete the original and its render derivative from the filesystem
    delete_logo_file(file_path, render_path)
    
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


# ============================================================================
# IMPORT FROM URL
#
# Two steps on purpose: fetch-and-stage, then confirm. Staging means the bytes
# the user approved in the preview are exactly the bytes that get stored - a
# re-fetch on confirm could be served different content the second time.
# The SSRF guard lives in app/url_fetch.py.
# ============================================================================

@bp.route('/import/fetch', methods=['POST'])
@login_required
def import_fetch():
    """Fetch an image from a user-supplied URL and stage it for confirmation"""
    payload = request.get_json(silent=True) or {}
    url = (payload.get('url') or '').strip()

    if not url:
        return jsonify({'error': 'Enter a URL to import.'}), 400

    if len(url) > MAX_IMPORT_URL_LENGTH:
        return jsonify({'error': 'That URL is too long.'}), 400

    allowed, retry_after = check_logo_import_rate_limit(current_user.id)
    if not allowed:
        return jsonify({
            'error': 'Too many import attempts. Wait a minute and try again.'
        }), 429, {'Retry-After': str(retry_after)}

    # Clear out previews nobody came back to confirm
    try:
        sweep_staged_logos()
    except OSError:
        current_app.logger.warning('Logo staging sweep failed', exc_info=True)

    try:
        result = fetch_remote_image(
            url,
            max_bytes=get_logo_max_upload_bytes(),
            allowed_ports=current_app.config.get('LOGO_IMPORT_ALLOWED_PORTS', (80, 443)),
            max_redirects=current_app.config.get('LOGO_IMPORT_MAX_REDIRECTS', 3),
            connect_timeout=current_app.config.get('LOGO_IMPORT_CONNECT_TIMEOUT', 5),
            read_timeout=current_app.config.get('LOGO_IMPORT_READ_TIMEOUT', 10),
            total_deadline=current_app.config.get('LOGO_IMPORT_TOTAL_DEADLINE', 15),
            user_agent=f"kast-web/{current_app.config.get('VERSION', 'unknown')}",
        )
    except UrlFetchError as exc:
        current_app.logger.info(
            'Logo import refused for user %s: %s', current_user.id, exc
        )
        return jsonify({'error': str(exc)}), 400

    # Same validation, sanitization and normalization as a file upload. The
    # server's Content-Type is not trusted; magic bytes decide.
    filename = _filename_from_url(result.final_url, result.data, result.content_type)
    try:
        prepared = prepare_logo(
            result.data, filename, max_dimension=get_logo_max_dimension()
        )
    except ValueError as exc:
        message = str(exc)
        if message.startswith('Unsupported file type'):
            # Content-Type comes from the remote server; keep it short.
            served = (result.content_type or 'unknown content')[:60]
            message = (
                f'That URL does not point to a supported image '
                f'(the server returned {served}).'
            )
        return jsonify({'error': message}), 400

    try:
        token = stage_prepared_logo(
            prepared, url, result.final_url, current_user.id
        )
    except OSError as exc:
        current_app.logger.exception('Failed to stage imported logo')
        return jsonify({'error': f'Could not store the fetched image: {exc}'}), 500

    return jsonify({
        'token': token,
        'preview_url': url_for('logos.import_preview', token=token),
        'format_label': prepared['label'],
        'width': prepared['width'],
        'height': prepared['height'],
        'file_size': len(prepared['original_bytes']),
        'is_normalized': prepared['render_bytes'] is not prepared['original_bytes'],
        'render_mime': prepared['render_mime'],
        'source_url': url,
        'final_url': result.final_url,
        'redirected': bool(result.redirects),
        'suggested_name': _suggested_name(result.final_url),
    })


@bp.route('/import/<token>/preview')
@login_required
def import_preview(token):
    """Serve the staged render derivative - what reports would embed"""
    meta = load_staged_logo(token, current_user.id)
    if not meta:
        abort(404)

    render_path = Path(meta['render_path'])
    if not render_path.exists():
        abort(404)

    return _send_logo(render_path, meta['render_mime'], render_path.name)


@bp.route('/import/confirm', methods=['POST'])
@login_required
def import_confirm():
    """Promote a staged import into a real logo"""
    payload = request.get_json(silent=True) or {}
    token = (payload.get('token') or '').strip()
    name = (payload.get('name') or '').strip()
    description = (payload.get('description') or '').strip()

    if not name:
        return jsonify({'error': 'Logo name is required.'}), 400

    meta = load_staged_logo(token, current_user.id)
    if not meta:
        return jsonify({
            'error': 'That preview has expired. Fetch the URL again.'
        }), 404

    original_path = Path(meta['original_path'])
    render_path = Path(meta['render_path'])
    if not original_path.exists():
        discard_staged_logo(token)
        return jsonify({
            'error': 'That preview has expired. Fetch the URL again.'
        }), 404

    # Rebuild the prepared shape from the staged files so the permanent write
    # goes through exactly the same helper as an upload.
    original_bytes = original_path.read_bytes()
    render_bytes = (
        original_bytes if render_path == original_path else render_path.read_bytes()
    )
    prepared = {
        'original_bytes': original_bytes,
        'render_bytes': render_bytes,
        'original_extension': meta['original_extension'],
        'render_extension': meta['render_extension'],
        'mime': meta['mime'],
        'render_mime': meta['render_mime'],
        'label': meta['label'],
        'kind': meta['kind'],
        'width': meta['width'],
        'height': meta['height'],
    }

    try:
        result = persist_prepared_logo(
            prepared,
            _filename_from_url(meta['final_url'], original_bytes, meta['mime']),
        )
    except OSError as exc:
        current_app.logger.exception('Failed to store imported logo')
        return jsonify({'error': f'Could not store the logo: {exc}'}), 500

    logo = ReportLogo(
        name=name,
        description=description,
        filename=result['filename'],
        file_path=result['file_path'],
        mime_type=result['mime_type'],
        file_size=result['file_size'],
        render_path=result['render_path'],
        render_mime=result['render_mime'],
        width=result['width'],
        height=result['height'],
        source_url=meta['final_url'],
        uploaded_by=current_user.id,
    )
    db.session.add(logo)
    db.session.commit()

    discard_staged_logo(token)

    AuditLog.log(
        user_id=current_user.id,
        action='logo_imported',
        resource_type='logo',
        resource_id=logo.id,
        details=(
            f'Imported logo: {name} from {meta["final_url"]} '
            f'(format: {result["format_label"]}, reports use: {result["render_mime"]})'
        )
    )

    flash(f'Logo "{name}" imported successfully', 'success')
    return jsonify({'ok': True, 'logo_id': logo.id,
                    'redirect': url_for('logos.manage')})


@bp.route('/import/<token>/discard', methods=['POST'])
@login_required
def import_discard(token):
    """Throw away a staged import the user decided against"""
    meta = load_staged_logo(token, current_user.id)
    if meta:
        discard_staged_logo(token)
    return jsonify({'ok': True})


def _filename_from_url(url, data, content_type=None):
    """
    Best-effort filename for a fetched image.

    The extension is taken from the bytes themselves rather than the URL. A
    remote filename is not something the user controls: plenty of asset URLs
    carry no extension at all, and content negotiation routinely serves WebP
    from a .png URL. Trusting the URL there would reject perfectly good
    images for a mismatch that is the server's doing.

    This is not a weakening: prepare_logo re-verifies the magic bytes against
    whatever extension it is handed, so an unrecognized payload still fails.
    """
    from app.logo_media import LOGO_FORMATS, SVG_PROBE_BYTES, extension_of, sniff_format

    path = urlsplit(url).path
    candidate = unquote(path.rsplit('/', 1)[-1]) if path else ''
    stem = candidate.rsplit('.', 1)[0] if '.' in candidate else candidate
    stem = stem or 'logo'

    detected = sniff_format(data[:SVG_PROBE_BYTES])
    if detected:
        return f"{stem}.{LOGO_FORMATS[detected]['extensions'][0]}"

    # Unrecognized bytes. Keep any extension the URL offered so prepare_logo
    # can produce a precise message about it.
    if candidate and extension_of(candidate):
        return candidate

    for spec in LOGO_FORMATS.values():
        if content_type and spec['mime'] == content_type.lower():
            return f"{stem}.{spec['extensions'][0]}"

    return candidate or 'logo'


def _suggested_name(url):
    """A starting point for the Logo Name field, derived from the URL."""
    path = urlsplit(url).path
    stem = unquote(path.rsplit('/', 1)[-1]) if path else ''
    stem = stem.rsplit('.', 1)[0] if '.' in stem else stem
    stem = stem.replace('-', ' ').replace('_', ' ').strip()
    if stem:
        return stem[:100]
    return urlsplit(url).hostname or ''


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
            'format_label': logo.format_label,
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
