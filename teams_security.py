"""
Teams security module for JWT validation and token encryption.

This module provides security utilities for the Microsoft Teams integration:
- JWT Bearer token validation for Bot Framework requests
- Token encryption/decryption using Fernet (same pattern as Slack)
- State parameter handling for Azure AD OAuth
- Teams OIDC authentication support
"""
import hmac
import hashlib
import time
import logging
import os
import secrets
import json
import httpx
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify
from cryptography.fernet import Fernet
import base64
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# Microsoft identity platform endpoints
MS_AUTHORITY_URL = 'https://login.microsoftonline.com'
BOT_FRAMEWORK_OPENID_CONFIG = 'https://login.botframework.com/v1/.well-known/openidconfiguration'
MS_COMMON_OPENID_CONFIG = 'https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration'

# Teams OIDC Endpoints (using Microsoft identity platform)
TEAMS_OIDC_SCOPES = 'openid profile email User.Read'

# Cache for JWKS client
_jwks_client = None
_jwks_cache_time = None
_JWKS_CACHE_DURATION = 3600  # 1 hour

# Cache for credentials
_teams_bot_app_id = None
_teams_bot_app_secret = None
_teams_bot_tenant_id = None


def get_teams_bot_app_id():
    """Get Teams Bot Azure AD application (client) ID."""
    global _teams_bot_app_id
    if _teams_bot_app_id is None:
        _teams_bot_app_id = os.environ.get('TEAMS_BOT_APP_ID')
        if not _teams_bot_app_id:
            try:
                from keyvault_client import keyvault_client
                _teams_bot_app_id = keyvault_client.get_secret(
                    'teams-bot-app-id',
                    fallback_env_var='TEAMS_BOT_APP_ID'
                )
            except Exception as e:
                logger.error(f"Failed to get Teams Bot app ID: {e}")
    return _teams_bot_app_id


def get_teams_bot_app_secret():
    """Get Teams Bot Azure AD client secret."""
    global _teams_bot_app_secret
    if _teams_bot_app_secret is None:
        _teams_bot_app_secret = os.environ.get('TEAMS_BOT_APP_SECRET')
        if not _teams_bot_app_secret:
            try:
                from keyvault_client import keyvault_client
                _teams_bot_app_secret = keyvault_client.get_secret(
                    'teams-bot-app-secret',
                    fallback_env_var='TEAMS_BOT_APP_SECRET'
                )
            except Exception as e:
                logger.error(f"Failed to get Teams Bot app secret: {e}")
    return _teams_bot_app_secret


def get_teams_bot_tenant_id():
    """Get Teams Bot Azure AD tenant ID (for single-tenant bot)."""
    global _teams_bot_tenant_id
    if _teams_bot_tenant_id is None:
        _teams_bot_tenant_id = os.environ.get('TEAMS_BOT_TENANT_ID')
        if not _teams_bot_tenant_id:
            try:
                from keyvault_client import keyvault_client
                _teams_bot_tenant_id = keyvault_client.get_secret(
                    'teams-bot-tenant-id',
                    fallback_env_var='TEAMS_BOT_TENANT_ID'
                )
            except Exception as e:
                logger.error(f"Failed to get Teams Bot tenant ID: {e}")
    return _teams_bot_tenant_id


def _get_jwks_client():
    """Get or create JWKS client for Bot Framework token validation."""
    global _jwks_client, _jwks_cache_time

    now = time.time()
    if _jwks_client is None or (now - (_jwks_cache_time or 0)) > _JWKS_CACHE_DURATION:
        try:
            # Get JWKS URI from OpenID configuration
            with httpx.Client() as client:
                config_response = client.get(BOT_FRAMEWORK_OPENID_CONFIG)
                config = config_response.json()
                jwks_uri = config.get('jwks_uri')

            _jwks_client = PyJWKClient(jwks_uri)
            _jwks_cache_time = now
        except Exception as e:
            logger.error(f"Failed to initialize JWKS client: {e}")
            raise

    return _jwks_client


