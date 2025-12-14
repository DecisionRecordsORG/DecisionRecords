"""
PostHog Analytics Integration Module

Features:
- Configurable event tracking via decorators
- Privacy-respecting user identification (hashed distinct_id)
- Lazy initialization (only loads PostHog when enabled)
- Cached configuration to minimize DB calls
"""

import hashlib
import json
import logging
import os
import traceback
from functools import wraps
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)

# Configuration cache
_config_cache = {
    'enabled': None,
    'host': None,
    'api_key': None,
    'person_profiling': None,
    'exception_capture': None,
    'event_mappings': {},
    'last_refresh': None,
    'posthog_client': None
}
_cache_lock = Lock()
CACHE_TTL_SECONDS = 300  # 5 minutes

# Default event mappings for all endpoints
# Format: { 'internal_endpoint_name': 'posthog_event_name' }
DEFAULT_EVENT_MAPPINGS = {
    # System & Health (3)
    'health_check': 'system_health_checked',
    'ping': 'system_ping',
    'get_version': 'version_viewed',

    # Authentication - Local (4)
    'auth_local': 'auth_local_attempted',
    'api_auth_login': 'auth_login_attempted',
    'api_auth_logout': 'user_logged_out',
    'api_auth_csrf_token': 'csrf_token_requested',

    # Authentication - SSO (3)
    'api_auth_sso_configs': 'sso_configs_listed',
    'auth_sso': 'sso_initiated',
    'auth_callback': 'sso_callback_received',

    # Authentication - Email Verification (5)
    'api_auth_send_verification': 'verification_email_sent',
    'api_auth_resend_verification': 'verification_email_resent',
    'api_auth_verify_email': 'email_verified',
    'api_auth_verification_status': 'verification_status_checked',
    'api_auth_direct_signup': 'direct_signup_attempted',

    # Authentication - Access Requests (1)
    'api_auth_access_request': 'access_request_submitted',

    # Authentication - Account Recovery (4)
    'api_auth_request_recovery': 'account_recovery_requested',
    'api_auth_setup_token_validate': 'setup_token_validated',
    'api_auth_setup_token_use': 'setup_token_used',
    'api_auth_setup_password': 'password_setup_completed',

    # Authentication - Password Management (2)
    'api_auth_set_password': 'password_set',
    'api_master_password_change': 'master_password_changed',

    # WebAuthn / Passkeys (4)
    'api_webauthn_register_options': 'webauthn_register_started',
    'api_webauthn_register_verify': 'webauthn_register_completed',
    'api_webauthn_auth_options': 'webauthn_auth_started',
    'api_webauthn_auth_verify': 'webauthn_auth_completed',

    # User Profile & Credentials (7)
    'api_user_me': 'user_profile_viewed',
    'api_user_subscription_get': 'subscription_viewed',
    'api_user_subscription_update': 'subscription_updated',
    'api_user_dismiss_admin_onboarding': 'admin_onboarding_dismissed',
    'api_user_credentials_list': 'credentials_listed',
    'api_user_credentials_delete': 'credential_deleted',
    'api_user_credentials_create': 'credential_created',

    # Architecture Decisions (8)
    'api_decisions_list': 'decisions_listed',
    'api_decisions_create': 'decision_created',
    'api_decisions_get': 'decision_viewed',
    'api_decisions_update': 'decision_updated',
    'api_decisions_delete': 'decision_deleted',
    'api_decisions_history': 'decision_history_viewed',
    'api_decisions_spaces_get': 'decision_spaces_viewed',
    'api_decisions_spaces_update': 'decision_spaces_updated',

    # Infrastructure (6)
    'api_infrastructure_list': 'infrastructure_listed',
    'api_infrastructure_create': 'infrastructure_created',
    'api_infrastructure_get': 'infrastructure_viewed',
    'api_infrastructure_update': 'infrastructure_updated',
    'api_infrastructure_delete': 'infrastructure_deleted',
    'api_infrastructure_types': 'infrastructure_types_listed',

    # Spaces (6)
    'api_spaces_list': 'spaces_listed',
    'api_spaces_create': 'space_created',
    'api_spaces_get': 'space_viewed',
    'api_spaces_update': 'space_updated',
    'api_spaces_delete': 'space_deleted',
    'api_spaces_decisions': 'space_decisions_listed',

    # Admin - SSO Configuration (4)
    'api_admin_sso_list': 'admin_sso_configs_listed',
    'api_admin_sso_create': 'admin_sso_config_created',
    'api_admin_sso_update': 'admin_sso_config_updated',
    'api_admin_sso_delete': 'admin_sso_config_deleted',

    # Admin - Email Configuration (6)
    'api_admin_email_get': 'admin_email_config_viewed',
    'api_admin_email_save': 'admin_email_config_saved',
    'api_admin_email_test': 'admin_email_tested',
    'api_admin_email_system_get': 'superadmin_email_viewed',
    'api_admin_email_system_save': 'superadmin_email_saved',
    'api_admin_email_system_test': 'superadmin_email_tested',

    # Admin - Session Settings (2)
    'api_admin_settings_session_get': 'session_settings_viewed',
    'api_admin_settings_session_save': 'session_settings_saved',

    # Admin - Licensing Settings (2)
    'api_admin_settings_licensing_get': 'licensing_settings_viewed',
    'api_admin_settings_licensing_save': 'licensing_settings_saved',

    # Admin - Analytics Settings (4)
    'api_admin_settings_analytics_get': 'analytics_settings_viewed',
    'api_admin_settings_analytics_save': 'analytics_settings_saved',
    'api_admin_settings_analytics_api_key': 'analytics_api_key_updated',
    'api_admin_settings_analytics_test': 'analytics_test_event_sent',

    # Admin - User Management (4)
    'api_admin_users_list': 'admin_users_listed',
    'api_admin_users_toggle_admin': 'admin_user_role_toggled',
    'api_admin_users_setup_link': 'setup_link_generated',
    'api_admin_users_send_setup_email': 'setup_email_sent',

    # Admin - Access Requests (4)
    'api_admin_access_requests_list': 'access_requests_listed',
    'api_admin_access_requests_pending': 'pending_requests_listed',
    'api_admin_access_requests_approve': 'access_request_approved',
    'api_admin_access_requests_reject': 'access_request_rejected',

    # Admin - Auth Config (2)
    'api_admin_auth_config_get': 'auth_config_viewed',
    'api_admin_auth_config_save': 'auth_config_saved',

    # Admin - Role Requests (4)
    'api_admin_role_requests_list': 'admin_role_requests_listed',
    'api_admin_role_requests_create': 'admin_role_request_created',
    'api_admin_role_requests_approve': 'admin_role_request_approved',
    'api_admin_role_requests_reject': 'admin_role_request_rejected',

    # Admin - Tenant Admins (1)
    'api_admin_tenant_admins': 'tenant_admins_listed',

    # Tenant - Role Requests (4)
    'api_tenant_role_requests_create': 'role_request_created',
    'api_tenant_role_requests_list': 'role_requests_listed',
    'api_tenant_role_requests_approve': 'role_request_approved',
    'api_tenant_role_requests_reject': 'role_request_rejected',

    # Tenant - Auth Config (2)
    'api_tenant_auth_config_get': 'tenant_auth_config_viewed',
    'api_tenant_auth_config_update': 'tenant_auth_config_updated',

    # Super Admin - System Config (6)
    'api_system_config_get': 'system_config_viewed',
    'api_system_config_key_get': 'system_config_key_viewed',
    'api_system_config_set': 'system_config_updated',
    'api_system_email_verification_get': 'email_verification_setting_viewed',
    'api_system_email_verification_set': 'email_verification_setting_updated',
    'api_system_super_admin_email_get': 'super_admin_email_viewed',
    'api_system_super_admin_email_set': 'super_admin_email_updated',

    # Super Admin - Tenants (8)
    'api_tenants_list': 'tenants_listed',
    'api_tenants_maturity_get': 'tenant_maturity_viewed',
    'api_tenants_maturity_update': 'tenant_maturity_updated',
    'api_tenants_maturity_force': 'tenant_maturity_forced',
    'api_tenants_delete': 'tenant_deleted',
    'api_tenants_restore': 'tenant_restored',
    'api_tenants_limits': 'tenant_limits_viewed',

    # Super Admin - Domains (5)
    'api_domains_pending': 'pending_domains_listed',
    'api_domains_all': 'all_domains_listed',
    'api_domains_approve': 'domain_approved',
    'api_domains_reject': 'domain_rejected',
    'api_domains_check': 'domain_checked',

    # Super Admin - Master Account (1)
    'api_master_info': 'master_info_viewed',

    # Public - Feedback & Sponsorship (2)
    'api_feedback': 'feedback_submitted',
    'api_sponsorship': 'sponsorship_inquiry_submitted',
}

