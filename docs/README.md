# kast-web Documentation

This is the documentation root for kast-web. Use the sections below to find what you need.

---

## Getting Started

| Document | What it covers |
|---|---|
| [INSTALL.md](operations/INSTALL.md) | Automated installer script walkthrough |
| [PRODUCTION_DEPLOYMENT.md](operations/PRODUCTION_DEPLOYMENT.md) | Full manual deployment: systemd, Nginx, SSL, permissions |
| [UPGRADING.md](operations/UPGRADING.md) | Upgrading from kast 2.x + kast-web 1.x to the 3.0/2.0 release |
| [MIGRATION_FROM_KAST_CLOUD.md](operations/MIGRATION_FROM_KAST_CLOUD.md) | Moving from kast 2.x cloud mode to kast-web 2.0 cloud infrastructure |

---

## Operations

Day-to-day administration and maintenance.

| Document | What it covers |
|---|---|
| [UPDATE_GUIDE.md](operations/UPDATE_GUIDE.md) | Updating a live production installation (rolling, with rollback) |
| [USER_MIGRATION.md](operations/USER_MIGRATION.md) | Exporting and importing users between servers |
| [ZAP_CLOUD_TOOLS_SETUP.md](operations/ZAP_CLOUD_TOOLS_SETUP.md) | Installing Terraform and cloud CLI tools (AWS/Azure/GCP) on the host |
| [STATUS_DEBUGGING.md](operations/STATUS_DEBUGGING.md) | Diagnosing scans stuck in pending or running state |
| [INSTALL_ENV_PRESERVATION.md](operations/INSTALL_ENV_PRESERVATION.md) | How `.env` is preserved across installs and upgrades |

---

## Feature Reference

In-depth documentation for specific features.

| Document | What it covers |
|---|---|
| [AUTHENTICATION.md](features/AUTHENTICATION.md) | Authentication system: session management, login flow, configuration |
| [USER_ROLES.md](features/USER_ROLES.md) | Role definitions (admin, power\_user, user, viewer) and capabilities |
| [SCAN_SHARING.md](features/SCAN_SHARING.md) | Sharing scan results via signed links, expiry, and access control |
| [CONFIG_PROFILES.md](features/CONFIG_PROFILES.md) | Config profile schema, access control, and management |
| [ZAP_REMOTE_MODE.md](features/ZAP_REMOTE_MODE.md) | Verifying and troubleshooting remote ZAP execution mode |
| [LOGO_WHITELABELING.md](features/LOGO_WHITELABELING.md) | Logo upload, system default, and per-scan branding |
| [EMAIL_NOTIFICATIONS.md](features/EMAIL_NOTIFICATIONS.md) | Email report delivery: SMTP config, templates, async delivery |
| [ASYNC_SETUP.md](features/ASYNC_SETUP.md) | Celery + Redis setup, verification, and background task architecture |
| [DATABASE_EXPLORER.md](features/DATABASE_EXPLORER.md) | Flask-Admin database browser at `/admin/db` |
| [SYSTEM_INFO.md](features/SYSTEM_INFO.md) | System information panel: resources, versions, service status |
| [QUICK_STARTS.md](features/QUICK_STARTS.md) | Concise how-to guides for six common tasks (Celery, profiles, logo, email, logs, CLI import) |

---

## Development

References for contributors writing code or database migrations.

| Document | What it covers |
|---|---|
| [MIGRATION_SCRIPT_STANDARDS.md](development/MIGRATION_SCRIPT_STANDARDS.md) | Conventions for `utils/migrate_*.py` scripts: idempotency, backup, tracking |

Also see in the repository root:

- [CHANGELOG.md](../CHANGELOG.md) — version history
- [UPGRADING.md](operations/UPGRADING.md) — upgrade guide

---

## Archive

`docs/archive/` contains historical implementation logs, phase documents, and bug-fix records written during development. These files are accurate for the version they describe but are not maintained going forward. They remain for reference and git-history continuity.
