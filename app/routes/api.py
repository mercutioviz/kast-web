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
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    
    # Get all results for this scan
    results = [result.to_dict() for result in scan.results.all()]
    
    response = {
        'scan_id': scan.id,
        'status': scan.status,
        'target': scan.target,
        'started_at': scan.started_at.isoformat() if scan.started_at else None,
        'completed_at': scan.completed_at.isoformat() if scan.completed_at else None,
        'duration': scan.duration,
        'error_message': scan.error_message,
        'results': results,
        'results_count': len(results)
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
