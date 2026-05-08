"""
app/cloud/providers — per-provider CloudProvider implementations.

Each module (aws, azure, gcp) contains a concrete subclass of CloudProvider.
The orchestrator selects the right provider based on CloudCredential.provider.
"""
