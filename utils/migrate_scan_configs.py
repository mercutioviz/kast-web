#!/usr/bin/env python3
"""
Migration script to add scan configuration profile support to KAST-Web

This migration:
1. Creates the scan_config_profiles table
2. Adds config_profile_id and config_overrides columns to scans table
3. Creates three preset configuration profiles (Standard, Stealth, Aggressive)

Run this script after backing up your database.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, db
from app.models import User
from sqlalchemy import text

# Preset configuration templates
PRESET_CONFIGS = {
    'standard': {
        'name': 'Standard',
        'description': 'Balanced configuration suitable for most scanning scenarios. Good default for beginners.',
        'allow_standard_users': True,
        'is_system_default': True,
        'config_yaml': """# Standard Configuration
# Balanced settings for general-purpose scanning

global:
  timeout: 300
  retry_count: 2

plugins:
  mozilla_observatory:
    timeout: 300
    retry_attempts: 1
    format: json

  subfinder:
    rate_limit: 150
    timeout: 30
    max_time: 10
    concurrent_goroutines: 10
    collect_sources: true
    active_only: false

  script_detection:
    request_timeout: 30
    verify_ssl: true
    follow_redirects: true
    max_redirects: 10

  wafw00f:
    find_all: true
    verbosity: 3
    follow_redirects: true
    timeout: 30

  katana:
    concurrency: 10
    rate_limit: 150
    delay: 0
    timeout: 10
    retry: 1
    field_scope: rdn
    headless: false
    xhr_extraction: false
    omit_body: true

  ftap:
    concurrency: 10
    rate_limit: 100
    delay: 0
    timeout: 10
    retry: 1
"""
    },
    'stealth': {
        'name': 'Stealth',
        'description': 'Low-profile configuration with reduced request rates and increased delays. Ideal for avoiding detection or when scanning sensitive targets.',
        'allow_standard_users': True,
        'is_system_default': False,
        'config_yaml': """# Stealth Configuration
# Slow, careful scanning to minimize detection risk

global:
  timeout: 600
  retry_count: 1

plugins:
  mozilla_observatory:
    timeout: 300
    retry_attempts: 1
    format: json

  subfinder:
    rate_limit: 10
    timeout: 60
    max_time: 20
    concurrent_goroutines: 3
    collect_sources: true
    active_only: false

  script_detection:
    request_timeout: 45
    verify_ssl: true
    follow_redirects: true
    max_redirects: 10

  wafw00f:
    find_all: true
    verbosity: 1
    follow_redirects: true
    timeout: 45

  katana:
    concurrency: 3
    rate_limit: 5
    delay: 2
    timeout: 30
    retry: 1
    field_scope: rdn
    headless: false
    xhr_extraction: false
    omit_body: true

  ftap:
    concurrency: 3
    rate_limit: 5
    delay: 2
    timeout: 30
    retry: 1
"""
    },
    'aggressive': {
        'name': 'Aggressive',
        'description': 'High-speed configuration with maximum concurrency and request rates. Best for internal testing environments or when speed is prioritized. NOT recommended for standard users or production targets.',
        'allow_standard_users': False,
        'is_system_default': False,
        'config_yaml': """# Aggressive Configuration
# Fast, high-concurrency scanning for internal testing

global:
  timeout: 180
  retry_count: 3

plugins:
  mozilla_observatory:
    timeout: 180
    retry_attempts: 2
    format: json

  subfinder:
    rate_limit: 500
    timeout: 20
    max_time: 5
    concurrent_goroutines: 50
    use_all_sources: true
    collect_sources: true
    active_only: false

  script_detection:
    request_timeout: 20
    verify_ssl: true
    follow_redirects: true
    max_redirects: 15

  wafw00f:
    find_all: true
    verbosity: 3
    follow_redirects: true
    timeout: 20

  katana:
    concurrency: 20
    rate_limit: 500
    delay: 0
    timeout: 10
    retry: 2
    field_scope: rdn
    headless: false
    xhr_extraction: false
    omit_body: true

  ftap:
    concurrency: 20
    rate_limit: 300
    delay: 0
    timeout: 10
    retry: 2
