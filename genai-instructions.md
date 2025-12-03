# GenAI Instructions for KAST-Web Project

## Project Overview

**KAST-Web** is a web-based interface for the Kali Automated Scan Tool (KAST), providing an intuitive way to configure, execute, and manage security scans through a browser. The application features asynchronous scan execution with real-time progress tracking, comprehensive user authentication with role-based access control, email notifications, scan sharing capabilities, and extensive administrative controls.

**Version:** 1.0.0  
**Primary Language:** Python 3.8+  
**Working Directory:** `/opt/kast-web`  
**Database Location:** `~/kast-web/db/kast.db` (SQLite default)  
**Scan Results Directory:** `~/kast_results/`

## Technology Stack

### Backend
- **Flask** - Python web framework with blueprint-based routing
- **SQLAlchemy** - ORM for database operations
- **SQLite** - Default database (PostgreSQL/MySQL supported for production)
- **WTForms** - Form handling and validation
- **Celery** - Asynchronous task queue for background scan execution and email sending
- **Redis** - Message broker for Celery
- **Flask-Login** - User session management and authentication
- **Flask-Bcrypt** - Password hashing
- **email-validator** - Email address validation
- **Flask-SocketIO** - Real-time communication support (installed but not fully utilized)
- **Gunicorn** - WSGI HTTP server for production

### Frontend
- **Bootstrap 5** - UI framework
- **Bootstrap Icons** - Icon library
- **Jinja2** - Template engine
- **JavaScript (Vanilla)** - Client-side interactivity with polling-based updates

### External Dependencies
- **KAST CLI** - Security scanning tool (must be installed at `/usr/local/bin/kast`)
- **Redis Server** - Required for Celery task queue

## Architecture & Structure

### Application Factory Pattern
The application uses Flask's application factory pattern (`app/__init__.py`) with configuration profiles (development, production, testing).

### Blueprint Organization
Routes are organized by feature into separate blueprints:
- `app/routes/main.py` - Home page and core scan functionality
- `app/routes/scans.py` - Scan management (history, detail, files, sharing, email)
- `app/routes/api.py` - RESTful API endpoints
- `app/routes/auth.py` - Authentication and user management
- `app/routes/admin.py` - Admin panel, system settings, database explorer, SMTP configuration
- `app/routes/logos.py` - Logo management for white-labeling

### Database Models
Located in `app/models.py`:

#### User
User accounts with comprehensive authentication and role-based permissions.
- **Roles:** `admin`, `power_user`, `user`, `viewer`
- **Fields:** id, username, email, password_hash, first_name, last_name, role, is_active, created_at, last_login, login_count, failed_login_attempts, last_failed_login
- **Key Methods:** `set_password()`, `check_password()`, `is_admin`, `is_power_user`, `can_run_active_scans`
- **Relationships:** One-to-many with Scan, AuditLog

#### Scan
Scan configuration and metadata.
- **Fields:** id, user_id, target, scan_mode, plugins, parallel, verbose, dry_run, status, output_dir, config_json, error_message, celery_task_id, started_at, completed_at, logo_id
- **Status Values:** `pending`, `running`, `completed`, `failed`
- **Properties:** `duration`, `plugin_list`
- **Relationships:** Belongs to User, one-to-many with ScanResult, one-to-many with ScanShare, optional belongs to ReportLogo

#### ScanResult
Individual plugin results per scan.
- **Fields:** id, scan_id, plugin_name, status, findings_count, raw_output_path, processed_output_path, error_message, executed_at
- **Status Values:** `success`, `fail`, `skipped`
- **Relationships:** Belongs to Scan

#### AuditLog
System audit trail for security and compliance.
- **Fields:** id, user_id, action, resource_type, resource_id, details, ip_address, user_agent, timestamp
- **Static Method:** `AuditLog.log()` - Convenience method for creating log entries
- **Relationships:** Belongs to User
- **Common Actions:** scan_created, scan_deleted, user_created, user_deleted, settings_updated, email_sent, share_created, logo_uploaded

#### ScanShare
Scan sharing (user-to-user and public links).
- **Fields:** id, scan_id, shared_with_user_id, permission_level, share_token, created_by, created_at, expires_at
- **Permission Levels:** `view`, `edit`
- **Share Types:** User-to-user (shared_with_user_id populated), Public link (shared_with_user_id is NULL)
- **Methods:** `is_expired()`, `is_public()`, `generate_token()` (static)
- **Relationships:** Belongs to Scan, optionally belongs to User (shared_with_user), belongs to User (creator)

#### ReportLogo
Custom logos for white-labeled reports.
- **Fields:** id, name, description, filename, file_path, mime_type, file_size, uploaded_by, uploaded_at
- **Storage Location:** `app/static/uploads/logos/`
- **Relationships:** Belongs to User (uploader), one-to-many with Scan

#### SystemSettings
Key-value store for system-wide configuration.
- **Fields:** id, key, value, value_type, description, updated_at, updated_by
- **Value Types:** `string`, `int`, `bool`, `json`
- **Static Methods:**
  - `get_settings()` - Returns all settings as dictionary
  - `get_setting(key, default=None)` - Returns single setting value
  - `set_setting(key, value, value_type, description, user_id)` - Sets single setting
  - `update_settings(settings_dict, user_id)` - Updates multiple settings at once
