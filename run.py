#!/usr/bin/env python3
"""
KAST Web - Development Server Entry Point
Run this file to start the Flask development server
"""

import os
import logging
from app import create_app

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set specific loggers to appropriate levels
logging.getLogger('werkzeug').setLevel(logging.INFO)  # Reduce werkzeug noise
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)  # Reduce SQL noise

# Create Flask app instance
app = create_app(os.getenv('FLASK_ENV', 'development'))

# Ensure app logger is at DEBUG level
app.logger.setLevel(logging.DEBUG)

if __name__ == '__main__':
    print("=" * 60)
    print("KAST Web - Development Server")
    print("Logging configured at DEBUG level")
    print("Status endpoint debugging is ENABLED")
    print("=" * 60)
    
    # Run development server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
