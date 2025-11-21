#!/usr/bin/env python3
"""
Verification script to check if --format both is working
"""

import sys
import os
from pathlib import Path
from app import create_app, db
from app.models import Scan

def verify_format_both():
    """Check recent scans for both HTML and JSON output"""
    
    app = create_app()
    
    with app.app_context():
        # Get most recent completed scan
        recent_scan = Scan.query.filter_by(status='completed').order_by(Scan.created_at.desc()).first()
        
        if not recent_scan:
            print("❌ No completed scans found in database")
            return False
        
        print(f"\n📊 Checking most recent scan:")
        print(f"   ID: {recent_scan.id}")
        print(f"   Target: {recent_scan.target}")
        print(f"   Created: {recent_scan.created_at}")
        print(f"   Output Dir: {recent_scan.output_dir}")
        
        if not recent_scan.output_dir:
            print("❌ No output directory recorded")
            return False
        
        output_path = Path(recent_scan.output_dir)
        
        if not output_path.exists():
            print(f"❌ Output directory does not exist: {output_path}")
            return False
        
        print(f"\n📁 Checking directory: {output_path}")
        
        # Check for HTML report
        html_report = output_path / "report.html"
        has_html = html_report.exists()
        
        # Check for JSON files
        json_files = list(output_path.glob("*_processed.json"))
        has_json = len(json_files) > 0
        
        print(f"\n✓ HTML Report: {'✅ FOUND' if has_html else '❌ MISSING'}")
        if has_html:
            print(f"  - {html_report}")
            print(f"  - Size: {html_report.stat().st_size:,} bytes")
        
        print(f"\n✓ JSON Files: {'✅ FOUND' if has_json else '❌ MISSING'}")
        if has_json:
            for json_file in json_files:
                print(f"  - {json_file.name} ({json_file.stat().st_size:,} bytes)")
        else:
            print(f"  - No *_processed.json files found")
        
        print("\n" + "="*60)
        
        if has_html and has_json:
            print("✅ SUCCESS: Both HTML and JSON formats are present!")
            print("   The --format both argument is working correctly.")
            return True
        elif has_html and not has_json:
            print("⚠️  WARNING: Only HTML found, JSON missing")
            print("   --format both may not be working correctly")
            return False
        elif has_json and not has_html:
            print("⚠️  WARNING: Only JSON found, HTML missing")
            print("   --format both may not be working correctly")
            return False
        else:
            print("❌ ERROR: Neither HTML nor JSON found")
            print("   Check if scan actually completed successfully")
            return False

if __name__ == '__main__':
    try:
        success = verify_format_both()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
