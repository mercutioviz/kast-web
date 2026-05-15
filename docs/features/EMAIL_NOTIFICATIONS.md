# Email Feature Documentation

## Overview

The Email Feature allows users to send scan reports via email directly from the KAST-Web interface. Reports are sent as PDF attachments with a professional HTML email template.

## Features

- **SMTP Configuration**: Admin-configurable SMTP settings in the control panel
- **Email Sending**: Send PDF reports to multiple recipients (up to 10)
- **Async Processing**: Email sending handled asynchronously via Celery
- **Audit Logging**: All email operations are logged for security
- **Security**: Email validation, recipient limits, and permission checks
- **Test Connection**: Built-in SMTP connection testing tool

## Installation

### 1. Run Migration Script

```bash
cd /opt/kast-web
python3 utils/migrate_email_feature.py
```

This adds the necessary email settings to the SystemSettings database table.

### 2. Ensure Celery is Running

Email sending requires Celery to be running for async task processing:

```bash
# Check if Celery is running
ps aux | grep celery

# If not running, start it
celery -A celery_worker.celery worker --loglevel=info
```

For production, ensure the Celery systemd service is enabled:

```bash
sudo systemctl status kast-celery
sudo systemctl enable kast-celery
sudo systemctl start kast-celery
```

## Configuration

### Admin Panel Configuration

1. Log in as an admin user
2. Navigate to **Admin Panel > Settings**
3. Scroll to the **Email Settings** section
4. Configure your SMTP server details:

#### Basic Settings

- **Enable Email Functionality**: Toggle to enable/disable email features
- **SMTP Host**: Your SMTP server address (e.g., `smtp.gmail.com`)
- **SMTP Port**: Common ports are:
  - `587` for TLS (recommended)
  - `465` for SSL
  - `25` for unencrypted (not recommended)
- **Use TLS**: Enable for port 587
- **Use SSL**: Enable for port 465

#### Authentication

- **SMTP Username**: Your email account username
- **SMTP Password**: Your email account password or app-specific password
- **From Email Address**: Email address shown as sender (e.g., `noreply@example.com`)
- **From Name**: Display name for outgoing emails (e.g., `KAST Security`)

### Provider-Specific Configuration

#### Gmail

1. Enable 2-Factor Authentication on your Google account
2. Generate an App-Specific Password:
   - Go to https://myaccount.google.com/security
   - Click "2-Step Verification"
   - Scroll to "App passwords"
   - Generate a new password for "Mail"
3. Use these settings:
   - **SMTP Host**: `smtp.gmail.com`
   - **SMTP Port**: `587`
   - **Use TLS**: Enabled
   - **SMTP Username**: Your Gmail address
   - **SMTP Password**: The app-specific password

#### Microsoft 365/Outlook

- **SMTP Host**: `smtp.office365.com`
- **SMTP Port**: `587`
- **Use TLS**: Enabled
- **SMTP Username**: Your Microsoft email address
- **SMTP Password**: Your account password or app password

#### SendGrid

- **SMTP Host**: `smtp.sendgrid.net`
- **SMTP Port**: `587`
- **Use TLS**: Enabled
- **SMTP Username**: `apikey` (literally the word "apikey")
- **SMTP Password**: Your SendGrid API key

#### Amazon SES

- **SMTP Host**: `email-smtp.us-east-1.amazonaws.com` (adjust region)
- **SMTP Port**: `587`
- **Use TLS**: Enabled
- **SMTP Username**: Your SMTP username from AWS SES
- **SMTP Password**: Your SMTP password from AWS SES

### Testing Configuration

After configuring SMTP settings:

1. Click the **Test SMTP Connection** button
2. Wait for the test to complete
3. Review the result:
   - ✓ Success: SMTP configuration is working
   - ✗ Error: Review error message and adjust settings

## Usage

### Sending a Report via Email

1. Navigate to a completed scan's detail page
2. Click the **Send via Email** button
3. In the modal dialog:
   - Enter recipient email addresses (comma-separated)
   - Maximum 10 recipients per email
4. Click **Send Email**
5. The system will:
   - Validate email addresses
   - Queue the email for async sending
   - Show confirmation message
6. The PDF report will be sent as an attachment

### Email Content

Emails include:
- Professional HTML template with KAST branding
- Scan information (target, date, scan ID)
- PDF report as attachment
- System information and contact details

## Security Considerations

### Access Control

- Only users with view access to a scan can send its report
- Email functionality must be enabled by admin
- All email operations are logged in the audit log

### Data Protection

- SMTP passwords are stored in the database (consider encryption)
- Email addresses are validated before sending
- Recipient limit prevents abuse (max 10 recipients)
- Async processing prevents UI blocking

### Best Practices

1. **Use App-Specific Passwords**: For Gmail/Outlook, use app passwords instead of account passwords
2. **Enable TLS**: Always use encrypted connections (TLS/SSL)
3. **Limit Recipients**: The 10-recipient limit prevents spam/abuse
4. **Monitor Logs**: Review audit logs for email activity
5. **Test Regularly**: Verify SMTP configuration after changes

## Troubleshooting

### Common Issues

