# kast-web

Web frontend for [KAST](https://github.com/your-org/kast) — the Kali Automated Scan Tool. Submit and manage ZAP-powered web-application security scans through a browser, provision ephemeral cloud scanning infrastructure, and share polished reports with stakeholders.

**Version:** 2.0.2  **Requires:** kast 3.0+

---

## Features

- **Scan management** — submit, monitor, re-run, clone, and delete scans; full execution log viewer with search
- **ZAP integration** — local, remote, and cloud ZAP execution modes; automation-plan and configuration management
- **Cloud infrastructure** — provision and tear down ephemeral ZAP instances on AWS, Azure, or GCP via Terraform; automatic orphan cleanup via Celery Beat
- **AI executive summary** — Claude-powered summary of scan findings; bring-your-own API key or use the shared org key
- **Config profiles** — save and reuse scan configurations; import/export YAML profiles
- **Report sharing** — generate shareable links with optional expiry; white-label with org logo
- **User management** — roles (admin, power\_user, user, viewer), login lockout, audit log
- **Admin panel** — dashboard with scan trend chart, settings, system info, database explorer

---

## Requirements

| Dependency | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| kast CLI | 3.0+ | installed at `KAST_CLI_PATH` (default `/usr/local/bin/kast`) |
| Redis | 6+ | Celery broker and result backend |
| Nginx | any | reverse proxy for production |

---

## Quick start

### Docker (recommended)

The Docker image handles both the web server and the Celery worker via a single image and a CMD override.

```bash
# Generate strong keys
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Web container
docker run -d \
  --name kast-web \
  -p 8000:8000 \
  -e SECRET_KEY="$SECRET_KEY" \
  -e ENCRYPTION_KEY="$ENCRYPTION_KEY" \
  -e CELERY_BROKER_URL=redis://redis:6379/0 \
  -e CELERY_RESULT_BACKEND=redis://redis:6379/0 \
  -v kast-data:/var/lib/kast-web \
  -v /usr/local/bin/kast:/usr/local/bin/kast:ro \
  kast-web:2.0.2

# Worker container (same image, different CMD)
docker run -d \
  --name kast-worker \
  -e SECRET_KEY="$SECRET_KEY" \
  -e ENCRYPTION_KEY="$ENCRYPTION_KEY" \
  -e CELERY_BROKER_URL=redis://redis:6379/0 \
  -e CELERY_RESULT_BACKEND=redis://redis:6379/0 \
  -v kast-data:/var/lib/kast-web \
  -v /usr/local/bin/kast:/usr/local/bin/kast:ro \
  kast-web:2.0.2 worker
```

The kast CLI binary must be bind-mounted or baked into a combined image; the container does not include it.

### pipx

```bash
pipx install kast-web
```

This registers the `kast-web` CLI. Run the application:

```bash
# Production (Gunicorn on port 8000)
kast-web serve

# Celery worker (separate terminal / process)
kast-web worker

# Development server with auto-reload
kast-web dev
```

### Manual / venv

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-production.txt
pip install --no-deps -e .

# Copy and edit the environment file
cp deployment/.env.production .env
# Set SECRET_KEY, ENCRYPTION_KEY, DATABASE_URL, etc. — see Configuration below

kast-web serve          # web server
kast-web worker         # celery worker (separate process)
```

---

## Configuration

All configuration is driven by environment variables (or a `.env` file in the working directory). The most important ones:

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **yes** (production) | insecure default | Flask session signing key; must be 32+ random bytes |
| `ENCRYPTION_KEY` | **yes** (production) | derived from SECRET\_KEY | Fernet key for encrypting cloud credentials at rest |
| `DATABASE_URL` | no | SQLite in `instance/` | SQLAlchemy connection string |
| `CELERY_BROKER_URL` | no | `redis://localhost:6379/0` | Redis broker for Celery |
| `CELERY_RESULT_BACKEND` | no | `redis://localhost:6379/0` | Redis backend for task results |
| `KAST_CLI_PATH` | no | `/usr/local/bin/kast` | Path to the kast CLI binary |
| `KAST_RESULTS_DIR` | no | `./kast_results` | Directory for scan output files |
| `FLASK_ENV` | no | `production` | `production` or `development` |

The app refuses to start in production if `SECRET_KEY` is the insecure default.

Generate strong keys:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Production deployment (systemd + Nginx)

Systemd service units and an Nginx config are in `deployment/`:

```
deployment/
├── .env.production           # environment variable template
├── nginx/
│   └── kast-web.conf         # Nginx reverse proxy config
└── systemd/
    ├── kast-web.service      # Gunicorn web server
    └── kast-celery.service   # Celery worker
```

Install steps:

```bash
# 1. Deploy application
sudo cp -r . /opt/kast-web
sudo chown -R www-data:www-data /opt/kast-web

# 2. Install dependencies
sudo -u www-data python3 -m venv /opt/kast-web/venv
sudo -u www-data /opt/kast-web/venv/bin/pip install -r /opt/kast-web/requirements-production.txt
sudo -u www-data /opt/kast-web/venv/bin/pip install --no-deps -e /opt/kast-web

# 3. Configure environment
sudo cp /opt/kast-web/deployment/.env.production /opt/kast-web/.env
sudo editor /opt/kast-web/.env   # set SECRET_KEY, ENCRYPTION_KEY, etc.

# 4. Create data directories
sudo mkdir -p /var/lib/kast-web/results /var/log/kast-web
sudo chown -R www-data:www-data /var/lib/kast-web /var/log/kast-web

# 5. Install systemd units and Nginx config
sudo cp deployment/systemd/kast-web.service /etc/systemd/system/
sudo cp deployment/systemd/kast-celery.service /etc/systemd/system/
sudo cp deployment/nginx/kast-web.conf /etc/nginx/sites-available/kast-web
sudo ln -s /etc/nginx/sites-available/kast-web /etc/nginx/sites-enabled/

# 6. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now redis-server kast-web kast-celery nginx
```

The web server binds to `127.0.0.1:8000`; Nginx proxies public traffic.

### Database migrations

Migrations are standalone Python scripts in `utils/`. Each script is idempotent and checks schema state before altering it.

After a fresh install, create the schema:

```bash
sudo -u www-data /opt/kast-web/venv/bin/python3 -c \
  "from app import create_app, db; app = create_app('production'); app.app_context().push(); db.create_all()"
```

For incremental upgrades, run only the scripts for new features. Check `utils/migration_tracker.py` to see which migrations have been applied.

---

## Architecture

```
Browser
  │
  ▼
Nginx (reverse proxy, static file serving)
  │
  ▼
Gunicorn (4 workers, port 8000)  ←── kast-web serve
  │
  ▼
Flask application (app/)
  ├── routes/         HTTP endpoints
  ├── models.py       SQLAlchemy ORM (SQLite default, Postgres/MySQL supported)
  ├── tasks.py        Celery task definitions (scan execution, cloud lifecycle)
  ├── cloud/          Cloud infrastructure module (AWS / Azure / GCP)
  │   ├── orchestrator.py
  │   ├── providers/{aws,azure,gcp}.py
  │   ├── terraform_manager.py
  │   └── ssh_executor.py
  ├── encryption.py   Fernet-based encryption for stored credentials
  └── templates/      Jinja2 + Bootstrap 5

Redis ◄──────────────────────────────────────────────────────┐
  │                                                           │
  ▼                                                           │
Celery worker  ←── kast-web worker                           │
  ├── execute_scan_task        shells out to kast CLI         │
  ├── cloud_provision_task     Terraform + SSH                │
  ├── cloud_teardown_task      Terraform destroy              │
  └── cloud_orphan_cleanup_task  (Beat schedule, 15 min)     │
                                                             │
kast CLI (/usr/local/bin/kast) ──────────────────────────────┘
  reads/writes scan output to KAST_RESULTS_DIR
```

### Cloud scan flow

1. User selects a cloud ZAP configuration and submits a scan.
2. `execute_scan_task` calls `cloud_provision_task`, which uses Terraform to stand up an ephemeral ZAP instance on the configured cloud provider.
3. kast-web launches kast with `--set zap.execution_mode=remote --set zap.remote.url=<provisioned-url>`.
4. kast connects to the already-running ZAP and runs the scan; results land in `KAST_RESULTS_DIR`.
5. `cloud_teardown_task` runs `terraform destroy` after the scan finishes.
6. A Celery Beat job (`cloud_orphan_cleanup_task`) runs every 15 minutes to catch infrastructure that did not tear down cleanly.

---

## Upgrading from kast 2.x (cloud mode)

kast 3.0 removes the `--mode cloud` flag. Cloud provisioning now lives entirely in kast-web. See [docs/MIGRATION_FROM_KAST_CLOUD.md](docs/MIGRATION_FROM_KAST_CLOUD.md) for step-by-step migration instructions.

---

## Development

```bash
# Clone and install with dev extras
git clone <repo-url> kast-web
cd kast-web
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Start Redis (required)
redis-server --daemonize yes

# Terminal 1 — Flask dev server (auto-reload)
kast-web dev

# Terminal 2 — Celery worker
kast-web worker --loglevel debug
```

Run the test suite:

```bash
pytest
```

Tests require Redis to be running. Cloud tests (`-m live_aws`, etc.) hit real infrastructure and are excluded by default.

---

## License

MIT — see [LICENSE](LICENSE).