- **Common Settings:** maintenance_mode, email_enabled, smtp_host, smtp_port, smtp_username, smtp_password, use_tls, use_ssl, from_email, from_name

### Asynchronous Architecture
- **Celery Worker** (`celery_worker.py`) executes scans and sends emails asynchronously
- **Redis** acts as message broker between Flask and Celery
- **Task Flow:** Form submission → Database record → Celery task queued → Worker executes → Status updates → Results stored
- **Status Polling:** Frontend polls `/api/scans/<id>/status` endpoint for real-time updates

## Code Standards & Conventions

### Python Style
- Follow **PEP 8** style guidelines
- Use **4 spaces** for indentation (never tabs)
- Maximum line length: **79 characters** (99 for comments/docstrings acceptable)
- Use **snake_case** for functions, methods, and variables
- Use **PascalCase** for class names
- Use **UPPER_CASE** for constants

### Import Organization
```python
# Standard library imports
import os
from datetime import datetime

# Third-party imports
from flask import Blueprint, render_template, request
from sqlalchemy import func
from flask_login import login_required, current_user

# Local application imports
from app import db
from app.models import Scan, User, AuditLog
from app.utils import admin_required, power_user_required
```

### Docstrings
Use descriptive docstrings for all functions, classes, and modules:
```python
def process_scan_results(scan_id):
    """
    Process and parse scan results for display.
    
    Args:
        scan_id (int): The ID of the scan to process
        
    Returns:
        dict: Processed scan data with plugin results
        
    Raises:
        ValueError: If scan_id is invalid
    """
```

### Naming Conventions
- **Routes:** Use lowercase with hyphens (e.g., `/scan-history`, `/api/scans`)
- **Templates:** Use lowercase with underscores (e.g., `scan_detail.html`, `report_viewer.html`)
- **Functions:** Use descriptive verb-noun combinations (e.g., `get_scan_status()`, `parse_plugin_output()`)
- **Database Columns:** Use snake_case (e.g., `created_at`, `celery_task_id`)

## Authentication & Authorization

### User Roles & Permissions

KAST-Web implements a comprehensive role-based access control system with four roles:

#### Admin Role
- **Full system access** - All permissions
- Create, edit, delete all users
- View and manage all scans (any user)
- Access admin panel and system settings
- Configure SMTP and email settings
- Access database explorer
- Enable/disable maintenance mode
- View complete audit logs
- Upload and manage logos
- No restrictions on any functionality

#### Power User Role
- **Enhanced scanning privileges**
- Can run **active scans** (security testing)
- Create and manage own scans
- View own scan history
- Share scans with others
- Send reports via email
- Upload logos for own reports
- Edit own profile and change password
- Cannot access admin features
- Cannot view other users' scans (unless shared)

#### User Role (Standard)
- **Basic scanning privileges**
- Can run **passive scans only** (reconnaissance)
- Create and manage own scans
- View own scan history
- Share scans with others
- Send reports via email
- Edit own profile and change password
- Cannot run active scans
- Cannot access admin features
- Cannot view other users' scans (unless shared)

#### Viewer Role
- **Read-only access**
- View scans shared with them
- Cannot create or modify scans
- Cannot run any scans
- Limited profile access
- No administrative functions

### Authentication System

#### Login & Session Management
Use Flask-Login decorators and utilities:
```python
from flask_login import login_required, current_user, login_user, logout_user

@bp.route('/scans')
@login_required
def scan_history():
    """Only authenticated users can access"""
    scans = Scan.query.filter_by(user_id=current_user.id).all()
    return render_template('scan_history.html', scans=scans)
```

#### Password Security
- Passwords hashed using Flask-Bcrypt
- Minimum 8 characters (configurable)
- Failed login attempt tracking
- Account lockout after repeated failures
- Password change functionality with current password verification

#### Role-Based Access Control
Use custom decorators from `app/utils.py`:
```python
from app.utils import admin_required, power_user_required

@bp.route('/admin/settings')
@admin_required
def admin_settings():
    """Only admins can access"""
    pass

@bp.route('/scan/create')
@login_required
def create_scan():
    """Check active scan permission"""
    if form.scan_mode.data == 'active' and not current_user.can_run_active_scans:
        flash('Active scans require power user or admin privileges', 'error')
        return redirect(url_for('main.index'))
    # Proceed with scan creation
```

#### Permission Checking Patterns
Always verify user permissions before allowing actions:
```python
# Check scan ownership
scan = Scan.query.get_or_404(scan_id)
if scan.user_id != current_user.id and not current_user.is_admin:
    abort(403)

# Check scan access (with sharing)
if not (scan.user_id == current_user.id or 
        current_user.is_admin or 
        has_shared_access(scan, current_user)):
    abort(403)

# Check active scan permission
if scan_mode == 'active' and not current_user.can_run_active_scans:
    abort(403)
```

