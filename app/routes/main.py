from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from app import db
from app.models import Scan
from app.forms import ScanConfigForm
from app.utils import get_available_plugins
from app.tasks import execute_scan_task
import json
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """Home page with scan configuration form"""
    form = ScanConfigForm()
    
    # Populate plugin choices dynamically
    plugins = get_available_plugins()
    form.plugins.choices = plugins
    
    # Get recent scans for display
    recent_scans = Scan.query.order_by(Scan.started_at.desc()).limit(5).all()
    
    return render_template('index.html', form=form, recent_scans=recent_scans)

@bp.route('/scan/new', methods=['POST'])
def create_scan():
    """Create and execute a new scan"""
    form = ScanConfigForm()
    
    # Populate plugin choices for validation
    plugins = get_available_plugins()
    form.plugins.choices = plugins
    
    if form.validate_on_submit():
        # Create scan record
        scan = Scan(
            target=form.target.data,
            scan_mode=form.scan_mode.data,
            plugins=','.join(form.plugins.data) if form.plugins.data else None,
            parallel=form.parallel.data,
            verbose=form.verbose.data,
            dry_run=form.dry_run.data,
            status='pending',
            config_json=json.dumps({
                'target': form.target.data,
                'scan_mode': form.scan_mode.data,
                'plugins': form.plugins.data,
                'parallel': form.parallel.data,
                'verbose': form.verbose.data,
                'dry_run': form.dry_run.data,
                'max_workers': form.max_workers.data
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
