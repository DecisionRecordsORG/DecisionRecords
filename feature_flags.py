"""
Feature Flags Module

Controls which features are enabled based on edition (Community vs Enterprise).
Commercial features are disabled in the Community Edition.

Configuration:
- Environment variable: DECISION_RECORDS_EDITION (default: 'community')
- Values: 'community' or 'enterprise'

Security Note:
- Features are strictly tied to edition - no environment variable overrides
- For development/testing with EE features, run with DECISION_RECORDS_EDITION=enterprise
- Physical code separation (ee/ directory excluded in Community builds) provides
  additional protection - EE code doesn't exist in Community Edition Docker images
"""
import os
import logging
from functools import wraps
from flask import jsonify

logger = logging.getLogger(__name__)


class Edition:
    """Product editions."""
    COMMUNITY = 'community'
    ENTERPRISE = 'enterprise'


# Get current edition from environment
EDITION = os.environ.get('DECISION_RECORDS_EDITION', Edition.COMMUNITY).lower()

# Validate edition value
if EDITION not in (Edition.COMMUNITY, Edition.ENTERPRISE):
    logger.warning(f"Invalid DECISION_RECORDS_EDITION '{EDITION}', defaulting to community")
    EDITION = Edition.COMMUNITY

logger.info(f"Decision Records Edition: {EDITION}")


# Feature definitions - strictly tied to edition
# Enterprise features require DECISION_RECORDS_EDITION=enterprise
FEATURES = {
    # Core features (always available in both editions)
    'decisions': True,
    'multi_tenancy': True,
    'webauthn': True,
    'generic_oidc': True,
    'local_auth': True,
    'governance': True,
    'audit_logs': True,
    'email_notifications': True,
    'spaces': True,
    'infrastructure': True,

    # Enterprise features (require Enterprise Edition)
    'slack_integration': EDITION == Edition.ENTERPRISE,
    'teams_integration': EDITION == Edition.ENTERPRISE,
    'google_oauth': EDITION == Edition.ENTERPRISE,
    'slack_oidc': EDITION == Edition.ENTERPRISE,
    'ai_features': EDITION == Edition.ENTERPRISE,
    'posthog_analytics': EDITION == Edition.ENTERPRISE,
    'azure_keyvault': EDITION == Edition.ENTERPRISE,
    'cloudflare_security': EDITION == Edition.ENTERPRISE,
    'marketing_pages': EDITION == Edition.ENTERPRISE,
}


def is_feature_enabled(feature: str) -> bool:
    """Check if a specific feature is enabled."""
    return FEATURES.get(feature, False)


def is_enterprise() -> bool:
    """Check if running Enterprise Edition."""
    return EDITION == Edition.ENTERPRISE


def is_community() -> bool:
    """Check if running Community Edition."""
    return EDITION == Edition.COMMUNITY


# Legacy compatibility functions
def is_commercial_enabled() -> bool:
    """Legacy: Check if commercial features are enabled."""
    return is_enterprise()


def is_slack_enabled() -> bool:
    """Check if Slack integration is enabled."""
    return is_feature_enabled('slack_integration')


def is_teams_enabled() -> bool:
    """Check if Microsoft Teams integration is enabled."""
    return is_feature_enabled('teams_integration')


def is_ai_enabled() -> bool:
    """Check if AI features are enabled."""
    return is_feature_enabled('ai_features')


def is_google_oauth_enabled() -> bool:
    """Check if Google OAuth is enabled."""
    return is_feature_enabled('google_oauth')


def is_slack_oidc_enabled() -> bool:
    """Check if Slack OIDC is enabled."""
    return is_feature_enabled('slack_oidc')


def is_analytics_enabled() -> bool:
    """Check if PostHog analytics is enabled."""
    return is_feature_enabled('posthog_analytics')


def require_enterprise(f):
    """
    Decorator to require Enterprise Edition for an endpoint.
    Returns 404 if not Enterprise (hides endpoint existence).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_enterprise():
            return jsonify({'error': 'Not found'}), 404
        return f(*args, **kwargs)
    return decorated_function


def require_feature(feature: str):
    """
    Decorator factory to require a specific feature for an endpoint.
    Returns 404 if feature is disabled (hides endpoint existence).

    Usage:
        @require_feature('slack_integration')
        def slack_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_feature_enabled(feature):
                return jsonify({'error': 'Not found'}), 404
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Legacy decorators for backwards compatibility
def require_commercial(f):
    """Legacy: Decorator to require commercial/enterprise features."""
    return require_enterprise(f)


def require_slack(f):
    """Decorator to require Slack integration."""
    return require_feature('slack_integration')(f)


def require_teams(f):
    """Decorator to require Teams integration."""
    return require_feature('teams_integration')(f)


def require_ai(f):
    """Decorator to require AI features."""
    return require_feature('ai_features')(f)


def get_enabled_features() -> dict:
    """
    Get a dictionary of enabled features.
    Used by the frontend to conditionally show/hide UI elements.
    """
    return {
        'edition': EDITION,
        'is_enterprise': is_enterprise(),
        **{feature: enabled for feature, enabled in FEATURES.items()},
        # Legacy fields for backwards compatibility
        'commercial': is_enterprise(),
        'slack': is_slack_enabled(),
        'teams': is_teams_enabled(),
    }


def invalidate_cache():
    """Clear cached feature flag values (no-op in new system, kept for compatibility)."""
    pass
