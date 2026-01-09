# Install Script .env Preservation Feature

## Overview

The KAST-Web install script has been enhanced to preserve the `.env` file during upgrades, preventing SECRET_KEY loss and the resulting encryption errors.

## Problem This Solves

**Before Enhancement:**
- Running the installer would always generate a new SECRET_KEY
- ZAP configurations stored with the old key couldn't be decrypted
- Users would get "Internal Server Error" when accessing encrypted data
- Manual backup and restore was required

**After Enhancement:**
- The installer automatically preserves SECRET_KEY during upgrades
- No encryption errors after reinstallation
- ZAP configurations remain accessible
- All other settings are also preserved

## How It Works

### Fresh Installation
When no existing installation is detected:
1. Generates a new random SECRET_KEY
2. Creates a new .env file with default settings
3. No preservation needed

### Upgrade Installation
When an existing installation is detected and you choose to upgrade:

1. **Backup Detection:**
   - Looks for the most recent backup directory created during upgrade
   - Backup directory format: `/opt/kast-web-backup-YYYYMMDD-HHMMSS`

2. **Settings Extraction:**
   - Reads the backed-up `.env` file
   - Extracts all existing settings:
     - `SECRET_KEY` (critical for encryption)
     - `DATABASE_URL`
     - `CELERY_BROKER_URL`
     - `CELERY_RESULT_BACKEND`
     - `KAST_CLI_PATH`
     - `KAST_RESULTS_DIR`

3. **Settings Preservation:**
   - Uses existing SECRET_KEY if found (prevents decryption errors)
   - Preserves other settings if they exist
   - Falls back to defaults only if settings are missing
   - Generates new SECRET_KEY only if none was found in backup

4. **New .env Creation:**
   - Creates new .env file with preserved settings
   - Adds timestamp comment noting it's an upgrade
   - Sets proper permissions (600) and ownership (www-data)

## File Locations

- **Installation Directory:** `/opt/kast-web`
- **Configuration File:** `/opt/kast-web/.env`
- **Backup Location:** `/opt/kast-web-backup-YYYYMMDD-HHMMSS/.env`

## Critical Settings Preserved

### 1. SECRET_KEY (Most Important)
```bash
# Used for:
# - Flask session encryption
# - ZAP configuration encryption (API keys, credentials)
# - Cookie signing
# - CSRF tokens
```

**Impact if changed:**
- ZAP configurations become inaccessible
- Users logged out (session invalidation)
- Encrypted database fields unreadable
- System settings with encrypted values fail

### 2. DATABASE_URL
```bash
# Database connection string
# Format depends on database type:
# - sqlite:////var/lib/kast-web/kast.db
# - postgresql://user:pass@localhost/dbname
# - mysql+pymysql://user:pass@localhost/dbname
```

### 3. Celery Settings
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 4. KAST Configuration
```bash
KAST_CLI_PATH=/usr/local/bin/kast
KAST_RESULTS_DIR=/var/lib/kast-web/results
```

## Usage

### Normal Upgrade (Automatic Preservation)
```bash
sudo ./install.sh
# When prompted, choose:
# [1] Backup and upgrade existing installation
```

The installer will:
1. Create a backup with timestamp
2. Copy `.env` to backup directory
3. Install new version
4. Restore `.env` settings automatically

### Manual Verification
After upgrade, verify settings were preserved:
```bash
# Check if SECRET_KEY was preserved
sudo grep "SECRET_KEY" /opt/kast-web/.env

# Check backup location
ls -la /opt/kast-web-backup-*/

# Verify the backup contains your old .env
cat /opt/kast-web-backup-*/​.env
```

### Testing ZAP Configs After Upgrade
```bash
# Restart services
sudo systemctl restart kast-web kast-celery

# Check for encryption errors in logs
sudo journalctl -u kast-web -n 50

# Access ZAP config page
# http://your-domain/admin/zap/configs
# Should load without "Internal Server Error"
```

## Troubleshooting

### Issue: ZAP Configs Still Showing Errors After Upgrade

**Cause:** Backup didn't contain the original SECRET_KEY

**Solution:**
1. Check if you have the old SECRET_KEY saved elsewhere
2. Manually update `.env` with old SECRET_KEY:
   ```bash
   sudo nano /opt/kast-web/.env
   # Replace SECRET_KEY with your old value
   ```
3. Restart services:
   ```bash
   sudo systemctl restart kast-web kast-celery
   ```

