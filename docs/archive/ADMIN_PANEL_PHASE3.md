# Admin Panel - Phase 3 Implementation

This document describes Phase 3 implementation: Admin Panel with system management, audit logging, and activity monitoring.

## Overview

Phase 3 adds a comprehensive admin panel for system administrators:
- **Dashboard** - System statistics and health monitoring
- **System Settings** - Configurable system-wide parameters
- **Audit Log** - Track all system actions and user activities
- **Activity Monitoring** - User behavior and scan analytics

## New Components

### 1. Database Models

#### AuditLog Model (`app/models.py`)
Tracks all significant system events:

```python
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey('users.id'))
    action = db.Column(db.String(100))        # login, logout, scan_created, etc.
    resource_type = db.Column(db.String(50))  # user, scan, system
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime)
```

**Usage:**
```python
AuditLog.log(
    user_id=current_user.id,
    action='scan_created',
    resource_type='scan',
    resource_id=scan.id,
    details=f'Scan created for {scan.target}'
)
```

#### SystemSettings Model (`app/models.py`)
Stores system configuration:

```python
class SystemSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20))  # string, int, bool, json
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime)
    updated_by = db.Column(db.Integer, ForeignKey('users.id'))
```

**Usage:**
```python
# Get single setting
maintenance_mode = SystemSettings.get_setting('maintenance_mode', False)

# Get all settings
settings = SystemSettings.get_settings()

# Set setting
SystemSettings.set_setting('site_name', 'My KAST Instance')

# Update multiple settings
SystemSettings.update_settings({
    'maintenance_mode': True,
    'max_scans_per_user': 100
}, user_id=current_user.id)
```

### 2. Admin Routes (`app/routes/admin.py`)

All admin routes are protected with `@admin_required` decorator.

#### Dashboard (`/admin/dashboard`)
Displays:
- User statistics (total, active, admins)
- Scan statistics (total, completed, failed, running)
- Recent activity (24-hour window)
- Top users by scan count
- Recent audit log entries
- System status

#### Settings (`/admin/settings`)
Configurable parameters:
- **General:**
  - Site name
  - Maintenance mode
- **User Management:**
  - Allow registration
  - Session timeout
- **Scan Settings:**
  - Maximum scan age (auto-deletion)
  - Maximum scans per user
- **Audit Log:**
  - Enable/disable logging

#### Audit Log (`/admin/audit-log`)
Features:
- Paginated log entries (50 per page)
- Filter by:
  - User
  - Action type
  - Resource type
- Clear old entries function
- Export capabilities (future)

#### Activity Monitoring (`/admin/activity`)
Analytics:
- Scans per user (configurable time period)
- Daily scan trends
- Failed scans per user
- Login activity
- User engagement metrics

### 3. Admin Templates

#### `app/templates/admin/dashboard.html`
- 4 stat cards (users, scans, running, failed)
- Recent activity metrics
- Top users leaderboard
- System status indicators
- Recent audit log preview

#### `app/templates/admin/settings.html`
- Organized settings form
- Real-time validation
- Help text for each setting
- Security tips sidebar

### 4. Navigation Updates

Added to Admin dropdown (`app/templates/base.html`):
```html
<li><a class="dropdown-item" href="{{ url_for('admin.dashboard') }}">
    <i class="bi bi-speedometer2"></i> Dashboard
</a></li>
```

## Default Settings

After migration, these defaults are configured:

| Setting | Default Value | Description |
|---------|--------------|-------------|
| site_name | "KAST Web" | Displayed in navigation |
| maintenance_mode | false | Block non-admin access |
| allow_registration | false | Self-service signup |
| max_scan_age_days | 90 | Auto-delete old scans (0=never) |
| max_scans_per_user | 0 | Per-user limit (0=unlimited) |
| enable_audit_log | true | Track system events |
| session_timeout_minutes | 60 | Auto-logout inactive users |

## Security Features

### 1. Access Control
```python
@admin_required
def admin_function():
    """Only admins can access"""
    pass
```

The `@admin_required` decorator:
- Checks `current_user.is_authenticated`
- Verifies `current_user.is_admin`
- Redirects non-admins with error message

### 2. Audit Trail
All admin actions are automatically logged:
- Settings changes
- User management
- System configuration
- Audit log maintenance

### 3. Data Protection
- Sensitive settings encrypted at rest
- IP addresses logged for security tracking
- User agent strings captured for forensics
- Timestamps with UTC for consistency

## Common Audit Actions

| Action | Resource Type | Description |
|--------|--------------|-------------|
| `login` | user | User logged in |
| `logout` | user | User logged out |
| `login_failed` | user | Failed login attempt |
| `user_created` | user | New user created |
| `user_updated` | user | User profile modified |
| `user_deleted` | user | User deleted |
| `scan_created` | scan | New scan initiated |
| `scan_deleted` | scan | Scan removed |
| `settings_updated` | system | Settings changed |
| `audit_log_cleared` | system | Old logs removed |
| `password_changed` | user | Password updated |

## Migration

Run the migration script:
```bash
python migrate_phase3.py
```

This creates:
- `audit_logs` table
- `system_settings` table
- Default configuration values

## Usage Examples

### Admin Dashboard Access
1. Log in as admin user
2. Click "Admin" → "Dashboard" in navigation
3. View system statistics and health
4. Monitor recent activity

### Configure System Settings
1. Navigate to Admin → Dashboard
2. Click "Settings" button
3. Modify desired settings
4. Click "Save Settings"
5. Changes take effect immediately

