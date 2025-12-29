"""
Google OAuth 2.0 authentication module.

This module provides OAuth 2.0 authentication support for "Sign in with Google":
- State parameter generation and verification (CSRF protection)
- Google credential management (via Key Vault or environment)
- OAuth flow helpers

The flow:
1. User clicks "Sign in with Google"
2. Redirected to Google with state parameter
3. User authenticates with Google account
4. Google redirects back with authorization code
5. Backend exchanges code for tokens
6. User info fetched and user created/logged in
"""
import os
import secrets
import json
import logging
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
import hashlib
import base64

logger = logging.getLogger(__name__)

# Google OAuth 2.0 Endpoints
GOOGLE_OAUTH_AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_OAUTH_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'
GOOGLE_OAUTH_SCOPES = 'openid email profile'

# Cache for credentials
_google_client_id = None
_google_client_secret = None
_encryption_key = None


def _get_encryption_key():
    """Get or generate encryption key for OAuth state.

    Uses the same key derivation as slack_security.py for consistency.
    """
    global _encryption_key
    if _encryption_key is None:
        secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
        key_material = hashlib.sha256(f"slack-token-key:{secret_key}".encode()).digest()
        _encryption_key = base64.urlsafe_b64encode(key_material)
    return _encryption_key


def get_google_client_id():
    """Get Google OAuth client ID from environment or Key Vault."""
    global _google_client_id
    if _google_client_id is None:
        # Try environment variable first
        _google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
        if not _google_client_id:
            # Fall back to Key Vault
            try:
                from keyvault_client import keyvault_client
                _google_client_id = keyvault_client.get_secret(
                    'google-client-id',
                    fallback_env_var='GOOGLE_CLIENT_ID'
                )
            except Exception as e:
                logger.error(f"Failed to get Google client ID: {e}")
    return _google_client_id


def get_google_client_secret():
    """Get Google OAuth client secret from environment or Key Vault."""
    global _google_client_secret
    if _google_client_secret is None:
        # Try environment variable first
        _google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        if not _google_client_secret:
            # Fall back to Key Vault
            try:
                from keyvault_client import keyvault_client
                _google_client_secret = keyvault_client.get_secret(
                    'google-client-secret',
                    fallback_env_var='GOOGLE_CLIENT_SECRET'
                )
            except Exception as e:
                logger.error(f"Failed to get Google client secret: {e}")
    return _google_client_secret


def is_google_oauth_configured():
    """Check if Google OAuth credentials are configured."""
    client_id = get_google_client_id()
    client_secret = get_google_client_secret()
    return bool(client_id and client_secret)


def generate_google_oauth_state(return_url=None, extra_data=None):
    """
    Generate an encrypted state parameter for Google OAuth flow.

    State is used for CSRF protection and passing data through the OAuth flow.

    Args:
        return_url: URL to redirect to after successful authentication
        extra_data: Any additional data to pass through the OAuth flow

    Returns:
        Encrypted state string
    """
    csrf_token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    state_data = {
        'type': 'google_oauth',
        'csrf_token': csrf_token,
        'expires_at': expires_at,
        'return_url': return_url,
        'extra_data': extra_data or {}
    }

    try:
        fernet = Fernet(_get_encryption_key())
        state_json = json.dumps(state_data)
        return fernet.encrypt(state_json.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to generate Google OAuth state: {e}")
        raise


def verify_google_oauth_state(state):
    """
    Verify and decode a Google OAuth state parameter.

    Args:
        state: Encrypted state string from OAuth callback

    Returns:
        Decoded state data dict if valid, None otherwise
    """
    if not state:
        return None

    try:
        fernet = Fernet(_get_encryption_key())
        state_json = fernet.decrypt(state.encode()).decode()
        state_data = json.loads(state_json)

        # Verify this is a Google OAuth state
        if state_data.get('type') != 'google_oauth':
            logger.warning("Invalid state type for Google OAuth")
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(state_data.get('expires_at', ''))
        if datetime.now(timezone.utc) > expires_at:
            logger.warning("Google OAuth state expired")
            return None

        return state_data
    except Exception as e:
        logger.warning(f"Failed to verify Google OAuth state: {e}")
        return None


def clear_credential_cache():
    """Clear cached credentials. Useful for testing."""
    global _google_client_id, _google_client_secret, _encryption_key
    _google_client_id = None
    _google_client_secret = None
    _encryption_key = None
