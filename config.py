import os
from datetime import timedelta
from pathlib import Path

basedir = os.path.abspath(os.path.dirname(__file__))

_INSECURE_DEFAULT_KEY = 'dev-secret-key-change-in-production'

# Application version — read from VERSION file at repo root, fall back to 'unknown'
try:
    VERSION = Path(basedir).joinpath('VERSION').read_text().strip()
except Exception:
    VERSION = 'unknown'

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or _INSECURE_DEFAULT_KEY
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Database configuration
    # Use absolute path to ensure consistent database location
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{os.path.join(basedir, "instance", "kast-web.db")}'
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

    # Report logo uploads (see app/logo_media.py for the supported formats)
    LOGO_MAX_UPLOAD_BYTES = int(
        os.environ.get('LOGO_MAX_UPLOAD_BYTES') or 5 * 1024 * 1024
    )  # 5MB
    LOGO_MAX_DIMENSION = int(
        os.environ.get('LOGO_MAX_DIMENSION') or 2000
    )  # longest edge in pixels for normalized raster logos

    # Where logo files live. Deliberately OUTSIDE app/static: nginx serves
    # /static straight off disk, so anything under it is public and
    # unauthenticated. Logos are served only through the /logos/<id> routes,
    # which add auth and a restrictive CSP.
    # Production sets this to /var/lib/kast-web/logos in .env.
    LOGO_STORAGE_DIR = os.environ.get('LOGO_STORAGE_DIR') or \
        os.path.join(basedir, 'instance', 'logos')

    # Logo import from URL (see app/url_fetch.py)
    LOGO_STAGING_TTL_SECONDS = int(
        os.environ.get('LOGO_STAGING_TTL_SECONDS') or 1800
    )  # how long a fetched-but-unconfirmed logo is kept
    LOGO_IMPORT_ALLOWED_PORTS = tuple(
        int(p) for p in (
            os.environ.get('LOGO_IMPORT_ALLOWED_PORTS') or '80,443'
        ).split(',') if p.strip()
    )
    LOGO_IMPORT_MAX_REDIRECTS = int(
        os.environ.get('LOGO_IMPORT_MAX_REDIRECTS') or 3
    )
    LOGO_IMPORT_CONNECT_TIMEOUT = int(
        os.environ.get('LOGO_IMPORT_CONNECT_TIMEOUT') or 5
    )
    LOGO_IMPORT_READ_TIMEOUT = int(
        os.environ.get('LOGO_IMPORT_READ_TIMEOUT') or 10
    )
    LOGO_IMPORT_TOTAL_DEADLINE = int(
        os.environ.get('LOGO_IMPORT_TOTAL_DEADLINE') or 15
    )
    LOGO_IMPORT_RATE_LIMIT = int(
        os.environ.get('LOGO_IMPORT_RATE_LIMIT') or 10
    )  # fetches per minute per user; 0 disables

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

    @classmethod
    def init_app(cls, app):
        super().init_app(app)
        if app.config.get('SECRET_KEY') == _INSECURE_DEFAULT_KEY:
            raise RuntimeError(
                "SECRET_KEY is set to the insecure default value. "
                "Set a strong SECRET_KEY in the environment before starting in production."
            )

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
