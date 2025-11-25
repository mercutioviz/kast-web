from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import config
from datetime import datetime

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_name='default'):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    
    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login"""
        from app.models import User
        return db.session.get(User, int(user_id))
    
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
    
    # Context processor to inject version into all templates
    @app.context_processor
    def inject_version():
        """Make version available to all templates"""
        from config import VERSION
        return {'app_version': VERSION}
    
    # Register blueprints
    from app.routes import main, scans, api, auth, admin, logos
    app.register_blueprint(main.bp)
    app.register_blueprint(scans.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(logos.bp)
    
    # Initialize Flask-Admin for database explorer
    from app.admin_db import init_admin
    init_admin(app, db)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app
