"""
Cloud Provider Data
Static lists of regions, zones, and instance types for AWS, Azure, and GCP
Used for ZAP cloud configuration forms
"""

# AWS Configuration Options
AWS_REGIONS = [
    ('us-east-1', 'US East (N. Virginia)'),
    ('us-east-2', 'US East (Ohio)'),
    ('us-west-1', 'US West (N. California)'),
    ('us-west-2', 'US West (Oregon)'),
    ('ca-central-1', 'Canada (Central)'),
    ('eu-west-1', 'Europe (Ireland)'),
    ('eu-west-2', 'Europe (London)'),
    ('eu-west-3', 'Europe (Paris)'),
    ('eu-central-1', 'Europe (Frankfurt)'),
    ('eu-north-1', 'Europe (Stockholm)'),
    ('ap-south-1', 'Asia Pacific (Mumbai)'),
    ('ap-northeast-1', 'Asia Pacific (Tokyo)'),
    ('ap-northeast-2', 'Asia Pacific (Seoul)'),
    ('ap-southeast-1', 'Asia Pacific (Singapore)'),
    ('ap-southeast-2', 'Asia Pacific (Sydney)'),
    ('sa-east-1', 'South America (São Paulo)'),
]

AWS_INSTANCE_TYPES = [
    ('t3.medium', 't3.medium - 2 vCPU, 4 GB RAM ($0.04/hr)'),
    ('t3.large', 't3.large - 2 vCPU, 8 GB RAM ($0.08/hr)'),
    ('t3.xlarge', 't3.xlarge - 4 vCPU, 16 GB RAM ($0.17/hr)'),
    ('t3.2xlarge', 't3.2xlarge - 8 vCPU, 32 GB RAM ($0.33/hr)'),
    ('m5.large', 'm5.large - 2 vCPU, 8 GB RAM ($0.10/hr)'),
    ('m5.xlarge', 'm5.xlarge - 4 vCPU, 16 GB RAM ($0.19/hr)'),
    ('c5.large', 'c5.large - 2 vCPU, 4 GB RAM - Compute ($0.09/hr)'),
    ('c5.xlarge', 'c5.xlarge - 4 vCPU, 8 GB RAM - Compute ($0.17/hr)'),
    ('r5.large', 'r5.large - 2 vCPU, 16 GB RAM - Memory ($0.13/hr)'),
]

# Azure Configuration Options
AZURE_REGIONS = [
    ('eastus', 'East US (Virginia)'),
    ('eastus2', 'East US 2 (Virginia)'),
    ('westus', 'West US (California)'),
    ('westus2', 'West US 2 (Washington)'),
    ('centralus', 'Central US (Iowa)'),
    ('northcentralus', 'North Central US (Illinois)'),
    ('southcentralus', 'South Central US (Texas)'),
    ('westcentralus', 'West Central US (Wyoming)'),
    ('canadacentral', 'Canada Central (Toronto)'),
    ('canadaeast', 'Canada East (Quebec)'),
    ('northeurope', 'North Europe (Ireland)'),
    ('westeurope', 'West Europe (Netherlands)'),
    ('uksouth', 'UK South (London)'),
    ('ukwest', 'UK West (Cardiff)'),
    ('francecentral', 'France Central (Paris)'),
    ('germanywestcentral', 'Germany West Central (Frankfurt)'),
    ('southeastasia', 'Southeast Asia (Singapore)'),
    ('eastasia', 'East Asia (Hong Kong)'),
    ('japaneast', 'Japan East (Tokyo)'),
    ('japanwest', 'Japan West (Osaka)'),
    ('australiaeast', 'Australia East (Sydney)'),
    ('australiasoutheast', 'Australia Southeast (Melbourne)'),
]

AZURE_VM_SIZES = [
    ('Standard_B2s', 'Standard_B2s - 2 vCPU, 4 GB RAM ($0.04/hr)'),
    ('Standard_B2ms', 'Standard_B2ms - 2 vCPU, 8 GB RAM ($0.08/hr)'),
    ('Standard_B4ms', 'Standard_B4ms - 4 vCPU, 16 GB RAM ($0.17/hr)'),
    ('Standard_D2s_v3', 'Standard_D2s_v3 - 2 vCPU, 8 GB RAM ($0.10/hr)'),
    ('Standard_D4s_v3', 'Standard_D4s_v3 - 4 vCPU, 16 GB RAM ($0.19/hr)'),
    ('Standard_D8s_v3', 'Standard_D8s_v3 - 8 vCPU, 32 GB RAM ($0.38/hr)'),
    ('Standard_F2s_v2', 'Standard_F2s_v2 - 2 vCPU, 4 GB RAM - Compute ($0.09/hr)'),
    ('Standard_F4s_v2', 'Standard_F4s_v2 - 4 vCPU, 8 GB RAM - Compute ($0.17/hr)'),
    ('Standard_E2s_v3', 'Standard_E2s_v3 - 2 vCPU, 16 GB RAM - Memory ($0.13/hr)'),
]

