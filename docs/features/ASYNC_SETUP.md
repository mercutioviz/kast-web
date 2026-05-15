# Asynchronous Scan Execution Setup Guide

This guide explains how to set up and run kast-web with asynchronous scan execution using Celery.

## Overview

The application now uses Celery to execute KAST scans asynchronously in the background. This allows:
- Immediate page load after starting a scan
- Real-time updates as the scan progresses
- Better user experience with no browser blocking

## Prerequisites

1. **Redis** - Required as the message broker for Celery
2. **Python dependencies** - Already in requirements.txt

## Installation Steps

### 1. Install and Start Redis

**Redis is REQUIRED** for async operation. The application will not work without it.

**On Debian/Ubuntu/Kali:**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**On macOS:**
```bash
brew install redis
brew services start redis
```

**Verify Redis is running:**
```bash
redis-cli ping
# Should return: PONG
```

### 2. Migrate the Database

If you have an existing database, run the migration script to add the new `celery_task_id` column:

```bash
python3 migrate_db.py
```

For new installations, the database will be created automatically with the correct schema.

### 3. Start the Application Components

You need to run **two** separate terminal processes (Redis runs as a service):

#### Terminal 1: Celery Worker
```bash
cd /opt/kast-web
source venv/bin/activate
celery -A celery_worker.celery worker --loglevel=info
```

#### Terminal 2: Flask Application
```bash
cd /opt/kast-web
./start.sh
```

**Quick Start Helper**: You can also use `./start_async.sh` which will:
- Check if Redis is running (and start it if needed)
- Show you the commands to run in separate terminals
- Start the Flask app

```bash
./start_async.sh
```

## How It Works

### 1. Scan Submission
When a user submits a new scan:
- A scan record is created in the database with status `pending`
- A Celery task is queued to execute the scan
- The user is immediately redirected to the scan detail page
- A flash message confirms the scan has started

### 2. Real-Time Updates
On the scan detail page:
- JavaScript polls the `/api/scans/<scan_id>/status` endpoint every 3 seconds
- The status badge, duration, and plugin results update automatically
- Polling stops when the scan completes or fails
- The page reloads once to show final results (reports, etc.)

### 3. Background Execution
The Celery worker:
- Picks up the queued scan task
- Updates the scan status to `running`
- Executes the KAST CLI command
- Parses results as they become available
- Updates the scan status to `completed` or `failed`

## API Endpoints

### Get Scan Status
```
GET /api/scans/<scan_id>/status
```

Returns:
```json
{
  "scan_id": 1,
  "status": "running",
  "target": "example.com",
  "started_at": "2025-11-07T09:00:00",
  "completed_at": null,
  "duration": null,
  "error_message": null,
  "results": [],
  "results_count": 0
}
```

## Troubleshooting

### "Connection refused" Error When Starting Scan
**Symptom**: Error in terminal: `Error 111 connecting to localhost:6379. Connection refused.`

**Solution**: Redis is not running. Start it with:
```bash
sudo systemctl start redis-server
```

Verify it's running:
```bash
redis-cli ping
# Should return: PONG
```

### Scans Stay in "Pending" Status
- Check if Celery worker is running
- Check Celery worker logs for errors
- Verify Redis is running: `redis-cli ping`

### Celery Worker Not Starting
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check for import errors in the worker logs
- Verify the virtual environment is activated

### Results Not Updating
- Check browser console for JavaScript errors
- Verify the API endpoint is accessible: `curl http://localhost:5000/api/scans/1/status`
- Check Flask application logs

## Configuration

### Redis Connection
Edit `config.py` to change Redis connection settings:

```python
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
```

### Polling Interval
Edit `app/templates/scan_detail.html` to change the polling frequency:

```javascript
// Poll every 3 seconds (change 3000 to desired milliseconds)
pollInterval = setInterval(updateScanStatus, 3000);
```

## Production Deployment

For production, consider:

1. **Running Celery as a service** using systemd
2. **Using a process manager** like Supervisor for the Flask app
3. **Setting up proper logging** for both Flask and Celery
4. **Configuring Redis persistence** for task reliability
5. **Using a production WSGI server** like Gunicorn instead of Flask's dev server

## Reverting to Synchronous Execution

If you need to revert to synchronous execution:

1. Edit `app/routes/main.py`
2. Replace the Celery task call with the original `execute_kast_scan()` function
3. Remove the `from app.tasks import execute_scan_task` import
4. Add back `from app.utils import execute_kast_scan`

## Additional Resources

- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/documentation)
- [Flask Documentation](https://flask.palletsprojects.com/)
