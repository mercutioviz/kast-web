# KAST Web - Production Deployment Quick Start

This is a condensed guide for quickly deploying KAST Web to production. For detailed information, see [PRODUCTION_DEPLOYMENT.md](../docs/PRODUCTION_DEPLOYMENT.md).

## Prerequisites

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx redis-server
```

## Quick Deployment Steps

### 1. Setup Application

```bash
# Navigate to application directory
cd /opt/kast-web

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-production.txt

# Configure environment
cp deployment/.env.production .env
nano .env  # Update SECRET_KEY, DATABASE_URL, etc.

# Generate secure secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Initialize database
python3 migrate_db.py
```

### 2. Setup Nginx

```bash
# Copy and configure Nginx
sudo cp deployment/nginx/kast-web.conf /etc/nginx/sites-available/kast-web
sudo nano /etc/nginx/sites-available/kast-web  # Update server_name

# Enable site
sudo ln -s /etc/nginx/sites-available/kast-web /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Optional

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Setup systemd Services

```bash
# Copy service files
sudo cp deployment/systemd/kast-web.service /etc/systemd/system/
sudo cp deployment/systemd/kast-celery.service /etc/systemd/system/

# Create log directories
sudo mkdir -p /var/log/kast-web /var/run/kast-web
sudo chown -R www-data:www-data /var/log/kast-web /var/run/kast-web

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable kast-web kast-celery redis-server nginx
sudo systemctl start redis-server kast-celery kast-web nginx
```

### 4. Verify Deployment

```bash
# Check service status
sudo systemctl status kast-web
sudo systemctl status kast-celery
sudo systemctl status nginx

# Test application
curl http://localhost:8000
curl http://your-domain.com
```

## SSL Setup (Optional but Recommended)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## Common Commands

```bash
# Restart services
sudo systemctl restart kast-web
sudo systemctl restart kast-celery

# View logs
sudo journalctl -u kast-web -f
sudo tail -f /var/log/kast-web/error.log

# Update application
cd /opt/kast-web
source venv/bin/activate
git pull
pip install -r requirements-production.txt
sudo systemctl restart kast-web kast-celery
```

## Troubleshooting

### Service won't start
```bash
sudo journalctl -u kast-web -n 50 --no-pager
sudo tail -f /var/log/kast-web/error.log
```

### 502 Bad Gateway
```bash
sudo systemctl status kast-web
sudo netstat -tlnp | grep 8000
curl http://127.0.0.1:8000
```

### Permission issues
```bash
sudo chown -R www-data:www-data /opt/kast-web
sudo chown -R www-data:www-data /var/log/kast-web
sudo chmod 600 /opt/kast-web/.env
```

## Architecture

```
Internet → Nginx (80/443) → Gunicorn (8000) → Flask App
                                ↓
                             Redis ← Celery Worker
```

## Files Created

- `wsgi.py` - WSGI entry point
- `gunicorn_config.py` - Gunicorn configuration
- `deployment/nginx/kast-web.conf` - Nginx configuration
- `deployment/systemd/kast-web.service` - Gunicorn systemd service
- `deployment/systemd/kast-celery.service` - Celery systemd service
- `deployment/.env.production` - Production environment template
- `requirements-production.txt` - Production dependencies

For detailed documentation, see [PRODUCTION_DEPLOYMENT.md](../docs/PRODUCTION_DEPLOYMENT.md).
