from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SelectMultipleField, SubmitField, IntegerField, PasswordField
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
            ('user', 'User - Can create and manage own scans'),
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
