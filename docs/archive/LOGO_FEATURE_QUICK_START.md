# Logo White-Labeling - Quick Start Guide

## Setup (One-Time)

### Step 1: Run Migration
```bash
cd /opt/kast-web
python utils/migrate_logo_feature.py
```

This creates the database tables and uploads directory.

### Step 2: Update KAST CLI
**IMPORTANT**: Your KAST CLI must support the `--logo` parameter.

Add support for:
```bash
kast -t example.com --logo /path/to/logo.png
kast --report-only /output/dir --logo /path/to/logo.png
```

### Step 3: Restart KAST Web
```bash
sudo systemctl restart kast-web
# or
python run.py
```

## Usage

### Upload Your First Logo

1. Log in as admin
2. Navigate to **Admin > Manage Logos**
3. Click **Upload New Logo**
4. Fill in:
   - Name: "My Company Logo"
   - Description: "Primary company branding"
   - File: Upload your PNG/JPG (max 2MB)
5. Click **Upload Logo**

### Set System Default

1. Find your uploaded logo
2. Click **Set Default**
3. This logo will now be used for all scans

### Use Different Logo for Specific Scan

When the system default logo is set, all new scans will automatically use it. To use a different logo:

1. **Option A - Via Database** (until UI is built):
   ```python
   from app import create_app, db
   from app.models import Scan
   
   app = create_app()
   with app.app_context():
       scan = Scan.query.get(SCAN_ID)
       scan.logo_id = LOGO_ID  # or None for system default
       db.session.commit()
   ```

2. **Option B - Future Enhancement**: UI selection in scan creation/edit forms

## Verification

### Check Logo is Being Used

1. Run a scan
2. Check the logs:
   ```bash
   tail -f logs/kast-web.log | grep logo
   ```
   You should see: `Using logo: /path/to/logo.png`

3. Open the generated HTML report
4. Verify your logo appears in the report header

## Troubleshooting

**Logo not showing in report?**
- Ensure KAST CLI supports `--logo` parameter: `kast --help | grep logo`
- Check logo file exists: `ls -la app/static/uploads/logos/`
- Review logs for errors

**Can't upload logo?**
- Check file size < 2MB
- Use PNG, JPG, or JPEG format only
- Verify uploads directory is writable: `ls -ld app/static/uploads/logos/`

## Example Use Cases

### MSP with Multiple Clients

1. Upload client logos:
   - "Client A Logo"
   - "Client B Logo"
   - "MSP Logo" (set as default)

2. For Client A scan: Set `scan.logo_id` to Client A's logo ID
3. For Client B scan: Set `scan.logo_id` to Client B's logo ID
4. All other scans: Use MSP logo (default)

### Single Organization

1. Upload company logo
2. Set as system default
3. All reports automatically use your logo

## Next Steps

For detailed information, see the full documentation:
- `docs/LOGO_WHITELABELING_FEATURE.md`