def validate_teams_jwt(auth_header: str) -> dict:
    """
    Validate incoming Bot Framework JWT Bearer token.

    The Bot Framework sends a JWT in the Authorization header that must be validated:
    - Signature verification using Bot Framework JWKS
    - Audience must match our bot's app ID
    - Token must not be expired
    - Issuer must be Bot Framework or Azure AD

    Args:
        auth_header: The Authorization header value (e.g., "Bearer eyJ...")

    Returns:
        Claims dict if valid, None if invalid
    """
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.warning("Missing or invalid Authorization header")
        return None

    token = auth_header[7:]  # Remove 'Bearer ' prefix
    app_id = get_teams_bot_app_id()

    if not app_id:
        logger.error("Teams Bot app ID not configured")
        return None

    try:
        # Get signing key from JWKS
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and validate the token
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256'],
            audience=app_id,
            options={
                'verify_exp': True,
                'verify_aud': True,
                'verify_iss': False,  # We'll check issuer manually
            }
        )

        # Validate issuer - should be from Bot Framework or Azure AD
        issuer = claims.get('iss', '')
        valid_issuers = [
            'https://api.botframework.com',
            'https://sts.windows.net/',
            'https://login.microsoftonline.com/',
        ]

        if not any(issuer.startswith(valid) for valid in valid_issuers):
            logger.warning(f"Invalid token issuer: {issuer}")
            return None

        return claims

    except jwt.ExpiredSignatureError:
        logger.warning("Teams JWT token expired")
        return None
    except jwt.InvalidAudienceError:
        logger.warning("Teams JWT token has invalid audience")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Teams JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to validate Teams JWT: {e}")
        return None


def verify_teams_request(f):
    """
    Decorator to verify Teams Bot Framework request JWT.

    This validates the Bearer token in the Authorization header
    and adds the claims to the request context.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        claims = validate_teams_jwt(auth_header)

        if not claims:
            return jsonify({'error': 'Unauthorized'}), 401

        # Store claims in request context for use in handler
        request.teams_claims = claims
        return f(*args, **kwargs)

    return decorated_function


# Token encryption - reuse same pattern as Slack for consistency
_encryption_key = None


def _get_encryption_key():
    """Get or generate encryption key for Teams tokens."""
    global _encryption_key
    if _encryption_key is None:
        # Use Flask SECRET_KEY as base for deriving encryption key
        secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
        # Derive a Fernet-compatible key from the secret
        # Use different salt than Slack to keep keys separate
        key_material = hashlib.sha256(f"teams-token-key:{secret_key}".encode()).digest()
        _encryption_key = base64.urlsafe_b64encode(key_material)
    return _encryption_key


def encrypt_token(token):
    """Encrypt a token for storage."""
    if not token:
        return None
    try:
        fernet = Fernet(_get_encryption_key())
        return fernet.encrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}")
        raise


def decrypt_token(encrypted_token):
    """Decrypt a stored token."""
    if not encrypted_token:
        return None
    try:
        fernet = Fernet(_get_encryption_key())
        return fernet.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt token: {e}")
        raise


# OAuth state parameter handling
def generate_teams_oauth_state(tenant_id, user_id=None, extra_data=None):
    """
    Generate an encrypted state parameter for Teams OAuth consent flow.

    The state contains:
    - tenant_id: Which Decision Records tenant is connecting Teams
    - user_id: Which user initiated the connection (if known)
    - csrf_token: Random token for CSRF protection
    - expires_at: Expiration timestamp (30 minutes)
    - extra_data: Any additional data to pass through OAuth
    """
    csrf_token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    state_data = {
        'type': 'teams_oauth',
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
        logger.error(f"Failed to generate Teams OAuth state: {e}")
        raise


def verify_teams_oauth_state(state):
    """
    Verify and decode a Teams OAuth state parameter.

    Returns the decoded state data if valid, None otherwise.
    """
    if not state:
        return None

    try:
        fernet = Fernet(_get_encryption_key())
        state_json = fernet.decrypt(state.encode()).decode()
        state_data = json.loads(state_json)

        # Verify this is a Teams OAuth state
        if state_data.get('type') != 'teams_oauth':
            logger.warning("Invalid state type for Teams OAuth")
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(state_data.get('expires_at', ''))
        if datetime.now(timezone.utc) > expires_at:
            logger.warning("Teams OAuth state expired")
            return None

        return state_data
    except Exception as e:
        logger.warning(f"Failed to verify Teams OAuth state: {e}")
        return None


# User linking token handling
def generate_teams_link_token(teams_workspace_id, aad_object_id, aad_email=None):
    """
    Generate an encrypted token for user account linking.

    This token is sent to Teams users who need to link their account
    via browser authentication.
    """
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    token_data = {
        'type': 'teams_link',
        'teams_workspace_id': teams_workspace_id,
        'aad_object_id': aad_object_id,
        'aad_email': aad_email,
        'expires_at': expires_at,
        'nonce': secrets.token_urlsafe(16)
    }

    try:
        fernet = Fernet(_get_encryption_key())
        token_json = json.dumps(token_data)
        return fernet.encrypt(token_json.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to generate Teams link token: {e}")
        raise


def verify_teams_link_token(token):
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

        # Verify this is a Teams link token
        if token_data.get('type') != 'teams_link':
            logger.warning("Invalid token type for Teams link")
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(token_data.get('expires_at', ''))
        if datetime.now(timezone.utc) > expires_at:
            logger.warning("Teams link token expired")
            return None

        return token_data
    except Exception as e:
        logger.warning(f"Failed to verify Teams link token: {e}")
        return None


# ==================== Teams OIDC Authentication ====================

def get_teams_oidc_authorize_url(tenant_id=None):
    """
    Get the Microsoft OIDC authorization URL.

    Args:
        tenant_id: Azure AD tenant ID (uses 'common' if not specified)

    Returns:
        Authorization endpoint URL
    """
    tenant = tenant_id or 'common'
    return f'{MS_AUTHORITY_URL}/{tenant}/oauth2/v2.0/authorize'


def get_teams_oidc_token_url(tenant_id=None):
    """
    Get the Microsoft OIDC token URL.

    Args:
        tenant_id: Azure AD tenant ID (uses 'common' if not specified)

    Returns:
        Token endpoint URL
    """
    tenant = tenant_id or 'common'
    return f'{MS_AUTHORITY_URL}/{tenant}/oauth2/v2.0/token'


def generate_teams_oidc_state(return_url=None, extra_data=None):
    """
    Generate an encrypted state parameter for Teams OIDC login flow.

    Unlike workspace OAuth, this doesn't need tenant_id since we derive
    the tenant from the user's email after authentication.

    Args:
        return_url: URL to redirect to after successful authentication
        extra_data: Any additional data to pass through the OAuth flow

    Returns:
        Encrypted state string
    """
    csrf_token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    state_data = {
        'type': 'teams_oidc',
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
        logger.error(f"Failed to generate Teams OIDC state: {e}")
        raise


def verify_teams_oidc_state(state):
    """
    Verify and decode a Teams OIDC state parameter.

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
        if state_data.get('type') != 'teams_oidc':
            logger.warning("Invalid state type for Teams OIDC")
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(state_data.get('expires_at', ''))
        if datetime.now(timezone.utc) > expires_at:
            logger.warning("Teams OIDC state expired")
            return None

        return state_data
    except Exception as e:
        logger.warning(f"Failed to verify Teams OIDC state: {e}")
        return None


