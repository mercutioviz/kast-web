"""
Authentication routes for user login, logout, and registration
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from datetime import datetime

from app import db
from app.models import User, SystemSettings
from app.forms import LoginForm, RegistrationForm, ChangePasswordForm

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        # Check if user exists and password is correct
        if user is None or not user.check_password(form.password.data):
            # Track failed login attempts
            if user:
                user.failed_login_attempts += 1
                user.last_failed_login = datetime.utcnow()
                db.session.commit()
            
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        
        # Check if account is active
        if not user.is_active:
            flash('Your account has been deactivated. Please contact an administrator.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Check maintenance mode - only allow admin users during maintenance
        maintenance_mode = SystemSettings.get_setting('maintenance_mode', False)
        if maintenance_mode and not user.is_admin:
            flash('The system is currently in maintenance mode. Only administrators can log in at this time. Please try again later.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Successful login
        login_user(user, remember=form.remember_me.data)
        
        # Update login statistics
        user.last_login = datetime.utcnow()
        user.login_count += 1
        user.failed_login_attempts = 0
        db.session.commit()
        
        flash(f'Welcome back, {user.username}!', 'success')
        
        # Redirect to next page or home
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.index')
        
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form, title='Login')


@bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    """User registration (admin only)"""
    # Only admins can create new users
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role=form.role.data,
            is_active=form.is_active.data
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'User {user.username} has been created successfully.', 'success')
        return redirect(url_for('auth.list_users'))
    
    return render_template('auth/register.html', form=form, title='Create User')


@bp.route('/users')
@login_required
def list_users():
    """List all users (admin only)"""
    # Only admins can view user list
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('auth/users.html', users=users, title='User Management')


_ALLOWED_MODEL_OVERRIDES = {
    '',
    'claude-haiku-4-5-20251001',
    'claude-sonnet-4-6',
    'claude-opus-4-7',
}


@bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    has_personal_ai_key = bool(current_user.anthropic_api_key_encrypted)
    return render_template('auth/profile.html', title='My Profile',
                           has_personal_ai_key=has_personal_ai_key,
                           user_ai_model=current_user.ai_model_override or '',
                           user_ai_base_url=current_user.ai_base_url or '')


@bp.route('/save-api-key', methods=['POST'])
@login_required
def save_api_key():
    """Save or clear the user's personal Anthropic API key."""
    from app.encryption import encrypt_value
    from app.models import AuditLog

    action = request.form.get('action', 'save')

    if action == 'clear':
        current_user.anthropic_api_key_encrypted = None
        db.session.commit()
        AuditLog.log(
            user_id=current_user.id,
            action='clear_personal_ai_key',
            resource_type='user',
            resource_id=current_user.id,
            ip_address=request.remote_addr,
        )
        flash('Your Anthropic API key has been removed.', 'success')
    else:
        new_key = request.form.get('api_key', '').strip()
        if not new_key:
            flash('No API key provided.', 'warning')
        else:
            current_user.anthropic_api_key_encrypted = encrypt_value(new_key)
            db.session.commit()
            AuditLog.log(
                user_id=current_user.id,
                action='save_personal_ai_key',
                resource_type='user',
                resource_id=current_user.id,
                ip_address=request.remote_addr,
            )
            flash('Your Anthropic API key has been saved.', 'success')

    return redirect(url_for('auth.profile'))


@bp.route('/save-ai-config', methods=['POST'])
@login_required
def save_ai_config():
    """Save the user's personal AI configuration (api_key, model, base_url)."""
    from app.encryption import encrypt_value
    from app.models import AuditLog

    action = request.form.get('action', 'save')
    changed_fields = []

    if action == 'clear_key':
        current_user.anthropic_api_key_encrypted = None
        db.session.commit()
        AuditLog.log(
            user_id=current_user.id,
            action='clear_personal_ai_key',
            resource_type='user',
            resource_id=current_user.id,
            ip_address=request.remote_addr,
        )
        flash('Your Anthropic API key has been removed.', 'success')
        return redirect(url_for('auth.profile'))

    # --- action == 'save' ---

    new_key = request.form.get('api_key', '').strip()
    if new_key:
        current_user.anthropic_api_key_encrypted = encrypt_value(new_key)
        changed_fields.append('api_key')

    model_override = request.form.get('model_override', '').strip()
    if model_override not in _ALLOWED_MODEL_OVERRIDES:
        flash(f'Invalid model selection: {model_override!r}', 'danger')
        return redirect(url_for('auth.profile'))
    current_user.ai_model_override = model_override or None
    changed_fields.append('model_override')

    base_url = request.form.get('base_url', '').strip()
    if base_url and not (base_url.startswith('http://') or base_url.startswith('https://')):
        flash('Custom API endpoint must start with http:// or https://', 'danger')
        return redirect(url_for('auth.profile'))
    current_user.ai_base_url = base_url or None
    changed_fields.append('base_url')

    db.session.commit()

    AuditLog.log(
        user_id=current_user.id,
        action='save_ai_config',
        resource_type='user',
        resource_id=current_user.id,
        details=f'fields_updated={",".join(changed_fields)}',
        ip_address=request.remote_addr,
    )
    flash('Your AI configuration has been saved.', 'success')
    return redirect(url_for('auth.profile'))


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        # Verify current password
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('auth.change_password'))
        
        # Set new password
        current_user.set_password(form.new_password.data)
        db.session.commit()
        
        flash('Your password has been changed successfully.', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html', form=form, title='Change Password')


@bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
def toggle_user_active(user_id):
    """Toggle user active status (admin only)"""
    if not current_user.is_admin:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('main.index'))
    
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.list_users'))
    
    # Prevent admin from deactivating themselves
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'warning')
        return redirect(url_for('auth.list_users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.username} has been {status}.', 'success')
    
    return redirect(url_for('auth.list_users'))


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete user (admin only)"""
    if not current_user.is_admin:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('main.index'))
    
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.list_users'))
    
    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'warning')
        return redirect(url_for('auth.list_users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {username} has been deleted.', 'success')
    return redirect(url_for('auth.list_users'))
