import os
from pathlib import Path

basedir = os.path.abspath(os.path.dirname(__file__))

# Application version
VERSION = '1.1.0'

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database configuration
    # Use environment variable if set, otherwise use default path
    _db_dir = Path.home() / 'kast-web' / 'db'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{_db_dir / "kast.db"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # KAST CLI configuration
    KAST_CLI_PATH = os.environ.get('KAST_CLI_PATH') or '/usr/local/bin/kast'
    KAST_RESULTS_DIR = Path.home() / 'kast_results'
    
    @classmethod
    def init_app(cls, app):
        """Initialize application-specific configuration"""
        # Create database directory only if using SQLite and path is not set via env
        if not os.environ.get('DATABASE_URL'):
            db_dir = cls._db_dir
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as e:
                app.logger.warning(f"Could not create database directory {db_dir}: {e}")
    
    # Celery configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    
    # Pagination
    SCANS_PER_PAGE = 20
    
    # File upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    # In production, ensure SECRET_KEY is set via environment variable

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