### Issue: No Backup Found During Upgrade

**Cause:** Backup creation failed or directory was deleted

**Solution:**
1. If you have a manual backup of `.env`, restore it:
   ```bash
   sudo cp /path/to/backup/.env /opt/kast-web/.env
   sudo chown www-data:www-data /opt/kast-web/.env
   sudo chmod 600 /opt/kast-web/.env
   ```
2. Restart services

### Issue: Want to Force New SECRET_KEY

**Scenario:** Security requirement to rotate keys

**Steps:**
1. Export existing encrypted data (if needed)
2. Delete old backups:
   ```bash
   sudo rm -rf /opt/kast-web-backup-*
   ```
3. Run installer - will generate new SECRET_KEY
4. Re-create ZAP configurations with new credentials
5. Import data using new encryption

## Security Considerations

### SECRET_KEY Security
- The SECRET_KEY should be kept secret and secure
- File permissions are 600 (owner read/write only)
- Owner is www-data (service account)
- Never commit .env to version control
- Rotate keys periodically in high-security environments

### Backup Security
- Backups contain sensitive information
- Located in `/opt/kast-web-backup-*` directories
- Should be secured with proper permissions
- Consider encrypting backups for long-term storage
- Clean up old backups periodically:
  ```bash
  # Keep only last 5 backups
  ls -t /opt/kast-web-backup-* | tail -n +6 | xargs sudo rm -rf
  ```

## Best Practices

### Before Reinstalling
1. **Manual backup (recommended):**
   ```bash
   sudo cp /opt/kast-web/.env ~/kast-env-backup-$(date +%Y%m%d).txt
   ```

2. **Document your SECRET_KEY** (secure location):
   ```bash
   sudo grep SECRET_KEY /opt/kast-web/.env > ~/secret-key-backup.txt
   chmod 600 ~/secret-key-backup.txt
   ```

### After Reinstalling
1. **Verify preservation:**
   ```bash
   # Compare old and new SECRET_KEY
   cat ~/secret-key-backup.txt
   sudo grep SECRET_KEY /opt/kast-web/.env
   ```

2. **Test critical functionality:**
   - Log in to admin panel
   - Access ZAP configurations
   - View system settings
   - Test scan creation

### Regular Maintenance
1. **Keep backups organized:**
   ```bash
   # List all backups with dates
   ls -lh /opt/kast-web-backup-*
   ```

2. **Clean old backups:**
   ```bash
   # Delete backups older than 30 days
   find /opt/kast-web-backup-* -mtime +30 -exec sudo rm -rf {} \;
   ```

## Implementation Details

### Code Location
File: `install.sh`
Function: `setup_application()`
Lines: ~680-780 (approximate)

### Logic Flow
```
Is this an upgrade?
├─ No (Fresh Install)
│  ├─ Generate new SECRET_KEY
│  └─ Create new .env with defaults
│
└─ Yes (Upgrade)
   ├─ Find latest backup directory
   ├─ Check if backup/.env exists
   ├─ Yes: Extract settings
   │  ├─ Read SECRET_KEY (if present)
   │  ├─ Read DATABASE_URL (if present)
   │  ├─ Read other settings
   │  └─ Create .env with preserved values
   │
   └─ No: Generate new settings
      ├─ Generate new SECRET_KEY
      └─ Create .env with defaults
```

### Validation Checks
The installer performs these checks:
1. Backup directory exists
2. Backup contains .env file
3. .env file is readable
4. SECRET_KEY value is non-empty
5. Extracted settings are valid

## Related Documentation

- **Main Installation Guide:** `docs/INSTALL.md`
- **Update Guide:** `docs/UPDATE_GUIDE.md`
- **Encryption Utilities:** `app/encryption.py`
- **ZAP Configuration:** `docs/ZAP_INTEGRATION_PHASE2.md`
- **Database Models:** `app/models.py` (ZapConfiguration class)

## Version History

- **v1.1** (2026-01-09): Added .env preservation during upgrades
- **v1.0** (2025-12-XX): Initial installer with basic .env creation

## Support

If you encounter issues with .env preservation:

1. Check installer logs: `/var/log/kast-web-install.log`
2. Verify backup was created: `ls -la /opt/kast-web-backup-*`
3. Check backup contains .env: `ls -la /opt/kast-web-backup-*/.env`
4. Review this documentation for troubleshooting steps
5. Report issues with relevant log excerpts