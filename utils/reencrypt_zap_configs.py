"""
Re-encryption utility for ZAP configurations.

If the SECRET_KEY was changed after ZAP configurations were created,
this script decrypts them using the old key and re-encrypts with the current key.

Usage:
    cd /opt/kast-web
    sudo -u www-data python3 utils/reencrypt_zap_configs.py [--old-key OLD_SECRET_KEY]

If --old-key is not provided, tries the insecure default key.
"""
import argparse
import base64
import hashlib
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.fernet import Fernet, InvalidToken


def make_fernet(secret_key_str):
    key = hashlib.sha256(secret_key_str.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def try_decrypt(fernet, ciphertext):
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        return None


def main():
    parser = argparse.ArgumentParser(description='Re-encrypt ZAP configs after SECRET_KEY rotation')
    parser.add_argument('--old-key', default='dev-secret-key-change-in-production',
                        help='Old SECRET_KEY value (default: insecure default)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be changed without writing')
    args = parser.parse_args()

    from app import create_app, db
    from app.models import ZapConfiguration
    from app.encryption import get_encryption_key

    app = create_app('production')

    with app.app_context():
        old_fernet = make_fernet(args.old_key)
        new_key = get_encryption_key()
        new_fernet = Fernet(new_key)

        configs = ZapConfiguration.query.all()
        updated = 0
        skipped = 0
        already_ok = 0

        for config in configs:
            fields = [
                ('local_config_encrypted', 'local'),
                ('remote_config_encrypted', 'remote'),
                ('cloud_config_encrypted', 'cloud'),
            ]
            config_changed = False

            for field_name, label in fields:
                ciphertext = getattr(config, field_name)
                if not ciphertext:
                    continue

                # First check if it already decrypts with the current key
                try:
                    new_fernet.decrypt(ciphertext.encode())
                    already_ok += 1
                    print(f'  Config {config.id} ({config.name}) {label}: already OK with current key')
                    continue
                except (InvalidToken, Exception):
                    pass

                # Try old key
                plaintext = try_decrypt(old_fernet, ciphertext)
                if plaintext is None:
                    print(f'  Config {config.id} ({config.name}) {label}: CANNOT DECRYPT with old key either — skipping', file=sys.stderr)
                    skipped += 1
                    continue

                # Validate it's valid JSON
                try:
                    json.loads(plaintext)
                except json.JSONDecodeError:
                    print(f'  Config {config.id} ({config.name}) {label}: decrypted but not valid JSON — skipping', file=sys.stderr)
                    skipped += 1
                    continue

                # Re-encrypt with new key
                new_ciphertext = new_fernet.encrypt(plaintext.encode()).decode()
                print(f'  Config {config.id} ({config.name}) {label}: decrypted OK, re-encrypting')

                if not args.dry_run:
                    setattr(config, field_name, new_ciphertext)
                    config_changed = True

            if config_changed:
                updated += 1

        if not args.dry_run and updated > 0:
            db.session.commit()
            print(f'\nCommitted. Updated {updated} config(s), skipped {skipped}, already OK {already_ok}.')
        else:
            print(f'\nDry run. Would update {updated} config(s), skip {skipped}, already OK {already_ok}.')
            if updated > 0:
                print('Run without --dry-run to apply changes.')


if __name__ == '__main__':
    main()
