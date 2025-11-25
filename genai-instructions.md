# GenAI Instructions for KAST-Web Project

## Project Overview

**KAST-Web** is a web-based interface for the Kali Automated Scan Tool (KAST), providing an intuitive way to configure, execute, and manage security scans through a browser. The application features asynchronous scan execution with real-time progress tracking, user authentication with role-based access control, and comprehensive reporting capabilities.

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
- **Celery** - Asynchronous task queue for background scan execution
- **Redis** - Message broker for Celery
- **Flask-Login** - User session management
- **Flask-SocketIO** - Real-time communication support (optional)
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
- `app/routes/scans.py` - Scan management (history, detail, files)
- `app/routes/api.py` - RESTful API endpoints
- `app/routes/auth.py` - Authentication and user management
- `app/routes/admin.py` - Admin panel and system settings
- `app/routes/logos.py` - Logo management for white-labeling

### Database Models
Located in `app/models.py`:
- **User** - User accounts with role-based permissions (admin, power_user, user, viewer)
- **Scan** - Scan configuration and metadata
- **ScanResult** - Individual plugin results per scan
- **AuditLog** - System audit trail for security and compliance
- **ScanShare** - Scan sharing (user-to-user and public links)
- **ReportLogo** - Custom logos for white-labeled reports
- **SystemSettings** - Key-value store for system-wide configuration

### Asynchronous Architecture
- **Celery Worker** (`celery_worker.py`) executes scans asynchronously
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

# Local application imports
from app import db
from app.models import Scan, User
from app.utils import requires_auth
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

## Database Patterns & Relationships

### User Roles & Permissions
```python
# Roles: admin, power_user, user, viewer
user.is_admin           # Full system access
user.is_power_user      # Can run active scans
user.can_run_active_scans  # admin or power_user only
```

### Key Relationships
- `User.scans` - One-to-many (user has many scans)
- `Scan.results` - One-to-many (scan has many plugin results)
- `Scan.shares` - One-to-many (scan can be shared multiple times)
- `User.audit_logs` - One-to-many (user has many audit log entries)

### Scan Status Flow
```
pending → running → completed
                 → failed
```

### Query Patterns
Always use SQLAlchemy ORM, not raw SQL:
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
```

## Authentication & Authorization

### Login Required
Use Flask-Login decorators:
```python
from flask_login import login_required, current_user

@bp.route('/scans')
@login_required
def scan_history():
    # Only authenticated users can access
```

### Role-Based Access
Use custom decorators from `app/utils.py`:
```python
from app.utils import admin_required, power_user_required

@bp.route('/admin/settings')
@admin_required
def admin_settings():
    # Only admins can access
```

### Audit Logging
Log all significant actions:
```python
from app.models import AuditLog

