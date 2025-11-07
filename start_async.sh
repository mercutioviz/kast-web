#!/bin/bash
# KAST Web - Async Start Script
# This script starts all required components for async operation

echo "=========================================="
echo "KAST Web - Async Mode Startup"
echo "=========================================="
echo ""

# Check if Redis is running
echo "Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis is running"
else
    echo "✗ Redis is not running"
    echo "  Starting Redis..."
    sudo systemctl start redis-server
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        echo "✓ Redis started successfully"
    else
        echo "✗ Failed to start Redis"
        echo "  Please start Redis manually: sudo systemctl start redis-server"
        exit 1
    fi
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Set environment variables
export FLASK_APP=run.py
export FLASK_ENV=development

echo "=========================================="
echo "Starting Components"
echo "=========================================="
echo ""
echo "You need to run these in separate terminals:"
echo ""
echo "Terminal 1 - Celery Worker:"
echo "  cd /opt/kast-web"
echo "  source venv/bin/activate"
echo "  celery -A celery_worker.celery worker --loglevel=info"
echo ""
echo "Terminal 2 - Flask App:"
echo "  cd /opt/kast-web"
echo "  ./start.sh"
echo ""
echo "=========================================="
echo ""
echo "Press Enter to start Flask app in this terminal..."
read

# Run the application
python3 run.py
