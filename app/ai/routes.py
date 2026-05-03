from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app import db
from app.models import AISettings, AISummary, AuditLog, Scan
from app.ai.forms import AISettingsForm
from app.ai.service import AIService
from app.encryption import encrypt_value

bp = Blueprint('ai', __name__)

_service = AIService()


def _admin_required(f):
    """Inline admin guard — mirrors the pattern used in other route files."""
    from functools import wraps
    from flask import abort
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ------------------------------------------------------------------ admin UI

@bp.route('/admin/ai/settings', methods=['GET', 'POST'])
@login_required
@_admin_required
def admin_ai_settings():
    settings = AISettings.get()
    form = AISettingsForm(obj=settings)

    if form.validate_on_submit():
        settings.ai_enabled = form.ai_enabled.data
        settings.default_mode = form.default_mode.data
        settings.monthly_budget_tokens = form.monthly_budget_tokens.data
        settings.model_id = form.model_id.data
        settings.updated_by = current_user.id
        settings.updated_at = db.func.now()

        new_key = form.api_key.data.strip() if form.api_key.data else ''
        if new_key:
            settings.api_key_encrypted = encrypt_value(new_key)

        db.session.commit()

        AuditLog.log(
            user_id=current_user.id,
            action='update_ai_settings',
            resource_type='ai_settings',
            resource_id=1,
            details={'ai_enabled': settings.ai_enabled, 'model_id': settings.model_id},
            ip_address=request.remote_addr,
        )
        flash('AI settings saved.', 'success')
        return redirect(url_for('ai.admin_ai_settings'))

    # Pre-populate checkbox (WTForms obj= doesn't handle BooleanField reliably on GET)
    if request.method == 'GET':
        form.ai_enabled.data = settings.ai_enabled
        form.default_mode.data = settings.default_mode
        form.monthly_budget_tokens.data = settings.monthly_budget_tokens
        form.model_id.data = settings.model_id

    has_api_key = bool(settings.api_key_encrypted)
    return render_template(
        'admin/ai/settings.html',
        form=form,
        settings=settings,
        has_api_key=has_api_key,
    )


# ------------------------------------------------------------------ scan-level API

@bp.route('/api/ai/summary/<int:scan_id>', methods=['GET'])
@login_required
def get_summary(scan_id):
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    if scan.user_id != current_user.id and current_user.role not in ('admin', 'power_user'):
        return jsonify({'error': 'Forbidden'}), 403

    summary = AISummary.query.filter_by(scan_id=scan_id).first()
    if not summary:
        cost_info = _service.estimate_cost(scan)
        return jsonify({
            'status': 'none',
            'estimated_cost_usd': cost_info['cost_usd'],
            'estimated_tokens_in': cost_info['tokens_in'],
            'ai_enabled': _service.is_enabled(),
        })

    return jsonify({
        'status': summary.status,
        'text': _service.display_text(summary),
        'raw_text': summary.raw_text,
        'edited_text': summary.edited_text,
        'tokens_in': summary.tokens_in,
        'tokens_out': summary.tokens_out,
        'cost_usd': summary.cost_usd,
        'generated_at': summary.generated_at.isoformat() if summary.generated_at else None,
        'error_message': summary.error_message,
        'prompt_version': summary.prompt_version,
    })


@bp.route('/api/ai/summary/<int:scan_id>/generate', methods=['POST'])
@login_required
def generate_summary(scan_id):
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    if scan.user_id != current_user.id and current_user.role not in ('admin', 'power_user'):
        return jsonify({'error': 'Forbidden'}), 403
    if scan.status != 'completed':
        return jsonify({'error': 'Scan is not completed'}), 400
    if not _service.is_enabled():
        return jsonify({'error': 'AI is disabled'}), 400

    cost_info = _service.estimate_cost(scan)
    if not _service.check_budget(cost_info['cost_usd']):
        return jsonify({'error': 'Monthly token budget exceeded'}), 429

    mode = request.json.get('mode') if request.is_json else None
    summary = _service.generate_summary(scan, mode=mode)
    if summary is None:
        return jsonify({'error': 'Generation failed — AI may be disabled'}), 500
    if summary.status == 'error':
        return jsonify({'error': summary.error_message or 'Generation failed'}), 500

    AuditLog.log(
        user_id=current_user.id,
        action='generate_ai_summary',
        resource_type='scan',
        resource_id=scan_id,
        details={'tokens_in': summary.tokens_in, 'tokens_out': summary.tokens_out,
                 'cost_usd': summary.cost_usd},
        ip_address=request.remote_addr,
    )
    return jsonify({
        'status': summary.status,
        'text': _service.display_text(summary),
        'tokens_in': summary.tokens_in,
        'tokens_out': summary.tokens_out,
        'cost_usd': summary.cost_usd,
    })


@bp.route('/api/ai/summary/<int:scan_id>/review', methods=['POST'])
@login_required
def review_summary(scan_id):
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    if scan.user_id != current_user.id and current_user.role not in ('admin', 'power_user'):
        return jsonify({'error': 'Forbidden'}), 403

    summary = AISummary.query.filter_by(scan_id=scan_id).first()
    if not summary or summary.status not in ('ready', 'accepted'):
        return jsonify({'error': 'No reviewable summary found'}), 404

    data = request.get_json(silent=True) or {}
    action = data.get('action')
    edited_text = data.get('edited_text', '')

    if action not in ('accept', 'discard'):
        return jsonify({'error': 'action must be accept or discard'}), 400

    _service.submit_review(summary, edited_text, action, current_user.id)

    AuditLog.log(
        user_id=current_user.id,
        action=f'ai_summary_{action}',
        resource_type='scan',
        resource_id=scan_id,
        details={'summary_id': summary.id, 'action': action},
        ip_address=request.remote_addr,
    )
    return jsonify({'status': summary.status, 'text': _service.display_text(summary)})
