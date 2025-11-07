from flask import Blueprint, jsonify, request
from app import db
from app.models import Scan, ScanResult

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
    
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    
    # Get all results for this scan from database
    db_results = {result.plugin_name: result.to_dict() for result in scan.results.all()}
    
    # Build plugin status list based on file existence
    plugin_statuses = []
    output_dir = Path(scan.output_dir) if scan.output_dir else None
    
    # Determine which plugins to check
    if scan.plugins:
        # Specific plugins were selected
        plugin_list = scan.plugin_list
    elif output_dir and output_dir.exists():
        # No specific plugins - scan all files in output directory
        # Only look for files matching the pattern: plugin.json or plugin_processed.json
        plugin_set = set()
        for json_file in output_dir.glob("*.json"):
            filename = json_file.name
            # Skip non-plugin files
            if filename == 'kast_report.json':
                continue
            # Only consider files ending with .json or _processed.json
            if filename.endswith('_processed.json'):
                plugin_name = filename[:-len('_processed.json')]
            elif filename.endswith('.json') and not '_' in filename[:-5]:
                # Only accept simple plugin.json files (no underscores before .json)
                plugin_name = filename[:-len('.json')]
            else:
                # Skip files with other patterns (like subfinder_tmp.json)
                continue
            plugin_set.add(plugin_name)
        plugin_list = sorted(plugin_set)
    else:
        # No plugins specified and no output directory yet
        plugin_list = []
    
    # Check status for each plugin
    for plugin in plugin_list:
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
            
            if processed_file.exists():
                # Plugin completed
                plugin_status['status'] = 'completed'
                # Get data from database if available
                if plugin in db_results:
                    plugin_status['findings_count'] = db_results[plugin]['findings_count']
                    plugin_status['executed_at'] = db_results[plugin]['executed_at']
            elif raw_file.exists():
                # Plugin in progress
                plugin_status['status'] = 'in_progress'
            # else: status remains 'pending'
        
        plugin_statuses.append(plugin_status)
    
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
