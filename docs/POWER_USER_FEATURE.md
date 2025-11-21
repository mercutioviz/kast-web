# Power User Feature Documentation

## Overview

The Power User feature introduces a new user role that has permission to run both active and passive scans. This provides a middle tier between standard users (passive scans only) and administrators (full system access).

## User Roles

The system now supports four user roles:

1. **Admin** - Full system access, can run active and passive scans
2. **Power User** - Can run both active and passive scans
3. **User** (Standard) - Can only run passive scans
4. **Viewer** - Read-only access

## Active Scan Permissions

### Who Can Run Active Scans?
- **Admin**: ✅ Yes
- **Power User**: ✅ Yes
- **User**: ❌ No
- **Viewer**: ❌ No

### Enforcement Points

1. **UI Level**: The active scan option is disabled (grayed out) for standard users and viewers
2. **Backend Level**: Server-side validation prevents unauthorized users from submitting active scans
3. **User Feedback**: Clear messaging explains why the option is unavailable

## Implementation Details

### Model Changes

**File: `app/models.py`**

Added new properties to the User model:
- `is_power_user`: Check if user has power_user role
- `can_run_active_scans`: Check if user can run active scans (admin or power_user)

```python
@property
def can_run_active_scans(self):
    """Check if user can run active scans"""
    return self.role in ('admin', 'power_user')
```

### Form Changes

**File: `app/forms.py`**

Updated the RegistrationForm to include power_user in role choices:
```python
role = SelectField(
    'Role',
    choices=[
        ('user', 'User - Can create and manage own scans (passive only)'),
        ('power_user', 'Power User - Can run active and passive scans'),
        ('admin', 'Admin - Full system access'),
        ('viewer', 'Viewer - Read-only access')
    ],
    ...
)
```

### Route Protection

**File: `app/routes/main.py`**

Added permission check in the scan creation route:
```python
if form.scan_mode.data == 'active' and not current_user.can_run_active_scans:
    flash('You do not have permission to run active scans...', 'danger')
    return redirect(url_for('main.index'))
```

### UI Changes

**File: `app/templates/index.html`**

1. Active scan option is disabled for unauthorized users
2. Warning message displays when users try to select the disabled option
3. Tooltip provides context on hover

## Migration

Run the migration script to see current role distribution:
```bash
python utils/migrate_power_user.py
```

Note: This migration doesn't modify existing users. The power_user role is available for:
- New user creation
- Existing user role updates via admin panel

## Upgrading Existing Users

To upgrade a standard user to power user:

1. Log in as an admin
2. Navigate to Admin Panel → Users
3. Click "Edit" on the user you want to upgrade
4. Change the "Role" dropdown from "User" to "Power User"
5. Save the changes

## User Experience

### For Standard Users

When a standard user accesses the scan form:
- The "Active" scan mode option appears but is disabled/grayed out
- If they attempt to select it, a warning message appears:
  > "This user is not allowed to run active scans. Only Power Users and Admins can run active scans."
- They can only create passive scans

### For Power Users

When a power user accesses the scan form:
- Both "Passive" and "Active" scan modes are fully available
- They can create either type of scan without restrictions

### For Admins

Admins have the same scanning capabilities as power users, plus:
- Full system administration access
- User management capabilities
- System settings management

## Security Considerations

1. **Defense in Depth**: Permission checks are enforced at multiple levels:
   - UI (prevents accidental attempts)
   - Backend (prevents malicious attempts)

2. **Clear Feedback**: Users understand why options are unavailable

3. **Role Separation**: Power users have scanning privileges without full admin access

## Testing

Test scenarios:
1. ✅ Standard user cannot select active scan mode
2. ✅ Standard user sees warning message when attempting active scan
3. ✅ Standard user blocked at backend if they bypass UI
4. ✅ Power user can select both passive and active modes
5. ✅ Admin can select both passive and active modes
6. ✅ Role can be changed via admin panel

## Future Enhancements

Potential improvements:
- Per-user active scan quotas
- Active scan scheduling restrictions
- Audit logging for active scan attempts
- Email notifications for active scan denials