# Endpoint categories for frontend UI
ENDPOINT_CATEGORIES = {
    'system': {
        'name': 'System',
        'icon': 'monitor_heart',
        'endpoints': ['health_check', 'ping', 'get_version']
    },
    'authentication': {
        'name': 'Authentication',
        'icon': 'login',
        'endpoints': [
            'auth_local', 'api_auth_login', 'api_auth_logout', 'api_auth_csrf_token',
            'api_auth_sso_configs', 'auth_sso', 'auth_callback',
            'api_auth_send_verification', 'api_auth_resend_verification',
            'api_auth_verify_email', 'api_auth_verification_status',
            'api_auth_direct_signup', 'api_auth_access_request',
            'api_auth_request_recovery', 'api_auth_setup_token_validate',
            'api_auth_setup_token_use', 'api_auth_setup_password',
            'api_auth_set_password', 'api_master_password_change'
        ]
    },
    'webauthn': {
        'name': 'WebAuthn / Passkeys',
        'icon': 'fingerprint',
        'endpoints': [
            'api_webauthn_register_options', 'api_webauthn_register_verify',
            'api_webauthn_auth_options', 'api_webauthn_auth_verify'
        ]
    },
    'user_profile': {
        'name': 'User Profile',
        'icon': 'person',
        'endpoints': [
            'api_user_me', 'api_user_subscription_get', 'api_user_subscription_update',
            'api_user_dismiss_admin_onboarding', 'api_user_credentials_list',
            'api_user_credentials_delete', 'api_user_credentials_create'
        ]
    },
    'decisions': {
        'name': 'Decisions',
        'icon': 'description',
        'endpoints': [
            'api_decisions_list', 'api_decisions_create', 'api_decisions_get',
            'api_decisions_update', 'api_decisions_delete', 'api_decisions_history',
            'api_decisions_spaces_get', 'api_decisions_spaces_update'
        ]
    },
    'infrastructure': {
        'name': 'Infrastructure',
        'icon': 'dns',
        'endpoints': [
            'api_infrastructure_list', 'api_infrastructure_create',
            'api_infrastructure_get', 'api_infrastructure_update',
            'api_infrastructure_delete', 'api_infrastructure_types'
        ]
    },
    'spaces': {
        'name': 'Spaces',
        'icon': 'folder',
        'endpoints': [
            'api_spaces_list', 'api_spaces_create', 'api_spaces_get',
            'api_spaces_update', 'api_spaces_delete', 'api_spaces_decisions'
        ]
    },
    'admin': {
        'name': 'Admin',
        'icon': 'admin_panel_settings',
        'endpoints': [
            'api_admin_sso_list', 'api_admin_sso_create', 'api_admin_sso_update',
            'api_admin_sso_delete', 'api_admin_email_get', 'api_admin_email_save',
            'api_admin_email_test', 'api_admin_users_list', 'api_admin_users_toggle_admin',
            'api_admin_users_setup_link', 'api_admin_users_send_setup_email',
            'api_admin_access_requests_list', 'api_admin_access_requests_pending',
            'api_admin_access_requests_approve', 'api_admin_access_requests_reject',
            'api_admin_auth_config_get', 'api_admin_auth_config_save',
            'api_admin_role_requests_list', 'api_admin_role_requests_create',
            'api_admin_role_requests_approve', 'api_admin_role_requests_reject',
            'api_admin_tenant_admins', 'api_tenant_role_requests_create',
            'api_tenant_role_requests_list', 'api_tenant_role_requests_approve',
            'api_tenant_role_requests_reject', 'api_tenant_auth_config_get',
            'api_tenant_auth_config_update'
        ]
    },
    'super_admin': {
        'name': 'Super Admin',
        'icon': 'security',
        'endpoints': [
            'api_admin_email_system_get', 'api_admin_email_system_save',
            'api_admin_email_system_test', 'api_admin_settings_session_get',
            'api_admin_settings_session_save', 'api_admin_settings_licensing_get',
            'api_admin_settings_licensing_save', 'api_admin_settings_analytics_get',
            'api_admin_settings_analytics_save', 'api_admin_settings_analytics_api_key',
            'api_admin_settings_analytics_test', 'api_system_config_get',
            'api_system_config_key_get', 'api_system_config_set',
            'api_system_email_verification_get', 'api_system_email_verification_set',
            'api_system_super_admin_email_get', 'api_system_super_admin_email_set',
            'api_tenants_list', 'api_tenants_maturity_get', 'api_tenants_maturity_update',
            'api_tenants_maturity_force', 'api_tenants_delete', 'api_tenants_restore',
            'api_tenants_limits', 'api_domains_pending', 'api_domains_all',
            'api_domains_approve', 'api_domains_reject', 'api_domains_check',
            'api_master_info'
        ]
    },
    'public': {
        'name': 'Public',
        'icon': 'public',
        'endpoints': ['api_feedback', 'api_sponsorship']
    }
}


