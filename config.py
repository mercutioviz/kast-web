import os
from pathlib import Path

basedir = os.path.abspath(os.path.dirname(__file__))

# Application version
VERSION = '1.3.0'

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///kast.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # KAST CLI configuration
    KAST_CLI_PATH = os.environ.get('KAST_CLI_PATH') or '/usr/local/bin/kast'
    KAST_RESULTS_DIR = os.environ.get('KAST_RESULTS_DIR') or './kast_results'
    
    @classmethod
    def init_app(cls, app):
        """Initialize application-specific configuration"""
        # Only create directories if they're explicitly configured via environment variables
        # This prevents unwanted directory creation during installation
        
        # Create database directory for SQLite if DATABASE_URL is explicitly set
        database_url = os.environ.get('DATABASE_URL', '')
        if database_url.startswith('sqlite:///'):
            # Extract the database file path
            db_path = database_url.replace('sqlite:///', '')
            db_dir = Path(db_path).parent
            
            # Only create directory if it's an absolute path (production setup)
            if db_dir.is_absolute():
                try:
                    db_dir.mkdir(parents=True, exist_ok=True)
                    # Set proper permissions if we're in a system directory
                    if str(db_dir).startswith('/var/lib/') or str(db_dir).startswith('/opt/'):
                        import stat
                        db_dir.chmod(stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH)  # 775
                except (OSError, PermissionError) as e:
                    app.logger.warning(f"Could not create database directory {db_dir}: {e}")
        
        # Create results directory only if KAST_RESULTS_DIR is explicitly set
        results_dir_env = os.environ.get('KAST_RESULTS_DIR')
        if results_dir_env:
            results_dir = Path(results_dir_env)
            
            # Only create if it's an absolute path (production setup)
            if results_dir.is_absolute():
                try:
                    results_dir.mkdir(parents=True, exist_ok=True)
                    # Set proper permissions if we're in a system directory
                    if str(results_dir).startswith('/var/lib/') or str(results_dir).startswith('/opt/'):
                        import stat
                        results_dir.chmod(stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH)  # 775
                except (OSError, PermissionError) as e:
                    app.logger.warning(f"Could not create results directory {results_dir}: {e}")
    
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
