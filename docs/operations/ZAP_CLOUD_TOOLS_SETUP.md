# ZAP Cloud Tools Setup Guide

## Overview

KAST-Web's ZAP integration supports deploying ZAP instances on AWS, GCP, and Azure cloud platforms. This guide covers the installation and configuration of the required tools for cloud-based ZAP deployments.

**Implementation Date**: January 2026  
**Feature**: Cloud Configuration Tool Detection and Authentication Testing

## Prerequisites

All three cloud providers require:
1. **Terraform** - Infrastructure as Code tool (required for ALL providers)
2. **Provider-specific CLI tool** - AWS CLI, Azure CLI, or gcloud CLI
3. **Valid cloud credentials** - Access keys, service principals, or service account credentials

## Tool Installation

### 1. Terraform (Required for All Providers)

Terraform manages infrastructure deployment across all cloud providers.

#### Ubuntu/Debian
```bash
# Add HashiCorp GPG key
wget -O- https://apt.releases.hashicorp.com/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

# Add HashiCorp repository
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
  https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/hashicorp.list

# Update and install
sudo apt update && sudo apt install terraform
```

#### Red Hat/CentOS/Fedora
```bash
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://rpm.releases.hashicorp.com/RHEL/hashicorp.repo
sudo yum -y install terraform
```

#### macOS
```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

#### Verify Installation
```bash
terraform --version
# Should output: Terraform v1.x.x
```

### 2. AWS CLI (For AWS Deployments)

#### Ubuntu/Debian/RHEL/macOS
```bash
# Download installer
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"

# Unzip
unzip awscliv2.zip

# Install
sudo ./aws/install

# Cleanup
rm -rf aws awscliv2.zip
```

#### Verify Installation
```bash
aws --version
# Should output: aws-cli/2.x.x Python/3.x.x...
```

#### Configure Credentials
```bash
# Interactive configuration
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

#### Test Authentication
```bash
aws sts get-caller-identity
# Should return your AWS account info
```

### 3. Azure CLI (For Azure Deployments)

#### Ubuntu/Debian
```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

#### Red Hat/CentOS/Fedora
```bash
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
sudo sh -c 'echo -e "[azure-cli]
name=Azure CLI
baseurl=https://packages.microsoft.com/yumrepos/azure-cli
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc" > /etc/yum.repos.d/azure-cli.repo'
sudo yum install azure-cli
```

#### macOS
```bash
brew update && brew install azure-cli
```

#### Verify Installation
```bash
az --version
# Should output: azure-cli 2.x.x
```

#### Configure Credentials (Service Principal)
```bash
# Login with service principal
az login --service-principal \
  -u <client-id> \
  -p <client-secret> \
  --tenant <tenant-id>

# Or set environment variables
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
```

#### Test Authentication
```bash
az account show
# Should return your Azure subscription info
```

### 4. Google Cloud CLI (For GCP Deployments)

#### Ubuntu/Debian
```bash
# Add Google Cloud SDK repository
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \
  https://packages.cloud.google.com/apt cloud-sdk main" | \
  sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# Import Google Cloud public key
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
  sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -

# Update and install
sudo apt-get update && sudo apt-get install google-cloud-cli
```

#### Red Hat/CentOS/Fedora
```bash
sudo tee -a /etc/yum.repos.d/google-cloud-sdk.repo << EOM
[google-cloud-cli]
name=Google Cloud CLI
baseurl=https://packages.cloud.google.com/yum/repos/cloud-sdk-el8-x86_64
enabled=1
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg
EOM

sudo yum install google-cloud-cli
```

#### macOS
```bash
brew install --cask google-cloud-sdk
```

#### Alternative: Interactive Installer
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

#### Verify Installation
```bash
gcloud --version
# Should output: Google Cloud SDK x.x.x
```

#### Configure Credentials (Service Account)
```bash
# Authenticate with service account key file
gcloud auth activate-service-account --key-file=/path/to/key.json

# Or set environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"

