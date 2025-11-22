from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Scan, ReportLogo, SystemSettings
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
    
    # Populate plugin choices dynamically
    plugins = get_available_plugins()
    form.plugins.choices = plugins
    
    # Populate logo choices
    logos = ReportLogo.query.order_by(ReportLogo.name).all()
    logo_choices = [(0, 'Use System Default')]  # 0 means use default
    for logo in logos:
        logo_choices.append((logo.id, logo.name))
    form.logo_id.choices = logo_choices
    
    # Get recent scans for display (user's own scans unless admin)
    if current_user.is_admin:
        recent_scans = Scan.query.order_by(Scan.started_at.desc()).limit(5).all()
    else:
        recent_scans = Scan.query.filter_by(user_id=current_user.id).order_by(Scan.started_at.desc()).limit(5).all()
    
    return render_template('index.html', form=form, recent_scans=recent_scans, can_run_active=current_user.can_run_active_scans)

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
    
    if form.validate_on_submit():
        # Check if user is allowed to run active scans
        if form.scan_mode.data == 'active' and not current_user.can_run_active_scans:
            flash('You do not have permission to run active scans. Only Power Users and Admins can run active scans.', 'danger')
            return redirect(url_for('main.index'))
        
        # Handle logo selection (0 means use system default, so store as None)
        logo_id = form.logo_id.data if form.logo_id.data and form.logo_id.data != 0 else None
        
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
            status='pending',
            config_json=json.dumps({
                'target': form.target.data,
                'scan_mode': form.scan_mode.data,
                'plugins': form.plugins.data,
                'parallel': form.parallel.data,
                'verbose': form.verbose.data,
                'dry_run': form.dry_run.data,
                'max_workers': form.max_workers.data,
                'logo_id': logo_id
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
