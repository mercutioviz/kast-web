# Database Explorer Feature

## Overview

The Database Explorer provides a comprehensive web-based interface for administrators to browse, search, filter, and manage all database tables in the KAST Web application. Built with Flask-Admin, it offers a powerful yet secure way to interact with the application's data.

## Features

### Security
- **Admin-Only Access**: Only users with the `admin` role can access the database explorer
- **Password Protection**: User password hashes are hidden from all views
- **Read-Only Options**: Audit logs are read-only to maintain data integrity
- **Session-Based Auth**: Integrates with existing Flask-Login authentication

### Capabilities
- **Browse All Tables**: View data from all 7 database tables (Users, Scans, ScanResults, AuditLogs, ScanShares, ReportLogos, SystemSettings)
- **Search & Filter**: Built-in search functionality and advanced filtering options
- **Sort Columns**: Click column headers to sort data
- **Export Data**: Export table data to CSV format
- **View Details**: Click individual records for detailed views
- **Edit Records**: Modify existing records (except audit logs)
- **Create Records**: Add new records to tables
- **Delete Records**: Remove records (except audit logs)

## Access

### URL
The database explorer is accessible at: `http://your-domain/admin/database`

### Navigation
1. Log in as an admin user
2. Go to the Admin Dashboard (`/admin/dashboard`)
3. Click the green "Database Explorer" button in the top-right corner
4. Or navigate directly to `/admin/database`

## Available Tables

### Core Tables

#### 1. Users
- **Purpose**: Manage user accounts and authentication
- **Features**: 
  - View user details, roles, and activity
  - Edit user information
  - Reset passwords (via "New Password" field)
  - Activate/deactivate accounts
- **Protected Fields**: Password hashes are hidden
- **Search**: Username, email, first name, last name
- **Filters**: Role, active status, creation date, last login

#### 2. Scans
- **Purpose**: View and manage security scans
- **Features**:
  - Browse all scans with status badges
  - View scan configuration and results
  - Filter by status, mode, user, dates
- **Search**: Target, Celery task ID
- **Filters**: Status, scan mode, user, start/completion dates
- **Status Badges**: Color-coded (success, failed, running, pending)

#### 3. Scan Results
- **Purpose**: View individual plugin results for each scan
- **Features**:
  - See plugin execution status
  - View findings counts
  - Access output file paths
- **Search**: Plugin name
- **Filters**: Status, scan ID, plugin name, execution date

#### 4. Audit Logs (Read-Only)
- **Purpose**: View system audit trail
- **Features**:
  - **Read-only**: Cannot create, edit, or delete
  - Track all system actions
  - View user activity
  - Monitor resource changes
- **Search**: Action, resource type, details, IP address
- **Filters**: Action, resource type, user, timestamp

### Feature Tables

#### 5. Scan Shares
- **Purpose**: Manage scan sharing configuration
- **Features**:
  - View shared scans
  - Manage sharing permissions
  - Set expiration dates
- **Search**: Share token
- **Filters**: Permission level, scan ID, user, dates

#### 6. Report Logos
- **Purpose**: Manage uploaded logo files for reports
- **Features**:
  - View all uploaded logos
  - See file details (size, MIME type)
  - Manage logo metadata
- **Search**: Name, filename, description
- **Filters**: MIME type, uploader, upload date
- **File Size**: Displayed in KB for easy reading

### Configuration Tables

#### 7. System Settings
- **Purpose**: Manage application-wide settings
- **Features**:
  - View all system settings
  - Edit setting values
  - See value types (string, int, bool, json)
  - JSON formatting in detail view
- **Search**: Key, value, description
- **Filters**: Value type, update date

## Usage Examples

### Viewing Users
1. Navigate to Database Explorer
2. Click "Users" in the navigation menu
3. Use the search box to find specific users
4. Apply filters for role or active status
5. Click a username to view full details

### Resetting a User Password
1. Go to Users table
2. Click the edit icon for the user
3. Enter a new password in the "New Password" field
4. Save changes

### Exporting Data
1. Navigate to any table view
2. Apply desired filters
3. Click the "Export" dropdown
4. Select "csv" format
5. Save the downloaded file

### Searching Scans
1. Go to Scans table
2. Enter a target or task ID in the search box
3. Apply status filter (e.g., "completed")
4. Results update automatically

### Viewing Audit History
1. Navigate to Audit Logs
2. Filter by action type or user
3. Use date filters for specific time ranges
4. View details for any log entry

## Technical Details

### Implementation
- **Framework**: Flask-Admin 1.6.1
- **Theme**: Bootstrap 4
- **Database**: SQLAlchemy ORM
- **Authentication**: Flask-Login integration

### Files Added
- `app/admin_db.py` - Flask-Admin configuration and ModelViews
- `app/templates/admin/db_base.html` - Custom base template
- `requirements.txt` - Added Flask-Admin dependency

### Files Modified
- `app/__init__.py` - Initialize Flask-Admin
- `app/templates/admin/dashboard.html` - Added navigation link

### Custom Features
- **Datetime Formatting**: All dates displayed in `YYYY-MM-DD HH:MM:SS` format
- **Status Badges**: Color-coded badges for scan and result statuses
- **File Size Formatting**: Automatic conversion to KB for readability
- **JSON Formatting**: Pretty-printed JSON in detail views
- **Custom Password Handling**: Secure password updates for users

### Security Measures
1. Admin-only access via `is_accessible()` method
2. Redirect to login for unauthorized users
3. Password hash exclusion from all views
4. Audit logs are read-only
5. Integration with existing authentication system

## Best Practices

### For Administrators
1. **Use Filters**: Instead of scrolling, use filters to find specific records
2. **Export Before Deletion**: Always export data before deleting records
3. **Check Audit Logs**: Monitor user activity regularly
4. **Be Careful with Edits**: Database changes are immediate and may affect running operations
5. **Regular Backups**: Maintain database backups before bulk operations

### Security Recommendations
1. Only grant admin role to trusted users
2. Monitor audit logs for suspicious activity
3. Use strong passwords and change them regularly
4. Log out when finished with administrative tasks
5. Don't share admin credentials

## Troubleshooting

### Cannot Access Database Explorer
- Verify you're logged in as an admin user
- Check your user role in the Users table (via SQL or admin panel)
- Clear browser cache and cookies
- Check application logs for errors

### Changes Not Saving
- Verify you have edit permissions
- Check for validation errors in form
- Ensure required fields are filled
- Check database connection

### Export Not Working
- Try a smaller data set with filters
- Check browser pop-up blocker settings
- Ensure sufficient disk space
- Try a different browser

## Future Enhancements

Potential improvements for future versions:
- Bulk edit operations
- Advanced query builder
- Data visualization dashboards
- Scheduled exports
- Custom report generation
- Database backup/restore interface
- Activity monitoring dashboard
- Real-time data updates

## Support

For issues or questions about the Database Explorer:
1. Check this documentation first
2. Review Flask-Admin documentation: https://flask-admin.readthedocs.io/
3. Report bugs using the `/reportbug` command in the application
4. Contact the development team

## Version History

### Version 1.0.0 (Initial Release)
- Full CRUD operations for all tables
- Search and filter capabilities
- CSV export functionality
- Admin-only security
- Bootstrap 4 theme integration
- Custom datetime and status formatting