### Audit Logging
Log all significant actions for security and compliance:
```python
from app.models import AuditLog

# Log scan creation
AuditLog.log(
    user_id=current_user.id,
    action='scan_created',
    resource_type='scan',
    resource_id=scan.id,
    details=f'Target: {scan.target}, Mode: {scan.scan_mode}',
    ip_address=request.remote_addr,
    user_agent=request.headers.get('User-Agent')
)

# Log user deletion
AuditLog.log(
    user_id=current_user.id,
    action='user_deleted',
    resource_type='user',
    resource_id=user.id,
    details=f'Deleted user: {user.username}',
    ip_address=request.remote_addr,
    user_agent=request.headers.get('User-Agent')
)

# Log email sent
AuditLog.log(
    user_id=current_user.id,
    action='email_sent',
    resource_type='scan',
    resource_id=scan.id,
    details=f'Report sent to {len(recipients)} recipient(s)',
    ip_address=request.remote_addr,
    user_agent=request.headers.get('User-Agent')
)
```

## Key Features & Implementation Patterns

### 1. Asynchronous Scan Execution
**Location:** `app/tasks.py`
```python
# Celery task pattern
@celery.task(bind=True)
def run_scan_task(self, scan_id):
    """Background task for scan execution"""
    scan = Scan.query.get(scan_id)
    scan.status = 'running'
    db.session.commit()
    
    # Execute scan...
    # Update status and results...
```

### 2. Real-Time Status Updates
**Pattern:** Polling-based (not WebSocket)
- Frontend polls `/api/scans/<id>/status` every 2-5 seconds
- Endpoint returns current status and per-plugin progress
- JavaScript updates UI dynamically

### 3. Form Validation
**Location:** `app/forms.py`
```python
from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SelectField
from wtforms.validators import DataRequired, ValidationError, Email

class ScanForm(FlaskForm):
    target = StringField('Target', validators=[DataRequired()])
    scan_mode = SelectField('Scan Mode', choices=[('passive', 'Passive'), ('active', 'Active')])
    
    def validate_target(self, field):
        # Custom validation logic
        pass

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
```

### 4. Template Inheritance
**Base Template:** `app/templates/base.html`
```jinja2
{% extends "base.html" %}
{% block title %}Scan History{% endblock %}
{% block content %}
    <!-- Page-specific content -->
{% endblock %}
```

### 5. API Endpoints
**Pattern:** RESTful design with JSON responses
```python
@api_bp.route('/api/scans/<int:scan_id>', methods=['GET'])
@login_required
def get_scan(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    # Check permissions...
    if scan.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    return jsonify(scan.to_dict()), 200
```

### 6. Email System
**Location:** `app/email.py`, `app/tasks.py`

#### SMTP Configuration
Stored in SystemSettings, managed via admin panel:
```python
from app.models import SystemSettings

# Get email settings
email_enabled = SystemSettings.get_setting('email_enabled', False)
smtp_host = SystemSettings.get_setting('smtp_host')
smtp_port = SystemSettings.get_setting('smtp_port', 587)
use_tls = SystemSettings.get_setting('use_tls', True)

# Update settings
SystemSettings.set_setting('smtp_host', 'smtp.gmail.com', 'string', user_id=current_user.id)
```

#### Sending Emails
```python
# Queue email task (async)
from app.tasks import send_report_email_task

task = send_report_email_task.delay(
    scan_id=scan.id,
    recipients=['user@example.com'],
    user_id=current_user.id
)

# Returns task ID for tracking
flash(f'Email queued for delivery to {len(recipients)} recipient(s)', 'success')
```

#### Email Validation
```python
from email_validator import validate_email, EmailNotValidError

try:
    valid = validate_email(email_address)
    email = valid.email  # normalized form
except EmailNotValidError as e:
    flash(f'Invalid email: {str(e)}', 'error')
```

### 7. Logo White-Labeling
**Feature:** Custom logos for reports

#### Upload Logo
```python
@logos_bp.route('/logos/upload', methods=['POST'])
@login_required
def upload_logo():
    if 'logo_file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['logo_file']
    # Validate file type, size
    # Generate unique filename
    # Save to app/static/uploads/logos/
    # Create ReportLogo database record
    
    logo = ReportLogo(
        name=form.name.data,
        description=form.description.data,
        filename=unique_filename,
        file_path=file_path,
        mime_type=file.content_type,
        file_size=os.path.getsize(file_path),
        uploaded_by=current_user.id
    )
    db.session.add(logo)
    db.session.commit()
```

#### Associate Logo with Scan
```python
scan = Scan(
    target=target,
    scan_mode=mode,
    logo_id=selected_logo_id,  # NULL = use system default
    user_id=current_user.id
)
```

### 8. Scan Sharing
**Two Types:** User-to-user and public links

#### Share with Specific User
```python
from app.models import ScanShare

share = ScanShare(
    scan_id=scan.id,
    shared_with_user_id=target_user.id,
    permission_level='view',  # or 'edit'
    created_by=current_user.id,
    expires_at=expiration_date  # Optional
)
db.session.add(share)
db.session.commit()
```

