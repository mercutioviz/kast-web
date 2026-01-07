# ZAP Integration Phase 2: Admin Panel Management

## Overview

Phase 2 adds comprehensive admin panel functionality for managing ZAP automation plans and execution configurations through the KAST-Web interface.

**Implementation Date**: January 2026  
**Status**: ✅ Complete

## Features Implemented

### 1. ZAP Automation Plans Management

Admin interface for creating, editing, and managing ZAP automation framework plans.

**Key Features**:
- Create/edit/delete automation plans
- YAML editor with real-time validation
- Plan preview with job breakdown
- Usage statistics and success rates
- System default plan designation
- Power user access control
- Draft mode for plan development
- Plan approval workflow

**Routes**:
- `/admin/zap/plans` - List all plans
- `/admin/zap/plans/create` - Create new plan
- `/admin/zap/plans/<id>` - View plan details
- `/admin/zap/plans/<id>/edit` - Edit plan
- `/admin/zap/plans/<id>/delete` - Delete plan
- `/admin/zap/plans/<id>/approve` - Approve draft plan
- `/admin/zap/plans/validate` - AJAX YAML validation

### 2. ZAP Configuration Management

Admin interface for managing ZAP execution environments and connection settings.

**Key Features**:
- Create/edit/delete configurations
- Multiple execution modes: Local (Docker), Remote, Cloud, Auto
- Dynamic form fields based on mode
- Connection testing
- Default configuration designation
- Usage statistics
- Mode-specific settings with validation

**Routes**:
- `/admin/zap/configs` - List all configurations
- `/admin/zap/configs/create` - Create new configuration
- `/admin/zap/configs/<id>/edit` - Edit configuration
- `/admin/zap/configs/<id>/delete` - Delete configuration
- `/admin/zap/configs/<id>/test` - Test connection
- `/admin/zap/configs/<id>/set-default` - Set as default

### 3. Admin Dashboard Integration

Added ZAP management cards to admin dashboard showing:
- Total automation plans (active/draft counts)
- System default plan
- Power user accessible plans
- Total configurations (by execution mode)
- Active configurations
- Quick access links

### 4. Default Plan Seeding

Migration script automatically imports 5 default plans from KAST CLI config:
1. **Quick Scan** - Fast CI/CD scan (~20 min)
2. **Standard Scan** - Balanced development scan (~45 min, DEFAULT)
3. **Thorough Scan** - Comprehensive pre-production scan (~90 min)
4. **API Scan** - REST API optimized scan (~30 min)
5. **Passive Scan** - Production-safe passive scan (~15 min)

## File Structure

```
app/
├── forms.py                    # Added ZapPlanForm, ZapConfigForm
├── zap_utils.py               # New - ZAP helper functions
├── routes/
│   └── zap_admin.py           # New - ZAP admin routes blueprint
├── templates/
│   └── admin/
│       ├── dashboard.html     # Updated - Added ZAP cards
│       └── zap/               # New directory
│           ├── plans_list.html
│           ├── plan_form.html
│           ├── plan_preview.html
│           ├── configs_list.html
│           └── config_form.html

utils/
└── migrate_zap_feature.py     # Updated - Imports KAST default plans

docs/
└── ZAP_INTEGRATION_PHASE2.md  # This file
```

## Database Models (From Phase 1)

### ZapAutomationPlan
```python
- id: Integer (PK)
- name: String(200) - Unique plan name
- description: Text - Plan purpose
- plan_yaml: Text - YAML configuration
- created_by: Integer (FK to User)
- is_system_default: Boolean - Default plan flag
- allow_power_users: Boolean - Power user access
- is_draft: Boolean - Draft status
- approved_at: DateTime - Approval timestamp
- created_at/updated_at: DateTime
```

### ZapConfiguration
```python
- id: Integer (PK)
- name: String(200) - Unique config name
- description: Text - Configuration purpose
- execution_mode: String(50) - local/remote/cloud/auto
- created_by: Integer (FK to User)
- is_active: Boolean - Active status
- is_default: Boolean - Default config flag
- local_config_encrypted: Text - Encrypted Docker settings
- remote_config_encrypted: Text - Encrypted remote settings
- cloud_config_encrypted: Text - Encrypted cloud settings
- created_at/updated_at: DateTime
```

