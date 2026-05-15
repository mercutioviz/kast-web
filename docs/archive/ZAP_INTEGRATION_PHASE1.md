# ZAP Integration - Phase 1: Database Schema & Models

**Status:** ✅ COMPLETED  
**Date:** January 7, 2026  
**Version:** 1.0

## Overview

Phase 1 establishes the foundational database schema and models for ZAP (OWASP Zed Attack Proxy) integration into KAST-Web. This phase includes encryption utilities, three new database models, and comprehensive seed data.

## Components Implemented

### 1. Encryption Module (`app/encryption.py`)

**Purpose:** Secure storage of sensitive ZAP configuration data (API keys, credentials, etc.)

**Functions:**
- `encrypt_value(value)` - Encrypt a string value using Fernet
- `decrypt_value(encrypted_value)` - Decrypt a string value
- `encrypt_json(data)` - Encrypt a dictionary/object as JSON
- `decrypt_json(encrypted_json)` - Decrypt and parse JSON back to dictionary

**Key Features:**
- Uses Flask `SECRET_KEY` for encryption key derivation (SHA-256 hash)
- Fernet symmetric encryption (cryptography library)
- JSON serialization for complex data structures
- Error handling with fallback values

**Security:**
- Encryption key derived from Flask SECRET_KEY
- All sensitive configuration data encrypted at rest
- Automatic encryption/decryption via model properties

### 2. Database Models

#### ZapAutomationPlan Model

**Purpose:** Store ZAP Automation Framework YAML plans

**Fields:**
- `id` - Primary key
- `name` - Unique plan name (indexed)
- `description` - Plan description
- `plan_yaml` - Full YAML content (TEXT)
- `created_by` - Foreign key to User
- `is_system_default` - Mark as system default plan
- `allow_power_users` - Allow power users to use this plan
- `is_draft` - Draft status (power user submissions)
- `approved_by` - Admin who approved draft (FK to User)
- `approved_at` - Approval timestamp
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp
- `last_used_at` - Last usage timestamp
- `usage_count` - Usage counter

**Methods:**
- `can_be_used_by(user)` - Check if user can use this plan
- `to_dict()` - Convert to dictionary

**Default Plans Seeded:**
1. **Quick Passive Scan** (Default)
   - Fast passive scan with spider only
   - Ideal for development environments
   - 5-minute max duration
   - Power users allowed

2. **Standard Active Scan**
   - Comprehensive active scan with moderate settings
   - Recommended for staging environments
   - 10-20 minute duration
   - Includes AJAX spider
   - Power users allowed

3. **Full Security Audit** (Admin Only)
   - Comprehensive security audit with aggressive settings
   - Use in pre-production only
   - 60-minute max duration
   - Extensive spidering and scanning
   - Admin approval required

#### ZapConfiguration Model

**Purpose:** Store ZAP execution environment configurations

**Fields:**
- `id` - Primary key
- `name` - Unique configuration name (indexed)
- `description` - Configuration description
- `execution_mode` - Mode: 'local', 'remote', 'cloud', 'auto'
- `local_config_encrypted` - Encrypted JSON for Docker settings
- `remote_config_encrypted` - Encrypted JSON for remote URL/API key
- `cloud_config_encrypted` - Encrypted JSON for cloud provider
- `is_active` - Active status
- `is_default` - Default configuration flag
- `created_by` - Foreign key to User
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp
- `last_used_at` - Last usage timestamp

**Properties (with encryption):**
- `local_config` - Get/set decrypted local configuration
- `remote_config` - Get/set decrypted remote configuration
- `cloud_config` - Get/set decrypted cloud configuration

**Methods:**
- `to_dict(include_sensitive=False)` - Convert to dict, optionally mask sensitive data
- `_mask_config(config)` - Static method to mask sensitive keys

**Default Configurations Seeded:**
1. **Local Docker (Default)**
   - Run ZAP in local Docker container
   - Image: ghcr.io/zaproxy/zaproxy:stable
   - Port: 8080
   - Auto-start and resource limits configured

2. **Remote ZAP Instance**
   - Connect to existing remote ZAP instance
   - Configurable URL and API key
   - Timeout and retry settings
   - SSL verification option

3. **AWS Cloud (Template)**
   - Template for running ZAP in AWS
   - EC2 instance configuration
   - Requires admin setup
   - Auto-terminate after scan

#### ZapScanProgress Model

**Purpose:** Track real-time ZAP scan progress and metrics

**Fields:**
- `id` - Primary key
- `scan_id` - Foreign key to Scan (unique, one-to-one)
- `plan_id` - ZAP plan identifier
- `status` - Status: 'pending', 'running', 'completed', 'failed'
- `spider_percent` - Spider progress (0-100)
- `active_scan_percent` - Active scan progress (0-100)
- `passive_scan_queue` - Passive scan queue size
- `total_alerts` - Total alert count
- `high_alerts` - High-risk alerts
- `medium_alerts` - Medium-risk alerts
- `low_alerts` - Low-risk alerts
- `informational_alerts` - Informational alerts
- `job_updates` - JSON array of job status messages
- `warnings` - JSON array of warnings
- `errors` - JSON array of errors
- `started_at` - Scan start time
- `last_updated` - Last progress update
- `completed_at` - Scan completion time
- `raw_snapshot` - Full JSON snapshot for debugging

