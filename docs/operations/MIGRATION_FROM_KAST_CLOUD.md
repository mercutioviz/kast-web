# Migrating from kast Cloud Mode to kast-web 2.0 Cloud

This guide is for users who ran ZAP scans in cloud mode via the kast CLI
(kast 2.x `--set zap.execution_mode=cloud`) and are upgrading to the
kast 3.0 + kast-web 2.0 coordinated release.

## What Changed and Why

In kast 2.x, the cloud runtime (Terraform, SSH bootstrapping, ZAP provisioning)
ran inside the kast CLI process. kast-web passed credentials as environment
variables and kast handled everything.

In kast 3.0 + kast-web 2.0, the cloud runtime moved to kast-web:

- **kast-web** provisions the cloud VM, waits for ZAP to start, and manages
  the Terraform state.
- **kast** connects to the already-running ZAP instance using remote mode
  (`--set zap.execution_mode=remote`) rather than cloud mode.
- Cloud mode (`--set zap.execution_mode=cloud`) is removed from kast 3.0.

The scan result files, report format, and kast-web UI are unchanged.


## Prerequisites

- kast-web 2.0 deployed and running (services `kast-web`, `kast-celery`,
  `kast-celery-beat` all active).
- kast 3.0 installed at `/usr/local/bin/kast` (replaces 2.x).
- The kast-web 2.0 database migration has been run:
  ```
  sudo -u www-data bash -c "cd /opt/kast-web2 && source .env && \
      venv/bin/python utils/migrate_cloud_v2.py"
  ```
- Terraform >= 1.5 installed on the kast-web server (same requirement as before).
- SSH key generation requires the `cryptography` Python package (added to
  `requirements.txt`; installed automatically by the deploy script).


## Migration Steps

### 1. Verify the database migration ran

The migration script created three new tables (`cloud_credentials`,
`cloud_scans`, `cloud_orphans`) and extracted any credential fields from
existing `ZapConfiguration.cloud_config` blobs into `CloudCredential` rows.

Check that credentials were migrated:

1. Open kast-web admin: `https://<your-server>/admin/cloud/credentials`
2. Confirm that a credential row exists for each cloud-mode ZapConfiguration
   you had previously. Each row shows the provider (aws/azure/gcp) and a
   created timestamp matching the original ZapConfiguration.

If credentials are missing, create them manually (see step 2 below).

### 2. Review and complete cloud credentials

Navigate to `/admin/cloud/credentials`. For each credential:

- Confirm the **provider** is correct (aws / azure / gcp).
- Confirm the credential name is meaningful. The migration script names rows
  after the ZapConfiguration they came from.
- Click **Edit** and paste the current JSON credentials to replace any that
  were migrated incorrectly.

Expected JSON shapes:

**AWS:**
```json
{
  "access_key_id": "AKIA...",
  "secret_access_key": "..."
}
```
Session tokens for IAM role assumption:
```json
{
  "access_key_id": "ASIA...",
  "secret_access_key": "...",
  "session_token": "..."
}
```

**Azure:**
```json
{
  "subscription_id": "...",
  "tenant_id": "...",
  "client_id": "...",
  "client_secret": "..."
}
```

**GCP:**
```json
{
  "project_id": "my-gcp-project",
  "service_account_json": "{\"type\": \"service_account\", ...}"
}
```
The `service_account_json` value is the full contents of the downloaded
service account key file as a JSON-encoded string.

### 3. Link ZapConfigurations to CloudCredentials

Each cloud-mode `ZapConfiguration` needs a `cloud_credential_id` pointing to
a `CloudCredential` row. The migration script sets this automatically when it
can. Confirm it worked:

1. Open `/admin/zap/configs` and click each cloud-mode configuration.
2. The **Cloud Credential** field should show the credential name, not empty.
3. If it is empty, select the correct credential from the dropdown and save.

### 4. Remove stale credential fields from ZapConfiguration cloud_config

The migration script strips credential keys (access keys, secrets, etc.) out
of the `cloud_config` blob and moves them to `CloudCredential`. Deployment
parameters (region, instance type, etc.) remain in `cloud_config` and are
still required.

Confirm your cloud configs retain:
- `region`
- `instance_type` (AWS) / `vm_size` (Azure) / `machine_type` (GCP)
- Any provider-specific options (zone, preemptible, spot pricing, etc.)

