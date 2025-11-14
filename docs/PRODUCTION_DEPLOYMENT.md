# KAST Web - Production Deployment Guide

This guide provides comprehensive instructions for deploying KAST Web in a production environment using Gunicorn, Nginx, and systemd.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Installation Steps](#installation-steps)
4. [Configuration](#configuration)
5. [SSL/TLS Setup](#ssltls-setup)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Security Best Practices](#security-best-practices)

## Architecture Overview

The production deployment uses the following stack:

- **Gunicorn**: WSGI HTTP server for running the Flask application
- **Nginx**: Reverse proxy and static file server
- **Redis**: Message broker for Celery task queue
- **Celery**: Asynchronous task processing
- **systemd**: Service management for automatic startup and monitoring

```
Internet → Nginx (Port 80/443) → Gunicorn (Port 8000) → Flask App
                                      ↓
                                   Redis ← Celery Worker
```

## Prerequisites

### System Requirements

- Linux server (Ubuntu 20.04+, Debian 11+, or similar)
- Python 3.8 or higher
- 2GB RAM minimum (4GB recommended)
- 10GB disk space minimum

### Required Software

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv nginx redis-server

# Install optional but recommended packages
sudo apt install -y git curl wget certbot python3-certbot-nginx
```

## Installation Steps

### 1. Create Application User

```bash
# Create a dedicated user for running the application
sudo useradd -r -s /bin/bash -d /opt/kast-web -m www-data

# Set proper ownership
sudo chown -R www-data:www-data /opt/kast-web
```

### 2. Clone and Setup Application

```bash
# Switch to application directory
cd /opt/kast-web

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install production dependencies
pip install -r requirements-production.txt

# Create necessary directories
mkdir -p /var/log/kast-web
mkdir -p /var/run/kast-web
sudo chown -R www-data:www-data /var/log/kast-web /var/run/kast-web
```

### 3. Configure Environment

```bash
# Copy and edit production environment file
cp deployment/.env.production .env
nano .env

# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_hex(32))"
# Copy the output and update SECRET_KEY in .env
```

**Important**: Update the following in `.env`:
- `SECRET_KEY`: Use the generated secure key
- `DATABASE_URL`: Configure your database connection
- `CELERY_BROKER_URL`: Verify Redis connection
- `KAST_CLI_PATH`: Ensure correct path to KAST CLI

### 4. Initialize Database

```bash
# Run database migrations
python3 migrate_db.py

# Verify database creation
ls -la ~/kast-web/db/
```

### 5. Configure Gunicorn

The `gunicorn_config.py` file is already configured with production-ready settings:

- **Workers**: Automatically calculated based on CPU cores (2 × CPU + 1)
- **Binding**: localhost:8000 (not exposed to internet)
- **Logging**: Configured to `/var/log/kast-web/`
- **Timeouts**: 30 seconds for request handling

You can customize these settings by editing `gunicorn_config.py`.

### 6. Setup Nginx

```bash
# Copy Nginx configuration
sudo cp deployment/nginx/kast-web.conf /etc/nginx/sites-available/kast-web

# Edit the configuration to set your domain
sudo nano /etc/nginx/sites-available/kast-web
# Update: server_name your-domain.com www.your-domain.com

# Create symbolic link to enable site
sudo ln -s /etc/nginx/sites-available/kast-web /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### 7. Setup systemd Services

```bash
# Copy systemd service files
sudo cp deployment/systemd/kast-web.service /etc/systemd/system/
sudo cp deployment/systemd/kast-celery.service /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable kast-web
sudo systemctl enable kast-celery
sudo systemctl enable redis-server
sudo systemctl enable nginx

# Start services
sudo systemctl start redis-server
sudo systemctl start kast-celery
sudo systemctl start kast-web
sudo systemctl start nginx
```

### 8. Verify Deployment

```bash
# Check service status
sudo systemctl status kast-web
sudo systemctl status kast-celery
sudo systemctl status nginx
sudo systemctl status redis-server

# Check logs
sudo journalctl -u kast-web -f
sudo tail -f /var/log/kast-web/access.log
sudo tail -f /var/log/kast-web/error.log

# Test application
curl http://localhost:8000
curl http://your-domain.com
```

## Configuration

### Gunicorn Configuration

Edit `gunicorn_config.py` to customize:

```python
# Number of worker processes
workers = multiprocessing.cpu_count() * 2 + 1

# Worker class (sync, gevent, eventlet)
worker_class = "sync"

# Timeout for requests
timeout = 30

# Binding address
bind = "127.0.0.1:8000"
```

### Nginx Configuration

Key settings in `deployment/nginx/kast-web.conf`:

- **Static files**: Served directly by Nginx for better performance
- **Proxy settings**: Configured for Gunicorn backend
- **WebSocket support**: Enabled for Flask-SocketIO
- **Security headers**: X-Frame-Options, X-Content-Type-Options, etc.
- **Client max body size**: 16MB (matches Flask config)

### Database Options

#### SQLite (Default)
```bash
DATABASE_URL=sqlite:////home/kali/kast-web/db/kast.db
```

#### PostgreSQL (Recommended for Production)
```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE kast_web;
CREATE USER kast_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE kast_web TO kast_user;
\q

# Update .env
DATABASE_URL=postgresql://kast_user:secure_password@localhost:5432/kast_web

# Install Python driver
pip install psycopg2-binary
```

#### MySQL/MariaDB
```bash
# Install MySQL
sudo apt install mysql-server

# Create database and user
sudo mysql
CREATE DATABASE kast_web;
CREATE USER 'kast_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON kast_web.* TO 'kast_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# Update .env
DATABASE_URL=mysql+pymysql://kast_user:secure_password@localhost:3306/kast_web

# Install Python driver
pip install PyMySQL
```

## SSL/TLS Setup

### Using Let's Encrypt (Recommended)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Certbot will automatically configure Nginx for HTTPS
# Or manually uncomment the HTTPS server block in kast-web.conf

# Test automatic renewal
sudo certbot renew --dry-run

# Certificates auto-renew via systemd timer
sudo systemctl status certbot.timer
```

### Using Custom SSL Certificate

```bash
# Copy your certificate files
sudo cp your-cert.crt /etc/ssl/certs/kast-web.crt
sudo cp your-key.key /etc/ssl/private/kast-web.key

# Update Nginx configuration
sudo nano /etc/nginx/sites-available/kast-web
# Uncomment HTTPS server block and update certificate paths

# Reload Nginx
sudo systemctl reload nginx
```

## Monitoring and Maintenance

### Service Management

```bash
# Start/Stop/Restart services
sudo systemctl start kast-web
sudo systemctl stop kast-web
sudo systemctl restart kast-web

# View service status
sudo systemctl status kast-web
sudo systemctl status kast-celery

# View logs
sudo journalctl -u kast-web -f
sudo journalctl -u kast-celery -f
```

### Log Files

- **Gunicorn Access**: `/var/log/kast-web/access.log`
- **Gunicorn Error**: `/var/log/kast-web/error.log`
- **Celery**: `/var/log/kast-web/celery.log`
- **Nginx Access**: `/var/log/nginx/kast-web-access.log`
- **Nginx Error**: `/var/log/nginx/kast-web-error.log`

### Log Rotation

Create `/etc/logrotate.d/kast-web`:

```bash
/var/log/kast-web/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload kast-web > /dev/null 2>&1 || true
    endscript
}
```

### Database Backup

```bash
# SQLite backup
cp ~/kast-web/db/kast.db ~/kast-web/db/kast.db.backup.$(date +%Y%m%d)

# PostgreSQL backup
pg_dump -U kast_user kast_web > kast_web_backup_$(date +%Y%m%d).sql

# MySQL backup
mysqldump -u kast_user -p kast_web > kast_web_backup_$(date +%Y%m%d).sql
```

### Automated Backups

Create `/etc/cron.daily/kast-web-backup`:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/kast-web"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR

# Backup database
cp ~/kast-web/db/kast.db $BACKUP_DIR/kast.db.$DATE

# Keep only last 7 days
find $BACKUP_DIR -name "kast.db.*" -mtime +7 -delete

# Backup configuration
tar -czf $BACKUP_DIR/config.$DATE.tar.gz /opt/kast-web/.env /opt/kast-web/config.py
```

Make it executable:
```bash
sudo chmod +x /etc/cron.daily/kast-web-backup
```

## Troubleshooting

### Application Won't Start

```bash
# Check service status
sudo systemctl status kast-web

# View detailed logs
sudo journalctl -u kast-web -n 100 --no-pager

# Check if port is already in use
sudo netstat -tlnp | grep 8000

# Verify Python environment
source /opt/kast-web/venv/bin/activate
python -c "from app import create_app; app = create_app('production')"
```

### Nginx 502 Bad Gateway

```bash
# Check if Gunicorn is running
sudo systemctl status kast-web

# Check Gunicorn logs
sudo tail -f /var/log/kast-web/error.log

# Verify Gunicorn is listening
sudo netstat -tlnp | grep 8000

# Test Gunicorn directly
curl http://127.0.0.1:8000
```

### Celery Tasks Not Processing

```bash
# Check Celery worker status
sudo systemctl status kast-celery

# Check Redis is running
sudo systemctl status redis-server
redis-cli ping  # Should return PONG

# View Celery logs
sudo tail -f /var/log/kast-web/celery.log

# Test Celery connection
source /opt/kast-web/venv/bin/activate
python -c "from celery_worker import celery; print(celery.control.inspect().active())"
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R www-data:www-data /opt/kast-web
sudo chown -R www-data:www-data /var/log/kast-web
sudo chown -R www-data:www-data /var/run/kast-web
sudo chown -R www-data:www-data ~/kast-web
sudo chown -R www-data:www-data ~/kast_results

# Fix permissions
sudo chmod -R 755 /opt/kast-web
sudo chmod 600 /opt/kast-web/.env
```

### High Memory Usage

```bash
# Check memory usage
free -h
ps aux | grep gunicorn | awk '{sum+=$6} END {print sum/1024 " MB"}'

# Reduce number of workers in gunicorn_config.py
workers = 2  # Instead of auto-calculated

# Restart service
sudo systemctl restart kast-web
```

## Security Best Practices

### 1. Firewall Configuration

```bash
# Install UFW
sudo apt install ufw

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### 2. Secure Environment Variables

```bash
# Restrict .env file permissions
chmod 600 /opt/kast-web/.env
chown www-data:www-data /opt/kast-web/.env

# Never commit .env to version control
echo ".env" >> .gitignore
```

### 3. Regular Updates

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python packages
source /opt/kast-web/venv/bin/activate
pip list --outdated
pip install --upgrade package-name
```

### 4. Fail2ban (Optional)

```bash
# Install Fail2ban
sudo apt install fail2ban

# Configure for Nginx
sudo nano /etc/fail2ban/jail.local
```

Add:
```ini
[nginx-http-auth]
enabled = true

[nginx-noscript]
enabled = true

[nginx-badbots]
enabled = true
```

```bash
# Restart Fail2ban
sudo systemctl restart fail2ban
```

### 5. Database Security

- Use strong passwords
- Restrict database access to localhost
- Regular backups
- Enable SSL for database connections (if using PostgreSQL/MySQL)

### 6. Application Security

- Keep `SECRET_KEY` secure and unique
- Enable HTTPS in production
- Set `SESSION_COOKIE_SECURE=True` when using HTTPS
- Regularly update dependencies
- Monitor logs for suspicious activity

## Performance Optimization

### 1. Gunicorn Workers

Adjust based on your server resources:
```python
# CPU-bound applications
workers = (2 × CPU_cores) + 1

# I/O-bound applications (with gevent/eventlet)
workers = (4 × CPU_cores) + 1
worker_class = "gevent"
```

### 2. Nginx Caching

Add to Nginx configuration:
```nginx
# Cache static files
location /static {
    alias /opt/kast-web/app/static;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

### 3. Database Connection Pooling

For PostgreSQL, add to `.env`:
```bash
SQLALCHEMY_ENGINE_OPTIONS={"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True}
```

### 4. Redis Optimization

Edit `/etc/redis/redis.conf`:
```conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

## Scaling Considerations

### Horizontal Scaling

- Use a load balancer (HAProxy, Nginx) to distribute traffic
- Run multiple Gunicorn instances on different servers
- Use a centralized database (PostgreSQL/MySQL)
- Use Redis Sentinel or Redis Cluster for high availability

### Vertical Scaling

- Increase server resources (CPU, RAM)
- Adjust Gunicorn worker count
- Optimize database queries
- Use caching (Redis, Memcached)

## Additional Resources

- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Flask Deployment Options](https://flask.palletsprojects.com/en/latest/deploying/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)

## Support

For issues specific to KAST Web, please refer to the main README.md or open an issue on the project repository.