**Methods:**
- `to_dict()` - Convert to dictionary
- `update_from_snapshot(scan_id, snapshot_data)` - Static method to update from JSON snapshot

**Relationship:**
- One-to-one with Scan model (backref: `scan.zap_progress`)

### 3. Scan Model Updates

**New Fields Added:**
- `zap_plan_id` - Foreign key to ZapAutomationPlan
- `zap_config_id` - Foreign key to ZapConfiguration
- `zap_execution_mode` - Track which mode was actually used

**New Relationships:**
- `zap_plan` - Relationship to ZapAutomationPlan
- `zap_config` - Relationship to ZapConfiguration
- `zap_progress` - Backref from ZapScanProgress (one-to-one)

### 4. Migration Script (`utils/migrate_zap_feature.py`)

**Functions:**
- `migrate()` - Main migration function
- `seed_default_plans()` - Create 3 default automation plans
- `seed_default_configs()` - Create 3 default configurations

**Features:**
- Creates all new tables via `db.create_all()`
- Seeds default data automatically
- Checks for existing records (idempotent)
- Creates admin user if none exists
- Comprehensive error handling and reporting

**Usage:**
```bash
python utils/migrate_zap_feature.py
```

### 5. Verification Script (`utils/verify_zap_migration.py`)

**Tests Performed:**
1. Database table creation verification
2. Encryption/decryption functionality
3. Default plan seeding verification
4. Default configuration seeding verification
5. Model relationship verification
6. Sensitive data masking verification

**Usage:**
```bash
python utils/verify_zap_migration.py
```

## Verification Results

✅ All verification tests passed:
- 3 ZAP Automation Plans created successfully
- 3 ZAP Configurations created successfully
- Encryption/decryption working correctly
- Model relationships functioning properly
- Sensitive data properly masked in API responses
- Database schema fully validated

## Dependencies Added

**New Requirements:**
- `cryptography==41.0.7` - Fernet encryption for sensitive data

Added to `requirements.txt`.

## Security Considerations

### Encryption
- All sensitive configuration data encrypted at rest
- Encryption key derived from Flask SECRET_KEY
- Must use strong SECRET_KEY in production

### Access Control
- ZapAutomationPlan: 
  - Admins: Full access to all plans
  - Power users: Access to plans where `allow_power_users=True`
  - Standard users: No access
  - Drafts: Require admin approval before use

- ZapConfiguration:
  - Only admins can view/edit configurations
  - Sensitive data masked in API responses by default
  - Full data only accessible with `include_sensitive=True` (admin only)

### Data Masking
- Sensitive keys automatically masked in `to_dict()` output
- Keys masked: api_key, password, secret, token, credential, access_key, secret_key
- Masked values shown as '********'
- Full decrypted data only for admin users

## Database Schema

### New Tables Created
1. `zap_automation_plans` - 13 columns, indexes on name, created_at
2. `zap_configurations` - 13 columns, indexes on name, created_at
3. `zap_scan_progress` - 20 columns, indexes on scan_id, status

### Updated Tables
1. `scans` - Added 3 new fields for ZAP relationships

## Next Steps (Phase 2)

Phase 2 will focus on:
1. Admin panel UI for managing ZAP plans and configurations
2. Form handlers for CRUD operations
3. Plan editor with YAML validation
4. Configuration manager with encryption handling
5. Permission enforcement in routes

## Testing Checklist

- [x] Database tables created successfully
- [x] Encryption/decryption working
- [x] Default plans seeded correctly
- [x] Default configurations seeded correctly
- [x] Model relationships working
- [x] Sensitive data masking working
- [x] Foreign key relationships validated
- [x] Property accessors/setters working
- [x] to_dict() methods working

## Files Created/Modified

### Created Files
- `app/encryption.py` - Encryption utilities
- `utils/migrate_zap_feature.py` - Migration script
- `utils/verify_zap_migration.py` - Verification script
- `docs/ZAP_INTEGRATION_PHASE1.md` - This documentation

### Modified Files
- `app/models.py` - Added 3 new models, updated Scan model
- `requirements.txt` - Added cryptography dependency

## Rollback Procedure

If rollback is needed:

1. Remove ZAP fields from Scan model:
   ```sql
   ALTER TABLE scans DROP COLUMN zap_plan_id;
   ALTER TABLE scans DROP COLUMN zap_config_id;
   ALTER TABLE scans DROP COLUMN zap_execution_mode;
   ```

2. Drop new tables:
   ```sql
   DROP TABLE zap_scan_progress;
   DROP TABLE zap_configurations;
   DROP TABLE zap_automation_plans;
   ```

3. Remove `cryptography==41.0.7` from requirements.txt
4. Delete `app/encryption.py`

## Notes

- Phase 1 focuses exclusively on database schema and models
- No UI or route changes in this phase
- All encryption keys derived from Flask SECRET_KEY
- Ensure strong SECRET_KEY in production
- Backup database before running migration
- Migration script is idempotent (safe to run multiple times)

## Support

For questions or issues:
- Review verification test output
- Check database schema with admin database explorer
- Verify SECRET_KEY is set in .env file
- Ensure cryptography package installed

---

**Phase 1 Complete:** Database schema and models ready for Phase 2 implementation.
