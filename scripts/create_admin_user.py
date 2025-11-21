#!/usr/bin/env python3
"""
Script to create the first admin user for KAST Web
This should be run after installing the new authentication dependencies
"""

import sys
from getpass import getpass
from app import create_app, db
from app.models import User

def create_admin():
    """Create the first admin user"""
    app = create_app()
    
    with app.app_context():
        # Create all database tables
        print("Creating database tables...")
        db.create_all()
        print("✓ Database tables created successfully")
        
        # Check if any users already exist
        existing_users = User.query.count()
        if existing_users > 0:
            print(f"\n⚠ Warning: {existing_users} user(s) already exist in the database.")
            response = input("Do you want to create another admin user? (y/N): ")
            if response.lower() != 'y':
                print("Aborted.")
                return
        
        print("\n=== Create Admin User ===")
        print("Please provide the following information:\n")
        
        # Get user input
        while True:
            username = input("Username (3-80 characters): ").strip()
            if 3 <= len(username) <= 80:
                # Check if username exists
                if User.query.filter_by(username=username).first():
                    print("❌ Username already exists. Please choose another.")
                    continue
                break
            print("❌ Username must be between 3 and 80 characters.")
        
        while True:
            email = input("Email address: ").strip()
            if '@' in email and '.' in email:
                # Check if email exists
                if User.query.filter_by(email=email).first():
                    print("❌ Email already exists. Please use another.")
                    continue
                break
            print("❌ Please enter a valid email address.")
        
        first_name = input("First name (optional): ").strip()
        last_name = input("Last name (optional): ").strip()
        
        while True:
            password = getpass("Password (min 8 characters): ")
            if len(password) >= 8:
                password_confirm = getpass("Confirm password: ")
                if password == password_confirm:
                    break
                print("❌ Passwords do not match. Please try again.")
            else:
                print("❌ Password must be at least 8 characters long.")
        
        # Create the admin user
        print("\nCreating admin user...")
        admin_user = User(
            username=username,
            email=email,
            first_name=first_name if first_name else None,
            last_name=last_name if last_name else None,
            role='admin',
            is_active=True
        )
        admin_user.set_password(password)
        
        db.session.add(admin_user)
        db.session.commit()
        
        print("\n✓ Admin user created successfully!")
        print(f"\n📋 User Details:")
        print(f"   Username: {admin_user.username}")
        print(f"   Email: {admin_user.email}")
        print(f"   Role: {admin_user.role}")
        print(f"\nYou can now log in at: http://localhost:5000/auth/login")

if __name__ == '__main__':
    try:
        create_admin()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)
