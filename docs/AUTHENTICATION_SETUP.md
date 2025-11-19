# Authentication System Setup Guide - Phase 1

This guide covers the installation and setup of the user authentication system for KAST Web.

## Overview

Phase 1 implements core authentication features:
- User model with password hashing
- Login/logout functionality
- Session management
- Role-based access control (Admin, User, Viewer)
- User management (admin only)
- Profile and password change

## Installation Steps

### 1. Install New Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `Flask-Login` - Session management
- `Flask-Bcrypt` - Password hashing
- `email-validator` - Email validation
- `Flask-Migrate` - Database migrations (for future use)

### 2. Create the First Admin User

Run the admin user creation script:

```bash
python create_admin_user.py
```

Follow the prompts to create your first admin account:
- Username (3-80 characters)
- Email address
- First name (optional)
- Last name (optional)
- Password (minimum 8 characters)

The script will:
- Create the necessary database tables
- Create your admin user account
- Display a confirmation message

### 3. Start the Application

```bash
python run.py
```

Or with the async worker:

```bash
./scripts/start_async.sh
```

### 4. Test the Authentication

1. **Access the Login Page**: Navigate to `http://localhost:5000/auth/login`
2. **Log in**: Use the credentials you created
3. **Verify Access**: You should be redirected to the home page with a welcome message

## Features Overview

### User Roles

**Admin Role:**
- Full system access
- Create/edit/delete users
- View all scans (any user)
- Access admin panel
- No restrictions

**User Role:**
- Create and manage own scans
- View own scan history
- Edit own profile
- Change password
- Cannot access admin features

**Viewer Role:**
- Read-only access
- View shared scans only
- Cannot create or modify scans
- Limited access

### Available Routes

**Public Routes (no login required):**
- `/auth/login` - Login page

**Authenticated Routes (login required):**
- `/` - Home page
- `/auth/profile` - User profile
- `/auth/change-password` - Change password
- `/auth/logout` - Logout
- `/scans/*` - Scan management

**Admin-Only Routes:**
- `/auth/users` - User management
- `/auth/register` - Create new user
- `/auth/users/<id>/toggle-active` - Activate/deactivate user
- `/auth/users/<id>/delete` - Delete user

### Navigation Changes

The navigation bar now includes:

**For All Authenticated Users:**
- Home
- My Scans
- About
- User dropdown (Profile, Change Password, Logout)

**For Admin Users (additional):**
- Admin dropdown (User Management, Create User, All Scans)

## Testing Checklist

### Basic Authentication
- [ ] Can access login page
- [ ] Can log in with admin credentials
- [ ] Redirected to home page after successful login
- [ ] See welcome message with username
- [ ] Navigation shows user dropdown with admin badge
- [ ] Can access profile page
- [ ] Can change password
- [ ] Can log out successfully

### Admin Features
- [ ] Can access User Management page
- [ ] Can create new user (all roles: admin, user, viewer)
- [ ] Can view list of all users
- [ ] Can activate/deactivate users
- [ ] Can delete users (but not self)
- [ ] Admin dropdown shows in navigation

### User Management
- [ ] Created users receive correct role
- [ ] Username uniqueness enforced
- [ ] Email uniqueness enforced
- [ ] Password requirements enforced (min 8 chars)
- [ ] Inactive users cannot log in
- [ ] Failed login attempts tracked

### Security
- [ ] Cannot access /auth/register without admin role
- [ ] Cannot access /auth/users without admin role
- [ ] Cannot access scan pages without login
- [ ] Password is hashed in database
- [ ] Session persists across page reloads (if "Remember Me" checked)
- [ ] Session expires after logout

## Database Changes

### New Table: `users`

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME,
    last_login DATETIME,
    login_count INTEGER DEFAULT 0,
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login DATETIME
);
```

### Modified Table: `scans`

Added foreign key to link scans to users:

```sql
ALTER TABLE scans ADD COLUMN user_id INTEGER NOT NULL;
```

**Note:** Existing scans in your database will need to be associated with a user. This can be done by:
1. Running a migration script to assign all existing scans to the admin user
2. Or deleting existing scans and starting fresh

## Migration for Existing Installations

If you have existing scans in your database:

```bash
python migrate_db.py
```

This will:
- Add the `user_id` column to existing scans
- Assign all existing scans to the first admin user
- Ensure database integrity

## Troubleshooting

### Issue: "Cannot import name 'User' from 'app.models'"

**Solution:** Restart your Python interpreter or Flask dev server. The new models need to be loaded.

### Issue: "No such table: users"

**Solution:** Run `python create_admin_user.py` to create the database tables.

### Issue: "Cannot access /scans after login"

**Solution:** Existing scans need a `user_id`. Run the migration script or clear your database:
```bash
rm ~/kast-web/db/kast.db
python create_admin_user.py
```

### Issue: "Login page doesn't show styling"

**Solution:** Clear your browser cache or do a hard refresh (Ctrl+F5 / Cmd+Shift+R).

### Issue: "Remember Me doesn't work"

**Solution:** Check that cookies are enabled in your browser and that you're not in incognito/private mode.

## Next Steps (Future Phases)

Phase 1 is complete! Future phases will include:

**Phase 2:** Basic Authorization
- Scan ownership enforcement
- User can only see/edit own scans
- Permission decorators

**Phase 3:** Admin Panel Basics
- System settings interface
- Audit logging
- User activity tracking

**Phase 4:** Database Management
- Backup functionality
- Restore functionality
- Scheduled backups

**Phase 5:** Email System
- Email configuration
- Send scan results via email
- Email templates
- Email logging

## Security Best Practices

1. **Change Default Admin Password:** After first login, change the admin password via Profile > Change Password

2. **Use Strong Passwords:** Enforce minimum 12 characters for production use (edit in `config.py`)

3. **Regular Backups:** Back up your database regularly (especially the `users` table)

4. **HTTPS in Production:** Always use HTTPS in production to protect credentials

5. **Session Security:** Configure secure session cookies in production:
   ```python
   SESSION_COOKIE_SECURE = True
   SESSION_COOKIE_HTTPONLY = True
   SESSION_COOKIE_SAMESITE = 'Lax'
   ```

## Support

If you encounter issues:
1. Check the console/terminal for error messages
2. Review the Flask logs
3. Verify all dependencies are installed
4. Ensure Python 3.8+ is being used

