"""
Import utility functions for importing CLI scan results into KAST-Web

This module provides functions to:
- Validate scan result directories
- Extract scan metadata from result files
- Import CLI scans into the database
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from flask import current_app
from app import db
from app.models import Scan, ScanResult, AuditLog


def validate_scan_directory(scan_dir):
    """
    Validate that the directory contains valid KAST scan results.
    
    Args:
        scan_dir (str): Path to scan results directory
        
    Returns:
        tuple: (is_valid, error_message, result_files)
            - is_valid (bool): True if directory is valid
            - error_message (str): Error message if invalid, None otherwise
            - result_files (list): List of *_processed.json files found
    """
    try:
        # Convert to Path object
        scan_path = Path(scan_dir)
        
        # Check if directory exists
        if not scan_path.exists():
            return False, f"Directory does not exist: {scan_dir}", []
        
        # Check if it's a directory
        if not scan_path.is_dir():
            return False, f"Path is not a directory: {scan_dir}", []
        
        # Check read permissions
        if not os.access(scan_path, os.R_OK):
            return False, f"Directory is not readable: {scan_dir}", []
        
        # Look for processed JSON files (KAST result files)
        result_files = list(scan_path.glob("*_processed.json"))
        
        if not result_files:
            return False, f"No KAST result files (*_processed.json) found in directory", []
        
        # Check if directory has already been imported
        existing_scan = Scan.query.filter_by(output_dir=str(scan_path)).first()
        if existing_scan:
            return False, f"This directory has already been imported (Scan ID: {existing_scan.id})", []
        
        return True, None, result_files
        
    except Exception as e:
        return False, f"Error validating directory: {str(e)}", []


def extract_scan_metadata(scan_dir, result_files):
    """
    Extract scan metadata from result files and directory structure.
    
    Args:
        scan_dir (str): Path to scan results directory
        result_files (list): List of Path objects for *_processed.json files
        
    Returns:
        dict: Metadata dictionary with keys:
            - target: Target domain
            - scan_mode: 'active' or 'passive'
            - plugins: Comma-separated list of plugins
            - started_at: Earliest timestamp from files
            - completed_at: Latest timestamp from files
    """
    try:
        scan_path = Path(scan_dir)
        
        # Extract target from directory name (format: target-YYYYMMDD-HHMMSS)
        dir_name = scan_path.name
        target_match = re.match(r'^(.+?)-\d{8}-\d{6}$', dir_name)
        if target_match:
            target = target_match.group(1)
        else:
            # Fallback: use directory name as target
            target = dir_name
        
        # Collect plugins and determine scan mode
        plugins = []
        active_plugins = {'nmap', 'nuclei', 'nikto', 'sqlmap'}  # Plugins that indicate active scanning
        is_active = False
        timestamps = []
        
        for result_file in result_files:
            # Extract plugin name from filename
            plugin_name = result_file.stem.replace('_processed', '')
            plugins.append(plugin_name)
            
            # Check if this is an active plugin
            if plugin_name.lower() in active_plugins:
                is_active = True
            
            # Get file modification time
            mtime = result_file.stat().st_mtime
            timestamps.append(datetime.fromtimestamp(mtime))
            
            # Try to extract additional info from JSON
            try:
                with open(result_file, 'r') as f:
                    data = json.load(f)
                    
                    # Check for target in JSON data
                    if 'target' in data and not target_match:
                        target = data['target']
                    
                    # Check for scan mode in JSON
                    if 'scan_mode' in data:
                        if data['scan_mode'] == 'active':
                            is_active = True
                    
            except Exception as e:
                current_app.logger.warning(f"Could not parse {result_file}: {e}")
                continue
        
        # Determine scan mode
        scan_mode = 'active' if is_active else 'passive'
        
        # Determine timestamps
        if timestamps:
            started_at = min(timestamps)
            completed_at = max(timestamps)
        else:
            # Fallback to directory creation time
            dir_stat = scan_path.stat()
            started_at = datetime.fromtimestamp(dir_stat.st_ctime)
            completed_at = datetime.fromtimestamp(dir_stat.st_mtime)
        
        return {
            'target': target,
            'scan_mode': scan_mode,
            'plugins': ','.join(sorted(plugins)),
            'started_at': started_at,
            'completed_at': completed_at
        }
        
    except Exception as e:
        current_app.logger.error(f"Error extracting metadata: {e}")
        raise


def import_cli_scan(scan_dir, user_id, admin_user_id):
    """
    Import a CLI scan into KAST-Web database.
    
    Args:
        scan_dir (str): Path to scan results directory
        user_id (int): ID of user to assign scan to
        admin_user_id (int): ID of admin user performing the import
        
    Returns:
        tuple: (success, scan_id, error_message)
            - success (bool): True if import successful
            - scan_id (int): ID of created scan, None if failed
            - error_message (str): Error message if failed, None otherwise
    """
    try:
        # Validate directory
        is_valid, error_msg, result_files = validate_scan_directory(scan_dir)
        if not is_valid:
            return False, None, error_msg
        
        # Extract metadata
        metadata = extract_scan_metadata(scan_dir, result_files)
        
        # Create Scan record
        scan = Scan(
            user_id=user_id,
            target=metadata['target'],
            scan_mode=metadata['scan_mode'],
            plugins=metadata['plugins'],
            parallel=False,  # Unknown for imported scans
            verbose=False,   # Unknown for imported scans
            dry_run=False,
            status='completed',  # Imported scans are already completed
            output_dir=str(scan_dir),
            source='imported',  # Mark as imported
            started_at=metadata['started_at'],
            completed_at=metadata['completed_at'],
            celery_task_id=None  # No Celery task for imported scans
        )
        
        db.session.add(scan)
        db.session.flush()  # Get the scan ID
        
        # Parse and import plugin results using existing function
        from app.tasks import parse_scan_results
        parse_scan_results(scan.id, scan_dir)
        
        # Log the import action
        AuditLog.log(
            user_id=admin_user_id,
            action='scan_imported',
            resource_type='scan',
            resource_id=scan.id,
            details=f'Imported CLI scan from {scan_dir}, assigned to user ID {user_id}. Target: {metadata["target"]}, Mode: {metadata["scan_mode"]}, Plugins: {len(result_files)}'
        )
        
        db.session.commit()
        
        current_app.logger.info(f"Successfully imported scan {scan.id} from {scan_dir}")
        return True, scan.id, None
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error importing scan: {str(e)}"
        current_app.logger.error(error_msg)
        
        # Log failed import
        try:
            AuditLog.log(
                user_id=admin_user_id,
                action='scan_import_failed',
                resource_type='scan',
                details=f'Failed to import scan from {scan_dir}: {str(e)}'
            )
        except:
            pass
        
        return False, None, error_msg


def get_import_preview(scan_dir):
    """
    Get a preview of what would be imported without actually importing.
    
    Args:
        scan_dir (str): Path to scan results directory
        
    Returns:
        dict: Preview information including:
            - valid: bool
            - error: str or None
            - metadata: dict or None
            - file_count: int
            - files: list of filenames
    """
    try:
        # Validate directory
        is_valid, error_msg, result_files = validate_scan_directory(scan_dir)
        
        if not is_valid:
            return {
                'valid': False,
                'error': error_msg,
                'metadata': None,
                'file_count': 0,
                'files': []
            }
        
        # Extract metadata
        metadata = extract_scan_metadata(scan_dir, result_files)
        
        return {
            'valid': True,
            'error': None,
            'metadata': metadata,
            'file_count': len(result_files),
            'files': [f.name for f in result_files]
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': f"Error generating preview: {str(e)}",
            'metadata': None,
            'file_count': 0,
            'files': []
        }
