# Migration Script Standards

This document defines the standards for all database migration scripts in the KAST-Web project to ensure consistency, reliability, and compatibility with automated installation/update processes.

## Overview

Migration scripts are located in the `utils/` directory and are automatically executed during installation and updates. They must support both interactive and non-interactive execution modes.

## File Naming Convention

- **Pattern**: `migrate_<feature_name>.py`
- **Examples**: 
  - `migrate_scan_configs.py`
  - `migrate_email_feature.py`
  - `migrate_logo_feature.py`

## Required Features

All migration scripts MUST include:

1. **Non-interactive mode support**
2. **Idempotent operations** (safe to run multiple times)
3. **Proper error handling**
4. **Clear status messages**
5. **Rollback capability** (where applicable)

## Standard Template

```python
#!/usr/bin/env python3
"""
Migration script for [Feature Name]

This migration:
1. [Action 1]
2. [Action 2]
3. [Action 3]

Run this script after backing up your database.

Usage:
  python3 migrate_feature.py [--non-interactive]
  python3 migrate_feature.py rollback [--non-interactive]
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path to import app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, db
from app.models import YourModels
from sqlalchemy import text, inspect


def is_interactive():
    """
    Check if running in interactive mode.
    Returns False if:
    - --non-interactive flag is passed
    - NON_INTERACTIVE environment variable is set
    - stdin is not a TTY
    """
    # Check command-line flag
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--non-interactive', action='store_true')
    args, _ = parser.parse_known_args()
    
    if args.non_interactive:
        return False
    
    # Check environment variable
    if os.environ.get('NON_INTERACTIVE', '').lower() in ('1', 'true', 'yes'):
        return False
    
    # Check if stdin is a TTY
    return sys.stdin.isatty()


def run_migration():
    """Execute the migration"""
    app = create_app()
    interactive = is_interactive()
    
    with app.app_context():
        print("=" * 60)
        print("KAST-Web [Feature Name] Migration")
        print("=" * 60)
        print()
        
        # Check if migration already applied
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'target_table' in existing_tables:
            print("⚠️  WARNING: target_table already exists!")
            
            if interactive:
                response = input("Do you want to continue anyway? (yes/no): ")
                if response.lower() != 'yes':
                    print("Migration cancelled.")
                    return
            else:
                print("ℹ️  Non-interactive mode: Checking if migration needed...")
                # Check if migration is actually complete
                existing_data = db.session.execute(
                    text("SELECT COUNT(*) FROM target_table")
                ).scalar()
                
                if existing_data > 0:
                    print(f"✓ Found {existing_data} existing records. Skipping migration.")
                    return
                else:
                    print("ℹ️  Table exists but empty. Proceeding...")
        
        # Perform migration steps
        print("Step 1: Creating tables...")
        try:
            db.create_all()
            print("✓ Tables created successfully")
        except Exception as e:
            print(f"✗ Error creating tables: {e}")
            db.session.rollback()
            return
        
        # Additional steps...
        
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)


def rollback_migration():
    """Rollback the migration (if applicable)"""
    app = create_app()
    interactive = is_interactive()
    
    with app.app_context():
        print("=" * 60)
        print("KAST-Web [Feature Name] Migration ROLLBACK")
        print("=" * 60)
        print()
        print("⚠️  WARNING: This will [describe what will be removed]!")
        print()
        
        if interactive:
            response = input("Are you sure you want to rollback? (yes/no): ")
            if response.lower() != 'yes':
                print("Rollback cancelled.")
                return
        else:
            print("⚠️  Non-interactive mode: Proceeding with rollback...")
        
        # Perform rollback...
        
        print("\n" + "=" * 60)
        print("✅ Rollback completed!")
        print("=" * 60)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback_migration()
    else:
        run_migration()
```

## Non-Interactive Mode Implementation

### 1. Detection Function

```python
def is_interactive():
    """
    Check if running in interactive mode.
    Priority order:
    1. Command-line flag (--non-interactive)
    2. Environment variable (NON_INTERACTIVE)
    3. TTY detection (sys.stdin.isatty())
    """
    # Check command-line flag
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--non-interactive', action='store_true')
    args, _ = parser.parse_known_args()
    
    if args.non_interactive:
        return False
    
    # Check environment variable
    if os.environ.get('NON_INTERACTIVE', '').lower() in ('1', 'true', 'yes'):
        return False
    
    # Check if stdin is a TTY
    return sys.stdin.isatty()
```

### 2. Handling User Input

**Interactive Mode:**
```python
if interactive:
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Operation cancelled.")
        return
```

**Non-Interactive Mode:**
```python
else:
    print("ℹ️  Non-interactive mode: Using safe default behavior")
    # Check if operation is needed
    if not needs_operation():
        print("✓ Operation not needed. Skipping.")
        return
    print("ℹ️  Proceeding with operation...")
```

## Idempotent Operations

Migrations MUST be idempotent - safe to run multiple times without causing errors or duplicate data.

### Checking Existing State

