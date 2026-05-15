# Authorization System - Phase 2: Scan Ownership

This document describes Phase 2 implementation: Basic Authorization and Scan Ownership enforcement.

## Overview

Phase 2 builds on Phase 1 (Authentication) by implementing authorization controls:
- Users can only view and manage their own scans
- Admins can view and manage all scans
- All scan operations are protected with ownership checks
- New scans are automatically assigned to the creator

## Changes Implemented

### 1. Route Protection (app/routes/scans.py)

**Added `@login_required` decorator to all routes:**
- `/scans/` - List scans
- `/scans/<id>` - View scan details
- `/scans/<id>/delete` - Delete scan
- `/scans/<id>/report` - View report
- `/scans/<id>/download` - Download report
- `/scans/<id>/files` - List scan files
- `/scans/<id>/view-file/<path>` - View individual files
- `/scans/<id>/regenerate-report` - Regenerate report
- `/scans/<id>/rerun` - Re-run scan

**Added `check_scan_access()` function:**
```python
def check_scan_access(scan):
    """Check if current user can access this scan"""
    if current_user.is_admin:
        return True
    return scan.user_id == current_user.id
```

This function is called before any scan operation to verify permissions.

### 2. Query Filtering

**Scan List Route:**
- Regular users: Only see their own scans
- Admin users: See all scans

```python
if current_user.is_admin:
    query = Scan.query
else:
    query = Scan.query.filter_by(user_id=current_user.id)
```

**Home Page (app/routes/main.py):**
- Recent scans shown are filtered by user
- Admins see all recent scans
- Regular users see only their recent scans

### 3. Scan Creation

**Updated scan creation to assign owner:**
```python
scan = Scan(
    user_id=current_user.id,  # Automatically assigned to current user
    target=form.target.data,
    # ... other fields
)
```

### 4. UI Updates

**Scan History Table (app/templates/scan_history.html):**
- Added "Owner" column (visible only to admins)
- Shows username of scan owner
- Displays "You" badge for admin's own scans

**Navigation (app/templates/base.html):**
- "My Scans" link for regular users
- "All Scans" option in admin dropdown

## Permission Matrix