"""
    }
}


def run_migration():
    """Execute the migration"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("KAST-Web Scan Configuration Profile Migration")
        print("=" * 60)
        print()
        
        # Check if tables already exist
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'scan_config_profiles' in existing_tables:
            print("⚠️  WARNING: scan_config_profiles table already exists!")
            response = input("Do you want to continue anyway? (yes/no): ")
            if response.lower() != 'yes':
                print("Migration cancelled.")
                return
        
        print("Step 1: Creating scan_config_profiles table...")
        try:
            # Create the scan_config_profiles table
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS scan_config_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT,
                    config_yaml TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    allow_standard_users BOOLEAN DEFAULT 0,
                    is_system_default BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
            """))
            db.session.commit()
            print("✓ scan_config_profiles table created")
        except Exception as e:
            print(f"✗ Error creating table: {e}")
            db.session.rollback()
            return
        
        print("\nStep 2: Adding new columns to scans table...")
        try:
            # Check if columns already exist
            scans_columns = [col['name'] for col in inspector.get_columns('scans')]
            
            if 'config_profile_id' not in scans_columns:
                db.session.execute(text("""
                    ALTER TABLE scans 
                    ADD COLUMN config_profile_id INTEGER 
                    REFERENCES scan_config_profiles(id)
                """))
                print("✓ Added config_profile_id column to scans table")
            else:
                print("⚠️  config_profile_id column already exists")
            
            if 'config_overrides' not in scans_columns:
                db.session.execute(text("""
                    ALTER TABLE scans 
                    ADD COLUMN config_overrides TEXT
                """))
                print("✓ Added config_overrides column to scans table")
            else:
                print("⚠️  config_overrides column already exists")
            
            db.session.commit()
        except Exception as e:
            print(f"✗ Error adding columns: {e}")
            db.session.rollback()
            return
        
        print("\nStep 3: Creating preset configuration profiles...")
        try:
            # Get the first admin user to assign as creator
            admin_user = User.query.filter_by(role='admin').first()
            if not admin_user:
                print("✗ No admin user found! Please create an admin user first.")
                return
            
            profiles_created = 0
            for preset_key, preset_data in PRESET_CONFIGS.items():
                # Check if profile already exists
                existing = db.session.execute(
                    text("SELECT id FROM scan_config_profiles WHERE name = :name"),
                    {'name': preset_data['name']}
                ).fetchone()
                
                if existing:
                    print(f"⚠️  Profile '{preset_data['name']}' already exists, skipping...")
                    continue
                
                # Insert the preset profile
                db.session.execute(text("""
                    INSERT INTO scan_config_profiles 
                    (name, description, config_yaml, created_by, allow_standard_users, is_system_default, created_at)
                    VALUES (:name, :description, :config_yaml, :created_by, :allow_standard_users, :is_system_default, CURRENT_TIMESTAMP)
                """), {
                    'name': preset_data['name'],
                    'description': preset_data['description'],
                    'config_yaml': preset_data['config_yaml'],
                    'created_by': admin_user.id,
                    'allow_standard_users': 1 if preset_data['allow_standard_users'] else 0,
                    'is_system_default': 1 if preset_data['is_system_default'] else 0
                })
                profiles_created += 1
                print(f"✓ Created '{preset_data['name']}' profile")
            
            db.session.commit()
            print(f"\n✓ Created {profiles_created} preset profiles")
        except Exception as e:
            print(f"✗ Error creating preset profiles: {e}")
            db.session.rollback()
            return
        
        print("\n" + "=" * 60)
        print("Migration completed successfully! ✓")
        print("=" * 60)
        print("\nPreset Profiles Created:")
        print("  • Standard (system default, available to all users)")
        print("  • Stealth (available to all users)")
        print("  • Aggressive (power users and admins only)")
        print("\nNext steps:")
        print("  1. Restart the application")
        print("  2. Navigate to the config management page")
        print("  3. Review and customize the preset profiles as needed")
        print()


def rollback_migration():
    """Rollback the migration"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("KAST-Web Scan Configuration Profile Migration ROLLBACK")
        print("=" * 60)
        print()
        print("⚠️  WARNING: This will delete all scan configuration profiles!")
        print("⚠️  Scans will lose their config_profile_id references!")
        print()
        response = input("Are you sure you want to rollback? (yes/no): ")
        
        if response.lower() != 'yes':
            print("Rollback cancelled.")
            return
        
        print("\nStep 1: Removing columns from scans table...")
        try:
            # SQLite doesn't support DROP COLUMN directly
            # We need to check if we can work around this or document manual steps
            print("⚠️  Note: SQLite doesn't support DROP COLUMN")
            print("   The config_profile_id and config_overrides columns will remain")
            print("   but will be unused after dropping the scan_config_profiles table")
        except Exception as e:
            print(f"Note: {e}")
        
        print("\nStep 2: Dropping scan_config_profiles table...")
        try:
            db.session.execute(text("DROP TABLE IF EXISTS scan_config_profiles"))
            db.session.commit()
            print("✓ scan_config_profiles table dropped")
        except Exception as e:
            print(f"✗ Error dropping table: {e}")
            db.session.rollback()
            return
        
        print("\n" + "=" * 60)
        print("Rollback completed! ✓")
        print("=" * 60)
        print()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback_migration()
    else:
        run_migration()
