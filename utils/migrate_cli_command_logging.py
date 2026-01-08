#!/usr/bin/env python3
"""
Migration script to add CLI command logging fields to Scan model
"""

import sqlite3
import sys
from pathlib import Path

def migrate():
    """Add actual_cli_command column to scans table"""
    
    # Database path
    db_path = Path(__file__).parent.parent / 'instance' / 'kast-web.db'
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(scans)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'actual_cli_command' in columns:
            print("✓ Column 'actual_cli_command' already exists in scans table")
        else:
            print("Adding 'actual_cli_command' column to scans table...")
            cursor.execute("""
                ALTER TABLE scans 
                ADD COLUMN actual_cli_command TEXT
            """)
            print("✓ Column 'actual_cli_command' added successfully")
        
        conn.commit()
        print("\n✓ Migration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"\n✗ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    
    finally:
        conn.close()

if __name__ == '__main__':
    print("="*60)
    print("CLI Command Logging Migration")
    print("="*60)
    migrate()
