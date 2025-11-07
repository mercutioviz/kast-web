from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config

# Initialize extensions
db = SQLAlchemy()

def create_app(config_name='default'):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    
    # Register blueprints
    from app.routes import main, scans, api
    app.register_blueprint(main.bp)
    app.register_blueprint(scans.bp)
    app.register_blueprint(api.bp)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app
