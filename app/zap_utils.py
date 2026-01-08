"""
ZAP Integration Utilities
Helper functions for ZAP automation plan validation and configuration testing
"""

import yaml
import subprocess
import re
from typing import Tuple, Dict, List, Any, Optional

# Standard container name for all ZAP operations
# Using a single container for all configs simplifies management
KAST_ZAP_CONTAINER_NAME = "kast-zap-local"


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
    
    # Success rate
    completed = Scan.query.filter(
        Scan.zap_config_id == config_id,
        Scan.status == 'completed'
    ).count()
    
    failed = Scan.query.filter(
        Scan.zap_config_id == config_id,
        Scan.status == 'failed'
    ).count()
    
    success_rate = 0
    if total_scans > 0:
        success_rate = (completed / total_scans) * 100
    
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
        'completed': completed,
        'failed': failed,
        'success_rate': round(success_rate, 1),
        'last_used': last_used
    }


def start_zap_container(config: Dict[str, Any], config_id: int) -> Tuple[bool, str, str]:
    """
    Start a ZAP Docker container for local mode
    Note: Uses a single shared container (KAST_ZAP_CONTAINER_NAME) regardless of config_id
    
    Args:
        config: Local configuration dictionary
        config_id: Configuration ID (retained for API compatibility but not used for naming)
        
    Returns:
        Tuple of (success, message, docker_command)
    """
    docker_cmd_str = ""  # Track command for error reporting
    
    try:
        container_name = KAST_ZAP_CONTAINER_NAME
        image = config.get('docker_image', 'ghcr.io/zaproxy/zaproxy:stable')
        port = config.get('port', 8080)
        memory = config.get('memory_limit', '2g')
        api_key = 'kast-local'  # Match the API key used in remote mode
        
        # Check if container already exists
        check_cmd = ['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Names}}']
        result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
        
        if result.stdout.strip() == container_name:
            # Container exists, check if running
            status_cmd = ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}']
            status_result = subprocess.run(status_cmd, capture_output=True, text=True, timeout=5)
            
            if status_result.stdout.strip() == container_name:
                return False, f"Container '{container_name}' is already running", ' '.join(check_cmd)
            
            # Container exists but not running, start it
            start_cmd = ['docker', 'start', container_name]
            docker_cmd_str = ' '.join(start_cmd)
            result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return True, f"Started existing container '{container_name}'", docker_cmd_str
            else:
                return False, f"Failed to start container: {result.stderr}", docker_cmd_str
        
        # Check if image exists locally
        image_check_cmd = ['docker', 'images', '-q', image]
        image_result = subprocess.run(image_check_cmd, capture_output=True, text=True, timeout=5)
        
        if not image_result.stdout.strip():
            # Image needs to be pulled - this will take time
            pull_message = f"Image '{image}' not found locally. Pulling from registry (this may take 2-5 minutes)..."
        else:
            pull_message = None
        
        # Build docker run command with proper API access configuration
        docker_cmd = [
            'docker', 'run', '-d',
            '--name', container_name,
            '-p', f'{port}:8080',
            '--memory', memory,
            image,
            'zap.sh', '-daemon',
            '-host', '0.0.0.0',
            '-port', '8080',
            '-config', f'api.key={api_key}',
            '-config', 'api.addrs.addr.name=.*',
            '-config', 'api.addrs.addr.regex=true'
        ]
        docker_cmd_str = ' '.join(docker_cmd)
        
        # Use longer timeout to allow for image pulling (180 seconds = 3 minutes)
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0:
            container_id = result.stdout.strip()[:12]
            success_msg = f"Started new container '{container_name}' (ID: {container_id})"
            if pull_message:
                success_msg = f"{pull_message}\n{success_msg}"
            return True, success_msg, docker_cmd_str
        else:
            error_msg = f"Failed to start container: {result.stderr}"
            if result.stdout:
                error_msg += f"\nStdout: {result.stdout}"
            return False, error_msg, docker_cmd_str
        
    except subprocess.TimeoutExpired:
        timeout_msg = "Docker command timed out after 180 seconds. "
        timeout_msg += "This usually happens when pulling a large image. "
        timeout_msg += f"Try manually pulling the image first: docker pull {image}"
        return False, timeout_msg, docker_cmd_str if docker_cmd_str else "docker run (command not captured)"
    except FileNotFoundError:
        return False, "Docker command not found. Is Docker installed?", docker_cmd_str if docker_cmd_str else "docker"
    except Exception as e:
        return False, f"Error starting container: {str(e)}", docker_cmd_str if docker_cmd_str else "docker run (error before command built)"


