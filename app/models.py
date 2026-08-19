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
    anthropic_api_key_encrypted = db.Column(db.Text, nullable=True)
    ai_model_override = db.Column(db.Text, nullable=True)
    ai_base_url = db.Column(db.Text, nullable=True)

    # Bumped on password reset (and other credential-invalidating events) to kill
    # existing sessions/remember-me cookies. See load_user() in app/__init__.py.
    session_token_version = db.Column(db.Integer, nullable=False, default=0, server_default='0')

    # Relationships
    scans = db.relationship('Scan', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'

    def get_id(self):
        """Return a versioned id so bumping session_token_version invalidates sessions."""
        return f'{self.id}|{self.session_token_version or 0}'

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
    
    # ZAP-specific fields
    zap_plan_id = db.Column(db.Integer, db.ForeignKey('zap_automation_plans.id'))
    zap_config_id = db.Column(db.Integer, db.ForeignKey('zap_configurations.id'))
    zap_execution_mode = db.Column(db.String(20))  # Track which mode was actually used
    
    # CLI command logging
    actual_cli_command = db.Column(db.Text)  # The actual command executed (with all --set args)

    # AI summary options
    generate_ai_summary = db.Column(db.Boolean, default=False, nullable=False, server_default='0')

    # SA annotations
    notes = db.Column(db.Text)
    tags = db.Column(db.Text)  # comma-separated

    # Batch grouping (UUID hex shared by all scans in one batch submission)
    batch_id = db.Column(db.String(36), index=True, nullable=True)

    # Remote execution: NULL = run locally on the kast-web host
    runner_id = db.Column(db.Integer, db.ForeignKey('scan_runners.id'), index=True, nullable=True)

    # Relationships
    results = db.relationship('ScanResult', backref='scan', lazy='dynamic', cascade='all, delete-orphan')
    config_profile = db.relationship('ScanConfigProfile', backref='scans')
    zap_plan = db.relationship('ZapAutomationPlan', backref='scans')
    zap_config = db.relationship('ZapConfiguration', backref='scans')
    runner = db.relationship('ScanRunner', backref='scans')
    
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


class ScanRunner(db.Model):
    """Remote host that executes kast scans over SSH on behalf of kast-web.

    The private key is stored encrypted (Fernet via app.encryption) and decrypted
    only at scan-dispatch time. The SSH user must have permission to run kast at
    kast_binary_path and write under remote_output_root.
    """
    __tablename__ = 'scan_runners'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    hostname = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False, default=22)
    username = db.Column(db.String(80), nullable=False)
    ssh_private_key_encrypted = db.Column(db.Text, nullable=False)
    kast_binary_path = db.Column(db.String(500), nullable=False, default='/usr/local/bin/kast')
    remote_output_root = db.Column(db.String(500), nullable=False, default='/tmp/kast-runs')
    region_label = db.Column(db.String(80))
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ScanRunner {self.name} ({self.username}@{self.hostname}:{self.port})>'


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


