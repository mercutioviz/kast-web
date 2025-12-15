# Migration Script Standards for KAST-Web

This document outlines best practices for creating database migration scripts in KAST-Web, ensuring they work correctly in both interactive and automated contexts.

## Overview

Migration scripts in the `utils/` directory are used to update the database schema. These scripts must work correctly when:
- Run manually by developers (interactive mode)
- Run automatically during installation (non-interactive mode)
- Run in CI/CD pipelines or cron jobs

## Non-Interactive Mode Detection

### The Problem

Interactive prompts (like `input()`) will cause migration scripts to hang when run in automated contexts where stdin is not available or is redirected to a log file.

### The Solution

Use Python's `sys.stdin.isatty()` **AND** `sys.stdout.isatty()` to detect if the script is running in an interactive terminal. Checking both ensures proper detection even when output is redirected during installation:

```python
import sys

# Check if running in an interactive environment
# Check both stdin and stdout to handle redirected output during installation
is_interactive = sys.stdin.isatty() and sys.stdout.isatty()

if not is_interactive:
    # Non-interactive mode: skip prompts, use safe defaults
    print("  Running in non-interactive mode - skipping re-migration")
    return
else:
    # Interactive mode: prompt user for input
    response = input("Do you want to continue anyway? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return
```

**Why check both stdin AND stdout?**
During installation, the install.sh script redirects output like this:
```bash
python3 "$migration" >> "$LOG_FILE" 2>&1
```

This redirects stdout and stderr to a log file, but stdin might still be attached to a TTY. By checking both `stdin.isatty()` and `stdout.isatty()`, we ensure proper non-interactive detection regardless of how the script is invoked.

## Standard Migration Script Template

All migration scripts should follow this pattern:

```python
#!/usr/bin/env python3
"""
Migration script description.

Usage:
    python3 utils/migrate_example.py

Changes:
    - List of changes this migration makes

Non-Interactive Mode:
    When run in an automated context, the script automatically detects
    non-interactive environments and skips prompts.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text

def migrate():
    """Run the migration"""
    app = create_app()
    
    with app.app_context():
        print("="*80)
        print("KAST-Web Example Migration")
        print("="*80)
        print()
        
        try:
            # Check if migration has already been applied
            # (Check for specific column, table, or data condition)
            
            if migration_already_applied:
                print("✓ Migration already applied")
                
                # Non-interactive mode detection
                if not sys.stdin.isatty():
                    print("  Running in non-interactive mode - skipping")
                    print()
                    print("="*80)
                    print("Migration skipped (already applied)")
                    print("="*80)
                    return
                
                # Interactive prompt
                print()
                response = input("Do you want to continue anyway? (y/N): ")
                if response.lower() != 'y':
                    print("Migration cancelled.")
                    return
            
            # Perform migration steps
            print("Applying migration...")
            
            # Your migration code here
            
            # Commit changes
            db.session.commit()
            
            print("="*80)
            print("Migration completed successfully!")
            print("="*80)
            print()
            
        except Exception as e:
            db.session.rollback()
            print()
            print("="*80)
            print("ERROR: Migration failed!")
            print("="*80)
            print(f"Error: {str(e)}")
            print()
            print("The database has been rolled back.")
            sys.exit(1)

if __name__ == '__main__':
    migrate()
```

## Key Points

### 1. Always Check if Migration Already Applied

Before making changes, check if the migration has already been run:

```python
# For SQLite
result = db.session.execute(text("PRAGMA table_info(table_name)"))
columns = [row[1] for row in result]
if 'new_column' in columns:
    # Already applied
```

```python
# For checking if a table exists (works for all DB types)
from sqlalchemy import inspect
inspector = inspect(db.engine)
if 'new_table' in inspector.get_table_names():
    # Already applied
```

### 2. Always Use TTY Detection for Interactive Prompts

```python
if not sys.stdin.isatty():
    # Non-interactive: safe default behavior
    return  # or continue with safe defaults
else:
    # Interactive: ask user
    response = input("Continue? (y/N): ")
```

### 3. Always Provide Clear Output

- Use clear section headers with `=` borders
- Indicate whether migration was applied or skipped
- Show progress for long operations
- Provide summary of changes made

