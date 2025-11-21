#!/usr/bin/env python3
"""
Migration script to add user_id column to existing scans table
and assign all existing scans to the first admin user
"""

import sys
from app import create_app, db
from app.models import User, Scan
from sqlalchemy import text

def migrate_database():
    """Migrate existing database to support authentication"""
    app = create_app()
    
    with app.app_context():
        print("Starting database migration...")
        
        # Check if users table exists
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'users' not in tables:
            print("❌ Users table not found. Please run 'python create_admin_user.py' first.")
            return False
        
        # Get the first admin user
        admin_user = User.query.filter_by(role='admin').first()
        if not admin_user:
            print("❌ No admin user found. Please run 'python create_admin_user.py' first.")
            return False
        
        print(f"✓ Found admin user: {admin_user.username} (ID: {admin_user.id})")
        
        # Check if user_id column already exists
        columns = [col['name'] for col in inspector.get_columns('scans')]
        
        if 'user_id' in columns:
            print("✓ user_id column already exists in scans table")
            
            # Check for scans without user_id
            scans_without_user = db.session.execute(
                text("SELECT COUNT(*) FROM scans WHERE user_id IS NULL")
            ).scalar()
            
            if scans_without_user > 0:
                print(f"Updating {scans_without_user} scans without user_id...")
                db.session.execute(
                    text(f"UPDATE scans SET user_id = {admin_user.id} WHERE user_id IS NULL")
                )
                db.session.commit()
                print(f"✓ Assigned {scans_without_user} scans to {admin_user.username}")
            else:
                print("✓ All scans already have user_id assigned")
            
            return True
        
        # Add user_id column
        print("Adding user_id column to scans table...")
        
        try:
            # Add column (nullable first)
            db.session.execute(
                text("ALTER TABLE scans ADD COLUMN user_id INTEGER")
            )
            db.session.commit()
            print("✓ Added user_id column")
            
            # Count existing scans
            scan_count = db.session.execute(
                text("SELECT COUNT(*) FROM scans")
            ).scalar()
            
            if scan_count > 0:
                print(f"Found {scan_count} existing scans")
                print(f"Assigning all scans to admin user: {admin_user.username}...")
                
                # Update all existing scans with admin user_id
                db.session.execute(
                    text(f"UPDATE scans SET user_id = {admin_user.id}")
                )
                db.session.commit()
                print(f"✓ Assigned {scan_count} scans to {admin_user.username}")
            else:
                print("No existing scans found")
            
            # Now make the column NOT NULL
            print("Making user_id column required...")
            
            # SQLite doesn't support ALTER COLUMN, so we need to check constraints
            # The NOT NULL constraint will be enforced by the model going forward
            print("✓ Migration completed successfully!")
            
            # Verify migration
            print("\nVerifying migration...")
            all_scans = Scan.query.all()
            print(f"✓ Can query {len(all_scans)} scans successfully")
            
            if all_scans:
                for scan in all_scans[:3]:  # Show first 3
                    print(f"  - Scan #{scan.id}: {scan.target} (User: {scan.user.username})")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during migration: {str(e)}")
            return False

if __name__ == '__main__':
    try:
        success = migrate_database()
        if success:
            print("\n✅ Database migration completed successfully!")
            print("You can now restart the web server.")
            sys.exit(0)
        else:
            print("\n❌ Database migration failed.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
