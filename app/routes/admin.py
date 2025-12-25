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
from sqlalchemy import func, text
from datetime import datetime, timedelta
import json
import psutil

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
            'session_timeout_minutes': int(request.form.get('session_timeout_minutes', 60)),
            # Scan settings
            'kast_results_root': request.form.get('kast_results_root', '/opt/kast-web').strip(),
            # Email settings
            'email_enabled': request.form.get('email_enabled') == 'on',
            'smtp_host': request.form.get('smtp_host', ''),
            'smtp_port': int(request.form.get('smtp_port', 587)),
            'smtp_username': request.form.get('smtp_username', ''),
            'smtp_password': request.form.get('smtp_password', ''),
            'from_email': request.form.get('from_email', ''),
            'from_name': request.form.get('from_name', 'KAST Security'),
            'use_tls': request.form.get('use_tls') == 'on',
            'use_ssl': request.form.get('use_ssl') == 'on'
        }
        
        SystemSettings.update_settings(settings_data, user_id=current_user.id)
        
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


@bp.route('/test-smtp', methods=['POST'])
@login_required
@admin_required
def test_smtp():
    """Test SMTP connection with current settings"""
    from app.email import EmailService
    
    # Get SMTP settings from form
    smtp_settings = {
        'smtp_host': request.form.get('smtp_host'),
        'smtp_port': int(request.form.get('smtp_port', 587)),
        'smtp_username': request.form.get('smtp_username'),
        'smtp_password': request.form.get('smtp_password'),
        'from_email': request.form.get('from_email'),
        'from_name': request.form.get('from_name', 'KAST Security'),
        'use_tls': request.form.get('use_tls') == 'on',
        'use_ssl': request.form.get('use_ssl') == 'on'
    }
    
    # Test connection
    email_service = EmailService(smtp_settings)
    success, error = email_service.test_connection()
    
    if success:
        return jsonify({'success': True, 'message': 'SMTP connection successful!'})
    else:
        return jsonify({'success': False, 'message': error}), 400


@bp.route('/test-kast-permissions', methods=['POST'])
@login_required
@admin_required
def test_kast_permissions():
    """Test permissions for KAST results root directory"""
    from app.utils import verify_kast_results_permissions
    
    # Get root path from form
    root_path = request.form.get('kast_results_root', '').strip()
    
    if not root_path:
        return jsonify({'success': False, 'message': 'No path provided'}), 400
    
    # Verify permissions
    success, message = verify_kast_results_permissions(root_path)
    
    if success:
        # Also show the full path that will be used
        from pathlib import Path
        full_path = Path(root_path).resolve() / 'kast_results'
        return jsonify({
            'success': True, 
            'message': message,
            'full_path': str(full_path)
        })
    else:
        return jsonify({'success': False, 'message': message}), 400


