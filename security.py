"""
Security module for multi-tenant data isolation and API security.

This module provides:
1. Tenant isolation decorators and helpers
2. Rate limiting configuration
3. Security headers
4. CSRF protection helpers
"""

from functools import wraps
from flask import g, jsonify, request, session
import logging
import hashlib
import hmac
import secrets
import time

logger = logging.getLogger(__name__)


# ==================== Tenant Isolation ====================

class TenantContext:
    """
    Context manager for tenant-scoped database operations.
    Ensures all queries are automatically filtered by tenant domain.
    """

    def __init__(self, domain):
        self.domain = domain

    @staticmethod
    def get_current_tenant():
        """Get the current tenant domain from the authenticated user."""
        from auth import is_master_account

        if is_master_account():
            # Master accounts don't have a tenant - they can see all
            return None

        if hasattr(g, 'current_user') and g.current_user:
            return g.current_user.sso_domain

        return None


def require_tenant_match(model_class, id_field='id'):
    """
    Decorator to verify that a resource belongs to the current tenant.
    Use this on endpoints that access specific resources by ID.

    Usage:
        @require_tenant_match(ArchitectureDecision)
        def get_decision(decision_id):
            # decision_id is validated to belong to current tenant
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from auth import is_master_account

            # Master accounts bypass tenant checks
            if is_master_account():
                return f(*args, **kwargs)

            # Get the resource ID from the route parameter
            resource_id = kwargs.get(id_field) or kwargs.get(f'{model_class.__name__.lower()}_id')

            if resource_id:
                resource = model_class.query.get(resource_id)
                if resource and hasattr(resource, 'domain'):
                    current_tenant = TenantContext.get_current_tenant()
                    if resource.domain != current_tenant:
                        logger.warning(
                            f"Tenant isolation violation: User from {current_tenant} "
                            f"tried to access {model_class.__name__} {resource_id} "
                            f"from domain {resource.domain}"
                        )
                        return jsonify({'error': 'Resource not found'}), 404

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def filter_by_tenant(query, model_class):
    """
    Filter a SQLAlchemy query by the current tenant.

    Usage:
        query = filter_by_tenant(ArchitectureDecision.query, ArchitectureDecision)
        decisions = query.all()
    """
    from auth import is_master_account

    if is_master_account():
        return query

    current_tenant = TenantContext.get_current_tenant()
    if current_tenant and hasattr(model_class, 'domain'):
        return query.filter(model_class.domain == current_tenant)

    return query


def validate_tenant_ownership(obj, allow_master=True):
    """
    Validate that an object belongs to the current tenant.
    Returns True if valid, False otherwise.

    Usage:
        if not validate_tenant_ownership(decision):
            return jsonify({'error': 'Not authorized'}), 403
    """
    from auth import is_master_account

    if allow_master and is_master_account():
        return True

    if not hasattr(obj, 'domain'):
        return True

    current_tenant = TenantContext.get_current_tenant()
    return obj.domain == current_tenant


# ==================== CSRF Protection ====================

def generate_csrf_token():
    """Generate a CSRF token for the current session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_urlsafe(32)
    return session['_csrf_token']


def validate_csrf_token(token):
    """Validate a CSRF token against the session token."""
    session_token = session.get('_csrf_token')
    if not session_token or not token:
        return False
    return hmac.compare_digest(session_token, token)


def csrf_protect(f):
    """
    Decorator to protect an endpoint from CSRF attacks.
    Checks for X-CSRF-Token header or csrf_token in request body.

    Exempt from CSRF:
    - GET, HEAD, OPTIONS requests
    - Requests with valid API keys (future)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return f(*args, **kwargs)

        # Check for CSRF token
        token = request.headers.get('X-CSRF-Token') or \
                request.form.get('csrf_token') or \
                (request.get_json(silent=True) or {}).get('csrf_token')

        # For now, log but don't block (gradual rollout)
        # TODO: Enable strict enforcement after frontend is updated
        if not validate_csrf_token(token):
            logger.debug(f"CSRF token missing or invalid for {request.path}")
            # return jsonify({'error': 'CSRF token missing or invalid'}), 403

        return f(*args, **kwargs)
    return decorated_function


# ==================== Rate Limiting Helpers ====================

def get_rate_limit_key():
    """
    Get a unique key for rate limiting.
    Uses user ID if authenticated, otherwise IP address.
    """
    if hasattr(g, 'current_user') and g.current_user:
        return f"user:{g.current_user.id}"

    # Use X-Forwarded-For for users behind proxies
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"

    return f"ip:{request.remote_addr}"


# ==================== Security Headers ====================

def get_security_headers():
    """
    Return security headers to be applied to all responses.
    These are used by Flask-Talisman or can be applied manually.
    """
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
    }


def apply_security_headers(response):
    """Apply security headers to a response object."""
    for header, value in get_security_headers().items():
        response.headers[header] = value
    return response


# ==================== Input Validation ====================

def sanitize_string(value, max_length=None, allow_html=False):
    """
    Sanitize a string input.
    - Strips leading/trailing whitespace
    - Optionally truncates to max_length
    - Optionally removes HTML tags (basic sanitization)
    """
    if not isinstance(value, str):
        return value

    value = value.strip()

    if max_length and len(value) > max_length:
        value = value[:max_length]

    if not allow_html:
        # Basic HTML tag removal (not comprehensive - use a proper library for untrusted input)
        import re
        value = re.sub(r'<[^>]+>', '', value)

    return value


def validate_email(email):
    """Basic email format validation."""
    import re
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_domain(domain):
    """Basic domain format validation."""
    import re
    if not domain:
        return False
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, domain))


# ==================== Logging Helpers ====================

def log_security_event(event_type, message, user_id=None, severity='INFO'):
    """
    Log a security-related event for auditing.

    Event types: 'auth', 'access', 'tenant_violation', 'rate_limit', 'csrf'
    """
    log_data = {
        'event_type': event_type,
        'message': message,
        'user_id': user_id or (g.current_user.id if hasattr(g, 'current_user') and g.current_user else None),
        'ip': request.remote_addr if request else None,
        'path': request.path if request else None,
        'method': request.method if request else None,
        'timestamp': time.time(),
    }

    log_message = f"[SECURITY:{event_type.upper()}] {message} | {log_data}"

    if severity == 'WARNING':
        logger.warning(log_message)
    elif severity == 'ERROR':
        logger.error(log_message)
    else:
        logger.info(log_message)
