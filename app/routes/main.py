import json
import uuid
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request
from flask_login import login_required, current_user

from app import db
from app.models import (
    Scan, ReportLogo, SystemSettings, ScanConfigProfile, AuditLog,
    ZapAutomationPlan, ZapConfiguration,
)
from app.forms import ScanConfigForm, BatchScanForm, parse_batch_targets, MAX_BATCH_TARGETS
from app.utils import get_available_plugins, filter_plugins_by_mode, power_user_required
from app.tasks import execute_scan_task

bp = Blueprint('main', __name__)


def _populate_scan_form_choices(form, user, default_scan_mode='passive'):
    """
    Populate plugin / logo / profile / ZAP choices on a ScanConfigForm or BatchScanForm.

    Also applies sensible defaults (system-default profile, system-default ZAP plan,
    default ZAP config). On POST, WTForms' formdata overrides these defaults.

    Returns the list of (name, desc, type) tuples for all available plugins so the
    caller can pass them to the template for the per-mode plugin filter UI.
    """
    all_plugins = get_available_plugins()
    form.plugins.choices = filter_plugins_by_mode(all_plugins, default_scan_mode)

    logos = ReportLogo.query.order_by(ReportLogo.name).all()
    form.logo_id.choices = [(0, 'Use System Default')] + [(l.id, l.name) for l in logos]

    if user.is_power_user or user.is_admin:
        profiles = ScanConfigProfile.query.order_by(ScanConfigProfile.name).all()
    else:
        profiles = ScanConfigProfile.query.filter_by(allow_standard_users=True).order_by(ScanConfigProfile.name).all()
    profile_choices = [(0, 'No Profile (Use Basic Settings)')]
    for profile in profiles:
        label = profile.name + (' (System Default)' if profile.is_system_default else '')
        profile_choices.append((profile.id, label))
    form.config_profile_id.choices = profile_choices
    default_profile = ScanConfigProfile.query.filter_by(is_system_default=True).first()
    if default_profile:
        form.config_profile_id.data = default_profile.id

    if user.is_power_user or user.is_admin:
        if user.is_admin:
            zap_plans = ZapAutomationPlan.query.filter_by(is_draft=False).order_by(ZapAutomationPlan.name).all()
        else:
            zap_plans = ZapAutomationPlan.query.filter_by(is_draft=False, allow_power_users=True).order_by(ZapAutomationPlan.name).all()
        zap_plan_choices = [(0, 'Use Default ZAP Plan')]
        for plan in zap_plans:
            label = plan.name + (' (System Default)' if plan.is_system_default else '')
            zap_plan_choices.append((plan.id, label))
        form.zap_plan_id.choices = zap_plan_choices
        default_zap_plan = ZapAutomationPlan.query.filter_by(is_system_default=True).first()
        if default_zap_plan:
            form.zap_plan_id.data = default_zap_plan.id
    else:
        form.zap_plan_id.choices = [(0, 'Use Default ZAP Plan')]
        form.zap_plan_id.data = 0

    zap_configs = ZapConfiguration.query.filter_by(is_active=True).order_by(ZapConfiguration.name).all()
    zap_config_choices = [(0, 'Use Default Configuration')]
    for config in zap_configs:
        label = f"{config.name} ({config.execution_mode})" + (' (Default)' if config.is_default else '')
        zap_config_choices.append((config.id, label))
    form.zap_config_id.choices = zap_config_choices
    default_zap_config = ZapConfiguration.query.filter_by(is_default=True).first()
    if default_zap_config:
        form.zap_config_id.data = default_zap_config.id
    else:
        form.zap_config_id.data = 0

    # Scan runner choices: only power_user/admin can target a remote runner
    if hasattr(form, 'runner_id'):
        from app.models import ScanRunner
        runner_choices = [(0, 'Local (this host)')]
        if user.is_power_user or user.is_admin:
            for r in ScanRunner.query.filter_by(enabled=True).order_by(ScanRunner.name).all():
                label = r.name + (f' — {r.region_label}' if r.region_label else '')
                runner_choices.append((r.id, label))
        form.runner_id.choices = runner_choices
        form.runner_id.data = 0

    return all_plugins