#### Create Public Share Link
```python
share = ScanShare(
    scan_id=scan.id,
    shared_with_user_id=None,  # NULL for public
    permission_level='view',
    share_token=ScanShare.generate_token(),
    created_by=current_user.id,
    expires_at=expiration_date  # Optional
)
db.session.add(share)
db.session.commit()

# Share URL: /scans/shared/{share_token}
```

#### Check Share Access
```python
def can_access_scan(scan, user):
    """Check if user can access scan"""
    # Owner can always access
    if scan.user_id == user.id:
        return True
    
    # Admin can access all
    if user.is_admin:
        return True
    
    # Check if shared with user
    share = ScanShare.query.filter_by(
        scan_id=scan.id,
        shared_with_user_id=user.id
    ).first()
    
    if share and not share.is_expired():
        return True
    
    return False
```

### 9. Admin Panel & System Settings
**Location:** `app/routes/admin.py`

#### System Settings Management
```python
@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """Admin panel settings page"""
    if request.method == 'POST':
        # Update settings
        settings_dict = {
            'maintenance_mode': request.form.get('maintenance_mode') == 'on',
            'email_enabled': request.form.get('email_enabled') == 'on',
            'smtp_host': request.form.get('smtp_host'),
            'smtp_port': int(request.form.get('smtp_port', 587))
        }
        SystemSettings.update_settings(settings_dict, user_id=current_user.id)
        
        # Log settings change
        AuditLog.log(
            user_id=current_user.id,
            action='settings_updated',
            resource_type='system',
            details='System settings updated',
            ip_address=request.remote_addr
        )
        
        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin.settings'))
    
    # Load current settings
    settings = SystemSettings.get_settings()
    return render_template('admin/settings.html', settings=settings)
```

#### Maintenance Mode
```python
# Check in before_request handler
@app.before_request
def check_maintenance_mode():
    """Block access if maintenance mode is enabled"""
    maintenance_mode = SystemSettings.get_setting('maintenance_mode', False)
    
    if maintenance_mode:
        # Allow admins through
        if current_user.is_authenticated and current_user.is_admin:
            return None
        
        # Allow auth routes for login
        if request.endpoint and request.endpoint.startswith('auth.'):
            return None
        
        # Block everyone else
        return render_template('maintenance.html'), 503
```

### 10. Database Explorer
**Location:** `app/admin_db.py`, admin panel

#### Execute Raw SQL Queries (Admin Only)
```python
from app.admin_db import execute_query

@admin_bp.route('/admin/database', methods=['GET', 'POST'])
@admin_required
def database_explorer():
    """Database explorer for admins"""
    if request.method == 'POST':
        query = request.form.get('query')
        
        # Log query execution
        AuditLog.log(
            user_id=current_user.id,
            action='database_query',
            resource_type='system',
            details=f'Executed query: {query[:100]}',
            ip_address=request.remote_addr
        )
        
        try:
            results = execute_query(query)
            return render_template('admin/db_results.html', results=results)
        except Exception as e:
            flash(f'Query error: {str(e)}', 'error')
    
    return render_template('admin/database.html')
```

**IMPORTANT:** Database explorer should be used with extreme caution. Always backup database before running queries.

## Database Patterns & Relationships

### User Roles & Permissions
```python
# Roles: admin, power_user, user, viewer
user.is_admin           # Full system access
user.is_power_user      # Enhanced privileges
user.can_run_active_scans  # admin or power_user only
```

### Key Relationships
- `User.scans` - One-to-many (user has many scans)
- `User.audit_logs` - One-to-many (user has many audit log entries)
- `Scan.user` - Many-to-one (scan belongs to user)
- `Scan.results` - One-to-many (scan has many plugin results)
- `Scan.shares` - One-to-many (scan can be shared multiple times)
- `Scan.logo` - Many-to-one (scan optionally belongs to logo)
- `ScanResult.scan` - Many-to-one (result belongs to scan)
- `ScanShare.scan` - Many-to-one (share belongs to scan)
- `ScanShare.shared_with_user` - Many-to-one (share optionally belongs to user)
- `ScanShare.creator` - Many-to-one (share belongs to creator)
- `AuditLog.user` - Many-to-one (log entry belongs to user)
- `ReportLogo.uploader` - Many-to-one (logo belongs to uploader)

### Scan Status Flow
```
pending → running → completed
                 → failed
```

### Query Patterns
Always use SQLAlchemy ORM, not raw SQL (except in admin database explorer):
```python
# Good
scan = Scan.query.get_or_404(scan_id)
scans = Scan.query.filter_by(user_id=user.id, status='completed').order_by(Scan.started_at.desc()).all()

# Also Good - for complex queries
from sqlalchemy import func
stats = db.session.query(
    func.count(Scan.id).label('total'),
    func.sum(db.case((Scan.status == 'completed', 1), else_=0)).label('completed')
).first()

# Good - with joins
from sqlalchemy.orm import joinedload
scans = Scan.query.options(joinedload(Scan.user)).filter_by(status='running').all()

# Good - checking permissions
scan = Scan.query.get_or_404(scan_id)
if scan.user_id != current_user.id and not current_user.is_admin:
    abort(403)
```

## Critical Constraints & Requirements

