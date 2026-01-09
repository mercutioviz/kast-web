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


def check_terraform_installed() -> Tuple[bool, str, str]:
    """
    Check if Terraform is installed
    
    Returns:
        Tuple of (is_installed, version_string, error_message)
    """
    try:
        result = subprocess.run(
            ['terraform', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Extract version from first line (e.g., "Terraform v1.5.0")
            version = result.stdout.split('\n')[0].strip()
            return True, version, ""
        return False, "", "Terraform command failed"
    except subprocess.TimeoutExpired:
        return False, "", "Terraform command timed out"
    except FileNotFoundError:
        return False, "", "Terraform not found in PATH"
    except Exception as e:
        return False, "", str(e)


def check_aws_cli_installed() -> Tuple[bool, str, str]:
    """
    Check if AWS CLI is installed
    
    Returns:
        Tuple of (is_installed, version_string, error_message)
    """
    try:
        result = subprocess.run(
            ['aws', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # AWS CLI outputs to stderr, version format: "aws-cli/2.x.x Python/3.x.x..."
            version = result.stderr.strip() if result.stderr else result.stdout.strip()
            return True, version, ""
        return False, "", "AWS CLI command failed"
    except subprocess.TimeoutExpired:
        return False, "", "AWS CLI command timed out"
    except FileNotFoundError:
        return False, "", "AWS CLI not found in PATH"
    except Exception as e:
        return False, "", str(e)


def check_azure_cli_installed() -> Tuple[bool, str, str]:
    """
    Check if Azure CLI is installed
    
    Returns:
        Tuple of (is_installed, version_string, error_message)
    """
    try:
        result = subprocess.run(
            ['az', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Extract version from output (first line usually contains azure-cli x.x.x)
            lines = result.stdout.split('\n')
            version = lines[0].strip() if lines else "Azure CLI"
            return True, version, ""
        return False, "", "Azure CLI command failed"
    except subprocess.TimeoutExpired:
        return False, "", "Azure CLI command timed out"
    except FileNotFoundError:
        return False, "", "Azure CLI not found in PATH"
    except Exception as e:
        return False, "", str(e)


def check_gcloud_cli_installed() -> Tuple[bool, str, str]:
    """
    Check if Google Cloud CLI is installed
    
    Returns:
        Tuple of (is_installed, version_string, error_message)
    """
    try:
        result = subprocess.run(
            ['gcloud', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Extract version from first line (e.g., "Google Cloud SDK x.x.x")
            lines = result.stdout.split('\n')
            version = lines[0].strip() if lines else "Google Cloud SDK"
            return True, version, ""
        return False, "", "gcloud command failed"
    except subprocess.TimeoutExpired:
        return False, "", "gcloud command timed out"
    except FileNotFoundError:
        return False, "", "gcloud not found in PATH"
    except Exception as e:
        return False, "", str(e)


def get_cloud_tools_status() -> Dict[str, Any]:
    """
    Get status of all cloud-related tools
    
    Returns:
        Dictionary with status of Terraform and cloud provider CLIs
    """
    status = {}
    
    # Check Terraform (required for all providers)
    tf_installed, tf_version, tf_error = check_terraform_installed()
    status['terraform'] = {
        'installed': tf_installed,
        'version': tf_version if tf_installed else None,
        'error': tf_error if not tf_installed else None,
        'install_url': 'https://www.terraform.io/downloads',
        'install_cmd_ubuntu': 'wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg && echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list && sudo apt update && sudo apt install terraform'
    }
    
    # Check AWS CLI
    aws_installed, aws_version, aws_error = check_aws_cli_installed()
    status['aws'] = {
        'installed': aws_installed,
        'version': aws_version if aws_installed else None,
        'error': aws_error if not aws_installed else None,
        'install_url': 'https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html',
        'install_cmd_ubuntu': 'curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && sudo ./aws/install'
    }
    
    # Check Azure CLI
    az_installed, az_version, az_error = check_azure_cli_installed()
    status['azure'] = {
        'installed': az_installed,
        'version': az_version if az_installed else None,
        'error': az_error if not az_installed else None,
        'install_url': 'https://docs.microsoft.com/en-us/cli/azure/install-azure-cli',
        'install_cmd_ubuntu': 'curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash'
    }
    
    # Check Google Cloud CLI
    gcloud_installed, gcloud_version, gcloud_error = check_gcloud_cli_installed()
    status['gcp'] = {
        'installed': gcloud_installed,
        'version': gcloud_version if gcloud_installed else None,
        'error': gcloud_error if not gcloud_installed else None,
        'install_url': 'https://cloud.google.com/sdk/docs/install',
        'install_cmd_ubuntu': 'curl https://sdk.cloud.google.com | bash && exec -l $SHELL && gcloud init'
    }
    
    return status


def test_cloud_config(config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Test cloud provider configuration with tool detection and authentication testing
    
    Args:
        config: Cloud configuration dictionary
        
    Returns:
        Tuple of (success, detailed_message)
    """
    provider = config.get('provider', '').lower()
    
    if not provider:
        return False, "⚠️ Cloud provider not specified"
    
    if provider not in ['aws', 'azure', 'gcp']:
        return False, f"⚠️ Unsupported cloud provider: {provider}"
    
    messages = []
    has_critical_errors = False
    
    # Step 1: Check Terraform (required for ALL cloud providers)
    tf_installed, tf_version, tf_error = check_terraform_installed()
    if not tf_installed:
        messages.append("⚠️ Terraform is not installed (required for all cloud providers)")
        messages.append(f"   Install: wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg")
        messages.append(f"   Then: echo \"deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main\" | sudo tee /etc/apt/sources.list.d/hashicorp.list")
        messages.append(f"   Finally: sudo apt update && sudo apt install terraform")
        messages.append(f"   Or visit: https://www.terraform.io/downloads")
    else:
        messages.append(f"✅ Terraform installed: {tf_version}")
    
    # Step 2: Check provider-specific CLI and authentication
    if provider == 'aws':
        # Check required fields
        required_fields = ['region', 'access_key', 'secret_key']
        missing = [f for f in required_fields if not config.get(f)]
        if missing:
            has_critical_errors = True
            messages.append(f"❌ Missing required fields: {', '.join(missing)}")
        
        # Check AWS CLI
        cli_installed, cli_version, cli_error = check_aws_cli_installed()
        if not cli_installed:
            messages.append("⚠️ AWS CLI is not installed")
            messages.append("   Install: curl \"https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip\" -o \"awscliv2.zip\"")
            messages.append("   Then: unzip awscliv2.zip && sudo ./aws/install")
            messages.append("   Or visit: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
        else:
            messages.append(f"✅ AWS CLI installed: {cli_version}")
            
            # Attempt authentication test if credentials provided
            if not missing:
                try:
                    import os
                    env = os.environ.copy()
                    env['AWS_ACCESS_KEY_ID'] = config.get('access_key', '')
                    env['AWS_SECRET_ACCESS_KEY'] = config.get('secret_key', '')
                    env['AWS_DEFAULT_REGION'] = config.get('region', 'us-east-1')
                    
                    auth_result = subprocess.run(
                        ['aws', 'sts', 'get-caller-identity'],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if auth_result.returncode == 0:
                        # Parse caller identity to show account
                        try:
                            import json
                            identity = json.loads(auth_result.stdout)
                            account = identity.get('Account', 'Unknown')
                            arn = identity.get('Arn', 'Unknown')
                            messages.append(f"✅ AWS authentication successful!")
                            messages.append(f"   Account: {account}")
                            messages.append(f"   Identity: {arn}")
                        except:
                            messages.append("✅ AWS authentication successful!")
                    else:
                        error_msg = auth_result.stderr.strip()[:200]
                        messages.append(f"⚠️ AWS authentication failed: {error_msg}")
                        messages.append("   Check your access key and secret key")
                except Exception as e:
                    messages.append(f"⚠️ AWS authentication test failed: {str(e)}")
    
    elif provider == 'azure':
        # Check required fields
        required_fields = ['region', 'subscription_id', 'client_id', 'client_secret', 'tenant_id']
        missing = [f for f in required_fields if not config.get(f)]
        if missing:
            has_critical_errors = True
            messages.append(f"❌ Missing required fields: {', '.join(missing)}")
        
        # Check Azure CLI
        cli_installed, cli_version, cli_error = check_azure_cli_installed()
        if not cli_installed:
            messages.append("⚠️ Azure CLI is not installed")
            messages.append("   Install: curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash")
            messages.append("   Or visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli")
        else:
            messages.append(f"✅ Azure CLI installed: {cli_version}")
            
            # Attempt authentication test if credentials provided
            if not missing:
                try:
                    import os
                    env = os.environ.copy()
                    env['AZURE_CLIENT_ID'] = config.get('client_id', '')
                    env['AZURE_CLIENT_SECRET'] = config.get('client_secret', '')
                    env['AZURE_TENANT_ID'] = config.get('tenant_id', '')
                    
                    # Login with service principal
                    auth_result = subprocess.run(
                        ['az', 'login', '--service-principal',
                         '-u', config.get('client_id', ''),
                         '-p', config.get('client_secret', ''),
                         '--tenant', config.get('tenant_id', '')],
                        capture_output=True,
                        text=True,
                        timeout=15
                    )
                    
                    if auth_result.returncode == 0:
                        messages.append("✅ Azure authentication successful!")
                        messages.append(f"   Subscription: {config.get('subscription_id', 'Unknown')}")
                        # Logout to clean up
                        subprocess.run(['az', 'logout'], capture_output=True, timeout=5)
                    else:
                        error_msg = auth_result.stderr.strip()[:200]
                        messages.append(f"⚠️ Azure authentication failed: {error_msg}")
                        messages.append("   Check your service principal credentials")
                except Exception as e:
                    messages.append(f"⚠️ Azure authentication test failed: {str(e)}")
    
    elif provider == 'gcp':
        # Check required fields
        required_fields = ['region', 'project_id', 'credentials']
        missing = [f for f in required_fields if not config.get(f)]
        if missing:
            has_critical_errors = True
            messages.append(f"❌ Missing required fields: {', '.join(missing)}")
        
        # Check gcloud CLI
        cli_installed, cli_version, cli_error = check_gcloud_cli_installed()
        if not cli_installed:
            messages.append("⚠️ Google Cloud CLI is not installed")
            messages.append("   Install: curl https://sdk.cloud.google.com | bash")
            messages.append("   Then: exec -l $SHELL && gcloud init")
            messages.append("   Or visit: https://cloud.google.com/sdk/docs/install")
        else:
            messages.append(f"✅ Google Cloud CLI installed: {cli_version}")
            
            # Attempt authentication test if credentials provided
            if not missing:
                try:
                    import tempfile
                    import json
                    import os
                    
                    # GCP credentials should be a JSON string
                    credentials = config.get('credentials', '')
                    
                    # Write credentials to temp file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        f.write(credentials)
                        creds_file = f.name
                    
                    try:
                        env = os.environ.copy()
                        env['GOOGLE_APPLICATION_CREDENTIALS'] = creds_file
                        
                        # Try to list projects as auth test
                        auth_result = subprocess.run(
                            ['gcloud', 'projects', 'list', '--limit=1',
                             f'--project={config.get("project_id", "")}'],
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=15
                        )
                        
                        if auth_result.returncode == 0:
                            messages.append("✅ GCP authentication successful!")
                            messages.append(f"   Project: {config.get('project_id', 'Unknown')}")
                        else:
                            error_msg = auth_result.stderr.strip()[:200]
                            messages.append(f"⚠️ GCP authentication failed: {error_msg}")
                            messages.append("   Check your service account credentials")
                    finally:
                        # Clean up temp file
                        os.unlink(creds_file)
                except Exception as e:
                    messages.append(f"⚠️ GCP authentication test failed: {str(e)}")
    
    # Determine overall success
    # Success if no critical errors (missing tools are warnings, not errors)
    success = not has_critical_errors
    
    return success, "\n".join(messages)


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