## Usage Guide

### Creating a New Automation Plan

1. Navigate to **Admin Panel** → **ZAP Automation Plans**
2. Click **Create New Plan**
3. Enter plan details:
   - Name (unique identifier)
   - Description (purpose and use case)
   - YAML configuration
4. Configure options:
   - System Default (only one plan can be default)
   - Allow Power Users (enable for power_user role)
   - Draft Mode (requires approval before use)
5. Click **Validate YAML** to check syntax
6. Click **Create Plan**

### YAML Structure

Required sections:
```yaml
env:
  contexts:
    - name: "context-name"
      urls:
        - "${TARGET_URL}"  # Auto-replaced at runtime
      includePaths:
        - "${TARGET_URL}.*"
      excludePaths:
        - ".*logout.*"
  parameters:
    failOnError: true
    progressToStdout: true

jobs:
  - type: "spider"
    parameters:
      maxDuration: 10
      maxDepth: 5
      
  - type: "passiveScan-wait"
    parameters:
      maxDuration: 10
      
  - type: "activeScan"
    parameters:
      maxScanDurationInMins: 30
      threadPerHost: 2
      
  - type: "report"
    parameters:
      template: "traditional-json"
      reportDir: "/zap/reports"
      reportFile: "zap_report.json"
```

### Creating a New Configuration

1. Navigate to **Admin Panel** → **ZAP Configurations**
2. Click **Create New Configuration**
3. Enter basic info:
   - Name
   - Description
   - Execution Mode
