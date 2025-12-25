from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Scan, ReportLogo, SystemSettings, ScanConfigProfile
from app.forms import ScanConfigForm
from app.utils import get_available_plugins
from app.tasks import execute_scan_task
import json
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def index():
    """Home page with scan configuration form"""
    form = ScanConfigForm()
    
    # Populate plugin choices dynamically with type information
    all_plugins = get_available_plugins()
    # For initial load, show passive plugins only (default scan mode)
    from app.utils import filter_plugins_by_mode
    form.plugins.choices = filter_plugins_by_mode(all_plugins, 'passive')
    
    # Populate logo choices
    logos = ReportLogo.query.order_by(ReportLogo.name).all()
    logo_choices = [(0, 'Use System Default')]  # 0 means use default
    for logo in logos:
        logo_choices.append((logo.id, logo.name))
    form.logo_id.choices = logo_choices
    
    # Populate config profile choices based on user role
    if current_user.is_power_user or current_user.is_admin:
        # Power users and admins see all profiles
        profiles = ScanConfigProfile.query.order_by(ScanConfigProfile.name).all()
    else:
        # Standard users only see profiles that allow standard users
        profiles = ScanConfigProfile.query.filter_by(allow_standard_users=True).order_by(ScanConfigProfile.name).all()
    
    profile_choices = [(0, 'No Profile (Use Basic Settings)')]  # 0 means no profile
    for profile in profiles:
        label = profile.name
        if profile.is_system_default:
            label += ' (System Default)'
        profile_choices.append((profile.id, label))
    form.config_profile_id.choices = profile_choices
    
    # Set default selection to system default profile if one exists
    default_profile = ScanConfigProfile.query.filter_by(is_system_default=True).first()
    if default_profile:
        form.config_profile_id.data = default_profile.id
    
    # Get recent scans for display (user's own scans unless admin)
    if current_user.is_admin:
        recent_scans = Scan.query.order_by(Scan.started_at.desc()).limit(5).all()
    else:
        recent_scans = Scan.query.filter_by(user_id=current_user.id).order_by(Scan.started_at.desc()).limit(5).all()
    
    # Pass all plugins with type info to template for dynamic filtering
    plugins_with_types = all_plugins
    
    return render_template('index.html', form=form, recent_scans=recent_scans, 
                         can_run_active=current_user.can_run_active_scans,
                         plugins_with_types=plugins_with_types)

@bp.route('/scan/new', methods=['POST'])
@login_required
def create_scan():
    """Create and execute a new scan"""
    form = ScanConfigForm()
    
    # Populate plugin choices for validation
    plugins = get_available_plugins()
    form.plugins.choices = plugins
    
    # Populate logo choices for validation
    logos = ReportLogo.query.order_by(ReportLogo.name).all()
    logo_choices = [(0, 'Use System Default')]
    for logo in logos:
        logo_choices.append((logo.id, logo.name))
    form.logo_id.choices = logo_choices
    
    # Populate config profile choices for validation
    if current_user.is_power_user or current_user.is_admin:
        profiles = ScanConfigProfile.query.order_by(ScanConfigProfile.name).all()
    else:
        profiles = ScanConfigProfile.query.filter_by(allow_standard_users=True).order_by(ScanConfigProfile.name).all()
    
    profile_choices = [(0, 'No Profile (Use Basic Settings)')]
    for profile in profiles:
        label = profile.name
        if profile.is_system_default:
            label += ' (System Default)'
        profile_choices.append((profile.id, label))
    form.config_profile_id.choices = profile_choices
    
    if form.validate_on_submit():
        # Check if user is allowed to run active scans
        if form.scan_mode.data == 'active' and not current_user.can_run_active_scans:
            flash('You do not have permission to run active scans. Only Power Users and Admins can run active scans.', 'danger')
            return redirect(url_for('main.index'))
        
        # Validate that passive scans don't include active plugins
        if form.scan_mode.data == 'passive' and form.plugins.data:
            # Get plugin types
            all_plugins = get_available_plugins()
            plugin_types = {name: ptype for name, _, ptype in all_plugins}
            
            # Check if any selected plugins are active-only
            active_plugins_selected = [p for p in form.plugins.data if plugin_types.get(p) == 'active']
            if active_plugins_selected:
                flash(f'Passive scans cannot include active plugins. Remove these plugins: {", ".join(active_plugins_selected)}', 'danger')
                return redirect(url_for('main.index'))
        
        # Handle logo selection (0 means use system default, so store as None)
        logo_id = form.logo_id.data if form.logo_id.data and form.logo_id.data != 0 else None
        
        # Handle config profile selection
        config_profile_id = form.config_profile_id.data if form.config_profile_id.data and form.config_profile_id.data != 0 else None
        
        # Validate that standard users can only use profiles that allow them
        if config_profile_id and not (current_user.is_power_user or current_user.is_admin):
            profile = ScanConfigProfile.query.get(config_profile_id)
            if profile and not profile.allow_standard_users:
                flash('You do not have permission to use this configuration profile.', 'danger')
                return redirect(url_for('main.index'))
        
        # Handle config overrides (only for power users and admins)
        config_overrides = None
        if form.config_overrides.data and (current_user.is_power_user or current_user.is_admin):
            config_overrides = form.config_overrides.data.strip()
        elif form.config_overrides.data and not (current_user.is_power_user or current_user.is_admin):
            flash('Only Power Users and Admins can use configuration overrides.', 'warning')
        
        # Create scan record (assign to current user)
        scan = Scan(
            user_id=current_user.id,
            target=form.target.data,
            scan_mode=form.scan_mode.data,
            plugins=','.join(form.plugins.data) if form.plugins.data else None,
            parallel=form.parallel.data,
            verbose=form.verbose.data,
            dry_run=form.dry_run.data,
            logo_id=logo_id,
            config_profile_id=config_profile_id,
            config_overrides=config_overrides,
            status='pending',
            config_json=json.dumps({
                'target': form.target.data,
                'scan_mode': form.scan_mode.data,
                'plugins': form.plugins.data,
                'parallel': form.parallel.data,
                'verbose': form.verbose.data,
                'dry_run': form.dry_run.data,
                'max_workers': form.max_workers.data,
                'logo_id': logo_id,
                'config_profile_id': config_profile_id,
                'config_overrides': config_overrides
            })
        )
        
        db.session.add(scan)
        db.session.commit()
        
        current_app.logger.info(f"Created scan {scan.id} for target {scan.target}")
        
        # Execute scan asynchronously using Celery
        try:
            task = execute_scan_task.delay(
                scan.id,
                scan.target,
                scan.scan_mode,
                plugins=scan.plugin_list if scan.plugins else None,
                parallel=scan.parallel,
                verbose=scan.verbose,
                dry_run=scan.dry_run,
                max_workers=form.max_workers.data
            )
            
            # Store task ID for tracking
            scan.celery_task_id = task.id
            db.session.commit()
            
            flash(f'Scan started for {scan.target}. Results will update automatically.', 'success')
        
        except Exception as e:
            current_app.logger.exception(f"Error starting scan: {str(e)}")
            flash(f'Error starting scan: {str(e)}', 'danger')
        
        return redirect(url_for('scans.detail', scan_id=scan.id))
    
    # Form validation failed
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{field}: {error}', 'danger')
    
    return redirect(url_for('main.index'))

@bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')
