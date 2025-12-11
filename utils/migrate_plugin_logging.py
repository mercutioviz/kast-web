#!/usr/bin/env python3
"""
Migration script to add execution logging support to KAST-Web

This migration adds the execution_log_path field to the Scan model
to support storing full KAST execution logs for debugging.

Usage:
    python3 utils/migrate_plugin_logging.py
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text

def migrate():
    """Run the migration"""
    app = create_app()
    
    with app.app_context():
        print("Starting plugin logging migration...")
        
        # Check if column already exists
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('scans')]
        
        if 'execution_log_path' in columns:
            print("✓ execution_log_path column already exists")
            return True
        
        try:
            # Add execution_log_path column to scans table
            print("Adding execution_log_path column to scans table...")
            db.session.execute(text(
                'ALTER TABLE scans ADD COLUMN execution_log_path VARCHAR(500)'
            ))
            db.session.commit()
            print("✓ execution_log_path column added successfully")
            
            print("\n✓ Plugin logging migration completed successfully!")
            print("\nNew features enabled:")
            print("  - Full KAST execution logs stored with scan results")
            print("  - Per-plugin error messages captured and displayed")
            print("  - View and download execution logs from scan detail page")
            
            return True
            
        except Exception as e:
            print(f"\n✗ Migration failed: {str(e)}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
