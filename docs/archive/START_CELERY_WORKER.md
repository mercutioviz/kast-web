# Starting the Celery Worker

## The Problem

Scans are stuck on "pending" status because the **Celery worker is not running**. The worker is responsible for picking up scan tasks from the queue and executing them in the background.

## Quick Start

Open a **NEW terminal window** and run:

```bash
cd /opt/kast-web
source venv/bin/activate
celery -A celery_worker.celery worker --loglevel=info
```

**Keep this terminal open** - the worker needs to stay running to process scans.

## What You Should See

When the worker starts successfully, you'll see output like:

```
 -------------- celery@hostname v5.3.4 (emerald-rush)
--- ***** ----- 
-- ******* ---- Linux-6.16-x86_64-with-glibc2.39 2025-11-07 09:28:00
- *** --- * --- 
- ** ---------- [config]
- ** ---------- .> app:         kast_web:0x...
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     redis://localhost:6379/0
- *** --- * --- .> concurrency: 4 (prefork)
-- ******* ---- .> task events: OFF (enable -E to monitor tasks in this worker)
--- ***** ----- 
 -------------- [queues]
                .> celery           exchange=celery(direct) key=celery

[tasks]
  . app.tasks.execute_scan_task
  . app.tasks.parse_scan_results_task

[2025-11-07 09:28:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-11-07 09:28:00,000: INFO/MainProcess] mingle: searching for neighbors
[2025-11-07 09:28:01,000: INFO/MainProcess] mingle: all alone
[2025-11-07 09:28:01,000: INFO/MainProcess] celery@hostname ready.
```

## Verifying the Worker is Running

In another terminal, run:

```bash
cd /opt/kast-web
source venv/bin/activate
celery -A celery_worker.celery inspect ping
```

You should see:

```
-> celery@hostname: OK
    pong
```

## Complete Startup Sequence

You need **TWO terminals** running simultaneously:

### Terminal 1: Celery Worker (Start FIRST)
```bash
cd /opt/kast-web
source venv/bin/activate
celery -A celery_worker.celery worker --loglevel=info
```

### Terminal 2: Flask Application (Start SECOND)
```bash
cd /opt/kast-web
./start.sh
```

## Testing

Once both are running:

1. Go to http://localhost:5000
2. Submit a new scan
3. You should be immediately redirected to the scan detail page
4. Watch Terminal 1 (Celery worker) - you should see task execution logs
5. The scan detail page should update every 3 seconds as the scan progresses

## Troubleshooting

### Worker Won't Start

**Error: "No module named 'celery_worker'"**
- Make sure you're in `/opt/kast-web` directory
- Make sure virtual environment is activated

**Error: "Connection refused to Redis"**
- Start Redis: `sudo systemctl start redis-server`
- Verify: `redis-cli ping` (should return PONG)

### Worker Starts But Tasks Don't Execute

**Check if tasks are registered:**
```bash
celery -A celery_worker.celery inspect registered
```

You should see:
```
app.tasks.execute_scan_task
app.tasks.parse_scan_results_task
```

### Stopping the Worker

Press `Ctrl+C` in the terminal where the worker is running.

## Running as a Background Service (Optional)

For production or persistent operation, you can run Celery as a systemd service. See `ASYNC_SETUP.md` for details.
