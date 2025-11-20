from flask import Blueprint, jsonify, request
from flask_login import login_required
from app import db
from app.models import Scan, ScanResult, User

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/scans', methods=['GET'])
def get_scans():
    """API endpoint to get list of scans"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '')
    
    query = Scan.query
    
    if status:
        query = query.filter(Scan.status == status)
    
    query = query.order_by(Scan.started_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'scans': [scan.to_dict() for scan in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })

@bp.route('/scans/<int:scan_id>', methods=['GET'])
def get_scan(scan_id):
    """API endpoint to get a specific scan"""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    
    results = [result.to_dict() for result in scan.results.all()]
    
    return jsonify({
        'scan': scan.to_dict(),
        'results': results
    })

@bp.route('/scans/<int:scan_id>/status', methods=['GET'])
def get_scan_status(scan_id):
    """API endpoint to get scan status and results (for polling)"""
    from pathlib import Path
    import json
    from datetime import datetime
    import logging
    
    # Set up logging for debugging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    logger.info(f"========== STATUS CHECK: Scan ID {scan_id} ==========")
    
    scan = db.session.get(Scan, scan_id)
    if not scan:
        logger.warning(f"Scan {scan_id} not found")
        return jsonify({'error': 'Scan not found'}), 404
    
    logger.info(f"Scan status: {scan.status}, target: {scan.target}")
    logger.info(f"Output directory: {scan.output_dir}")
    
    # Parse any new results during the scan
    if scan.status == 'running' and scan.output_dir:
        logger.debug("Scan is running, parsing any new results...")
        from app.tasks import parse_scan_results
        parse_scan_results(scan_id, scan.output_dir)
    
    # Get all results for this scan from database
    db_results = {result.plugin_name: result.to_dict() for result in scan.results.all()}
    logger.debug(f"Database results count: {len(db_results)}")
    logger.debug(f"Database results plugins: {list(db_results.keys())}")
    
    # Build plugin status list based on file existence
    plugin_statuses = []
    output_dir = Path(scan.output_dir) if scan.output_dir else None
    
    if output_dir:
        logger.debug(f"Checking output directory: {output_dir}")
        if output_dir.exists():
            logger.debug(f"Output directory EXISTS")
            # List all files in the directory for debugging
            try:
                all_files = sorted([f.name for f in output_dir.iterdir() if f.is_file()])
                logger.debug(f"Files in output directory ({len(all_files)}): {all_files}")
            except Exception as e:
                logger.error(f"Error listing directory contents: {e}")
        else:
            logger.warning(f"Output directory DOES NOT EXIST yet")
    else:
        logger.warning("No output directory set for this scan")
    
    # Determine which plugins to check
    if scan.plugins:
        # Specific plugins were selected
        plugin_list = scan.plugin_list
        logger.info(f"Using SPECIFIC plugins from scan config: {plugin_list}")
    elif output_dir and output_dir.exists():
        # No specific plugins - scan all files in output directory
        # Only look for files matching the pattern: plugin.json or plugin_processed.json
        logger.info("No specific plugins configured - discovering from output directory")
        plugin_set = set()
        for json_file in output_dir.glob("*.json"):
            filename = json_file.name
            logger.debug(f"Examining file: {filename}")
            # Skip non-plugin files
            if filename == 'kast_report.json':
                logger.debug(f"  -> Skipping kast_report.json")
                continue
            # Only consider files ending with .json or _processed.json
            if filename.endswith('_processed.json'):
                plugin_name = filename[:-len('_processed.json')]
                logger.debug(f"  -> Found processed file for plugin: {plugin_name}")
            elif filename.endswith('.json') and not '_' in filename[:-5]:
                # Only accept simple plugin.json files (no underscores before .json)
                plugin_name = filename[:-len('.json')]
                logger.debug(f"  -> Found raw file for plugin: {plugin_name}")
            else:
                # Skip files with other patterns (like subfinder_tmp.json)
                logger.debug(f"  -> Skipping file (pattern doesn't match)")
                continue
            plugin_set.add(plugin_name)
        plugin_list = sorted(plugin_set)
        logger.info(f"Discovered {len(plugin_list)} plugins from files: {plugin_list}")
    else:
        # No plugins specified and no output directory yet
        logger.info("No plugins configured and no output directory - empty plugin list")
        plugin_list = []
    
    # Check status for each plugin
    logger.info(f"Checking status for {len(plugin_list)} plugins...")
    for plugin in plugin_list:
        logger.debug(f"--- Plugin: {plugin} ---")
        plugin_status = {
            'plugin_name': plugin,
            'status': 'pending',
            'findings_count': 0,
            'executed_at': None
        }
        
        # Check file existence to determine status
        if output_dir and output_dir.exists():
            processed_file = output_dir / f"{plugin}_processed.json"
            raw_file = output_dir / f"{plugin}.json"
            
            logger.debug(f"  Checking processed file: {processed_file.name} -> exists={processed_file.exists()}")
            logger.debug(f"  Checking raw file: {raw_file.name} -> exists={raw_file.exists()}")
            
            if processed_file.exists():
                # Plugin completed
                plugin_status['status'] = 'completed'
                logger.debug(f"  Status: COMPLETED (processed file exists)")
                # Get data from database if available
                if plugin in db_results:
                    plugin_status['findings_count'] = db_results[plugin]['findings_count']
                    plugin_status['executed_at'] = db_results[plugin]['executed_at']
                    logger.debug(f"  Database data: {db_results[plugin]['findings_count']} findings")
                else:
                    logger.debug(f"  No database entry found for this plugin yet")
            elif raw_file.exists():
                # Plugin in progress
                plugin_status['status'] = 'in_progress'
                logger.debug(f"  Status: IN_PROGRESS (raw file exists, no processed file)")
            else:
                # Status remains 'pending'
                logger.debug(f"  Status: PENDING (no files found)")
        else:
            logger.debug(f"  Status: PENDING (output directory not available)")
        
        plugin_statuses.append(plugin_status)
        logger.debug(f"  Final status: {plugin_status['status']}")
    
    response = {
        'scan_id': scan.id,
        'status': scan.status,
        'target': scan.target,
        'started_at': scan.started_at.isoformat() if scan.started_at else None,
        'completed_at': scan.completed_at.isoformat() if scan.completed_at else None,
        'duration': scan.duration,
        'error_message': scan.error_message,
        'results': plugin_statuses,
        'results_count': len(plugin_statuses)
    }
    
    # Log summary of response
    status_summary = {}
    for ps in plugin_statuses:
        status = ps['status']
        status_summary[status] = status_summary.get(status, 0) + 1
    logger.info(f"Response summary: {len(plugin_statuses)} total plugins - {status_summary}")
    logger.info(f"========== END STATUS CHECK ==========\n")
    
    return jsonify(response)

@bp.route('/plugins', methods=['GET'])
def get_plugins():
    """API endpoint to get available plugins"""
    from app.utils import get_available_plugins
    
    plugins = get_available_plugins()
    
    return jsonify({
        'plugins': [{'name': name, 'description': desc} for name, desc in plugins]
    })

@bp.route('/stats', methods=['GET'])
def get_stats():
    """API endpoint to get scan statistics"""
    total_scans = Scan.query.count()
    completed_scans = Scan.query.filter(Scan.status == 'completed').count()
    failed_scans = Scan.query.filter(Scan.status == 'failed').count()
    running_scans = Scan.query.filter(Scan.status == 'running').count()
    
    return jsonify({
        'total_scans': total_scans,
        'completed': completed_scans,
        'failed': failed_scans,
        'running': running_scans
    })

@bp.route('/users/active', methods=['GET'])
@login_required
def get_active_users():
    """API endpoint to get active users for sharing"""
    users = User.query.filter_by(is_active=True).order_by(User.username).all()
    
    return jsonify({
        'users': [{
            'id': user.id,
            'username': user.username,
            'email': user.email
        } for user in users]
    })
