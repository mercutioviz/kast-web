from datetime import datetime
from app import db

class Scan(db.Model):
    """Model for storing scan information"""
    __tablename__ = 'scans'
    
    id = db.Column(db.Integer, primary_key=True)
    target = db.Column(db.String(255), nullable=False, index=True)
    scan_mode = db.Column(db.String(20), nullable=False, default='passive')  # active or passive
    plugins = db.Column(db.Text)  # Comma-separated list of plugins
    parallel = db.Column(db.Boolean, default=False)
    verbose = db.Column(db.Boolean, default=False)
    dry_run = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, running, completed, failed
    output_dir = db.Column(db.String(500))
    config_json = db.Column(db.Text)  # JSON string of full configuration
    error_message = db.Column(db.Text)
    celery_task_id = db.Column(db.String(255))  # Celery task ID for tracking
    started_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    results = db.relationship('ScanResult', backref='scan', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Scan {self.id}: {self.target} ({self.status})>'
    
    @property
    def duration(self):
        """Calculate scan duration"""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None
    
    @property
    def plugin_list(self):
        """Return plugins as a list"""
        if self.plugins:
            return [p.strip() for p in self.plugins.split(',')]
        return []
    
    def to_dict(self):
        """Convert scan to dictionary"""
        return {
            'id': self.id,
            'target': self.target,
            'scan_mode': self.scan_mode,
            'plugins': self.plugin_list,
            'parallel': self.parallel,
            'verbose': self.verbose,
            'dry_run': self.dry_run,
            'status': self.status,
            'output_dir': self.output_dir,
            'error_message': self.error_message,
            'celery_task_id': self.celery_task_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration': self.duration
        }

class ScanResult(db.Model):
    """Model for storing individual plugin results"""
    __tablename__ = 'scan_results'
    
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), nullable=False, index=True)
    plugin_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # success, fail, skipped
    findings_count = db.Column(db.Integer, default=0)
    raw_output_path = db.Column(db.String(500))
    processed_output_path = db.Column(db.String(500))
    error_message = db.Column(db.Text)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ScanResult {self.id}: {self.plugin_name} ({self.status})>'
    
    def to_dict(self):
        """Convert result to dictionary"""
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'plugin_name': self.plugin_name,
            'status': self.status,
            'findings_count': self.findings_count,
            'raw_output_path': self.raw_output_path,
            'processed_output_path': self.processed_output_path,
            'error_message': self.error_message,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None
        }
