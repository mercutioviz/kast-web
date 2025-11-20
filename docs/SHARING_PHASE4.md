# Sharing & Collaboration - Phase 4 Implementation Plan

This document describes Phase 4 implementation: Scan Sharing and Collaboration features.

## Overview

Phase 4 adds collaboration features to allow users to share scans with others:
- **Direct User Sharing** - Share scans with specific users
- **Public Link Sharing** - Generate public links for anonymous access
- **Permission Levels** - Read-only vs. edit permissions
- **Ownership Transfer** - Transfer scan ownership to another user

## Database Schema Changes

### 1. New Table: scan_shares

```sql
CREATE TABLE scan_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    shared_with_user_id INTEGER,  -- NULL for public shares
    permission_level VARCHAR(20) NOT NULL,  -- 'view' or 'edit'
    share_token VARCHAR(64) UNIQUE,  -- For public link shares
    created_by INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    expires_at DATETIME,  -- NULL = never expires
    
    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);
```

### 2. Indexes

```sql
CREATE INDEX idx_scan_shares_scan_id ON scan_shares(scan_id);
CREATE INDEX idx_scan_shares_user_id ON scan_shares(shared_with_user_id);
CREATE INDEX idx_scan_shares_token ON scan_shares(share_token);
```

## Features

### 1. Direct User Sharing

**Share with Specific Users:**
- Select users from dropdown
- Choose permission level (view or edit)
- Optional expiration date
- Email notification to shared user (future)

**Permission Levels:**
- **View:** Can view scan details, report, and files
- **Edit:** Can also delete, regenerate report, and re-run scan

### 2. Public Link Sharing

**Generate Public Links:**
- Creates unique token (64-char random string)
- Accessible without login
- Optional expiration date
- Can be revoked anytime

**Public Link Features:**
- View-only access by default
- Shows limited UI (no edit options)
- Can be shared via email, Slack, etc.
- Trackable access (optional in future phases)

### 3. Ownership Transfer

**Transfer Ownership:**
- Admin or owner can transfer to another user
- All permissions are preserved
- Original owner loses access unless re-shared
- Audit log entry created

## UI Components

### 1. Scan Detail Page Additions

**Share Button:**
```html
<div class="btn-group">
    <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#shareModal">
        <i class="bi bi-share"></i> Share
    </button>
</div>
```

**Share Modal:**
- Tab 1: Share with Users
  - User selector
  - Permission dropdown
  - Expiration date picker
  - Share button
- Tab 2: Public Link
  - Generate link button
  - Copy link button
  - Expiration settings
  - Revoke button
- Tab 3: Current Shares (list of active shares)

### 2. Scan List Page Updates

**Shared Badge:**
```html
<span class="badge bg-info">
    <i class="bi bi-people"></i> Shared
</span>
```

**Shared With Me Filter:**
```html
<ul class="nav nav-tabs">
    <li><a href="?filter=mine">My Scans</a></li>
    <li><a href="?filter=shared">Shared With Me</a></li>
    <li><a href="?filter=all">All</a></li>
</ul>
```

### 3. Admin Features

**Scan Ownership Page:**
- View all scan shares
- Transfer ownership
- Revoke any share
- View share statistics

## API Endpoints

### Share Management

```python
POST   /scans/<id>/share/user          # Share with specific user
POST   /scans/<id>/share/public        # Generate public link
DELETE /scans/<id>/share/<share_id>   # Revoke share
GET    /scans/<id>/shares              # List all shares for scan
POST   /scans/<id>/transfer            # Transfer ownership
```

### Public Access

```python
GET    /shared/<token>                 # Access scan via public link
GET    /shared/<token>/report          # View report
GET    /shared/<token>/files           # List files
```

## Permission Checking

### Updated check_scan_access()

```python
def check_scan_access(scan, required_permission='view'):
    """
    Check if current user can access this scan
    
    Args:
        scan: Scan object
        required_permission: 'view' or 'edit'
    
    Returns:
        tuple: (has_access, permission_level)
    """
    # Admin always has full access
    if current_user.is_authenticated and current_user.is_admin:
        return (True, 'edit')
    
    # Owner always has full access
    if current_user.is_authenticated and scan.user_id == current_user.id:
        return (True, 'edit')
    
    # Check if shared with current user
    if current_user.is_authenticated:
        share = ScanShare.query.filter_by(
            scan_id=scan.id,
            shared_with_user_id=current_user.id
        ).first()
        
        if share and not share.is_expired():
            if required_permission == 'view' or share.permission_level == 'edit':
                return (True, share.permission_level)
    
    return (False, None)
```