### 1. Celery Worker Must Be Running
**Requirement:** Celery worker must be active for scans and emails to execute.
- Scans will remain in "pending" status if worker is down
- Emails won't be sent if worker is down
- Start worker: `celery -A celery_worker.celery worker --loglevel=info`
- Check status: `celery -A celery_worker.celery inspect active`
- Production: `sudo systemctl status kast-celery`

### 2. Redis Dependency
**Requirement:** Redis must be running for task queue.
- Start Redis: `sudo systemctl start redis-server`
- Test connection: `redis-cli ping` (should return "PONG")
- Configuration: `CELERY_BROKER_URL` in config

### 3. KAST CLI Tool
**Requirement:** KAST CLI must be installed and executable.
- Default path: `/usr/local/bin/kast`
- Configurable via `KAST_CLI_PATH` environment variable
- Test: `kast --list-plugins`

### 4. File Permissions
**Requirement:** Proper permissions for directories.
- Database directory: `~/kast-web/db/` must be writable
- Results directory: `~/kast_results/` must be writable
- Upload directory: `app/static/uploads/` must be writable
- In production: `www-data` user needs access

### 5. Database Migrations
**Requirement:** Migration scripts in `utils/` directory.
- Always create migration scripts for schema changes
- Test migrations on development database first
- Document migration steps in `docs/` directory
- Available migrations:
  - `migrate_db.py` - Initial database setup
  - `migrate_email_feature.py` - Email functionality
  - `migrate_existing_db.py` - Existing installation upgrade
  - `migrate_logo_feature.py` - Logo white-labeling
  - `migrate_phase3.py` - Admin panel phase 3
  - `migrate_phase4.py` - Sharing phase 4
  - `migrate_power_user.py` - Power user role

### 6. Security Considerations
**Requirements:**
- Never commit secrets to git (use environment variables)
- Always use `@login_required` for protected routes
- Validate user permissions before data access
- Log sensitive actions to audit log
- Use HTTPS in production
- Set strong `SECRET_KEY` in production
- Use app-specific passwords for email (Gmail, Outlook)
- Regular audit log review
- Backup database before using database explorer

### 7. Email Configuration
**Requirement:** SMTP must be configured for email functionality.
- Configure via admin panel at `/admin/settings`
- Test connection with "Test SMTP" button
- Use TLS/SSL for secure connections
- For Gmail: Enable 2FA and use app-specific password
- Email functionality can be disabled system-wide

### 8. Authentication Required
**Requirement:** All users must authenticate.
- No anonymous access to scans or functionality
- First admin user created via `scripts/create_admin_user.py`
- Session timeout configurable
- Failed login tracking and account lockout

## Development Workflow

### Starting the Application (Development)
```bash
# Terminal 1 - Redis (if not running as service)
redis-server

# Terminal 2 - Celery Worker
source venv/bin/activate
celery -A celery_worker.celery worker --loglevel=info

# Terminal 3 - Flask App
source venv/bin/activate
python3 run.py

# Or use helper script
./scripts/start_async.sh
```

### Making Code Changes
1. **Create feature branch:** `git checkout -b feature/your-feature`
2. **Make changes** following code standards
3. **Test locally** with development server
4. **Update documentation** if needed (README, docs/, genai-instructions.md)
5. **Create migration** if database schema changed
6. **Test authentication/authorization** if permissions changed
7. **Check audit logging** if adding sensitive operations
8. **Commit with descriptive message**

### Database Migrations
```bash
# Create migration utility in utils/
python3 utils/migrate_<feature>.py

# Document migration in docs/
# Create docs/<FEATURE>_MIGRATION.md or update existing docs
```

### Testing Checklist
```bash
# Manual testing checklist:
# - Test with Celery worker running
# - Test without Celery worker (should fail gracefully)
# - Test with different user roles (admin, power_user, user, viewer)
# - Check audit logs are created for sensitive actions
# - Verify permissions are enforced
# - Test email functionality (if applicable)
# - Test sharing functionality (if applicable)
# - Check maintenance mode (if applicable)
# - Verify logo association (if applicable)
```

## Common Pitfalls & Solutions

### 1. Scans Stuck in "Pending"
**Cause:** Celery worker not running  
**Solution:** Start Celery worker, verify Redis connection
```bash
# Check if running
ps aux | grep celery
# Start worker
celery -A celery_worker.celery worker --loglevel=info
```

### 2. Emails Not Sending
**Cause:** SMTP not configured or Celery worker not running  
**Solution:** 
- Configure SMTP in admin panel
- Test connection with "Test SMTP" button
- Verify Celery worker is running
- Check Celery logs for errors

### 3. Permission Denied Errors
**Cause:** User lacks required role or permission  
**Solution:** 
- Verify user role in database
- Check `@login_required`, `@admin_required`, `@power_user_required` decorators
- Ensure active scans restricted to power_user/admin

### 4. Import Circular Dependencies
**Cause:** Importing app models in `__init__.py`  
**Solution:** Import models only where needed, not at module level

### 5. Database Session Issues
**Cause:** Not committing changes or accessing detached objects  
**Solution:** Always `db.session.commit()` after changes, use `get_or_404()` for queries

