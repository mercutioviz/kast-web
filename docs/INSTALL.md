# KAST-Web Installation Guide

This guide provides detailed instructions for installing KAST-Web using the automated installer script.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Installation Options](#installation-options)
- [Interactive Installation](#interactive-installation)
- [Non-Interactive Installation](#non-interactive-installation)
- [Post-Installation](#post-installation)
- [Validation](#validation)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

## Prerequisites

### Required

1. **KAST CLI Tool**: The KAST CLI must be installed and available at `/usr/local/bin/kast`
   - If KAST is installed elsewhere, the installer will fail
   - Verify with: `which kast` or `kast --version`

2. **Operating System**: 
   - Ubuntu 18.04+ (tested)
   - Debian 10+ (tested)
   - Kali Linux (tested)
   - Other Debian-based distributions (may work)

3. **Root Access**: Installation requires root privileges (sudo)

4. **Disk Space**: Minimum 1GB free space in `/opt`

5. **Internet Connection**: Required for downloading packages

### Recommended

- 2GB RAM minimum (4GB+ recommended for production)
- Modern multi-core processor
- Domain name (for SSL setup)

## Quick Start

For a basic installation with default settings (SQLite database, auto-detected web server):

```bash
# Clone or download KAST-Web repository to /opt/kast-web
cd /opt
git clone https://github.com/mercutioviz/kast-web.git kast-web
cd kast-web

# Run the installer
sudo ./install.sh
```

The installer will:
1. Detect your system configuration
2. Prompt for admin credentials
3. Install all dependencies
4. Configure services
5. Start KAST-Web

## Installation Options

The installer supports various command-line options for automated/customized installations:

### Database Options

```bash
--database=TYPE
```

Where TYPE is one of:
- `sqlite` (default) - Simple, no additional setup
- `postgresql` - Recommended for production
- `mysql` - MySQL database
- `mariadb` - MariaDB database

### Web Server Options

```bash
--web-server=SERVER
```

Where SERVER is:
- `nginx` (recommended) - Automatically installed if not present
- `apache` - Uses Apache if installed, or installs it

If not specified, the installer will:
1. Detect existing web servers
2. Prompt you to choose if both are installed
3. Install Nginx if neither is present

### SSL/TLS Configuration

```bash
--ssl              # Install Let's Encrypt SSL certificate
--no-ssl           # Skip SSL setup (default)
--domain=DOMAIN    # Domain name for SSL and web server config
```

**Note**: SSL requires a valid domain name (not localhost)

### Admin User Configuration

```bash
--admin-user=USERNAME          # Admin username (3-80 characters)
--admin-email=EMAIL           # Admin email address
--admin-pass=PASSWORD         # Admin password (min 8 characters)
--admin-first-name=FIRSTNAME  # Optional first name
--admin-last-name=LASTNAME    # Optional last name
```

### Non-Interactive Mode

```bash
--non-interactive
```

Runs the installer without prompting for input. Requires all necessary parameters to be provided via command-line options.

### Help

```bash
--help, -h
```

Display help message with all available options.

## Interactive Installation

The interactive installation mode guides you through each step with prompts:

```bash
sudo ./install.sh
```

You will be prompted for:
1. **Database Type**: Choose from SQLite, PostgreSQL, MySQL, or MariaDB
2. **Web Server**: If both Nginx and Apache are detected, choose which to use
3. **Domain Name**: Enter your domain or use localhost
4. **SSL Certificate**: Choose whether to install Let's Encrypt SSL
5. **Admin Credentials**: Username, email, password, and optional name

### Example Interactive Session

```
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║          KAST-Web Installation Script v1.0            ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════
  System Compatibility Check
═══════════════════════════════════════════════════════

✓ OS: Ubuntu 22.04 LTS (Supported)

Select database type:
  [1] SQLite (default - no additional setup required)
  [2] PostgreSQL (recommended for production)
  [3] MySQL
  [4] MariaDB

Enter choice [1-4] (default: 1): 2

...
```

## Non-Interactive Installation

For automation, CI/CD, or scripted deployments:

### Basic Non-Interactive Install

```bash
sudo ./install.sh \
  --non-interactive \
  --admin-user=admin \
  --admin-email=admin@example.com \
  --admin-pass=SecurePassword123
```

### Production Install with PostgreSQL and SSL

```bash
sudo ./install.sh \
  --non-interactive \
  --database=postgresql \
  --web-server=nginx \
  --ssl \
  --domain=kast.yourdomain.com \
  --admin-user=admin \
  --admin-email=admin@yourdomain.com \
  --admin-pass=VerySecurePassword123 \
  --admin-first-name=Admin \
  --admin-last-name=User
```

### Development Install (SQLite, no SSL)

```bash
sudo ./install.sh \
  --non-interactive \
  --database=sqlite \
  --web-server=nginx \
  --no-ssl \
  --domain=localhost \
  --admin-user=dev \
  --admin-email=dev@localhost \
  --admin-pass=DevPass123
```

## Post-Installation

After successful installation, you'll see a summary report:

```
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║   KAST-Web Installation Completed Successfully!       ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝

Installation Details:
  Installation Directory: /opt/kast-web
  Database Type: postgresql
  Web Server: nginx
  Domain: kast.example.com
  SSL Enabled: yes

Access Information:
  URL: https://kast.example.com
  Admin Username: admin
  Admin Email: admin@example.com

Service Status:
  Redis:        RUNNING
  Celery:       RUNNING
  Gunicorn:     RUNNING
  Nginx:        RUNNING
```

### First Steps

1. **Access the Application**
   - Navigate to the URL shown in the installation report
   - Log in with your admin credentials

2. **Configure Firewall** (if warnings were shown)
   - For UFW: `sudo ufw allow 80/tcp && sudo ufw allow 443/tcp`
   - For firewalld: `sudo firewall-cmd --permanent --add-service=http --add-service=https && sudo firewall-cmd --reload`

3. **Verify Installation**
   ```bash
   sudo ./scripts/validate-install.sh
   ```

4. **Check Service Status**
   ```bash
   sudo systemctl status kast-web kast-celery
   ```

5. **View Logs**
   ```bash
   # Application logs
   sudo journalctl -u kast-web -f
   
   # Celery worker logs
   sudo journalctl -u kast-celery -f
   
   # Web server logs
   sudo tail -f /var/log/nginx/kast-web-access.log
   ```

## Validation

Run the validation script to check your installation:

```bash
sudo ./scripts/validate-install.sh
```

This comprehensive check validates:
- Service status (Redis, Celery, Gunicorn, Web Server)
- Port availability
- File system structure
- Application responsiveness
- Database connectivity
- KAST CLI integration
- Web server configuration
- Systemd service configuration

### Expected Output

```
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║     KAST-Web Installation Validation Report           ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════
  Service Status
═══════════════════════════════════════════════════════

✓ Redis server is running
✓ Redis is responding to ping
✓ Celery worker service is running
✓ KAST-Web (Gunicorn) service is running
✓ Nginx web server is running

...

Results:
  Passed:   28
  Failed:   0
  Warnings: 0
  Total:    28

✓ Installation validation completed successfully!
  All critical checks passed.
```

## Troubleshooting

### Installation Fails at KAST CLI Check

**Problem**: `KAST CLI not found at /usr/local/bin/kast`

**Solution**: 
1. Install KAST CLI first
2. If KAST is installed elsewhere, create a symlink:
   ```bash
   sudo ln -s /path/to/kast /usr/local/bin/kast
   ```

### Service Won't Start

**Problem**: `kast-web service failed to start`

**Solution**:
1. Check service logs:
   ```bash
   sudo journalctl -u kast-web -n 50
   ```
2. Verify configuration:
   ```bash
   cat /opt/kast-web/.env
   ```
3. Test manually:
   ```bash
   cd /opt/kast-web
   source venv/bin/activate
   gunicorn --bind 127.0.0.1:8000 wsgi:app
   ```

### Database Connection Errors

**Problem**: Application can't connect to database

**Solution**:
1. Check DATABASE_URL in `/opt/kast-web/.env`
2. For PostgreSQL:
   ```bash
   sudo -u postgres psql -c "\l" | grep kast_web
   ```
3. For MySQL:
   ```bash
   mysql -u root -e "SHOW DATABASES;" | grep kast_web
   ```

### Port Already in Use

**Problem**: Port 80 or 8000 already in use

**Solution**:
1. Check what's using the port:
   ```bash
   sudo netstat -tlnp | grep :80
   sudo ss -tlnp | grep :8000
   ```
2. Stop conflicting service or change KAST-Web port

### Firewall Blocking Access

**Problem**: Cannot access web interface remotely

**Solution**:
1. Check firewall status:
   ```bash
   sudo ufw status  # For UFW
   sudo firewall-cmd --list-all  # For firewalld
   ```
2. Allow HTTP/HTTPS:
   ```bash
   # UFW
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   
   # firewalld
   sudo firewall-cmd --permanent --add-service=http
   sudo firewall-cmd --permanent --add-service=https
   sudo firewall-cmd --reload
   ```

### SSL Certificate Issues

**Problem**: Certbot fails to obtain certificate

**Solution**:
1. Ensure domain points to your server
2. Port 80 must be accessible from internet
3. Try manual certificate:
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

### Existing Installation Detected

**Problem**: Previous installation found

**Options**:
1. **Backup and Upgrade**: Preserves data and upgrades
2. **Fresh Install**: Removes everything and starts fresh
3. **Abort**: Cancel installation

To manually remove before installing:
```bash
sudo systemctl stop kast-web kast-celery
sudo rm -rf /opt/kast-web
```

## Uninstallation

To remove KAST-Web from your system:

```bash
sudo ./scripts/uninstall.sh
```

The uninstall script will:
1. Offer to create a backup
2. Stop and disable services
3. Remove systemd service files
4. Remove web server configuration
5. Optionally remove application files
6. Optionally remove database
7. Optionally remove system dependencies

### Uninstall Options

During uninstallation, you'll be prompted for:
- Backup creation (recommended)
- Application directory removal
- Log file removal
- Database removal
- System package removal (Redis, etc.)

### Complete Uninstall

To remove everything including backups:

```bash
sudo ./scripts/uninstall.sh
# Answer 'yes' to all prompts

# Remove backups manually
sudo rm -rf /opt/kast-web-*
```

## Advanced Configuration

### Custom Installation Directory

The installer uses `/opt/kast-web` by default. To change this, edit the `INSTALL_DIR` variable in `install.sh` before running.

### Custom Service User

By default, services run as `www-data`. To change this, edit the `SERVICE_USER` variable in `install.sh`.

### Multiple Instances

To run multiple KAST-Web instances:
1. Modify `INSTALL_DIR` in installer
2. Use different ports for Gunicorn
3. Create separate web server configurations
4. Use separate database names

## Support

For issues not covered in this guide:

1. Check the installation log: `/var/log/kast-web-install.log`
2. Run validation script: `sudo ./scripts/validate-install.sh`
3. Review service logs: `sudo journalctl -u kast-web -n 100`
4. Consult project documentation in `/opt/kast-web/docs/`
5. Check GitHub issues or create a new one

## Security Considerations

After installation:

1. **Change Default Password**: Log in and change the admin password immediately
2. **Enable HTTPS**: Use SSL in production environments
3. **Firewall Configuration**: Restrict access to necessary ports only
4. **Regular Updates**: Keep system packages and Python dependencies updated
5. **Backup Strategy**: Implement regular database backups
6. **Monitor Logs**: Regularly review application and access logs

## Performance Tuning

For production deployments:

1. **Gunicorn Workers**: Adjust in `/etc/systemd/system/kast-web.service`
   - Formula: `(2 × CPU cores) + 1`
   
2. **Database Optimization**: 
   - Use PostgreSQL for production
   - Configure connection pooling
   - Regular VACUUM and ANALYZE

3. **Redis Configuration**: Tune Redis settings for your workload

4. **Web Server**: Enable gzip compression and caching

## Upgrade Process

To upgrade an existing installation:

1. Backup your data:
   ```bash
   sudo ./scripts/uninstall.sh  # Choose backup option
   ```

2. Pull latest code:
   ```bash
   cd /opt/kast-web
   git pull
   ```

3. Run installer (choose "Backup and upgrade"):
   ```bash
   sudo ./install.sh
   ```

The installer will preserve your data and configuration while upgrading the application.
