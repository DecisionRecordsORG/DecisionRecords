"""
Slack security module for request verification and token encryption.

This module provides security utilities for the Slack integration:
- Request signature verification (HMAC-SHA256)
- Token encryption/decryption using Fernet
- State parameter handling for OAuth
- Slack OIDC authentication support
"""
import hmac
import hashlib
import time
import logging
import os
import secrets
import json
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)

# Slack OIDC Endpoints
SLACK_OIDC_AUTHORIZE_URL = 'https://slack.com/openid/connect/authorize'
SLACK_OIDC_TOKEN_URL = 'https://slack.com/api/openid.connect.token'
SLACK_OIDC_USERINFO_URL = 'https://slack.com/api/openid.connect.userInfo'
SLACK_OIDC_SCOPES = 'openid profile email'

# Cache for signing secret
_slack_signing_secret = None


def get_slack_signing_secret():
    """Get Slack signing secret from environment or Key Vault."""
    global _slack_signing_secret
    if _slack_signing_secret is None:
        # Try environment variable first (from .env)
        _slack_signing_secret = os.environ.get('SIGNING_SECRET')
        if not _slack_signing_secret:
            # Fall back to Key Vault
            try:
                from keyvault_client import keyvault_client
                _slack_signing_secret = keyvault_client.get_secret(
                    'slack-signing-secret',
                    fallback_env_var='SIGNING_SECRET'
                )
            except Exception as e:
                logger.error(f"Failed to get Slack signing secret: {e}")
    return _slack_signing_secret


def get_slack_client_id():
    """Get Slack app client ID."""
    client_id = os.environ.get('CLIENT_ID')
    if not client_id:
        try:
            from keyvault_client import keyvault_client
            client_id = keyvault_client.get_secret(
                'slack-client-id',
                fallback_env_var='CLIENT_ID'
            )
        except Exception as e:
            logger.error(f"Failed to get Slack client ID: {e}")
    return client_id


def get_slack_client_secret():
    """Get Slack app client secret."""
    client_secret = os.environ.get('CLIENT_SECRET')
    if not client_secret:
        try:
            from keyvault_client import keyvault_client
            client_secret = keyvault_client.get_secret(
                'slack-client-secret',
                fallback_env_var='CLIENT_SECRET'
            )
        except Exception as e:
            logger.error(f"Failed to get Slack client secret: {e}")
    return client_secret


