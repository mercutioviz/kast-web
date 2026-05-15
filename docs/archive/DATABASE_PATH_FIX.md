# Database Path Fix - December 24, 2025

## Issue

After implementing the configuration profiles feature, Flask was throwing an error:
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such column: scans.config_profile_id
```

## Root Cause

The issue was caused by **TWO problems**:

1. **Relative database path in config.py** (initially):
```python
SQLALCHEMY_DATABASE_URI = 'sqlite:///kast.db'  # Relative path!
```

2. **Environment variable override in .env file** (main issue):
```bash
DATABASE_URL=sqlite:////home/kali/kast-web/db/kast.db  # Wrong path!
```

Even after fixing `config.py` to use an absolute path, the `.env` file was overriding it with a completely different database path. The `run.py` script loads `.env` via `load_dotenv()` BEFORE creating the app, so the environment variable takes precedence over the config.py default.

## Files Found

Before the fix, we had **4 database files**:
1. `/opt/kast-web/kast.db` (160K) - Flask was using this
2. `/opt/kast-web/kast-web.db` (0 bytes) - Empty file from migration attempt
3. `/opt/kast-web/instance/kast.db` (112K) - Another database
4. `/opt/kast-web/instance/kast-web.db` (0 bytes) - Empty from migration

## Solution Applied

### 1. Updated config.py
Changed the database URI to use an **absolute path**:

```python
# Before
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///kast.db'

# After
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    f'sqlite:///{os.path.join(basedir, "instance", "kast-web.db")}'
```

This creates: `/opt/kast-web/instance/kast-web.db` (absolute path)

### 2. Fixed .env file
Updated the `.env` file to use the correct database path:

```bash
# Before
DATABASE_URL=sqlite:////home/kali/kast-web/db/kast.db

# After
DATABASE_URL=sqlite:////opt/kast-web/instance/kast-web.db
```

**Critical:** The `.env` file is loaded by `run.py` via `load_dotenv()` and takes precedence over config.py defaults!

### 3. Added Startup Logging
Enhanced `run.py` to display the database path on startup in bright green:

```python
# ANSI color codes
GREEN = '\033[92m'
CYAN = '\033[96m'
RESET = '\033[0m'

if __name__ == '__main__':
    print("=" * 60)
    print("KAST Web - Development Server")
    print("Logging configured at DEBUG level")
    print("Status endpoint debugging is ENABLED")
    print("=" * 60)
    print(f"{GREEN}Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}{RESET}")
    print("=" * 60)
```

This makes it immediately obvious which database Flask is using.

### 4. Consolidated Database
- Copied the main database (`kast.db` with 160K data) to the new location
- Ran the migration script successfully (now targeting correct database!)
- Backed up old database files to `/opt/kast-web/backups/`

### 3. Cleanup
```bash
# Old files backed up
/opt/kast-web/backups/kast.db.backup-20251224
/opt/kast-web/backups/instance-kast.db.backup-20251224

# Only one database remains
/opt/kast-web/instance/kast-web.db
```

## Verification

All verification steps passed:
```bash
# Database path is now absolute
python -c "from config import Config; print(Config.SQLALCHEMY_DATABASE_URI)"
# Output: sqlite:////opt/kast-web/instance/kast-web.db

# Columns were added successfully
sqlite3 instance/kast-web.db "PRAGMA table_info(scans);" | grep config
# Output: 16|config_profile_id|INTEGER|0||0
#         17|config_overrides|TEXT|0||0

# Profiles were created
sqlite3 instance/kast-web.db "SELECT name FROM scan_config_profiles;"
# Output: Standard
#         Stealth
#         Aggressive

# Flask starts without errors
python -c "from app import create_app; create_app()"
# Output: ✓ Flask app created successfully
```

## Migration Results

The migration completed successfully and created:
- `scan_config_profiles` table with 3 preset profiles
- `config_profile_id` column in `scans` table
- `config_overrides` column in `scans` table

**Preset Profiles Created:**
1. **Standard** - System default, available to all users
2. **Stealth** - Low-profile scanning, available to all users
3. **Aggressive** - High-speed scanning, power users only

## Lessons Learned

### Why Absolute Paths Are Better

1. **Consistency** - Same database file regardless of working directory
2. **Predictability** - Always know where the database is located
3. **Migration Safety** - Migrations always target the correct database
4. **Production Ready** - No ambiguity in deployment

### Best Practices

1. **Always use absolute paths** for database files in production
2. **Use the `instance` folder** for Flask application data (standard convention)
3. **Test configuration** before running migrations
4. **Backup databases** before making schema changes
5. **Verify migration targets** before executing

## Impact

- ✅ Flask now starts without errors
- ✅ Configuration profiles feature is fully functional
- ✅ All existing data preserved
- ✅ Database location is predictable and consistent
- ✅ Old database files safely backed up

## Future Considerations

### Environment Variable Override
The DATABASE_URL environment variable can still override the default:
```bash
export DATABASE_URL="sqlite:////custom/path/to/database.db"
```

### Production Deployment
In production deployments using the deployment scripts, ensure:
- DATABASE_URL is set explicitly in `/opt/kast-web/deployment/.env.production`
- Database directory has proper permissions
- Backups are configured

### SQLite Limitations
Consider migrating to PostgreSQL for production deployments with:
- Multiple concurrent users
- High transaction volumes
- Better concurrent access
- Advanced features

## Related Documentation

- `docs/CONFIG_PROFILES_IMPLEMENTATION.md` - Full feature documentation
- `docs/CONFIG_PROFILES_QUICK_START.md` - User guide
- `utils/migrate_scan_configs.py` - Migration script
- `config.py` - Updated configuration file
