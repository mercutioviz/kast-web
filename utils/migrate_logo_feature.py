#!/usr/bin/env python3
"""
Database migration script for Logo White-Labeling Feature
Adds:
- report_logos table
- logo_id column to scans table
- default_logo_id system setting
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import ReportLogo, SystemSettings
from datetime import datetime
import shutil

def migrate():
    """Run the migration"""
    app = create_app()
    
    with app.app_context():
        print("Starting logo feature migration...")
        
        # Create new tables (report_logos)
        print("Creating database tables...")
        db.create_all()
        print("✓ New tables created")
        
        # Add logo_id column to scans table if it doesn't exist
        print("Adding logo_id column to scans table...")
        try:
            # Check if column already exists
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('scans')]
            
            if 'logo_id' not in columns:
                # Add the column using raw SQL (required for SQLite)
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE scans ADD COLUMN logo_id INTEGER'))
                    conn.commit()
                print("✓ Added logo_id column to scans table")
            else:
                print("✓ logo_id column already exists in scans table")
        except Exception as e:
            print(f"⚠ Error adding column: {e}")
            print("  Attempting to continue...")
        
        # Create uploads directory structure
        print("Creating uploads directory structure...")
        uploads_dir = Path(app.root_path) / 'static' / 'uploads' / 'logos'
        uploads_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {uploads_dir}")
        
        # Copy current kast-logo.png to uploads and create default logo entry
        print("Setting up default logo...")
        current_logo = Path(app.root_path) / 'static' / 'images' / 'kast-logo.png'
        
        if current_logo.exists():
            # Copy to uploads directory with a unique name
            import uuid
            default_logo_filename = f"{uuid.uuid4()}-kast-logo.png"
            default_logo_path = uploads_dir / default_logo_filename
            shutil.copy2(current_logo, default_logo_path)
            
            # Get file size
            file_size = default_logo_path.stat().st_size
            
            # Find or create admin user (user_id=1 typically)
            from app.models import User
            admin_user = User.query.filter_by(role='admin').first()
            if not admin_user:
                admin_user = User.query.first()
            
            if admin_user:
                # Create default logo entry
                default_logo = ReportLogo(
                    name='KAST Default Logo',
                    description='Original KAST logo - system default',
                    filename='kast-logo.png',
                    file_path=str(default_logo_path),
                    mime_type='image/png',
                    file_size=file_size,
                    uploaded_by=admin_user.id,
                    uploaded_at=datetime.utcnow()
                )
                db.session.add(default_logo)
                db.session.commit()
                
                print(f"✓ Created default logo entry (ID: {default_logo.id})")
                
                # Set as system default
                SystemSettings.set_setting(
                    key='default_logo_id',
                    value=str(default_logo.id),
                    value_type='int',
                    description='Default logo for reports',
                    user_id=admin_user.id
                )
                print(f"✓ Set system default logo to ID: {default_logo.id}")
            else:
                print("⚠ Warning: No users found. Please create a logo entry manually.")
        else:
            print(f"⚠ Warning: Default logo not found at {current_logo}")
            print("  You'll need to upload a default logo through the admin interface.")
        
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Ensure the KAST CLI tool has been updated with --logo parameter support")
        print("2. Restart the application to load the new models")
        print("3. Access the logo management page at /logos/manage (once routes are implemented)")

if __name__ == '__main__':
    migrate()
