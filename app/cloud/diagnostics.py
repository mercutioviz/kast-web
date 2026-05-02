"""
app/cloud/diagnostics — admin troubleshooting for cloud infrastructure.

Ported from kast/kast/scripts/diagnose_infrastructure.py with logger swap.
Exposed via GET /admin/cloud/* routes (D8) so admins can diagnose problems
without needing shell access to the server.

These functions are read-only; they never modify cloud resources.
"""

from flask import current_app


def check_provider(provider: str) -> dict:
    """Verify that a cloud provider's CLI tools and SDK dependencies are present.

    Checks Terraform binary is on PATH, provider-specific SDK can be imported,
    and that the terraform/{provider}/ config directory exists.

    Args:
        provider: One of 'aws', 'azure', 'gcp'.

    Returns:
        dict with keys:
            ok (bool): True if all checks passed.
            checks (list[dict]): Per-check results, each with
                {name, ok, message}.
    """
    raise NotImplementedError("Will be implemented in D8 (diagnostics port)")


def check_credentials(credential_id: int) -> dict:
    """Verify that a CloudCredential's keys are present and structurally valid.

    Does NOT make live API calls; only checks that the expected keys are
    present in the decrypted credentials dict and are non-empty.

    Args:
        credential_id: ID of the CloudCredential row to check.

    Returns:
        dict with keys:
            ok (bool): True if all required keys are present.
            provider (str): Provider name from the credential.
            checks (list[dict]): Per-key results, each with
                {key, present, message}.

    Raises:
        ValueError: if credential_id does not exist.
        CredentialError: if decryption fails.
    """
    raise NotImplementedError("Will be implemented in D8 (diagnostics port)")


def check_state(scan_id: int) -> dict:
    """Return the current infrastructure state for a cloud scan.

    Reads the CloudScan row and, if a Terraform state file exists,
    summarises the live resources it describes.

    Args:
        scan_id: ID of the Scan row (not CloudScan).

    Returns:
        dict with keys:
            cloud_scan_id (int | None): ID of the associated CloudScan, if any.
            status (str): CloudScan.status value, or 'no_cloud_scan'.
            terraform_state_exists (bool): True if state file is on disk.
            resources (list[dict]): Resources from terraform show, if available.
    """
    raise NotImplementedError("Will be implemented in D8 (diagnostics port)")