AuditLog.log(
    user_id=current_user.id,
    action='scan_created',
    resource_type='scan',
    resource_id=scan.id,
    details=f'Target: {scan.target}, Mode: {scan.scan_mode}',
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
from wtforms.validators import DataRequired, ValidationError

class ScanForm(FlaskForm):
    target = StringField('Target', validators=[DataRequired()])
    scan_mode = SelectField('Scan Mode', choices=[('passive', 'Passive'), ('active', 'Active')])
    
    def validate_target(self, field):
        # Custom validation logic
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
    return jsonify(scan.to_dict()), 200
```

### 6. Logo White-Labeling
**Feature:** Custom logos for reports
- Logos stored in `app/static/uploads/logos/`
- Database stores metadata in `ReportLogo` model
- Scan can reference logo via `scan.logo_id`

### 7. Scan Sharing
**Two Types:**
- **User-to-User:** `shared_with_user_id` populated
- **Public Link:** `share_token` generated, `shared_with_user_id` is NULL
- Expiration supported via `expires_at` field

## Critical Constraints & Requirements

### 1. Celery Worker Must Be Running
**Requirement:** Celery worker must be active for scans to execute.
- Scans will remain in "pending" status if worker is down
- Start worker: `celery -A celery_worker.celery worker --loglevel=info`
- Check status: `celery -A celery_worker.celery inspect active`

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

### 6. Security Considerations
**Requirements:**
- Never commit secrets to git (use environment variables)
- Always use `@login_required` for protected routes
- Validate user permissions before data access
- Log sensitive actions to audit log
- Use HTTPS in production
- Set strong `SECRET_KEY` in production

## Development Workflow

### Starting the Application (Development)
```bash
# Terminal 1 - Celery Worker
source venv/bin/activate
celery -A celery_worker.celery worker --loglevel=info

# Terminal 2 - Flask App
source venv/bin/activate
python3 run.py

# Or use helper script
./scripts/start_async.sh
```

### Making Code Changes
1. **Create feature branch:** `git checkout -b feature/your-feature`
2. **Make changes** following code standards
3. **Test locally** with development server
4. **Update documentation** if needed (README, docs/)
5. **Create migration** if database schema changed
6. **Commit with descriptive message**

### Database Migrations
```bash
# Create migration utility
python3 utils/migrate_<feature>.py

# Document migration
# Create docs/<FEATURE>_MIGRATION.md
```

### Testing
```bash
# Run tests (when test suite exists)
pytest

# Manual testing checklist:
# - Test with Celery worker running
# - Test without Celery worker (should fail gracefully)
# - Test with different user roles
# - Check audit logs are created
# - Verify permissions are enforced
```

## Common Pitfalls & Solutions

### 1. Scans Stuck in "Pending"
**Cause:** Celery worker not running  
**Solution:** Start Celery worker, verify Redis connection

### 2. Import Circular Dependencies
**Cause:** Importing app models in `__init__.py`  
**Solution:** Import models only where needed, not at module level

### 3. Database Session Issues
**Cause:** Not committing changes or accessing detached objects  
**Solution:** Always `db.session.commit()` after changes, use `get_or_404()` for queries

### 4. Template Context Errors
**Cause:** Variables not passed to template  
**Solution:** Always pass required context: `render_template('page.html', var=value)`

### 5. Form CSRF Errors
**Cause:** Missing CSRF token in forms  
**Solution:** Always include `{{ form.hidden_tag() }}` in forms

### 6. Permission Bypass
**Cause:** Forgetting to check user permissions  
**Solution:** Always verify user can access resource:
```python
if scan.user_id != current_user.id and not current_user.is_admin:
    abort(403)
```

### 7. Task Serialization Errors
**Cause:** Passing non-serializable objects to Celery tasks  
**Solution:** Pass only primitive types (int, str, dict) to tasks

## Best Practices

### 1. Error Handling
Always use try-except blocks for external operations:
```python
try:
    result = subprocess.run(['kast', '--list-plugins'], capture_output=True)
except Exception as e:
    flash(f'Error: {str(e)}', 'error')
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

### 4. Query Optimization
- Use `.filter_by()` for simple equality checks
- Use `.filter()` for complex conditions
- Add database indexes on frequently queried columns
- Use `.join()` to avoid N+1 queries
- Use pagination for large result sets

### 5. Template Organization
- Keep templates DRY (Don't Repeat Yourself)
- Use macros for repeated components
- Organize templates by feature in subdirectories
- Use template inheritance effectively

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
```

## Documentation Requirements

### When to Update Documentation
- New features added → Update README.md and create doc in `docs/`
- Configuration changes → Update `.env.example` and deployment docs
- Database schema changes → Create migration doc
- API changes → Update API section in README.md
- Deployment changes → Update production deployment docs

### Documentation Files
- `README.md` - Main project documentation
- `docs/PRODUCTION_DEPLOYMENT.md` - Production setup guide
- `docs/ASYNC_SETUP.md` - Celery/async configuration
- `docs/QUICK_REFERENCE.md` - Common commands and procedures
- Feature-specific docs in `docs/` with descriptive names

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
```

## File & Directory Structure Reference

```
/opt/kast-web/
├── app/                          # Main application package
│   ├── __init__.py              # App factory, extensions init
│   ├── models.py                # Database models
│   ├── forms.py                 # WTForms classes
│   ├── tasks.py                 # Celery tasks
│   ├── utils.py                 # Helper functions, decorators
│   ├── admin_db.py              # Admin database utilities
│   ├── routes/                  # Blueprint routes
│   │   ├── main.py             # Home, scan submission
│   │   ├── scans.py            # Scan management
│   │   ├── api.py              # RESTful API
│   │   ├── auth.py             # Authentication
│   │   ├── admin.py            # Admin panel
│   │   └── logos.py            # Logo management
│   ├── templates/               # Jinja2 templates
│   │   ├── base.html           # Base template
│   │   ├── index.html          # Home page
│   │   ├── scan_*.html         # Scan-related pages
│   │   ├── admin/              # Admin templates
│   │   ├── auth/               # Auth templates
│   │   └── logos/              # Logo templates
│   └── static/                  # Static assets
│       ├── css/custom.css
│       ├── js/main.js
│       ├── js/report-viewer.js
│       ├── images/
│       └── uploads/logos/
├── config.py                    # Configuration classes
├── celery_worker.py            # Celery worker entry point
├── run.py                       # Development server entry
├── wsgi.py                      # Production WSGI entry
├── requirements.txt             # Python dependencies
├── scripts/                     # Helper scripts
├── utils/                       # Migration utilities
├── docs/                        # Project documentation
└── deployment/                  # Production deployment files
```

## Additional Notes for AI Assistants

### When Creating New Features
1. **Read existing similar code first** to match patterns
2. **Check if models need updates** - create migration if so
3. **Add appropriate decorators** for authentication/authorization
4. **Include audit logging** for sensitive actions
5. **Update API endpoints** if exposing functionality
6. **Create/update templates** following Bootstrap 5 patterns
7. **Add to navigation** if user-facing feature
8. **Update documentation** in README.md and/or docs/

### When Fixing Bugs
1. **Identify root cause** - check logs, database state
2. **Test fix locally** before committing
3. **Consider edge cases** and error handling
4. **Update tests** if test suite exists
5. **Document fix** in commit message
6. **Check if documentation needs updates**

### When Refactoring
1. **Understand current implementation** fully before changes
2. **Maintain backward compatibility** where possible
3. **Update all references** to change
