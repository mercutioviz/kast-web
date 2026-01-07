"""
Encryption utilities for sensitive data storage
Uses Fernet symmetric encryption with key derived from SECRET_KEY
"""
from cryptography.fernet import Fernet
from flask import current_app
import base64
import hashlib
import json


def get_encryption_key():
    """
    Derive encryption key from Flask SECRET_KEY
    Uses SHA256 to ensure consistent 32-byte key
    """
    secret = current_app.config['SECRET_KEY'].encode()
    key = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_value(value):
    """
    Encrypt a string value
    
    Args:
        value: String to encrypt
        
    Returns:
        Encrypted string or None if value is empty
    """
    if not value:
        return None
    f = Fernet(get_encryption_key())
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value):
    """
    Decrypt a string value
    
    Args:
        encrypted_value: Encrypted string
        
    Returns:
        Decrypted string or None if encrypted_value is empty
    """
    if not encrypted_value:
        return None
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_value.encode()).decode()


def encrypt_json(data):
    """
    Encrypt a dictionary as JSON
    
    Args:
        data: Dictionary to encrypt
        
    Returns:
        Encrypted JSON string or None if data is empty
    """
    if not data:
        return None
    json_str = json.dumps(data)
    return encrypt_value(json_str)


def decrypt_json(encrypted_json):
    """
    Decrypt JSON back to dictionary
    
    Args:
        encrypted_json: Encrypted JSON string
        
    Returns:
        Decrypted dictionary or empty dict if encrypted_json is empty
    """
    if not encrypted_json:
        return {}
    json_str = decrypt_value(encrypted_json)
    return json.loads(json_str)
