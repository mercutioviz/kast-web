# Maintenance Mode Enforcement

## Overview
This document describes the implementation of maintenance mode enforcement that restricts login access to admin users only when maintenance mode is active.

## Implementation Details

### Changes Made
Modified `app/routes/auth.py` to enforce maintenance mode restrictions during login:

1. **Import Added**: Added `SystemSettings` model import
2. **Maintenance Check**: Added validation after user authentication and before login to check if maintenance mode is active
3. **Admin-Only Access**: Only users with `role='admin'` can log in when maintenance mode is enabled
4. **User Feedback**: Non-admin users receive a clear message explaining the system is in maintenance mode

### Code Location
File: `app/routes/auth.py`
Function: `login()`
Lines: After active account check, before successful login

### Logic Flow
```python
# After password and account status validation:
1. Check if maintenance_mode setting is enabled
2. If enabled AND user is not admin:
   - Display warning message
   - Redirect back to login page
   - Prevent login
3. If maintenance_mode is disabled OR user is admin:
   - Proceed with normal login
```

## How It Works

### For Admin Users
- Can log in regardless of maintenance mode status
- Full access to all system features including the admin panel
- Can toggle maintenance mode on/off from `/admin/settings`

### For Normal Users
- Cannot log in when maintenance mode is active
- Receive message: "The system is currently in maintenance mode. Only administrators can log in at this time. Please try again later."
- Can log in normally once maintenance mode is disabled

## Testing

### Enable Maintenance Mode
1. Log in as an admin user
2. Navigate to Admin Panel → Settings (`/admin/settings`)
3. Enable "Maintenance Mode" checkbox
4. Save settings

### Test Non-Admin Login
1. Log out
2. Try to log in with a non-admin account
3. Should see maintenance mode warning and be unable to log in

### Test Admin Login
1. Log in with an admin account
2. Should be able to log in successfully
3. Can disable maintenance mode from settings

### Disable Maintenance Mode
1. As admin, navigate to Settings
2. Disable "Maintenance Mode" checkbox
3. Save settings
4. Normal users can now log in again

## Security Considerations
- Maintenance mode check happens after password validation but before session creation
- Failed login attempts are still tracked even during maintenance mode
- Admin users retain full access to ensure system can be managed during maintenance
- Setting is stored in database and persists across server restarts

## Related Files
- `app/routes/auth.py` - Login logic with maintenance mode check
- `app/routes/admin.py` - Admin settings management
- `app/models.py` - SystemSettings model for storing configuration
- `app/templates/admin/settings.html` - UI for toggling maintenance mode
