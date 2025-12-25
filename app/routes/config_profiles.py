"""
Routes for managing scan configuration profiles
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import ScanConfigProfile, AuditLog
from app.forms import ScanConfigProfileForm
from app.utils import admin_required, power_user_required
import yaml
import json

bp = Blueprint('config_profiles', __name__, url_prefix='/config-profiles')


@bp.route('/')
@login_required
def list_profiles():
    """List all configuration profiles accessible to the user"""
    if current_user.is_admin or current_user.is_power_user:
        # Admins and power users see all profiles
        profiles = ScanConfigProfile.query.order_by(
            ScanConfigProfile.is_system_default.desc(),
            ScanConfigProfile.name
        ).all()
    else:
        # Standard users only see profiles they can use
        profiles = ScanConfigProfile.query.filter_by(
            allow_standard_users=True
        ).order_by(
            ScanConfigProfile.is_system_default.desc(),
            ScanConfigProfile.name
        ).all()
    
    return render_template('config_profiles/list.html', profiles=profiles)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@power_user_required
def create_profile():
    """Create a new configuration profile"""
    form = ScanConfigProfileForm()
    
    if form.validate_on_submit():
        try:
            # Validate YAML syntax
            yaml.safe_load(form.config_yaml.data)
            
            # Only one profile can be system default
            if form.is_system_default.data:
                # Remove default flag from all other profiles
                ScanConfigProfile.query.filter_by(is_system_default=True).update(
                    {'is_system_default': False}
                )
            
            # Create new profile
            profile = ScanConfigProfile(
                name=form.name.data,
                description=form.description.data,
                config_yaml=form.config_yaml.data,
                created_by=current_user.id,
                allow_standard_users=form.allow_standard_users.data,
                is_system_default=form.is_system_default.data
            )
            
            db.session.add(profile)
            db.session.commit()
            
            # Audit log
            AuditLog.log(
                user_id=current_user.id,
                action='config_profile_create',
                resource_type='config_profile',
                resource_id=profile.id,
                details=f"Created config profile '{profile.name}'"
            )
            
            flash(f'Configuration profile "{profile.name}" created successfully!', 'success')
            return redirect(url_for('config_profiles.view_profile', profile_id=profile.id))
            
        except yaml.YAMLError as e:
            flash(f'Invalid YAML syntax: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating profile: {str(e)}', 'danger')
    
    return render_template('config_profiles/create.html', form=form)


@bp.route('/<int:profile_id>')
@login_required
def view_profile(profile_id):
    """View a configuration profile"""
    profile = ScanConfigProfile.query.get_or_404(profile_id)
    
    # Check access
    if not profile.can_be_used_by(current_user):
        flash('You do not have permission to view this profile.', 'danger')
        return redirect(url_for('config_profiles.list_profiles'))
    
    # Parse YAML for display
    try:
        config_dict = yaml.safe_load(profile.config_yaml)
        config_json = json.dumps(config_dict, indent=2)
    except:
        config_json = None
    
    return render_template('config_profiles/view.html', 
                         profile=profile, 
                         config_json=config_json)


@bp.route('/<int:profile_id>/edit', methods=['GET', 'POST'])
@login_required
@power_user_required
def edit_profile(profile_id):
    """Edit a configuration profile"""
    profile = ScanConfigProfile.query.get_or_404(profile_id)
    form = ScanConfigProfileForm(obj=profile)
    
    if form.validate_on_submit():
        try:
            # Validate YAML syntax
            yaml.safe_load(form.config_yaml.data)
            
            # Only one profile can be system default
            if form.is_system_default.data and not profile.is_system_default:
                # Remove default flag from all other profiles
                ScanConfigProfile.query.filter(
                    ScanConfigProfile.id != profile.id,
                    ScanConfigProfile.is_system_default == True
                ).update({'is_system_default': False})
            
            # Update profile
            old_name = profile.name
            profile.name = form.name.data
            profile.description = form.description.data
            profile.config_yaml = form.config_yaml.data
            profile.allow_standard_users = form.allow_standard_users.data
            profile.is_system_default = form.is_system_default.data
            
            db.session.commit()
            
            # Audit log
            AuditLog.log(
                user_id=current_user.id,
                action='config_profile_update',
                resource_type='config_profile',
                resource_id=profile.id,
                details=f"Updated config profile '{old_name}' to '{profile.name}'"
            )
            
            flash(f'Configuration profile "{profile.name}" updated successfully!', 'success')
            return redirect(url_for('config_profiles.view_profile', profile_id=profile.id))
            
        except yaml.YAMLError as e:
            flash(f'Invalid YAML syntax: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')
    
    return render_template('config_profiles/edit.html', form=form, profile=profile)


@bp.route('/<int:profile_id>/delete', methods=['POST'])
@login_required
@power_user_required
def delete_profile(profile_id):
    """Delete a configuration profile"""
    profile = ScanConfigProfile.query.get_or_404(profile_id)
    
    # Check if profile is in use
    scan_count = len(profile.scans)
    if scan_count > 0:
        flash(f'Cannot delete profile "{profile.name}" as it is being used by {scan_count} scan(s).', 'danger')
        return redirect(url_for('config_profiles.view_profile', profile_id=profile.id))
    
    profile_name = profile.name
    
    try:
        # Audit log before deletion
        AuditLog.log(
            user_id=current_user.id,
            action='config_profile_delete',
            resource_type='config_profile',
            resource_id=profile.id,
            details=f"Deleted config profile '{profile_name}'"
        )
        
        db.session.delete(profile)
        db.session.commit()
        
        flash(f'Configuration profile "{profile_name}" deleted successfully!', 'success')
        return redirect(url_for('config_profiles.list_profiles'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting profile: {str(e)}', 'danger')
        return redirect(url_for('config_profiles.view_profile', profile_id=profile.id))


@bp.route('/<int:profile_id>/duplicate', methods=['POST'])
@login_required
@power_user_required
def duplicate_profile(profile_id):
    """Duplicate a configuration profile"""
    original = ScanConfigProfile.query.get_or_404(profile_id)
    
    try:
        # Create duplicate with modified name
        duplicate = ScanConfigProfile(
            name=f"{original.name} (Copy)",
            description=original.description,
            config_yaml=original.config_yaml,
            created_by=current_user.id,
            allow_standard_users=original.allow_standard_users,
            is_system_default=False  # Duplicates are never default
        )
        
        db.session.add(duplicate)
        db.session.commit()
        
        # Audit log
        AuditLog.log(
            user_id=current_user.id,
            action='config_profile_duplicate',
            resource_type='config_profile',
            resource_id=duplicate.id,
            details=f"Duplicated config profile '{original.name}' to '{duplicate.name}'"
        )
        
        flash(f'Configuration profile duplicated successfully as "{duplicate.name}"!', 'success')
        return redirect(url_for('config_profiles.edit_profile', profile_id=duplicate.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error duplicating profile: {str(e)}', 'danger')
        return redirect(url_for('config_profiles.view_profile', profile_id=profile_id))


@bp.route('/<int:profile_id>/validate', methods=['POST'])
@login_required
@power_user_required
def validate_yaml(profile_id):
    """AJAX endpoint to validate YAML syntax"""
    try:
        yaml_content = request.json.get('yaml_content', '')
        
        # Try to parse YAML
        parsed = yaml.safe_load(yaml_content)
        
        return jsonify({
            'valid': True,
            'message': 'YAML syntax is valid',
            'parsed': json.dumps(parsed, indent=2)
        })
        
    except yaml.YAMLError as e:
        return jsonify({
            'valid': False,
            'message': f'YAML syntax error: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'valid': False,
            'message': f'Validation error: {str(e)}'
        }), 400
