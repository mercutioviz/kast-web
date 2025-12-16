# KAST-Web Update Guide

Complete guide for updating production KAST-Web installations.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Update Types](#update-types)
3. [Before You Update](#before-you-update)
4. [Update Procedures](#update-procedures)
5. [Rollback Procedures](#rollback-procedures)
6. [Version Management](#version-management)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)
9. [Migration Guide](#migration-guide)

---

## Quick Start

### Common Update Scenarios

#### Scenario 1: Minor Updates (CSS, Templates, Code)
```bash
cd /opt/kast-web
sudo ./scripts/update.sh
```
**Downtime:** ~10-15 seconds  
**What happens:** Git pull + service restart

#### Scenario 2: Major Updates (New Features, Dependencies)
```bash
cd /opt/kast-web
sudo ./scripts/update.sh --full
```
**Downtime:** ~30-60 seconds  
**What happens:** Git pull + dependency updates + migrations + service restart

#### Scenario 3: Preview Changes Before Applying
```bash
cd /opt/kast-web
sudo ./scripts/update.sh --dry-run
```
**What happens:** Shows what would be changed without making any modifications

#### Scenario 4: Quick Rollback After Failed Update
```bash
cd /opt/kast-web
sudo ./scripts/rollback.sh
```
**What happens:** Restores from most recent backup

---

## Update Types

### Quick Update (Default)

**Use for:**
- CSS/styling changes
- Template modifications
- Code-only changes
- Bug fixes without dependencies

**Command:**
```bash
sudo ./scripts/update.sh
```

**Process:**
1. Creates backup
2. Pulls latest code from git
3. Restarts services
4. Validates update

**Duration:** ~10-15 seconds downtime

### Full Update

**Use for:**
- New feature additions
- Dependency changes
- Database schema changes
- Major version updates

**Command:**
```bash
sudo ./scripts/update.sh --full
```

**Process:**
1. Creates backup
2. Pulls latest code from git
3. Updates Python dependencies
4. Runs database migrations
5. Restarts services
6. Validates update

**Duration:** ~30-60 seconds downtime

---

## Before You Update

### Pre-Update Checklist

- [ ] Review release notes/changelog
- [ ] Verify current version: `grep "VERSION = " /opt/kast-web/config.py`
- [ ] Check disk space: `df -h /opt` (need at least 1GB free)
- [ ] Backup database manually (optional, script does this automatically)
- [ ] Notify users of upcoming downtime if needed
- [ ] Check for uncommitted changes: `cd /opt/kast-web && git status`
- [ ] Verify services are running: `systemctl status kast-web kast-celery`

### Understanding Version Numbers

KAST-Web uses semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR** (1.x.x): Breaking changes, may require manual intervention
- **MINOR** (x.2.x): New features, backward compatible
- **PATCH** (x.x.3): Bug fixes, backward compatible

**Update Guidelines:**
- Patch updates: Use quick update
- Minor updates: Use full update (recommended)
- Major updates: Review migration guide, use full update, test thoroughly

---

## Update Procedures

### Standard Update Process

#### Step 1: Prepare
```bash
# Navigate to installation directory
cd /opt/kast-web

# Check current status
git status
git fetch origin
```

#### Step 2: Preview (Optional)
```bash
# See what would change
sudo ./scripts/update.sh --dry-run
```

Review the output to understand:
- Which commits will be pulled
- What migrations will run (if --full)
- Which services will restart

#### Step 3: Execute Update
```bash
# Quick update (default)
sudo ./scripts/update.sh

# OR full update for major changes
sudo ./scripts/update.sh --full
```

The script will:
1. Validate environment
2. Check git status
3. Display version information
4. Ask for confirmation
5. Create backup
6. Apply updates
7. Restart services
8. Validate success

#### Step 4: Verify
```bash
# Check services
systemctl status kast-web
systemctl status kast-celery

# View logs
sudo journalctl -u kast-web -n 50
sudo journalctl -u kast-celery -n 50

# Test application
curl -I http://localhost:8000
```

Access the application in a browser and verify functionality.

### Update Options

#### Force Update
Skip safety checks (uncommitted changes, no updates available):
```bash
sudo ./scripts/update.sh --force
```

#### Skip Backup
**NOT RECOMMENDED** - Skip backup creation:
```bash
sudo ./scripts/update.sh --skip-backup
```

#### Disable Auto-Rollback
Prevent automatic rollback on failure:
```bash
sudo ./scripts/update.sh --no-rollback
```

#### Combined Options
```bash
# Full update with dry-run
sudo ./scripts/update.sh --full --dry-run

# Force quick update
sudo ./scripts/update.sh --force
```

### Monitoring During Update

The update script provides real-time feedback:

```
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║          KAST-Web Update Script v1.0                  ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════
  Environment Validation
═══════════════════════════════════════════════════════

✓ Installation directory verified
✓ Virtual environment found
✓ Systemd services verified
✓ Sufficient disk space available: 50GB

═══════════════════════════════════════════════════════
  Git Repository Status
═══════════════════════════════════════════════════════
```

Watch for:
- ✓ Green checkmarks indicate success
- ✗ Red X marks indicate failures
- ⚠ Yellow warnings indicate caution
- ℹ Blue info provides context

---

## Rollback Procedures

### When to Rollback

Consider rollback if:
- Application fails to start after update
- Critical functionality is broken
- Performance severely degraded
- Database errors occur
- Services won't restart

### Quick Rollback

#### Interactive Selection
```bash
cd /opt/kast-web
sudo ./scripts/rollback.sh
```

The script will:
1. List available backups
2. Show backup metadata (version, date, type)
3. Ask you to select a backup
4. Confirm before proceeding
5. Restore all components
6. Validate restoration

**Example Output:**
```
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║         KAST-Web Rollback Script v1.0                 ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝

⚠ This script will rollback KAST-Web to a previous backup

═══════════════════════════════════════════════════════
  Available Backups
═══════════════════════════════════════════════════════

Found 3 backup(s):

  [1] kast-web-backup-20241216-210500
      Date: 2024-12-16 21:05:00
      Version: 1.2.0
      Type: full

  [2] kast-web-backup-20241215-143000
      Date: 2024-12-15 14:30:00
      Version: 1.1.5
      Type: quick

  [3] kast-web-backup-20241214-090000
      Date: 2024-12-14 09:00:00
      Version: 1.1.4
      Type: full

Select a backup to restore:
Enter backup number (1-3), or 'q' to quit:
```

#### Direct Backup Specification
```bash
# Rollback to specific backup
sudo ./scripts/rollback.sh /opt/kast-web-backup-20241216-210500
```

### What Gets Restored

The rollback process restores:
1. **Git State** - Code reverted to backup commit
2. **Database** - Database restored from backup
3. **Configuration** - .env file restored
4. **Uploads** - User-uploaded files restored (logos, etc.)

### Post-Rollback Verification

After rollback:
```bash
# Check version
grep "VERSION = " /opt/kast-web/config.py

# Check services
systemctl status kast-web kast-celery

# View logs
sudo journalctl -u kast-web -f

# Test application
curl http://localhost:8000
```

### Manual Rollback

If automated rollback fails:

```bash
# 1. Stop services
sudo systemctl stop kast-web kast-celery

# 2. Find backup
ls -la /opt/kast-web-backup-*

# 3. Restore git state
cd /opt/kast-web
BACKUP_DIR="/opt/kast-web-backup-20241216-210500"
COMMIT=$(cat $BACKUP_DIR/git-commit.txt)
git reset --hard $COMMIT

# 4. Restore database (SQLite example)
source $BACKUP_DIR/.env
DB_PATH="${DATABASE_URL#sqlite:///}"
cp $BACKUP_DIR/$(basename $DB_PATH) $DB_PATH
chown www-data:www-data $DB_PATH

# 5. Restore configuration
cp $BACKUP_DIR/.env /opt/kast-web/.env
chmod 600 /opt/kast-web/.env

# 6. Restart services
sudo systemctl start kast-celery
sleep 2
sudo systemctl start kast-web
```

---

## Version Management

### Checking Current Version

```bash
# Via config file
grep "VERSION = " /opt/kast-web/config.py

# Via git
cd /opt/kast-web
git log -1 --oneline

# Via admin panel (when logged in as admin)
# Navigate to: Admin Panel > System Info
```

### Version History

Update logs are stored in:
```
/var/log/kast-web/update.log
/var/log/kast-web/rollback.log
```

View recent updates:
```bash
sudo tail -100 /var/log/kast-web/update.log
```

### Backup Management

Backups are stored in `/opt/kast-web-backup-YYYYMMDD-HHMMSS/`

The update script automatically:
- Creates backups before each update
- Keeps the last 5 backups
- Removes older backups automatically

**Manual backup cleanup:**
```bash
# List backups
ls -lh /opt/kast-web-backup-*

# Remove specific backup
sudo rm -rf /opt/kast-web-backup-20241201-100000

# Remove all backups older than 30 days
find /opt/kast-web-backup-* -maxdepth 0 -mtime +30 -exec rm -rf {} \;
```

**Backup contents:**
```
/opt/kast-web-backup-YYYYMMDD-HHMMSS/
├── backup-info.txt        # Metadata (version, date, type)
├── git-commit.txt         # Git commit hash
├── .env                   # Configuration
├── kast.db                # Database (SQLite)
└── uploads/               # Uploaded files
    └── logos/
```

---

## Troubleshooting

### Common Issues

#### 1. Update Script Won't Run

**Error:** "This script must be run as root or with sudo"

**Solution:**
```bash
sudo ./scripts/update.sh
```

---

#### 2. Uncommitted Changes Warning

**Error:** "Uncommitted changes detected"

**Cause:** Local modifications to tracked files

**Solutions:**

Option A - Commit changes:
```bash
git add .
git commit -m "Local changes before update"
sudo ./scripts/update.sh
```

Option B - Stash changes:
```bash
git stash
sudo ./scripts/update.sh
git stash pop  # After update
```

Option C - Force update:
```bash
sudo ./scripts/update.sh --force
```

---

#### 3. Git Pull Fails

**Error:** "Git pull failed"

**Diagnosis:**
```bash
cd /opt/kast-web
git status
git pull origin main  # Or your branch name
```

**Common causes:**
- Merge conflicts
- Network issues
- Invalid git configuration

**Solutions:**

For merge conflicts:
```bash
# Reset to remote state
git fetch origin
git reset --hard origin/main

# Then update
sudo ./scripts/update.sh
```

For network issues:
```bash
# Test connection
git fetch origin --dry-run

# Check remote
git remote -v
```

---

#### 4. Services Won't Start After Update

**Error:** "kast-web service failed to start"

**Diagnosis:**
```bash
# Check service status
sudo systemctl status kast-web
sudo systemctl status kast-celery

# View detailed logs
sudo journalctl -u kast-web -n 100
sudo journalctl -u kast-celery -n 100
```

**Common causes:**
- Database migration errors
- Missing dependencies
- Configuration issues
- Port conflicts

**Solutions:**

Check for errors in logs, then:

For dependency issues:
```bash
cd /opt/kast-web
source venv/bin/activate
pip install -r requirements-production.txt
sudo systemctl restart kast-web
```

For database issues:
```bash
# Check database
cd /opt/kast-web
source venv/bin/activate
python3 -c "from app import db, create_app; app = create_app(); app.app_context().push(); db.create_all()"
```

For configuration issues:
```bash
# Verify .env file
cat /opt/kast-web/.env
# Check for missing or invalid settings
```

If problems persist, rollback:
```bash
sudo ./scripts/rollback.sh
```

---

#### 5. Application Responding But Broken

**Symptoms:** Site loads but features don't work

**Diagnosis:**
1. Check browser console for JavaScript errors
2. Check application logs
3. Test specific features

**Solutions:**

Clear browser cache:
```bash
# Hard refresh in browser: Ctrl+Shift+R (Linux/Windows) or Cmd+Shift+R (Mac)
```

Check for database migration issues:
```bash
cd /opt/kast-web
source venv/bin/activate
set -a
source .env
set +a
python3 utils/migrate_db.py  # Or specific migration script
```

Verify static files:
```bash
ls -la /opt/kast-web/app/static/
# Ensure proper permissions
sudo chown -R www-data:www-data /opt/kast-web/app/static/
```

---

#### 6. Celery Worker Issues

**Error:** "kast-celery service failed to start"

**Diagnosis:**
```bash
sudo systemctl status kast-celery
sudo journalctl -u kast-celery -n 50
```

**Common causes:**
- Redis not running
- Import errors
- Permission issues

**Solutions:**

Check Redis:
```bash
sudo systemctl status redis-server
sudo systemctl restart redis-server
```

Test Celery manually:
```bash
cd /opt/kast-web
source venv/bin/activate
celery -A celery_worker.celery worker --loglevel=info
# Press Ctrl+C to stop, then restart service
sudo systemctl restart kast-celery
```

---

#### 7. Insufficient Disk Space

**Error:** "Insufficient disk space"

**Check:**
```bash
df -h /opt
```

**Solutions:**

Clean old backups:
```bash
# Remove backups older than 30 days
sudo find /opt/kast-web-backup-* -maxdepth 0 -mtime +30 -exec rm -rf {} \;
```

Clean old scan results:
```bash
# Check results directory size
du -sh /var/lib/kast-web/results/*

# Remove old results (adjust date as needed)
sudo find /var/lib/kast-web/results/ -maxdepth 1 -mtime +60 -type d -exec rm -rf {} \;
```

Clean system:
```bash
sudo apt clean
sudo apt autoremove
sudo journalctl --vacuum-time=7d
```

---

#### 8. Database Errors After Update

**Symptoms:** 
- "No such table" errors
- "Column not found" errors
- Application won't load

**Cause:** Missing or failed database migrations

**Solutions:**

Run migrations manually:
```bash
cd /opt/kast-web
source venv/bin/activate
set -a
source .env
set +a

# Run all migrations
for migration in utils/migrate*.py; do
    echo "Running $migration..."
    python3 "$migration"
done
```

If problems persist, restore database from backup:
```bash
# Find recent backup
ls -la /opt/kast-web-backup-*

# Restore database (SQLite example)
BACKUP_DIR="/opt/kast-web-backup-20241216-210500"
source $BACKUP_DIR/.env
DB_PATH="${DATABASE_URL#sqlite:///}"
sudo systemctl stop kast-web kast-celery
cp $BACKUP_DIR/$(basename $DB_PATH) $DB_PATH
sudo systemctl start kast-celery kast-web
```

---

#### 9. Permission Errors

**Error:** Permission denied errors in logs

**Solutions:**

Fix ownership:
```bash
sudo chown -R www-data:www-data /opt/kast-web
sudo chown -R www-data:www-data /var/lib/kast-web
sudo chown www-data:www-data /var/lib/kast-web/kast.db
```

Fix permissions:
```bash
sudo chmod 755 /opt/kast-web
sudo chmod 664 /var/lib/kast-web/kast.db
sudo chmod 600 /opt/kast-web/.env
```

---

### Getting Help

If you encounter issues not covered here:

1. **Check logs:**
   ```bash
   sudo journalctl -u kast-web -f
   sudo journalctl -u kast-celery -f
   tail -f /var/log/kast-web/update.log
   ```

2. **Gather information:**
   - Current version: `grep "VERSION = " /opt/kast-web/config.py`
   - Git status: `cd /opt/kast-web && git status`
   - Service status: `systemctl status kast-web kast-celery`
   - Recent errors from logs

3. **Try rollback:**
   ```bash
   sudo ./scripts/rollback.sh
   ```

4. **Contact support** with:
   - Version information
   - Error messages
   - What you were trying to do
   - What happened instead

---

## Best Practices

### Update Frequency

**Recommended schedule:**
- **Security patches:** Apply immediately
- **Bug fixes:** Within 1 week
- **New features:** Monthly or as needed
- **Major versions:** Plan and test thoroughly

### Pre-Production Testing

For critical environments:

1. **Maintain a staging server**
   - Clone production environment
   - Test updates here first
   - Verify all functionality

2. **Review changes**
   ```bash
   cd /opt/kast-web
   git fetch origin
   git log HEAD..origin/main --oneline
   git diff HEAD..origin/main
   ```

3. **Test migrations**
   ```bash
   # On staging: run full update
   sudo ./scripts/update.sh --full
   
   # Verify database schema
   # Test all features
   # Check logs for errors
   ```

### Scheduled Maintenance Windows

For production systems:

1. **Plan maintenance windows**
   - Schedule during low-traffic periods
   - Notify users in advance
   - Document maintenance window in calendar

2. **Announce downtime**
   ```bash
   # Enable maintenance mode before update
   cd /opt/kast-web
   source venv/bin/activate
   python3 << EOF
from app import create_app, db
from app.models import SystemSettings
app = create_app()
with app.app_context():
    SystemSettings.set_setting('maintenance_mode', 'true', 'bool', 1)
EOF
   ```

3. **Perform update**
   ```bash
   sudo ./scripts/update.sh --full
   ```

4. **Disable maintenance mode**
   ```bash
   cd /opt/kast-web
   source venv/bin/activate
   python3 << EOF
from app import create_app, db
from app.models import SystemSettings
app = create_app()
with app.app_context():
    SystemSettings.set_setting('maintenance_mode', 'false', 'bool', 1)
EOF
   ```

### Change Management

**Document updates:**
1. Record what was updated
2. Note any issues encountered
3. Document resolution steps
4. Track downtime duration

**Example log entry:**
```
Date: 2024-12-16
Update Type: Full
Version: 1.1.5 -> 1.2.0
Downtime: 45 seconds
Issues: None
Notes: Added email notification feature
```

### Communication

**Before update:**
- Notify users of scheduled maintenance
- Provide expected downtime duration
- Share emergency contact information

**After update:**
- Announce completion
- Highlight new features
- Provide feedback channel

---

## Migration Guide

### Database Migrations

KAST-Web uses Python migration scripts in the `utils/` directory.

**Migration script naming convention:**
```
migrate_<feature_name>.py
```

**How migrations work:**
1. Update script detects migration files
2. Runs them in alphabetical order
3. Logs success/failure
4. Continues even if one fails (with warning)

**Available migrations:**
- `migrate_db.py` - Base schema
- `migrate_phase3.py` - Admin panel features
- `migrate_phase4.py` - Scan sharing
- `migrate_email_feature.py` - Email system
- `migrate_logo_feature.py` - Logo white-labeling
- `migrate_power_user.py` - Power user role
- `migrate_plugin_logging.py` - Enhanced logging
- `migrate_import_feature.py` - CLI import

**Manual migration:**
```bash
cd /opt/kast-web
source venv/bin/activate
set -a
source .env
set +a

# Run specific migration
python3 utils/migrate_<feature_name>.py

# Or run all migrations
for migration in utils/migrate*.py; do
    echo "Running $migration..."
    python3 "$migration"
done
```

### Version-Specific Migrations

#### Upgrading to v1.2.0 from v1.1.x
- **Database changes:** Email system tables
- **New dependencies:** `email-validator`
- **Configuration:** SMTP settings in SystemSettings
- **Migration:** `utils/migrate_email_feature.py`

**Update command:**
```bash
sudo ./scripts/update.sh --full
```

#### Upgrading to v1.1.0 from v1.0.x
- **Database changes:** ScanShare, ReportLogo tables
- **New features:** Scan sharing, logo white-labeling
- **Migrations:** Multiple migration scripts

**Update command:**
```bash
sudo ./scripts/update.sh --full
```

### Configuration Changes

Some updates may require configuration changes:

**Check for new environment variables:**
```bash
# Compare current .env with example
diff /opt/kast-web/.env /opt/kast-web/.env.example
```

**Add missing variables:**
```bash
# Edit .env file
sudo nano /opt/kast-web/.env

# Restart services
sudo systemctl restart kast-web kast-celery
```

### Breaking Changes

**Major version updates (1.x.x -> 2.x.x) may include:**
- Database schema incompatibilities
- API changes
- Configuration format changes
- Dependency conflicts

**Always:**
1. Read release notes thoroughly
2. Test on staging environment
3. Backup before upgrading
4. Plan rollback strategy

---

## Appendix

### Update Script Options Reference

```
Usage: sudo ./scripts/update.sh [options]

Update Modes:
  (default)          Quick update - pull code and restart services
  --full             Full update - includes dependencies and migrations

Options:
  --dry-run          Show what would be done without making changes
  --force            Skip safety checks and force update
  --skip-backup      Skip backup creation (NOT RECOMMENDED)
  --no-rollback      Disable automatic rollback on failure
  --help, -h         Show help message
```

### Rollback Script Options Reference

```
Usage: sudo ./scripts/rollback.sh [backup-directory]

Arguments:
  backup-directory   Optional path to specific backup to restore

Interactive Mode:
  If no directory specified, script will list available backups
  and prompt for selection
```

### File Locations Reference

```
Installation:
  /opt/kast-web/                    Main installation directory
  /opt/kast-web/venv/               Python virtual environment
  /opt/kast-web/.env                Configuration file
  /opt/kast-web/config.py           Application configuration
  /opt/kast-web/scripts/            Update/rollback scripts
  /opt/kast-web/utils/              Migration scripts

Data:
  /var/lib/kast-web/                Data directory
  /var/lib/kast-web/kast.db         SQLite database
  /var/lib/kast-web/results/        Scan results

Logs:
  /var/log/kast-web/update.log      Update operation logs
  /var/log/kast-web/rollback.log    Rollback operation logs
  
System Logs (via journalctl):
  kast-web service logs
  kast-celery service logs

Backups:
  /opt/kast-web-backup-*/           Timestamped backup directories

Services:
  /etc/systemd/system/kast-web.service
  /etc/systemd/system/kast-celery.service
```

### Version History Example

Track updates in a log file:

```bash
# Create update log
cat >> /var/log/kast-web/version-history.txt << EOF
$(date): Updated to $(grep "VERSION = " /opt/kast-web/config.py | cut -d"'" -f2)
EOF

# View history
cat /var/log/kast-web/version-history.txt
```

### Quick Reference Card

**Daily Operations:**
```bash
# Check version
grep "VERSION = " /opt/kast-web/config.py

# Check services
systemctl status kast-web kast-celery

# View logs
sudo journalctl -u kast-web -f
```

**Quick Update:**
```bash
cd /opt/kast-web
sudo ./scripts/update.sh
```

**Full Update:**
```bash
cd /opt/kast-web
sudo ./scripts/update.sh --full
```

**Rollback:**
```bash
cd /opt/kast-web
sudo ./scripts/rollback.sh
```

**Emergency Procedures:**
```bash
# Stop services
sudo systemctl stop kast-web kast-celery

# Start services
sudo systemctl start kast-celery kast-web

# Restart services
sudo systemctl restart kast-celery kast-web

# View recent errors
sudo journalctl -u kast-web -n 100 -p err
```

---

## Summary

This guide provides comprehensive information for updating KAST-Web in production:

✓ **Two update modes:** Quick for minor changes, Full for major updates  
✓ **Automatic backups:** Created before every update  
✓ **Easy rollback:** Quick restore from backups  
✓ **Validation:** Post-update checks ensure success  
✓ **Detailed logging:** Track all operations  
✓ **Safety features:** Dry-run mode, automatic rollback on failure  

**Remember:**
- Always review changes before updating
- Use `--dry-run` to preview updates
- Backups are created automatically
- Rollback is quick and easy
- Test critical updates on staging first

For additional help, consult:
- `README.md` - Project overview
- `genai-instructions.md` - Development guidelines
- `docs/PRODUCTION_DEPLOYMENT.md` - Deployment guide
- Feature-specific documentation in `docs/`