def verify_slack_signature(f):
    """
    Decorator to verify Slack request signatures.

    Uses HMAC-SHA256 as per Slack's verification spec:
    https://api.slack.com/authentication/verifying-requests-from-slack

    The signature is computed over: v0:{timestamp}:{request_body}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        signing_secret = get_slack_signing_secret()
        if not signing_secret:
            logger.error("Slack signing secret not configured")
            return jsonify({'error': 'Slack integration not configured'}), 500

        timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
        signature = request.headers.get('X-Slack-Signature', '')

        if not timestamp or not signature:
            logger.warning("Missing Slack signature headers")
            return jsonify({'error': 'Invalid request'}), 403

        # Check timestamp to prevent replay attacks (allow 5 min window)
        try:
            request_time = int(timestamp)
            if abs(time.time() - request_time) > 300:
                logger.warning("Slack request timestamp too old or too far in future")
                return jsonify({'error': 'Invalid request timestamp'}), 403
        except ValueError:
            logger.warning("Invalid timestamp format in Slack request")
            return jsonify({'error': 'Invalid timestamp'}), 403

        # Build the signature base string
        request_body = request.get_data(as_text=True)
        sig_basestring = f"v0:{timestamp}:{request_body}"

        # Calculate expected signature
        expected_sig = 'v0=' + hmac.new(
            signing_secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_sig, signature):
            logger.warning("Invalid Slack signature")
            return jsonify({'error': 'Invalid signature'}), 403

        return f(*args, **kwargs)
    return decorated_function


# Token encryption for storing Slack bot tokens
_encryption_key = None


def _get_encryption_key():
    """Get or generate encryption key for Slack tokens."""
    global _encryption_key
    if _encryption_key is None:
        # Use Flask SECRET_KEY as base for deriving encryption key
        secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
        # Derive a Fernet-compatible key from the secret
        key_material = hashlib.sha256(f"slack-token-key:{secret_key}".encode()).digest()
        _encryption_key = base64.urlsafe_b64encode(key_material)
    return _encryption_key


def encrypt_token(token):
    """Encrypt a Slack bot token for storage."""
    if not token:
        return None
    try:
        fernet = Fernet(_get_encryption_key())
        return fernet.encrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}")
        raise


def decrypt_token(encrypted_token):
    """Decrypt a stored Slack bot token."""
    if not encrypted_token:
        return None
    try:
        fernet = Fernet(_get_encryption_key())
        return fernet.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt token: {e}")
        raise


# OAuth state parameter handling
def generate_oauth_state(tenant_id, user_id=None, extra_data=None):
    """
    Generate an encrypted state parameter for OAuth flow.

    The state contains:
    - tenant_id: Which tenant is installing
    - user_id: Which user initiated the install (if known)
    - csrf_token: Random token for CSRF protection
    - expires_at: Expiration timestamp (30 minutes)
    - extra_data: Any additional data to pass through OAuth
    """
    csrf_token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(minutes=30)).isoformat()

    state_data = {
        'tenant_id': tenant_id,
        'user_id': user_id,
        'csrf_token': csrf_token,
        'expires_at': expires_at,
        'extra_data': extra_data or {}
    }

    try:
        fernet = Fernet(_get_encryption_key())
        state_json = json.dumps(state_data)
        return fernet.encrypt(state_json.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to generate OAuth state: {e}")
        raise


def verify_oauth_state(state):
    """
    Verify and decode an OAuth state parameter.

    Returns the decoded state data if valid, None otherwise.
    """
    if not state:
        return None

    try:
        fernet = Fernet(_get_encryption_key())
        state_json = fernet.decrypt(state.encode()).decode()
        state_data = json.loads(state_json)

        # Check expiration
        expires_at = datetime.fromisoformat(state_data.get('expires_at', ''))
        if datetime.utcnow() > expires_at:
            logger.warning("OAuth state expired")
            return None

        return state_data
    except Exception as e:
        logger.warning(f"Failed to verify OAuth state: {e}")
        return None


# User linking token handling
def generate_link_token(slack_workspace_id, slack_user_id, slack_email=None):
    """
    Generate an encrypted token for user account linking.

    This token is sent to Slack users who need to link their account
    via browser authentication.
    """
    expires_at = (datetime.utcnow() + timedelta(minutes=30)).isoformat()

    token_data = {
        'slack_workspace_id': slack_workspace_id,
        'slack_user_id': slack_user_id,
        'slack_email': slack_email,
        'expires_at': expires_at,
        'nonce': secrets.token_urlsafe(16)
    }

    try:
        fernet = Fernet(_get_encryption_key())
        token_json = json.dumps(token_data)
        return fernet.encrypt(token_json.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to generate link token: {e}")
        raise


def verify_link_token(token):
    """
    Verify and decode a user linking token.

    Returns the decoded token data if valid, None otherwise.
    """
    if not token:
        return None

    try:
        fernet = Fernet(_get_encryption_key())
        token_json = fernet.decrypt(token.encode()).decode()
        token_data = json.loads(token_json)

        # Check expiration
        expires_at = datetime.fromisoformat(token_data.get('expires_at', ''))
        if datetime.utcnow() > expires_at:
            logger.warning("Link token expired")
            return None

        return token_data
    except Exception as e:
        logger.warning(f"Failed to verify link token: {e}")
        return None


# ==================== Slack OIDC Authentication ====================

def generate_slack_oidc_state(return_url=None, extra_data=None):
    """
    Generate an encrypted state parameter for Slack OIDC login flow.

    Unlike workspace OAuth, this doesn't need tenant_id since we derive
    the tenant from the user's email after authentication.

    Args:
        return_url: URL to redirect to after successful authentication
        extra_data: Any additional data to pass through the OAuth flow

    Returns:
        Encrypted state string
    """
    csrf_token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()

    state_data = {
        'type': 'slack_oidc',
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
        logger.error(f"Failed to generate Slack OIDC state: {e}")
        raise


def verify_slack_oidc_state(state):
    """
    Verify and decode a Slack OIDC state parameter.

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

        # Verify this is an OIDC state (not workspace OAuth state)
        if state_data.get('type') != 'slack_oidc':
            logger.warning("Invalid state type for Slack OIDC")
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(state_data.get('expires_at', ''))
        if datetime.utcnow() > expires_at:
            logger.warning("Slack OIDC state expired")
            return None

        return state_data
    except Exception as e:
        logger.warning(f"Failed to verify Slack OIDC state: {e}")
        return None