| Action | Regular User (Own Scan) | Regular User (Other's Scan) | Admin |
|--------|------------------------|----------------------------|-------|
| View scan list | ✅ Own scans only | ❌ Hidden | ✅ All scans |
| View scan details | ✅ Yes | ❌ No | ✅ Yes |
| View report | ✅ Yes | ❌ No | ✅ Yes |
| Download report | ✅ Yes | ❌ No | ✅ Yes |
| Regenerate report | ✅ Yes | ❌ No | ✅ Yes |
| Re-run scan | ✅ Yes | ❌ No | ✅ Yes |
| Delete scan | ✅ Yes | ❌ No | ✅ Yes |
| Create scan | ✅ Yes (assigned to self) | N/A | ✅ Yes (assigned to self) |

## Security Features

### 1. Access Control
- All routes require authentication (`@login_required`)
- Ownership checked before any scan operation
- HTTP 403 (Forbidden) returned for unauthorized access
- HTTP 404 (Not Found) for scans that don't exist

### 2. Data Isolation
- Users cannot see other users' scans in lists
- Direct URL access to other users' scans is blocked
- File downloads are restricted to scan owners
- Report viewing is restricted to scan owners

### 3. Admin Privileges
- Admins bypass all ownership checks
- Admins can view/manage any scan
- Useful for troubleshooting and support
- Admin status clearly indicated in UI

## Testing Phase 2

### Test as Regular User

1. **Create a scan:**
   ```
   - Log in as regular user
   - Create a new scan from home page
   - Verify scan is created and assigned to you
   ```

2. **View own scans:**
   ```
   - Navigate to "My Scans"
   - Verify you only see your own scans
   - Click on a scan to view details
   - View report (if completed)
   ```

3. **Attempt unauthorized access:**
   ```
   - Try to access another user's scan by ID (e.g., /scans/1)
   - Should see "You do not have permission" message
   - Should be redirected to your scan list
   ```

4. **Scan operations:**
   ```
   - Delete your own scan - should work
   - Re-run your own scan - should work
   - Regenerate report - should work
   ```

### Test as Admin

1. **View all scans:**
   ```
   - Log in as admin
   - Navigate to "Admin" → "All Scans"
   - Verify you see scans from all users
   - "Owner" column shows username for each scan
   ```

2. **Access any scan:**
   ```
   - Click on scans from different users
   - View details, reports, files
   - All operations should work
   ```

3. **Create scan:**
   ```
   - Create a new scan
   - Verify it's assigned to you
   - Verify it appears in the scan list
   ```

### Test Permission Boundaries

1. **Create test users:**
   ```bash
   # As admin, create two regular users:
   - user1 / user1@example.com
   - user2 / user2@example.com
   ```

2. **Create scans as each user:**
   ```
   - Log in as user1, create 2-3 scans
   - Log in as user2, create 2-3 scans
   ```

3. **Verify isolation:**
   ```
   - Log in as user1
   - Should only see user1's scans
   - Try direct URL to user2's scan
   - Should be denied access
   ```

4. **Verify admin access:**
   ```
   - Log in as admin
   - Should see all scans from both users
   - Can access any scan
   - Owner column shows correct usernames
   ```

## API Endpoints Protected

All these endpoints now require authentication and check ownership:

```
GET    /scans                        - List scans (filtered)
GET    /scans/<id>                   - View scan (checked)
POST   /scans/<id>/delete            - Delete scan (checked)
GET    /scans/<id>/report            - View report (checked)
GET    /scans/<id>/download          - Download report (checked)
GET    /scans/<id>/files             - List files (checked)
GET    /scans/<id>/view-file/<path>  - View file (checked)
POST   /scans/<id>/regenerate-report - Regenerate (checked)
POST   /scans/<id>/rerun             - Re-run scan (checked)
GET    /scans/<id>/<path>            - Serve assets (checked)
```

## Error Handling

### 403 Forbidden
Returned when user tries to access a scan they don't own:
- Direct URL access to other user's scan
- File downloads from other user's scan
- Report viewing from other user's scan

### 404 Not Found
Returned when:
- Scan ID doesn't exist
- Scan exists but user has no access (obscures existence)

### Redirect with Flash Message
Used for:
- Unauthorized access attempts
- Missing resources
- Form validation errors

## Database Considerations

### Existing Data
- All existing scans were migrated to admin user (mscollins)
- Migration script: `migrate_existing_db.py`
- All scans now have required `user_id`

### Constraints
- `user_id` is required (NOT NULL)
- Foreign key relationship enforced
- Cascade delete: Deleting user deletes their scans

## Future Enhancements

### Phase 3: Admin Panel Basics
- System settings management
- Audit logging
- User activity tracking
- Scan statistics per user

### Phase 4: Sharing & Collaboration
- Share scans with specific users
- Share scans via public link
- Read-only vs. edit permissions
- Scan ownership transfer

### Phase 5: Advanced Authorization
- Role-based permissions (custom roles)
- Organization/team support
- Scan quotas per user
- Rate limiting per user

## Troubleshooting

### Issue: Can't see any scans after upgrade

**Cause:** Scans not assigned to any user (missing user_id)

**Solution:**
```bash
python migrate_existing_db.py
```

### Issue: "You do not have permission" for own scans

**Cause:** Session issue or user_id mismatch

**Solution:**
1. Log out and log back in
2. Check database: `SELECT id, target, user_id FROM scans;`
3. Verify your user ID matches scan user_id

### Issue: Admin can't see "Owner" column

**Cause:** Template caching or not logged in as admin

**Solution:**
1. Hard refresh browser (Ctrl+F5)
2. Verify admin status: Check for admin badge in navbar
3. Check database: `SELECT username, role FROM users WHERE id = X;`

### Issue: New scans not assigned to user

**Cause:** Code not updated or session expired

**Solution:**
1. Verify `app/routes/main.py` has `user_id=current_user.id`
2. Restart Flask server
3. Clear browser cookies and re-login

## Security Best Practices

1. **Never expose user IDs in URLs** - Use opaque tokens for sharing if needed
2. **Always check ownership** - Even if UI hides links, validate on server
3. **Log access attempts** - Track unauthorized access for security monitoring
4. **Consistent error messages** - Don't reveal existence of resources user can't access
5. **Test with multiple users** - Always verify isolation between users

## Summary

Phase 2 successfully implements:
✅ Scan ownership enforcement
✅ User-based access control  
✅ Admin bypass for all operations
✅ Query filtering by user
✅ UI updates showing ownership
✅ Comprehensive permission checks
✅ Secure error handling

