import re

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SelectMultipleField, SubmitField, IntegerField, PasswordField, TextAreaField, FieldList, FormField
from wtforms.validators import DataRequired, Regexp, Length, NumberRange, Email, EqualTo, ValidationError, Optional
from wtforms.widgets import CheckboxInput, ListWidget
from app.cloud_provider_data import (
    AWS_REGIONS, AWS_INSTANCE_TYPES,
    AZURE_REGIONS, AZURE_VM_SIZES,
    GCP_REGIONS, GCP_MACHINE_TYPES
)

# Shared target regex (domain name, optional :port). Used by ScanConfigForm.target
# and BatchScanForm.targets per-line validation.
TARGET_REGEX = re.compile(
    r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*'
    r'(:\d{1,5})?$'
)

MAX_BATCH_TARGETS = 50


def parse_batch_targets(raw):
    """
    Split a batch-targets textarea into a list.

    Returns (clean_targets, duplicates, line_errors) where:
      clean_targets — deduplicated list in original order
      duplicates    — list of targets that appeared more than once (each listed once)
      line_errors   — list of (line_number, line_text) for lines that fail the regex
    """
    seen = set()
    clean = []
    duplicates = []
    line_errors = []
    for idx, raw_line in enumerate((raw or '').splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if not TARGET_REGEX.match(line):
            line_errors.append((idx, line))
            continue
        if line in seen:
            if line not in duplicates:
                duplicates.append(line)
            continue
        seen.add(line)
        clean.append(line)
    return clean, duplicates, line_errors

def _validate_password_complexity(form, field):
    p = field.data or ''
    errors = []
    if not any(c.isupper() for c in p):
        errors.append('one uppercase letter')
    if not any(c.islower() for c in p):
        errors.append('one lowercase letter')
    if not any(c.isdigit() for c in p):
        errors.append('one digit')
    if errors:
        raise ValidationError(f'Password must contain at least: {", ".join(errors)}.')


class MultiCheckboxField(SelectMultipleField):
    """Custom field for multiple checkboxes"""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class ScanConfigForm(FlaskForm):
    """Form for configuring a new scan"""
    
    target = StringField(
        'Target Domain',
        validators=[
            DataRequired(message='Target domain is required'),
            Length(min=3, max=255, message='Domain must be between 3 and 255 characters'),
            Regexp(
                r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*(:\d{1,5})?$',
                message='Please enter a valid domain or host:port (e.g., example.com or 127.0.0.1:8080)'
            )
        ],
        render_kw={'placeholder': 'example.com', 'class': 'form-control'}
    )
    
    scan_mode = SelectField(
        'Scan Mode',
        choices=[
            ('passive', 'Passive - Non-intrusive reconnaissance'),
            ('active', 'Active - Direct interaction with target')
        ],
        default='passive',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    plugins = MultiCheckboxField(
        'Select Plugins',
        choices=[],  # Will be populated dynamically
        render_kw={'class': 'form-check-input'}
    )
    
    parallel = BooleanField(
        'Run plugins in parallel',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    verbose = BooleanField(
        'Verbose output',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    dry_run = BooleanField(
        'Dry run (preview only)',
        default=False,
        render_kw={'class': 'form-check-input'}
    )

    generate_ai_summary = BooleanField(
        'Auto-generate AI executive summary after scan',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    max_workers = IntegerField(
        'Max Workers',
        default=5,
        validators=[
            NumberRange(
                min=1, 
                max=32, 
                message='Max workers must be between 1 and 32'
            )
        ],
        render_kw={
            'class': 'form-control',
            'min': '1',
            'max': '32',
            'placeholder': '5'
        }
    )
    
    logo_id = SelectField(
        'Report Logo',
        coerce=int,
        choices=[],  # Will be populated dynamically
        render_kw={'class': 'form-select'}
    )
    
    config_profile_id = SelectField(
        'Configuration Profile',
        coerce=int,
        choices=[],  # Will be populated dynamically based on user role
        render_kw={'class': 'form-select'}
    )
    
    config_overrides = StringField(
        'Configuration Overrides (Advanced)',
        validators=[
            Length(max=1000, message='Overrides must not exceed 1000 characters')
        ],
        render_kw={
            'placeholder': 'e.g., plugins.katana.rate_limit=50,plugins.ftap.concurrency=5',
            'class': 'form-control font-monospace'
        }
    )
    
    # ZAP-specific configuration (optional, shown only when ZAP is selected)
    zap_plan_id = SelectField(
        'ZAP Automation Plan',
        coerce=int,
        validators=[Optional()],  # Optional since not all users can access this
        choices=[],  # Populated dynamically based on user role
        render_kw={
            'class': 'form-select',
            'data-plugin': 'zap'  # For conditional display via JavaScript
        }
    )
    
    zap_config_id = SelectField(
        'ZAP Execution Configuration',
        coerce=int,
        validators=[Optional()],  # Optional since ZAP plugin may not be selected
        choices=[],  # Populated dynamically from ZapConfiguration
        render_kw={
            'class': 'form-select',
            'data-plugin': 'zap'  # For conditional display via JavaScript
        }
    )

    runner_id = SelectField(
        'Run on',
        coerce=int,
        validators=[Optional()],
        choices=[(0, 'Local (this host)')],  # Populated dynamically with enabled ScanRunners
        default=0,
        render_kw={'class': 'form-select'},
    )

    submit = SubmitField('Start Scan', render_kw={'class': 'btn btn-primary btn-lg'})


def _validate_batch_targets(form, field):
    """Validator for BatchScanForm.targets — count, per-line regex, dedupe is informational."""
    clean, _duplicates, line_errors = parse_batch_targets(field.data)
    if line_errors:
        bad = ', '.join(f'line {n} ("{t}")' for n, t in line_errors[:5])
        more = '' if len(line_errors) <= 5 else f' (+{len(line_errors) - 5} more)'
        raise ValidationError(f'Invalid target on {bad}{more}.')
    if not clean:
        raise ValidationError('Enter at least one target (one per line).')
    if len(clean) > MAX_BATCH_TARGETS:
        raise ValidationError(
            f'Too many targets: {len(clean)} (max {MAX_BATCH_TARGETS}).'
        )


class BatchScanForm(FlaskForm):
    """Form for configuring a batch scan (multiple targets, identical settings)."""

    targets = TextAreaField(
        'Targets (one per line)',
        validators=[
            DataRequired(message='At least one target is required'),
            _validate_batch_targets,
        ],
        render_kw={
            'placeholder': 'example.com\n10.0.0.1:8080\nstaging.example.com',
            'class': 'form-control font-monospace',
            'rows': '8',
        },
    )

    scan_mode = SelectField(
        'Scan Mode',
        choices=[
            ('passive', 'Passive - Non-intrusive reconnaissance'),
            ('active', 'Active - Direct interaction with target'),
        ],
        default='passive',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'},
    )

    plugins = MultiCheckboxField(
        'Select Plugins',
        choices=[],
        render_kw={'class': 'form-check-input'},
    )

    parallel = BooleanField(
        'Run plugins in parallel',
        default=True,
        render_kw={'class': 'form-check-input'},
    )

    verbose = BooleanField(
        'Verbose output',
        default=True,
        render_kw={'class': 'form-check-input'},
    )

    dry_run = BooleanField(
        'Dry run (preview only)',
        default=False,
        render_kw={'class': 'form-check-input'},
    )

    generate_ai_summary = BooleanField(
        'Auto-generate AI executive summary after scan',
        default=False,
        render_kw={'class': 'form-check-input'},
    )

    max_workers = IntegerField(
        'Max Workers',
        default=5,
        validators=[
            NumberRange(min=1, max=32, message='Max workers must be between 1 and 32'),
        ],
        render_kw={'class': 'form-control', 'min': '1', 'max': '32', 'placeholder': '5'},
    )

    logo_id = SelectField(
        'Report Logo',
        coerce=int,
        choices=[],
        render_kw={'class': 'form-select'},
    )

    config_profile_id = SelectField(
        'Configuration Profile',
        coerce=int,
        choices=[],
        render_kw={'class': 'form-select'},
    )

    config_overrides = StringField(
        'Configuration Overrides (Advanced)',
        validators=[
            Length(max=1000, message='Overrides must not exceed 1000 characters'),
        ],
        render_kw={
            'placeholder': 'e.g., plugins.katana.rate_limit=50,plugins.ftap.concurrency=5',
            'class': 'form-control font-monospace',
        },
    )

    zap_plan_id = SelectField(
        'ZAP Automation Plan',
        coerce=int,
        validators=[Optional()],
        choices=[],
        render_kw={'class': 'form-select', 'data-plugin': 'zap'},
    )

    zap_config_id = SelectField(
        'ZAP Execution Configuration',
        coerce=int,
        validators=[Optional()],
        choices=[],
        render_kw={'class': 'form-select', 'data-plugin': 'zap'},
    )

    runner_id = SelectField(
        'Run on',
        coerce=int,
        validators=[Optional()],
        choices=[(0, 'Local (this host)')],
        default=0,
        render_kw={'class': 'form-select'},
    )

    submit = SubmitField('Start Batch', render_kw={'class': 'btn btn-primary btn-lg'})


class LoginForm(FlaskForm):
    """Form for user login"""
    
    username = StringField(
        'Username',
        validators=[
            DataRequired(message='Username is required'),
            Length(min=3, max=80, message='Username must be between 3 and 80 characters')
        ],
        render_kw={'placeholder': 'Enter your username', 'class': 'form-control', 'autocomplete': 'username'}
    )
    
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='Password is required')
        ],
        render_kw={'placeholder': 'Enter your password', 'class': 'form-control', 'autocomplete': 'current-password'}
    )
    
    remember_me = BooleanField(
        'Remember Me',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    submit = SubmitField('Login', render_kw={'class': 'btn btn-primary w-100'})


class RegistrationForm(FlaskForm):
    """Form for user registration (admin only)"""
    
    username = StringField(
        'Username',
        validators=[
            DataRequired(message='Username is required'),
            Length(min=3, max=80, message='Username must be between 3 and 80 characters'),
            Regexp(r'^[a-zA-Z0-9_-]+$', message='Username can only contain letters, numbers, underscores, and hyphens')
        ],
        render_kw={'placeholder': 'Enter username', 'class': 'form-control', 'autocomplete': 'username'}
    )
    
    email = StringField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Please enter a valid email address'),
            Length(max=120, message='Email must not exceed 120 characters')
        ],
        render_kw={'placeholder': 'user@example.com', 'class': 'form-control', 'autocomplete': 'email'}
    )
    
    first_name = StringField(
        'First Name',
        validators=[
            Length(max=100, message='First name must not exceed 100 characters')
        ],
        render_kw={'placeholder': 'First name (optional)', 'class': 'form-control', 'autocomplete': 'given-name'}
    )
    
    last_name = StringField(
        'Last Name',
        validators=[
            Length(max=100, message='Last name must not exceed 100 characters')
        ],
        render_kw={'placeholder': 'Last name (optional)', 'class': 'form-control', 'autocomplete': 'family-name'}
    )
    
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='Password is required'),
            Length(min=8, max=128, message='Password must be between 8 and 128 characters'),
            _validate_password_complexity
        ],
        render_kw={'placeholder': 'Enter password', 'class': 'form-control', 'autocomplete': 'new-password'}
    )
    
    password_confirm = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(message='Please confirm your password'),
            EqualTo('password', message='Passwords must match')
        ],
        render_kw={'placeholder': 'Confirm password', 'class': 'form-control', 'autocomplete': 'new-password'}
    )
    
    role = SelectField(
        'Role',
        choices=[
            ('user', 'User - Can create and manage own scans (passive only)'),
            ('power_user', 'Power User - Can run active and passive scans'),
            ('admin', 'Admin - Full system access'),
            ('viewer', 'Viewer - Read-only access')
        ],
        default='user',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    is_active = BooleanField(
        'Account Active',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    submit = SubmitField('Create User', render_kw={'class': 'btn btn-primary'})
    
    def validate_username(self, username):
        """Check if username already exists"""
        from app.models import User
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        """Check if email already exists"""
        from app.models import User
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email address.')


class ChangePasswordForm(FlaskForm):
    """Form for changing password"""
    
    current_password = PasswordField(
        'Current Password',
        validators=[
            DataRequired(message='Current password is required')
        ],
        render_kw={'placeholder': 'Enter current password', 'class': 'form-control', 'autocomplete': 'current-password'}
    )
    
    new_password = PasswordField(
        'New Password',
        validators=[
            DataRequired(message='New password is required'),
            Length(min=8, max=128, message='Password must be between 8 and 128 characters'),
            _validate_password_complexity
        ],
        render_kw={'placeholder': 'Enter new password', 'class': 'form-control', 'autocomplete': 'new-password'}
    )
    
    new_password_confirm = PasswordField(
        'Confirm New Password',
        validators=[
            DataRequired(message='Please confirm your new password'),
            EqualTo('new_password', message='Passwords must match')
        ],
        render_kw={'placeholder': 'Confirm new password', 'class': 'form-control', 'autocomplete': 'new-password'}
    )
    
    submit = SubmitField('Change Password', render_kw={'class': 'btn btn-primary'})


class ShareWithUserForm(FlaskForm):
    """Form for sharing a scan with a specific user"""
    
    user_id = SelectField(
        'User',
        coerce=int,
        validators=[DataRequired(message='Please select a user')],
        render_kw={'class': 'form-select'}
    )
    
    permission_level = SelectField(
        'Permission Level',
        choices=[
            ('view', 'View Only - Can view scan details and reports'),
            ('edit', 'Can Edit - Can also regenerate reports and re-run scans')
        ],
        default='view',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    expires_in_days = IntegerField(
        'Expires in (days)',
        default=0,
        validators=[
            NumberRange(min=0, max=365, message='Expiration must be between 0 and 365 days')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '0 = Never expires',
            'min': '0',
            'max': '365'
        }
    )
    
    submit = SubmitField('Share with User', render_kw={'class': 'btn btn-primary'})


class GeneratePublicLinkForm(FlaskForm):
    """Form for generating a public sharing link"""
    
    expires_in_days = IntegerField(
        'Expires in (days)',
        default=7,
        validators=[
            NumberRange(min=1, max=365, message='Expiration must be between 1 and 365 days')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '7',
            'min': '1',
            'max': '365'
        }
    )
    
    submit = SubmitField('Generate Public Link', render_kw={'class': 'btn btn-success'})


class TransferOwnershipForm(FlaskForm):
    """Form for transferring scan ownership to another user"""
    
    new_owner_id = SelectField(
        'New Owner',
        coerce=int,
        validators=[DataRequired(message='Please select a new owner')],
        render_kw={'class': 'form-select'}
    )
    
    submit = SubmitField('Transfer Ownership', render_kw={'class': 'btn btn-warning'})


class ImportScanForm(FlaskForm):
    """Form for importing CLI scan results into KAST-Web"""
    
    scan_directory = StringField(
        'Scan Results Directory',
        validators=[
            DataRequired(message='Directory path is required'),
            Length(min=1, max=500, message='Path must not exceed 500 characters')
        ],
        render_kw={
            'placeholder': '/home/user/kast_results/example.com-20250101-120000',
            'class': 'form-control'
        }
    )
    
    assign_to_user = SelectField(
        'Assign to User',
        coerce=int,
        choices=[],  # Will be populated dynamically
        validators=[DataRequired(message='Please select a user')],
        render_kw={'class': 'form-select'}
    )
    
    submit = SubmitField('Import Scan', render_kw={'class': 'btn btn-success'})


class ScanRunnerForm(FlaskForm):
    """Form for registering / editing a remote scan runner (admin only)."""

    name = StringField(
        'Name',
        validators=[
            DataRequired(message='Name is required'),
            Length(min=1, max=80),
            Regexp(r'^[A-Za-z0-9 _.\-]+$', message='Letters, digits, spaces, dot, underscore, dash only'),
        ],
        render_kw={'class': 'form-control', 'placeholder': 'e.g. canada-1'},
    )
    hostname = StringField(
        'Hostname or IP',
        validators=[DataRequired(), Length(max=255)],
        render_kw={'class': 'form-control', 'placeholder': '3.99.130.11'},
    )
    port = IntegerField(
        'SSH Port',
        default=22,
        validators=[NumberRange(min=1, max=65535)],
        render_kw={'class': 'form-control'},
    )
    username = StringField(
        'SSH Username',
        validators=[DataRequired(), Length(max=80)],
        render_kw={'class': 'form-control', 'placeholder': 'admin'},
    )
    ssh_private_key = TextAreaField(
        'SSH Private Key (PEM)',
        validators=[Optional(), Length(max=10000)],
        render_kw={
            'class': 'form-control font-monospace',
            'rows': '6',
            'placeholder': '-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----',
        },
    )
    kast_binary_path = StringField(
        'kast Binary Path',
        default='/usr/local/bin/kast',
        validators=[DataRequired(), Length(max=500)],
        render_kw={'class': 'form-control'},
    )
    remote_output_root = StringField(
        'Remote Output Root',
        default='/tmp/kast-runs',
        validators=[DataRequired(), Length(max=500)],
        render_kw={'class': 'form-control'},
    )
    region_label = StringField(
        'Region Label',
        validators=[Optional(), Length(max=80)],
        render_kw={'class': 'form-control', 'placeholder': 'ca-central-1'},
    )
    enabled = BooleanField(
        'Enabled',
        default=True,
        render_kw={'class': 'form-check-input'},
    )
    submit = SubmitField('Save Runner', render_kw={'class': 'btn btn-primary'})


class ScanConfigProfileForm(FlaskForm):
    """Form for creating/editing scan configuration profiles"""
    
    name = StringField(
        'Profile Name',
        validators=[
            DataRequired(message='Profile name is required'),
            Length(min=3, max=100, message='Name must be between 3 and 100 characters'),
            Regexp(r'^[a-zA-Z0-9\s\-_()]+$', message='Name can only contain letters, numbers, spaces, hyphens, underscores, and parentheses')
        ],
        render_kw={'placeholder': 'e.g., Standard, Stealth, Aggressive', 'class': 'form-control'}
    )
    
    description = TextAreaField(
        'Description',
        validators=[
            Length(max=1000, message='Description must not exceed 1000 characters')
        ],
        render_kw={
            'placeholder': 'Describe the purpose and characteristics of this configuration profile...',
            'class': 'form-control',
            'rows': 3
        }
    )
    
    config_yaml = TextAreaField(
        'Configuration (YAML)',
        validators=[
            DataRequired(message='Configuration YAML is required')
        ],
        render_kw={
            'placeholder': 'Enter YAML configuration here...',
            'class': 'form-control font-monospace',
            'rows': 20,
            'spellcheck': 'false'
        }
    )
    
    allow_standard_users = BooleanField(
        'Allow Standard Users',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    is_system_default = BooleanField(
        'Set as System Default',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    submit = SubmitField('Save Profile', render_kw={'class': 'btn btn-primary'})
    
    def validate_name(self, name):
        """Check if profile name already exists (for new profiles)"""
        from app.models import ScanConfigProfile
        # Only check for new profiles or if name changed
        if not hasattr(self, 'obj') or (self.obj and self.obj.name != name.data):
            profile = ScanConfigProfile.query.filter_by(name=name.data).first()
            if profile:
                raise ValidationError('A profile with this name already exists. Please choose a different name.')


class ZapAutomationPlanForm(FlaskForm):
    """Form for creating/editing ZAP Automation Framework plans"""
    
    name = StringField(
        'Plan Name',
        validators=[
            DataRequired(message='Plan name is required'),
            Length(min=3, max=100, message='Name must be between 3 and 100 characters'),
            Regexp(r'^[a-zA-Z0-9\s\-_()]+$', message='Name can only contain letters, numbers, spaces, hyphens, underscores, and parentheses')
        ],
        render_kw={'placeholder': 'e.g., Quick Passive Scan, Full Security Audit', 'class': 'form-control'}
    )
    
    description = TextAreaField(
        'Description',
        validators=[
            Length(max=1000, message='Description must not exceed 1000 characters')
        ],
        render_kw={
            'placeholder': 'Describe the purpose and scope of this automation plan...',
            'class': 'form-control',
            'rows': 3
        }
    )
    
    plan_yaml = TextAreaField(
        'Automation Plan (YAML)',
        validators=[
            DataRequired(message='Plan YAML is required')
        ],
        render_kw={
            'placeholder': 'Enter ZAP Automation Framework YAML here...',
            'class': 'form-control font-monospace',
            'rows': 25,
            'spellcheck': 'false'
        }
    )
    
    allow_power_users = BooleanField(
        'Allow Power Users',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    is_system_default = BooleanField(
        'Set as System Default',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    is_draft = BooleanField(
        'Save as Draft',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    submit = SubmitField('Save Plan', render_kw={'class': 'btn btn-primary'})
    
    def validate_name(self, name):
        """Check if plan name already exists (for new plans)"""
        from app.models import ZapAutomationPlan
        # Only check for new plans or if name changed
        if not hasattr(self, 'obj') or (self.obj and self.obj.name != name.data):
            plan = ZapAutomationPlan.query.filter_by(name=name.data).first()
            if plan:
                raise ValidationError('A plan with this name already exists. Please choose a different name.')


class ZapConfigurationForm(FlaskForm):
    """Form for creating/editing ZAP execution configurations"""
    
    name = StringField(
        'Configuration Name',
        validators=[
            DataRequired(message='Configuration name is required'),
            Length(min=3, max=100, message='Name must be between 3 and 100 characters'),
            Regexp(r'^[a-zA-Z0-9\s\-_()]+$', message='Name can only contain letters, numbers, spaces, hyphens, underscores, and parentheses')
        ],
        render_kw={'placeholder': 'e.g., Local Docker, Production ZAP Server', 'class': 'form-control'}
    )
    
    description = TextAreaField(
        'Description',
        validators=[
            Length(max=1000, message='Description must not exceed 1000 characters')
        ],
        render_kw={
            'placeholder': 'Describe this ZAP execution environment...',
            'class': 'form-control',
            'rows': 3
        }
    )
    
    execution_mode = SelectField(
        'Execution Mode',
        choices=[
            ('local', 'Local Docker - Run ZAP in local Docker container'),
            ('remote', 'Remote Instance - Connect to existing ZAP server'),
            ('cloud', 'Cloud - Run ZAP in cloud environment'),
            ('auto', 'Auto - Automatically select best available mode')
        ],
        default='local',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    # Local Docker configuration
    docker_image = StringField(
        'Docker Image',
        validators=[
            Optional(),
            Length(max=200, message='Image name must not exceed 200 characters')
        ],
        render_kw={
            'placeholder': 'ghcr.io/zaproxy/zaproxy:stable',
            'class': 'form-control'
        }
    )
    
    docker_port = IntegerField(
        'Docker Port',
        validators=[
            Optional(),
            NumberRange(min=1024, max=65535, message='Port must be between 1024 and 65535')
        ],
        render_kw={
            'placeholder': '8080',
            'class': 'form-control'
        }
    )
    
    docker_memory_limit = StringField(
        'Memory Limit',
        validators=[
            Optional(),
            Length(max=20, message='Memory limit must not exceed 20 characters')
        ],
        render_kw={
            'placeholder': '2g',
            'class': 'form-control'
        }
    )
    
    docker_auto_remove = BooleanField(
        'Auto-remove Container',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    # Remote configuration
    remote_url = StringField(
        'ZAP Server URL',
        validators=[
            Optional(),
            Length(max=500, message='URL must not exceed 500 characters')
        ],
        render_kw={
            'placeholder': 'http://zap-server:8080',
            'class': 'form-control'
        }
    )
    
    remote_api_key = StringField(
        'API Key',
        validators=[
            Optional(),
            Length(max=200, message='API key must not exceed 200 characters')
        ],
        render_kw={
            'placeholder': 'Enter ZAP API key',
            'class': 'form-control',
            'type': 'password'
        }
    )
    
    remote_timeout = IntegerField(
        'Connection Timeout (seconds)',
        validators=[
            Optional(),
            NumberRange(min=5, max=300, message='Timeout must be between 5 and 300 seconds')
        ],
        render_kw={
            'placeholder': '30',
            'class': 'form-control'
        }
    )
    
    remote_verify_ssl = BooleanField(
        'Verify SSL Certificate',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    # Cloud configuration
    cloud_credential_id = SelectField(
        'Cloud Credential',
        choices=[],
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-select', 'id': 'cloud_credential_id'}
    )

    cloud_provider = SelectField(
        'Cloud Provider',
        choices=[
            ('aws', 'Amazon Web Services (AWS)'),
            ('azure', 'Microsoft Azure'),
            ('gcp', 'Google Cloud Platform (GCP)')
        ],
        render_kw={'class': 'form-select', 'id': 'cloud_provider'}
    )
    
    # CIDR blocks for security group configuration
    cloud_allowed_cidrs = TextAreaField(
        'Allowed CIDR Blocks',
        validators=[
            Optional(),
            Length(max=2000, message='CIDR blocks must not exceed 2000 characters')
        ],
        render_kw={
            'placeholder': 'One CIDR per line, e.g.:\n192.168.1.0/24\n10.0.0.1/32',
            'class': 'form-control font-monospace',
            'rows': 5,
            'id': 'cloud_allowed_cidrs'
        }
    )
    
    # AWS-specific fields
    aws_region = SelectField(
        'AWS Region',
        choices=[('', 'Select Region')] + AWS_REGIONS,
        validators=[Optional()],
        render_kw={'class': 'form-select', 'data-provider': 'aws'}
    )
    
    aws_instance_type = SelectField(
        'Instance Type',
        choices=[('', 'Select Instance Type')] + AWS_INSTANCE_TYPES,
        validators=[Optional()],
        render_kw={'class': 'form-select', 'data-provider': 'aws'}
    )
    
    aws_ami_id = StringField(
        'AMI ID (Optional)',
        validators=[
            Optional(),
            Length(max=100, message='AMI ID must not exceed 100 characters')
        ],
        render_kw={
            'placeholder': 'Leave empty for default Ubuntu 22.04 LTS',
            'class': 'form-control',
            'data-provider': 'aws'
        }
    )
    
    aws_spot_max_price = StringField(
        'Spot Max Price (Optional)',
        validators=[
            Optional(),
            Length(max=20, message='Price must not exceed 20 characters')
        ],
        render_kw={
            'placeholder': 'e.g., 0.10',
            'class': 'form-control',
            'data-provider': 'aws'
        }
    )
    
    # Azure-specific fields
    azure_region = SelectField(
        'Azure Region',
        choices=[('', 'Select Region')] + AZURE_REGIONS,
        validators=[Optional()],
        render_kw={'class': 'form-select', 'data-provider': 'azure'}
    )
    
    azure_vm_size = SelectField(
        'VM Size',
        choices=[('', 'Select VM Size')] + AZURE_VM_SIZES,
        validators=[Optional()],
        render_kw={'class': 'form-select', 'data-provider': 'azure'}
    )
    
    azure_spot_enabled = BooleanField(
        'Enable Spot Instance',
        default=True,
        render_kw={'class': 'form-check-input', 'data-provider': 'azure'}
    )
    
    # GCP-specific fields
    gcp_region = SelectField(
        'GCP Region',
        choices=[('', 'Select Region')] + GCP_REGIONS,
        validators=[Optional()],
        render_kw={'class': 'form-select', 'data-provider': 'gcp', 'id': 'gcp_region'}
    )
    
    gcp_zone = StringField(
        'Zone',
        validators=[
            Optional(),
            Length(max=50, message='Zone must not exceed 50 characters')
        ],
        render_kw={
            'placeholder': 'e.g., us-central1-a',
            'class': 'form-control',
            'data-provider': 'gcp',
            'id': 'gcp_zone'
        }
    )
    
    gcp_machine_type = SelectField(
        'Machine Type',
        choices=[('', 'Select Machine Type')] + GCP_MACHINE_TYPES,
        validators=[Optional()],
        render_kw={'class': 'form-select', 'data-provider': 'gcp'}
    )
    
    gcp_preemptible = BooleanField(
        'Use Preemptible Instance',
        default=True,
        render_kw={'class': 'form-check-input', 'data-provider': 'gcp'}
    )
    
    cloud_auto_terminate = BooleanField(
        'Auto-terminate After Scan',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    # General settings
    is_active = BooleanField(
        'Active',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    is_default = BooleanField(
        'Set as Default',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    submit = SubmitField('Save Configuration', render_kw={'class': 'btn btn-primary'})
    
    def validate_name(self, name):
        """Check if configuration name already exists (for new configs)"""
        from app.models import ZapConfiguration
        # Only check for new configs or if name changed
        if not hasattr(self, 'obj') or (self.obj and self.obj.name != name.data):
            config = ZapConfiguration.query.filter_by(name=name.data).first()
            if config:
                raise ValidationError('A configuration with this name already exists. Please choose a different name.')


class CloudCredentialForm(FlaskForm):
    """Form for creating and editing CloudCredential rows."""

    name = StringField(
        'Credential Name',
        validators=[
            DataRequired(message='Name is required'),
            Length(min=2, max=100),
        ],
        render_kw={'placeholder': 'e.g., AWS Prod, GCP East', 'class': 'form-control'},
    )

    provider = SelectField(
        'Cloud Provider',
        choices=[
            ('aws', 'AWS — Amazon Web Services'),
            ('azure', 'Azure — Microsoft Azure'),
            ('gcp', 'GCP — Google Cloud Platform'),
        ],
        validators=[DataRequired()],
        render_kw={'class': 'form-select', 'id': 'provider-select'},
    )

    credentials_json = TextAreaField(
        'Credentials (JSON)',
        validators=[DataRequired(message='Credentials JSON is required')],
        render_kw={
            'class': 'form-control font-monospace',
            'rows': 8,
            'placeholder': '{ "access_key_id": "...", "secret_access_key": "..." }',
            'id': 'credentials-json',
        },
    )

    is_active = BooleanField(
        'Active',
        default=True,
        render_kw={'class': 'form-check-input'},
    )

    submit = SubmitField('Save Credential', render_kw={'class': 'btn btn-primary'})

    def validate_credentials_json(self, field):
        import json
        try:
            data = json.loads(field.data)
        except (ValueError, TypeError):
            raise ValidationError('Must be valid JSON.')
        if not isinstance(data, dict):
            raise ValidationError('Must be a JSON object.')
        if not data:
            raise ValidationError('Credentials cannot be empty.')
