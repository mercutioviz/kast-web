"""
Fix migration script to add missing ZAP columns to scans table
Adds: zap_plan_id, zap_config_id, zap_execution_mode columns
"""
import sys
import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / 'instance' / 'kast-web.db'


def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def add_missing_columns():
    """Add missing ZAP columns to scans table"""
    print("=" * 60)
    print("FIX MIGRATION: Add ZAP Columns to Scans Table")
    print("=" * 60)
    print()
    
    if not DB_PATH.exists():
        print(f"✗ Error: Database not found at {DB_PATH}")
        return False
    
    print(f"Database: {DB_PATH}")
    print()
    
    # Connect to database
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    columns_to_add = [
        {
            'name': 'zap_plan_id',
            'definition': 'INTEGER REFERENCES zap_automation_plans(id)',
            'description': 'Foreign key to ZAP automation plan'
        },
        {
            'name': 'zap_config_id',
            'definition': 'INTEGER REFERENCES zap_configurations(id)',
            'description': 'Foreign key to ZAP configuration'
        },
        {
            'name': 'zap_execution_mode',
            'definition': 'VARCHAR(20)',
            'description': 'Track which execution mode was used'
        }
    ]
    
    print("Checking existing columns...")
    existing_columns = []
    missing_columns = []
    
    for col in columns_to_add:
        if check_column_exists(cursor, 'scans', col['name']):
            existing_columns.append(col['name'])
            print(f"  ✓ Column '{col['name']}' already exists")
        else:
            missing_columns.append(col)
            print(f"  ✗ Column '{col['name']}' is missing")
    
    print()
    
    if not missing_columns:
        print("✓ All ZAP columns already exist in scans table!")
        conn.close()
        return True
    
    print(f"Adding {len(missing_columns)} missing column(s)...")
    print()
    
    try:
        for col in missing_columns:
            sql = f"ALTER TABLE scans ADD COLUMN {col['name']} {col['definition']}"
            print(f"  Executing: {sql}")
            cursor.execute(sql)
            print(f"  ✓ Added column '{col['name']}' - {col['description']}")
        
        conn.commit()
        print()
        print("✓ Successfully added all missing columns!")
        
    except sqlite3.Error as e:
        print(f"\n✗ Error adding columns: {e}")
        conn.rollback()
        conn.close()
        return False
    
    # Verify all columns now exist
    print()
    print("Verifying migration...")
    all_present = True
    for col in columns_to_add:
        if check_column_exists(cursor, 'scans', col['name']):
            print(f"  ✓ Verified: {col['name']}")
        else:
            print(f"  ✗ Failed: {col['name']}")
            all_present = False
    
    conn.close()
    
    if all_present:
        print()
        print("=" * 60)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print()
        print("The scans table now has all required ZAP columns.")
        print("You can now restart your Flask application.")
        print()
        return True
    else:
        print()
        print("✗ Migration verification failed!")
        return False


if __name__ == '__main__':
    print()
    success = add_missing_columns()
    if success:
        sys.exit(0)
    else:
        print()
        print("Migration failed. Database backup is available in backups/ directory.")
        print("You can restore it with:")
        print("  cp backups/kast-web.db.backup-YYYYMMDD-HHMMSS instance/kast-web.db")
        print()
        sys.exit(1)