### Public Link Access

```python
def check_public_link_access(token):
    """Check if public link is valid"""
    share = ScanShare.query.filter_by(
        share_token=token,
        shared_with_user_id=None  # Public share
    ).first()
    
    if share and not share.is_expired():
        return (True, share.scan)
    
    return (False, None)
```

## Implementation Steps

### Step 1: Database Models

Create `ScanShare` model in `app/models.py`:

```python
class ScanShare(db.Model):
    __tablename__ = 'scan_shares'
    
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), nullable=False)
    shared_with_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    permission_level = db.Column(db.String(20), nullable=False)
    share_token = db.Column(db.String(64), unique=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    
    # Relationships
    scan = db.relationship('Scan', backref='shares')
    shared_with_user = db.relationship('User', foreign_keys=[shared_with_user_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def is_expired(self):
        """Check if share has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_public(self):
        """Check if this is a public share"""
        return self.shared_with_user_id is None
    
    @staticmethod
    def generate_token():
        """Generate unique share token"""
        import secrets
        return secrets.token_urlsafe(48)
```

### Step 2: Routes

Create sharing routes in `app/routes/scans.py` or new `app/routes/sharing.py`

### Step 3: Forms

Create sharing forms in `app/forms.py`:

```python
class ShareWithUserForm(FlaskForm):
    user_id = SelectField('User', coerce=int, validators=[DataRequired()])
    permission_level = SelectField('Permission', choices=[
        ('view', 'View Only'),
        ('edit', 'Can Edit')
    ])
    expires_in_days = IntegerField('Expires in (days)', default=0)
    submit = SubmitField('Share')

class GeneratePublicLinkForm(FlaskForm):
    expires_in_days = IntegerField('Expires in (days)', default=7)
    submit = SubmitField('Generate Link')

class TransferOwnershipForm(FlaskForm):
    new_owner_id = SelectField('New Owner', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Transfer')
```

### Step 4: Templates

Create sharing UI components:
- Share modal
- Shared scans list
- Public link viewer

### Step 5: Migration

Create migration script `migrate_phase4.py`

## Security Considerations

### 1. Token Security
- Use cryptographically secure random tokens
- Store hashed tokens in database (optional)
- Validate token format before queries

### 2. Permission Validation
- Always check permissions on server-side
- Never trust client-side permission checks
- Validate expiration on every access

### 3. Audit Logging
- Log all share creations
- Log all share deletions
- Log ownership transfers
- Log public link access

### 4. Rate Limiting
- Limit public link creation per user
- Limit share operations per day
- Prevent abuse of public links

## Testing Phase 4

### Test User Sharing

1. **Share scan with another user:**
   - User A shares scan with User B (view permission)
   - User B logs in, sees scan in "Shared With Me"
   - User B can view but not edit
   - User A changes permission to edit
   - User B can now edit

2. **Expiration:**
   - User A shares with expiration date
   - Verify access before expiration
   - Verify no access after expiration

3. **Revoke access:**
   - User A shares scan
   - User A revokes share
   - User B loses access immediately

### Test Public Links

1. **Generate public link:**
   - User creates public link
   - Copy link and open in incognito window
   - Should see scan without login
   - Should see view-only interface

2. **Expiration:**
   - Create link with 1-day expiration
   - Verify works immediately
   - Advance system time or wait
   - Verify link expires

3. **Revoke:**
   - Create public link
   - Share with someone
   - Revoke link
   - Verify access denied

### Test Ownership Transfer

1. **Transfer to another user:**
   - User A transfers scan to User B
   - User B becomes owner
   - User A loses access (unless re-shared)
   - Verify in database

2. **Admin transfer:**
   - Admin transfers scan between users
   - Verify both users updated
   - Check audit log

## Future Enhancements

### Phase 5: Advanced Sharing
- Team/group sharing
- Share with multiple users at once
- Bulk sharing operations
- Share templates

### Phase 6: Notifications
- Email notifications on share
- In-app notifications
- Share activity feed
- Digest emails

### Phase 7: Analytics
- Track who viewed what
- Download statistics
- Most shared scans
- Share analytics dashboard

## Summary

Phase 4 will implement:
- ✅ Share scans with specific users
- ✅ Generate public links for anonymous access
- ✅ Permission levels (view vs. edit)
- ✅ Ownership transfer
- ✅ Expiration dates
- ✅ Share management UI
- ✅ Audit logging for all sharing actions

This creates a complete collaboration system while maintaining security and proper access control.
