"""
Admin Panel Routes
Provides administrative functions including:
- Dashboard with system statistics
- System settings management
- Audit logging
- User activity monitoring
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import User, Scan, AuditLog, SystemSettings
from sqlalchemy import func
from datetime import datetime, timedelta
import json

bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You must be an administrator to access this page', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with system statistics"""
    
    # User statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    admin_users = User.query.filter_by(role='admin').count()
    
    # Scan statistics
    total_scans = Scan.query.count()
    completed_scans = Scan.query.filter_by(status='completed').count()
    failed_scans = Scan.query.filter_by(status='failed').count()
    running_scans = Scan.query.filter_by(status='running').count()
    
    # Recent activity (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_scans = Scan.query.filter(Scan.started_at >= yesterday).count()
    recent_logins = User.query.filter(User.last_login >= yesterday).count()
    
    # Top users by scan count
    top_users = db.session.query(
        User.username,
        func.count(Scan.id).label('scan_count')
    ).join(Scan).group_by(User.id).order_by(func.count(Scan.id).desc()).limit(5).all()
    
    # Recent audit logs
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()
    
    # System status
    settings = SystemSettings.get_settings()
    
    stats = {
        'users': {
            'total': total_users,
            'active': active_users,
            'admins': admin_users,
            'inactive': total_users - active_users
        },
        'scans': {
            'total': total_scans,
            'completed': completed_scans,
            'failed': failed_scans,
            'running': running_scans,
            'recent': recent_scans
        },
        'activity': {
            'recent_logins': recent_logins,
            'top_users': top_users
        },
        'system': {
            'maintenance_mode': settings.get('maintenance_mode', False),
            'registration_enabled': settings.get('allow_registration', False)
        }
    }
    
    return render_template('admin/dashboard.html', 
                         stats=stats, 
                         recent_logs=recent_logs)


@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    """System settings management"""
    
    if request.method == 'POST':
        # Update settings
        settings_data = {
            'site_name': request.form.get('site_name', 'KAST Web'),
            'maintenance_mode': request.form.get('maintenance_mode') == 'on',
            'allow_registration': request.form.get('allow_registration') == 'on',
            'max_scan_age_days': int(request.form.get('max_scan_age_days', 90)),
            'max_scans_per_user': int(request.form.get('max_scans_per_user', 0)),
            'enable_audit_log': request.form.get('enable_audit_log') == 'on',
            'session_timeout_minutes': int(request.form.get('session_timeout_minutes', 60))
        }
        
        SystemSettings.update_settings(settings_data)
        
        # Log the change
        AuditLog.log(
            user_id=current_user.id,
            action='settings_updated',
            resource_type='system',
            details=f'System settings updated by {current_user.username}'
        )
        
        flash('System settings updated successfully', 'success')
        return redirect(url_for('admin.settings'))
    
    # GET request - show settings form
    current_settings = SystemSettings.get_settings()
    
    return render_template('admin/settings.html', settings=current_settings)


@bp.route('/audit-log')
@login_required
@admin_required
def audit_log():
    """View audit log with filtering"""
    
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Get filter parameters
    user_filter = request.args.get('user', '')
    action_filter = request.args.get('action', '')
    resource_filter = request.args.get('resource', '')
    
    # Build query
    query = AuditLog.query
    
    if user_filter:
        query = query.join(User).filter(User.username.contains(user_filter))
    
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    
    if resource_filter:
        query = query.filter(AuditLog.resource_type == resource_filter)
    
    # Order by most recent first
    query = query.order_by(AuditLog.timestamp.desc())
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    logs = pagination.items
    
    # Get unique actions and resource types for filters
    actions = db.session.query(AuditLog.action).distinct().all()
    actions = [a[0] for a in actions]
    
    resources = db.session.query(AuditLog.resource_type).distinct().all()
    resources = [r[0] for r in resources]
    
    return render_template('admin/audit_log.html',
                         logs=logs,
                         pagination=pagination,
                         actions=actions,
                         resources=resources,
                         user_filter=user_filter,
                         action_filter=action_filter,
                         resource_filter=resource_filter)


@bp.route('/activity')
@login_required
@admin_required
def activity():
    """User activity monitoring"""
    
    # Get activity period
    period = request.args.get('period', 7, type=int)  # days
    start_date = datetime.utcnow() - timedelta(days=period)
    
    # Active users in period
    active_users = User.query.filter(User.last_login >= start_date).all()
    
    # Scans per user in period
    user_scans = db.session.query(
        User.username,
        User.email,
        User.last_login,
        func.count(Scan.id).label('scan_count')
    ).outerjoin(Scan).filter(
        (Scan.started_at >= start_date) | (Scan.started_at.is_(None))
    ).group_by(User.id).order_by(func.count(Scan.id).desc()).all()
    
    # Scan activity over time
    daily_scans = db.session.query(
        func.date(Scan.started_at).label('date'),
        func.count(Scan.id).label('count')
    ).filter(Scan.started_at >= start_date).group_by(
        func.date(Scan.started_at)
    ).order_by(func.date(Scan.started_at)).all()
    
    # Failed scans per user
    failed_scans = db.session.query(
        User.username,
        func.count(Scan.id).label('failed_count')
    ).join(Scan).filter(
        Scan.status == 'failed',
        Scan.started_at >= start_date
    ).group_by(User.id).order_by(func.count(Scan.id).desc()).all()
    
    return render_template('admin/activity.html',
                         user_scans=user_scans,
                         daily_scans=daily_scans,
                         failed_scans=failed_scans,
                         period=period)


@bp.route('/clear-audit-log', methods=['POST'])
@login_required
@admin_required
def clear_audit_log():
    """Clear old audit log entries"""
    
    days = request.form.get('days', 90, type=int)
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    deleted_count = AuditLog.query.filter(AuditLog.timestamp < cutoff_date).delete()
    db.session.commit()
    
    # Log this action
    AuditLog.log(
        user_id=current_user.id,
        action='audit_log_cleared',
        resource_type='system',
        details=f'Cleared {deleted_count} audit log entries older than {days} days'
    )
    
    flash(f'Cleared {deleted_count} audit log entries', 'success')
    return redirect(url_for('admin.audit_log'))


@bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """API endpoint for dashboard statistics (for real-time updates)"""
    
    stats = {
        'users': {
            'total': User.query.count(),
            'active': User.query.filter_by(is_active=True).count()
        },
        'scans': {
            'total': Scan.query.count(),
            'running': Scan.query.filter_by(status='running').count(),
            'completed': Scan.query.filter_by(status='completed').count(),
            'failed': Scan.query.filter_by(status='failed').count()
        }
    }
    
    return jsonify(stats)