@bp.route('/')
@login_required
def index():
    """Home page with scan configuration form"""
    form = ScanConfigForm()
    all_plugins = _populate_scan_form_choices(form, current_user)

    if current_user.is_power_user or current_user.is_admin:
        profiles = ScanConfigProfile.query.order_by(ScanConfigProfile.name).all()
    else:
        profiles = ScanConfigProfile.query.filter_by(allow_standard_users=True).order_by(ScanConfigProfile.name).all()

    if current_user.is_admin:
        recent_scans = Scan.query.order_by(Scan.started_at.desc()).limit(5).all()
    else:
        recent_scans = Scan.query.filter_by(user_id=current_user.id).order_by(Scan.started_at.desc()).limit(5).all()

    results_dir = current_app.config.get('KAST_RESULTS_DIR', './kast_results')
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

    clone_source = None
    clone_preselected_plugins = []
    clone_id = request.args.get('clone', type=int)
    if clone_id:
        _src = db.session.get(Scan, clone_id)
        if _src and (_src.user_id == current_user.id or current_user.is_admin):
            clone_source = _src
            clone_preselected_plugins = _src.plugin_list

    profile_data = {
        str(p.id): {'name': p.name, 'description': p.description or ''}
        for p in profiles
    }

    return render_template('index.html', form=form, recent_scans=recent_scans,
                         can_run_active=current_user.can_run_active_scans,
                         plugins_with_types=all_plugins,
                         results_dir=results_dir,
                         db_path=db_path,
                         ai_enabled=ai_enabled,
                         clone_source=clone_source,
                         clone_preselected_plugins=clone_preselected_plugins,
                         profile_data=profile_data)

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

    # Scan runner choices (only power_user/admin see non-local options)
    from app.models import ScanRunner
    runner_choices = [(0, 'Local (this host)')]
    if current_user.is_power_user or current_user.is_admin:
        for r in ScanRunner.query.filter_by(enabled=True).order_by(ScanRunner.name).all():
            label = r.name + (f' — {r.region_label}' if r.region_label else '')
            runner_choices.append((r.id, label))
    form.runner_id.choices = runner_choices

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
        
        # Capture tags from form (plain text field, not a WTForm field)
        raw_tags = request.form.get('tags', '').strip()
        tags_value = ','.join(t.strip() for t in raw_tags.split(',') if t.strip()) or None

        # Scan runner selection (power_user / admin only; 0 = local)
        runner_id = None
        try:
            chosen_runner = int(form.runner_id.data or 0) if hasattr(form, 'runner_id') else 0
        except (TypeError, ValueError):
            chosen_runner = 0
        if chosen_runner:
            if not (current_user.is_power_user or current_user.is_admin):
                flash('Only Power Users and Admins can target a remote scan runner.', 'danger')
                return redirect(url_for('main.index'))
            from app.models import ScanRunner
            runner_row = db.session.get(ScanRunner, chosen_runner)
            if not runner_row or not runner_row.enabled:
                flash('Selected scan runner is unavailable.', 'danger')
                return redirect(url_for('main.index'))
            runner_id = runner_row.id

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
            runner_id=runner_id,
            tags=tags_value,
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

