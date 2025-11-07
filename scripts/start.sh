#!/bin/bash
# KAST Web - Quick Start Script

echo "Starting KAST Web..."
echo "===================="
echo ""

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export FLASK_APP=run.py
export FLASK_ENV=development

# Run the application
python3 run.py
