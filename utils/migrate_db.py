#!/usr/bin/env python3
"""
Database migration script to add celery_task_id column to scans table
Run this script to update the database schema
"""

import os
import sqlite3
from pathlib import Path

def migrate_database():
    """Add celery_task_id column to scans table if it doesn't exist"""
    
    # Get database path from config
    db_dir = Path.home() / 'kast-web' / 'db'
    db_path = db_dir / 'kast.db'
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Database will be created automatically when you run the application.")
        return
    
    print(f"Migrating database at {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(scans)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'celery_task_id' not in columns:
            print("Adding celery_task_id column to scans table...")
            cursor.execute("ALTER TABLE scans ADD COLUMN celery_task_id VARCHAR(255)")
            conn.commit()
            print("✓ Migration completed successfully!")
        else:
            print("✓ Database already up to date (celery_task_id column exists)")
    
    except Exception as e:
        print(f"✗ Error during migration: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()
