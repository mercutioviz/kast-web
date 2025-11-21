# User Migration Guide

This guide explains how to migrate users from one kast-web server to another without migrating scans.

## Overview

The user migration process uses two scripts:
- `export_users.py` - Exports users from the current server to a JSON file
- `import_users.py` - Imports users from the JSON file to a new server

## Features

- Exports all user data including password hashes (users keep their passwords)
- Preserves user roles (admin, user, viewer)
- Maintains user metadata (creation date, login count, etc.)
- Excludes scans and scan-related data
- Options to skip or update existing users during import

## Prerequisites

Both the source and destination servers must have:
- Python 3.x installed
- kast-web application installed
- Python dependencies installed (Flask, SQLAlchemy, etc.)
- Virtual environment activated (if using one)

**On the destination server, ensure dependencies are installed:**

```bash
cd /opt/kast-web
# If using a virtual environment, activate it first:
source venv/bin/activate  # or your venv path

# Install dependencies if not already installed:
pip install -r requirements.txt
```

## Migration Process

### Step 1: Export Users from Current Server

On the **current/source server**, run:

```bash
cd /opt/kast-web
python export_users.py
```

This creates a file called `users_export.json` containing all users.

**Optional: Specify custom output file:**
```bash
python export_users.py /path/to/custom_export.json
```

### Step 2: Transfer Export File

Copy the export file to the new server:

```bash
scp users_export.json user@new-server:/opt/kast-web/
```

Or use any other file transfer method (rsync, sftp, etc.)

### Step 3: Import Users on New Server

On the **new/destination server**:

1. **Activate the virtual environment** (if using one):
   ```bash
   cd /opt/kast-web
   source venv/bin/activate  # or your venv path
   ```

2. **Run the import script**:
   ```bash
   python import_users.py
   ```

**Options:**

1. **Skip existing users** (default):
   ```bash
   python import_users.py
   # or explicitly:
   python import_users.py --skip-existing
   ```

2. **Update existing users** with exported data:
   ```bash
   python import_users.py --update-existing
   ```

3. **Specify custom input file:**
   ```bash
   python import_users.py /path/to/custom_export.json
   ```

## What Gets Migrated

### User Data Included:
- Username
- Email address
- Password hash (users can log in with their existing passwords)
- First and last name
- Role (admin, user, viewer)
- Active status
- Account creation date
- Last login date
- Login count
- Failed login attempts

### Data NOT Migrated:
- Scans
- Scan results
- Audit logs
- Scan shares
- System settings

## Example Usage

### Complete Migration Example

**On source server:**
```bash
cd /opt/kast-web
python export_users.py users_backup_2025.json
# Output: Successfully exported 15 users to users_backup_2025.json
```

**Transfer file:**
```bash
scp users_backup_2025.json admin@new-server:/opt/kast-web/
```

**On destination server:**
```bash
cd /opt/kast-web
python import_users.py users_backup_2025.json
# Output: Import Summary:
#   Users imported: 15
#   ✓ Import completed successfully!
```

## Handling Conflicts

When importing to a server that already has users:

### Skip Existing (Default)
```bash
python import_users.py --skip-existing
```
- Imports only new users
- Leaves existing users unchanged
- Prevents accidental overwrites

### Update Existing
```bash
python import_users.py --update-existing
```
- Imports new users
- Updates existing users with exported data
- Useful for syncing changes

## Verification

After import, verify the migration:

```bash
# List all users in the database
python -c "
from app import create_app, db
from app.models import User
app = create_app()
with app.app_context():
    users = User.query.all()
    print(f'Total users: {len(users)}')
    for u in users:
        print(f'  - {u.username} ({u.email}) - {u.role}')
"
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'flask'"
- The Python dependencies are not installed
- Activate the virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

### "No users found in database"
- The source database is empty
- Check the database path in config.py

### "File not found" error
- Verify the export file path
- Ensure the file was transferred correctly

### "Invalid JSON" error
- The export file is corrupted
- Re-export from the source server

### Duplicate username/email errors
- Use `--skip-existing` to avoid conflicts
- Or use `--update-existing` to overwrite existing users

## Security Notes

1. **Password Hashes**: The export includes password hashes, which allows users to keep their passwords. Handle the export file securely.

2. **File Permissions**: Set appropriate permissions on export files:
   ```bash
   chmod 600 users_export.json
   ```

3. **Secure Transfer**: Use secure methods (scp, sftp) to transfer export files between servers.

4. **Clean Up**: Delete export files after successful import:
   ```bash
   rm users_export.json
   ```

## Related Documentation

- [Authentication Setup](AUTHENTICATION_SETUP.md) - User authentication system
- [Authorization](AUTHORIZATION_PHASE2.md) - User roles and permissions
- [Admin Panel](ADMIN_PANEL_PHASE3.md) - Managing users through the web interface

## Additional Notes

- The migration scripts work with SQLite databases (default)
- For other database types, ensure proper database configuration
- The new server must have the same or compatible database schema
- No downtime required on either server during migration
- Users can continue using the old server during the process
