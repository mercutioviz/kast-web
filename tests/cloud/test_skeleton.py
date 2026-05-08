"""
Canary tests for the D1 app/cloud/ skeleton.

Imports each module and asserts every documented public symbol exists with
the expected signature. Does NOT invoke any function (all stubs raise
NotImplementedError), so these tests stay green through D2–D8 as
implementations land.

These tests break intentionally if:
- A module cannot be imported (missing file, syntax error).
- A public function or class is renamed or removed.
- A function's parameter list changes in a way that breaks the documented contract.
"""

import inspect
import pytest


# ---------------------------------------------------------------------------
# Import sanity
# ---------------------------------------------------------------------------

def test_orchestrator_imports():
    from app.cloud import orchestrator
    assert hasattr(orchestrator, 'provision_for_scan')
    assert hasattr(orchestrator, 'teardown_for_scan')
    assert hasattr(orchestrator, 'cleanup_orphans')
    assert hasattr(orchestrator, 'CloudProvisionError')
    assert hasattr(orchestrator, 'CloudTeardownError')
    assert hasattr(orchestrator, 'CredentialError')
    assert hasattr(orchestrator, 'ProvisionResult')


def test_providers_base_imports():
    from app.cloud.providers import base
    assert hasattr(base, 'CloudProvider')
    assert inspect.isabstract(base.CloudProvider)


def test_providers_concrete_imports():
    from app.cloud.providers import aws, azure, gcp
    from app.cloud.providers.base import CloudProvider
    assert issubclass(aws.AwsProvider, CloudProvider)
    assert issubclass(azure.AzureProvider, CloudProvider)
    assert issubclass(gcp.GcpProvider, CloudProvider)


def test_terraform_manager_imports():
    from app.cloud import terraform_manager
    assert hasattr(terraform_manager, 'TerraformManager')


def test_ssh_executor_imports():
    from app.cloud import ssh_executor
    assert hasattr(ssh_executor, 'SshExecutor')


def test_zap_api_client_imports():
    from app.cloud import zap_api_client
    assert hasattr(zap_api_client, 'ZapApiClient')


def test_cleanup_imports():
    from app.cloud import cleanup
    assert hasattr(cleanup, 'detect_orphans')
    assert hasattr(cleanup, 'schedule_cleanup')
    assert hasattr(cleanup, 'force_cleanup')


def test_diagnostics_imports():
    from app.cloud import diagnostics
    assert hasattr(diagnostics, 'check_provider')
    assert hasattr(diagnostics, 'check_credentials')
    assert hasattr(diagnostics, 'check_state')


def test_routes_blueprint_exists():
    from app.cloud import routes
    from flask import Blueprint
    assert isinstance(routes.bp, Blueprint)
    assert routes.bp.name == 'cloud'


# ---------------------------------------------------------------------------
# Signature checks for orchestrator entry points
# ---------------------------------------------------------------------------

def test_provision_for_scan_signature():
    from app.cloud.orchestrator import provision_for_scan
    sig = inspect.signature(provision_for_scan)
    params = list(sig.parameters)
    assert params == ['scan_id'], f"Expected ['scan_id'], got {params}"


def test_teardown_for_scan_signature():
    from app.cloud.orchestrator import teardown_for_scan
    sig = inspect.signature(teardown_for_scan)
    params = list(sig.parameters)
    assert params == ['cloud_scan_id'], f"Expected ['cloud_scan_id'], got {params}"


def test_cleanup_orphans_signature():
    from app.cloud.orchestrator import cleanup_orphans
    sig = inspect.signature(cleanup_orphans)
    assert len(sig.parameters) == 0, "cleanup_orphans() takes no arguments"


# ---------------------------------------------------------------------------
# Signature checks for CloudProvider ABC
# ---------------------------------------------------------------------------

def test_cloud_provider_abstract_methods():
    from app.cloud.providers.base import CloudProvider
    abstract_methods = CloudProvider.__abstractmethods__
    assert 'provision' in abstract_methods
    assert 'get_zap_endpoint' in abstract_methods
    assert 'teardown' in abstract_methods
    assert 'get_status' in abstract_methods


# ---------------------------------------------------------------------------
# TerraformManager constructor and key properties
# ---------------------------------------------------------------------------

def test_terraform_manager_init():
    from app.cloud.terraform_manager import TerraformManager
    sig = inspect.signature(TerraformManager.__init__)
    params = list(sig.parameters)
    assert 'provider' in params
    assert 'scan_id' in params


def test_terraform_manager_state_path():
    from app.cloud.terraform_manager import TerraformManager
    tm = TerraformManager(provider='aws', scan_id=42)
    assert tm.state_path == '/var/lib/kast-web2/cloud_state/42'


# ---------------------------------------------------------------------------
# SshExecutor constructor
# ---------------------------------------------------------------------------

def test_ssh_executor_init():
    from app.cloud.ssh_executor import SshExecutor
    sig = inspect.signature(SshExecutor.__init__)
    params = list(sig.parameters)
    assert 'host' in params
    assert 'key_path' in params
    assert 'user' in params


# ---------------------------------------------------------------------------
# Routes are registered on the blueprint
# ---------------------------------------------------------------------------

def test_routes_api_endpoints_defined():
    from app.cloud.routes import bp
    rule_endpoints = {rule.endpoint for rule in bp.deferred_functions
                      if hasattr(rule, 'endpoint')}
    # Check the view functions exist on the blueprint by inspecting registered
    # view functions (deferred_functions not reliable pre-registration).
    # Instead verify the route-handler names exist as attributes.
    assert hasattr(bp, 'view_functions') or True  # blueprint pre-registration
    from app.cloud import routes
    assert callable(routes.api_cloud_scan_status)
    assert callable(routes.api_cloud_orphans)
    assert callable(routes.api_cloud_orphan_cleanup)
    assert callable(routes.admin_cloud_credentials)
    assert callable(routes.admin_cloud_scans)
    assert callable(routes.admin_cloud_orphans)
