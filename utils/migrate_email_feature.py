#!/usr/bin/env python3
"""
Migration script for Email Feature
Adds email-related settings to SystemSettings table
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import SystemSettings

def migrate_email_feature():
    """Add email-related settings to SystemSettings"""
    app = create_app()
    
    with app.app_context():
        print("Starting Email Feature Migration...")
        print("=" * 60)
        
        # Email settings to add
        email_settings = {
            'email_enabled': False,
            'smtp_host': '',
            'smtp_port': 587,
            'smtp_username': '',
            'smtp_password': '',
            'from_email': '',
            'from_name': 'KAST Security',
            'use_tls': True,
            'use_ssl': False
        }
        
        # Check which settings already exist
        existing_settings = {}
        for key in email_settings.keys():
            setting = SystemSettings.query.filter_by(key=key).first()
            if setting:
                existing_settings[key] = setting.value
                print(f"✓ Setting '{key}' already exists with value: {setting.value}")
        
        # Add missing settings
        added_count = 0
        for key, default_value in email_settings.items():
            if key not in existing_settings:
                setting = SystemSettings(key=key, value=str(default_value))
                db.session.add(setting)
                added_count += 1
                print(f"+ Adding setting '{key}' with default value: {default_value}")
        
        if added_count > 0:
            db.session.commit()
            print(f"\n✓ Successfully added {added_count} email settings to database")
        else:
            print("\n✓ All email settings already exist in database")
        
        print("=" * 60)
        print("Email Feature Migration completed!")
        print("\nNext steps:")
        print("1. Configure SMTP settings in Admin Panel > Settings")
        print("2. Test SMTP connection using the 'Test SMTP Connection' button")
        print("3. Enable email functionality by toggling 'Enable Email Functionality'")
        print("4. Users can now send scan reports via email")

if __name__ == '__main__':
    try:
        migrate_email_feature()
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
