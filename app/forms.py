from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SelectMultipleField, SubmitField
from wtforms.validators import DataRequired, Regexp, Length
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
    
    submit = SubmitField('Start Scan', render_kw={'class': 'btn btn-primary btn-lg'})
