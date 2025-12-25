from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    """Model for user accounts"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    role = db.Column(db.String(20), nullable=False, default='user')  # admin, power_user, user, viewer
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    login_count = db.Column(db.Integer, default=0)
    failed_login_attempts = db.Column(db.Integer, default=0)
    last_failed_login = db.Column(db.DateTime)
    
    # Relationships
    scans = db.relationship('Scan', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        """Check if user is admin"""
        return self.role == 'admin'
    
    @property
    def is_power_user(self):
        """Check if user is power user"""
        return self.role == 'power_user'
    
    @property
    def can_run_active_scans(self):
        """Check if user can run active scans"""
        return self.role in ('admin', 'power_user')
    
    def to_dict(self):
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'login_count': self.login_count
        }


class Scan(db.Model):
    """Model for storing scan information"""
    __tablename__ = 'scans'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    target = db.Column(db.String(255), nullable=False, index=True)
    scan_mode = db.Column(db.String(20), nullable=False, default='passive')  # active or passive
    plugins = db.Column(db.Text)  # Comma-separated list of plugins
    parallel = db.Column(db.Boolean, default=False)
    verbose = db.Column(db.Boolean, default=False)
    dry_run = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, running, completed, failed
    output_dir = db.Column(db.String(500))
    config_json = db.Column(db.Text)  # JSON string of full configuration
    error_message = db.Column(db.Text)
    celery_task_id = db.Column(db.String(255))  # Celery task ID for tracking
    started_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime)
    logo_id = db.Column(db.Integer, db.ForeignKey('report_logos.id'), nullable=True)  # NULL = use system default
    execution_log_path = db.Column(db.String(500))  # Path to full KAST execution log
    source = db.Column(db.String(20), default='web')  # 'web' = GUI-executed, 'imported' = CLI-imported
    config_profile_id = db.Column(db.Integer, db.ForeignKey('scan_config_profiles.id'), nullable=True)  # NULL = use system default
    config_overrides = db.Column(db.Text)  # JSON dict of --set overrides (admin/power_user only)
    
    # Relationships
    results = db.relationship('ScanResult', backref='scan', lazy='dynamic', cascade='all, delete-orphan')
    config_profile = db.relationship('ScanConfigProfile', backref='scans')
    
    def __repr__(self):
        return f'<Scan {self.id}: {self.target} ({self.status})>'
    
    @property
    def duration(self):
        """Calculate scan duration"""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None
    
    @property
    def plugin_list(self):
        """Return plugins as a list"""
        if self.plugins:
            return [p.strip() for p in self.plugins.split(',')]
        return []
    
    def get_cli_command(self, kast_cli_path):
        """
        Reconstruct the KAST CLI command that was/will be executed for this scan
        
        Args:
            kast_cli_path: Path to KAST CLI executable from config
        
        Returns:
            str: Formatted CLI command with line breaks
        """
        # Start building command parts
        cmd_parts = [kast_cli_path]
        cmd_parts.extend(['-t', self.target])
        cmd_parts.extend(['-m', self.scan_mode])
        cmd_parts.extend(['--format', 'both'])
        
        # Add config profile if used
        if self.config_profile_id and self.config_profile:
            cmd_parts.extend(['--config', f'{self.config_profile.name}.yaml'])
        
        # Add config overrides if specified
        if self.config_overrides:
            overrides = [o.strip() for o in self.config_overrides.split(',') if o.strip()]
            for override in overrides:
                cmd_parts.extend(['--set', override])
        
        # Add logo if used
        if self.logo_id:
            cmd_parts.extend(['--logo', '<logo_file>'])
        
        # Add plugins if specified
        if self.plugins:
            cmd_parts.extend(['--run-only', ','.join(self.plugin_list)])
        
        # Add parallel execution
        if self.parallel:
            cmd_parts.append('-p')
            cmd_parts.extend(['--max-workers', '5'])
        
        # Add verbose flag
        if self.verbose:
            cmd_parts.append('-v')
        
        # Add dry-run flag
        if self.dry_run:
            cmd_parts.append('--dry-run')
        
        # Add output directory
        if self.output_dir:
            cmd_parts.extend(['-o', self.output_dir])
        
        # Format with line breaks (use backslash continuation)
        formatted_cmd = cmd_parts[0] + ' \\\n'
        for i, part in enumerate(cmd_parts[1:], 1):
            formatted_cmd += f'  {part}'
            if i < len(cmd_parts) - 1:
                formatted_cmd += ' \\\n'
        
        return formatted_cmd
    
    def to_dict(self):
        """Convert scan to dictionary"""
        return {
            'id': self.id,
            'target': self.target,
            'scan_mode': self.scan_mode,
            'plugins': self.plugin_list,
            'parallel': self.parallel,
            'verbose': self.verbose,
            'dry_run': self.dry_run,
            'status': self.status,
            'output_dir': self.output_dir,
            'error_message': self.error_message,
            'celery_task_id': self.celery_task_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration': self.duration,
            'source': self.source
        }

class ScanResult(db.Model):
    """Model for storing individual plugin results"""
    __tablename__ = 'scan_results'
    
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), nullable=False, index=True)
    plugin_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # success, fail, skipped
    findings_count = db.Column(db.Integer, default=0)
    raw_output_path = db.Column(db.String(500))
    processed_output_path = db.Column(db.String(500))
    error_message = db.Column(db.Text)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ScanResult {self.id}: {self.plugin_name} ({self.status})>'
    
    def to_dict(self):
        """Convert result to dictionary"""
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'plugin_name': self.plugin_name,
            'status': self.status,
            'findings_count': self.findings_count,
            'raw_output_path': self.raw_output_path,
            'processed_output_path': self.processed_output_path,
            'error_message': self.error_message,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None
        }


class AuditLog(db.Model):
    """Model for audit logging system actions"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    resource_type = db.Column(db.String(50), index=True)  # user, scan, system, etc.
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    user = db.relationship('User', backref='audit_logs')
    
    def __repr__(self):
        return f'<AuditLog {self.id}: {self.action} by User {self.user_id}>'
    
    @staticmethod
    def log(user_id, action, resource_type=None, resource_id=None, details=None, ip_address=None, user_agent=None):
        """Convenience method to create audit log entry"""
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry
    
    def to_dict(self):
        """Convert audit log to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class ScanShare(db.Model):
    """Model for sharing scans with users or via public links"""
    __tablename__ = 'scan_shares'
    
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), nullable=False, index=True)
    shared_with_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # NULL for public shares
    permission_level = db.Column(db.String(20), nullable=False)  # 'view' or 'edit'
    share_token = db.Column(db.String(64), unique=True, index=True)  # For public link shares
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expires_at = db.Column(db.DateTime, index=True)  # NULL = never expires
    
    # Relationships
    scan = db.relationship('Scan', backref='shares')
    shared_with_user = db.relationship('User', foreign_keys=[shared_with_user_id], backref='shared_scans')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        if self.is_public():
            return f'<ScanShare {self.id}: Public link for Scan {self.scan_id}>'
        return f'<ScanShare {self.id}: Scan {self.scan_id} shared with User {self.shared_with_user_id}>'
    
    def is_expired(self):
        """Check if share has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_public(self):
        """Check if this is a public share"""
        return self.shared_with_user_id is None
    
    @staticmethod
    def generate_token():
        """Generate unique share token"""
        import secrets
        return secrets.token_urlsafe(48)
    
    def to_dict(self):
        """Convert share to dictionary"""
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'shared_with_user_id': self.shared_with_user_id,
            'shared_with_username': self.shared_with_user.username if self.shared_with_user else None,
            'permission_level': self.permission_level,
            'share_token': self.share_token,
            'created_by': self.created_by,
            'creator_username': self.creator.username if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired(),
            'is_public': self.is_public()
        }