```python
# Check if table exists
inspector = inspect(db.engine)
existing_tables = inspector.get_table_names()

if 'new_table' in existing_tables:
    print("⚠️  Table already exists")
    # Decide whether to skip or continue

# Check if column exists
columns = [col['name'] for col in inspector.get_columns('existing_table')]
if 'new_column' not in columns:
    # Add column
else:
    print("⚠️  Column already exists, skipping")

# Check if data exists
existing_count = db.session.execute(
    text("SELECT COUNT(*) FROM table WHERE condition")
).scalar()

if existing_count > 0:
    print(f"✓ Found {existing_count} existing records. Skipping data creation.")
    return
```

### Creating Tables

```python
# Use CREATE TABLE IF NOT EXISTS
db.session.execute(text("""
    CREATE TABLE IF NOT EXISTS new_table (
        id INTEGER PRIMARY KEY,
        ...
    )
"""))
```

### Adding Columns (SQLite)

```python
# Check before adding
columns = [col['name'] for col in inspector.get_columns('table_name')]

if 'new_column' not in columns:
    db.session.execute(text("""
        ALTER TABLE table_name 
        ADD COLUMN new_column TYPE
    """))
    print("✓ Added new_column")
else:
    print("⚠️  new_column already exists")
```

### Inserting Data

```python
# Check if record exists before inserting
existing = db.session.execute(
    text("SELECT id FROM table WHERE unique_key = :key"),
    {'key': value}
).fetchone()

if not existing:
    # Insert new record
    db.session.execute(text("INSERT INTO ..."), {...})
    print("✓ Record created")
else:
    print("⚠️  Record already exists, skipping")
```

## Error Handling

### Database Operations

```python
try:
    db.session.execute(text("..."))
    db.session.commit()
    print("✓ Operation successful")
except Exception as e:
    print(f"✗ Error: {e}")
    db.session.rollback()
    return  # or sys.exit(1) for critical failures
```

### File Operations

```python
try:
    Path(directory).mkdir(parents=True, exist_ok=True)
    print(f"✓ Created directory: {directory}")
except Exception as e:
    print(f"✗ Error creating directory: {e}")
    # Decide whether to continue or fail
```

## Status Messages

Use clear, consistent status messages:

```python
# Info messages
print("ℹ️  Checking database structure...")

# Success messages
print("✓ Table created successfully")

# Warning messages
print("⚠️  WARNING: Table already exists!")

# Error messages
print("✗ Error: Failed to create table")

# Non-interactive mode messages
print("ℹ️  Non-interactive mode: Proceeding with defaults...")
```

## Testing Checklist

Before committing a migration script, verify:

- [ ] **Interactive Mode**: Runs successfully with user prompts
- [ ] **Non-Interactive Mode**: Runs with `--non-interactive` flag
- [ ] **Environment Variable**: Respects `NON_INTERACTIVE=1`
- [ ] **Idempotent**: Can be run multiple times safely
- [ ] **Fresh Database**: Works on new installation
- [ ] **Existing Data**: Handles existing tables/columns correctly
- [ ] **Error Handling**: Gracefully handles failures
- [ ] **Rollback**: Rollback function works (if provided)
- [ ] **Status Messages**: Clear output for both modes
- [ ] **Documentation**: Docstring explains what migration does

## Integration with Install/Update Scripts

### Install Script (install.sh)

```bash
# Run database migrations if they exist
if [[ -d "$INSTALL_DIR/utils" ]]; then
    print_info "Running database migrations..."
    
    # Set environment variable for non-interactive mode
    export NON_INTERACTIVE=1
    
    for migration in "$INSTALL_DIR"/utils/migrate*.py; do
        if [[ -f "$migration" ]]; then
            print_info "Running migration: $(basename "$migration")"
            # Pass --non-interactive flag to all migration scripts
            python3 "$migration" --non-interactive >> "$LOG_FILE" 2>&1 || true
        fi
    done
    
    # Unset the environment variable
    unset NON_INTERACTIVE
fi
```

### Update Script (update.sh)

```bash
# Run migration scripts if they exist
if [[ -d "$INSTALL_DIR/utils" ]]; then
    # Set environment variable for non-interactive mode
    export NON_INTERACTIVE=1
    
    MIGRATION_COUNT=0
    for migration in "$INSTALL_DIR"/utils/migrate*.py; do
        if [[ -f "$migration" ]]; then
            print_info "Running migration: $(basename "$migration")"
            # Pass --non-interactive flag to all migration scripts
            if python3 "$migration" --non-interactive >> "$LOG_FILE" 2>&1; then
                print_success "Migration completed: $(basename "$migration")"
                ((MIGRATION_COUNT++))
            else
                print_warning "Migration had issues: $(basename "$migration") (continuing)"
            fi
        fi
    done
    
    # Unset the environment variable
    unset NON_INTERACTIVE
fi
```

## Common Patterns

### Pattern 1: Simple Table Creation

