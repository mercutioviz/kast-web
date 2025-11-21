#!/usr/bin/env python3
"""
Import users into the kast-web database.
This script imports users from a JSON export file created by export_users.py.

Usage:
    python import_users.py [input_file] [--skip-existing|--update-existing]
    
    Default input file: users_export.json
    Default behavior: Skip existing users
    
Options:
    --skip-existing    Skip users that already exist (default)
    --update-existing  Update existing users with exported data
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Add the app to the path
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app, db
from app.models import User

def parse_datetime(dt_string):
    """Parse ISO format datetime string"""
    if not dt_string:
        return None
    try:
        return datetime.fromisoformat(dt_string)
    except:
        return None

def import_users(input_file='users_export.json', update_existing=False):
    """Import users from a JSON file"""
    
    # Read the export file
    try:
        with open(input_file, 'r') as f:
            export_data = json.load(f)
    except FileNotFoundError:
        print(f"✗ Error: File '{input_file}' not found.")
        return False
    except json.JSONDecodeError:
        print(f"✗ Error: Invalid JSON in '{input_file}'.")
        return False
    
    users_data = export_data.get('users', [])
    
    if not users_data:
        print("✗ No users found in export file.")
        return False
    
    print(f"Found {len(users_data)} users in export file")
    print(f"Export date: {export_data.get('export_date', 'Unknown')}")
    print()
    
    app = create_app()
    
    with app.app_context():
        imported = 0
        skipped = 0
        updated = 0
        errors = 0
        
        for user_data in users_data:
            username = user_data.get('username')
            email = user_data.get('email')
            
            if not username or not email:
                print(f"✗ Skipping invalid user entry (missing username or email)")
                errors += 1
                continue
            
            # Check if user already exists
            existing_user = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                if not update_existing:
                    print(f"  Skipping {username} (already exists)")
                    skipped += 1
                    continue
                else:
                    # Update existing user
                    print(f"  Updating {username}")
                    existing_user.email = email
                    existing_user.password_hash = user_data.get('password_hash')
                    existing_user.first_name = user_data.get('first_name')
                    existing_user.last_name = user_data.get('last_name')
                    existing_user.role = user_data.get('role', 'user')
                    existing_user.is_active = user_data.get('is_active', True)
                    existing_user.login_count = user_data.get('login_count', 0)
                    existing_user.failed_login_attempts = user_data.get('failed_login_attempts', 0)
                    
                    # Update datetime fields if present
                    if user_data.get('created_at'):
                        existing_user.created_at = parse_datetime(user_data['created_at'])
                    if user_data.get('last_login'):
                        existing_user.last_login = parse_datetime(user_data['last_login'])
                    if user_data.get('last_failed_login'):
                        existing_user.last_failed_login = parse_datetime(user_data['last_failed_login'])
                    
                    updated += 1
            else:
                # Create new user
                print(f"  Importing {username} ({email}) - Role: {user_data.get('role', 'user')}")
                
                new_user = User(
                    username=username,
                    email=email,
                    password_hash=user_data.get('password_hash'),
                    first_name=user_data.get('first_name'),
                    last_name=user_data.get('last_name'),
                    role=user_data.get('role', 'user'),
                    is_active=user_data.get('is_active', True),
                    login_count=user_data.get('login_count', 0),
                    failed_login_attempts=user_data.get('failed_login_attempts', 0)
                )
                
                # Set datetime fields
                if user_data.get('created_at'):
                    new_user.created_at = parse_datetime(user_data['created_at'])
                if user_data.get('last_login'):
                    new_user.last_login = parse_datetime(user_data['last_login'])
                if user_data.get('last_failed_login'):
                    new_user.last_failed_login = parse_datetime(user_data['last_failed_login'])
                
                db.session.add(new_user)
                imported += 1
        
        # Commit all changes
        try:
            db.session.commit()
            print()
            print("=" * 60)
            print("Import Summary:")
            print("=" * 60)
            print(f"  Users imported: {imported}")
            if updated > 0:
                print(f"  Users updated:  {updated}")
            if skipped > 0:
                print(f"  Users skipped:  {skipped}")
            if errors > 0:
                print(f"  Errors:         {errors}")
            print()
            print("✓ Import completed successfully!")
            return True
        except Exception as e:
            db.session.rollback()
            print()
            print(f"✗ Error during import: {str(e)}")
            return False

if __name__ == '__main__':
    input_file = 'users_export.json'
    update_existing = False
    
    # Parse command line arguments
    for arg in sys.argv[1:]:
        if arg == '--update-existing':
            update_existing = True
        elif arg == '--skip-existing':
            update_existing = False
        elif not arg.startswith('--'):
            input_file = arg
    
    print("=" * 60)
    print("KAST-WEB User Import Tool")
    print("=" * 60)
    print(f"Input file: {input_file}")
    print(f"Mode: {'Update existing users' if update_existing else 'Skip existing users'}")
    print()
    
    success = import_users(input_file, update_existing)
    
    if not success:
        sys.exit(1)
