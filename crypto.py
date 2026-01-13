"""
Cryptographic utilities for secure credential storage.

This module provides encryption/decryption for sensitive data like SMTP passwords.
The encryption key is stored in Azure Key Vault and retrieved at runtime.

Security Design:
- Uses Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256)
- Encryption key stored in Azure Key Vault
- Encrypted values prefixed with 'encrypted:' for identification
- Passwords can only be used (decrypted for sending), never retrieved via API
"""
import logging
import base64
import os
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Prefix to identify encrypted values in the database
ENCRYPTED_PREFIX = 'encrypted:'

# Key Vault secret name for the encryption key
ENCRYPTION_KEY_SECRET_NAME = 'smtp-encryption-key'


def _get_encryption_key():
    """
    Get the encryption key from Key Vault or environment.

    Returns:
        bytes: The Fernet encryption key, or None if unavailable
    """
    from ee.backend.azure.keyvault_client import keyvault_client

    # Try Key Vault first
    key = keyvault_client.get_secret(
        ENCRYPTION_KEY_SECRET_NAME,
        fallback_env_var='SMTP_ENCRYPTION_KEY'
    )

    if key:
        # Ensure it's properly encoded as bytes
        if isinstance(key, str):
            key = key.encode('utf-8')
        return key

    logger.warning("SMTP encryption key not found - encrypted credentials cannot be used")
    return None


def generate_encryption_key():
    """
    Generate a new Fernet encryption key.

    Use this to create a key to store in Azure Key Vault:
        python -c "from crypto import generate_encryption_key; print(generate_encryption_key())"

    Then store in Key Vault:
        az keyvault secret set --vault-name adr-keyvault-eu --name smtp-encryption-key --value "KEY_HERE"

    Returns:
        str: A new Fernet key (URL-safe base64 encoded)
    """
    return Fernet.generate_key().decode('utf-8')


def encrypt_password(plaintext_password):
    """
    Encrypt a password for secure storage.

    Args:
        plaintext_password: The password to encrypt

    Returns:
        str: Encrypted password prefixed with 'encrypted:', or the original
             password if encryption is unavailable (with warning logged)
    """
    if not plaintext_password:
        return plaintext_password

    # Don't re-encrypt already encrypted passwords
    if plaintext_password.startswith(ENCRYPTED_PREFIX):
        return plaintext_password

    # Special case: 'from-keyvault' placeholder for system config
    if plaintext_password == 'from-keyvault':
        return plaintext_password

    key = _get_encryption_key()
    if not key:
        logger.warning("Encryption key unavailable - storing password without encryption")
        return plaintext_password

    try:
        f = Fernet(key)
        encrypted = f.encrypt(plaintext_password.encode('utf-8'))
        return ENCRYPTED_PREFIX + encrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encrypt password: {e}")
        # Return original to avoid data loss, but log the issue
        return plaintext_password


def decrypt_password(encrypted_password):
    """
    Decrypt a password for use (e.g., SMTP authentication).

    Args:
        encrypted_password: The encrypted password from the database

    Returns:
        str: The decrypted password, or the original value if not encrypted
             or decryption fails
    """
    if not encrypted_password:
        return encrypted_password

    # Special case: 'from-keyvault' placeholder for system config
    if encrypted_password == 'from-keyvault':
        return encrypted_password

    # Only attempt decryption if it's actually encrypted
    if not encrypted_password.startswith(ENCRYPTED_PREFIX):
        return encrypted_password

    key = _get_encryption_key()
    if not key:
        logger.error("Encryption key unavailable - cannot decrypt password")
        return None

    try:
        f = Fernet(key)
        encrypted_data = encrypted_password[len(ENCRYPTED_PREFIX):].encode('utf-8')
        decrypted = f.decrypt(encrypted_data)
        return decrypted.decode('utf-8')
    except InvalidToken:
        logger.error("Invalid encryption token - password may be corrupted or key rotated")
        return None
    except Exception as e:
        logger.error(f"Failed to decrypt password: {e}")
        return None


def is_password_encrypted(password):
    """
    Check if a password value is encrypted.

    Args:
        password: The password value to check

    Returns:
        bool: True if the password is encrypted
    """
    if not password:
        return False
    return password.startswith(ENCRYPTED_PREFIX)


def mask_password(password):
    """
    Return a masked version of the password for display.

    Args:
        password: The password (encrypted or plain)

    Returns:
        str: '***PROTECTED***' if password exists, empty string otherwise
    """
    if password and password != 'from-keyvault':
        return '***PROTECTED***'
    return ''
