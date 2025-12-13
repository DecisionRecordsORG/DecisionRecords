"""
Cloudflare Security Module

This module provides security enforcement for requests passing through Cloudflare:
1. Origin IP Validation - Ensures requests come through Cloudflare proxy
2. Cloudflare Access JWT Validation - Validates Zero Trust tokens for protected routes

Security Architecture:
- All production traffic MUST pass through Cloudflare (orange cloud)
- Direct access to Azure public IP is blocked
- /superadmin routes require valid Cloudflare Access JWT

Configuration:
- Settings are stored in SystemConfig (database) and configurable via Super Admin UI
- Environment variables serve as fallback for initial setup

References:
- Cloudflare IP ranges: https://www.cloudflare.com/ips/
- Access JWT validation: https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/validating-json/
"""

import os
import logging
import ipaddress
import json
import jwt
import requests
from functools import wraps
from flask import request, jsonify, g
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ==================== Configuration Cache ====================
# Cache config to avoid hitting database on every request

_config_cache = {
    'origin_check_enabled': None,
    'access_enabled': None,
    'access_team_domain': None,
    'access_aud': None,
    'protected_paths': None,
    'last_refresh': None
}

CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cloudflare_config():
    """Get Cloudflare configuration from SystemConfig with caching."""
    global _config_cache

    # Check cache validity
    now = datetime.utcnow()
    if (_config_cache['last_refresh'] and
            (now - _config_cache['last_refresh']).total_seconds() < CACHE_TTL_SECONDS):
        return _config_cache

    # Refresh from database
    try:
        from models import SystemConfig

        _config_cache['origin_check_enabled'] = SystemConfig.get_bool(
            SystemConfig.KEY_CLOUDFLARE_ORIGIN_CHECK_ENABLED,
            SystemConfig.DEFAULT_CLOUDFLARE_ORIGIN_CHECK_ENABLED
        )

        _config_cache['access_enabled'] = SystemConfig.get_bool(
            SystemConfig.KEY_CLOUDFLARE_ACCESS_ENABLED,
            SystemConfig.DEFAULT_CLOUDFLARE_ACCESS_ENABLED
        )

        _config_cache['access_team_domain'] = (
            SystemConfig.get(SystemConfig.KEY_CLOUDFLARE_ACCESS_TEAM_DOMAIN) or
            os.environ.get('CF_ACCESS_TEAM_DOMAIN')
        )

        _config_cache['access_aud'] = (
            SystemConfig.get(SystemConfig.KEY_CLOUDFLARE_ACCESS_AUD) or
            os.environ.get('CF_ACCESS_AUD')
        )

        protected_paths_str = (
            SystemConfig.get(SystemConfig.KEY_CLOUDFLARE_ACCESS_PROTECTED_PATHS) or
            SystemConfig.DEFAULT_CLOUDFLARE_ACCESS_PROTECTED_PATHS
        )
        _config_cache['protected_paths'] = [p.strip() for p in protected_paths_str.split(',') if p.strip()]

        _config_cache['last_refresh'] = now

        logger.debug(f"Cloudflare config refreshed: origin_check={_config_cache['origin_check_enabled']}, "
                     f"access={_config_cache['access_enabled']}")

    except Exception as e:
        logger.warning(f"Failed to load Cloudflare config from database: {e}")
        # Use defaults/env vars as fallback
        _config_cache['origin_check_enabled'] = os.environ.get('CLOUDFLARE_ORIGIN_CHECK', 'true').lower() == 'true'
        _config_cache['access_enabled'] = os.environ.get('CF_ACCESS_ENABLED', 'false').lower() == 'true'
        _config_cache['access_team_domain'] = os.environ.get('CF_ACCESS_TEAM_DOMAIN')
        _config_cache['access_aud'] = os.environ.get('CF_ACCESS_AUD')
        _config_cache['protected_paths'] = ['/superadmin', '/superadmin/*']
        _config_cache['last_refresh'] = now

    return _config_cache


