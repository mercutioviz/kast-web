from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, IntegerField, PasswordField, StringField
from wtforms.validators import Optional, NumberRange, Length


class AISettingsForm(FlaskForm):
    ai_enabled = BooleanField(
        'Enable AI Executive Summaries',
        render_kw={'class': 'form-check-input', 'id': 'ai_enabled'}
    )
    default_mode = SelectField(
        'Default Generation Mode',
        choices=[
            ('review', 'Review — SA edits before sharing'),
            ('auto', 'Auto — publish immediately'),
        ],
        render_kw={'class': 'form-select'}
    )
    monthly_budget_tokens = IntegerField(
        'Monthly Token Budget',
        validators=[NumberRange(min=1000, max=10000000)],
        render_kw={'class': 'form-control'}
    )
    model_id = SelectField(
        'Claude Model',
        choices=[
            ('claude-sonnet-4-6', 'Claude Sonnet 4.6 (recommended)'),
            ('claude-opus-4-7', 'Claude Opus 4.7 (higher quality, higher cost)'),
            ('claude-haiku-4-5-20251001', 'Claude Haiku 4.5 (fastest, lowest cost)'),
        ],
        render_kw={'class': 'form-select'}
    )
    api_key = PasswordField(
        'Anthropic API Key',
        validators=[Optional(), Length(max=200)],
        render_kw={
            'class': 'form-control',
            'placeholder': 'sk-ant-... (leave blank to keep existing)',
            'autocomplete': 'new-password'
        }
    )