def exchange_teams_oidc_code(code, redirect_uri):
    """
    Exchange an authorization code for tokens in Teams OIDC flow.

    Args:
        code: Authorization code from Microsoft
        redirect_uri: Redirect URI that was used in the authorization request

    Returns:
        Tuple of (id_token_claims, access_token) or (None, None) on failure
    """
    app_id = get_teams_bot_app_id()
    app_secret = get_teams_bot_app_secret()

    if not app_id or not app_secret:
        logger.error("Teams Bot credentials not configured for OIDC")
        return None, None

    try:
        with httpx.Client() as client:
            response = client.post(
                get_teams_oidc_token_url(),
                data={
                    'client_id': app_id,
                    'client_secret': app_secret,
                    'code': code,
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code',
                    'scope': TEAMS_OIDC_SCOPES,
                }
            )

            if response.status_code != 200:
                logger.error(f"Teams OIDC token exchange failed: {response.text}")
                return None, None

            token_data = response.json()

            # Decode ID token (without verification - already verified by Microsoft)
            id_token = token_data.get('id_token')
            if id_token:
                # Decode without verification since we trust Microsoft's endpoint
                id_claims = jwt.decode(id_token, options={'verify_signature': False})
            else:
                id_claims = None

            access_token = token_data.get('access_token')

            return id_claims, access_token

    except Exception as e:
        logger.error(f"Failed to exchange Teams OIDC code: {e}")
        return None, None


def get_teams_user_info(access_token):
    """
    Get user information from Microsoft Graph API.

    Args:
        access_token: Access token from OIDC flow

    Returns:
        User info dict or None on failure
    """
    try:
        with httpx.Client() as client:
            response = client.get(
                'https://graph.microsoft.com/v1.0/me',
                headers={'Authorization': f'Bearer {access_token}'}
            )

            if response.status_code != 200:
                logger.error(f"Failed to get Teams user info: {response.text}")
                return None

            return response.json()

    except Exception as e:
        logger.error(f"Failed to get Teams user info: {e}")
        return None
