#!/usr/bin/env python3
"""
Migration script for Phase 4: Sharing & Collaboration

This script creates the scan_shares table for sharing functionality.
"""

import sys
from app import create_app, db
from app.models import ScanShare

def migrate_phase4():
    """Create scan_shares table"""
    app = create_app()
    
    with app.app_context():
        print("Phase 4 Migration: Creating scan_shares table")
        print("=" * 60)
        
        try:
            # Create scan_shares table
            print("\n1. Creating scan_shares table...")
            db.create_all()
            print("   ✓ scan_shares table created successfully")
            
            # Verify table exists
            print("\n2. Verifying table structure...")
            inspector = db.inspect(db.engine)
            if 'scan_shares' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('scan_shares')]
                print(f"   ✓ Table exists with columns: {', '.join(columns)}")
            else:
                print("   ✗ Table creation failed")
                return False
            
            # Check indexes
            print("\n3. Verifying indexes...")
            indexes = inspector.get_indexes('scan_shares')
            print(f"   ✓ Found {len(indexes)} indexes")
            for idx in indexes:
                print(f"     - {idx['name']}: {idx['column_names']}")
            
            print("\n" + "=" * 60)
            print("✓ Phase 4 migration completed successfully!")
            print("\nNew features available:")
            print("  • Share scans with specific users")
            print("  • Generate public sharing links")
            print("  • Set view/edit permissions")
            print("  • Configure expiration dates")
            print("  • Transfer scan ownership")
            print("\nNext steps:")
            print("  1. Restart Flask application")
            print("  2. Test sharing functionality")
            print("  3. Review docs/SHARING_PHASE4.md for details")
            
            return True
            
        except Exception as e:
            print(f"\n✗ Migration failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = migrate_phase4()
    sys.exit(0 if success else 1)