And no longer contain:
- `access_key`, `secret_key`, `access_key_id`, `secret_access_key` (AWS)
- `client_id`, `client_secret`, `tenant_id`, `subscription_id` (Azure)
- `service_account_key_path`, `project_id` (GCP — project_id moves to
  the CloudCredential JSON)

### 5. Test a scan

Submit a new scan with a cloud-mode ZapConfiguration. Watch the Celery worker
log to confirm the provisioning flow:

```
[orchestrator] provisioning scan <id> via aws
[GcpProvider] provisioning scan <id>   # or aws/azure
[bootstrap] waiting for SSH on <ip>
[bootstrap] ZAP ready at http://<ip>:8080
[orchestrator] scan <id> provisioned: cloud_scan_id=<n> zap_url=http://<ip>:8080
```

The kast CLI log will then show `execution_mode=remote` rather than `cloud`.

Monitor the cloud scan lifecycle at `/admin/cloud/scans`.


## What Happens to In-Flight Scans During Upgrade

If a scan was running in kast 2.x cloud mode during the upgrade window:

- kast 2.x finished (or failed) the scan before kast was replaced.
- The Terraform state for that scan lives under `~/.kast/terraform_state/`
  (the old path). kast-web 2.0 does not know about this state.
- **Action required**: manually run `terraform destroy` in the old state
  directory, or use the cloud provider console to terminate the instance.
  New scans use the new state path (`/var/lib/kast-web2/cloud_state/`).


## Rollback

If you need to roll back to kast 2.x + kast-web 1.5:

1. Stop kast-web 2.0 services.
2. Re-deploy kast-web 1.5 from the `main` branch.
3. Re-install kast 2.x: `pip install kast==2.14.*` in the kast venv.
4. The original `ZapConfiguration.cloud_config` blobs are preserved — the
   migration script does not destructively overwrite them.

Note: any `CloudCredential` rows created in 2.0 will not be readable by 1.5
(the table does not exist), but the data is not lost; the tables remain in the
SQLite file and will be visible again if you re-deploy 2.0.


## Troubleshooting

**"ZapConfiguration has no cloud_credential_id" error in Celery log**

The ZapConfiguration was not linked to a CloudCredential. Follow step 3 above.

**"CloudCredential X cannot be decrypted" error**

The `SECRET_KEY` used by kast-web 2.0 differs from 1.5. Both deployments must
use the same `SECRET_KEY` value in `.env` — the deploy script preserves this.
If you re-generated the key, re-enter the credentials at
`/admin/cloud/credentials/<id>/edit`.

**Terraform init fails with "provider not found"**

The Terraform configs are bundled in `app/cloud/terraform/{aws,azure,gcp}/`.
Confirm the kast-web process can reach the Terraform registry (or that
`terraform init` was previously run in the state directory and the
`.terraform/` directory was preserved from a prior run).

**Scan stuck in "provisioning" for more than 45 minutes**

The orphan cleanup task (runs every 15 minutes via Celery Beat) will detect it
and dispatch teardown. You can also trigger teardown immediately at
`/admin/cloud/orphans`. Check the Celery worker log for provisioning errors.

**SSH connection refused during bootstrap**

The security group / firewall rules on the provisioned instance must allow
inbound TCP 22 from the kast-web server's IP. AWS and Azure configs include a
`allowed_cidrs` variable in the Terraform templates; verify it is set
correctly in the ZapConfiguration cloud_config.

**"Terraform outputs missing 'public_ip'" error**

The Terraform apply succeeded but the instance did not receive a public IP.
This can happen if the AWS subnet has `map_public_ip_on_launch` disabled.
Verify the subnet and VPC routing table allow internet access.


## File Locations (kast-web 2.0)

| Item | Path |
|------|------|
| Terraform state | `/var/lib/kast-web2/cloud_state/<scan_id>/` |
| Ephemeral SSH private key | `<state_path>/zap_key.pem` |
| GCP service account key (temp) | `<state_path>/gcp_sa_key.json` |
| Terraform configs | `app/cloud/terraform/{aws,azure,gcp}/` |
| Celery Beat schedule | `celery_worker.py` (`beat_schedule`) |
| Admin UI | `/admin/cloud/{credentials,scans,orphans}` |
| Status API | `GET /api/cloud/scans/<scan_id>/status` |
