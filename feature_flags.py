"""
Feature Flags Module

Controls which features are enabled based on deployment type.
Commercial features (like Slack integration) can be disabled for
open-source deployments.

Configuration:
- Environment variable: COMMERCIAL_FEATURES_ENABLED (default: false)
- Azure Key Vault: commercial-features-enabled
"""
import os
import logging
from functools import wraps
from flask import jsonify

logger = logging.getLogger(__name__)

# Cache for feature flags
_commercial_enabled = None


def is_commercial_enabled():
    """
    Check if commercial features are enabled.

    Commercial features include:
    - Slack integration
    - (Future: other integrations, advanced analytics, etc.)

    Returns True if commercial features are enabled, False otherwise.
    """
    global _commercial_enabled

    if _commercial_enabled is None:
        # Check environment variable first
        env_value = os.environ.get('COMMERCIAL_FEATURES_ENABLED', '').lower()

        if env_value in ('true', '1', 'yes'):
            _commercial_enabled = True
        elif env_value in ('false', '0', 'no', ''):
            # Default to checking Key Vault if not in env
            try:
                from keyvault_client import keyvault_client
                kv_value = keyvault_client.get_secret(
                    'commercial-features-enabled',
                    fallback_env_var='COMMERCIAL_FEATURES_ENABLED'
                )
                _commercial_enabled = kv_value and kv_value.lower() in ('true', '1', 'yes')
            except Exception as e:
                logger.debug(f"Could not check Key Vault for commercial features flag: {e}")
                _commercial_enabled = False
        else:
            _commercial_enabled = False

        logger.info(f"Commercial features enabled: {_commercial_enabled}")

    return _commercial_enabled


def is_slack_enabled():
    """Check if Slack integration is enabled."""
    return is_commercial_enabled()


def require_commercial(f):
    """
    Decorator to require commercial features for an endpoint.

    Returns 404 if commercial features are disabled (hides endpoint existence).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_commercial_enabled():
            return jsonify({'error': 'Not found'}), 404
        return f(*args, **kwargs)
    return decorated_function


def require_slack(f):
    """
    Decorator to require Slack integration for an endpoint.

    Returns 404 if Slack is disabled (hides endpoint existence).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_slack_enabled():
            return jsonify({'error': 'Not found'}), 404
        return f(*args, **kwargs)
    return decorated_function


def invalidate_cache():
    """Clear cached feature flag values."""
    global _commercial_enabled
    _commercial_enabled = None


def get_enabled_features():
    """
    Get a dictionary of enabled commercial features.

    Used by the frontend to conditionally show/hide UI elements.
    """
    return {
        'commercial': is_commercial_enabled(),
        'slack': is_slack_enabled(),
    }