class ReportLogo(db.Model):
    """Model for storing report logo files for white-labeling"""
    __tablename__ = 'report_logos'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    uploader = db.relationship('User', backref='uploaded_logos')
    
    def __repr__(self):
        return f'<ReportLogo {self.id}: {self.name}>'
    
    def to_dict(self):
        """Convert logo to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'filename': self.filename,
            'file_path': self.file_path,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'uploaded_by': self.uploaded_by,
            'uploader_username': self.uploader.username if self.uploader else None,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }


class ScanConfigProfile(db.Model):
    """Model for storing reusable scan configuration profiles"""
    __tablename__ = 'scan_config_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    config_yaml = db.Column(db.Text, nullable=False)
    
    # Access Control
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    allow_standard_users = db.Column(db.Boolean, default=False)
    is_system_default = db.Column(db.Boolean, default=False)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', backref='created_configs')
    
    def __repr__(self):
        return f'<ScanConfigProfile {self.id}: {self.name}>'
    
    def can_be_used_by(self, user):
        """Check if a user can use this config profile"""
        # Admins can use anything
        if user.is_admin:
            return True
        
        # Power users can use anything
        if user.is_power_user:
            return True
        
        # Standard users can only use profiles marked as allowed
        if user.role == 'user':
            return self.allow_standard_users
        
        # Viewers can't create scans anyway
        return False
    
    def to_dict(self):
        """Convert config profile to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'config_yaml': self.config_yaml,
            'created_by': self.created_by,
            'creator_username': self.creator.username if self.creator else None,
            'allow_standard_users': self.allow_standard_users,
            'is_system_default': self.is_system_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class SystemSettings(db.Model):
    """Model for storing system-wide settings"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default='string')  # string, int, bool, json
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def __repr__(self):
        return f'<SystemSettings {self.key}={self.value}>'
    
    @staticmethod
    def get_settings():
        """Get all settings as a dictionary"""
        settings = {}
        for setting in SystemSettings.query.all():
            if setting.value_type == 'bool':
                settings[setting.key] = setting.value.lower() == 'true'
            elif setting.value_type == 'int':
                settings[setting.key] = int(setting.value)
            elif setting.value_type == 'json':
                import json
                settings[setting.key] = json.loads(setting.value)
            else:
                settings[setting.key] = setting.value
        return settings
    
    @staticmethod
    def get_setting(key, default=None):
        """Get a single setting value"""
        setting = SystemSettings.query.filter_by(key=key).first()
        if not setting:
            return default
        
        if setting.value_type == 'bool':
            return setting.value.lower() == 'true'
        elif setting.value_type == 'int':
            return int(setting.value)
        elif setting.value_type == 'json':
            import json
            return json.loads(setting.value)
        return setting.value
    
    @staticmethod
    def set_setting(key, value, value_type='string', description=None, user_id=None):
        """Set a single setting value"""
        setting = SystemSettings.query.filter_by(key=key).first()
        
        # Convert value to string for storage
        if value_type == 'bool':
            str_value = 'true' if value else 'false'
        elif value_type == 'json':
            import json
            str_value = json.dumps(value)
        else:
            str_value = str(value)
        
        if setting:
            setting.value = str_value
            setting.value_type = value_type
            setting.updated_at = datetime.utcnow()
            if user_id:
                setting.updated_by = user_id
        else:
            setting = SystemSettings(
                key=key,
                value=str_value,
                value_type=value_type,
                description=description,
                updated_by=user_id
            )
            db.session.add(setting)
        
        db.session.commit()
        return setting
    
    @staticmethod
    def update_settings(settings_dict, user_id=None):
        """Update multiple settings at once"""
        for key, value in settings_dict.items():
            # Determine type
            if isinstance(value, bool):
                value_type = 'bool'
            elif isinstance(value, int):
                value_type = 'int'
            elif isinstance(value, (dict, list)):
                value_type = 'json'
            else:
                value_type = 'string'
            
            SystemSettings.set_setting(key, value, value_type, user_id=user_id)