### 4. Always Handle Errors Gracefully

```python
try:
    # Migration code
    db.session.commit()
except Exception as e:
    db.session.rollback()
    print(f"ERROR: {str(e)}")
    sys.exit(1)  # Non-zero exit for automation
```

### 5. Always Set Working Directory

To prevent files being created in the wrong location:

```python
# At the start of migrate()
os.chdir('/opt/kast-web')  # or use path from config
```

## Testing Migration Scripts

Test both interactive and non-interactive modes:

### Interactive Mode
```bash
# Run directly in terminal
python3 utils/migrate_example.py
```

### Non-Interactive Mode
```bash
# Simulate automated context (no TTY)
python3 utils/migrate_example.py < /dev/null

# Or redirect output (like install.sh does)
python3 utils/migrate_example.py >> /tmp/test.log 2>&1
```

### Test Idempotency
```bash
# Run twice to ensure it handles "already applied" correctly
python3 utils/migrate_example.py
python3 utils/migrate_example.py  # Should skip gracefully
```

## Examples

### Example 1: Adding a Column (Simple)

```python
# Check if column exists
result = db.session.execute(text("PRAGMA table_info(scans)"))
columns = [row[1] for row in result]

if 'new_field' in columns:
    print("✓ Column 'new_field' already exists")
    if not sys.stdin.isatty():
        print("  Non-interactive mode - skipping")
        return
    # ... interactive prompt ...

# Add column
db.session.execute(text(
    "ALTER TABLE scans ADD COLUMN new_field VARCHAR(50)"
))
db.session.commit()
```

### Example 2: Creating a New Table

```python
from sqlalchemy import inspect

inspector = inspect(db.engine)
if 'new_table' in inspector.get_table_names():
    print("✓ Table 'new_table' already exists")
    if not sys.stdin.isatty():
        return
    # ... interactive prompt ...

# Create table using SQLAlchemy model
db.create_all()  # Creates only missing tables
db.session.commit()
```

### Example 3: Data Migration

```python
# Check if data migration already done
result = db.session.execute(text(
    "SELECT COUNT(*) FROM users WHERE migrated_flag = 1"
))
migrated_count = result.scalar()

if migrated_count > 0:
    print(f"✓ Data migration already applied ({migrated_count} records)")
    if not sys.stdin.isatty():
        return
    # ... interactive prompt ...

# Perform data migration
db.session.execute(text("""
    UPDATE users 
    SET new_field = old_field, migrated_flag = 1 
    WHERE migrated_flag = 0
"""))
db.session.commit()
```

## Installation Script Integration

The `install.sh` script runs migrations in non-interactive mode:

```bash
# In initialize_database() function
for migration in "$INSTALL_DIR"/utils/migrate*.py; do
    if [[ -f "$migration" ]]; then
        print_info "Running migration: $(basename "$migration")"
        python3 "$migration" >> "$LOG_FILE" 2>&1 || true
    fi
done
```

Key points:
- Output is redirected to log file (triggers non-interactive mode)
- `|| true` ensures failure doesn't stop installation
- Migrations run in alphabetical order

## Troubleshooting

### Migration Hangs During Installation

**Cause:** Interactive prompt waiting for input
**Solution:** Add `sys.stdin.isatty()` check before any `input()` calls

### Migration Runs Twice

**Cause:** No check for "already applied" condition
**Solution:** Add detection at start of migration

### Files Created in Wrong Location

**Cause:** Working directory not set
**Solution:** Use `os.chdir()` or absolute paths

## References

- Python `sys.stdin.isatty()` documentation
- SQLAlchemy inspection API
- KAST-Web migration examples in `utils/`

## Checklist for New Migration Scripts

- [ ] Follows template structure
- [ ] Checks if migration already applied
- [ ] Uses `sys.stdin.isatty()` for any interactive prompts
- [ ] Sets working directory if needed
- [ ] Has clear error handling and rollback
- [ ] Tested in both interactive and non-interactive modes
- [ ] Tested running twice (idempotent)
- [ ] Documentation updated (this file, README, etc.)
- [ ] Added to version control

---

**Last Updated:** December 2025  
**Author:** KAST-Web Development Team
