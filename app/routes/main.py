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
    
    # Populate ZAP automation plan choices (admin/power users only)
    from app.models import ZapAutomationPlan, ZapConfiguration
    
    if current_user.is_power_user or current_user.is_admin:
        # Power users see plans that allow them, admins see all
        if current_user.is_admin:
            zap_plans = ZapAutomationPlan.query.filter_by(is_draft=False).order_by(ZapAutomationPlan.name).all()
        else:
            zap_plans = ZapAutomationPlan.query.filter_by(is_draft=False, allow_power_users=True).order_by(ZapAutomationPlan.name).all()
        
        zap_plan_choices = [(0, 'Use Default ZAP Plan')]
        for plan in zap_plans:
            label = plan.name
            if plan.is_system_default:
                label += ' (System Default)'
            zap_plan_choices.append((plan.id, label))
        form.zap_plan_id.choices = zap_plan_choices
        
        # Set default ZAP plan if one exists
        default_zap_plan = ZapAutomationPlan.query.filter_by(is_system_default=True).first()
        if default_zap_plan:
            form.zap_plan_id.data = default_zap_plan.id
    else:
        # Standard users can't configure ZAP - set to default
        form.zap_plan_id.choices = [(0, 'Use Default ZAP Plan')]
        form.zap_plan_id.data = 0  # Explicitly set to 0 (default)
    
    # Populate ZAP execution configuration choices (all users)
    zap_configs = ZapConfiguration.query.filter_by(is_active=True).order_by(ZapConfiguration.name).all()
    zap_config_choices = [(0, 'Use Default Configuration')]
    for config in zap_configs:
        label = f"{config.name} ({config.execution_mode})"
        if config.is_default:
            label += ' (Default)'
        zap_config_choices.append((config.id, label))
    form.zap_config_id.choices = zap_config_choices
    
    # Set default ZAP config if one exists, otherwise explicitly set to 0
    default_zap_config = ZapConfiguration.query.filter_by(is_default=True).first()
    if default_zap_config:
        form.zap_config_id.data = default_zap_config.id
    else:
        form.zap_config_id.data = 0  # Explicitly set to 0 (default)
    
    # Get recent scans for display (user's own scans unless admin)
    if current_user.is_admin:
        recent_scans = Scan.query.order_by(Scan.started_at.desc()).limit(5).all()
    else:
        recent_scans = Scan.query.filter_by(user_id=current_user.id).order_by(Scan.started_at.desc()).limit(5).all()
    
    # Pass all plugins with type info to template for dynamic filtering
    plugins_with_types = all_plugins
    
    # Get actual configuration paths for Quick Info display
    results_dir = current_app.config.get('KAST_RESULTS_DIR', './kast_results')
    
    # Extract database path from SQLALCHEMY_DATABASE_URI
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
    else:
        db_path = 'Configured database'
    
    from app.models import AISettings
    try:
        ai_enabled = AISettings.get().ai_enabled
    except Exception:
        ai_enabled = False

    return render_template('index.html', form=form, recent_scans=recent_scans,
                         can_run_active=current_user.can_run_active_scans,
                         plugins_with_types=plugins_with_types,
                         results_dir=results_dir,
                         db_path=db_path,
                         ai_enabled=ai_enabled)

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
    
    # Populate ZAP choices for validation
    from app.models import ZapAutomationPlan, ZapConfiguration
    
    if current_user.is_power_user or current_user.is_admin:
        if current_user.is_admin:
            zap_plans = ZapAutomationPlan.query.filter_by(is_draft=False).order_by(ZapAutomationPlan.name).all()
        else:
            zap_plans = ZapAutomationPlan.query.filter_by(is_draft=False, allow_power_users=True).order_by(ZapAutomationPlan.name).all()
        
        zap_plan_choices = [(0, 'Use Default ZAP Plan')]
        for plan in zap_plans:
            zap_plan_choices.append((plan.id, plan.name))
        form.zap_plan_id.choices = zap_plan_choices
    else:
        form.zap_plan_id.choices = [(0, 'Use Default ZAP Plan')]
    
    zap_configs = ZapConfiguration.query.filter_by(is_active=True).order_by(ZapConfiguration.name).all()
    zap_config_choices = [(0, 'Use Default Configuration')]
    for config in zap_configs:
        zap_config_choices.append((config.id, f"{config.name} ({config.execution_mode})"))
    form.zap_config_id.choices = zap_config_choices
    
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
        
        # Handle ZAP configuration (0 means use default, so store as None)
        zap_plan_id = None
        zap_config_id = None
        
        # Only process ZAP fields if ZAP plugin is selected
        if form.plugins.data and 'zap' in form.plugins.data:
            # ZAP plan (admin/power users only)
            if current_user.is_power_user or current_user.is_admin:
                # Safely get zap_plan_id, handling None or invalid values
                try:
                    if form.zap_plan_id.data and form.zap_plan_id.data != 0:
                        zap_plan_id = form.zap_plan_id.data
                        
                        # Validate plan access for power users
                        if not current_user.is_admin:
                            plan = ZapAutomationPlan.query.get(zap_plan_id)
                            if plan and not plan.allow_power_users:
                                flash('You do not have permission to use this ZAP automation plan.', 'danger')
                                return redirect(url_for('main.index'))
                except (ValueError, TypeError):
                    # Invalid value, ignore and use default
                    current_app.logger.warning(f"Invalid zap_plan_id value: {form.zap_plan_id.data}")
                    zap_plan_id = None
            else:
                # Standard users cannot select ZAP plans, always use default
                zap_plan_id = None
            
            # ZAP execution config (all users)
            # Safely get zap_config_id, handling None or invalid values
            try:
                if form.zap_config_id.data and form.zap_config_id.data != 0:
                    zap_config_id = form.zap_config_id.data
                    
                    # Validate config is active
                    config = ZapConfiguration.query.get(zap_config_id)
                    if config and not config.is_active:
                        flash('The selected ZAP configuration is not active.', 'danger')
                        return redirect(url_for('main.index'))
            except (ValueError, TypeError):
                # Invalid value, ignore and use default
                current_app.logger.warning(f"Invalid zap_config_id value: {form.zap_config_id.data}")
                zap_config_id = None
        
        # Create scan record (assign to current user)
        scan = Scan(
            user_id=current_user.id,
            target=form.target.data,
            scan_mode=form.scan_mode.data,
            plugins=','.join(form.plugins.data) if form.plugins.data else None,
            parallel=form.parallel.data,
            verbose=form.verbose.data,
            dry_run=form.dry_run.data,
            generate_ai_summary=form.generate_ai_summary.data,
            logo_id=logo_id,
            config_profile_id=config_profile_id,
            config_overrides=config_overrides,
            zap_plan_id=zap_plan_id,
            zap_config_id=zap_config_id,
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
                'config_overrides': config_overrides,
                'zap_plan_id': zap_plan_id,
                'zap_config_id': zap_config_id
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