```python
def run_migration():
    app = create_app()
    interactive = is_interactive()
    
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'new_table' in existing_tables:
            if interactive:
                response = input("Table exists. Continue? (yes/no): ")
                if response.lower() != 'yes':
                    return
            else:
                print("ℹ️  Table exists. Skipping migration.")
                return
        
        db.create_all()
        print("✓ Tables created")
```

### Pattern 2: Column Addition

```python
def run_migration():
    app = create_app()
    interactive = is_interactive()
    
    with app.app_context():
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('existing_table')]
        
        if 'new_column' not in columns:
            db.session.execute(text("""
                ALTER TABLE existing_table 
                ADD COLUMN new_column TEXT
            """))
            db.session.commit()
            print("✓ Column added")
        else:
            print("⚠️  Column already exists. Skipping.")
```

### Pattern 3: Data Population

```python
def run_migration():
    app = create_app()
    interactive = is_interactive()
    
    with app.app_context():
        # Check if data exists
        count = db.session.execute(
            text("SELECT COUNT(*) FROM table")
        ).scalar()
        
        if count > 0:
            if interactive:
                response = input(f"Found {count} records. Add more? (yes/no): ")
                if response.lower() != 'yes':
                    return
            else:
                print(f"✓ Found {count} existing records. Skipping.")
                return
        
        # Insert data...
        print("✓ Data populated")
```

## Best Practices

1. **Always check before creating**: Use `IF NOT EXISTS` or check existence first
2. **Use transactions**: Wrap related operations in try-except with rollback
3. **Provide clear feedback**: Use emoji prefixes (✓ ⚠️ ✗ ℹ️) for status
4. **Handle both modes**: Support interactive and non-interactive execution
5. **Be defensive**: Assume migrations may run multiple times
6. **Log important actions**: Use print statements for audit trail
7. **Test thoroughly**: Verify on fresh DB and existing DB
8. **Document changes**: Update relevant docs when adding migrations

## Rollback Considerations

Not all migrations can be safely rolled back. When implementing rollback:

1. **Document what gets deleted**: Clearly state in warnings
2. **Require confirmation**: In interactive mode, ask for explicit "yes"
3. **Handle dependencies**: Check for foreign key constraints
4. **Backup data**: Suggest backup before rollback
5. **SQLite limitations**: Note that SQLite doesn't support DROP COLUMN

```python
def rollback_migration():
    app = create_app()
    interactive = is_interactive()
    
    with app.app_context():
        print("⚠️  WARNING: This will delete all [feature] data!")
        print("⚠️  This action cannot be undone!")
        print()
        
        if interactive:
            print("Please type 'DELETE ALL DATA' to confirm:")
            response = input("> ")
            if response != 'DELETE ALL DATA':
                print("Rollback cancelled.")
                return
        else:
            print("⚠️  Non-interactive mode: Proceeding with rollback...")
        
        # Perform rollback operations...
```

## Troubleshooting

### Common Issues

**Issue**: Migration hangs during automated install
- **Cause**: Interactive prompt waiting for input
- **Solution**: Ensure `is_interactive()` detects non-interactive mode

**Issue**: Migration creates duplicate data
- **Cause**: Not checking if data already exists
- **Solution**: Always check before inserting

**Issue**: Migration fails on SQLite
- **Cause**: Using unsupported SQL operations
- **Solution**: Use SQLite-compatible syntax, check docs

**Issue**: Migration fails with permission error
- **Cause**: Database file ownership/permissions
- **Solution**: Ensure proper ownership (www-data:www-data)

## Migration Script Checklist

Use this checklist when creating a new migration:

```markdown
## Migration Script Checklist

- [ ] Added `is_interactive()` function
- [ ] Supports `--non-interactive` flag
- [ ] Respects `NON_INTERACTIVE` environment variable
- [ ] Checks for existing tables/columns before creating
- [ ] Handles existing data gracefully
- [ ] Provides clear status messages
- [ ] Includes proper error handling with rollback
- [ ] Has informative docstring with usage examples
- [ ] Tested in interactive mode
- [ ] Tested in non-interactive mode
- [ ] Tested on fresh database
- [ ] Tested on database with existing data
- [ ] Tested running twice (idempotent)
- [ ] Rollback function provided (if applicable)
- [ ] Updated this documentation if new patterns added
```

## Future Considerations

As the project evolves, consider:

1. **Migration versioning**: Track which migrations have been applied
2. **Migration dependencies**: Specify which migrations must run first
3. **Migration history table**: Record when each migration ran
4. **Automated testing**: CI/CD tests for all migrations
5. **Migration rollback tracking**: Keep history of rollbacks

## Reference Examples

See these existing migrations for reference:

- **Simple table creation**: `migrate_phase3.py`
- **Column addition**: `migrate_logo_feature.py`
- **Data population**: `migrate_email_feature.py`
- **Complex migration**: `migrate_scan_configs.py` (includes rollback)

## Conclusion

Following these standards ensures that all migration scripts work reliably in both interactive and automated deployment scenarios. This consistency makes the installation and update process more robust and maintainable.
