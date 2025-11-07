from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, abort
from app import db
from app.models import Scan, ScanResult
from app.utils import format_duration
from pathlib import Path
import os

bp = Blueprint('scans', __name__, url_prefix='/scans')

@bp.route('/')
def list():
    """List all scans with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get filter parameters
    status_filter = request.args.get('status', '')
    target_filter = request.args.get('target', '')
    
    # Build query
    query = Scan.query
    
    if status_filter:
        query = query.filter(Scan.status == status_filter)
    
    if target_filter:
        query = query.filter(Scan.target.contains(target_filter))
    
    # Order by most recent first
    query = query.order_by(Scan.started_at.desc())
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    scans = pagination.items
    
    return render_template(
        'scan_history.html',
        scans=scans,
        pagination=pagination,
        status_filter=status_filter,
        target_filter=target_filter,
        format_duration=format_duration
    )

@bp.route('/<int:scan_id>')
def detail(scan_id):
    """View scan details"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Get scan results
    results = scan.results.all()
    
    # Check if HTML report exists
    report_path = None
    if scan.output_dir:
        potential_report = Path(scan.output_dir) / 'kast_report.html'
        if potential_report.exists():
            report_path = str(potential_report)
    
    return render_template(
        'scan_detail.html',
        scan=scan,
        results=results,
        report_path=report_path,
        format_duration=format_duration
    )

@bp.route('/<int:scan_id>/delete', methods=['POST'])
def delete(scan_id):
    """Delete a scan"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    target = scan.target
    
    # Delete from database (cascade will delete results)
    db.session.delete(scan)
    db.session.commit()
    
    flash(f'Scan for {target} deleted successfully', 'success')
    return redirect(url_for('scans.list'))

@bp.route('/<int:scan_id>/report')
def view_report(scan_id):
    """View HTML report"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    if not scan.output_dir:
        flash('No output directory found for this scan', 'warning')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    report_path = Path(scan.output_dir) / 'kast_report.html'
    
    if not report_path.exists():
        flash('Report file not found', 'warning')
        return redirect(url_for('scans.detail', scan_id=scan_id))
    
    # Read and display report
    with open(report_path, 'r') as f:
        report_html = f.read()
    
    return render_template('report_viewer.html', scan=scan, report_html=report_html)

@bp.route('/<int:scan_id>/download')
def download_report(scan_id):
    """Download HTML report"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        abort(404)
    
    if not scan.output_dir:
        abort(404)
    
    report_path = Path(scan.output_dir) / 'kast_report.html'
    
    if not report_path.exists():
        abort(404)
    
    return send_file(
        report_path,
        as_attachment=True,
        download_name=f'kast_report_{scan.target}_{scan.id}.html'
    )

@bp.route('/<int:scan_id>/rerun', methods=['POST'])
def rerun(scan_id):
    """Re-run a scan with the same configuration"""
    original_scan = db.session.get(Scan, scan_id)
    if not original_scan:
        flash('Scan not found', 'danger')
        return redirect(url_for('scans.list'))
    
    # Create new scan with same configuration
    new_scan = Scan(
        target=original_scan.target,
        scan_mode=original_scan.scan_mode,
        plugins=original_scan.plugins,
        parallel=original_scan.parallel,
        verbose=original_scan.verbose,
        dry_run=original_scan.dry_run,
        status='pending',
        config_json=original_scan.config_json
    )
    
    db.session.add(new_scan)
    db.session.commit()
    
    flash(f'Re-running scan for {new_scan.target}', 'info')
    
    # Execute scan
    from app.utils import execute_kast_scan
    try:
        result = execute_kast_scan(
            new_scan.id,
            new_scan.target,
            new_scan.scan_mode,
            plugins=new_scan.plugin_list if new_scan.plugins else None,
            parallel=new_scan.parallel,
            verbose=new_scan.verbose,
            dry_run=new_scan.dry_run
        )
        
        if result['success']:
            flash(f'Scan completed successfully', 'success')
        else:
            flash(f'Scan failed: {result.get("error", "Unknown error")}', 'danger')
    
    except Exception as e:
        flash(f'Error executing scan: {str(e)}', 'danger')
    
    return redirect(url_for('scans.detail', scan_id=new_scan.id))
