# KAST-Web Configuration Profiles Implementation

## Overview

This document describes the implementation of the scan configuration profile system for KAST-Web. This feature allows power users and admins to create, manage, and use reusable KAST scan configurations with custom plugin settings.

## Implementation Status

### ✅ Phase 1: Database Foundation (COMPLETE)
- **Migration Script**: `utils/migrate_scan_configs.py`
- **Database Tables**:
  - `scan_config_profiles` - Stores configuration profiles
  - Added `config_profile_id` and `config_overrides` to `scans` table
- **Models**: `ScanConfigProfile` model in `app/models.py`
- **Relationships**: Bidirectional relationships between User, ScanConfigProfile, and Scan
- **Preset Profiles**: Three system profiles created (Standard, Stealth, Aggressive)

### ✅ Phase 2: Basic CRUD Operations (COMPLETE)
- **Routes**: `app/routes/config_profiles.py` with full CRUD operations
- **Forms**: `ScanConfigProfileForm` in `app/forms.py`
- **Templates**:
  - `list.html` - Browse all accessible profiles
  - `view.html` - View profile details with YAML/JSON display
  - `create.html` - Create new profiles with validation
  - `edit.html` - Edit existing profiles
- **Navigation**: Links added to base template for power users/admins
- **Authorization**: Decorators (`@power_user_required`, `@admin_required`) in `app/utils.py`
- **Dependencies**: PyYAML added to `requirements.txt`

### 🔄 Phase 3: Visual Form Builder (OPTIONAL)
- Interactive form builder for creating YAML configs
- Real-time YAML preview
- Plugin-specific setting forms
- Not required for basic functionality

### ⏳ Phase 4: Scan Integration (NEXT PRIORITY)
- Integration with scan execution flow
- Apply config profile settings when running scans
- Support for `--config` and `--set` KAST CLI arguments
- Config override functionality for power users/admins
- **This is the critical next step**

### ⏳ Phase 5: Polish and Documentation
- Complete user documentation
- Admin guide for managing profiles
- Testing and bug fixes
- Performance optimization

## Database Schema

### scan_config_profiles Table
```sql
CREATE TABLE scan_config_profiles (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    config_yaml TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    allow_standard_users BOOLEAN DEFAULT FALSE,
    is_system_default BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);
```

### scans Table (New Columns)
```sql
ALTER TABLE scans ADD COLUMN config_profile_id INTEGER;
ALTER TABLE scans ADD COLUMN config_overrides TEXT;
ALTER TABLE scans ADD FOREIGN KEY (config_profile_id) REFERENCES scan_config_profiles(id);
```

## Access Control

### Role-Based Permissions

| Role | List Profiles | View Profiles | Create/Edit/Delete | Use Any Profile | Override Settings |
|------|--------------|---------------|-------------------|-----------------|-------------------|
| **Viewer** | No | No | No | No | No |
| **User** | Standard only | Standard only | No | Standard only | No |
| **Power User** | All | All | Yes | All | Yes (--set) |
| **Admin** | All | All | Yes | All | Yes (--set) |

### Profile Access Flags
- `allow_standard_users`: If TRUE, standard users can use this profile
- `is_system_default`: Only one profile can be the system default

## Preset Configuration Profiles

Three preset profiles are created during migration:

### 1. Standard (Default)
- **Purpose**: Balanced configuration for general-purpose scanning
- **Standard Users**: ✅ Allowed
- **Characteristics**:
  - Moderate request rates (100-150 req/sec)
  - Balanced concurrency (10 workers)
  - Suitable for most targets

### 2. Stealth
- **Purpose**: Low-profile scanning to minimize detection
- **Standard Users**: ✅ Allowed
- **Characteristics**:
  - Very low request rates (5-10 req/sec)
  - Low concurrency (3 workers)
  - Increased delays (2 seconds)
  - Suitable for sensitive targets

### 3. Aggressive
- **Purpose**: High-speed scanning for internal testing
- **Standard Users**: ❌ Power Users Only
- **Characteristics**:
  - High request rates (300-500 req/sec)
  - High concurrency (20 workers)
  - No delays
  - Only for dev/test/UAT environments

## API Routes

### Public Routes (Authenticated)
- `GET /config-profiles/` - List accessible profiles
- `GET /config-profiles/<id>` - View profile details

