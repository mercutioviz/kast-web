#!/bin/bash
# Script to verify Celery worker is running and configured correctly

echo "=========================================="
echo "Celery Worker Verification"
echo "=========================================="
echo ""

# Check if Redis is running
echo "1. Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "   ✓ Redis is running"
else
    echo "   ✗ Redis is NOT running"
    echo "   Start it with: sudo systemctl start redis-server"
    exit 1
fi
echo ""

# Check if Celery worker process is running
echo "2. Checking for Celery worker process..."
if ps aux | grep -v grep | grep "celery.*worker" > /dev/null; then
    echo "   ✓ Celery worker process is running"
    echo ""
    echo "   Process details:"
    ps aux | grep -v grep | grep "celery.*worker" | head -3
else
    echo "   ✗ Celery worker is NOT running"
    echo ""
    echo "   Start it with:"
    echo "   cd /opt/kast-web"
    echo "   source venv/bin/activate"
    echo "   celery -A celery_worker.celery worker --loglevel=info"
    exit 1
fi
echo ""

# Check if worker responds to ping
echo "3. Pinging Celery worker..."
cd /opt/kast-web
source venv/bin/activate
PING_RESULT=$(celery -A celery_worker.celery inspect ping 2>&1)

if echo "$PING_RESULT" | grep -q "pong"; then
    echo "   ✓ Worker responds to ping"
    echo "$PING_RESULT" | grep -A 1 "pong"
else
    echo "   ✗ Worker does not respond"
    echo "   Output: $PING_RESULT"
    exit 1
fi
echo ""

# Check registered tasks
echo "4. Checking registered tasks..."
TASKS=$(celery -A celery_worker.celery inspect registered 2>&1)

if echo "$TASKS" | grep -q "execute_scan_task"; then
    echo "   ✓ Scan tasks are registered"
    echo "$TASKS" | grep "execute_scan_task"
    echo "$TASKS" | grep "parse_scan_results_task"
else
    echo "   ✗ Tasks not properly registered"
    echo "   Output: $TASKS"
    exit 1
fi
echo ""

# Check active tasks
echo "5. Checking for active tasks..."
ACTIVE=$(celery -A celery_worker.celery inspect active 2>&1)

if echo "$ACTIVE" | grep -q "empty"; then
    echo "   ℹ No tasks currently running (this is normal if no scans are active)"
else
    echo "   ℹ Active tasks found:"
    echo "$ACTIVE"
fi
echo ""

echo "=========================================="
echo "✓ All checks passed!"
echo "Celery worker is running and ready"
echo "=========================================="
