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
from app.models import User, Scan, AuditLog, SystemSettings, ScanResult, ScanShare, ReportLogo, ZapAutomationPlan, ZapConfiguration, CloudCredential, CloudScan, CloudOrphan, AISettings, AISummary
from sqlalchemy import func, text
from datetime import datetime, timedelta
import json
import psutil
import os
import shutil
import re

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
    
    # ZAP statistics
    total_plans = ZapAutomationPlan.query.count()
    active_plans = ZapAutomationPlan.query.filter_by(is_draft=False).count()
    default_plan = ZapAutomationPlan.query.filter_by(is_system_default=True).first()
    power_user_plans = ZapAutomationPlan.query.filter_by(allow_power_users=True, is_draft=False).count()
    
    total_configs = ZapConfiguration.query.count()
    active_configs = ZapConfiguration.query.filter_by(is_active=True).count()
    
    # Count configs by execution mode
    local_configs = ZapConfiguration.query.filter_by(execution_mode='local').count()
    remote_configs = ZapConfiguration.query.filter_by(execution_mode='remote').count()
    cloud_configs = ZapConfiguration.query.filter_by(execution_mode='cloud').count()
    auto_configs = ZapConfiguration.query.filter_by(execution_mode='auto').count()

    # AI statistics
    try:
        ai_settings = AISettings.get()
        ai_enabled = ai_settings.ai_enabled
        ai_model = ai_settings.model_id or 'not set'
        ai_total_summaries = AISummary.query.count()
        ai_accepted_summaries = AISummary.query.filter_by(status='accepted').count()
    except Exception:
        ai_enabled = False
        ai_model = 'unknown'
        ai_total_summaries = 0
        ai_accepted_summaries = 0

    # Cloud statistics
    try:
        cloud_credential_count = CloudCredential.query.count()
        cloud_active_scans = CloudScan.query.filter(
            CloudScan.status.in_(['provisioning', 'provisioned', 'scan_running'])
        ).count()
        cloud_unresolved_orphans = CloudOrphan.query.filter(
            CloudOrphan.status.in_(['detected', 'cleanup_pending', 'failed'])
        ).count()
    except Exception:
        cloud_credential_count = 0
        cloud_active_scans = 0
        cloud_unresolved_orphans = 0

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
        },
        'zap': {
            'plans': {
                'total': total_plans,
                'active': active_plans,
                'default_name': default_plan.name if default_plan else 'None',
                'power_user_count': power_user_plans
            },
            'configs': {
                'total': total_configs,
                'active': active_configs,
                'by_mode': {
                    'local': local_configs,
                    'remote': remote_configs,
                    'cloud': cloud_configs,
                    'auto': auto_configs
                }
            }
        },
        'ai': {
            'enabled': ai_enabled,
            'model': ai_model,
            'total_summaries': ai_total_summaries,
            'accepted_summaries': ai_accepted_summaries,
        },
        'cloud': {
            'credential_count': cloud_credential_count,
            'active_scans': cloud_active_scans,
            'unresolved_orphans': cloud_unresolved_orphans,
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


@bp.route('/api/scan-trend')
@login_required
@admin_required
def api_scan_trend():
    """30-day daily scan counts for dashboard trend chart."""
    from collections import defaultdict
    import calendar

    today = datetime.utcnow().date()
    start = today - timedelta(days=29)

    rows = db.session.execute(
        text(
            "SELECT date(started_at) as day, status, count(*) as cnt "
            "FROM scans "
            "WHERE date(started_at) >= :start "
            "GROUP BY date(started_at), status"
        ),
        {'start': start.isoformat()}
    ).fetchall()

    # Build day-keyed buckets
    completed_by_day = defaultdict(int)
    failed_by_day = defaultdict(int)
    for row in rows:
        day, status, cnt = row[0], row[1], row[2]
        if status == 'completed':
            completed_by_day[day] += cnt
        elif status == 'failed':
            failed_by_day[day] += cnt

    labels, completed, failed, total = [], [], [], []
    for i in range(30):
        d = start + timedelta(days=i)
        key = d.isoformat()
        c = completed_by_day.get(key, 0)
        f = failed_by_day.get(key, 0)
        labels.append(d.strftime('%b %-d'))
        completed.append(c)
        failed.append(f)
        total.append(c + f)

    return jsonify({'labels': labels, 'completed': completed, 'failed': failed, 'total': total})


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


def get_database_stats():
    """Get database file statistics and table counts"""
    from flask import current_app
    
    stats = {
        'size_mb': 0,
        'size_human': 'N/A',
        'modified': 'N/A',
        'tables': {}
    }
    
    try:
        # Get database path
        db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
            
            if os.path.exists(db_path):
                # Get file size
                size_bytes = os.path.getsize(db_path)
                stats['size_mb'] = round(size_bytes / (1024 * 1024), 2)
                
                # Human readable size
                if size_bytes < 1024:
                    stats['size_human'] = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    stats['size_human'] = f"{round(size_bytes / 1024, 2)} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    stats['size_human'] = f"{round(size_bytes / (1024 * 1024), 2)} MB"
                else:
                    stats['size_human'] = f"{round(size_bytes / (1024 * 1024 * 1024), 2)} GB"
                
                # Last modified timestamp
                mod_time = os.path.getmtime(db_path)
                stats['modified'] = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        
        # Get table counts
        stats['tables'] = {
            'users': User.query.count(),
            'scans': Scan.query.count(),
            'scan_results': ScanResult.query.count(),
            'audit_logs': AuditLog.query.count(),
            'scan_shares': ScanShare.query.count(),
            'report_logos': ReportLogo.query.count(),
            'system_settings': SystemSettings.query.count()
        }
        
    except Exception as e:
        stats['error'] = str(e)
    
    return stats


def get_health_warnings():
    """Check system health and return warnings"""
    warnings = []
    
    try:
        # Check disk space
        for mount in ['/', '/opt', '/var']:
            try:
                usage = shutil.disk_usage(mount)
                percent = (usage.used / usage.total) * 100
                if percent > 90:
                    warnings.append({
                        'severity': 'danger',
                        'message': f'Critical: {mount} disk space is {round(percent, 1)}% full (< 10% free)'
                    })
                elif percent > 80:
                    warnings.append({
                        'severity': 'warning',
                        'message': f'Warning: {mount} disk space is {round(percent, 1)}% full'
                    })
            except:
                pass
        
        # Check memory usage
        try:
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                warnings.append({
                    'severity': 'danger',
                    'message': f'Critical: Memory usage is {mem.percent}% (< 10% available)'
                })
            elif mem.percent > 80:
                warnings.append({
                    'severity': 'warning',
                    'message': f'Warning: Memory usage is {mem.percent}%'
                })
        except:
            pass
        
        # Check Redis/Celery services
        try:
            from redis import Redis
            from flask import current_app
            redis_url = current_app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
            if '://' in redis_url:
                parts = redis_url.split('://')[1].split('/')
                host_port = parts[0].split(':')
                host = host_port[0] if len(host_port) > 0 else 'localhost'
                port = int(host_port[1]) if len(host_port) > 1 else 6379
            else:
                host, port = 'localhost', 6379
            
            r = Redis(host=host, port=port, socket_connect_timeout=2)
            r.ping()
        except:
            warnings.append({
                'severity': 'danger',
                'message': 'Critical: Redis/Celery broker is not accessible'
            })
        
        # Check database size
        try:
            from flask import current_app
            db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if db_url.startswith('sqlite:///'):
                db_path = db_url.replace('sqlite:///', '')
                if os.path.exists(db_path):
                    size_gb = os.path.getsize(db_path) / (1024 * 1024 * 1024)
                    if size_gb > 1:
                        warnings.append({
                            'severity': 'warning',
                            'message': f'Database file is {round(size_gb, 2)} GB - consider optimization'
                        })
        except:
            pass
        
        # Check for recent scan activity
        try:
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_scans = Scan.query.filter(Scan.started_at >= week_ago).count()
            if recent_scans == 0:
                warnings.append({
                    'severity': 'info',
                    'message': 'No scans have been run in the last 7 days'
                })
        except:
            pass
            
    except Exception as e:
        warnings.append({
            'severity': 'danger',
            'message': f'Error checking system health: {str(e)}'
        })
    
    return warnings


def get_recent_activity():
    """Get 24-hour activity statistics"""
    activity = {
        'scans': {'completed': 0, 'failed': 0, 'running': 0},
        'active_users': 0,
        'last_successful_scan': None,
        'last_failed_scan': None
    }
    
    try:
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # Scan counts by status
        activity['scans']['completed'] = Scan.query.filter(
            Scan.started_at >= yesterday,
            Scan.status == 'completed'
        ).count()
        
        activity['scans']['failed'] = Scan.query.filter(
            Scan.started_at >= yesterday,
            Scan.status == 'failed'
        ).count()
        
        activity['scans']['running'] = Scan.query.filter(
            Scan.started_at >= yesterday,
            Scan.status == 'running'
        ).count()
        
        # Active users
        activity['active_users'] = User.query.filter(
            User.last_login >= yesterday
        ).count()
        
        # Last successful scan
        last_success = Scan.query.filter_by(status='completed').order_by(
            Scan.completed_at.desc()
        ).first()
        if last_success:
            activity['last_successful_scan'] = {
                'id': last_success.id,
                'target': last_success.target,
                'time': last_success.completed_at.strftime('%Y-%m-%d %H:%M:%S') if last_success.completed_at else 'N/A'
            }
        
        # Last failed scan
        last_failed = Scan.query.filter_by(status='failed').order_by(
            Scan.completed_at.desc()
        ).first()
        if last_failed:
            activity['last_failed_scan'] = {
                'id': last_failed.id,
                'target': last_failed.target,
                'time': last_failed.completed_at.strftime('%Y-%m-%d %H:%M:%S') if last_failed.completed_at else 'N/A',
                'error': last_failed.error_message[:100] if last_failed.error_message else 'Unknown error'
            }
            
    except Exception as e:
        activity['error'] = str(e)
    
    return activity


def parse_kast_plugins(kast_path):
    """Parse kast -ls output for plugin details
    
    Expected format:
    ✓ plugin_name (priority: N, type: passive/active)
      Description text (may span multiple lines)
    """
    import subprocess
    
    plugins = []
    error = None
    
    try:
        result = subprocess.run(
            [kast_path, '-ls'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            error = f"Command returned error code {result.returncode}"
            if result.stderr:
                error += f": {result.stderr.strip()}"
            return plugins, error
        
        # Parse output line by line
        # Format: ✓ plugin_name (priority: N, type: passive/active)
        #           Description (indented, may be multi-line)
        lines = result.stdout.split('\n')
        i = 0
        current_plugin = None
        
        while i < len(lines):
            line = lines[i]
            
            # Check if this is a plugin header line (starts with checkmark or plugin name)
            # Format: ✓ plugin_name (priority: N, type: X)
            if line.strip() and (line.strip().startswith('✓') or '(priority:' in line):
                # Save previous plugin if exists
                if current_plugin and current_plugin.get('name'):
                    plugins.append(current_plugin)
                
                # Parse new plugin header
                match = re.match(r'[✓\s]*(\w+)\s*\(priority:\s*(\d+)', line)
                if match:
                    current_plugin = {
                        'name': match.group(1),
                        'priority': int(match.group(2)),
                        'description': ''
                    }
                else:
                    current_plugin = None
            
            # Check if this is a description line (indented)
            elif line.startswith('  ') and current_plugin:
                desc_line = line.strip()
                if desc_line:
                    if current_plugin['description']:
                        current_plugin['description'] += ' ' + desc_line
                    else:
                        current_plugin['description'] = desc_line
            
            # Skip empty lines and headers
            elif not line.strip() or 'Available KAST Plugins' in line:
                pass
            
            i += 1
        
        # Don't forget the last plugin
        if current_plugin and current_plugin.get('name'):
            plugins.append(current_plugin)
        
        if not plugins and result.stdout:
            error = f"Could not parse plugin output. Raw output:\n{result.stdout[:500]}"
            
    except subprocess.TimeoutExpired:
        error = "Command timed out after 5 seconds"
    except Exception as e:
        error = f"Exception during parsing: {str(e)}"
    
    return plugins, error


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
                
                # Parse plugins using helper function (returns tuple: plugins, error)
                plugins, parse_error = parse_kast_plugins(kast_path)
                
                info = {
                    'path': kast_path,
                    'exists': True,
                    'version': version,
                    'plugin_count': len(plugins),
                    'plugins': plugins
                }
                
                # Add error if plugin parsing failed
                if parse_error:
                    info['plugin_error'] = parse_error
                
                return info
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
    
    # Cloud Tools Information (only if cloud configs exist)
    has_cloud_configs = ZapConfiguration.query.filter_by(execution_mode='cloud').count() > 0
    if has_cloud_configs:
        from app.zap_utils import get_cloud_tools_status
        info['cloud_tools'] = get_cloud_tools_status()
    else:
        info['cloud_tools'] = None
    
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
    
    # NEW: Collect enhanced data
    info['database_stats'] = get_database_stats()
    info['health_warnings'] = get_health_warnings()
    info['recent_activity'] = get_recent_activity()
    
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


@bp.route('/quick-action/test-kast', methods=['POST'])
@login_required
@admin_required
def test_kast_cli():
    """Test KAST CLI execution"""
    import subprocess
    
    try:
        kast_path = os.environ.get('KAST_CLI_PATH', '/usr/local/bin/kast')
        
        if not os.path.exists(kast_path):
            return jsonify({
                'success': False,
                'message': f'KAST CLI not found at {kast_path}'
            }), 400
        
        # Test version command
        result = subprocess.run(
            [kast_path, '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'message': f'KAST CLI returned error code {result.returncode}'
            }), 400
        
        version = result.stdout.strip()
        
        # Test plugin list
        result = subprocess.run(
            [kast_path, '-ls'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'message': 'KAST CLI version OK but plugin list failed'
            }), 400
        
        plugin_count = result.stdout.count('(priority:')
        
        # Log the action
        AuditLog.log(
            user_id=current_user.id,
            action='kast_cli_tested',
            resource_type='system',
            details=f'KAST CLI test performed by {current_user.username}'
        )
        
        return jsonify({
            'success': True,
            'message': f'KAST CLI is working correctly!\n\nVersion: {version}\nPlugins found: {plugin_count}'
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'message': 'KAST CLI test timed out after 5 seconds'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error testing KAST CLI: {str(e)}'
        }), 400


@bp.route('/quick-action/backup-database', methods=['POST'])
@login_required
@admin_required
def backup_database():
    """Create database backup"""
    from flask import current_app
    
    try:
        # Get database path
        db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if not db_url.startswith('sqlite:///'):
            return jsonify({
                'success': False,
                'message': 'Backup only supported for SQLite databases'
            }), 400
        
        db_path = db_url.replace('sqlite:///', '')
        
        if not os.path.exists(db_path):
            return jsonify({
                'success': False,
                'message': f'Database file not found: {db_path}'
            }), 400
        
        # Backups live next to the DB so the directory is always writable by the app user.
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        backup_filename = f'kast.db.backup-{timestamp}'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy database file
        shutil.copy2(db_path, backup_path)
        
        # Get backup file size
        backup_size = os.path.getsize(backup_path)
        if backup_size < 1024:
            size_str = f"{backup_size} B"
        elif backup_size < 1024 * 1024:
            size_str = f"{round(backup_size / 1024, 2)} KB"
        else:
            size_str = f"{round(backup_size / (1024 * 1024), 2)} MB"
        
        # Log the action
        AuditLog.log(
            user_id=current_user.id,
            action='database_backed_up',
            resource_type='system',
            details=f'Database backup created by {current_user.username}: {backup_filename}'
        )
        
        return jsonify({
            'success': True,
            'message': f'Database backup created successfully!\n\nFile: {backup_filename}\nSize: {size_str}\nLocation: {backup_dir}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating backup: {str(e)}'
        }), 400


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
