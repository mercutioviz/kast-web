"""
ZAP Admin Routes
Administrative functions for managing ZAP automation plans and configurations
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import ZapAutomationPlan, ZapConfiguration, AuditLog, Scan, User
from app.forms import ZapAutomationPlanForm, ZapConfigurationForm
from app.zap_utils import (
    validate_plan_yaml, parse_plan_jobs, test_docker_connection,
    test_remote_connection, test_cloud_config, get_plan_statistics,
    get_config_statistics, extract_plan_summary
)
from datetime import datetime

bp = Blueprint('zap_admin', __name__, url_prefix='/admin/zap')


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You must be an administrator to access this page', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# ZAP AUTOMATION PLANS
# ============================================================================

@bp.route('/plans')
@login_required
@admin_required
def plans_list():
    """List all ZAP automation plans"""
    
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    
    # Build query
    query = ZapAutomationPlan.query
    
    if status_filter == 'active':
        query = query.filter_by(is_draft=False)
    elif status_filter == 'draft':
        query = query.filter_by(is_draft=True)
    elif status_filter == 'default':
        query = query.filter_by(is_system_default=True)
    
    # Order by most recently updated
    plans = query.order_by(ZapAutomationPlan.updated_at.desc()).all()
    
    # Add usage statistics to each plan
    for plan in plans:
        plan.stats = get_plan_statistics(plan.id)
    
    return render_template('admin/zap/plans_list.html',
                         plans=plans,
                         status_filter=status_filter)


@bp.route('/plans/create', methods=['GET', 'POST'])
@login_required
@admin_required
def plan_create():
    """Create a new ZAP automation plan"""
    
    form = ZapAutomationPlanForm()
    
    if form.validate_on_submit():
        # Validate YAML
        is_valid, error, parsed_data = validate_plan_yaml(form.plan_yaml.data)
        
        if not is_valid:
            flash(f'Invalid YAML: {error}', 'danger')
            return render_template('admin/zap/plan_form.html', form=form, mode='create')
        
        # If setting as default, unset other defaults
        if form.is_system_default.data:
            ZapAutomationPlan.query.filter_by(is_system_default=True).update(
                {'is_system_default': False}
            )
        
        # Create plan
        plan = ZapAutomationPlan(
            name=form.name.data,
            description=form.description.data,
            plan_yaml=form.plan_yaml.data,
            created_by=current_user.id,
            is_system_default=form.is_system_default.data,
            allow_power_users=form.allow_power_users.data,
            is_draft=form.is_draft.data
        )
        
        db.session.add(plan)
        db.session.commit()
        
        # Log the action
        AuditLog.log(
            user_id=current_user.id,
            action='zap_plan_created',
            resource_type='zap_plan',
            resource_id=plan.id,
            details=f'Created ZAP plan: {plan.name}'
        )
        
        flash(f'ZAP automation plan "{plan.name}" created successfully', 'success')
        return redirect(url_for('zap_admin.plans_list'))
    
    return render_template('admin/zap/plan_form.html', form=form, mode='create')


@bp.route('/plans/<int:plan_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def plan_edit(plan_id):
    """Edit an existing ZAP automation plan"""
    
    plan = ZapAutomationPlan.query.get_or_404(plan_id)
    form = ZapAutomationPlanForm(obj=plan)
    form.obj = plan  # Store for name validation
    
    if form.validate_on_submit():
        # Validate YAML
        is_valid, error, parsed_data = validate_plan_yaml(form.plan_yaml.data)
        
        if not is_valid:
            flash(f'Invalid YAML: {error}', 'danger')
            return render_template('admin/zap/plan_form.html', form=form, plan=plan, mode='edit')
        
        # If setting as default, unset other defaults
        if form.is_system_default.data and not plan.is_system_default:
            ZapAutomationPlan.query.filter_by(is_system_default=True).update(
                {'is_system_default': False}
            )
        
        # Update plan
        plan.name = form.name.data
        plan.description = form.description.data
        plan.plan_yaml = form.plan_yaml.data
        plan.is_system_default = form.is_system_default.data
        plan.allow_power_users = form.allow_power_users.data
        plan.is_draft = form.is_draft.data
        plan.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log the action
        AuditLog.log(
            user_id=current_user.id,
            action='zap_plan_updated',
            resource_type='zap_plan',
            resource_id=plan.id,
            details=f'Updated ZAP plan: {plan.name}'
        )
        
        flash(f'ZAP automation plan "{plan.name}" updated successfully', 'success')
        return redirect(url_for('zap_admin.plans_list'))
    
    return render_template('admin/zap/plan_form.html', form=form, plan=plan, mode='edit')


@bp.route('/plans/<int:plan_id>/delete', methods=['POST'])
@login_required
@admin_required
def plan_delete(plan_id):
    """Delete a ZAP automation plan"""
    
    plan = ZapAutomationPlan.query.get_or_404(plan_id)
    
    # Check if plan is in use
    scans_using_plan = Scan.query.filter_by(zap_plan_id=plan_id).count()
    
    if scans_using_plan > 0:
        flash(f'Cannot delete plan "{plan.name}" - it is used by {scans_using_plan} scan(s)', 'danger')
        return redirect(url_for('zap_admin.plans_list'))
    
    plan_name = plan.name
    
    db.session.delete(plan)
    db.session.commit()
    
    # Log the action
    AuditLog.log(
        user_id=current_user.id,
        action='zap_plan_deleted',
        resource_type='zap_plan',
        resource_id=plan_id,
        details=f'Deleted ZAP plan: {plan_name}'
    )
    
    flash(f'ZAP automation plan "{plan_name}" deleted successfully', 'success')
    return redirect(url_for('zap_admin.plans_list'))


@bp.route('/plans/<int:plan_id>/approve', methods=['POST'])
@login_required
@admin_required
def plan_approve(plan_id):
    """Approve a draft ZAP automation plan"""
    
    plan = ZapAutomationPlan.query.get_or_404(plan_id)
    
    if not plan.is_draft:
        flash('This plan is not a draft', 'warning')
        return redirect(url_for('zap_admin.plans_list'))
    
    # Approve the plan
    plan.is_draft = False
    plan.approved_by = current_user.id
    plan.approved_at = datetime.utcnow()
    plan.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    # Log the action
    AuditLog.log(
        user_id=current_user.id,
        action='zap_plan_approved',
        resource_type='zap_plan',
        resource_id=plan.id,
        details=f'Approved ZAP plan: {plan.name}'
    )
    
    flash(f'ZAP automation plan "{plan.name}" approved successfully', 'success')
    return redirect(url_for('zap_admin.plans_list'))


@bp.route('/plans/<int:plan_id>/preview')
@login_required
@admin_required
def plan_preview(plan_id):
    """Preview a ZAP automation plan with parsed details"""
    
    plan = ZapAutomationPlan.query.get_or_404(plan_id)
    
    # Parse plan details
    jobs = parse_plan_jobs(plan.plan_yaml)
    summary = extract_plan_summary(plan.plan_yaml)
    stats = get_plan_statistics(plan.id)
    
    return render_template('admin/zap/plan_preview.html',
                         plan=plan,
                         jobs=jobs,
                         summary=summary,
                         stats=stats)


@bp.route('/plans/validate-yaml', methods=['POST'])
@login_required
@admin_required
def plan_validate_yaml():
    """AJAX endpoint to validate YAML syntax"""
    
    yaml_content = request.json.get('yaml', '')
    
    is_valid, error, parsed_data = validate_plan_yaml(yaml_content)
    
    if is_valid:
        summary = extract_plan_summary(yaml_content)
        jobs = parse_plan_jobs(yaml_content)
        
        return jsonify({
            'success': True,
            'message': 'YAML is valid',
            'summary': summary,
            'jobs': jobs
        })
    else:
        return jsonify({
            'success': False,
            'message': error
        }), 400


# ============================================================================
# ZAP CONFIGURATIONS
# ============================================================================

@bp.route('/configs')
@login_required
@admin_required
def configs_list():
    """List all ZAP configurations"""
    
    # Get filter parameters
    mode_filter = request.args.get('mode', 'all')
    status_filter = request.args.get('status', 'all')
    
    # Build query
    query = ZapConfiguration.query
    
    if mode_filter != 'all':
        query = query.filter_by(execution_mode=mode_filter)
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    elif status_filter == 'default':
        query = query.filter_by(is_default=True)
    
    # Order by most recently updated
    configs = query.order_by(ZapConfiguration.updated_at.desc()).all()
    
    # Add usage statistics to each config
    for config in configs:
        config.stats = get_config_statistics(config.id)
    
    return render_template('admin/zap/configs_list.html',
                         configs=configs,
                         mode_filter=mode_filter,
                         status_filter=status_filter)


@bp.route('/configs/create', methods=['GET', 'POST'])
@login_required
@admin_required
def config_create():
    """Create a new ZAP configuration"""
    
    form = ZapConfigurationForm()
    
    if form.validate_on_submit():
        # If setting as default, unset other defaults
        if form.is_default.data:
            ZapConfiguration.query.filter_by(is_default=True).update(
                {'is_default': False}
            )
        
        # Create configuration
        config = ZapConfiguration(
            name=form.name.data,
            description=form.description.data,
            execution_mode=form.execution_mode.data,
            is_active=form.is_active.data,
            is_default=form.is_default.data,
            created_by=current_user.id
        )
        
        # Set mode-specific configuration (will be encrypted automatically)
        if form.execution_mode.data == 'local':
            config.local_config = {
                'docker_image': form.docker_image.data or 'ghcr.io/zaproxy/zaproxy:stable',
                'port': form.docker_port.data or 8080,
                'memory_limit': form.docker_memory_limit.data or '2g',
                'auto_remove': form.docker_auto_remove.data
            }
        elif form.execution_mode.data == 'remote':
            config.remote_config = {
                'zap_url': form.remote_url.data or '',
                'api_key': form.remote_api_key.data or '',
                'timeout': form.remote_timeout.data or 30,
                'verify_ssl': form.remote_verify_ssl.data
            }
        elif form.execution_mode.data == 'cloud':
            config.cloud_config = {
                'provider': form.cloud_provider.data or 'aws',
                'region': form.cloud_region.data or '',
                'instance_type': form.cloud_instance_type.data or '',
                'access_key': form.cloud_access_key.data or '',
                'secret_key': form.cloud_secret_key.data or '',
                'auto_terminate': form.cloud_auto_terminate.data
            }
        
        db.session.add(config)
        db.session.commit()
        
        # Log the action
        AuditLog.log(
            user_id=current_user.id,
            action='zap_config_created',
            resource_type='zap_config',
            resource_id=config.id,
            details=f'Created ZAP configuration: {config.name} ({config.execution_mode})'
        )
        
        flash(f'ZAP configuration "{config.name}" created successfully', 'success')
        return redirect(url_for('zap_admin.configs_list'))
    
    return render_template('admin/zap/config_form.html', form=form, mode='create')


@bp.route('/configs/<int:config_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def config_edit(config_id):
    """Edit an existing ZAP configuration"""
    
    config = ZapConfiguration.query.get_or_404(config_id)
    form = ZapConfigurationForm()
    form.obj = config  # Store for name validation
    
    if request.method == 'GET':
        # Populate form with existing data
        form.name.data = config.name
        form.description.data = config.description
        form.execution_mode.data = config.execution_mode
        form.is_active.data = config.is_active
        form.is_default.data = config.is_default
        
        # Populate mode-specific fields
        if config.execution_mode == 'local':
            local_conf = config.local_config
            form.docker_image.data = local_conf.get('docker_image', '')
            form.docker_port.data = local_conf.get('port', 8080)
            form.docker_memory_limit.data = local_conf.get('memory_limit', '2g')
            form.docker_auto_remove.data = local_conf.get('auto_remove', True)
        elif config.execution_mode == 'remote':
            remote_conf = config.remote_config
            form.remote_url.data = remote_conf.get('zap_url', '')
            # Don't populate API key for security (user must re-enter if changing)
            form.remote_timeout.data = remote_conf.get('timeout', 30)
            form.remote_verify_ssl.data = remote_conf.get('verify_ssl', True)
        elif config.execution_mode == 'cloud':
            cloud_conf = config.cloud_config
            form.cloud_provider.data = cloud_conf.get('provider', 'aws')
            form.cloud_region.data = cloud_conf.get('region', '')
            form.cloud_instance_type.data = cloud_conf.get('instance_type', '')
            # Don't populate keys for security (user must re-enter if changing)
            form.cloud_auto_terminate.data = cloud_conf.get('auto_terminate', True)
    
    if form.validate_on_submit():
        # If setting as default, unset other defaults
        if form.is_default.data and not config.is_default:
            ZapConfiguration.query.filter_by(is_default=True).update(
                {'is_default': False}
            )
        
        # Update configuration
        config.name = form.name.data
        config.description = form.description.data
        config.execution_mode = form.execution_mode.data
        config.is_active = form.is_active.data
        config.is_default = form.is_default.data
        config.updated_at = datetime.utcnow()
        
        # Update mode-specific configuration
        if form.execution_mode.data == 'local':
            config.local_config = {
                'docker_image': form.docker_image.data or 'ghcr.io/zaproxy/zaproxy:stable',
                'port': form.docker_port.data or 8080,
                'memory_limit': form.docker_memory_limit.data or '2g',
                'auto_remove': form.docker_auto_remove.data
            }
        elif form.execution_mode.data == 'remote':
            remote_conf = {
                'zap_url': form.remote_url.data or '',
                'timeout': form.remote_timeout.data or 30,
                'verify_ssl': form.remote_verify_ssl.data
            }
            # Only update API key if provided
            if form.remote_api_key.data:
                remote_conf['api_key'] = form.remote_api_key.data
            else:
                # Keep existing API key
                existing_remote = config.remote_config
                remote_conf['api_key'] = existing_remote.get('api_key', '')
            config.remote_config = remote_conf
        elif form.execution_mode.data == 'cloud':
            cloud_conf = {
                'provider': form.cloud_provider.data or 'aws',
                'region': form.cloud_region.data or '',
                'instance_type': form.cloud_instance_type.data or '',
                'auto_terminate': form.cloud_auto_terminate.data
            }
            # Only update keys if provided
            if form.cloud_access_key.data:
                cloud_conf['access_key'] = form.cloud_access_key.data
            else:
                existing_cloud = config.cloud_config
                cloud_conf['access_key'] = existing_cloud.get('access_key', '')
            
            if form.cloud_secret_key.data:
                cloud_conf['secret_key'] = form.cloud_secret_key.data
            else:
                existing_cloud = config.cloud_config
                cloud_conf['secret_key'] = existing_cloud.get('secret_key', '')
            
            config.cloud_config = cloud_conf
        
        db.session.commit()
        
        # Log the action
        AuditLog.log(
            user_id=current_user.id,
            action='zap_config_updated',
            resource_type='zap_config',
            resource_id=config.id,
            details=f'Updated ZAP configuration: {config.name}'
        )
        
        flash(f'ZAP configuration "{config.name}" updated successfully', 'success')
        return redirect(url_for('zap_admin.configs_list'))
    
    return render_template('admin/zap/config_form.html', form=form, config=config, mode='edit')


@bp.route('/configs/<int:config_id>/delete', methods=['POST'])
@login_required
@admin_required
def config_delete(config_id):
    """Delete a ZAP configuration"""
    
    config = ZapConfiguration.query.get_or_404(config_id)
    
    # Check if config is in use
    scans_using_config = Scan.query.filter_by(zap_config_id=config_id).count()
    
    if scans_using_config > 0:
        flash(f'Cannot delete configuration "{config.name}" - it is used by {scans_using_config} scan(s)', 'danger')
        return redirect(url_for('zap_admin.configs_list'))
    
    config_name = config.name
    
    db.session.delete(config)
    db.session.commit()
    
    # Log the action
    AuditLog.log(
        user_id=current_user.id,
        action='zap_config_deleted',
        resource_type='zap_config',
        resource_id=config_id,
        details=f'Deleted ZAP configuration: {config_name}'
    )
    
    flash(f'ZAP configuration "{config_name}" deleted successfully', 'success')
    return redirect(url_for('zap_admin.configs_list'))


@bp.route('/configs/<int:config_id>/set-default', methods=['POST'])
@login_required
@admin_required
def config_set_default(config_id):
    """Set a configuration as the default"""
    
    config = ZapConfiguration.query.get_or_404(config_id)
    
    # Unset other defaults
    ZapConfiguration.query.filter_by(is_default=True).update({'is_default': False})
    
    # Set this as default
    config.is_default = True
    config.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    # Log the action
    AuditLog.log(
        user_id=current_user.id,
        action='zap_config_default_set',
        resource_type='zap_config',
        resource_id=config.id,
        details=f'Set ZAP configuration as default: {config.name}'
    )
    
    flash(f'ZAP configuration "{config.name}" set as default', 'success')
    return redirect(url_for('zap_admin.configs_list'))


@bp.route('/configs/<int:config_id>/test', methods=['POST'])
@login_required
@admin_required
def config_test(config_id):
    """Test a ZAP configuration"""
    
    config = ZapConfiguration.query.get_or_404(config_id)
    
    success = False
    message = ""
    
    try:
        if config.execution_mode == 'local':
            success, message = test_docker_connection(config.local_config)
        elif config.execution_mode == 'remote':
            success, message = test_remote_connection(config.remote_config)
        elif config.execution_mode == 'cloud':
            success, message = test_cloud_config(config.cloud_config)
        elif config.execution_mode == 'auto':
            # Test in order: local, remote, cloud
            success, message = test_docker_connection({'docker_image': 'ghcr.io/zaproxy/zaproxy:stable'})
            if not success:
                message = "Auto mode will attempt other methods. " + message
                success = True
        else:
            message = f"Unknown execution mode: {config.execution_mode}"
        
        # Log the test
        AuditLog.log(
            user_id=current_user.id,
            action='zap_config_tested',
            resource_type='zap_config',
            resource_id=config.id,
            details=f'Tested ZAP configuration: {config.name} - {"Success" if success else "Failed"}'
        )
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Test error: {str(e)}'}), 400


@bp.route('/configs/<int:config_id>/start-container', methods=['POST'])
@login_required
@admin_required
def config_start_container(config_id):
    """Start ZAP Docker container for a local configuration"""
    
    config = ZapConfiguration.query.get_or_404(config_id)
    
    # Only allow for local mode
    if config.execution_mode != 'local':
        return jsonify({
            'success': False,
            'message': f'Container management only available for local mode (current: {config.execution_mode})',
            'command': ''
        }), 400
    
    try:
        from app.zap_utils import start_zap_container
        
        success, message, docker_command = start_zap_container(config.local_config, config_id)
        
        # Log the action
        AuditLog.log(
            user_id=current_user.id,
            action='zap_container_started' if success else 'zap_container_start_failed',
            resource_type='zap_config',
            resource_id=config.id,
            details=f'Started ZAP container for: {config.name} - {message}'
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'command': docker_command
            })
        else:
            return jsonify({
                'success': False,
                'message': message,
                'command': docker_command
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'command': ''
        }), 500


@bp.route('/configs/<int:config_id>/stop-container', methods=['POST'])
@login_required
@admin_required
def config_stop_container(config_id):
    """Stop ZAP Docker container for a local configuration"""
    
    config = ZapConfiguration.query.get_or_404(config_id)
    
    # Only allow for local mode
    if config.execution_mode != 'local':
        return jsonify({
            'success': False,
            'message': f'Container management only available for local mode (current: {config.execution_mode})',
            'command': ''
        }), 400
    
    try:
        from app.zap_utils import stop_zap_container
        
        success, message, docker_command = stop_zap_container(config_id)
        
        # Log the action
        AuditLog.log(
            user_id=current_user.id,
            action='zap_container_stopped' if success else 'zap_container_stop_failed',
            resource_type='zap_config',
            resource_id=config.id,
            details=f'Stopped ZAP container for: {config.name} - {message}'
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'command': docker_command
            })
        else:
            return jsonify({
                'success': False,
                'message': message,
                'command': docker_command
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'command': ''
        }), 500


@bp.route('/configs/<int:config_id>/remove-container', methods=['POST'])
@login_required
@admin_required
def config_remove_container(config_id):
    """Remove ZAP Docker container for a local configuration"""
    
    config = ZapConfiguration.query.get_or_404(config_id)
    
    # Only allow for local mode
    if config.execution_mode != 'local':
        return jsonify({
            'success': False,
            'message': f'Container management only available for local mode (current: {config.execution_mode})',
            'command': ''
        }), 400
    
    try:
        from app.zap_utils import remove_zap_container
        
        success, message, docker_command = remove_zap_container(config_id)
        
        # Log the action
        AuditLog.log(
            user_id=current_user.id,
            action='zap_container_removed' if success else 'zap_container_remove_failed',
            resource_type='zap_config',
            resource_id=config.id,
            details=f'Removed ZAP container for: {config.name} - {message}'
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'command': docker_command
            })
        else:
            return jsonify({
                'success': False,
                'message': message,
                'command': docker_command
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'command': ''
        }), 500


@bp.route('/configs/<int:config_id>/container-status', methods=['GET'])
@login_required
@admin_required
def config_container_status(config_id):
    """Get status of ZAP Docker container for a local configuration"""
    
    config = ZapConfiguration.query.get_or_404(config_id)
    
    # Only allow for local mode
    if config.execution_mode != 'local':
        return jsonify({
            'status': 'not_applicable',
            'message': 'Container status only available for local mode',
            'command': ''
        })
    
    try:
        from app.zap_utils import get_container_status
        
        status, message, docker_command = get_container_status(config_id)
        
        return jsonify({
            'status': status,
            'message': message,
            'command': docker_command
        })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}',
            'command': ''
        }), 500


@bp.route('/configs/<int:config_id>/container-logs', methods=['GET'])
@login_required
@admin_required
def config_container_logs(config_id):
    """Get logs from ZAP Docker container for a local configuration"""
    
    config = ZapConfiguration.query.get_or_404(config_id)
    
    # Only allow for local mode
    if config.execution_mode != 'local':
        return jsonify({
            'success': False,
            'message': 'Container logs only available for local mode',
            'logs': '',
            'command': ''
        }), 400
    
    try:
        from app.zap_utils import get_container_logs
        
        tail = request.args.get('tail', 100, type=int)
        success, logs_or_error, docker_command = get_container_logs(config_id, tail)
        
        if success:
            return jsonify({
                'success': True,
                'logs': logs_or_error,
                'command': docker_command
            })
        else:
            return jsonify({
                'success': False,
                'message': logs_or_error,
                'logs': '',
                'command': docker_command
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'logs': '',
            'command': ''
        }), 500


@bp.route('/check-cloud-tools', methods=['GET'])
@login_required
@admin_required
def check_cloud_tools():
    """AJAX endpoint to check cloud tool availability"""
    
    from app.zap_utils import get_cloud_tools_status
    
    try:
        status = get_cloud_tools_status()
        
        # Log the check
        AuditLog.log(
            user_id=current_user.id,
            action='zap_cloud_tools_checked',
            resource_type='zap_config',
            resource_id=None,
            details='Checked cloud tools availability'
        )
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'terraform': {'installed': False, 'error': 'Failed to check'},
            'aws': {'installed': False, 'error': 'Failed to check'},
            'azure': {'installed': False, 'error': 'Failed to check'},
            'gcp': {'installed': False, 'error': 'Failed to check'}
        }), 500