4. Configure mode-specific settings:

   **Local (Docker)**:
   - Docker Image (default: ghcr.io/zaproxy/zaproxy:stable)
   - Port (default: 8080)
   - Memory Limit (e.g., 2g)
   - Auto Remove Container

   **Remote**:
   - Remote URL (e.g., http://zap-server:8080)
   - API Key (encrypted)
   - Timeout (seconds)
   - Verify SSL

   **Cloud**:
   - Provider (AWS/GCP/Azure)
   - Region
   - Instance Type
   - Access Credentials (encrypted)
   - Auto Terminate

5. Set as active/default if needed
6. Click **Test Connection** to verify
7. Click **Create Configuration**

## Security Features

### Encryption
- All sensitive data (API keys, credentials) encrypted at rest using Fernet
- Encryption key from environment: `ENCRYPTION_KEY`
- See `app/encryption.py` for implementation

### Access Control
- All routes require `@admin_required` decorator
- Plans can be restricted to admin-only (allow_power_users=False)
- Audit logging for all sensitive actions

### Data Protection
- Credentials never shown in UI after creation
- Placeholder text shown: "Leave blank to keep existing"
- Sensitive data masked in logs

## API Endpoints

### AJAX Endpoints

**POST** `/admin/zap/plans/validate`
```json
Request: {"yaml": "..."}
Response: {
  "message": "YAML is valid",
  "jobs": [{"type": "spider", "context": "..."}],
  "summary": {...}
}
```

**POST** `/admin/zap/configs/<id>/test`
```json
Response: {
  "message": "Connection successful",
  "details": {...}
}
```

## Integration with KAST CLI

### Plan Import
Migration script imports default plans from:
```
/opt/kast/kast/config/
├── zap_automation_quick.yaml
├── zap_automation_standard.yaml (DEFAULT)
├── zap_automation_thorough.yaml
├── zap_automation_api.yaml
└── zap_automation_passive.yaml
```

### Fallback Plans
If KAST config directory not found, uses built-in fallback plans.

## Migration

### Running the Migration

```bash
# From project root
cd /opt/kast-web
python utils/migrate_zap_feature.py
```

### Migration Steps
1. Creates database tables (ZapAutomationPlan, ZapConfiguration)
2. Imports 5 default plans from KAST config
3. Creates 3 default configurations (Local, Remote, Cloud template)
4. Sets "Standard Scan" as system default

### Verification

```bash
python utils/verify_zap_migration.py
```

Checks:
- Tables exist
- Default plans imported
- Default configuration set
- Encryption working

## Admin Dashboard Stats

Dashboard now includes `stats.zap` with:

```python
stats = {
    'zap': {
        'plans': {
            'total': 5,
            'active': 4,  # Non-draft count
            'default_name': 'Standard Scan',
            'power_user_count': 4
        },
        'configs': {
            'total': 3,
            'active': 2,
            'by_mode': {
                'local': 1,
                'remote': 1,
                'cloud': 1,
                'auto': 0
            }
        }
    }
}
```

## Testing

### Manual Testing Checklist

**Plans Management**:
- [ ] Create new plan with valid YAML
- [ ] Edit existing plan
- [ ] Validate YAML (both valid and invalid)
- [ ] View plan preview with job breakdown
- [ ] Set plan as system default
- [ ] Toggle power user access
- [ ] Approve draft plan
- [ ] Delete non-default plan
- [ ] Verify default plan cannot be deleted

**Configurations Management**:
- [ ] Create local Docker config
- [ ] Create remote ZAP config
- [ ] Create cloud config (template)
- [ ] Edit configuration (verify credentials not shown)
- [ ] Test connection (both success and failure)
- [ ] Set as default configuration
- [ ] Toggle active/inactive status
- [ ] Delete non-default config

**Dashboard**:
- [ ] Verify ZAP cards display correct counts
- [ ] Click "Manage Plans" link
- [ ] Click "Create Plan" link
- [ ] Click "Manage Configurations" link
- [ ] Click "Create Configuration" link

## Known Limitations

1. **No Plan Versioning** - Plans are updated in-place (Phase 3 feature)
2. **No Configuration Testing** - Test button validates connection only, not full scan
3. **No Plan Templates** - Cannot duplicate existing plans (workaround: copy YAML)
4. **Limited Cloud Support** - Cloud configs are templates only, not yet functional

## Future Enhancements (Phase 3)

Potential features for next phase:
- Plan versioning and rollback
- Plan duplication/templating
- Advanced YAML editor with syntax highlighting
- Configuration import/export
- Bulk operations
- Plan scheduling
- Configuration profiles
- Performance metrics dashboard

## Troubleshooting

### YAML Validation Fails
**Symptom**: "Invalid YAML syntax" error
**Solution**: 
- Check for proper indentation (spaces, not tabs)
- Verify all required sections present (env, jobs)
- Ensure ${TARGET_URL} placeholder used
- Use online YAML validator: yamllint.com

### Plans Not Appearing
**Symptom**: Plans list is empty after migration
**Solution**:
- Verify KAST directory exists: `/opt/kast/kast/config`
- Check migration output for errors
- Run verification script: `python utils/verify_zap_migration.py`
- Check for admin user in database

### Test Connection Fails
**Symptom**: Configuration test always fails
**Solution**:
- For local mode: Verify Docker is running
- For remote mode: Check URL and API key
- For cloud mode: Not yet implemented (Phase 3)
- Check firewall rules and network access

### Encryption Errors
**Symptom**: "Encryption key not configured" error
**Solution**:
- Set ENCRYPTION_KEY in environment or .env file
- Generate key: `from cryptography.fernet import Fernet; print(Fernet.generate_key())`
- Restart application after setting key

## Support

For issues or questions:
1. Check Phase 1 documentation: `docs/ZAP_INTEGRATION_PHASE1.md`
2. Review KAST CLI docs: `/opt/kast/kast/config/ZAP_TEST_PLANS_README.md`
3. Check audit log for errors
4. Use `/reportbug` command in KAST CLI

## Changelog

### v1.0.0 (January 2026)
- ✅ Initial Phase 2 implementation
- ✅ Admin panel UI for plans and configurations
- ✅ YAML validation with AJAX
- ✅ Connection testing for configurations
- ✅ Dashboard integration
- ✅ Default plan import from KAST CLI
- ✅ Complete documentation

---

**Phase 2 Status**: ✅ Complete  
**Next Phase**: Phase 3 - Scan Execution Integration