def _get_analytics_config():
    """Get analytics configuration with caching."""
    from models import SystemConfig

    with _cache_lock:
        now = datetime.utcnow()
        if (_config_cache['last_refresh'] and
            (now - _config_cache['last_refresh']).total_seconds() < CACHE_TTL_SECONDS):
            return _config_cache

        # Refresh from database
        _config_cache['enabled'] = SystemConfig.get_bool(
            SystemConfig.KEY_ANALYTICS_ENABLED,
            default=SystemConfig.DEFAULT_ANALYTICS_ENABLED
        )
        _config_cache['host'] = SystemConfig.get(
            SystemConfig.KEY_ANALYTICS_HOST,
            default=SystemConfig.DEFAULT_ANALYTICS_HOST
        )
        _config_cache['person_profiling'] = SystemConfig.get_bool(
            SystemConfig.KEY_ANALYTICS_PERSON_PROFILING,
            default=SystemConfig.DEFAULT_ANALYTICS_PERSON_PROFILING
        )
        _config_cache['exception_capture'] = SystemConfig.get_bool(
            SystemConfig.KEY_ANALYTICS_EXCEPTION_CAPTURE,
            default=SystemConfig.DEFAULT_ANALYTICS_EXCEPTION_CAPTURE
        )

        # Load event mappings (JSON from SystemConfig or defaults)
        mappings_json = SystemConfig.get(SystemConfig.KEY_ANALYTICS_EVENT_MAPPINGS)
        if mappings_json:
            try:
                _config_cache['event_mappings'] = json.loads(mappings_json)
            except json.JSONDecodeError:
                _config_cache['event_mappings'] = DEFAULT_EVENT_MAPPINGS.copy()
        else:
            _config_cache['event_mappings'] = DEFAULT_EVENT_MAPPINGS.copy()

        # Get API key from Key Vault (cloud) or SystemConfig (self-hosted)
        _config_cache['api_key'] = _get_api_key()

        _config_cache['last_refresh'] = now

        # Initialize/reinitialize PostHog client if enabled
        if _config_cache['enabled'] and _config_cache['api_key']:
            _init_posthog_client()

        return _config_cache