def stop_zap_container(config_id: int) -> Tuple[bool, str, str]:
    """
    Stop a running ZAP Docker container
    Note: Uses a single shared container (KAST_ZAP_CONTAINER_NAME) regardless of config_id
    
    Args:
        config_id: Configuration ID (retained for API compatibility but not used for naming)
        
    Returns:
        Tuple of (success, message, docker_command)
    """
    try:
        container_name = KAST_ZAP_CONTAINER_NAME
        
        # Check if container is running
        check_cmd = ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}']
        result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
        
        if result.stdout.strip() != container_name:
            return False, f"Container '{container_name}' is not running", ' '.join(check_cmd)
        
        # Stop the container
        stop_cmd = ['docker', 'stop', container_name]
        result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return True, f"Stopped container '{container_name}'", ' '.join(stop_cmd)
        else:
            return False, f"Failed to stop container: {result.stderr}", ' '.join(stop_cmd)
        
    except subprocess.TimeoutExpired:
        return False, "Docker command timed out", "docker stop ..."
    except FileNotFoundError:
        return False, "Docker command not found", "docker"
    except Exception as e:
        return False, f"Error stopping container: {str(e)}", "docker stop ..."


def remove_zap_container(config_id: int) -> Tuple[bool, str, str]:
    """
    Remove a ZAP Docker container (stops first if running)
    Note: Uses a single shared container (KAST_ZAP_CONTAINER_NAME) regardless of config_id
    
    Args:
        config_id: Configuration ID (retained for API compatibility but not used for naming)
        
    Returns:
        Tuple of (success, message, docker_command)
    """
    try:
        container_name = KAST_ZAP_CONTAINER_NAME
        
        # Check if container exists
        check_cmd = ['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Names}}']
        result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
        
        if result.stdout.strip() != container_name:
            return False, f"Container '{container_name}' does not exist", ' '.join(check_cmd)
        
        # Force remove the container (stops if running)
        rm_cmd = ['docker', 'rm', '-f', container_name]
        result = subprocess.run(rm_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return True, f"Removed container '{container_name}'", ' '.join(rm_cmd)
        else:
            return False, f"Failed to remove container: {result.stderr}", ' '.join(rm_cmd)
        
    except subprocess.TimeoutExpired:
        return False, "Docker command timed out", "docker rm ..."
    except FileNotFoundError:
        return False, "Docker command not found", "docker"
    except Exception as e:
        return False, f"Error removing container: {str(e)}", "docker rm ..."


def get_container_status(config_id: int) -> Tuple[str, str, str]:
    """
    Get the status of a ZAP Docker container
    Note: Uses a single shared container (KAST_ZAP_CONTAINER_NAME) regardless of config_id
    
    Args:
        config_id: Configuration ID (retained for API compatibility but not used for naming)
        
    Returns:
        Tuple of (status, message, docker_command)
        status can be: 'running', 'stopped', 'not_found'
    """
    try:
        container_name = KAST_ZAP_CONTAINER_NAME
        
        # Check if container exists and is running
        running_cmd = ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Status}}']
        result = subprocess.run(running_cmd, capture_output=True, text=True, timeout=5)
        
        if result.stdout.strip():
            status_text = result.stdout.strip()
            return 'running', f"Container is running ({status_text})", ' '.join(running_cmd)
        
        # Check if container exists but is stopped
        all_cmd = ['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Status}}']
        result = subprocess.run(all_cmd, capture_output=True, text=True, timeout=5)
        
        if result.stdout.strip():
            status_text = result.stdout.strip()
            return 'stopped', f"Container exists but is not running ({status_text})", ' '.join(all_cmd)
        
        return 'not_found', f"Container '{container_name}' not found", ' '.join(all_cmd)
        
    except subprocess.TimeoutExpired:
        return 'error', "Docker command timed out", "docker ps ..."
    except FileNotFoundError:
        return 'error', "Docker command not found", "docker"
    except Exception as e:
        return 'error', f"Error checking status: {str(e)}", "docker ps ..."


def get_container_logs(config_id: int, tail: int = 100) -> Tuple[bool, str, str]:
    """
    Get logs from a ZAP Docker container
    Note: Uses a single shared container (KAST_ZAP_CONTAINER_NAME) regardless of config_id
    
    Args:
        config_id: Configuration ID (retained for API compatibility but not used for naming)
        tail: Number of lines to show from end of logs
        
    Returns:
        Tuple of (success, logs_or_error_message, docker_command)
    """
    try:
        container_name = KAST_ZAP_CONTAINER_NAME
        
        # Get container logs
        logs_cmd = ['docker', 'logs', '--tail', str(tail), container_name]
        result = subprocess.run(logs_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logs = result.stdout if result.stdout else result.stderr
            if not logs:
                logs = "(No logs available)"
            return True, logs, ' '.join(logs_cmd)
        else:
            return False, f"Failed to get logs: {result.stderr}", ' '.join(logs_cmd)
        
    except subprocess.TimeoutExpired:
        return False, "Docker command timed out", "docker logs ..."
    except FileNotFoundError:
        return False, "Docker command not found", "docker"
    except Exception as e:
        return False, f"Error getting logs: {str(e)}", "docker logs ..."


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
