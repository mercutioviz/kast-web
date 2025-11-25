"""
Flask-Admin Database Explorer Configuration
Provides admin interface for browsing and managing database tables
"""

from flask import redirect, url_for, request
from flask_login import current_user
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import rules
from wtforms import PasswordField
from app.models import User, Scan, ScanResult, AuditLog, ScanShare, ReportLogo, SystemSettings
from datetime import datetime
import json


class SecureAdminIndexView(AdminIndexView):
    """Custom index view that requires admin authentication"""
    
    @expose('/')
    def index(self):
        """Admin index page"""
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for('auth.login', next=request.url))
        return super(SecureAdminIndexView, self).index()
    
    def is_accessible(self):
        """Check if user can access admin interface"""
        return current_user.is_authenticated and current_user.is_admin


class SecureModelView(ModelView):
    """Base model view with admin authentication"""
    
    def is_accessible(self):
        """Check if user can access this view"""
        return current_user.is_authenticated and current_user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        """Redirect to login if not authorized"""
        return redirect(url_for('auth.login', next=request.url))
    
    # Default settings for all views
    can_export = True
    can_view_details = True
    page_size = 50
    
    # Format datetime columns
    column_formatters = {
        'created_at': lambda v, c, m, p: m.created_at.strftime('%Y-%m-%d %H:%M:%S') if m.created_at else '',
        'updated_at': lambda v, c, m, p: m.updated_at.strftime('%Y-%m-%d %H:%M:%S') if m.updated_at else '',
        'started_at': lambda v, c, m, p: m.started_at.strftime('%Y-%m-%d %H:%M:%S') if m.started_at else '',
        'completed_at': lambda v, c, m, p: m.completed_at.strftime('%Y-%m-%d %H:%M:%S') if m.completed_at else '',
        'timestamp': lambda v, c, m, p: m.timestamp.strftime('%Y-%m-%d %H:%M:%S') if m.timestamp else '',
        'last_login': lambda v, c, m, p: m.last_login.strftime('%Y-%m-%d %H:%M:%S') if m.last_login else '',
        'expires_at': lambda v, c, m, p: m.expires_at.strftime('%Y-%m-%d %H:%M:%S') if m.expires_at else '',
        'executed_at': lambda v, c, m, p: m.executed_at.strftime('%Y-%m-%d %H:%M:%S') if m.executed_at else '',
        'uploaded_at': lambda v, c, m, p: m.uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if m.uploaded_at else '',
        'last_failed_login': lambda v, c, m, p: m.last_failed_login.strftime('%Y-%m-%d %H:%M:%S') if m.last_failed_login else '',
    }


class UserModelView(SecureModelView):
    """User table view with password protection"""
    
    column_list = ['id', 'username', 'email', 'role', 'is_active', 'created_at', 'last_login', 'login_count']
    column_searchable_list = ['username', 'email', 'first_name', 'last_name']
    column_filters = ['role', 'is_active', 'created_at', 'last_login']
    column_sortable_list = ['id', 'username', 'email', 'role', 'is_active', 'created_at', 'last_login', 'login_count']
    column_default_sort = ('created_at', True)
    
    # Exclude password hash from all views
    column_exclude_list = ['password_hash']
    form_excluded_columns = ['password_hash', 'scans', 'audit_logs', 'shared_scans', 'uploaded_logos']
    
    # Add custom password field for editing
    form_extra_fields = {
        'new_password': PasswordField('New Password')
    }
    
    column_descriptions = {
        'role': 'User role: admin, power_user, user, or viewer',
        'is_active': 'Whether the user account is active',
        'login_count': 'Number of successful logins',
        'failed_login_attempts': 'Number of consecutive failed login attempts'
    }
    
    def on_model_change(self, form, model, is_created):
        """Handle password changes"""
        if form.new_password.data:
            model.set_password(form.new_password.data)


class ScanModelView(SecureModelView):
    """Scan table view"""
    
    column_list = ['id', 'target', 'scan_mode', 'status', 'user_id', 'started_at', 'completed_at', 'celery_task_id']
    column_searchable_list = ['target', 'celery_task_id']
    column_filters = ['status', 'scan_mode', 'user_id', 'started_at', 'completed_at']
    column_sortable_list = ['id', 'target', 'scan_mode', 'status', 'user_id', 'started_at', 'completed_at']
    column_default_sort = ('started_at', True)
    
    form_excluded_columns = ['results', 'shares']
    
    column_descriptions = {
        'scan_mode': 'active or passive scan mode',
        'status': 'pending, running, completed, or failed',
        'celery_task_id': 'Background task ID for tracking',
        'plugins': 'Comma-separated list of plugins to run'
    }
    
    # Custom formatters for specific columns
    column_formatters = dict(
        SecureModelView.column_formatters,
        plugins=lambda v, c, m, p: ', '.join(m.plugin_list) if m.plugin_list else '',
        status=lambda v, c, m, p: f'<span class="badge badge-{"success" if m.status == "completed" else "danger" if m.status == "failed" else "warning" if m.status == "running" else "secondary"}">{m.status}</span>',
    )
    
    column_formatters_detail = column_formatters


