#!/usr/bin/env python3
"""
Celery worker configuration for KAST Web
Run with: celery -A celery_worker.celery worker --loglevel=info
"""

import os
from celery import Celery

# Initialize Celery with config
celery = Celery(
    'kast_web',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

# Celery configuration
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,  # Explicitly enable connection retries during startup (Celery 6.0+ compatibility)
)

# Import Flask app for context (done after Celery init to avoid circular import)
def get_flask_app():
    """Lazy load Flask app to avoid circular imports"""
    from app import create_app
    return create_app(os.getenv('FLASK_ENV', 'development'))

# Set Flask app context for tasks
class ContextTask(celery.Task):
    _flask_app = None
    
    @property
    def flask_app(self):
        if self._flask_app is None:
            self._flask_app = get_flask_app()
        return self._flask_app
    
    def __call__(self, *args, **kwargs):
        with self.flask_app.app_context():
            return self.run(*args, **kwargs)

celery.Task = ContextTask

# Import tasks to register them with Celery
# This must be done after Celery is configured
from app import tasks  # noqa: F401