### View Audit Log
1. Go to Admin → Dashboard
2. Click "Audit Log" button (or "View All" in recent logs)
3. Use filters to find specific events:
   - Filter by username
   - Filter by action type
   - Filter by resource type
4. Paginate through results

### Monitor User Activity
1. Navigate to Admin → Activity
2. Select time period (7, 14, 30 days)
3. View:
   - Scans per user
   - Daily scan trends
   - Failed scans analysis
   - Login statistics

### Clear Old Audit Logs
1. Go to Audit Log page
2. Scroll to bottom
3. Enter number of days to retain
4. Click "Clear Old Entries"
5. Confirm action

## API Endpoints

### `/admin/api/stats` (GET)
Returns real-time statistics in JSON:

```json
{
  "users": {
    "total": 5,
    "active": 4
  },
  "scans": {
    "total": 30,
    "running": 2,
    "completed": 25,
    "failed": 3
  }
}
```

**Use case:** Dashboard auto-refresh, monitoring integrations

## Best Practices

### 1. Regular Monitoring
- Check dashboard daily
- Review failed scans
- Monitor user activity patterns
- Watch for unusual login attempts

### 2. Audit Log Management
- Clear old entries periodically (e.g., > 90 days)
- Export logs before clearing for compliance
- Review logs after security incidents
- Track admin action patterns

### 3. Settings Management
- Enable maintenance mode before updates
- Keep registration disabled unless needed
- Set reasonable session timeouts (30-120 min)
- Configure scan limits based on resources

### 4. Security Hardening
- Regularly review user list
- Disable inactive accounts
- Monitor failed login attempts
- Track admin actions via audit log
- Keep audit logging enabled

## Troubleshooting

### Issue: Can't access admin panel

**Symptoms:** 403 Forbidden or redirect to home page

**Solution:**
1. Verify admin status:
   ```sql
   SELECT username, role FROM users WHERE username = 'your_username';
   ```
2. Should show `role = 'admin'`
3. If not, update:
   ```sql
   UPDATE users SET role = 'admin' WHERE username = 'your_username';
   ```
4. Log out and log back in

### Issue: Dashboard shows no statistics

**Symptoms:** All numbers are zero

**Causes:**
- No scans in database
- No users besides admin
- Database connection issue

**Solution:**
1. Verify data exists:
   ```sql
   SELECT COUNT(*) FROM scans;
   SELECT COUNT(*) FROM users;
   ```
2. If zero, create test data
3. Refresh dashboard

### Issue: Settings not saving

**Symptoms:** Settings revert after save

**Causes:**
- Permission issue
- Database write failure
- Validation error

**Solution:**
1. Check application logs
2. Verify database write permissions
3. Check for validation errors in flash messages
4. Review browser console for JS errors

### Issue: Audit log not recording events

**Symptoms:** No new log entries appear

**Causes:**
- Audit logging disabled in settings
- Database write issue
- Code not calling `AuditLog.log()`

**Solution:**
1. Check Settings → Enable Audit Logging
2. Verify database permissions
3. Test manually:
   ```python
   AuditLog.log(
       user_id=1,
       action='test',
       details='Test entry'
   )
   ```

### Issue: Migration failed

**Symptoms:** Error running `migrate_phase3.py`

**Common causes:**
- Tables already exist
- Database locked
- Permission denied

**Solution:**
1. Check if tables exist:
   ```sql
   SELECT name FROM sqlite_master WHERE type='table';
   ```
2. If `audit_logs` and `system_settings` exist, migration already ran
3. If database locked, stop all Flask instances
4. Re-run migration

## Future Enhancements

### Phase 4: Database Management
- Backup functionality
- Restore from backup
- Scheduled automatic backups
- Database optimization tools

### Phase 5: Email Integration
- Email notification system
- Send scan results via email
- Alert on scan failures
- System status reports

### Phase 6: Advanced Analytics
- Scan success rate trends
- Plugin performance metrics
- User engagement scoring
- Resource utilization graphs
- Predictive maintenance alerts

### Phase 7: Multi-tenancy
- Organization support
- Team management
- Resource quotas per org
- Billing integration

## Performance Considerations

### Dashboard Loading
- Queries optimized with indexes
- Limited to recent data (24h window)
- Top users limited to 5
- Recent logs limited to 10

### Audit Log Pagination
- 50 entries per page
- Indexed on timestamp and user_id
- Filters use database indexes
- Efficient for millions of entries

### Settings Cache
- Settings loaded once per request
- Cached in memory for performance
- Updated immediately on save
- No external cache needed

## Compliance & Privacy

### Data Retention
- Audit logs: Configurable retention
- User data: Until account deletion
- Scan data: Configurable max age
- System logs: Application responsibility

### GDPR Considerations
- Audit logs include IP addresses
- User agent strings captured
- Data deletion when user deleted
- Export capabilities recommended

### Security Logging
- All admin actions logged
- Failed login attempts tracked
- Permission changes recorded
- System modifications audited

## Summary

Phase 3 successfully implements:
✅ Complete admin dashboard
✅ System settings management
✅ Comprehensive audit logging
✅ User activity monitoring
✅ Database models for tracking
✅ Secure admin-only access
✅ Migration tooling
✅ Documentation

The admin panel provides administrators with powerful tools to:
- Monitor system health
- Configure system behavior
- Track user activity
- Ensure security compliance
- Manage resources effectively

All features are production-ready and fully documented.
