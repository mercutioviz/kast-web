#!/opt/kast-web/venv/bin/python3
"""
Script to reset a user's password from the command line
Usage: 
  As www-data user: sudo -u www-data /opt/kast-web/scripts/reset_password.py
  Or with wrapper: sudo /opt/kast-web/scripts/reset_password_wrapper.sh
"""

import sys
import os
from getpass import getpass
from datetime import datetime

# Add parent directory to path so we can import app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env before importing the app so DATABASE_URL and other config resolve
# the same way they do under run.py / celery_worker.py. Without this, the app
# falls back to a relative sqlite path and errors with "unable to open database file".
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app, db
from app.models import User, AuditLog

def reset_password():
    """Reset a user's password"""
    app = create_app()
    
    with app.app_context():
        print("\n=== KAST-Web Password Reset ===")
        print("This script allows you to reset a user's password.\n")
        
        # Get user identification
        print("Enter the username or email of the user whose password you want to reset:")
        identifier = input("Username or Email: ").strip()
        
        if not identifier:
            print("❌ No username or email provided.")
            return
        
        # Look up user by username or email
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()
        
        if not user:
            print(f"❌ No user found with username or email: {identifier}")
            return
        
        # Display user information
        print(f"\n📋 User Found:")
        print(f"   ID: {user.id}")
        print(f"   Username: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   Role: {user.role}")
        print(f"   Active: {user.is_active}")
        
        if not user.is_active:
            print("\n⚠ Warning: This user account is currently inactive.")
        
        # Confirm action
        print("\n⚠ You are about to reset the password for this user.")
        confirm = input("Do you want to proceed? (yes/no): ").strip().lower()
        
        if confirm not in ['yes', 'y']:
            print("Aborted.")
            return
        
        # Get new password
        print("\n=== New Password ===")
        while True:
            password = getpass("Enter new password (min 8 characters): ")
            if len(password) >= 8:
                password_confirm = getpass("Confirm new password: ")
                if password == password_confirm:
                    break
                print("❌ Passwords do not match. Please try again.")
            else:
                print("❌ Password must be at least 8 characters long.")
        
        # Reset password
        try:
            print("\nResetting password...")
            user.set_password(password)
            
            # Reset failed login attempts if any
            if user.failed_login_attempts > 0:
                user.failed_login_attempts = 0
                user.last_failed_login = None
                print("   ↳ Cleared failed login attempts")
            
            # Create audit log entry
            # Note: Using user.id as the actor since this is an admin action on behalf of the user
            AuditLog.log(
                user_id=user.id,
                action='password_reset_cli',
                resource_type='user',
                resource_id=user.id,
                details=f'Password reset via CLI script for user {user.username}',
                ip_address='127.0.0.1',
                user_agent='CLI Script'
            )
            
            db.session.commit()
            
            print("\n✓ Password reset successfully!")
            print(f"\n📋 Summary:")
            print(f"   User: {user.username}")
            print(f"   Email: {user.email}")
            print(f"   Reset Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"\nThe user can now log in with the new password.")
            
            # Additional info for inactive accounts
            if not user.is_active:
                print(f"\n⚠ Note: This account is currently inactive.")
                print(f"   The user will need to have their account activated before they can log in.")
                print(f"   You can activate it via the admin panel or database.")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error resetting password: {str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    try:
        reset_password()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)
