"""
Migration script to add ZAP integration tables and fields
Adds: ZapAutomationPlan, ZapConfiguration, ZapScanProgress models
Updates: Scan model with ZAP-specific fields
Seeds: Default automation plans and configurations
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, db
from app.models import (
    ZapAutomationPlan, ZapConfiguration, ZapScanProgress,
    Scan, User
)
from datetime import datetime


def migrate():
    """Add ZAP feature tables and seed data"""
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("ZAP INTEGRATION FEATURE MIGRATION")
        print("=" * 60)
        print()
        
        # Create tables
        print("Step 1: Creating new database tables...")
        try:
            db.create_all()
            print("✓ Tables created successfully")
        except Exception as e:
            print(f"✗ Error creating tables: {e}")
            return False
        
        print()
        
        # Seed default ZAP automation plans
        print("Step 2: Seeding default ZAP automation plans...")
        try:
            seed_default_plans()
            print("✓ Default plans seeded successfully")
        except Exception as e:
            print(f"✗ Error seeding plans: {e}")
            return False
        
        print()
        
        # Seed default ZAP configurations
        print("Step 3: Seeding default ZAP configurations...")
        try:
            seed_default_configs()
            print("✓ Default configurations seeded successfully")
        except Exception as e:
            print(f"✗ Error seeding configurations: {e}")
            return False
        
        print()
        print("=" * 60)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print()
        print("Summary:")
        print(f"  - ZAP Automation Plans: {ZapAutomationPlan.query.count()} total")
        print(f"  - ZAP Configurations: {ZapConfiguration.query.count()} total")
        print()
        return True


def seed_default_plans():
    """Create default ZAP automation plans"""
    # Get or create system admin user
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        print("  ⚠ Warning: No admin user found. Creating default admin...")
        admin = User(
            username='admin',
            email='admin@example.com',
            role='admin',
            is_active=True
        )
        admin.set_password('changeme')
        db.session.add(admin)
        db.session.commit()
        print(f"  → Created admin user (ID: {admin.id})")
    
    plans_data = [
        {
            'name': 'Quick Passive Scan',
            'description': 'Fast passive scan with spider only - ideal for development environments',
            'allow_power_users': True,
            'is_system_default': True,
            'plan_yaml': '''# Quick Passive Scan - Fast Development Testing
env:
  contexts:
    - name: "Default Context"
      urls:
        - "${TARGET_URL}"
      includePaths:
        - "${TARGET_URL}.*"
      excludePaths: []
  parameters:
    failOnError: true
    failOnWarning: false
    progressToStdout: true

jobs:
  - type: spider
    parameters:
      maxDuration: 5
      maxDepth: 5
      maxChildren: 10
      acceptCookies: true
      handleODataParametersVisited: false
      
  - type: passiveScan-wait
    parameters:
      maxDuration: 5
      
  - type: report
    parameters:
      template: traditional-html
      reportDir: "."
      reportFile: kast_report
      reportTitle: "ZAP Quick Scan Report"
      reportDescription: "Quick passive scan results for development testing"
'''
        },
        {
            'name': 'Standard Active Scan',
            'description': 'Comprehensive active scan with moderate settings - recommended for staging environments',
            'allow_power_users': True,
            'is_system_default': False,
            'plan_yaml': '''# Standard Active Scan - Staging Environment Testing
env:
  contexts:
    - name: "Default Context"
      urls:
        - "${TARGET_URL}"
      includePaths:
        - "${TARGET_URL}.*"
      excludePaths: []
  parameters:
    failOnError: true
    failOnWarning: false
    progressToStdout: true

jobs:
  - type: spider
    parameters:
      maxDuration: 10
      maxDepth: 10
      maxChildren: 20
      acceptCookies: true
      handleODataParametersVisited: false
      
  - type: spiderAjax
    parameters:
      maxDuration: 10
      maxCrawlDepth: 10
      numberOfBrowsers: 1
      inScopeOnly: true
      
  - type: passiveScan-wait
    parameters:
      maxDuration: 10
      
  - type: activeScan
    parameters:
      maxRuleDurationInMins: 10
      maxScanDurationInMins: 20
      threadPerHost: 2
      delayInMs: 0
      addQueryParam: false
      handleAntiCSRFTokens: true
      injectPluginIdInHeader: true
      scanHeadersAllRequests: true
      
  - type: passiveScan-wait
    parameters:
      maxDuration: 10
      
  - type: report
    parameters:
      template: traditional-html
      reportDir: "."
      reportFile: kast_report
      reportTitle: "ZAP Standard Active Scan Report"
      reportDescription: "Comprehensive active scan results for staging environment"
'''
        },
        {
            'name': 'Full Security Audit',
            'description': 'Comprehensive security audit with aggressive settings - use in pre-production only',
            'allow_power_users': False,  # Admin only
            'is_system_default': False,
            'plan_yaml': '''# Full Security Audit - Pre-Production Comprehensive Testing
env:
  contexts:
    - name: "Default Context"
      urls:
        - "${TARGET_URL}"
      includePaths:
        - "${TARGET_URL}.*"
      excludePaths: []
  parameters:
    failOnError: true
    failOnWarning: false
    progressToStdout: true

jobs:
  # Comprehensive Spidering
  - type: spider
    parameters:
      maxDuration: 15
      maxDepth: 15
      maxChildren: 30
      acceptCookies: true
      handleODataParametersVisited: true
      parseComments: true
      parseGit: true
      parseRobotsTxt: true
      parseSitemapXml: true
      parseSVNEntries: true
      postForm: true
      processForm: true
      
  # AJAX Spider for Single-Page Applications
  - type: spiderAjax
    parameters:
      maxDuration: 15
      maxCrawlDepth: 15
      numberOfBrowsers: 2
      inScopeOnly: true
      clickDefaultElems: true
      clickElemsOnce: true
      eventWait: 1000
      maxCrawlStates: 0
      randomInputs: true
      
  # Passive Scan After Spidering
  - type: passiveScan-wait
    parameters:
      maxDuration: 15
      
  # Aggressive Active Scan
  - type: activeScan
    parameters:
      maxRuleDurationInMins: 15
      maxScanDurationInMins: 60
      threadPerHost: 4
      delayInMs: 0
      addQueryParam: true
      handleAntiCSRFTokens: true
      injectPluginIdInHeader: true
      scanHeadersAllRequests: true
      
  # Final Passive Scan
  - type: passiveScan-wait
    parameters:
      maxDuration: 15
      
  # Generate Comprehensive Report
  - type: report
    parameters:
      template: traditional-html
      reportDir: "."
      reportFile: kast_report
      reportTitle: "ZAP Full Security Audit Report"
      reportDescription: "Comprehensive security audit with aggressive scanning - Pre-Production"
      displayReport: false
'''
        }
    ]
    
    for plan_data in plans_data:
        # Check if plan already exists
        existing = ZapAutomationPlan.query.filter_by(name=plan_data['name']).first()
        if existing:
            print(f"  → Plan '{plan_data['name']}' already exists (ID: {existing.id})")
            continue
        
        # Create new plan
        plan = ZapAutomationPlan(
            name=plan_data['name'],
            description=plan_data['description'],
            plan_yaml=plan_data['plan_yaml'],
            created_by=admin.id,
            is_system_default=plan_data['is_system_default'],
            allow_power_users=plan_data['allow_power_users'],
            is_draft=False
        )
        db.session.add(plan)
        db.session.commit()
        print(f"  ✓ Created plan: {plan_data['name']} (ID: {plan.id})")


def seed_default_configs():
    """Create default ZAP configurations"""
    # Get admin user
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        print("  ⚠ Warning: No admin user found")
        return
    
    configs_data = [
        {
            'name': 'Local Docker (Default)',
            'description': 'Run ZAP in local Docker container',
            'execution_mode': 'local',
            'is_default': True,
            'local_config': {
                'docker_image': 'ghcr.io/zaproxy/zaproxy:stable',
                'container_name': 'kast-zap',
                'host_port': 8080,
                'auto_start': True,
                'auto_remove': False,
                'memory_limit': '2g',
                'cpu_limit': '2.0',
                'network_mode': 'bridge',
                'volumes': {
                    'zap_data': '/zap/wrk'
                },
                'environment': {
                    'ZAP_PORT': '8080'
                }
            },
            'remote_config': {},
            'cloud_config': {}
        },
        {
            'name': 'Remote ZAP Instance',
            'description': 'Connect to existing remote ZAP instance',
            'execution_mode': 'remote',
            'is_default': False,
            'local_config': {},
            'remote_config': {
                'zap_url': 'http://zap-server:8080',
                'api_key': '',  # To be configured by admin
                'timeout': 300,
                'verify_ssl': True,
                'proxy_url': '',
                'retry_attempts': 3,
                'retry_delay': 5
            },
            'cloud_config': {}
        },
        {
            'name': 'AWS Cloud (Template)',
            'description': 'Template for running ZAP in AWS (requires configuration)',
            'execution_mode': 'cloud',
            'is_default': False,
            'local_config': {},
            'remote_config': {},
            'cloud_config': {
                'provider': 'aws',
                'region': 'us-east-1',
                'instance_type': 't3.medium',
                'ami_id': '',  # To be configured
                'security_group_id': '',  # To be configured
                'subnet_id': '',  # To be configured
                'key_name': '',  # To be configured
                'aws_access_key_id': '${AWS_ACCESS_KEY_ID}',  # Environment variable
                'aws_secret_access_key': '${AWS_SECRET_ACCESS_KEY}',  # Environment variable
                'auto_terminate': True,
                'max_runtime_minutes': 60,
                'tags': {
                    'Name': 'KAST-ZAP-Instance',
                    'ManagedBy': 'KAST-Web',
                    'Purpose': 'Security-Scanning'
                }
            }
        }
    ]
    
    for config_data in configs_data:
        # Check if config already exists
        existing = ZapConfiguration.query.filter_by(name=config_data['name']).first()
        if existing:
            print(f"  → Configuration '{config_data['name']}' already exists (ID: {existing.id})")
            continue
        
        # Create new configuration
        config = ZapConfiguration(
            name=config_data['name'],
            description=config_data['description'],
            execution_mode=config_data['execution_mode'],
            created_by=admin.id,
            is_active=True,
            is_default=config_data['is_default']
        )
        
        # Set encrypted configs using property setters
        if config_data['local_config']:
            config.local_config = config_data['local_config']
        if config_data['remote_config']:
            config.remote_config = config_data['remote_config']
        if config_data['cloud_config']:
            config.cloud_config = config_data['cloud_config']
        
        db.session.add(config)
        db.session.commit()
        print(f"  ✓ Created configuration: {config_data['name']} (ID: {config.id})")


if __name__ == '__main__':
    print()
    success = migrate()
    if success:
        print("You can now use ZAP integration features in KAST-Web.")
        print()
        print("Next steps:")
        print("  1. Review and configure ZAP settings in Admin Panel")
        print("  2. Ensure Docker is installed if using local mode")
        print("  3. Pull ZAP Docker image: docker pull ghcr.io/zaproxy/zaproxy:stable")
        print("  4. Configure remote/cloud settings if needed")
        print()
        sys.exit(0)
    else:
        print("Migration failed. Please check errors above.")
        sys.exit(1)