# Set default project
gcloud config set project your-project-id
```

#### Test Authentication
```bash
gcloud projects list
# Should list your GCP projects
```

## KAST-Web Integration

### Cloud Configuration in Admin Panel

1. Navigate to **Admin Panel** → **ZAP Configurations**
2. Click **Create New Configuration**
3. Select **Cloud** as execution mode
4. Choose cloud provider (AWS/Azure/GCP)
5. Fill in provider-specific credentials
6. Click **Test Connection**

### Tool Detection Features

KAST-Web automatically detects and validates:

- **Terraform Installation**: Checks if `terraform` is in PATH and version
- **Provider CLI Installation**: Checks if `aws`, `az`, or `gcloud` is available
- **Authentication**: Tests credentials by calling provider APIs
  - AWS: `aws sts get-caller-identity`
  - Azure: `az login --service-principal ...`
  - GCP: `gcloud projects list`

### System Info Display

When cloud configurations exist, the System Info page shows:

- Tool installation status (✅ Installed / ❌ Not Found)
- Version information
- Installation links and quick commands
- Authentication test results

### Configuration Form Validation

The ZAP configuration form provides real-time feedback:

- Checks tool availability when cloud mode is selected
- Shows warning if required tools are missing
- Provides installation guidance
- Displays authentication status

## Credential Security

### Best Practices

1. **Use IAM Roles** (when possible)
   - AWS: EC2 instance roles, ECS task roles
   - Azure: Managed identities
   - GCP: Service account impersonation

2. **Least Privilege Principle**
   - Grant only necessary permissions
   - Use separate credentials per environment
   - Rotate credentials regularly

3. **Secure Storage**
   - KAST-Web encrypts all credentials at rest
   - Never commit credentials to version control
   - Use environment variables for CI/CD

4. **Audit and Monitor**
   - Review cloud audit logs regularly
   - Set up alerts for unusual activity
   - Track credential usage in KAST-Web audit log

### Required Permissions

#### AWS
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:DescribeInstances",
        "ec2:CreateSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

#### Azure
- Role: `Contributor` or `Virtual Machine Contributor`
- Permissions: Create/delete VMs, manage network security groups

#### GCP
- Role: `Compute Instance Admin (v1)` or custom role
- Permissions: `compute.instances.*`, `compute.securityPolicies.*`

## Troubleshooting

### Terraform Not Found

**Symptom**: "Terraform not found in PATH"

**Solution**:
```bash
# Check if installed
which terraform

# If not found, install using instructions above

# Verify PATH includes terraform location
echo $PATH

# Add to PATH if needed (add to ~/.bashrc or ~/.profile)
export PATH="/usr/local/bin:$PATH"
```

### AWS CLI Authentication Fails

**Symptom**: "AWS authentication failed: The security token included in the request is invalid"

**Solution**:
```bash
# Verify credentials are set
aws configure list

# Test with specific credentials
AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=yyy aws sts get-caller-identity

# Check for clock skew (AWS requires accurate time)
date
# Compare with: date -u

# Regenerate access keys in AWS Console if needed
```

### Azure CLI Login Issues

**Symptom**: "Azure authentication failed: AADSTS70002: Error validating credentials"

**Solution**:
```bash
# Verify service principal credentials
az login --service-principal -u <client-id> -p <client-secret> --tenant <tenant-id> --debug

# Check if service principal exists
az ad sp show --id <client-id>

# Verify role assignments
az role assignment list --assignee <client-id>

# Create new service principal if needed
az ad sp create-for-rbac --name "kast-web-sp" --role Contributor
```

### GCP Authentication Problems

**Symptom**: "GCP authentication failed: Could not load the default credentials"

**Solution**:
```bash
# Verify service account key file
cat /path/to/key.json | jq .

# Verify credentials are activated
gcloud auth list

# Re-activate with key file
gcloud auth activate-service-account --key-file=/path/to/key.json

# Verify project is set
gcloud config get-value project

# Test with explicit key file
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json gcloud projects list
```

### Permission Denied Errors

**Symptom**: "Permission denied" or "403 Forbidden"

**Solution**:
1. Verify IAM roles/permissions are correctly assigned
2. Check if MFA is required (not supported for automation)
3. Ensure service account/principal is active
4. Review cloud provider audit logs for denial reasons
5. Test permissions with minimal operation first

## Production Deployment

### Recommendations

1. **Separate Credentials**
   - Dev/staging/prod environments use different credentials
   - Limited scope per environment

2. **Infrastructure as Code**
   - Use Terraform workspaces
   - Version control Terraform configs
   - Implement approval workflows

3. **Monitoring**
   - Set up CloudWatch/Azure Monitor/Cloud Monitoring
   - Alert on unexpected resource creation
   - Track costs and usage

4. **Backup and DR**
   - Regular snapshots of ZAP instances
   - Documented recovery procedures
   - Tested failover scenarios

5. **Compliance**
   - Encrypt data in transit and at rest
   - Log all API calls
   - Regular security audits
   - Comply with industry standards (PCI-DSS, HIPAA, etc.)

## Quick Reference

### Installation Commands (Ubuntu)

```bash
# Install all tools at once
# Terraform
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform

# AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && sudo ./aws/install && rm -rf aws awscliv2.zip

# Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Google Cloud CLI
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
sudo apt-get update && sudo apt-get install google-cloud-cli
```

### Verification Commands

```bash
# Check all tools
terraform --version
aws --version
az --version
gcloud --version

# Test authentication
aws sts get-caller-identity
az account show
gcloud projects list
```

## Support

For issues or questions:
1. Check KAST-Web System Info page for tool status
2. Review audit logs for error details
3. Test tools manually with verification commands
4. Consult cloud provider documentation
5. Use `/reportbug` command in KAST-Web

## Related Documentation

- [ZAP Integration Phase 2](ZAP_INTEGRATION_PHASE2.md) - ZAP admin panel features
- [System Information Feature](SYSTEM_INFO_FEATURE.md) - System info page details
- [Production Deployment](PRODUCTION_DEPLOYMENT.md) - Production setup guide

---

**Last Updated**: January 2026  
**Version**: 1.0