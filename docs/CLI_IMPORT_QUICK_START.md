# CLI Import Feature - Quick Start Guide

## Quick Setup (3 Steps)

### 1. Run Database Migration

```bash
cd /opt/kast-web
python3 utils/migrate_import_feature.py
```

### 2. Access Import Feature

- Log in as admin user
- Navigate to **Admin Dashboard**
- Click **Import Scan** button

### 3. Import a Scan

1. Enter the full path to CLI scan results directory
2. Select user to assign scan to
3. Click **Import Scan**

## Example Usage

```bash
# 1. Run a KAST scan from CLI
kast -t example.com -o ~/kast_results

# 2. Find the results directory
ls ~/kast_results/
# Output: example.com-20250112-143000/

# 3. Import via web interface
# Navigate to: Admin Dashboard → Import Scan
# Enter path: /home/username/kast_results/example.com-20250112-143000
# Select user and click Import
```

## Requirements Checklist

- ✅ Admin user account
- ✅ CLI scan results with `*_processed.json` files
- ✅ Directory readable by web server
- ✅ Database migration completed

## What Gets Imported

| Data | Source |
|------|--------|
| Target | Directory name |
| Scan Mode | Plugin analysis (active/passive) |
| Plugins | `*_processed.json` filenames |
| Results | Existing JSON files |
| Reports | Existing HTML/JSON reports |
| Timestamps | File modification times |

## Key Features

- ✨ **Automatic Detection**: Target, mode, and plugins extracted automatically
- 🔒 **Admin Only**: Secure import restricted to administrators
- 📝 **Audit Logging**: All imports tracked in audit log
- ✅ **Validation**: Prevents duplicate imports and validates structure
- 🎯 **User Assignment**: Assign imported scans to any user
- 📊 **Full Integration**: View, share, and manage like any other scan

## Common Paths

- **Default CLI Results**: `~/kast_results/`
- **System Results**: `/var/lib/kast/results/`
- **Custom Output**: Whatever path you specified with `-o` flag

## Troubleshooting

**Can't find import button?**
- Ensure you're logged in as admin
- Check Admin Dashboard top button bar

**Import fails with "Directory not found"?**
- Use absolute paths (e.g., `/home/user/...` not `~/...`)
- Verify path is correct with `ls /path/to/directory`

**"No KAST result files found"?**
- Ensure directory contains `*_processed.json` files
- Check scan completed successfully from CLI

**"Directory is not readable"?**
- Run: `sudo chmod -R o+rX /path/to/results`
- Or copy results to web-accessible location

## Next Steps

After importing:
1. View imported scan in scan history
2. Check scan detail page for all results
3. Share with team members if needed
4. Generate reports using existing report functionality

## Documentation

- **Full Documentation**: See `docs/CLI_IMPORT_FEATURE.md`
- **Support**: Use `/reportbug` command in KAST-Web

---

**Quick Start Version**: 1.0  
**Last Updated**: December 11, 2025
