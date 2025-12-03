# Email Feature - Quick Start Guide

## Overview

This guide will help you quickly set up and start using the email feature in KAST-Web.

## Prerequisites

✓ KAST-Web installed and running
✓ Celery worker running (required for async email processing)
✓ Admin access to configure SMTP settings

## Setup Steps

### Step 1: Run Migration

```bash
cd /opt/kast-web
python3 utils/migrate_email_feature.py
```

Expected output:
```
Starting Email Feature Migration...
============================================================
+ Adding setting 'email_enabled' with default value: False
+ Adding setting 'smtp_host' with default value: 
...
✓ Successfully added 9 email settings to database
```

### Step 2: Configure SMTP Settings

1. Log in to KAST-Web as admin
2. Go to **Admin Panel** (gear icon) → **Settings**
3. Scroll to **Email Settings** section
4. Fill in your SMTP details:

**Example - Gmail Configuration:**
```
Enable Email Functionality: ✓ (checked)
SMTP Host: smtp.gmail.com
SMTP Port: 587
Use TLS: ✓ (checked)
Use SSL: ☐ (unchecked)
SMTP Username: your-email@gmail.com
SMTP Password: [your-app-specific-password]
From Email Address: noreply@yourdomain.com
From Name: KAST Security
```

5. Click **Test SMTP Connection** to verify
6. Click **Save Settings**

### Step 3: Send Your First Email

1. Navigate to a **completed scan**
2. Click **Send via Email** button
3. Enter recipient email(s): `user@example.com, admin@example.com`
4. Click **Send Email**
5. Wait for confirmation: "Email queued for delivery to 2 recipient(s)"

## Common SMTP Configurations

### Gmail (Personal Account)

```
Host: smtp.gmail.com
Port: 587
TLS: Yes
Username: your-email@gmail.com
Password: [16-character app password]
```

**Getting Gmail App Password:**
1. Enable 2FA on your Google account
2. Visit: https://myaccount.google.com/apppasswords
3. Generate password for "Mail"
4. Use this password (not your regular password)

### Microsoft 365

```
Host: smtp.office365.com
Port: 587
TLS: Yes
Username: your-email@company.com
Password: [your account password]
```

### SendGrid

```
Host: smtp.sendgrid.net
Port: 587
TLS: Yes
Username: apikey
Password: [Your SendGrid API key]
```

## Troubleshooting

### ❌ "Email functionality is disabled"
**Fix:** Enable in Admin Panel > Settings > Email Settings

### ❌ "Authentication failed"
**Fix:** 
- Verify username and password
- For Gmail: Use app-specific password, not account password
- For 2FA accounts: Generate app password

### ❌ "Email queued but never sent"
**Fix:** Celery worker not running

```bash
# Check Celery status
sudo systemctl status kast-celery

# Start if not running
sudo systemctl start kast-celery

# View logs
sudo journalctl -u kast-celery -f
```

### ❌ "Connection timeout"
**Fix:**
- Check firewall allows outbound SMTP
- Try alternative ports (587, 465, 25)
- Verify SMTP host is correct

## Testing Tips

1. **Always test SMTP first**: Use "Test SMTP Connection" button before sending real emails
2. **Start with yourself**: Send first email to your own address
3. **Check spam folder**: Emails might be filtered as spam initially
4. **Monitor Celery logs**: Watch for errors during email sending
5. **Verify Celery is running**: Email won't send without Celery worker

## Security Notes

- SMTP passwords stored in database (plaintext)
- Maximum 10 recipients per email (prevents abuse)
- Only users with scan access can email reports
- All email operations logged in audit log
- Use TLS/SSL for encrypted connections

## Next Steps

- Review full documentation: `docs/EMAIL_FEATURE.md`
- Set up Celery as systemd service for production
- Configure SPF/DKIM records for your domain
- Test with different email providers
- Monitor audit logs for email activity

## Support

If you encounter issues:
1. Check this troubleshooting section
2. Review Celery logs: `sudo journalctl -u kast-celery -f`
3. Test SMTP manually using Python script (see EMAIL_FEATURE.md)
4. Verify all settings in admin panel

## Summary

The email feature allows users to send scan reports via email with:
- PDF report as attachment
- Professional HTML email template
- Async processing (doesn't block UI)
- Multiple recipients support
- Admin-controlled SMTP configuration
- Built-in testing and validation

Enjoy sending your scan reports! 📧
