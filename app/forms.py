from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SelectMultipleField, SubmitField, IntegerField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, Regexp, Length, NumberRange, Email, EqualTo, ValidationError
from wtforms.widgets import CheckboxInput, ListWidget

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
                r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$',
                message='Please enter a valid domain name (e.g., example.com)'
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
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    verbose = BooleanField(
        'Verbose output',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    dry_run = BooleanField(
        'Dry run (preview only)',
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
    
    submit = SubmitField('Start Scan', render_kw={'class': 'btn btn-primary btn-lg'})


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
            Length(min=8, message='Password must be at least 8 characters long')
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
            Length(min=8, message='Password must be at least 8 characters long')
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
