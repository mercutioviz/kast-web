# ZAP Migration Database Fix

## Issue

After running the initial ZAP integration migration (`utils/migrate_zap_feature.py`), the application failed to start with the following error:

```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such column: scans.zap_plan_id
```

## Root Cause

The migration script used `db.create_all()` which creates NEW tables but does NOT alter existing tables to add new columns. The three new ZAP tables were created successfully:
- `zap_automation_plans`
- `zap_configurations`
- `zap_scan_progress`

However, the three new columns were NOT added to the existing `scans` table:
- `zap_plan_id` - Foreign key to zap_automation_plans
- `zap_config_id` - Foreign key to zap_configurations
- `zap_execution_mode` - String field to track execution mode

## Solution

Created a fix migration script: `utils/fix_zap_scan_columns.py`

This script:
1. Checks which columns are missing from the `scans` table
2. Uses `ALTER TABLE` statements to add the missing columns
3. Verifies all columns were added successfully
4. Provides clear success/failure messages

## Files Created/Modified

**Created:**
- `utils/fix_zap_scan_columns.py` - Fix migration script

**Modified:**
- `utils/verify_zap_migration.py` - Added explicit column verification in Test 5

**Database Backups:**
- Automatic backup created before running fix: `backups/kast-web.db.backup-YYYYMMDD-HHMMSS`

## Running the Fix

```bash
# From project root
cd /opt/kast-web

# Run the fix migration
python utils/fix_zap_scan_columns.py

# Verify the fix
python utils/verify_zap_migration.py

# Restart the application
# (Flask will now start without errors)
```

## Migration Output

```
============================================================
FIX MIGRATION: Add ZAP Columns to Scans Table
============================================================

Database: /opt/kast-web/instance/kast-web.db

Checking existing columns...
  ✗ Column 'zap_plan_id' is missing
  ✗ Column 'zap_config_id' is missing
  ✗ Column 'zap_execution_mode' is missing

Adding 3 missing column(s)...

  Executing: ALTER TABLE scans ADD COLUMN zap_plan_id INTEGER REFERENCES zap_automation_plans(id)
  ✓ Added column 'zap_plan_id' - Foreign key to ZAP automation plan
  Executing: ALTER TABLE scans ADD COLUMN zap_config_id INTEGER REFERENCES zap_configurations(id)
  ✓ Added column 'zap_config_id' - Foreign key to ZAP configuration
  Executing: ALTER TABLE scans ADD COLUMN zap_execution_mode VARCHAR(20)
  ✓ Added column 'zap_execution_mode' - Track which execution mode was used

✓ Successfully added all missing columns!

Verifying migration...
  ✓ Verified: zap_plan_id
  ✓ Verified: zap_config_id
  ✓ Verified: zap_execution_mode

============================================================
MIGRATION COMPLETED SUCCESSFULLY!
============================================================
```

## Verification Results

After running the fix, all verification tests pass:

```
============================================================
ZAP INTEGRATION VERIFICATION
============================================================

Test 1: Verifying database tables...
  ✓ ZapAutomationPlan table exists (8 records)
  ✓ ZapConfiguration table exists (3 records)
  ✓ ZapScanProgress table exists

Test 2: Testing encryption/decryption...
  ✓ JSON encryption/decryption works correctly
  ✓ String encryption/decryption works correctly

Test 3: Verifying default ZAP automation plans...
  ✓ All 8 default plans seeded successfully

Test 4: Verifying default ZAP configurations...
  ✓ All 3 default configurations seeded successfully

Test 5: Verifying model relationships...
  ✓ ZapAutomationPlan.creator relationship works
  ✓ ZapConfiguration.creator relationship works
  ✓ Scan model updated with ZAP fields:
    - zap_plan_id (verified in database)
    - zap_config_id (verified in database)
    - zap_execution_mode (verified in database)

Test 6: Testing sensitive data masking...
  ✓ Sensitive data properly masked in to_dict()
  ✓ Full data accessible with include_sensitive=True

============================================================
ALL VERIFICATION TESTS PASSED! ✓
============================================================
```

## Updated Database Schema

The `scans` table now includes the ZAP integration columns:

```sql
CREATE TABLE scans (
    id INTEGER NOT NULL,
    target VARCHAR(255) NOT NULL,
    scan_mode VARCHAR(20) NOT NULL,
    plugins TEXT,
    parallel BOOLEAN,
    verbose BOOLEAN,
    dry_run BOOLEAN,
    status VARCHAR(20) NOT NULL,
    output_dir VARCHAR(500),
    config_json TEXT,
    error_message TEXT,
    started_at DATETIME,
    completed_at DATETIME,
    celery_task_id VARCHAR(255),
    user_id INTEGER,
    logo_id INTEGER,
    execution_log_path VARCHAR(500),
    source VARCHAR(20) DEFAULT 'web',
    config_profile_id INTEGER REFERENCES scan_config_profiles(id),
    config_overrides TEXT,
    zap_plan_id INTEGER REFERENCES zap_automation_plans(id),      -- NEW
    zap_config_id INTEGER REFERENCES zap_configurations(id),      -- NEW
    zap_execution_mode VARCHAR(20),                               -- NEW
    PRIMARY KEY (id)
);
```

## Rollback (If Needed)

If you need to rollback this fix:

```bash
# Stop the application first
# Then restore from backup
cp backups/kast-web.db.backup-YYYYMMDD-HHMMSS instance/kast-web.db

# Restart the application
```

## Lessons Learned

For future migrations that need to ALTER existing tables:
1. Use explicit `ALTER TABLE` statements instead of relying on `db.create_all()`
2. Always create automatic backups before migrations
3. Verify column existence before attempting to add them
4. Include column verification in verification scripts
5. Follow the migration script pattern in `utils/fix_zap_scan_columns.py`

## Status

✅ **FIXED** - Database migration completed successfully  
✅ All verification tests passing  
✅ Application starts without errors  
✅ Ready for Phase 3 implementation

---

**Date Fixed**: January 7, 2026  
**Issue**: Missing ZAP columns in scans table  
**Resolution**: Created and ran fix migration script
