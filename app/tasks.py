"""
Celery tasks for asynchronous scan execution
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime
from celery_worker import celery
from app import db
from app.models import Scan, ScanResult


@celery.task(bind=True)
def execute_scan_task(self, scan_id, target, scan_mode, plugins=None, parallel=False, verbose=False, dry_run=False, max_workers=5):
    """
    Celery task to execute a KAST scan asynchronously
    
    Args:
        scan_id: Database scan ID
        target: Target domain
        scan_mode: 'active' or 'passive'
        plugins: List of plugin names to run (None = all)
        parallel: Run plugins in parallel
        verbose: Enable verbose output
        dry_run: Dry run mode
        max_workers: Maximum number of workers for parallel mode (default: 5)
    
    Returns:
        dict with 'success', 'output_dir', 'error' keys
    """
    from flask import current_app
    from app.utils import get_logo_for_scan
    
    try:
        # Get scan from database
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return {'success': False, 'error': 'Scan not found'}
        
        # Generate output directory name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = Path(current_app.config['KAST_RESULTS_DIR']) / f"{target}-{timestamp}"
        
        # Update scan status and output directory BEFORE starting the scan
        scan.status = 'running'
        scan.output_dir = str(output_dir)
        db.session.commit()
        
        # Build command
        kast_cli = current_app.config['KAST_CLI_PATH']
        cmd = [kast_cli, '-t', target, '-m', scan_mode, '--format', 'both']
        
        # Add logo if available
        logo_path = get_logo_for_scan(scan)
        if logo_path:
            cmd.extend(['--logo', logo_path])
            current_app.logger.info(f"Using logo: {logo_path}")
        
        if plugins:
            cmd.extend(['--run-only', ','.join(plugins)])
        
        if parallel:
            cmd.append('-p')
            cmd.extend(['--max-workers', str(max_workers)])
        
        if verbose:
            cmd.append('-v')
        
        if dry_run:
            cmd.append('--dry-run')
        
        cmd.extend(['-o', str(output_dir)])
        
        current_app.logger.info(f"Executing KAST command: {' '.join(cmd)}")
        
        # Execute scan with real-time result parsing
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Update task state to show progress
        self.update_state(state='PROGRESS', meta={'status': 'running', 'scan_id': scan_id})
        
        # Wait for process to complete
        stdout, stderr = process.communicate(timeout=3600)  # 1 hour timeout
        
        # Update scan with results
        scan.output_dir = str(output_dir)
        scan.completed_at = datetime.utcnow()
        
        if process.returncode == 0:
            scan.status = 'completed'
            db.session.commit()
            
            # Parse results
            parse_scan_results(scan_id, output_dir)
            
            return {
                'success': True,
                'output_dir': str(output_dir),
                'stdout': stdout,
                'stderr': stderr
            }
        else:
            scan.status = 'failed'
            scan.error_message = stderr or 'Scan failed with no error message'
            db.session.commit()
            
            return {
                'success': False,
                'error': stderr or 'Unknown error',
                'stdout': stdout
            }
    
    except subprocess.TimeoutExpired:
        scan.status = 'failed'
        scan.error_message = 'Scan timed out after 1 hour'
        scan.completed_at = datetime.utcnow()
        db.session.commit()
        return {'success': False, 'error': 'Scan timed out'}
    
    except Exception as e:
        current_app.logger.exception(f"Error executing scan: {str(e)}")
        scan.status = 'failed'
        scan.error_message = str(e)
        scan.completed_at = datetime.utcnow()
        db.session.commit()
        return {'success': False, 'error': str(e)}


def parse_scan_results(scan_id, output_dir):
    """
    Parse scan results from output directory and store in database
    
    Args:
        scan_id: Database scan ID
        output_dir: Path to scan output directory
    """
    from flask import current_app
    
    try:
        output_path = Path(output_dir)
        if not output_path.exists():
            current_app.logger.warning(f"Output directory does not exist: {output_dir}")
            return
        
        # Look for processed JSON files
        for json_file in output_path.glob("*_processed.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                plugin_name = data.get('plugin_name', json_file.stem.replace('_processed', ''))
                
                # Count findings correctly - look at results array within findings
                findings_data = data.get('findings', {})
                if isinstance(findings_data, dict):
                    # findings is a dict with a 'results' key containing the actual findings
                    findings_count = len(findings_data.get('results', []))
                else:
                    # fallback: findings is a list
                    findings_count = len(findings_data) if isinstance(findings_data, list) else 0
                
                # Get file modification time as executed_at
                file_mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                
                # Check if result already exists
                existing_result = ScanResult.query.filter_by(
                    scan_id=scan_id,
                    plugin_name=plugin_name
                ).first()
                
                if existing_result:
                    # Update existing result
                    existing_result.status = data.get('disposition', 'unknown')
                    existing_result.findings_count = findings_count
                    existing_result.processed_output_path = str(json_file)
                    existing_result.executed_at = file_mtime
                else:
                    # Create new scan result entry
                    result = ScanResult(
                        scan_id=scan_id,
                        plugin_name=plugin_name,
                        status=data.get('disposition', 'unknown'),
                        findings_count=findings_count,
                        processed_output_path=str(json_file),
                        executed_at=file_mtime
                    )
                    db.session.add(result)
            
            except Exception as e:
                current_app.logger.error(f"Error parsing {json_file}: {str(e)}")
        
        db.session.commit()
    
    except Exception as e:
        current_app.logger.exception(f"Error parsing scan results: {str(e)}")


@celery.task
def parse_scan_results_task(scan_id, output_dir):
    """
    Celery task to parse scan results (can be called periodically during scan)
    
    Args:
        scan_id: Database scan ID
        output_dir: Path to scan output directory
    """
    parse_scan_results(scan_id, output_dir)


@celery.task(bind=True)
def regenerate_report_task(self, scan_id):
    """
    Celery task to regenerate the KAST HTML report using --report-only flag
    
    Args:
        scan_id: Database scan ID
    
    Returns:
        dict with 'success', 'error' keys
    """
    from flask import current_app
    from app.utils import get_logo_for_scan
    
    try:
        # Get scan from database
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return {'success': False, 'error': 'Scan not found'}
        
        if not scan.output_dir:
            return {'success': False, 'error': 'No output directory found for this scan'}
        
        output_dir = Path(scan.output_dir)
        if not output_dir.exists():
            return {'success': False, 'error': 'Output directory does not exist'}
        
        # Build command with --report-only flag and format both
        kast_cli = current_app.config['KAST_CLI_PATH']
        cmd = [kast_cli, '--report-only', str(output_dir), '--format', 'both']
        
        # Add logo if available
        logo_path = get_logo_for_scan(scan)
        if logo_path:
            cmd.extend(['--logo', logo_path])
            current_app.logger.info(f"Using logo for report regeneration: {logo_path}")
        
        current_app.logger.info(f"Executing KAST report regeneration: {' '.join(cmd)}")
        
        # Update task state to show progress
        self.update_state(state='PROGRESS', meta={'status': 'regenerating', 'scan_id': scan_id})
        
        # Execute command
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for process to complete
        stdout, stderr = process.communicate(timeout=300)  # 5 minute timeout
        
        if process.returncode == 0:
            current_app.logger.info(f"Report regenerated successfully for scan {scan_id}")
            return {
                'success': True,
                'stdout': stdout,
                'stderr': stderr
            }
        else:
            error_msg = stderr or 'Report regeneration failed with no error message'
            current_app.logger.error(f"Report regeneration failed for scan {scan_id}: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'stdout': stdout
            }
    
    except subprocess.TimeoutExpired:
        current_app.logger.error(f"Report regeneration timed out for scan {scan_id}")
        return {'success': False, 'error': 'Report regeneration timed out after 5 minutes'}
    
    except Exception as e:
        current_app.logger.exception(f"Error regenerating report for scan {scan_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@celery.task(bind=True)
def send_report_email_task(self, scan_id, recipients, sender_user_id, include_zip=False):
    """
    Celery task to send scan report via email asynchronously
    
    Args:
        scan_id: Database scan ID
        recipients: List of recipient email addresses
        sender_user_id: ID of user sending the email
        include_zip: Whether to include zip file of all results
    
    Returns:
        dict with 'success', 'error', 'recipients_count' keys
    """
    from flask import current_app
    from app.models import User, AuditLog
    from app.email import send_scan_report_email
    
    try:
        # Get scan from database
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return {'success': False, 'error': 'Scan not found'}
        
        # Get sender information
        sender = db.session.get(User, sender_user_id)
        if not sender:
            return {'success': False, 'error': 'Sender not found'}
        
        sender_name = f"{sender.first_name} {sender.last_name}".strip() or sender.username
        
        # Get SMTP settings from SystemSettings
        from app.models import SystemSettings
        smtp_settings = {
            'smtp_host': SystemSettings.get_setting('smtp_host'),
            'smtp_port': SystemSettings.get_setting('smtp_port', 587),
            'smtp_username': SystemSettings.get_setting('smtp_username'),
            'smtp_password': SystemSettings.get_setting('smtp_password'),
            'from_email': SystemSettings.get_setting('from_email'),
            'from_name': SystemSettings.get_setting('from_name', 'KAST Security'),
            'use_tls': SystemSettings.get_setting('use_tls', True),
            'use_ssl': SystemSettings.get_setting('use_ssl', False)
        }
        
        # Check if email is enabled
        email_enabled = SystemSettings.get_setting('email_enabled', False)
        if not email_enabled:
            return {'success': False, 'error': 'Email functionality is disabled in system settings'}
        
        # Update task state to show progress
        self.update_state(state='PROGRESS', meta={'status': 'sending', 'scan_id': scan_id})
        
        # Send email
        current_app.logger.info(f"Sending report for scan {scan_id} to {len(recipients)} recipient(s){' with zip file' if include_zip else ''}")
        success, error = send_scan_report_email(
            scan=scan,
            recipients=recipients,
            sender_name=sender_name,
            smtp_settings=smtp_settings,
            include_zip=include_zip
        )
        
        # Log the action
        if success:
            details = f'Report sent to {len(recipients)} recipient(s): {", ".join(recipients)}'
            if include_zip:
                details += ' (with results zip)'
            AuditLog.log(
                user_id=sender_user_id,
                action='email_report_sent',
                resource_type='scan',
                resource_id=scan_id,
                details=details
            )
            current_app.logger.info(f"Report email sent successfully for scan {scan_id}")
        else:
            AuditLog.log(
                user_id=sender_user_id,
                action='email_report_failed',
                resource_type='scan',
                resource_id=scan_id,
                details=f'Failed to send report: {error}'
            )
            current_app.logger.error(f"Failed to send report email for scan {scan_id}: {error}")
        
        return {
            'success': success,
            'error': error,
            'recipients_count': len(recipients)
        }
    
    except Exception as e:
        current_app.logger.exception(f"Error sending report email for scan {scan_id}: {str(e)}")
        return {'success': False, 'error': str(e)}