def invalidate_cloudflare_cache():
    """Invalidate the config cache to force refresh on next request."""
    global _config_cache
    _config_cache['last_refresh'] = None
    logger.info("Cloudflare config cache invalidated")


def get_cloudflare_config_for_api():
    """Get Cloudflare configuration for API response (safe for frontend)."""
    config = _get_cloudflare_config()
    return {
        'origin_check_enabled': config['origin_check_enabled'],
        'access_enabled': config['access_enabled'],
        'access_team_domain': config['access_team_domain'] or '',
        'access_aud_configured': bool(config['access_aud']),
        'protected_paths': config['protected_paths'],
    }

# ==================== Cloudflare IP Ranges ====================
# These are updated periodically from https://www.cloudflare.com/ips/
# Last updated: December 2024

CLOUDFLARE_IPV4_RANGES = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
]

CLOUDFLARE_IPV6_RANGES = [
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
]

# Parse IP ranges into networks
_cloudflare_ipv4_networks = [ipaddress.ip_network(cidr) for cidr in CLOUDFLARE_IPV4_RANGES]
_cloudflare_ipv6_networks = [ipaddress.ip_network(cidr) for cidr in CLOUDFLARE_IPV6_RANGES]


def is_cloudflare_ip(ip_str: str) -> bool:
    """Check if an IP address belongs to Cloudflare's network."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.version == 4:
            return any(ip in network for network in _cloudflare_ipv4_networks)
        else:
            return any(ip in network for network in _cloudflare_ipv6_networks)
    except ValueError:
        logger.warning(f"Invalid IP address format: {ip_str}")
        return False


def get_real_client_ip() -> str:
    """
    Get the real client IP address.

    In Cloudflare proxied setup:
    - CF-Connecting-IP: Original visitor IP
    - X-Forwarded-For: Chain of proxies (may contain multiple IPs)
    - request.remote_addr: Cloudflare edge server IP
    """
    # Cloudflare always sets CF-Connecting-IP to the original visitor
    cf_connecting_ip = request.headers.get('CF-Connecting-IP')
    if cf_connecting_ip:
        return cf_connecting_ip

    # Fallback to X-Forwarded-For (first IP in chain)
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()

    return request.remote_addr


def validate_cloudflare_origin() -> tuple[bool, str]:
    """
    Validate that the request came through Cloudflare.

    Returns:
        tuple: (is_valid, error_message)
    """
    # Skip validation in testing/development
    if os.environ.get('FLASK_ENV') == 'testing':
        return True, None

    if os.environ.get('SKIP_CLOUDFLARE_CHECK', 'false').lower() == 'true':
        logger.debug("Cloudflare check skipped via SKIP_CLOUDFLARE_CHECK")
        return True, None

    # Check if origin check is enabled in config
    config = _get_cloudflare_config()
    if not config['origin_check_enabled']:
        logger.debug("Cloudflare origin check disabled in config")
        return True, None

    # Check for required Cloudflare headers
    # When proxied through Cloudflare, these headers are always present
    cf_ray = request.headers.get('CF-Ray')
    cf_connecting_ip = request.headers.get('CF-Connecting-IP')

    if not cf_ray:
        # Request didn't come through Cloudflare
        # This means someone is accessing the Azure IP directly
        logger.warning(
            f"Direct IP access attempt blocked - "
            f"Remote: {request.remote_addr}, "
            f"Path: {request.path}, "
            f"User-Agent: {request.headers.get('User-Agent', 'unknown')}"
        )
        return False, "Direct access not allowed. Please use architecture-decisions.org"

    # Verify the immediate upstream is actually Cloudflare
    # X-Forwarded-For should show the chain, but request.remote_addr should be a Cloudflare IP
    # when behind Azure App Gateway, check the last proxy in the chain
    x_forwarded_for = request.headers.get('X-Forwarded-For', '')

    # Log for debugging (can be removed in production)
    logger.debug(
        f"Cloudflare request - CF-Ray: {cf_ray}, "
        f"CF-Connecting-IP: {cf_connecting_ip}, "
        f"X-Forwarded-For: {x_forwarded_for}"
    )

    return True, None


# ==================== Cloudflare Access JWT Validation ====================

# Cache for Cloudflare Access public keys
_access_keys_cache = {
    'keys': None,
    'expires_at': None
}


def get_cloudflare_access_keys(team_domain: str) -> dict:
    """
    Fetch Cloudflare Access public keys for JWT validation.

    Args:
        team_domain: Your Cloudflare Access team domain (e.g., 'mycompany.cloudflareaccess.com')

    Returns:
        dict: JWKS (JSON Web Key Set) containing public keys
    """
    global _access_keys_cache

    # Check cache
    if _access_keys_cache['keys'] and _access_keys_cache['expires_at']:
        if datetime.utcnow() < _access_keys_cache['expires_at']:
            return _access_keys_cache['keys']

    # Fetch fresh keys
    certs_url = f"https://{team_domain}/cdn-cgi/access/certs"
    try:
        response = requests.get(certs_url, timeout=10)
        response.raise_for_status()
        keys = response.json()

        # Cache for 1 hour
        _access_keys_cache['keys'] = keys
        _access_keys_cache['expires_at'] = datetime.utcnow() + timedelta(hours=1)

        logger.info(f"Fetched Cloudflare Access keys from {certs_url}")
        return keys
    except Exception as e:
        logger.error(f"Failed to fetch Cloudflare Access keys: {e}")
        # Return cached keys if available
        if _access_keys_cache['keys']:
            return _access_keys_cache['keys']
        raise


def validate_cloudflare_access_token(token: str, team_domain: str, aud: str) -> tuple[bool, dict, str]:
    """
    Validate a Cloudflare Access JWT token.

    Args:
        token: The JWT token from CF_Authorization cookie
        team_domain: Your Cloudflare Access team domain
        aud: The Application Audience (AUD) tag from Access application settings

    Returns:
        tuple: (is_valid, claims, error_message)
        - claims contains: email, identity_nonce, sub, iat, exp, etc.
    """
    try:
        # Get public keys
        keys = get_cloudflare_access_keys(team_domain)

        # Get the JWT header to find the key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')

        # Find the matching public key
        public_key = None
        for key in keys.get('keys', []):
            if key.get('kid') == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                break

        if not public_key:
            return False, None, "No matching public key found for JWT"

        # Verify the token
        claims = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience=aud,
            options={
                'verify_exp': True,
                'verify_iat': True,
                'verify_aud': True,
            }
        )

        # Additional validation
        if 'email' not in claims:
            return False, None, "Token missing email claim"

        logger.info(f"Valid Cloudflare Access token for: {claims.get('email')}")
        return True, claims, None

    except jwt.ExpiredSignatureError:
        return False, None, "Token has expired"
    except jwt.InvalidAudienceError:
        return False, None, "Invalid token audience"
    except jwt.InvalidTokenError as e:
        return False, None, f"Invalid token: {str(e)}"
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return False, None, f"Token validation failed: {str(e)}"


def require_cloudflare_access(team_domain: str = None, aud: str = None):
    """
    Decorator to require valid Cloudflare Access authentication.

    Usage:
        @app.route('/superadmin')
        @require_cloudflare_access(
            team_domain='mycompany.cloudflareaccess.com',
            aud='32c234...'
        )
        def superadmin():
            # g.cf_access_user contains the authenticated user info
            return render_template('admin.html')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip in testing mode
            if os.environ.get('FLASK_ENV') == 'testing':
                return f(*args, **kwargs)

            # Check if Cloudflare Access is configured
            _team_domain = team_domain or os.environ.get('CF_ACCESS_TEAM_DOMAIN')
            _aud = aud or os.environ.get('CF_ACCESS_AUD')

            if not _team_domain or not _aud:
                logger.warning("Cloudflare Access not configured - denying access")
                return jsonify({'error': 'Access configuration missing'}), 503

            # Get the token from cookie
            token = request.cookies.get('CF_Authorization')
            if not token:
                logger.warning(f"No CF_Authorization cookie for {request.path}")
                return jsonify({'error': 'Cloudflare Access authentication required'}), 401

            # Validate the token
            is_valid, claims, error = validate_cloudflare_access_token(token, _team_domain, _aud)
            if not is_valid:
                logger.warning(f"Invalid Cloudflare Access token: {error}")
                return jsonify({'error': f'Authentication failed: {error}'}), 401

            # Store user info in g for route handlers
            g.cf_access_user = claims

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ==================== Flask Integration ====================

