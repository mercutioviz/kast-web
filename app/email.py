"""
Email utility module for sending scan reports via email
Handles SMTP configuration, email composition, and PDF attachments
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails with SMTP"""
    
    def __init__(self, smtp_settings: dict):
        """
        Initialize email service with SMTP settings
        
        Args:
            smtp_settings: Dictionary containing SMTP configuration
        """
        self.smtp_host = smtp_settings.get('smtp_host')
        self.smtp_port = int(smtp_settings.get('smtp_port', 587))
        self.smtp_username = smtp_settings.get('smtp_username')
        self.smtp_password = smtp_settings.get('smtp_password')
        self.from_email = smtp_settings.get('from_email')
        self.from_name = smtp_settings.get('from_name', 'KAST Security')
        self.use_tls = smtp_settings.get('use_tls', True)
        self.use_ssl = smtp_settings.get('use_ssl', False)
        
    def validate_settings(self) -> Tuple[bool, Optional[str]]:
        """
        Validate SMTP settings
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.smtp_host:
            return False, "SMTP host is required"
        if not self.smtp_port:
            return False, "SMTP port is required"
        if not self.smtp_username:
            return False, "SMTP username is required"
        if not self.smtp_password:
            return False, "SMTP password is required"
        if not self.from_email:
            return False, "From email address is required"
        
        return True, None
    
    def test_connection(self) -> Tuple[bool, Optional[str]]:
        """
        Test SMTP connection
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            is_valid, error = self.validate_settings()
            if not is_valid:
                return False, error
            
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
                if self.use_tls:
                    server.starttls()
            
            server.login(self.smtp_username, self.smtp_password)
            server.quit()
            
            return True, None
            
        except smtplib.SMTPAuthenticationError:
            return False, "Authentication failed. Check username and password."
        except smtplib.SMTPConnectError:
            return False, f"Could not connect to SMTP server at {self.smtp_host}:{self.smtp_port}"
        except Exception as e:
            return False, f"SMTP connection test failed: {str(e)}"
    
    def send_email(
        self,
        recipients: List[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        attachments: Optional[List[Tuple[str, bytes, str]]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Send an email with optional attachments
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            html_body: HTML body content
            text_body: Plain text body (fallback)
            attachments: List of (filename, content, mime_type) tuples
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Validate settings
            is_valid, error = self.validate_settings()
            if not is_valid:
                return False, error
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr((self.from_name, self.from_email))
            msg['To'] = ', '.join(recipients)
            msg['Date'] = formataddr((None, datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')))
            
            # Add text body
            if text_body:
                msg.attach(MIMEText(text_body, 'plain'))
            
            # Add HTML body
            msg.attach(MIMEText(html_body, 'html'))
            
            # Add attachments
            if attachments:
                for filename, content, mime_type in attachments:
                    attachment = MIMEApplication(content, _subtype=mime_type.split('/')[-1])
                    attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(attachment)
            
            # Connect and send
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
                if self.use_tls:
                    server.starttls()
            
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(self.from_email, recipients, msg.as_string())
            server.quit()
            
            logger.info(f"Email sent successfully to {len(recipients)} recipient(s)")
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            return False, error_msg


def validate_email_address(email: str) -> bool:
    """
    Validate email address format
    
    Args:
        email: Email address to validate
    
    Returns:
        True if valid, False otherwise
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def parse_email_list(email_string: str) -> List[str]:
    """
    Parse comma-separated email addresses and validate them
    
    Args:
        email_string: Comma-separated email addresses
    
    Returns:
        List of valid email addresses
    """
    emails = [email.strip() for email in email_string.split(',')]
    return [email for email in emails if email and validate_email_address(email)]


def create_report_email_body(scan_data: dict, sender_name: str) -> Tuple[str, str]:
    """
    Create HTML and text email body for scan report
    
    Args:
        scan_data: Dictionary with scan information
        sender_name: Name of the user sending the email
    
    Returns:
        Tuple of (html_body, text_body)
    """
    target = scan_data.get('target', 'Unknown')
    scan_mode = scan_data.get('scan_mode', 'Unknown').title()
    started_at = scan_data.get('started_at', 'Unknown')
    completed_at = scan_data.get('completed_at', 'Unknown')
    findings_count = scan_data.get('findings_count', 0)
    scan_id = scan_data.get('scan_id', 'N/A')
    
    # HTML body
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #0d6efd;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f8f9fa;
                padding: 20px;
                border: 1px solid #dee2e6;
                border-radius: 0 0 5px 5px;
            }}
            .info-table {{
                width: 100%;
                margin: 20px 0;
            }}
            .info-table td {{
                padding: 8px;
                border-bottom: 1px solid #dee2e6;
            }}
            .info-table td:first-child {{
                font-weight: bold;
                width: 150px;
            }}
            .footer {{
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
                font-size: 12px;
                color: #6c757d;
            }}
            .findings {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 10px;
                margin: 15px 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>🔒 Security Scan Report</h2>
        </div>
        <div class="content">
            <p>A security scan report has been shared with you by <strong>{sender_name}</strong>.</p>
            
            <table class="info-table">
                <tr>
                    <td>Target:</td>
                    <td>{target}</td>
                </tr>
                <tr>
                    <td>Scan Mode:</td>
                    <td>{scan_mode}</td>
                </tr>
                <tr>
                    <td>Scan ID:</td>
                    <td>#{scan_id}</td>
                </tr>
                <tr>
                    <td>Started:</td>
                    <td>{started_at}</td>
                </tr>
                <tr>
                    <td>Completed:</td>
                    <td>{completed_at}</td>
                </tr>
            </table>
            
            <div class="findings">
                <strong>Total Findings:</strong> {findings_count}
            </div>
            
            <p>Please find the detailed security scan report attached as a PDF document.</p>
            
            <div class="footer">
                <p><strong>Note:</strong> This is an automated email from KAST Security Scanner. Please do not reply to this email.</p>
                <p>The attached report contains sensitive security information. Please handle it with appropriate care and do not forward it to unauthorized parties.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Text body (fallback)
    text_body = f"""
Security Scan Report

A security scan report has been shared with you by {sender_name}.

Target: {target}
Scan Mode: {scan_mode}
Scan ID: #{scan_id}
Started: {started_at}
Completed: {completed_at}
Total Findings: {findings_count}

Please find the detailed security scan report attached as a PDF document.

---
Note: This is an automated email from KAST Security Scanner. Please do not reply to this email.
The attached report contains sensitive security information. Please handle it with appropriate care and do not forward it to unauthorized parties.
    """
    
    return html_body, text_body


def send_scan_report_email(
    scan,
    recipients: List[str],
    sender_name: str,
    smtp_settings: dict
) -> Tuple[bool, Optional[str]]:
    """
    Send scan report via email
    
    Args:
        scan: Scan model instance
        recipients: List of recipient email addresses
        sender_name: Name of the user sending the email
        smtp_settings: SMTP configuration dictionary
    
    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Check if PDF report exists
        if not scan.output_dir:
            return False, "Scan has no output directory"
        
        pdf_path = Path(scan.output_dir) / 'kast_report.pdf'
        if not pdf_path.exists():
            return False, "PDF report not found. Please ensure the scan has completed."
        
        # Read PDF content
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        # Prepare scan data for email template
        scan_data = {
            'target': scan.target,
            'scan_mode': scan.scan_mode,
            'scan_id': scan.id,
            'started_at': scan.started_at.strftime('%Y-%m-%d %H:%M:%S UTC') if scan.started_at else 'N/A',
            'completed_at': scan.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if scan.completed_at else 'N/A',
            'findings_count': scan.results.count()
        }
        
        # Create email body
        html_body, text_body = create_report_email_body(scan_data, sender_name)
        
        # Create email subject
        subject = f"Security Scan Report: {scan.target}"
        
        # Prepare attachment
        pdf_filename = f"kast_report_{scan.target}_{scan.id}.pdf"
        attachments = [(pdf_filename, pdf_content, 'application/pdf')]
        
        # Send email
        email_service = EmailService(smtp_settings)
        success, error = email_service.send_email(
            recipients=recipients,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            attachments=attachments
        )
        
        return success, error
        
    except Exception as e:
        error_msg = f"Error preparing email: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
