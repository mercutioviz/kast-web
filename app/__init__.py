from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config
from datetime import datetime

# Initialize extensions
db = SQLAlchemy()

def create_app(config_name='default'):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    
    # Register custom template filters
    @app.template_filter('timestamp_to_datetime')
    def timestamp_to_datetime(timestamp):
        """Convert Unix timestamp to formatted datetime string"""
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return 'N/A'
    
    @app.template_filter('filesizeformat')
    def filesizeformat(bytes):
        """Format file size in human-readable format"""
        try:
            bytes = float(bytes)
            if bytes < 1024:
                return f"{bytes:.0f} B"
            elif bytes < 1024 * 1024:
                return f"{bytes / 1024:.1f} KB"
            elif bytes < 1024 * 1024 * 1024:
                return f"{bytes / (1024 * 1024):.1f} MB"
            else:
                return f"{bytes / (1024 * 1024 * 1024):.1f} GB"
        except (ValueError, TypeError):
            return '0 B'
    
    # Register blueprints
    from app.routes import main, scans, api
    app.register_blueprint(main.bp)
    app.register_blueprint(scans.bp)
    app.register_blueprint(api.bp)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app