class ZapAutomationPlan(db.Model):
    """Model for storing ZAP automation framework plans (YAML)"""
    __tablename__ = 'zap_automation_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    plan_yaml = db.Column(db.Text, nullable=False)
    
    # Access control
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_system_default = db.Column(db.Boolean, default=False)
    allow_power_users = db.Column(db.Boolean, default=True)
    
    # Draft system for power user submissions
    is_draft = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    usage_count = db.Column(db.Integer, default=0)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_zap_plans')
    approver = db.relationship('User', foreign_keys=[approved_by])
    
    def __repr__(self):
        return f'<ZapAutomationPlan {self.id}: {self.name}>'
    
    def can_be_used_by(self, user):
        """Check if user can use this plan"""
        if user.is_admin:
            return True
        if self.is_draft:
            return False  # Drafts not usable
        if user.is_power_user and self.allow_power_users:
            return True
        return False
    
    def to_dict(self):
        """Convert plan to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'plan_yaml': self.plan_yaml,
            'created_by': self.created_by,
            'creator_username': self.creator.username if self.creator else None,
            'is_system_default': self.is_system_default,
            'allow_power_users': self.allow_power_users,
            'is_draft': self.is_draft,
            'approved_by': self.approved_by,
            'approver_username': self.approver.username if self.approver else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'usage_count': self.usage_count
        }


class ZapConfiguration(db.Model):
    """Model for storing ZAP execution environment configurations"""
    __tablename__ = 'zap_configurations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    execution_mode = db.Column(db.String(20), nullable=False)  # local, server, remote, cloud, auto
    
    # Mode-specific configs (stored as encrypted JSON strings)
    local_config_encrypted = db.Column(db.Text)  # Docker settings
    remote_config_encrypted = db.Column(db.Text)  # URL, API key
    cloud_config_encrypted = db.Column(db.Text)  # Provider, credentials
    
    # Spider type passed to kast as --set zap.spider_type=<value>
    # traditional = HTTP spider (no browser); ajax = Firefox/Selenium; client = Playwright
    spider_type = db.Column(db.String(20), nullable=False, default='traditional')

    # Polling interval passed to kast as --set zap.zap_config.poll_interval_seconds=<value>
    poll_interval_seconds = db.Column(db.Integer, nullable=False, default=30)

    # Scan profile passed to kast as --zap-profile <value> (NULL = kast default)
    # Ignored when a custom automation plan is attached to the scan
    zap_profile = db.Column(db.String(20), nullable=True)

    # Settings
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)

    # Phase D: reference to the new cloud credentials table
    cloud_credential_id = db.Column(db.Integer, db.ForeignKey('cloud_credentials.id'), nullable=True)

    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    
    # Relationships
    creator = db.relationship('User', backref='created_zap_configs')
    cloud_credential = db.relationship('CloudCredential', backref='zap_configurations')
    
    def __repr__(self):
        return f'<ZapConfiguration {self.id}: {self.name}>'
    
    @property
    def local_config(self):
        """Decrypt and return local config"""
        if self.local_config_encrypted:
            from app.encryption import decrypt_json
            try:
                return decrypt_json(self.local_config_encrypted)
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    'ZapConfiguration %s local_config decryption failed (key rotation?)', self.id)
                return {}
        return {}

    @property
    def local_config_decryption_failed(self):
        """True if encrypted data exists but cannot be decrypted with the current key."""
        return bool(self.local_config_encrypted) and not self.local_config

    @local_config.setter
    def local_config(self, value):
        """Encrypt and store local config"""
        from app.encryption import encrypt_json
        self.local_config_encrypted = encrypt_json(value)

    @property
    def remote_config(self):
        """Decrypt and return remote config"""
        if self.remote_config_encrypted:
            from app.encryption import decrypt_json
            try:
                return decrypt_json(self.remote_config_encrypted)
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    'ZapConfiguration %s remote_config decryption failed (key rotation?)', self.id)
                return {}
        return {}

    @property
    def remote_config_decryption_failed(self):
        return bool(self.remote_config_encrypted) and not self.remote_config

    @remote_config.setter
    def remote_config(self, value):
        """Encrypt and store remote config"""
        from app.encryption import encrypt_json
        self.remote_config_encrypted = encrypt_json(value)

    @property
    def cloud_config(self):
        """Decrypt and return cloud config"""
        if self.cloud_config_encrypted:
            from app.encryption import decrypt_json
            try:
                return decrypt_json(self.cloud_config_encrypted)
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    'ZapConfiguration %s cloud_config decryption failed (key rotation?)', self.id)
                return {}
        return {}

    @property
    def cloud_config_decryption_failed(self):
        return bool(self.cloud_config_encrypted) and not self.cloud_config

    @cloud_config.setter
    def cloud_config(self, value):
        """Encrypt and store cloud config"""
        from app.encryption import encrypt_json
        self.cloud_config_encrypted = encrypt_json(value)
    
    def to_dict(self, include_sensitive=False):
        """Convert to dict, optionally masking sensitive data"""
        result = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'execution_mode': self.execution_mode,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'created_by': self.created_by,
            'creator_username': self.creator.username if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None
        }
        
        if include_sensitive:
            # Only include decrypted configs for admin users
            result['local_config'] = self.local_config
            result['remote_config'] = self.remote_config
            result['cloud_config'] = self.cloud_config
        else:
            # Mask sensitive values
            result['local_config'] = self._mask_config(self.local_config)
            result['remote_config'] = self._mask_config(self.remote_config)
            result['cloud_config'] = self._mask_config(self.cloud_config)
        
        return result
    
    @staticmethod
    def _mask_config(config):
        """Mask sensitive values in config dict"""
        if not config:
            return {}
        
        masked = config.copy()
        sensitive_keys = ['api_key', 'password', 'secret', 'token', 'credential', 'access_key', 'secret_key']
        
        for key in masked:
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if masked[key]:
                    masked[key] = '********'
        
        return masked


class CloudCredential(db.Model):
    """Encrypted cloud-provider credentials (Phase D)."""
    __tablename__ = 'cloud_credentials'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    provider = db.Column(db.String(20), nullable=False)  # aws, azure, gcp
    credentials_encrypted = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    creator = db.relationship('User', backref='cloud_credentials')

    def __repr__(self):
        return f'<CloudCredential {self.id}: {self.name} ({self.provider})>'

    @property
    def credentials(self):
        if self.credentials_encrypted:
            from app.encryption import decrypt_json
            return decrypt_json(self.credentials_encrypted)
        return {}

    @credentials.setter
    def credentials(self, value):
        from app.encryption import encrypt_json
        self.credentials_encrypted = encrypt_json(value)


class CloudScan(db.Model):
    """Tracks provisioned cloud infrastructure for a scan (Phase D)."""
    __tablename__ = 'cloud_scans'

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), nullable=False, index=True)
    cloud_credential_id = db.Column(db.Integer, db.ForeignKey('cloud_credentials.id'), nullable=False)
    provider = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='provisioning')
    # provisioning, provisioned, scan_running, scan_complete, teardown, torn_down, failed
    zap_url = db.Column(db.String(255))
    zap_api_key_encrypted = db.Column(db.Text)
    terraform_state_path = db.Column(db.String(255))
    error_message = db.Column(db.Text)
    provisioned_at = db.Column(db.DateTime)
    torn_down_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    scan = db.relationship('Scan', backref=db.backref('cloud_scan', uselist=False))
    credential = db.relationship('CloudCredential', backref='cloud_scans')

    def __repr__(self):
        return f'<CloudScan {self.id}: scan={self.scan_id} status={self.status}>'

    @property
    def zap_api_key(self):
        if self.zap_api_key_encrypted:
            from app.encryption import decrypt_value
            return decrypt_value(self.zap_api_key_encrypted)
        return None

    @zap_api_key.setter
    def zap_api_key(self, value):
        from app.encryption import encrypt_value
        self.zap_api_key_encrypted = encrypt_value(value) if value else None


class CloudOrphan(db.Model):
    """Tracks cloud resources that outlived their scan and need cleanup (Phase D)."""
    __tablename__ = 'cloud_orphans'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(20), nullable=False)
    resource_id = db.Column(db.String(255), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False)
    cloud_scan_id = db.Column(db.Integer, db.ForeignKey('cloud_scans.id'), nullable=True)
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    cleanup_attempts = db.Column(db.Integer, default=0)
    last_cleanup_attempt = db.Column(db.DateTime)
    status = db.Column(db.String(20), nullable=False, default='detected')
    # detected, cleanup_pending, cleaning, cleaned, failed
    error_message = db.Column(db.Text)

    cloud_scan = db.relationship('CloudScan', backref='orphans')

    def __repr__(self):
        return f'<CloudOrphan {self.id}: {self.provider}/{self.resource_type}/{self.resource_id}>'


class ZapScanProgress(db.Model):
    """Model for tracking real-time ZAP scan progress"""
    __tablename__ = 'zap_scan_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), unique=True, nullable=False, index=True)
    
    # Progress metrics
    plan_id = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed
    spider_percent = db.Column(db.Integer, default=0)
    active_scan_percent = db.Column(db.Integer, default=0)
    passive_scan_queue = db.Column(db.Integer, default=0)
    
    # Alert counts
    total_alerts = db.Column(db.Integer, default=0)
    critical_alerts = db.Column(db.Integer, default=0)
    high_alerts = db.Column(db.Integer, default=0)
    medium_alerts = db.Column(db.Integer, default=0)
    low_alerts = db.Column(db.Integer, default=0)
    informational_alerts = db.Column(db.Integer, default=0)
    
    # Job tracking
    job_updates = db.Column(db.Text)  # JSON array of job status messages
    warnings = db.Column(db.Text)  # JSON array of warnings
    errors = db.Column(db.Text)  # JSON array of errors
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    last_updated = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Full snapshot (for debugging)
    raw_snapshot = db.Column(db.Text)  # Full JSON from zap_scan_progress.json
    
    # Relationship
    scan = db.relationship('Scan', backref=db.backref('zap_progress', uselist=False))
    
    def __repr__(self):
        return f'<ZapScanProgress {self.id}: Scan {self.scan_id} ({self.status})>'
    
    def to_dict(self):
        """Convert to dictionary"""
        import json
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'plan_id': self.plan_id,
            'status': self.status,
            'progress': {
                'spider_percent': self.spider_percent,
                'active_scan_percent': self.active_scan_percent,
                'passive_scan_queue': self.passive_scan_queue
            },
            'alerts': {
                'total': self.total_alerts,
                'critical': self.critical_alerts,
                'high': self.high_alerts,
                'medium': self.medium_alerts,
                'low': self.low_alerts,
                'informational': self.informational_alerts
            },
            'job_updates': json.loads(self.job_updates) if self.job_updates else [],
            'warnings': json.loads(self.warnings) if self.warnings else [],
            'errors': json.loads(self.errors) if self.errors else [],
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
    
    @staticmethod
    def update_from_snapshot(scan_id, snapshot_data):
        """Update progress from zap_scan_progress.json snapshot"""
        import json
        
        progress = ZapScanProgress.query.filter_by(scan_id=scan_id).first()
        if not progress:
            progress = ZapScanProgress(scan_id=scan_id)
            db.session.add(progress)
        
        # Update fields from snapshot
        progress.plan_id = snapshot_data.get('plan_id')
        progress.status = snapshot_data.get('status', 'running')
        
        # Progress metrics
        prog = snapshot_data.get('progress', {})
        progress.spider_percent = prog.get('spider_percent', 0)
        progress.active_scan_percent = prog.get('active_scan_percent', 0)
        progress.passive_scan_queue = prog.get('passive_scan_queue', 0)
        
        # Alerts
        alerts = snapshot_data.get('alerts', {})
        progress.total_alerts = alerts.get('total', 0)
        by_risk = alerts.get('by_risk', {})
        progress.critical_alerts = by_risk.get('Critical', 0)
        progress.high_alerts = by_risk.get('High', 0)
        progress.medium_alerts = by_risk.get('Medium', 0)
        progress.low_alerts = by_risk.get('Low', 0)
        progress.informational_alerts = by_risk.get('Informational', 0)
        
        # Job updates
        progress.job_updates = json.dumps(snapshot_data.get('job_updates', []))
        progress.warnings = json.dumps(snapshot_data.get('warnings', []))
        progress.errors = json.dumps(snapshot_data.get('errors', []))
        
        # Timestamps
        from datetime import datetime as dt
        if snapshot_data.get('scan_started'):
            try:
                progress.started_at = dt.fromisoformat(snapshot_data['scan_started'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        if snapshot_data.get('last_updated'):
            try:
                progress.last_updated = dt.fromisoformat(snapshot_data['last_updated'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        if snapshot_data.get('finished'):
            try:
                progress.completed_at = dt.fromisoformat(snapshot_data['finished'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        # Store raw snapshot
        progress.raw_snapshot = json.dumps(snapshot_data)

        db.session.commit()
        return progress


class AISettings(db.Model):
    """Singleton row (id=1) storing org-wide AI configuration."""
    __tablename__ = 'ai_settings'

    id = db.Column(db.Integer, primary_key=True)
    ai_enabled = db.Column(db.Boolean, default=False, nullable=False)
    default_mode = db.Column(db.String(10), default='review', nullable=False)  # auto, review
    monthly_budget_tokens = db.Column(db.Integer, default=100000, nullable=False)
    current_period_tokens = db.Column(db.Integer, default=0, nullable=False)
    period_reset_date = db.Column(db.DateTime, nullable=True)
    api_key_encrypted = db.Column(db.Text, nullable=True)
    model_id = db.Column(db.String(100), default='claude-sonnet-4-6', nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    updater = db.relationship('User', backref='ai_settings_updates')

    @classmethod
    def get(cls):
        """Return the singleton row, creating it with defaults if absent."""
        row = cls.query.get(1)
        if row is None:
            row = cls(id=1)
            db.session.add(row)
            db.session.commit()
        return row


class AIModelPreset(db.Model):
    """Admin-managed list of additional AI model IDs available to users."""
    __tablename__ = 'ai_model_presets'

    id         = db.Column(db.Integer, primary_key=True)
    model_id   = db.Column(db.Text, nullable=False)
    label      = db.Column(db.Text, nullable=False)
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AIModelPreset {self.model_id!r}>'


class AIEndpointPreset(db.Model):
    """Admin-managed list of named API endpoint presets available to users."""
    __tablename__ = 'ai_endpoint_presets'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.Text, nullable=False)
    url        = db.Column(db.Text, nullable=False)
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AIEndpointPreset {self.name!r}>'


class AISummary(db.Model):
    """LLM-generated executive summary for a completed scan."""
    __tablename__ = 'ai_summaries'

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), unique=True, nullable=False, index=True)
    prompt_version = db.Column(db.String(50), default='exec_summary_v1', nullable=False)
    raw_text = db.Column(db.Text, nullable=True)
    edited_text = db.Column(db.Text, nullable=True)
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # pending → generating → ready → accepted | error
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    tokens_in = db.Column(db.Integer, default=0)
    tokens_out = db.Column(db.Integer, default=0)
    cost_usd = db.Column(db.Float, default=0.0)
    generated_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    scan = db.relationship('Scan', backref=db.backref('ai_summary', uselist=False))
    reviewer = db.relationship('User', backref='reviewed_ai_summaries')


class PasswordResetToken(db.Model):
    """Single-use, time-bounded password reset token.

    The raw token is never stored; only its SHA-256 hex digest lives in the DB.
    The raw token is delivered once via email and then compared by hash on redemption.
    """
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True)
    requested_ip = db.Column(db.String(45), nullable=True)

    user = db.relationship('User', backref='password_reset_tokens')

    TTL_MINUTES = 60

    @staticmethod
    def _hash(raw_token):
        import hashlib
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    @classmethod
    def create_for(cls, user, ip_address=None):
        """Invalidate outstanding unused tokens for user, then create + return (row, raw_token).

        The raw token is returned only here; after this call, only its hash is retrievable.
        """
        import secrets
        from datetime import timedelta

        # Invalidate any prior outstanding tokens so only the newest is redeemable.
        now = datetime.utcnow()
        cls.query.filter_by(user_id=user.id, used_at=None).update(
            {'used_at': now}, synchronize_session=False
        )

        raw = secrets.token_urlsafe(32)
        row = cls(
            user_id=user.id,
            token_hash=cls._hash(raw),
            expires_at=now + timedelta(minutes=cls.TTL_MINUTES),
            requested_ip=ip_address,
        )
        db.session.add(row)
        return row, raw

    @classmethod
    def find_valid(cls, raw_token):
        """Return the row matching raw_token iff it exists, is unused, and unexpired."""
        import hmac
        if not raw_token:
            return None
        candidate_hash = cls._hash(raw_token)
        row = cls.query.filter_by(token_hash=candidate_hash).first()
        if row is None:
            return None
        if not hmac.compare_digest(row.token_hash, candidate_hash):
            return None
        if row.used_at is not None:
            return None
        if row.expires_at < datetime.utcnow():
            return None
        return row

    def mark_used(self):
        self.used_at = datetime.utcnow()


class PasswordResetAttempt(db.Model):
    """Rate-limiting ledger for /forgot-password requests.

    One row per POST regardless of whether an email was actually sent, so the
    counter can't be gamed by submitting non-existent addresses.
    """
    __tablename__ = 'password_reset_attempts'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    # Stored lowercased. May be empty string if the client submitted no address.
    email = db.Column(db.String(120), nullable=False, index=True, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Windows and thresholds. Tuned conservatively; adjust if we see legitimate friction.
    WINDOW_MINUTES = 60
    MAX_PER_IP = 10
    MAX_PER_EMAIL = 5

    @classmethod
    def is_rate_limited(cls, ip_address, email):
        """Return True if this (ip, email) pair should be throttled."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(minutes=cls.WINDOW_MINUTES)
        norm_email = (email or '').strip().lower()

        ip_count = cls.query.filter(
            cls.ip_address == ip_address,
            cls.created_at >= cutoff,
        ).count()
        if ip_count >= cls.MAX_PER_IP:
            return True

        if norm_email:
            email_count = cls.query.filter(
                cls.email == norm_email,
                cls.created_at >= cutoff,
            ).count()
            if email_count >= cls.MAX_PER_EMAIL:
                return True

        return False

    @classmethod
    def record(cls, ip_address, email):
        row = cls(ip_address=ip_address or '', email=(email or '').strip().lower())
        db.session.add(row)
        return row


class SchemaMigration(db.Model):
    """Records which migration scripts have been applied to this database.

    Created automatically by db.create_all() at startup; also maintained by
    utils/migration_tracker.py so standalone migration scripts can record
    themselves without going through Flask-SQLAlchemy.
    """
    __tablename__ = 'schema_migrations'

    id          = db.Column(db.Integer, primary_key=True)
    script_name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    applied_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<SchemaMigration {self.script_name!r}>'
