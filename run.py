#!/usr/bin/env python3
"""
KAST Web - Development Server Entry Point
Run this file to start the Flask development server
"""

import os
from app import create_app

# Create Flask app instance
app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    # Run development server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