### 6. Template Context Errors
**Cause:** Variables not passed to template  
**Solution:** Always pass required context: `render_template('page.html', var=value)`

### 7. Form CSRF Errors
**Cause:** Missing CSRF token in forms  
**Solution:** Always include `{{ form.hidden_tag() }}` in forms

### 8. Permission Bypass
**Cause:** Forgetting to check user permissions  
**Solution:** Always verify user can access resource:
```python
if scan.user_id != current_user.id and not current_user.is_admin:
    abort(403)
```

### 9. Task Serialization Errors
**Cause:** Passing non-serializable objects to Celery tasks  
**Solution:** Pass only primitive types (int, str, dict) to tasks

### 10. Maintenance Mode Lockout
**Cause:** Enabled maintenance mode and can't log in as admin  
**Solution:** 
- Maintenance mode allows admin login
- Or disable in database: `sqlite3 ~/kast-web/db/kast.db "UPDATE system_settings SET value='false' WHERE key='maintenance_mode'"`

### 11. Share Token Not Working
**Cause:** Share expired or token invalid  
**Solution:** 
- Check `expires_at` field
- Verify token matches database
- Check if share was deleted

### 12. Logo Not Displaying
**Cause:** File path incorrect or file missing  
**Solution:**
- Verify file exists in `app/static/uploads/logos/`
- Check `file_path` in ReportLogo table
- Ensure web server can read file

## Best Practices

### 1. Error Handling
Always use try-except blocks for external operations:
```python
try:
    result = subprocess.run(['kast', '--list-plugins'], capture_output=True)
except Exception as e:
    flash(f'Error: {str(e)}', 'error')
    # Log error
    AuditLog.log(
        user_id=current_user.id,
        action='error',
        details=f'KAST CLI error: {str(e)}',
        ip_address=request.remote_addr
    )
    return redirect(url_for('main.index'))
```

### 2. Flash Messages
Provide user feedback for all actions:
```python
flash('Scan created successfully!', 'success')
flash('Invalid target domain', 'error')
flash('Settings updated', 'info')
flash('This action requires admin privileges', 'warning')
```

### 3. Input Validation
Validate all user input:
- Use WTForms validators
- Add custom validation methods
- Sanitize file uploads
- Validate domain/URL formats
- Check email addresses with email-validator

### 4. Query Optimization
- Use `.filter_by()` for simple equality checks
- Use `.filter()` for complex conditions
- Add database indexes on frequently queried columns
- Use `.join()` to avoid N+1 queries
- Use pagination for large result sets
- Use `.options(joinedload())` for eager loading

