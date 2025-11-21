#!/usr/bin/env python3
"""
Migration script to add power_user role support
This script doesn't modify existing users, but the new role will be available for new users
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User

def migrate():
    """Add power_user role support to the system"""
    app = create_app()
    
    with app.app_context():
        print("=== Power User Role Migration ===")
        print("This migration adds support for the 'power_user' role")
        print("Power users can run both active and passive scans")
        print()
        
        # Check current users and their roles
        users = User.query.all()
        print(f"Current users in database: {len(users)}")
        
        role_counts = {}
        for user in users:
            role_counts[user.role] = role_counts.get(user.role, 0) + 1
        
        print("\nRole distribution:")
        for role, count in sorted(role_counts.items()):
            print(f"  - {role}: {count} user(s)")
        
        print("\n" + "="*50)
        print("Migration Notes:")
        print("- The 'power_user' role is now available for new users")
        print("- Existing users are not modified by this migration")
        print("- To upgrade a user to power_user:")
        print("  1. Log in as admin")
        print("  2. Go to Users management page")
        print("  3. Edit the user and change their role to 'Power User'")
        print()
        print("- Admin users can already run active scans")
        print("- Standard 'user' role can only run passive scans")
        print("- 'power_user' role can run both active and passive scans")
        print("="*50)
        print("\nMigration completed successfully!")
        print("No database changes were needed - role support is already in place.")

if __name__ == '__main__':
    migrate()