def _get_api_key():
    """Get PostHog API key from Key Vault, env var, or SystemConfig."""
    from keyvault_client import keyvault_client
    from models import SystemConfig

    # Try Key Vault first (cloud deployment)
    api_key = keyvault_client.get_posthog_api_key()
    if api_key:
        return api_key

    # Fallback to SystemConfig (self-hosted)
    api_key = SystemConfig.get(SystemConfig.KEY_ANALYTICS_API_KEY)
    if api_key:
        return api_key

    return None


def _get_analytics_salt():
    """Get salt for generating distinct IDs."""
    from keyvault_client import keyvault_client
    return keyvault_client.get_analytics_salt()


def _init_posthog_client():
    """Initialize PostHog client lazily."""
    try:
        from posthog import Posthog

        if _config_cache['posthog_client']:
            # Shutdown existing client
            try:
                _config_cache['posthog_client'].shutdown()
            except:
                pass

        _config_cache['posthog_client'] = Posthog(
            project_api_key=_config_cache['api_key'],
            host=_config_cache['host'],
            # Timeout configuration - fail fast to avoid blocking requests
            timeout=5,  # Reduced from default 15s to fail faster
            feature_flags_request_timeout_seconds=3,
            # Performance optimizations
            gzip=True,  # Compress payloads to reduce bandwidth
            max_retries=2,  # Retry failed requests (default is 3)
            # Async batching settings
            flush_at=50,  # Flush after 50 events (default is 100)
            flush_interval=1.0,  # Flush every 1 second (default is 0.5)
            # Error handling
            on_error=lambda e, items: logger.warning(f"PostHog error (non-blocking): {e}")
        )
        logger.info(f"PostHog client initialized for host: {_config_cache['host']} (timeout=5s, gzip=true)")
    except ImportError:
        logger.warning("PostHog package not installed. Analytics disabled.")
        _config_cache['posthog_client'] = None
    except Exception as e:
        logger.error(f"Failed to initialize PostHog: {e}")
        _config_cache['posthog_client'] = None