#### "Email functionality is disabled"
- **Solution**: Admin must enable it in Settings panel

#### "Failed to connect to SMTP server"
- **Causes**: Wrong host, port, or firewall blocking
- **Solution**: 
  - Verify SMTP host and port
  - Check firewall rules
  - Test with `telnet smtp.example.com 587`

#### "Authentication failed"
- **Causes**: Wrong username/password
- **Solution**:
  - Verify credentials
  - Use app-specific password for Gmail
  - Check if 2FA is enabled

#### "Connection timeout"
- **Causes**: Firewall, wrong port, or network issues
- **Solution**:
  - Check network connectivity
  - Verify port is not blocked
  - Try alternative ports (587, 465, 25)

#### "Email queued but not sent"
- **Cause**: Celery worker not running
- **Solution**:
  ```bash
  # Check Celery status
  sudo systemctl status kast-celery
  
  # Restart Celery
  sudo systemctl restart kast-celery
  
  # View Celery logs
  sudo journalctl -u kast-celery -f
  ```

### Debugging

#### Check Celery Logs

```bash
# View recent logs
sudo journalctl -u kast-celery -n 100

# Follow logs in real-time
sudo journalctl -u kast-celery -f
```

#### Check Application Logs

Look for email-related errors in the Flask logs:

```bash
# If running with systemd
sudo journalctl -u kast-web -f | grep -i email

# If running manually
# Check the terminal output where Flask is running
```

#### Test SMTP Manually

```python
# Test SMTP connection with Python
import smtplib
from email.mime.text import MIMEText

smtp_server = "smtp.gmail.com"
smtp_port = 587
username = "your-email@gmail.com"
password = "your-app-password"

try:
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(username, password)
    print("✓ SMTP connection successful")
    server.quit()
except Exception as e:
    print(f"✗ SMTP connection failed: {e}")
```

## API Reference

### Send Email Endpoint

**POST** `/scans/<scan_id>/send-email`

#### Request

```http
POST /scans/123/send-email HTTP/1.1
Content-Type: multipart/form-data

recipients=user1@example.com,user2@example.com
```

#### Response (Success)

```json
{
  "success": true,
  "message": "Email queued for delivery to 2 recipient(s)",
  "task_id": "abc123-def456-ghi789",
  "recipients_count": 2
}
```

#### Response (Error)

```json
{
  "success": false,
  "error": "Email functionality is disabled"
}
```

### Test SMTP Endpoint

**POST** `/admin/test-smtp`

#### Request

```http
POST /admin/test-smtp HTTP/1.1
Content-Type: multipart/form-data

smtp_host=smtp.gmail.com
smtp_port=587
smtp_username=user@gmail.com
smtp_password=app-password
use_tls=on
from_email=noreply@example.com
from_name=KAST Security
```

#### Response (Success)

```json
{
  "success": true,
  "message": "SMTP connection successful"
}
```

## Architecture

### Components

1. **app/email.py**: Email utility functions
   - SMTP configuration
   - Email validation
   - Message creation

2. **app/tasks.py**: Celery tasks
   - `send_report_email_task`: Async email sending

3. **app/routes/admin.py**: Admin endpoints
   - SMTP configuration
   - Test connection

4. **app/routes/scans.py**: Scan endpoints
   - Send email endpoint

5. **app/templates/**: UI templates
   - Email modal in scan_detail.html
   - SMTP settings in admin/settings.html

### Email Flow

```
User clicks "Send via Email"
    ↓
Frontend validates input
    ↓
POST to /scans/<id>/send-email
    ↓
Backend validates permissions and email addresses
    ↓
Create Celery task (async)
    ↓
Return success message
    ↓
Celery worker processes task
    ↓
Connect to SMTP server
    ↓
Send email with PDF attachment
    ↓
Log result to audit log
```

## Files Modified/Created

### New Files
- `app/email.py` - Email utilities
- `utils/migrate_email_feature.py` - Migration script
- `docs/EMAIL_FEATURE.md` - This documentation

### Modified Files
- `app/tasks.py` - Added email sending task
- `app/routes/admin.py` - Added SMTP settings and test endpoint
- `app/routes/scans.py` - Added send email endpoint
- `app/templates/admin/settings.html` - Added email configuration UI
- `app/templates/scan_detail.html` - Added email modal and button

## Future Enhancements

Potential improvements for future versions:

1. **Email Templates**: Customizable email templates
2. **Scheduled Reports**: Automated email delivery
3. **Email History**: Track sent emails per scan
4. **Batch Sending**: Send multiple reports at once
5. **Email Encryption**: PGP/GPG support for attachments
6. **Custom Messages**: User-defined email body text
7. **HTML Report Option**: Send HTML instead of PDF
8. **Distribution Lists**: Predefined recipient groups

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Celery and application logs
3. Test SMTP configuration with test button
4. Verify Celery worker is running
5. Check audit logs for email activity

## Changelog

### Version 1.0 (Initial Release)
- SMTP configuration in admin panel
- Send PDF reports via email
- Support for multiple recipients
- Async email processing with Celery
- SMTP connection testing
- Email validation and security
- Audit logging for email operations