### Power User/Admin Routes
- `GET /config-profiles/create` - Create new profile
- `POST /config-profiles/create` - Submit new profile
- `GET /config-profiles/<id>/edit` - Edit profile form
- `POST /config-profiles/<id>/edit` - Submit profile changes
- `POST /config-profiles/<id>/delete` - Delete profile
- `POST /config-profiles/<id>/duplicate` - Duplicate profile
- `POST /config-profiles/<id>/validate` - Validate YAML (AJAX)

## Configuration Structure

### YAML Format
```yaml
global:
  timeout: 300
  retry_count: 2

plugins:
  subfinder:
    rate_limit: 150
    timeout: 30
    max_time: 10
    concurrent_goroutines: 10
    
  katana:
    concurrency: 10
    rate_limit: 150
    delay: 0
    
  ftap:
    concurrency: 10
    rate_limit: 100
```

### Available Plugins (Passive Scan)
- `mozilla_observatory` - Mozilla Observatory scanning
- `subfinder` - Subdomain enumeration
- `script_detection` - JavaScript detection
- `wafw00f` - WAF detection
- `katana` - Web crawling
- `ftap` - Technology profiling

## Usage Examples

### As Admin: Create Custom Profile
1. Navigate to "Config Profiles" in navigation
2. Click "Create New Profile"
3. Enter name, description, and YAML configuration
4. Set permissions (allow standard users)
5. Save profile

### As User: Use Profile in Scan
1. Go to "New Scan"
2. Select configuration profile from dropdown
3. Configure target and plugins
4. Run scan with selected profile

### As Power User: Override Settings
1. Select base configuration profile
2. Add custom overrides in "Advanced Settings"
3. Override specific plugin settings
4. Run scan with overrides

## Next Steps (Phase 4: Scan Integration)

To complete the feature, we need to:

1. **Update Scan Form** (`app/forms.py`)
   - Add `config_profile_id` field
   - Add `config_overrides` textarea for power users/admins
   - Load available profiles based on user role

2. **Update Scan Routes** (`app/routes/scans.py`)
   - Pass selected config profile to scan execution
   - Handle config overrides
   - Generate temporary config file if needed

3. **Update Task Execution** (`app/tasks.py`)
   - Modify `run_scan_task` to use config profiles
   - Generate config YAML file from profile
   - Add `--config` argument to KAST CLI command
   - Add `--set` arguments for overrides

4. **Update Scan Creation Template** (`app/templates/index.html`)
   - Add config profile dropdown
   - Add override section for power users/admins
   - Show profile description on selection

5. **Testing**
   - Test profile selection
   - Test config overrides
   - Verify correct KAST CLI arguments
   - Test with different user roles

## Migration

To apply the database changes:

```bash
cd /opt/kast-web
python utils/migrate_scan_configs.py
```

This will:
- Create the `scan_config_profiles` table
- Add columns to `scans` table
- Create admin user if needed
- Create three preset profiles (Standard, Stealth, Aggressive)

## Dependencies

Added to `requirements.txt`:
- `PyYAML==6.0.3` - For YAML parsing and validation

## Security Considerations

1. **YAML Validation**: All YAML is validated before saving
2. **Access Control**: Proper role-based restrictions enforced
3. **Audit Logging**: All profile operations logged to `audit_logs`
4. **Deletion Protection**: Profiles in use cannot be deleted
5. **Standard User Protection**: Aggressive profiles restricted to power users

## Testing Checklist

- [ ] Create new profile as power user
- [ ] View profile as standard user
- [ ] Edit existing profile
- [ ] Duplicate profile
- [ ] Delete unused profile
- [ ] Attempt to delete profile in use
- [ ] Validate YAML syntax
- [ ] Use profile in scan (Phase 4)
- [ ] Override profile settings (Phase 4)
- [ ] Test role-based access controls

## Known Limitations

1. **Active Scan Configs**: Currently only passive scan plugins supported
2. **Visual Builder**: Phase 3 visual form builder not yet implemented
3. **Scan Integration**: Phase 4 scan execution integration pending
4. **Profile Versioning**: No version history tracking for profile changes

## Future Enhancements

1. Profile import/export (JSON/YAML files)
2. Profile templates library
3. Profile versioning and history
4. Profile usage analytics
5. Scheduled scans with profiles
6. Profile sharing between organizations
7. ZAP active scan configuration support

## Support

For questions or issues:
- Review `genai-instructions.md` for project guidelines
- Check audit logs for troubleshooting
- Test with different user roles
- Verify YAML syntax with `kast --config-schema`