def generate_distinct_id(user_id, tenant_domain):
    """
    Generate a privacy-respecting distinct_id for PostHog.

    Uses: SHA256(user_id + tenant_domain + secret_salt)[:32]

    Properties:
    - Deterministic: Same user gets same ID across sessions
    - Not reversible: Cannot derive user_id from distinct_id
    - Tenant-scoped: Same user in different tenants has different IDs
    """
    salt = _get_analytics_salt()

    # Create deterministic hash
    data = f"{user_id}:{tenant_domain or 'no-tenant'}:{salt}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def track_event(endpoint_name, properties=None):
    """
    Track an analytics event.

    Args:
        endpoint_name: Internal endpoint name (e.g., 'api_decisions_create')
        properties: Optional dict of additional properties
    """
    from flask import g, request, session

    config = _get_analytics_config()

    if not config['enabled'] or not config['posthog_client']:
        return

    # Get event name from mappings
    event_name = config['event_mappings'].get(endpoint_name)
    if not event_name:
        # Event not mapped - skip tracking
        logger.debug(f"No event mapping for endpoint: {endpoint_name}")
        return

    # Generate distinct_id
    distinct_id = 'anonymous'
    user_type = 'anonymous'
    tenant_domain = None

    # Check if user is authenticated
    if session.get('is_master'):
        # Master admin
        distinct_id = 'master_admin'
        user_type = 'master_admin'
    elif hasattr(g, 'current_user') and g.current_user:
        # Authenticated tenant user
        tenant_domain = getattr(g.current_user, 'sso_domain', None)
        distinct_id = generate_distinct_id(g.current_user.id, tenant_domain)
        user_type = 'authenticated'

    # Build properties
    event_properties = {
        'user_type': user_type,
        'endpoint': endpoint_name,
        'path': request.path if request else None,
        'method': request.method if request else None,
    }

    if tenant_domain:
        # Hash tenant domain for privacy
        event_properties['tenant_hash'] = hashlib.sha256(
            tenant_domain.encode()
        ).hexdigest()[:16]

    if properties:
        event_properties.update(properties)

    # Optionally disable person profile creation
    if not config['person_profiling']:
        event_properties['$process_person_profile'] = False

    try:
        config['posthog_client'].capture(
            distinct_id=distinct_id,
            event=event_name,
            properties=event_properties
        )
        logger.debug(f"Tracked event: {event_name} for {distinct_id}")
    except Exception as e:
        logger.warning(f"Failed to track event {event_name}: {e}")