@bp.route('/scan/batch', methods=['GET', 'POST'])
@login_required
@power_user_required
def batch_scan():
    """Submit a batch of scans that share identical settings but target different hosts."""
    form = BatchScanForm()
    all_plugins = _populate_scan_form_choices(form, current_user)

    if request.method == 'POST' and form.validate_on_submit():
        if form.scan_mode.data == 'active' and not current_user.can_run_active_scans:
            flash('You do not have permission to run active scans.', 'danger')
            return redirect(url_for('main.batch_scan'))

        clean_targets, duplicates, _ = parse_batch_targets(form.targets.data)

        if form.scan_mode.data == 'passive' and form.plugins.data:
            plugin_types = {name: ptype for name, _, ptype in all_plugins}
            active_selected = [p for p in form.plugins.data if plugin_types.get(p) == 'active']
            if active_selected:
                flash(f'Passive scans cannot include active plugins. Remove: {", ".join(active_selected)}', 'danger')
                return redirect(url_for('main.batch_scan'))

        logo_id = form.logo_id.data if form.logo_id.data else None
        config_profile_id = form.config_profile_id.data if form.config_profile_id.data else None

        if config_profile_id and not (current_user.is_power_user or current_user.is_admin):
            profile = ScanConfigProfile.query.get(config_profile_id)
            if profile and not profile.allow_standard_users:
                flash('You do not have permission to use this configuration profile.', 'danger')
                return redirect(url_for('main.batch_scan'))

        config_overrides = None
        if form.config_overrides.data and (current_user.is_power_user or current_user.is_admin):
            config_overrides = form.config_overrides.data.strip()

        zap_plan_id = None
        zap_config_id = None
        if form.plugins.data and 'zap' in form.plugins.data:
            if (current_user.is_power_user or current_user.is_admin) and form.zap_plan_id.data:
                zap_plan_id = form.zap_plan_id.data
                if not current_user.is_admin:
                    plan = ZapAutomationPlan.query.get(zap_plan_id)
                    if plan and not plan.allow_power_users:
                        flash('You do not have permission to use this ZAP automation plan.', 'danger')
                        return redirect(url_for('main.batch_scan'))
            if form.zap_config_id.data:
                zap_config_id = form.zap_config_id.data
                config = ZapConfiguration.query.get(zap_config_id)
                if config and not config.is_active:
                    flash('The selected ZAP configuration is not active.', 'danger')
                    return redirect(url_for('main.batch_scan'))

        # Scan runner selection (power_user / admin only; 0 = local)
        runner_id = None
        try:
            chosen_runner = int(form.runner_id.data or 0) if hasattr(form, 'runner_id') else 0
        except (TypeError, ValueError):
            chosen_runner = 0
        if chosen_runner:
            if not (current_user.is_power_user or current_user.is_admin):
                flash('Only Power Users and Admins can target a remote scan runner.', 'danger')
                return redirect(url_for('main.batch_scan'))
            from app.models import ScanRunner
            runner_row = db.session.get(ScanRunner, chosen_runner)
            if not runner_row or not runner_row.enabled:
                flash('Selected scan runner is unavailable.', 'danger')
                return redirect(url_for('main.batch_scan'))
            runner_id = runner_row.id

        batch_id = uuid.uuid4().hex

        raw_tags = request.form.get('tags', '').strip()
        tags_value = ','.join(t.strip() for t in raw_tags.split(',') if t.strip()) or None

        plugins_csv = ','.join(form.plugins.data) if form.plugins.data else None
        plugin_list_for_config = form.plugins.data or None

        is_cloud_scan = False
        if zap_config_id:
            cfg = ZapConfiguration.query.get(zap_config_id)
            if cfg and cfg.execution_mode == 'cloud':
                is_cloud_scan = True
        needs_stagger = form.scan_mode.data == 'active' or is_cloud_scan

        scans_created = []
        for target in clean_targets:
            scan = Scan(
                user_id=current_user.id,
                target=target,
                scan_mode=form.scan_mode.data,
                plugins=plugins_csv,
                parallel=form.parallel.data,
                verbose=form.verbose.data,
                dry_run=form.dry_run.data,
                generate_ai_summary=form.generate_ai_summary.data,
                logo_id=logo_id,
                config_profile_id=config_profile_id,
                config_overrides=config_overrides,
                zap_plan_id=zap_plan_id,
                zap_config_id=zap_config_id,
                tags=tags_value,
                status='pending',
                batch_id=batch_id,
                runner_id=runner_id,
                config_json=json.dumps({
                    'target': target,
                    'scan_mode': form.scan_mode.data,
                    'plugins': plugin_list_for_config,
                    'parallel': form.parallel.data,
                    'verbose': form.verbose.data,
                    'dry_run': form.dry_run.data,
                    'max_workers': form.max_workers.data,
                    'logo_id': logo_id,
                    'config_profile_id': config_profile_id,
                    'config_overrides': config_overrides,
                    'zap_plan_id': zap_plan_id,
                    'zap_config_id': zap_config_id,
                    'batch_id': batch_id,
                }),
            )
            db.session.add(scan)
            scans_created.append(scan)

        db.session.commit()

        for idx, scan in enumerate(scans_created):
            try:
                task_kwargs = dict(
                    plugins=scan.plugin_list if scan.plugins else None,
                    parallel=scan.parallel,
                    verbose=scan.verbose,
                    dry_run=scan.dry_run,
                    max_workers=form.max_workers.data,
                )
                if needs_stagger:
                    task = execute_scan_task.apply_async(
                        args=[scan.id, scan.target, scan.scan_mode],
                        kwargs=task_kwargs,
                        countdown=idx * 8,
                    )
                else:
                    task = execute_scan_task.delay(
                        scan.id, scan.target, scan.scan_mode, **task_kwargs
                    )
                scan.celery_task_id = task.id
            except Exception as e:
                current_app.logger.exception(f"Error dispatching batch scan {scan.id}: {e}")
                scan.status = 'failed'
                scan.error_message = f'Dispatch error: {e}'
        db.session.commit()

        try:
            AuditLog.log(
                user_id=current_user.id,
                action='batch_scan_started',
                resource_type='scan_batch',
                resource_id=None,
                details=(f"batch_id={batch_id} mode={form.scan_mode.data} "
                         f"count={len(scans_created)} targets={','.join(clean_targets)}"),
                ip_address=request.remote_addr,
            )
        except Exception as e:
            current_app.logger.warning(f"AuditLog for batch_scan_started failed: {e}")

        if duplicates:
            flash(f'Removed {len(duplicates)} duplicate target(s): {", ".join(duplicates)}', 'info')
        flash(f'Batch started: {len(scans_created)} scan(s) queued.', 'success')
        return redirect(url_for('scans.list', batch_id=batch_id))

    if request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')

    return render_template(
        'scan_batch.html',
        form=form,
        plugins_with_types=all_plugins,
        max_batch_targets=MAX_BATCH_TARGETS,
        can_run_active=current_user.can_run_active_scans,
    )


@bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')
