#!/usr/bin/env python3
"""
KAST Web - WSGI Entry Point for Production
This file is used by WSGI servers like Gunicorn
"""

import os
from app import create_app

# Create Flask app instance with production config
app = create_app(os.getenv('FLASK_ENV', 'production'))

if __name__ == '__main__':
    app.run()