@bp.route('/system-info')
@login_required
@admin_required
def system_info():
    """Display comprehensive system information for troubleshooting"""
    import sys
    import os
    import platform
    import subprocess
    from flask import current_app
    from importlib import metadata
    
    def mask_sensitive(value, show_chars=4):
        """Mask sensitive information, showing only last few characters"""
        if not value or len(value) <= show_chars:
            return '***'
        return '*' * (len(value) - show_chars) + value[-show_chars:]
    
    def check_service_status(service_name):
        """Check if a systemd service is running"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() == 'active'
        except:
            return None
    
    def get_disk_usage(path):
        """Get disk usage for a path"""
        try:
            import shutil
            usage = shutil.disk_usage(path)
            return {
                'total': usage.total // (1024**3),  # GB
                'used': usage.used // (1024**3),
                'free': usage.free // (1024**3),
                'percent': round((usage.used / usage.total) * 100, 1)
            }
        except:
            return None
    
    def test_redis_connection():
        """Test Redis connection"""
        try:
            from redis import Redis
            redis_url = current_app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
            # Parse URL to get host and port
            if '://' in redis_url:
                parts = redis_url.split('://')[1].split('/')
                host_port = parts[0].split(':')
                host = host_port[0] if len(host_port) > 0 else 'localhost'
                port = int(host_port[1]) if len(host_port) > 1 else 6379
            else:
                host, port = 'localhost', 6379
            
            r = Redis(host=host, port=port, socket_connect_timeout=2)
            r.ping()
            return True, None
        except Exception as e:
            return False, str(e)
    
    def test_database_connection():
        """Test database connection"""
        try:
            db.session.execute(text('SELECT 1'))
            return True, None
        except Exception as e:
            return False, str(e)
    
    def get_kast_cli_info():
        """Get KAST CLI version and info"""
        try:
            kast_path = os.environ.get('KAST_CLI_PATH', '/usr/local/bin/kast')
            if os.path.exists(kast_path):
                result = subprocess.run(
                    [kast_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                version = result.stdout.strip() if result.returncode == 0 else 'Unknown'
                
                # Get plugin count
                result = subprocess.run(
                    [kast_path, '-ls'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                plugin_count = result.stdout.count('(priority:') if result.returncode == 0 else 0
                
                return {
                    'path': kast_path,
                    'exists': True,
                    'version': version,
                    'plugin_count': plugin_count
                }
            else:
                return {'path': kast_path, 'exists': False}
        except Exception as e:
            return {'error': str(e)}
    
    # Collect system information
    info = {}
    
    # Python Environment
    info['python'] = {
        'version': sys.version,
        'executable': sys.executable,
        'prefix': sys.prefix,
        'path': sys.path,
        'packages': sorted([f"{dist.name}=={dist.version}" for dist in metadata.distributions()])
    }
    
    # System Information
    info['system'] = {
        'platform': platform.platform(),
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'hostname': platform.node(),
        'python_implementation': platform.python_implementation()
    }
    
    # Get CPU and memory info
    try:
        info['system']['cpu_count'] = psutil.cpu_count()
        info['system']['cpu_percent'] = psutil.cpu_percent(interval=1)
        
        mem = psutil.virtual_memory()
        info['system']['memory'] = {
            'total': round(mem.total / (1024**3), 2),  # GB
            'available': round(mem.available / (1024**3), 2),
            'used': round(mem.used / (1024**3), 2),
            'percent': mem.percent
        }
    except Exception:
        # psutil may fail on some systems
        pass
    
    # Environment Variables (filtered and masked)
    sensitive_vars = ['SECRET_KEY', 'PASSWORD', 'PASS', 'TOKEN', 'KEY', 'DATABASE_URL']
    info['environment'] = {}
    for key, value in os.environ.items():
        if any(sens in key.upper() for sens in sensitive_vars):
            info['environment'][key] = mask_sensitive(value)
        elif key in ['PATH', 'PYTHONPATH', 'LD_LIBRARY_PATH']:
            # Split path-like variables for readability
            info['environment'][key] = value.split(':') if value else []
        elif key.startswith('FLASK_') or key.startswith('CELERY_') or key.startswith('KAST_'):
            info['environment'][key] = value
    
    # Flask Configuration (masked)
    info['flask_config'] = {}
    for key, value in current_app.config.items():
        if any(sens in key.upper() for sens in sensitive_vars):
            info['flask_config'][key] = mask_sensitive(str(value))
        else:
            info['flask_config'][key] = value
    
    # File Paths and Permissions
    info['paths'] = {
        'installation': os.getcwd(),
        'logs': '/var/log/kast-web',
        'results': os.environ.get('KAST_RESULTS_DIR', '/var/lib/kast-web/results'),
        'uploads': os.path.join(current_app.root_path, 'static', 'uploads'),
        'database': current_app.config.get('SQLALCHEMY_DATABASE_URI', 'N/A')
    }
    
    # Check path permissions
    for name, path in list(info['paths'].items()):
        if name == 'database':
            continue  # Skip database URI
        try:
            if os.path.exists(path):
                stat_info = os.stat(path)
                info['paths'][f'{name}_exists'] = True
                info['paths'][f'{name}_writable'] = os.access(path, os.W_OK)
                info['paths'][f'{name}_mode'] = oct(stat_info.st_mode)[-3:]
            else:
                info['paths'][f'{name}_exists'] = False
        except:
            pass
    
    # Disk Usage
    info['disk_usage'] = {
        'root': get_disk_usage('/'),
        'opt': get_disk_usage('/opt'),
        'var': get_disk_usage('/var'),
        'tmp': get_disk_usage('/tmp')
    }
    
    # Service Status
    info['services'] = {
        'redis': check_service_status('redis-server'),
        'kast_web': check_service_status('kast-web'),
        'kast_celery': check_service_status('kast-celery'),
        'nginx': check_service_status('nginx'),
        'apache2': check_service_status('apache2')
    }
    
    # Connection Tests
    redis_ok, redis_error = test_redis_connection()
    db_ok, db_error = test_database_connection()
    
    info['connections'] = {
        'redis': {
            'status': redis_ok,
            'error': redis_error
        },
        'database': {
            'status': db_ok,
            'error': db_error
        }
    }
    
    # KAST CLI Information
    info['kast_cli'] = get_kast_cli_info()
    
    # Database Information (masked)
    db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_url:
        if db_url.startswith('sqlite'):
            info['database'] = {
                'type': 'SQLite',
                'path': db_url.replace('sqlite:///', '')
            }
        elif db_url.startswith('postgresql'):
            info['database'] = {
                'type': 'PostgreSQL',
                'url': mask_sensitive(db_url, 10)
            }
        elif db_url.startswith('mysql'):
            info['database'] = {
                'type': 'MySQL/MariaDB',
                'url': mask_sensitive(db_url, 10)
            }
    
    # Log this action
    AuditLog.log(
        user_id=current_user.id,
        action='system_info_viewed',
        resource_type='system',
        details=f'System information viewed by {current_user.username}'
    )
    
    return render_template('admin/system_info.html', info=info)


@bp.route('/system-info/export')
@login_required
@admin_required
def export_system_info():
    """Export system information as JSON"""
    # This would call the same collection logic but return JSON
    # For now, redirect to the main page
    flash('Export functionality coming soon', 'info')
    return redirect(url_for('admin.system_info'))


@bp.route('/import-scan', methods=['GET', 'POST'])
@login_required
@admin_required
def import_scan():
    """Import CLI scan results into KAST-Web"""
    from app.forms import ImportScanForm
    from app.import_utils import import_cli_scan, get_import_preview
    
    form = ImportScanForm()
    
    # Populate user choices (current user first, then others alphabetically)
    users = User.query.order_by(User.username).all()
    form.assign_to_user.choices = [
        (current_user.id, f'{current_user.username} (me)')
    ] + [
        (u.id, u.username) for u in users if u.id != current_user.id
    ]
    
    preview_data = None
    
    if request.method == 'POST':
        if form.validate_on_submit():
            scan_dir = form.scan_directory.data.strip()
            user_id = form.assign_to_user.data
            
            # Import the scan
            success, scan_id, error = import_cli_scan(
                scan_dir,
                user_id,
                current_user.id
            )
            
            if success:
                flash(f'Scan imported successfully! Scan ID: {scan_id}', 'success')
                return redirect(url_for('scans.detail', scan_id=scan_id))
            else:
                flash(f'Import failed: {error}', 'danger')
        else:
            flash('Please correct the errors in the form', 'warning')
    
    # If GET request with directory parameter, show preview
    preview_dir = request.args.get('preview')
    if preview_dir:
        preview_data = get_import_preview(preview_dir)
        form.scan_directory.data = preview_dir
    
    return render_template('admin/import_scan.html', form=form, preview=preview_data)
