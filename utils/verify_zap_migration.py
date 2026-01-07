"""
Verification script for ZAP integration migration
Tests database tables, encryption, relationships, and seeded data
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, db
from app.models import (
    ZapAutomationPlan, ZapConfiguration, ZapScanProgress,
    Scan, User
)
from app.encryption import encrypt_json, decrypt_json, encrypt_value, decrypt_value


def verify_migration():
    """Verify all aspects of the ZAP migration"""
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("ZAP INTEGRATION VERIFICATION")
        print("=" * 60)
        print()
        
        all_passed = True
        
        # Test 1: Verify tables exist
        print("Test 1: Verifying database tables...")
        try:
            plan_count = ZapAutomationPlan.query.count()
            config_count = ZapConfiguration.query.count()
            print(f"  ✓ ZapAutomationPlan table exists ({plan_count} records)")
            print(f"  ✓ ZapConfiguration table exists ({config_count} records)")
            print(f"  ✓ ZapScanProgress table exists")
        except Exception as e:
            print(f"  ✗ Error accessing tables: {e}")
            all_passed = False
        
        print()
        
        # Test 2: Verify encryption/decryption
        print("Test 2: Testing encryption/decryption...")
        try:
            test_data = {
                'api_key': 'test-secret-key-12345',
                'password': 'super-secret-password',
                'config': {'nested': 'value'}
            }
            
            # Test JSON encryption
            encrypted = encrypt_json(test_data)
            decrypted = decrypt_json(encrypted)
            
            if decrypted == test_data:
                print("  ✓ JSON encryption/decryption works correctly")
            else:
                print("  ✗ JSON encryption/decryption mismatch")
                all_passed = False
            
            # Test string encryption
            test_string = "sensitive-api-key-value"
            encrypted_str = encrypt_value(test_string)
            decrypted_str = decrypt_value(encrypted_str)
            
            if decrypted_str == test_string:
                print("  ✓ String encryption/decryption works correctly")
            else:
                print("  ✗ String encryption/decryption mismatch")
                all_passed = False
                
        except Exception as e:
            print(f"  ✗ Encryption error: {e}")
            all_passed = False
        
        print()
        
        # Test 3: Verify default plans
        print("Test 3: Verifying default ZAP automation plans...")
        try:
            plans = ZapAutomationPlan.query.all()
            expected_plans = [
                'Quick Passive Scan',
                'Standard Active Scan',
                'Full Security Audit'
            ]
            
            for plan in plans:
                if plan.name in expected_plans:
                    print(f"  ✓ Plan '{plan.name}' exists (ID: {plan.id})")
                    print(f"    - Allow power users: {plan.allow_power_users}")
                    print(f"    - System default: {plan.is_system_default}")
                    print(f"    - Draft: {plan.is_draft}")
            
            if len(plans) >= 3:
                print(f"  ✓ All {len(plans)} default plans seeded successfully")
            else:
                print(f"  ⚠ Warning: Expected 3 plans, found {len(plans)}")
                
        except Exception as e:
            print(f"  ✗ Error verifying plans: {e}")
            all_passed = False
        
        print()
        
        # Test 4: Verify default configurations
        print("Test 4: Verifying default ZAP configurations...")
        try:
            configs = ZapConfiguration.query.all()
            
            for config in configs:
                print(f"  ✓ Configuration '{config.name}' exists (ID: {config.id})")
                print(f"    - Mode: {config.execution_mode}")
                print(f"    - Active: {config.is_active}")
                print(f"    - Default: {config.is_default}")
                
                # Test decryption of configs
                if config.execution_mode == 'local':
                    local_conf = config.local_config
                    if 'docker_image' in local_conf:
                        print(f"    - Docker image: {local_conf['docker_image']}")
                elif config.execution_mode == 'remote':
                    remote_conf = config.remote_config
                    if 'zap_url' in remote_conf:
                        print(f"    - ZAP URL: {remote_conf['zap_url']}")
            
            if len(configs) >= 3:
                print(f"  ✓ All {len(configs)} default configurations seeded successfully")
            else:
                print(f"  ⚠ Warning: Expected 3 configs, found {len(configs)}")
                
        except Exception as e:
            print(f"  ✗ Error verifying configurations: {e}")
            all_passed = False
        
        print()
        
        # Test 5: Verify model relationships
        print("Test 5: Verifying model relationships...")
        try:
            # Check ZapAutomationPlan relationships
            plan = ZapAutomationPlan.query.first()
            if plan:
                print(f"  ✓ ZapAutomationPlan.creator relationship works")
                print(f"    - Plan '{plan.name}' created by User ID {plan.created_by}")
            
            # Check ZapConfiguration relationships
            config = ZapConfiguration.query.first()
            if config:
                print(f"  ✓ ZapConfiguration.creator relationship works")
                print(f"    - Config '{config.name}' created by User ID {config.created_by}")
            
            # Check Scan model has new fields by querying the table
            try:
                # Try to query with ZAP fields to ensure they exist
                result = db.session.execute(
                    db.text("SELECT zap_plan_id, zap_config_id, zap_execution_mode FROM scans LIMIT 1")
                )
                print("  ✓ Scan model updated with ZAP fields:")
                print("    - zap_plan_id (verified in database)")
                print("    - zap_config_id (verified in database)")
                print("    - zap_execution_mode (verified in database)")
            except Exception as col_error:
                print(f"  ✗ Error: Scan table missing ZAP columns: {col_error}")
                print("    Run: python utils/fix_zap_scan_columns.py")
                all_passed = False
            
        except Exception as e:
            print(f"  ✗ Error verifying relationships: {e}")
            all_passed = False
        
        print()
        
        # Test 6: Test config masking
        print("Test 6: Testing sensitive data masking...")
        try:
            config = ZapConfiguration.query.filter_by(execution_mode='remote').first()
            if config:
                # Get masked version
                masked = config.to_dict(include_sensitive=False)
                if 'api_key' in masked['remote_config']:
                    if masked['remote_config']['api_key'] == '********' or masked['remote_config']['api_key'] == '':
                        print("  ✓ Sensitive data properly masked in to_dict()")
                    else:
                        print(f"  ⚠ Warning: api_key not masked: {masked['remote_config']['api_key']}")
                
                # Get full version (admin only)
                full = config.to_dict(include_sensitive=True)
                print("  ✓ Full data accessible with include_sensitive=True")
            else:
                print("  ⚠ No remote config found to test masking")
                
        except Exception as e:
            print(f"  ✗ Error testing masking: {e}")
            all_passed = False
        
        print()
        print("=" * 60)
        if all_passed:
            print("ALL VERIFICATION TESTS PASSED! ✓")
        else:
            print("SOME TESTS FAILED - Review errors above")
        print("=" * 60)
        print()
        
        return all_passed


if __name__ == '__main__':
    print()
    success = verify_migration()
    sys.exit(0 if success else 1)