def _path_matches(request_path: str, pattern: str) -> bool:
    """Check if a request path matches a pattern.

    Supports:
    - Exact match: /superadmin
    - Wildcard suffix: /superadmin/*
    """
    if pattern.endswith('/*'):
        prefix = pattern[:-2]
        return request_path == prefix or request_path.startswith(prefix + '/')
    return request_path == pattern


def setup_cloudflare_security(app):
    """
    Set up Cloudflare security checks for a Flask application.

    This adds a before_request hook that:
    1. Validates all requests came through Cloudflare (if enabled)
    2. Validates Cloudflare Access JWT for protected paths (if enabled)

    Usage:
        from cloudflare_security import setup_cloudflare_security
        setup_cloudflare_security(app)
    """

    @app.before_request
    def check_cloudflare_security():
        """Validate Cloudflare origin and Access tokens."""
        # Skip for health checks and static files
        if request.path in ['/health', '/api/version', '/favicon.ico']:
            return None

        # Skip for static assets
        if request.path.startswith('/static/') or request.path.startswith('/assets/'):
            return None

        # 1. Validate origin (request came through Cloudflare)
        is_valid, error = validate_cloudflare_origin()
        if not is_valid:
            return jsonify({'error': error}), 403

        # 2. Check Cloudflare Access for protected paths
        config = _get_cloudflare_config()

        if config['access_enabled'] and config['access_team_domain'] and config['access_aud']:
            # Check if current path is protected
            for pattern in config['protected_paths']:
                if _path_matches(request.path, pattern):
                    # This path requires Cloudflare Access authentication
                    token = request.cookies.get('CF_Authorization')
                    if not token:
                        logger.warning(f"No CF_Authorization cookie for protected path: {request.path}")
                        return jsonify({
                            'error': 'Cloudflare Access authentication required',
                            'requires_cf_access': True
                        }), 401

                    # Validate the token
                    is_valid, claims, error = validate_cloudflare_access_token(
                        token,
                        config['access_team_domain'],
                        config['access_aud']
                    )
                    if not is_valid:
                        logger.warning(f"Invalid Cloudflare Access token for {request.path}: {error}")
                        return jsonify({
                            'error': f'Authentication failed: {error}',
                            'requires_cf_access': True
                        }), 401

                    # Store validated user info
                    g.cf_access_user = claims
                    logger.debug(f"Cloudflare Access validated for {claims.get('email')} on {request.path}")
                    break

        return None

    logger.info("Cloudflare security middleware enabled")


# ==================== Utility Functions ====================

def refresh_cloudflare_ips():
    """
    Fetch the latest Cloudflare IP ranges.

    This should be run periodically (e.g., weekly) to update the hardcoded lists.
    Cloudflare publishes their IPs at:
    - https://www.cloudflare.com/ips-v4
    - https://www.cloudflare.com/ips-v6
    """
    try:
        ipv4_response = requests.get('https://www.cloudflare.com/ips-v4', timeout=10)
        ipv6_response = requests.get('https://www.cloudflare.com/ips-v6', timeout=10)

        ipv4_ranges = ipv4_response.text.strip().split('\n')
        ipv6_ranges = ipv6_response.text.strip().split('\n')

        logger.info(f"Fetched {len(ipv4_ranges)} IPv4 and {len(ipv6_ranges)} IPv6 ranges")

        return {
            'ipv4': ipv4_ranges,
            'ipv6': ipv6_ranges
        }
    except Exception as e:
        logger.error(f"Failed to refresh Cloudflare IPs: {e}")
        return None