def track_endpoint(endpoint_name, extra_properties=None):
    """
    Decorator to track API endpoint calls.

    Usage:
        @app.route('/api/decisions', methods=['GET'])
        @login_required
        @track_endpoint('api_decisions_list')
        def list_decisions():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Execute the endpoint first
            result = f(*args, **kwargs)

            # Track event (non-blocking, errors don't affect response)
            try:
                properties = extra_properties.copy() if extra_properties else {}

                # Add response status if available
                if isinstance(result, tuple) and len(result) > 1:
                    if isinstance(result[1], int):
                        properties['response_status'] = result[1]

                track_event(endpoint_name, properties)
            except Exception as e:
                logger.debug(f"Analytics tracking failed: {e}")

            return result
        return decorated_function
    return decorator


def invalidate_cache():
    """Invalidate configuration cache (call after settings change)."""
    with _cache_lock:
        _config_cache['last_refresh'] = None
        logger.debug("Analytics configuration cache invalidated")


def shutdown():
    """Shutdown PostHog client gracefully."""
    with _cache_lock:
        if _config_cache['posthog_client']:
            try:
                _config_cache['posthog_client'].shutdown()
                logger.info("PostHog client shutdown complete")
            except Exception as e:
                logger.warning(f"Error shutting down PostHog client: {e}")
            _config_cache['posthog_client'] = None


def capture_exception(exception, endpoint_name=None, extra_properties=None):
    """
    Capture an exception to PostHog for error monitoring.

    Args:
        exception: The exception object to capture
        endpoint_name: Optional name of the endpoint where the error occurred
        extra_properties: Optional dict of additional properties

    Usage:
        try:
            risky_operation()
        except Exception as e:
            capture_exception(e, 'api_decisions_create')
            raise
    """
    from flask import g, request, session

    config = _get_analytics_config()

    # Check if exception capture is enabled
    if not config['enabled'] or not config['exception_capture'] or not config['posthog_client']:
        return

    # Generate distinct_id (same logic as track_event)
    distinct_id = 'anonymous'
    user_type = 'anonymous'
    tenant_domain = None

    if session.get('is_master'):
        distinct_id = 'master_admin'
        user_type = 'master_admin'
    elif hasattr(g, 'current_user') and g.current_user:
        tenant_domain = getattr(g.current_user, 'sso_domain', None)
        distinct_id = generate_distinct_id(g.current_user.id, tenant_domain)
        user_type = 'authenticated'

    # Build exception properties following PostHog's exception format
    exception_type = type(exception).__name__
    exception_message = str(exception)
    exception_traceback = traceback.format_exc()

    # Parse traceback into structured format
    tb_lines = exception_traceback.strip().split('\n')

    event_properties = {
        # PostHog standard exception properties
        '$exception_type': exception_type,
        '$exception_message': exception_message,
        '$exception_list': [{
            'type': exception_type,
            'value': exception_message,
            'stacktrace': {
                'type': 'raw',
                'frames': tb_lines[-10:] if len(tb_lines) > 10 else tb_lines  # Last 10 lines
            }
        }],
        # Custom properties
        'user_type': user_type,
        'endpoint': endpoint_name,
        'path': request.path if request else None,
        'method': request.method if request else None,
    }

    if tenant_domain:
        event_properties['tenant_hash'] = hashlib.sha256(
            tenant_domain.encode()
        ).hexdigest()[:16]

    if extra_properties:
        event_properties.update(extra_properties)

    # Optionally disable person profile creation
    if not config['person_profiling']:
        event_properties['$process_person_profile'] = False

    try:
        config['posthog_client'].capture(
            distinct_id=distinct_id,
            event='$exception',
            properties=event_properties
        )
        logger.debug(f"Captured exception: {exception_type} for {distinct_id}")
    except Exception as e:
        # Never let exception capture cause additional errors
        logger.warning(f"Failed to capture exception: {e}")


def get_config_for_api():
    """Get analytics configuration for API response (without sensitive data)."""
    config = _get_analytics_config()

    return {
        'enabled': config['enabled'],
        'host': config['host'],
        'person_profiling': config['person_profiling'],
        'exception_capture': config['exception_capture'],
        'api_key_configured': bool(config['api_key']),
        'event_mappings': config['event_mappings'],
        'categories': ENDPOINT_CATEGORIES
    }
