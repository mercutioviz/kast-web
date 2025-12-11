# System Information Feature

## Overview

The System Information feature provides administrators with a comprehensive view of the system's configuration, status, and environment - similar to PHP's `phpinfo()` function but tailored for the KAST-Web application.

## Access

**URL:** `/admin/system-info`

**Requirements:**
- Must be logged in
- Must have admin role
- Access is logged in the audit log

## Navigation

1. Log in as an administrator
2. Go to Admin Dashboard
3. Click the "System Info" button in the top navigation
4. Or navigate directly to `/admin/system-info`

## Information Displayed

### 1. Service Status Overview (Top of Page)
Real-time status indicators for:
- **Redis Server** - Message broker status
- **kast-web** - Main application service
- **kast-celery** - Background worker service
- **nginx/apache2** - Web server status
- **Redis Connection** - Actual connection test
- **Database Connection** - Database connectivity test

Status badges: 🟢 Running | 🔴 Stopped | ⚪ Unknown

### 2. Python Environment (Expandable Section)
- Python version and executable path
- Python prefix (virtual environment location)
- sys.path entries (module search paths)
- Complete list of installed packages with versions

**Use Cases:**
- Verify correct Python version
- Check if required packages are installed
- Identify package version conflicts
- Confirm virtual environment is active

### 3. System Information
- Operating system and platform details
- System architecture (x86_64, ARM, etc.)
- Hostname
- CPU count and current usage percentage
- Memory statistics (total, used, available, percentage)

**Use Cases:**
- Check system resources
- Identify performance bottlenecks
- Verify deployment environment

### 4. Environment Variables
- **PATH** - Formatted list of binary search paths
- **PYTHONPATH** - Python module search paths
- **Flask/Celery/KAST variables** - Application-specific variables
- **Sensitive values are masked** (passwords, secret keys, tokens)

**Use Cases:**
- Verify KAST CLI is in PATH
- Check application configuration
- Troubleshoot import issues
- Validate environment setup

### 5. Flask Configuration
Complete Flask application configuration with:
- Boolean values shown as colored badges
- Sensitive values masked (SECRET_KEY, DATABASE_URL, etc.)
- All configuration keys sorted alphabetically

**Use Cases:**
- Verify configuration settings
- Check if debug mode is disabled in production
- Validate database connection string
- Review security settings

### 6. File Paths & Permissions
Table showing critical directories:
- **Installation** - `/opt/kast-web`
- **Logs** - `/var/log/kast-web`
- **Results** - `/var/lib/kast-web/results`
- **Uploads** - `/opt/kast-web/app/static/uploads`

For each path:
- ✅ Exists indicator
- ✅ Writable indicator  
- File permissions (octal notation)

**Use Cases:**
- Diagnose permission issues
- Verify directory structure
- Check file ownership problems
- Validate write access for scans

### 7. Disk Usage
Visual progress bars showing disk space for:
- `/` (root filesystem)
- `/opt` (application installation)
- `/var` (logs and data)
- `/tmp` (temporary files)

Color coding:
- 🟢 Green: < 75% used
- 🟡 Yellow: 75-90% used
- 🔴 Red: > 90% used

**Use Cases:**
- Monitor disk space
- Prevent out-of-space errors
- Plan storage upgrades
- Identify space-consuming directories

### 8. Database Information
- Database type (SQLite, PostgreSQL, MySQL/MariaDB)
- File path (SQLite) or connection URL (masked for security)
- Connection test status

**Use Cases:**
- Verify database configuration
- Check connection issues
- Validate database path
- Confirm database type

### 9. KAST CLI Information
- Installation path
- Version information
- Plugin count
- Executable status

**Use Cases:**
- Verify KAST CLI is installed
- Check KAST version
- Confirm plugin availability
- Troubleshoot scan failures

## Security Features

### Data Masking
Sensitive information is automatically masked:
- SECRET_KEY
- Database passwords
- API tokens
- SMTP passwords
- Any variable containing: PASSWORD, PASS, TOKEN, KEY

Example: `mysecretkey123` → `***tkey123` (shows last 4 characters)

### Audit Logging
Every access to the system information page is logged with:
- Timestamp
- Username
- Action: `system_info_viewed`
- IP address (if available)

### Access Control
- Requires admin role (@admin_required decorator)
- Requires authentication (@login_required decorator)
- Unauthorized access redirected with error message

## Troubleshooting Use Cases

### Scenario 1: Scans Not Running
Check:
1. Service Status → Is kast-celery running?
2. Redis Connection → Is Redis accessible?
3. KAST CLI Info → Is KAST installed and working?
4. File Paths → Does results directory have write permissions?

### Scenario 2: Application Crashes
Check:
1. System Info → Memory usage high?
2. Disk Usage → Out of disk space?
3. Python Environment → All packages installed?
4. Service Status → Are services running?

### Scenario 3: Database Errors
Check:
1. Database Connection → Can connect?
2. Database Info → Correct type and path?
3. File Paths → Database file writable (SQLite)?
4. Flask Config → DATABASE_URL correct?

### Scenario 4: Configuration Issues
Check:
1. Environment Variables → Variables set correctly?
2. Flask Configuration → Settings match requirements?
3. File Paths → All directories exist and writable?
4. Python Environment → In correct virtual environment?

## Export Functionality

Currently, the page is view-only. Future enhancement planned:
- Export system info as JSON
- Download diagnostic report
- Email system info to support
- Generate support ticket with system info attached

## Best Practices

1. **Regular Checks**: Review system info periodically (weekly recommended)
2. **After Changes**: Check after configuration changes or updates
3. **Before Support**: Gather system info before requesting help
4. **Performance Issues**: Review when experiencing slowness
5. **Post-Deployment**: Validate environment after deployment

## Integration with Other Features

The system info page complements:
- **Admin Dashboard** - High-level overview
- **Database Explorer** - Database content inspection
- **Audit Log** - Security and activity monitoring
- **Settings Page** - Configuration management

## Notes

- Page loads may take 2-3 seconds to collect all information
- Service checks use systemctl (requires systemd)
- Some info requires psutil package (installed by default)
- Disk usage calculated at page load time
- Connection tests have 2-5 second timeouts

## Future Enhancements

Planned improvements:
- JSON/CSV export functionality
- Historical tracking of key metrics
- Alerting when issues detected
- Integration with monitoring tools
- Real-time updates via WebSocket
- Comparison with previous states
- Health check API endpoint

---

**Related Documentation:**
- [Admin Panel Phase 3](ADMIN_PANEL_PHASE3.md)
- [Production Deployment](PRODUCTION_DEPLOYMENT.md)
- [Quick Reference](QUICK_REFERENCE.md)
