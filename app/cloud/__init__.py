"""
app/cloud — kast-web cloud-deployment subsystem.

Provides Terraform/SSH/ZAP provisioning so kast-web can spin up ephemeral
cloud ZAP instances, run the kast CLI in remote mode against them, and tear
them down. Replaces the cloud-mode path that previously lived in kast CLI.

Public entry points (used by app/tasks.py):
    from app.cloud.orchestrator import provision_for_scan, teardown_for_scan
    from app.cloud.cleanup import detect_orphans

Routes blueprint (registered in app/__init__.py during D8):
    from app.cloud.routes import bp as cloud_bp
"""