# GCP Configuration Options
GCP_REGIONS = [
    ('us-central1', 'Iowa (us-central1)'),
    ('us-east1', 'South Carolina (us-east1)'),
    ('us-east4', 'N. Virginia (us-east4)'),
    ('us-west1', 'Oregon (us-west1)'),
    ('us-west2', 'Los Angeles (us-west2)'),
    ('us-west3', 'Salt Lake City (us-west3)'),
    ('us-west4', 'Las Vegas (us-west4)'),
    ('northamerica-northeast1', 'Montreal (northamerica-northeast1)'),
    ('europe-west1', 'Belgium (europe-west1)'),
    ('europe-west2', 'London (europe-west2)'),
    ('europe-west3', 'Frankfurt (europe-west3)'),
    ('europe-west4', 'Netherlands (europe-west4)'),
    ('europe-north1', 'Finland (europe-north1)'),
    ('asia-east1', 'Taiwan (asia-east1)'),
    ('asia-east2', 'Hong Kong (asia-east2)'),
    ('asia-northeast1', 'Tokyo (asia-northeast1)'),
    ('asia-northeast2', 'Osaka (asia-northeast2)'),
    ('asia-south1', 'Mumbai (asia-south1)'),
    ('asia-southeast1', 'Singapore (asia-southeast1)'),
    ('australia-southeast1', 'Sydney (australia-southeast1)'),
]

GCP_ZONES = {
    'us-central1': ['us-central1-a', 'us-central1-b', 'us-central1-c', 'us-central1-f'],
    'us-east1': ['us-east1-b', 'us-east1-c', 'us-east1-d'],
    'us-east4': ['us-east4-a', 'us-east4-b', 'us-east4-c'],
    'us-west1': ['us-west1-a', 'us-west1-b', 'us-west1-c'],
    'us-west2': ['us-west2-a', 'us-west2-b', 'us-west2-c'],
    'us-west3': ['us-west3-a', 'us-west3-b', 'us-west3-c'],
    'us-west4': ['us-west4-a', 'us-west4-b', 'us-west4-c'],
    'northamerica-northeast1': ['northamerica-northeast1-a', 'northamerica-northeast1-b', 'northamerica-northeast1-c'],
    'europe-west1': ['europe-west1-b', 'europe-west1-c', 'europe-west1-d'],
    'europe-west2': ['europe-west2-a', 'europe-west2-b', 'europe-west2-c'],
    'europe-west3': ['europe-west3-a', 'europe-west3-b', 'europe-west3-c'],
    'europe-west4': ['europe-west4-a', 'europe-west4-b', 'europe-west4-c'],
    'europe-north1': ['europe-north1-a', 'europe-north1-b', 'europe-north1-c'],
    'asia-east1': ['asia-east1-a', 'asia-east1-b', 'asia-east1-c'],
    'asia-east2': ['asia-east2-a', 'asia-east2-b', 'asia-east2-c'],
    'asia-northeast1': ['asia-northeast1-a', 'asia-northeast1-b', 'asia-northeast1-c'],
    'asia-northeast2': ['asia-northeast2-a', 'asia-northeast2-b', 'asia-northeast2-c'],
    'asia-south1': ['asia-south1-a', 'asia-south1-b', 'asia-south1-c'],
    'asia-southeast1': ['asia-southeast1-a', 'asia-southeast1-b', 'asia-southeast1-c'],
    'australia-southeast1': ['australia-southeast1-a', 'australia-southeast1-b', 'australia-southeast1-c'],
}

GCP_MACHINE_TYPES = [
    ('n1-standard-1', 'n1-standard-1 - 1 vCPU, 3.75 GB RAM ($0.05/hr)'),
    ('n1-standard-2', 'n1-standard-2 - 2 vCPU, 7.5 GB RAM ($0.10/hr)'),
    ('n1-standard-4', 'n1-standard-4 - 4 vCPU, 15 GB RAM ($0.19/hr)'),
    ('n1-standard-8', 'n1-standard-8 - 8 vCPU, 30 GB RAM ($0.38/hr)'),
    ('n2-standard-2', 'n2-standard-2 - 2 vCPU, 8 GB RAM ($0.10/hr)'),
    ('n2-standard-4', 'n2-standard-4 - 4 vCPU, 16 GB RAM ($0.19/hr)'),
    ('n2-standard-8', 'n2-standard-8 - 8 vCPU, 32 GB RAM ($0.39/hr)'),
    ('e2-medium', 'e2-medium - 1 vCPU, 4 GB RAM ($0.03/hr)'),
    ('e2-standard-2', 'e2-standard-2 - 2 vCPU, 8 GB RAM ($0.07/hr)'),
    ('e2-standard-4', 'e2-standard-4 - 4 vCPU, 16 GB RAM ($0.13/hr)'),
    ('c2-standard-4', 'c2-standard-4 - 4 vCPU, 16 GB RAM - Compute ($0.21/hr)'),
    ('c2-standard-8', 'c2-standard-8 - 8 vCPU, 32 GB RAM - Compute ($0.42/hr)'),
]


def get_gcp_zones_for_region(region):
    """Get available zones for a specific GCP region"""
    return GCP_ZONES.get(region, [])
