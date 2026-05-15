# Quick Reference - Async Scans

## Verify Celery Worker Status

Run this anytime to check if Celery is running:

```bash
./verify_celery.sh
```

**Expected output when working:**
```
✓ Redis is running
✓ Celery worker process is running
✓ Worker responds to ping
✓ Scan tasks are registered
✓ All checks passed!
```

**If worker is NOT running, you'll see:**
```
✗ Celery worker is NOT running
```

## Start Celery Worker

**Open a NEW terminal** and run:

```bash
cd /opt/kast-web
source venv/bin/activate
celery -A celery_worker.celery worker --loglevel=info
```

Keep this terminal open while using the application.

## Quick Commands

### Check if worker is running
```bash
ps aux | grep celery | grep -v grep
```

### Ping the worker
```bash
cd /opt/kast-web
source venv/bin/activate
celery -A celery_worker.celery inspect ping
```

### See registered tasks
```bash
cd /opt/kast-web
source venv/bin/activate
celery -A celery_worker.celery inspect registered
```

### See active/running tasks
```bash
cd /opt/kast-web
source venv/bin/activate
celery -A celery_worker.celery inspect active
```

### Stop the worker
Press `Ctrl+C` in the terminal where it's running

## Typical Startup Sequence

1. **Start Redis** (if not already running):
   ```bash
   sudo systemctl start redis-server
   ```

2. **Terminal 1 - Start Celery Worker**:
   ```bash
   cd /opt/kast-web
   source venv/bin/activate
   celery -A celery_worker.celery worker --loglevel=info
   ```

3. **Terminal 2 - Start Flask App**:
   ```bash
   cd /opt/kast-web
   ./start.sh
   ```

4. **Verify everything is working**:
   ```bash
   ./verify_celery.sh
   ```

## Troubleshooting

### Scans stuck on "pending"
→ Celery worker is not running. Start it as shown above.

### "Connection refused" errors
→ Redis is not running. Start it: `sudo systemctl start redis-server`

### Worker starts but tasks don't execute
→ Check registered tasks: `celery -A celery_worker.celery inspect registered`
→ Should show `app.tasks.execute_scan_task`

## What You Should See

### In Celery Worker Terminal
When a scan starts, you'll see:
```
[2025-11-07 09:30:00,000: INFO/MainProcess] Task app.tasks.execute_scan_task[abc-123] received
[2025-11-07 09:30:00,000: INFO/ForkPoolWorker-1] Executing KAST command: ...
[2025-11-07 09:35:00,000: INFO/ForkPoolWorker-1] Task app.tasks.execute_scan_task[abc-123] succeeded
```

### In Browser
- Scan detail page loads immediately
- Status updates every 3 seconds
- Plugin results appear as they complete
- Status changes: pending → running → completed