class ScanResultModelView(SecureModelView):
    """Scan result table view"""
    
    column_list = ['id', 'scan_id', 'plugin_name', 'status', 'findings_count', 'executed_at']
    column_searchable_list = ['plugin_name']
    column_filters = ['status', 'scan_id', 'plugin_name', 'executed_at']
    column_sortable_list = ['id', 'scan_id', 'plugin_name', 'status', 'findings_count', 'executed_at']
    column_default_sort = ('executed_at', True)
    
    column_descriptions = {
        'status': 'success, fail, or skipped',
        'findings_count': 'Number of findings/issues detected',
        'raw_output_path': 'Path to raw plugin output file',
        'processed_output_path': 'Path to processed output file'
    }
    
    column_formatters = dict(
        SecureModelView.column_formatters,
        status=lambda v, c, m, p: f'<span class="badge badge-{"success" if m.status == "success" else "danger" if m.status == "fail" else "secondary"}">{m.status}</span>',
    )


class AuditLogModelView(SecureModelView):
    """Audit log table view - read only"""
    
    can_create = False
    can_edit = False
    can_delete = False
    
    column_list = ['id', 'user_id', 'action', 'resource_type', 'resource_id', 'timestamp', 'ip_address']
    column_searchable_list = ['action', 'resource_type', 'details', 'ip_address']
    column_filters = ['action', 'resource_type', 'user_id', 'timestamp']
    column_sortable_list = ['id', 'user_id', 'action', 'resource_type', 'resource_id', 'timestamp']
    column_default_sort = ('timestamp', True)
    
    column_descriptions = {
        'action': 'Action performed by the user',
        'resource_type': 'Type of resource affected (user, scan, system, etc.)',
        'resource_id': 'ID of the affected resource',
        'details': 'Additional details about the action'
    }


class ScanShareModelView(SecureModelView):
    """Scan share table view"""
    
    column_list = ['id', 'scan_id', 'shared_with_user_id', 'permission_level', 'created_at', 'expires_at']
    column_searchable_list = ['share_token']
    column_filters = ['permission_level', 'scan_id', 'shared_with_user_id', 'created_at', 'expires_at']
    column_sortable_list = ['id', 'scan_id', 'permission_level', 'created_at', 'expires_at']
    column_default_sort = ('created_at', True)
    
    form_excluded_columns = ['scan', 'shared_with_user', 'creator']
    
    column_descriptions = {
        'shared_with_user_id': 'User ID (NULL for public shares)',
        'permission_level': 'view or edit',
        'share_token': 'Token for public link shares',
        'expires_at': 'When the share expires (NULL = never)'
    }


class ReportLogoModelView(SecureModelView):
    """Report logo table view"""
    
    column_list = ['id', 'name', 'filename', 'mime_type', 'file_size', 'uploaded_by', 'uploaded_at']
    column_searchable_list = ['name', 'filename', 'description']
    column_filters = ['mime_type', 'uploaded_by', 'uploaded_at']
    column_sortable_list = ['id', 'name', 'filename', 'file_size', 'uploaded_at']
    column_default_sort = ('uploaded_at', True)
    
    form_excluded_columns = ['uploader']
    
    column_descriptions = {
        'name': 'Friendly name for the logo',
        'file_path': 'Server path to the logo file',
        'mime_type': 'MIME type of the uploaded file',
        'file_size': 'File size in bytes'
    }
    
    column_formatters = dict(
        SecureModelView.column_formatters,
        file_size=lambda v, c, m, p: f'{m.file_size / 1024:.1f} KB' if m.file_size else '0 KB',
    )


class SystemSettingsModelView(SecureModelView):
    """System settings table view"""
    
    column_list = ['id', 'key', 'value', 'value_type', 'description', 'updated_at']
    column_searchable_list = ['key', 'value', 'description']
    column_filters = ['value_type', 'updated_at']
    column_sortable_list = ['id', 'key', 'value_type', 'updated_at']
    column_default_sort = ('key', False)
    
    column_descriptions = {
        'key': 'Setting key/name',
        'value': 'Setting value (stored as text)',
        'value_type': 'Data type: string, int, bool, or json',
        'description': 'Description of what this setting controls'
    }
    
    # Show value formatting in detail view
    column_formatters_detail = dict(
        SecureModelView.column_formatters,
        value=lambda v, c, m, p: f'<pre>{json.dumps(json.loads(m.value), indent=2)}</pre>' if m.value_type == 'json' else m.value,
    )


def init_admin(app, db):
    """Initialize Flask-Admin with the app"""
    
    # Create admin instance with custom index view
    admin = Admin(
        app,
        name='KAST Database Explorer',
        template_mode='bootstrap4',
        index_view=SecureAdminIndexView(
            name='Database Home',
            endpoint='db_admin',
            url='/admin/database'
        ),
        base_template='admin/db_base.html',
        url='/admin/database'
    )
    
    # Add model views
    admin.add_view(UserModelView(User, db.session, name='Users', category='Core Tables'))
    admin.add_view(ScanModelView(Scan, db.session, name='Scans', category='Core Tables'))
    admin.add_view(ScanResultModelView(ScanResult, db.session, name='Scan Results', category='Core Tables'))
    admin.add_view(AuditLogModelView(AuditLog, db.session, name='Audit Logs', category='Core Tables'))
    admin.add_view(ScanShareModelView(ScanShare, db.session, name='Scan Shares', category='Features'))
    admin.add_view(ReportLogoModelView(ReportLogo, db.session, name='Report Logos', category='Features'))
    admin.add_view(SystemSettingsModelView(SystemSettings, db.session, name='System Settings', category='Configuration'))
    
    return admin