### 5. Template Organization
- Keep templates DRY (Don't Repeat Yourself)
- Use macros for repeated components
- Organize templates by feature in subdirectories
- Use template inheritance effectively
- Pass only necessary context to templates

### 6. API Response Format
Consistent JSON structure:
```python
# Success
return jsonify({
    'status': 'success',
    'data': scan.to_dict()
}), 200

# Error
return jsonify({
    'status': 'error',
    'message': 'Scan not found'
}), 404

# With additional info
return jsonify({
    'status': 'success',
    'message': 'Email queued',
    'task_id': task.id,
    'count': len(recipients)
}), 200
```

### 7. Audit Logging
Log all significant actions:
- User authentication (login, logout, failed attempts)
- Scan operations (create, delete, share)
- User management (create, delete, role changes)
- System settings changes
- Email sending
- Logo uploads
- Database queries (via admin panel)

### 8. Permission Checks
Always check permissions before operations:
```python
# Check ownership
if resource.user_id != current_user.id and not current_user.is_admin:
    abort(403)

# Check share access
if not can_access_scan(scan, current_user):
    abort(403)

# Check role requirement
if not current_user.can_run_active_scans:
    flash('Active scans require power user privileges', 'error')
    return redirect(url_for('main.index'))
```

### 9. Email Best Practices
- Always validate email addresses before sending
- Use async tasks for email sending
- Test SMTP configuration before enabling
- Use app-specific passwords for Gmail/Outlook
- Enable TLS/SSL for security
- Log all email operations
- Respect recipient limits (max 10)

### 10. Database Explorer Safety
- **ALWAYS** backup database before running queries
- Test queries on development database first
- Avoid DELETE/DROP without WHERE clause
- Log all queries to audit log
- Restrict to admin users only
- Consider read-only mode for browsing

## Documentation Requirements

### When to Update Documentation
- New features added → Update README.md, this file, and create doc in `docs/`
- Configuration changes → Update `.env.example` and deployment docs
- Database schema changes → Create migration doc in `docs/`
- API changes → Update API section in README.md
- Deployment changes → Update `docs/PRODUCTION_DEPLOYMENT.md`
- Security changes → Update security sections
- New user roles/permissions → Update authentication sections

### Documentation Files
- `README.md` - Main project documentation and quick start
- `genai-instructions.md` - This file - comprehensive development guide
- `docs/PRODUCTION_DEPLOYMENT.md` - Production setup guide
- `docs/ASYNC_SETUP.md` - Celery/async configuration
- `docs/QUICK_REFERENCE.md` - Common commands and procedures
- `docs/AUTHENTICATION_SETUP.md` - Auth system setup (Phase 1)
- `docs/AUTHORIZATION_PHASE2.md` - Authorization and permissions (Phase 2)
- `docs/ADMIN_PANEL_PHASE3.md` - Admin panel features (Phase 3)
- `docs/SHARING_PHASE4.md` - Scan sharing implementation (Phase 4)
- `docs/SHARING_PHASE4_COMPLETE.md` - Sharing completion notes
- `docs/EMAIL_FEATURE.md` - Email system documentation
- `docs/EMAIL_QUICK_START.md` - Quick email setup guide
- `docs/LOGO_WHITELABELING_FEATURE.md` - Logo system documentation
- `docs/LOGO_IMPLEMENTATION_SUMMARY.md` - Logo implementation notes
- `docs/LOGO_FEATURE_QUICK_START.md` - Quick logo setup
- `docs/POWER_USER_FEATURE.md` - Power user role documentation
- `docs/DATABASE_EXPLORER_FEATURE.md` - Database explorer guide
- `docs/MAINTENANCE_MODE_ENFORCEMENT.md` - Maintenance mode docs
- `docs/OUTPUT_FILES_FEATURE.md` - Output file handling
- `docs/REGENERATE_REPORT_FEATURE.md` - Report regeneration
- Feature-specific docs with descriptive names

## Environment Variables

### Development
```bash
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=dev-secret-key-change-in-production
```

### Production
```bash
FLASK_ENV=production
SECRET_KEY=<strong-random-key>
DATABASE_URL=postgresql://user:pass@localhost/kast_web
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
KAST_CLI_PATH=/usr/local/bin/kast
KAST_RESULTS_DIR=/var/lib/kast_results
```

## File & Directory Structure Reference

```
/opt/kast-web/
├── app/                          # Main application package
│   ├── __init__.py              # App factory, extensions init, login manager
│   ├── models.py                # Database models (User, Scan, ScanResult, AuditLog, ScanShare, ReportLogo, SystemSettings)
│   ├── forms.py                 # WTForms classes
│   ├── tasks.py                 # Celery tasks (run_scan_task, send_report_email_task)
│   ├── utils.py                 # Helper functions, decorators (admin_required, power_user_required)
│   ├── email.py                 # Email utilities and SMTP handling
│   ├── admin_db.py              # Admin database explorer utilities
│   ├── routes/                  # Blueprint routes
│   │   ├── __init__.py
│   │   ├── main.py             # Home, scan submission
│   │   ├── scans.py            # Scan management, sharing, email sending
│   │   ├── api.py              # RESTful API endpoints
│   │   ├── auth.py             # Authentication, user management
│   │   ├── admin.py            # Admin panel, settings, database explorer
│   │   └── logos.py            # Logo upload and management
│   ├── templates/               # Jinja2 templates
│   │   ├── base.html           # Base template with navigation
│   │   ├── index.html          # Home page
│   │   ├── scan_*.html         # Scan-related pages
│   │   ├── auth/               # Authentication templates
│   │   │   ├── login.html
│   │   │   ├── register.html
│   │   │   ├── profile.html
│   │   │   ├── change_password.html
│   │   │   └── users.html
│   │   ├── admin/              # Admin panel templates
│   │   │   ├── dashboard.html
│   │   │   ├── settings.html
│   │   │   ├── activity.html
│   │   │   └── db_base.html
│   │   └── logos/              # Logo management templates
│   │       └── manage.html
│   └── static/                  # Static assets
│       ├── css/custom.css
│       ├── js/main.js
│       ├── js/report-viewer.js
│       ├── images/
│       │   ├── favicon.ico
│       │   └── kast-logo.png
│       └── uploads/
│           └── logos/          # Uploaded logo files
├── config.py                    # Configuration classes
├── celery_worker.py            # Celery worker entry point
├── run.py                       # Development server entry
├── wsgi.py                      # Production WSGI entry
├── gunicorn_config.py          # Gunicorn configuration
├── requirements.txt             # Python dependencies
├── requirements-production.txt  # Production dependencies
├── .env.example                 # Environment variables template
├── scripts/                     # Helper scripts
│   ├── start.sh                # Start Flask dev server
│   ├── start_async.sh          # Start all components
│   ├── create_admin_user.py    # Create first admin user
│   ├── verify_celery.sh        # Verify Celery setup
│   └── validate-install.sh     # Validate installation
├── utils/                       # Migration utilities
│   ├── migrate_db.py
│   ├── migrate_email_feature.py
│   ├── migrate_existing_db.py
│   ├── migrate_logo_feature.py
│   ├── migrate_phase3.py
│   ├── migrate_phase4.py
│   ├── migrate_power_user.py
│   ├── export_users.py
│   └── import_users.py
├── docs/                        # Project documentation
│   ├── PRODUCTION_DEPLOYMENT.md
│   ├── ASYNC_SETUP.md
│   ├── AUTHENTICATION_SETUP.md
│   ├── AUTHORIZATION_PHASE2.md
│   ├── ADMIN_PANEL_PHASE3.md
│   ├── SHARING_PHASE4.md
│   ├── EMAIL_FEATURE.md
│   ├── LOGO_WHITELABELING_FEATURE.md
│   ├── POWER_USER_FEATURE.md
│   ├── DATABASE_EXPLORER_FEATURE.md
│   ├── MAINTENANCE_MODE_ENFORCEMENT.md
│   └── ... (additional feature docs)
├── deployment/                  # Production deployment files
│   ├── QUICK_START.md
│   ├── .env.production
│   ├── nginx/
│   │   └── kast-web.conf
│   └── systemd/
│       ├── kast-web.service
│       └── kast-celery.service
├── genai-instructions.md        # This file
├── README.md                    # Main project documentation
├── .gitignore
└── LICENSE
```

## Additional Notes for AI Assistants

### When Creating New Features
1. **Read existing similar code first** to match patterns
2. **Check if models need updates** - create migration if so
3. **Add appropriate decorators** for authentication/authorization
4. **Include audit logging** for sensitive actions
5. **Update API endpoints** if exposing functionality
6. **Create/update templates** following Bootstrap 5 patterns
7. **Add to navigation** if user-facing feature (check role requirements)
8. **Update documentation** in README.md, this file, and/or docs/
9. **Test with different user roles** to verify permissions
10. **Check for email/Celery integration** if applicable

### When Fixing Bugs
1. **Identify root cause** - check logs, database state, audit logs
2. **Test fix locally** with all user roles before committing
3. **Consider edge cases** and error handling
4. **Update tests** if test suite exists
5. **Document fix** in commit message and update docs if needed
6. **Check if documentation needs updates**
7. **Verify audit logging** still works correctly

### When Refactoring
1. **Understand current implementation** fully before changes
2. **Maintain backward compatibility** where possible
3. **Update all references** to changed code
4. **Test thoroughly** with different scenarios and user roles
5. **Update documentation** to reflect changes
6. **Consider migration path** if database changes involved
7. **Verify permissions** and audit logging still work

### Security Checklist for New Code
- [ ] Uses `@login_required` for protected routes
- [ ] Checks user permissions appropriately
- [ ] Validates all user input
- [ ] Logs sensitive actions to AuditLog
- [ ] Doesn't expose sensitive data in responses
- [ ] Uses parameterized queries (ORM) not string concatenation
- [ ] Handles errors gracefully without exposing internals
- [ ] Respects maintenance mode
- [ ] Follows principle of least privilege

### Database Changes Checklist
- [ ] Create migration script in `utils/`
- [ ] Test migration on development database
- [ ] Document migration in `docs/`
- [ ] Update models.py with new fields/relationships
- [ ] Update this file with model documentation
- [ ] Consider backward compatibility
- [ ] Plan rollback strategy
- [ ] Test with existing data

### Adding New User Roles/Permissions
- [ ] Update User model if needed
- [ ] Create appropriate decorators in `app/utils.py`
- [ ] Update permission checking logic
- [ ] Update navigation/UI to respect new role
- [ ] Document role in this file
- [ ] Create migration for existing users
- [ ] Test thoroughly with all role combinations
- [ ] Update admin panel if role is manageable

## Future Enhancements

Planned features for future releases (not yet implemented):

### WebSocket Integration
- Real-time updates using Flask-SocketIO (currently installed but not used)
- Eliminate polling for status updates
- Push notifications for scan completion

### Scan Scheduling
- Automated recurring scans with cron-like scheduling
- Scan templates for common configurations
- Queue management and prioritization

### Advanced Analytics
- Trend analysis and vulnerability tracking dashboards
- Historical data visualization
- Comparison across multiple scans
- Executive summary reports

### Export Functionality
- Export results to various formats (CSV, JSON, XML)
- Bulk export capabilities
- Custom export templates

### API Authentication
- Token-based API access for external integrations
- API key management
- Rate limiting

### Plugin Management
- Web interface for managing KAST plugins
- Plugin installation/updates
- Custom plugin configuration

### Resource Monitoring
- Track system resource usage during scans
- Automatic throttling for resource management
- Performance metrics and optimization

### Enhanced Sharing
- Group-based sharing
- Distribution lists
- More granular permission levels
- Share analytics and tracking

## Support & References

### Getting Help
1. Check this file for implementation patterns
2. Review similar existing code in the codebase
3. Check feature-specific documentation in `docs/`
4. Review README.md for project overview
5. Check audit logs for debugging issues
6. Review Flask, SQLAlchemy, and Celery documentation

### External Documentation
- **Flask:** https://flask.palletsprojects.com/
- **SQLAlchemy:** https://docs.sqlalchemy.org/
- **Celery:** https://docs.celeryproject.org/
- **Flask-Login:** https://flask-login.readthedocs.io/
- **WTForms:** https://wtforms.readthedocs.io/
- **Bootstrap 5:** https://getbootstrap.com/docs/5.0/

### Project Resources
- Repository: Check git remote for repository URL
- Issues: Use repository issue tracker
- Documentation: `docs/` directory
- Migration scripts: `utils/` directory
- Deployment guides: `deployment/` directory

---

**Last Updated:** December 3, 2025  
**Document Version:** 2.0 (Major update reflecting all implemented features)
