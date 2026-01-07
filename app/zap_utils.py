"""
ZAP Integration Utilities
Helper functions for ZAP automation plan validation and configuration testing
"""

import yaml
import subprocess
import re
from typing import Tuple, Dict, List, Any, Optional


def validate_plan_yaml(yaml_content: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Validate ZAP Automation Framework YAML plan
    
    Args:
        yaml_content: YAML string content
        
    Returns:
        Tuple of (is_valid, error_message, parsed_data)
    """
    if not yaml_content or not yaml_content.strip():
        return False, "YAML content cannot be empty", None
    
    try:
        # Parse YAML
        data = yaml.safe_load(yaml_content)
        
        if not isinstance(data, dict):
            return False, "YAML must be a dictionary/object", None
        
        # Check for required top-level fields
        if 'env' not in data:
            return False, "Missing required 'env' section", None
        
        env = data['env']
        if not isinstance(env, dict):
            return False, "'env' section must be a dictionary", None
        
        # Validate env.contexts
        if 'contexts' not in env:
            return False, "Missing required 'env.contexts' section", None
        
        contexts = env['contexts']
        if not isinstance(contexts, list) or len(contexts) == 0:
            return False, "'env.contexts' must be a non-empty list", None
        
        # Validate each context has a URL
        for i, context in enumerate(contexts):
            if not isinstance(context, dict):
                return False, f"Context {i} must be a dictionary", None
            if 'urls' not in context:
                return False, f"Context {i} missing required 'urls' field", None
        
        # Check for jobs section (optional but recommended)
        if 'jobs' in data:
            jobs = data['jobs']
            if not isinstance(jobs, list):
                return False, "'jobs' section must be a list", None
            
            # Validate job structure
            for i, job in enumerate(jobs):
                if not isinstance(job, dict):
                    return False, f"Job {i} must be a dictionary", None
                if 'type' not in job:
                    return False, f"Job {i} missing required 'type' field", None
        
        return True, None, data
        
    except yaml.YAMLError as e:
        return False, f"YAML parsing error: {str(e)}", None
    except Exception as e:
        return False, f"Validation error: {str(e)}", None


def parse_plan_jobs(yaml_content: str) -> List[Dict[str, Any]]:
    """
    Extract and parse job information from ZAP automation plan
    
    Args:
        yaml_content: YAML string content
        
    Returns:
        List of job dictionaries with type, name, and parameters
    """
    jobs_info = []
    
    try:
        data = yaml.safe_load(yaml_content)
        
        if not isinstance(data, dict) or 'jobs' not in data:
            return jobs_info
        
        for job in data.get('jobs', []):
            if not isinstance(job, dict):
                continue
            
            job_info = {
                'type': job.get('type', 'unknown'),
                'name': job.get('name', job.get('type', 'Unnamed')),
                'parameters': {}
            }
            
            # Extract common parameters based on job type
            job_type = job.get('type', '')
            
            if job_type == 'spider':
                job_info['parameters']['max_duration'] = job.get('parameters', {}).get('maxDuration', 'Not set')
                job_info['parameters']['max_depth'] = job.get('parameters', {}).get('maxDepth', 'Not set')
            elif job_type == 'spiderAjax':
                job_info['parameters']['max_duration'] = job.get('parameters', {}).get('maxDuration', 'Not set')
                job_info['parameters']['max_crawl_depth'] = job.get('parameters', {}).get('maxCrawlDepth', 'Not set')
            elif job_type == 'activeScan':
                job_info['parameters']['policy'] = job.get('parameters', {}).get('policy', 'Default')
                job_info['parameters']['max_scan_duration'] = job.get('parameters', {}).get('maxScanDurationInMins', 'Not set')
            elif job_type == 'passiveScan-wait':
                job_info['parameters']['max_duration'] = job.get('parameters', {}).get('maxDuration', 'Not set')
            
            jobs_info.append(job_info)
            
    except Exception:
        pass
    
    return jobs_info


def test_docker_connection(config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Test Docker availability and configuration
    
    Args:
        config: Local configuration dictionary
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Check if Docker is installed
        result = subprocess.run(
            ['docker', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return False, "Docker is not installed or not in PATH"
        
        docker_version = result.stdout.strip()
        
        # Check if Docker daemon is running
        result = subprocess.run(
            ['docker', 'ps'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return False, "Docker daemon is not running"
        
        # Check if specified image exists or can be pulled
        image = config.get('docker_image', 'ghcr.io/zaproxy/zaproxy:stable')
        result = subprocess.run(
            ['docker', 'images', '-q', image],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return True, f"Docker is ready. Image '{image}' is available. {docker_version}"
        else:
            return True, f"Docker is ready. Image '{image}' will be pulled on first use. {docker_version}"
        
    except subprocess.TimeoutExpired:
        return False, "Docker command timed out"
    except FileNotFoundError:
        return False, "Docker command not found. Please install Docker."
    except Exception as e:
        return False, f"Error testing Docker: {str(e)}"


def test_remote_connection(config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Test connection to remote ZAP instance
    
    Args:
        config: Remote configuration dictionary
        
    Returns:
        Tuple of (success, message)
    """
    try:
        import requests
        
        zap_url = config.get('zap_url', '')
        api_key = config.get('api_key', '')
        timeout = config.get('timeout', 30)
        verify_ssl = config.get('verify_ssl', True)
        
        if not zap_url:
            return False, "ZAP URL is not configured"
        
        # Construct API endpoint
        if not zap_url.endswith('/'):
            zap_url += '/'
        
        # Try to access ZAP API version endpoint
        api_url = f"{zap_url}JSON/core/view/version/"
        params = {}
        if api_key:
            params['apikey'] = api_key
        
        response = requests.get(
            api_url,
            params=params,
            timeout=timeout,
            verify=verify_ssl
        )
        
        if response.status_code == 200:
            data = response.json()
            version = data.get('version', 'Unknown')
            return True, f"Successfully connected to ZAP {version} at {zap_url}"
        elif response.status_code == 401:
            return False, "Authentication failed. Check API key."
        else:
            return False, f"Connection failed with status code {response.status_code}"
        
    except ImportError:
        return False, "requests library not installed"
    except requests.exceptions.Timeout:
        return False, f"Connection timeout after {timeout} seconds"
    except requests.exceptions.SSLError:
        return False, "SSL certificate verification failed. Consider disabling SSL verification for self-signed certificates."
    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to {zap_url}. Check URL and network connectivity."
    except Exception as e:
        return False, f"Connection error: {str(e)}"


def test_cloud_config(config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Test cloud provider configuration
    
    Args:
        config: Cloud configuration dictionary
        
    Returns:
        Tuple of (success, message)
    """
    provider = config.get('provider', '')
    
    if not provider:
        return False, "Cloud provider not specified"
    
    # Basic validation
    required_fields = {
        'aws': ['region', 'access_key', 'secret_key'],
        'azure': ['region', 'subscription_id', 'client_id', 'client_secret'],
        'gcp': ['region', 'project_id', 'credentials']
    }
    
    if provider not in required_fields:
        return False, f"Unsupported cloud provider: {provider}"
    
    missing = []
    for field in required_fields[provider]:
        if not config.get(field):
            missing.append(field)
    
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    
    # Note: Full cloud provider testing requires SDK libraries and actual API calls
    # This is a basic configuration validation
    return True, f"Cloud configuration appears valid for {provider.upper()}. Note: Actual cloud connectivity not tested."


def get_plan_statistics(plan_id: int) -> Dict[str, Any]:
    """
    Get usage statistics for a ZAP automation plan
    
    Args:
        plan_id: Plan ID
        
    Returns:
        Dictionary with usage statistics
    """
    from app.models import ZapAutomationPlan, Scan
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    plan = ZapAutomationPlan.query.get(plan_id)
    if not plan:
        return {}
    
    # Total usage
    total_scans = Scan.query.filter_by(zap_plan_id=plan_id).count()
    
    # Recent usage (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_scans = Scan.query.filter(
        Scan.zap_plan_id == plan_id,
        Scan.started_at >= thirty_days_ago
    ).count()
    
    # Success rate
    completed = Scan.query.filter(
        Scan.zap_plan_id == plan_id,
        Scan.status == 'completed'
    ).count()
    
    failed = Scan.query.filter(
        Scan.zap_plan_id == plan_id,
        Scan.status == 'failed'
    ).count()
    
    success_rate = 0
    if total_scans > 0:
        success_rate = (completed / total_scans) * 100
    
    # Last used
    last_scan = Scan.query.filter_by(zap_plan_id=plan_id).order_by(
        Scan.started_at.desc()
    ).first()
    
    last_used = None
    if last_scan:
        last_used = last_scan.started_at
    
    return {
        'total_scans': total_scans,
        'recent_scans': recent_scans,
        'completed': completed,
        'failed': failed,
        'success_rate': round(success_rate, 1),
        'last_used': last_used
    }


def get_config_statistics(config_id: int) -> Dict[str, Any]:
    """
    Get usage statistics for a ZAP configuration
    
    Args:
        config_id: Configuration ID
        
    Returns:
        Dictionary with usage statistics
    """
    from app.models import ZapConfiguration, Scan
    from datetime import datetime, timedelta
    
    config = ZapConfiguration.query.get(config_id)
    if not config:
        return {}
    
    # Total usage
    total_scans = Scan.query.filter_by(zap_config_id=config_id).count()
    
    # Recent usage (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_scans = Scan.query.filter(
        Scan.zap_config_id == config_id,
        Scan.started_at >= thirty_days_ago
    ).count()
    
    # Last used
    last_scan = Scan.query.filter_by(zap_config_id=config_id).order_by(
        Scan.started_at.desc()
    ).first()
    
    last_used = None
    if last_scan:
        last_used = last_scan.started_at
    
    return {
        'total_scans': total_scans,
        'recent_scans': recent_scans,
        'last_used': last_used
    }


def extract_plan_summary(yaml_content: str) -> Dict[str, Any]:
    """
    Extract a summary of key information from a ZAP automation plan
    
    Args:
        yaml_content: YAML string content
        
    Returns:
        Dictionary with plan summary
    """
    summary = {
        'contexts': 0,
        'jobs': 0,
        'job_types': [],
        'has_spider': False,
        'has_ajax_spider': False,
        'has_active_scan': False,
        'estimated_duration': 'Unknown'
    }
    
    try:
        data = yaml.safe_load(yaml_content)
        
        if not isinstance(data, dict):
            return summary
        
        # Count contexts
        if 'env' in data and 'contexts' in data['env']:
            summary['contexts'] = len(data['env']['contexts'])
        
        # Analyze jobs
        if 'jobs' in data and isinstance(data['jobs'], list):
            summary['jobs'] = len(data['jobs'])
            
            job_types = set()
            total_duration = 0
            
            for job in data['jobs']:
                if not isinstance(job, dict):
                    continue
                
                job_type = job.get('type', '')
                job_types.add(job_type)
                
                if job_type == 'spider':
                    summary['has_spider'] = True
                    duration = job.get('parameters', {}).get('maxDuration', 0)
                    if duration:
                        total_duration += int(duration)
                elif job_type == 'spiderAjax':
                    summary['has_ajax_spider'] = True
                    duration = job.get('parameters', {}).get('maxDuration', 0)
                    if duration:
                        total_duration += int(duration)
                elif job_type == 'activeScan':
                    summary['has_active_scan'] = True
                    duration = job.get('parameters', {}).get('maxScanDurationInMins', 0)
                    if duration:
                        total_duration += int(duration)
            
            summary['job_types'] = sorted(list(job_types))
            
            if total_duration > 0:
                summary['estimated_duration'] = f"~{total_duration} minutes"
        
    except Exception:
        pass
    
    return summary
