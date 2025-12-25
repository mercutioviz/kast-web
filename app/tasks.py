"""
Celery tasks for asynchronous scan execution
"""

import subprocess
import json
import os
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
    from app.models import ScanConfigProfile
    import tempfile
    import yaml
    
    try:
        # Get scan from database
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return {'success': False, 'error': 'Scan not found'}
        
        # ============================================================
        # DEBUGGING: Log comprehensive pre-execution environment
        # ============================================================
        current_app.logger.info("="*80)
        current_app.logger.info(f"=== PRE-EXECUTION ENVIRONMENT DEBUG (Scan ID: {scan_id}) ===")
        current_app.logger.info("="*80)
        
        # Working directory and user context
        current_app.logger.info(f"Current Working Directory: {os.getcwd()}")
        current_app.logger.info(f"Process UID: {os.getuid()}, GID: {os.getgid()}")
        
        # Key environment variables
        current_app.logger.info(f"HOME: {os.environ.get('HOME', 'NOT SET')}")
        current_app.logger.info(f"USER: {os.environ.get('USER', 'NOT SET')}")
        current_app.logger.info(f"PATH: {os.environ.get('PATH', 'NOT SET')}")
        current_app.logger.info(f"TMPDIR: {os.environ.get('TMPDIR', 'NOT SET')}")
        current_app.logger.info(f"PWD: {os.environ.get('PWD', 'NOT SET')}")
        
        # Python environment
        current_app.logger.info(f"Python executable: {os.sys.executable}")
        current_app.logger.info(f"Python version: {os.sys.version}")
        
        # Generate output directory name with absolute path
        from app.utils import get_kast_results_dir
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = get_kast_results_dir() / f"{target}-{timestamp}"
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Log output directory details
        current_app.logger.info(f"Output directory: {output_dir}")
        current_app.logger.info(f"Output directory exists: {output_dir.exists()}")
        current_app.logger.info(f"Output directory is writable: {os.access(output_dir, os.W_OK)}")
        current_app.logger.info(f"Output directory permissions: {oct(output_dir.stat().st_mode)[-3:]}")
        
        # Create execution log file
        log_file_path = output_dir / 'kast_execution.log'
        
        # Update scan status and output directory BEFORE starting the scan
        scan.status = 'running'
        scan.output_dir = str(output_dir)
        scan.execution_log_path = str(log_file_path)
        db.session.commit()
        
        # Handle config profile if specified
        config_file_path = None
        temp_config_fd = None
        
        if scan.config_profile_id:
            profile = db.session.get(ScanConfigProfile, scan.config_profile_id)
            if profile:
                current_app.logger.info(f"Using config profile: {profile.name} (ID: {profile.id})")
                
                # Create temporary config file
                temp_config_fd, config_file_path = tempfile.mkstemp(suffix='.yaml', prefix='kast_config_')
                
                try:
                    # Write profile YAML to temp file
                    with os.fdopen(temp_config_fd, 'w') as f:
                        f.write(profile.config_yaml)
                    temp_config_fd = None  # Mark as handled
                    
                    current_app.logger.info(f"Created temporary config file: {config_file_path}")
                except Exception as e:
                    current_app.logger.error(f"Error creating config file: {e}")
                    if temp_config_fd:
                        os.close(temp_config_fd)
                    if config_file_path and os.path.exists(config_file_path):
                        os.unlink(config_file_path)
                    config_file_path = None
            else:
                current_app.logger.warning(f"Config profile ID {scan.config_profile_id} not found")
        
        # Build command
        kast_cli = current_app.config['KAST_CLI_PATH']
        cmd = [kast_cli, '-t', target, '-m', scan_mode, '--format', 'both']
        
        # Add config file if we created one
        if config_file_path:
            cmd.extend(['--config', config_file_path])
            current_app.logger.info(f"Added --config argument: {config_file_path}")
        
        # Add config overrides if specified (power users/admins only)
        if scan.config_overrides:
            # Parse comma-separated overrides: "key1=value1,key2=value2"
            overrides = [o.strip() for o in scan.config_overrides.split(',') if o.strip()]
            for override in overrides:
                cmd.extend(['--set', override])
            current_app.logger.info(f"Added {len(overrides)} config override(s): {overrides}")
        
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
        
        current_app.logger.info(f"Full command to execute: {' '.join(cmd)}")
        current_app.logger.info(f"Command list: {cmd}")
        
        # ============================================================
        # DEBUGGING: Capture file system state BEFORE execution
        # ============================================================
        current_app.logger.info("="*80)
        current_app.logger.info("=== BEFORE EXECUTION: File System State ===")
        try:
            files_before = set(output_dir.iterdir())
            current_app.logger.info(f"Files in output dir BEFORE scan: {[f.name for f in files_before]}")
        except Exception as e:
            current_app.logger.warning(f"Could not list files before scan: {e}")
            files_before = set()
        
        # Write command to execution log
        with open(log_file_path, 'w') as log_file:
            log_file.write("="*80 + "\n")
            log_file.write("KAST Web Execution Log\n")
            log_file.write("="*80 + "\n\n")
            log_file.write(f"Scan ID: {scan_id}\n")
            log_file.write(f"Target: {target}\n")
            log_file.write(f"Mode: {scan_mode}\n")
            log_file.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            log_file.write("Command executed:\n")
            log_file.write(f"  {' '.join(cmd)}\n\n")
            log_file.write("="*80 + "\n\n")
        
        # Execute scan and capture output
        current_app.logger.info(f"Starting subprocess with Popen...")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        current_app.logger.info(f"Subprocess PID: {process.pid}")
        current_app.logger.info(f"Subprocess started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Update task state to show progress
        self.update_state(state='PROGRESS', meta={'status': 'running', 'scan_id': scan_id})
        
        # Wait for process to complete
        current_app.logger.info(f"Waiting for subprocess to complete (timeout: 3600s)...")
        stdout, stderr = process.communicate(timeout=3600)  # 1 hour timeout
        
        current_app.logger.info(f"Subprocess completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        current_app.logger.info(f"Subprocess return code: {process.returncode}")
        
        # ============================================================
        # DEBUGGING: Check file system state AFTER execution
        # ============================================================
        current_app.logger.info("="*80)
        current_app.logger.info("=== AFTER EXECUTION: File System State ===")
        
        try:
            files_after = set(output_dir.iterdir())
            new_files = files_after - files_before
            current_app.logger.info(f"Files in output dir AFTER scan: {[f.name for f in files_after]}")
            current_app.logger.info(f"NEW files created during scan: {[f.name for f in new_files]}")
            
            # Specifically check for katana.txt
            katana_file = output_dir / "katana.txt"
            current_app.logger.info(f"katana.txt exists in output dir: {katana_file.exists()}")
            
            if not katana_file.exists():
                # Check if it was created in the working directory instead
                cwd_katana = Path(os.getcwd()) / "katana.txt"
                current_app.logger.info(f"katana.txt exists in CWD ({os.getcwd()}): {cwd_katana.exists()}")
                
                # Check in /tmp
                tmp_katana = Path("/tmp") / "katana.txt"
                current_app.logger.info(f"katana.txt exists in /tmp: {tmp_katana.exists()}")
                
                # Search for any files with 'katana' in the name
                current_app.logger.info("Searching for any files with 'katana' in name...")
                for file in output_dir.rglob("*katana*"):
                    current_app.logger.info(f"  Found: {file}")
            else:
                # If it exists, log details
                stat_info = katana_file.stat()
                current_app.logger.info(f"katana.txt size: {stat_info.st_size} bytes")
                current_app.logger.info(f"katana.txt mtime: {datetime.fromtimestamp(stat_info.st_mtime)}")
                
        except Exception as e:
            current_app.logger.error(f"Error checking files after scan: {e}")
        
        # Append stdout and stderr to log file
        with open(log_file_path, 'a') as log_file:
            log_file.write("STDOUT:\n")
            log_file.write("-"*80 + "\n")
            log_file.write(stdout if stdout else "(no output)\n")
            log_file.write("\n" + "="*80 + "\n\n")
            
            log_file.write("STDERR:\n")
            log_file.write("-"*80 + "\n")
            log_file.write(stderr if stderr else "(no errors)\n")
            log_file.write("\n" + "="*80 + "\n\n")
            
            log_file.write(f"Return Code: {process.returncode}\n")
            log_file.write(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write("="*80 + "\n")
        
        # ============================================================
        # DEBUGGING: Log stdout/stderr for analysis
        # ============================================================
        current_app.logger.info("="*80)
        current_app.logger.info("=== SUBPROCESS OUTPUT ===")
        current_app.logger.info(f"STDOUT length: {len(stdout) if stdout else 0} characters")
        current_app.logger.info(f"STDERR length: {len(stderr) if stderr else 0} characters")
        
        # Log first 500 chars of stdout (to see plugin execution)
        if stdout:
            current_app.logger.info("STDOUT (first 500 chars):")
            current_app.logger.info(stdout[:500])
        
        # Log all of stderr if present
        if stderr:
            current_app.logger.info("STDERR (full):")
            current_app.logger.info(stderr)
        
        # Search for katana-specific messages in output
        if stdout and 'katana' in stdout.lower():
            current_app.logger.info("Katana mentioned in STDOUT - extracting relevant lines:")
            for line in stdout.split('\n'):
                if 'katana' in line.lower():
                    current_app.logger.info(f"  {line}")
        
        if stderr and 'katana' in stderr.lower():
            current_app.logger.info("Katana mentioned in STDERR - extracting relevant lines:")
            for line in stderr.split('\n'):
                if 'katana' in line.lower():
                    current_app.logger.info(f"  {line}")
        
        current_app.logger.info("="*80)
        
        # Update scan with results
        scan.output_dir = str(output_dir)
        scan.completed_at = datetime.utcnow()
        
        if process.returncode == 0:
            scan.status = 'completed'
            db.session.commit()
            
            # Parse execution log to create per-plugin log files
            parse_plugin_logs(log_file_path, output_dir)
            
            # Parse results and extract plugin errors
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
            
            # Parse execution log to create per-plugin log files even on failure
            parse_plugin_logs(log_file_path, output_dir)
            
            # Still parse results to capture any plugin-level errors
            parse_scan_results(scan_id, output_dir)
            
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
    
    finally:
        # Clean up temporary config file if it was created
        if config_file_path and os.path.exists(config_file_path):
            try:
                os.unlink(config_file_path)
                current_app.logger.info(f"Cleaned up temporary config file: {config_file_path}")
            except Exception as e:
                current_app.logger.warning(f"Could not delete temporary config file: {e}")


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
                disposition = data.get('disposition', 'unknown')
                
                # Count findings correctly - look at results array within findings
                findings_data = data.get('findings', {})
                if isinstance(findings_data, dict):
                    # findings is a dict with a 'results' key containing the actual findings
                    findings_count = len(findings_data.get('results', []))
                else:
                    # fallback: findings is a list
                    findings_count = len(findings_data) if isinstance(findings_data, list) else 0
                
                # Extract error message if plugin failed
                error_message = extract_plugin_error(data, disposition)
                
                # Get file modification time as executed_at
                file_mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                
                # Check if result already exists
                existing_result = ScanResult.query.filter_by(
                    scan_id=scan_id,
                    plugin_name=plugin_name
                ).first()
                
                if existing_result:
                    # Update existing result
                    existing_result.status = disposition
                    existing_result.findings_count = findings_count
                    existing_result.processed_output_path = str(json_file)
                    existing_result.executed_at = file_mtime
                    existing_result.error_message = error_message
                else:
                    # Create new scan result entry
                    result = ScanResult(
                        scan_id=scan_id,
                        plugin_name=plugin_name,
                        status=disposition,
                        findings_count=findings_count,
                        processed_output_path=str(json_file),
                        executed_at=file_mtime,
                        error_message=error_message
                    )
                    db.session.add(result)
            
            except Exception as e:
                current_app.logger.error(f"Error parsing {json_file}: {str(e)}")
        
        db.session.commit()
    
    except Exception as e:
        current_app.logger.exception(f"Error parsing scan results: {str(e)}")


def extract_plugin_error(plugin_data, disposition):
    """
    Extract error message from plugin JSON data
    
    Args:
        plugin_data: Parsed plugin JSON data
        disposition: Plugin disposition (success, fail, etc.)
    
    Returns:
        str: Error message or None
    """
    # Only extract errors for failed plugins
    if disposition != 'fail':
        return None
    
    error_msg = None
    
    # Try multiple locations where error information might be stored
    # Different plugins may store error info in different places
    
    # 1. Check for top-level 'error' field
    if 'error' in plugin_data:
        error_msg = str(plugin_data['error'])
    
    # 2. Check for 'message' field
    elif 'message' in plugin_data:
        error_msg = str(plugin_data['message'])
    
    # 3. Check for 'error_message' field
    elif 'error_message' in plugin_data:
        error_msg = str(plugin_data['error_message'])
    
    # 4. Check within findings dict
    elif 'findings' in plugin_data:
        findings = plugin_data['findings']
        if isinstance(findings, dict):
            if 'error' in findings:
                error_msg = str(findings['error'])
            elif 'message' in findings:
                error_msg = str(findings['message'])
    
    # 5. Check for 'details' field
    elif 'details' in plugin_data:
        error_msg = str(plugin_data['details'])
    
    # 6. Check for 'reason' field
    elif 'reason' in plugin_data:
        error_msg = str(plugin_data['reason'])
    
    # Truncate if too long (database field limit)
    if error_msg and len(error_msg) > 1000:
        error_msg = error_msg[:997] + "..."
    
    return error_msg


def parse_plugin_logs(execution_log_path, output_dir):
    """
    Parse the execution log and create individual log files for each plugin
    
    Args:
        execution_log_path: Path to the main execution log
        output_dir: Directory where plugin logs should be written
    """
    from flask import current_app
    
    try:
        # Read the execution log
        with open(execution_log_path, 'r') as f:
            log_content = f.read()
        
        # Common patterns that indicate plugin execution in KAST output
        # These patterns help identify where each plugin's output starts
        plugin_patterns = [
            r'\[[\+\-\*]\]\s*(?:Running|Executing)\s+plugin[:\s]+(\w+)',
            r'\[[\+\-\*]\]\s*Plugin[:\s]+(\w+)',
            r'^\s*(\w+)\s*plugin',
            r'Starting\s+(\w+)',
        ]
        
        import re
        
        # Split log into lines for processing
        lines = log_content.split('\n')
        
        # Track current plugin and its output
        current_plugin = None
        plugin_logs = {}
        
        for line in lines:
            # Check if this line indicates a new plugin starting
            plugin_found = False
            for pattern in plugin_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    plugin_name = match.group(1).lower()
                    current_plugin = plugin_name
                    if current_plugin not in plugin_logs:
                        plugin_logs[current_plugin] = []
                    plugin_logs[current_plugin].append(line)
                    plugin_found = True
                    break
            
            # If no new plugin found, add line to current plugin's log
            if not plugin_found and current_plugin:
                plugin_logs[current_plugin].append(line)
            
            # Check for plugin completion/failure markers
            if current_plugin and any(marker in line.lower() for marker in 
                ['completed', 'failed', 'finished', 'done', 'error']):
                # This might be the end of this plugin's output
                # Continue collecting until we see a new plugin start
                pass
        
        # Write individual plugin log files
        output_path = Path(output_dir)
        for plugin_name, log_lines in plugin_logs.items():
            if log_lines:  # Only write if there's content
                plugin_log_file = output_path / f"{plugin_name}_plugin.log"
                with open(plugin_log_file, 'w') as f:
                    f.write("="*80 + "\n")
                    f.write(f"Plugin: {plugin_name}\n")
                    f.write("="*80 + "\n\n")
                    f.write('\n'.join(log_lines))
                    f.write("\n\n" + "="*80 + "\n")
                
                current_app.logger.info(f"Created plugin log: {plugin_log_file}")
        
        current_app.logger.info(f"Parsed {len(plugin_logs)} plugin logs from execution log")
        
    except Exception as e:
        current_app.logger.error(f"Error parsing plugin logs: {str(e)}")


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
