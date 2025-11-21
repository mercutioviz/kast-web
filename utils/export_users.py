#!/usr/bin/env python3
"""
Export users from the current kast-web database.
This script exports all users without their scans to a JSON file.

Usage:
    python export_users.py [output_file]
    
    Default output file: users_export.json
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Add the app to the path
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app, db
from app.models import User

def export_users(output_file='users_export.json'):
    """Export all users to a JSON file"""
    
    app = create_app()
    
    with app.app_context():
        # Get all users
        users = User.query.all()
        
        if not users:
            print("No users found in database.")
            return False
        
        # Convert users to dictionary format
        users_data = []
        for user in users:
            user_dict = {
                'username': user.username,
                'email': user.email,
                'password_hash': user.password_hash,  # Keep the hash
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'login_count': user.login_count,
                'failed_login_attempts': user.failed_login_attempts,
                'last_failed_login': user.last_failed_login.isoformat() if user.last_failed_login else None
            }
            users_data.append(user_dict)
        
        # Export metadata
        export_data = {
            'export_date': datetime.utcnow().isoformat(),
            'user_count': len(users_data),
            'users': users_data
        }
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"✓ Successfully exported {len(users_data)} users to {output_file}")
        print(f"\nExported users:")
        for user in users:
            print(f"  - {user.username} ({user.email}) - Role: {user.role}")
        
        return True

if __name__ == '__main__':
    output_file = sys.argv[1] if len(sys.argv) > 1 else 'users_export.json'
    
    print("=" * 60)
    print("KAST-WEB User Export Tool")
    print("=" * 60)
    print(f"Output file: {output_file}")
    print()
    
    success = export_users(output_file)
    
    if success:
        print()
        print("=" * 60)
        print("Export complete!")
        print("=" * 60)
        print(f"\nTo import on the new server, copy '{output_file}' and run:")
        print(f"  python import_users.py {output_file}")
    else:
        sys.exit(1)
