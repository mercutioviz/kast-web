#!/usr/bin/env python3
"""
Migration script for Phase 3: Admin Panel
Creates audit_logs and system_settings tables
"""

import sys
from app import create_app, db
from app.models import AuditLog, SystemSettings

def migrate_phase3():
    """Create new tables for Phase 3"""
    print("Starting Phase 3 migration...")
    print("=" * 60)
    
    app = create_app()
    
    with app.app_context():
        print("\n1. Creating new tables...")
        
        try:
            # Create tables
            db.create_all()
            print("✓ Tables created successfully")
            
            # Initialize default settings
            print("\n2. Initializing default system settings...")
            
            default_settings = {
                'site_name': 'KAST Web',
                'maintenance_mode': False,
                'allow_registration': False,
                'max_scan_age_days': 90,
                'max_scans_per_user': 0,
                'enable_audit_log': True,
                'session_timeout_minutes': 60
            }
            
            for key, value in default_settings.items():
                existing = SystemSettings.query.filter_by(key=key).first()
                if not existing:
                    SystemSettings.set_setting(key, value)
                    print(f"  - Set {key} = {value}")
                else:
                    print(f"  - {key} already exists, skipping")
            
            print("\n3. Verifying tables...")
            
            # Check audit_logs table
            audit_count = AuditLog.query.count()
            print(f"✓ audit_logs table exists ({audit_count} entries)")
            
            # Check system_settings table
            settings_count = SystemSettings.query.count()
            print(f"✓ system_settings table exists ({settings_count} entries)")
            
            print("\n" + "=" * 60)
            print("✅ Phase 3 migration completed successfully!")
            print("\nNew features available:")
            print("  - Admin Dashboard (/admin/dashboard)")
            print("  - System Settings (/admin/settings)")
            print("  - Audit Log (/admin/audit-log)")
            print("  - User Activity Monitoring (/admin/activity)")
            print("\nRestart the web server to access admin panel.")
            
        except Exception as e:
            print(f"\n❌ Migration failed: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    migrate_phase3()
