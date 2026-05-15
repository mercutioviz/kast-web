# Security Tool Configuration Fix for www-data User

## Problem Summary

When running KAST scans through kast-web, certain plugins (katana, subfinder) failed to create their output files, while the same plugins worked correctly when run from the CLI.

### Root Cause

Security tools like **katana** and **subfinder** look for configuration files in the user's home directory at `~/.config/<tool>/config.yaml`. When run as different users:

- **CLI execution**: Tools run as the logged-in user (e.g., `kali`) and find config files in `/home/kali/.config/`
- **kast-web execution**: Tools run as `www-data` user and look for config files in `/var/www/.config/`

Since `/var/www/.config/` didn't exist, these tools failed with errors like:
```
[FTL] Could not read flags: cause="no such file or directory" chain="could not parse flags"
```

This prevented the tools from executing properly and creating their output files.

## Solution

Create configuration directories for the `www-data` user and populate them with appropriate config files.

### Manual Fix (Immediate)

Run these commands to set up the configuration directories:

```bash
# Create config directory structure for www-data
sudo mkdir -p /var/www/.config/katana
sudo mkdir -p /var/www/.config/subfinder

# Option 1: Copy existing configs from your user (if they exist)
if [ -f ~/.config/katana/config.yaml ]; then
    sudo cp ~/.config/katana/config.yaml /var/www/.config/katana/
fi

if [ -f ~/.config/subfinder/config.yaml ]; then
    sudo cp ~/.config/subfinder/config.yaml /var/www/.config/subfinder/
fi

# Option 2: Create minimal/empty config files
# (Tools will use defaults if configs are empty)
sudo touch /var/www/.config/katana/config.yaml
sudo touch /var/www/.config/subfinder/config.yaml

# Set proper ownership
sudo chown -R www-data:www-data /var/www/.config

# Set proper permissions
sudo chmod -R 755 /var/www/.config
sudo chmod 644 /var/www/.config/katana/config.yaml
sudo chmod 644 /var/www/.config/subfinder/config.yaml

# Test that katana now works as www-data
sudo -u www-data katana -version
```

### Automated Fix (Install Script)

The `install.sh` script has been updated with a new function `configure_security_tool_configs()` that automatically:

1. Creates `/var/www/.config/katana/` and `/var/www/.config/subfinder/` directories
2. Copies existing config files from the installing user's home directory (if they exist)
3. Creates empty config files if no existing configs are found
4. Sets proper ownership (`www-data:www-data`)
5. Sets proper permissions (directories: 755, files: 644)
6. Tests katana execution as www-data

This function runs automatically during installation, ensuring new installations have the proper configuration structure.

## Verification

After applying the fix:

1. **Test katana as www-data:**
   ```bash
   sudo -u www-data katana -silent -u example.com -ob -rl 15 -fs fqdn -o /tmp/test-katana.txt
   ls -la /tmp/test-katana.txt  # File should exist
   ```

2. **Test subfinder as www-data:**
   ```bash
   sudo -u www-data subfinder --version  # Should not show config error
   ```

3. **Restart Celery worker:**
   ```bash
   sudo systemctl restart kast-celery
   ```

4. **Run scan through kast-web:**
   - Submit a scan that includes the katana plugin
   - Check scan results directory for `katana.txt` file
   - Verify the file contains the expected output

## Files Modified

- `install.sh`: Added `configure_security_tool_configs()` function and integrated into installation flow

## Additional Notes

### Other ProjectDiscovery Tools

The same approach applies to other tools from ProjectDiscovery that may require config files:

- **nuclei**: `~/.config/nuclei/config.yaml`
- **httpx**: `~/.config/httpx/config.yaml`
- **naabu**: `~/.config/naabu/config.yaml`

If you use these tools in KAST plugins, create their config directories:

```bash
sudo mkdir -p /var/www/.config/{nuclei,httpx,naabu}
sudo touch /var/www/.config/nuclei/config.yaml
sudo touch /var/www/.config/httpx/config.yaml
sudo touch /var/www/.config/naabu/config.yaml
sudo chown -R www-data:www-data /var/www/.config
sudo chmod -R 755 /var/www/.config
```

### API Keys and Credentials

If your configuration files contain API keys or credentials:

1. **Use separate configs for www-data** to avoid exposing your personal credentials
2. **Set restrictive permissions** (600 or 644) on config files
3. **Store sensitive data in environment variables** when possible

### Upgrading Existing Installations

For existing installations that don't have these config directories:

1. Run the manual fix commands above
2. Restart the Celery worker: `sudo systemctl restart kast-celery`
3. Future installations using the updated install.sh will handle this automatically

## Related Issues

This fix resolves issues where:
- katana.txt file was not created in scan output directories
- subfinder failed with "no such file or directory" errors
- Any ProjectDiscovery tool failed when run through kast-web but worked from CLI

## Credits

Issue identified and fixed on 2025-12-11.
