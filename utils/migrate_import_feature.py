#!/usr/bin/env python3
"""
Migration script to add import feature support to KAST-Web database.

This migration adds the 'source' field to the scans table to distinguish between
web-executed scans and CLI-imported scans.

Usage:
    python3 utils/migrate_import_feature.py

Changes:
    - Adds 'source' column to scans table (default: 'web')
    - Sets all existing scans to source='web'
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
        print("KAST-Web Import Feature Migration")
        print("="*80)
        print()
        
        try:
            # Check if column already exists
            result = db.session.execute(text("PRAGMA table_info(scans)"))
            columns = [row[1] for row in result]
            
            if 'source' in columns:
                print("✓ Column 'source' already exists in scans table")
                print("  Migration may have already been run.")
                print()
                response = input("Do you want to continue anyway? (y/N): ")
                if response.lower() != 'y':
                    print("Migration cancelled.")
                    return
            
            print("Adding 'source' column to scans table...")
            
            # Add source column with default value 'web'
            db.session.execute(text(
                "ALTER TABLE scans ADD COLUMN source VARCHAR(20) DEFAULT 'web'"
            ))
            
            print("✓ Column added successfully")
            print()
            
            # Update all existing scans to have source='web'
            print("Setting existing scans to source='web'...")
            result = db.session.execute(text(
                "UPDATE scans SET source = 'web' WHERE source IS NULL"
            ))
            
            print(f"✓ Updated {result.rowcount} existing scan records")
            print()
            
            # Commit changes
            db.session.commit()
            
            print("="*80)
            print("Migration completed successfully!")
            print("="*80)
            print()
            print("Summary:")
            print("  - Added 'source' column to scans table")
            print("  - Set existing scans to source='web'")
            print("  - Import feature is now ready to use")
            print()
            
        except Exception as e:
            db.session.rollback()
            print()
            print("="*80)
            print("ERROR: Migration failed!")
            print("="*80)
            print(f"Error: {str(e)}")
            print()
            print("The database has been rolled back to its previous state.")
            print("Please check the error message and try again.")
            sys.exit(1)

if __name__ == '__main__':
    migrate()
