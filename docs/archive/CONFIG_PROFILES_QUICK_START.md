# Configuration Profiles Quick Start Guide

## What Are Configuration Profiles?

Configuration profiles allow you to create reusable KAST scan configurations with custom plugin settings. Instead of manually configuring scan parameters each time, you can select a predefined profile that applies your preferred settings automatically.

## Getting Started

### Step 1: Apply Database Migration

Run the migration script to set up the database tables:

```bash
cd /opt/kast-web
python utils/migrate_scan_configs.py
```

This creates:
- Configuration profiles table
- Three preset profiles (Standard, Stealth, Aggressive)
- Updates scans table with config fields

### Step 2: Install Dependencies

Ensure PyYAML is installed:

```bash
pip install -r requirements.txt
```

### Step 3: Start the Application

```bash
python run.py
```

## Using Configuration Profiles

### For Power Users and Admins

#### View Existing Profiles
1. Log in as power user or admin
2. Click "Config Profiles" in navigation
3. Browse available profiles

#### Create New Profile
1. Go to Config Profiles → "Create New Profile"
2. Enter:
   - **Name**: Descriptive name (e.g., "Fast Scan", "Quiet Mode")
   - **Description**: Explain the purpose and characteristics
   - **YAML Configuration**: Plugin settings (see examples below)
   - **Allow Standard Users**: Check if standard users can use it
   - **System Default**: Check if this should be the default profile

3. Click "Validate YAML" to check syntax
4. Click "Create Profile"

#### Edit Profile
1. Go to Config Profiles → Select profile → "Edit"
2. Make changes to settings
3. Save changes

#### Duplicate Profile
1. Go to Config Profiles → Select profile
2. Click "Duplicate"
3. Edit the duplicated profile as needed

#### Delete Profile
1. Go to Config Profiles → Select profile
2. Click "Delete" (only if not in use)

### For Standard Users

Standard users can:
- View profiles marked as "Allow Standard Users"
- Use these profiles when creating scans
- Cannot create, edit, or delete profiles

## YAML Configuration Examples

### Example 1: Balanced Standard Profile
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

### Example 2: Stealth Profile (Low Detection)
```yaml
global:
  timeout: 600
  retry_count: 1

plugins:
  subfinder:
    rate_limit: 5
    timeout: 60
    max_time: 20
    concurrent_goroutines: 3
    
  katana:
    concurrency: 3
    rate_limit: 5
    delay: 2
    
  ftap:
    concurrency: 3
    rate_limit: 5
    delay: 2
```

### Example 3: Aggressive Profile (Fast Scanning)
```yaml
global:
  timeout: 180
  retry_count: 3

plugins:
  subfinder:
    rate_limit: 300
    timeout: 20
    max_time: 5
    concurrent_goroutines: 20
    
  katana:
    concurrency: 20
    rate_limit: 500
    delay: 0
    
  ftap:
    concurrency: 15
    rate_limit: 300
```

## Plugin Settings Reference

### Common Settings (Most Plugins)
- `rate_limit`: Requests per second (e.g., 150)
- `timeout`: Request timeout in seconds (e.g., 30)
- `concurrency`: Number of concurrent workers (e.g., 10)
- `delay`: Delay between requests in seconds (e.g., 0)
- `retry`: Number of retry attempts (e.g., 2)

### Plugin-Specific Settings

#### subfinder
- `max_time`: Maximum time for enumeration in minutes
- `concurrent_goroutines`: Number of concurrent goroutines

#### katana
- `crawl_depth`: Maximum depth to crawl
- `field_scope`: Scope of fields to extract

#### ftap
- `probe_timeout`: Timeout for individual probes

## View Full Schema

To see all available configuration options:

```bash
kast --config-schema
```

This displays the complete JSON schema with all plugins and their settings.

## Access Control

### Profile Visibility by Role

| Role | Can View | Can Create/Edit | Can Use in Scans |
|------|----------|-----------------|------------------|
| Viewer | ❌ | ❌ | ❌ |
| User | ✅ Standard only | ❌ | ✅ Standard only |
| Power User | ✅ All | ✅ | ✅ All |
| Admin | ✅ All | ✅ | ✅ All |

### "Allow Standard Users" Flag
- When checked: Standard users can use this profile in their scans
- When unchecked: Only power users and admins can use this profile
- Recommendation: Keep aggressive/intensive profiles restricted

## Best Practices

### Creating Profiles
1. **Name Clearly**: Use descriptive names that indicate the profile's purpose
2. **Validate First**: Always validate YAML before saving
3. **Test Carefully**: Test new profiles with known targets first
4. **Document Well**: Write clear descriptions explaining when to use each profile
5. **Consider Security**: Restrict aggressive profiles to power users only

### Using Profiles
1. **Choose Appropriately**: Match profile to target sensitivity
2. **Standard for Most**: Use "Standard" profile for general-purpose scanning
3. **Stealth for Sensitive**: Use "Stealth" for production environments
4. **Aggressive for Testing**: Use "Aggressive" only in dev/test/UAT

### Managing Profiles
1. **Regular Review**: Periodically review and update profiles
2. **Remove Unused**: Delete profiles that are no longer needed
3. **Track Usage**: Monitor which profiles are most used
4. **Version Naming**: Include version numbers in profile names if needed

## Troubleshooting

### YAML Validation Errors
- Check indentation (use spaces, not tabs)
- Verify plugin names match `kast --list-plugins`
- Ensure all values are valid types (numbers, booleans, strings)
- Reference `kast --config-schema` for correct structure

### Profile Not Visible
- Check role permissions (viewer can't see any profiles)
- Verify "Allow Standard Users" flag for user role
- Confirm you're logged in

### Cannot Delete Profile
- Profile may be in use by existing scans
- Check profile details page for usage count
- Profiles in use cannot be deleted (by design)

## Next Steps

**Phase 4 - Scan Integration** (Coming Next):
- Select configuration profile when creating a scan
- Override specific settings (power users/admins only)
- Apply profile settings during scan execution
- View which profile was used for completed scans

**Phase 5 - Polish**:
- Visual form builder for easier profile creation
- Profile import/export functionality
- Usage analytics and statistics
- Additional preset profiles

## Support

For more information:
- Full documentation: `docs/CONFIG_PROFILES_IMPLEMENTATION.md`
- Project guidelines: `genai-instructions.md`
- KAST schema: `kast --config-schema`
