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


# ==================== Input Validation & Sanitization ====================

# Initialize Bleach for HTML sanitization
try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
    logger.warning("Bleach not installed, using basic HTML sanitization")

# Allowed HTML tags and attributes for user content
ALLOWED_TAGS = ['p', 'br', 'b', 'i', 'u', 'strong', 'em', 'ul', 'ol', 'li', 'a', 'code', 'pre']
ALLOWED_ATTRS = {
    'a': ['href', 'title'],
    '*': []
}


def sanitize_html(value, allowed_tags=None, allowed_attrs=None):
    """
    Sanitize HTML content using Bleach.
    Only allows safe tags and attributes.

    Args:
        value: The HTML string to sanitize
        allowed_tags: List of allowed HTML tags (default: ALLOWED_TAGS)
        allowed_attrs: Dict of allowed attributes per tag (default: ALLOWED_ATTRS)

    Returns:
        Sanitized HTML string
    """
    if not isinstance(value, str):
        return value

    if allowed_tags is None:
        allowed_tags = ALLOWED_TAGS
    if allowed_attrs is None:
        allowed_attrs = ALLOWED_ATTRS

    if BLEACH_AVAILABLE:
        # Use Bleach for proper HTML sanitization
        return bleach.clean(
            value,
            tags=allowed_tags,
            attributes=allowed_attrs,
            strip=True,
            strip_comments=True
        )
    else:
        # Fallback: Remove all HTML tags
        import re
        return re.sub(r'<[^>]+>', '', value)


def sanitize_string(value, max_length=None, allow_html=False, strip_all_tags=False):
    """
    Sanitize a string input.

    Args:
        value: The string to sanitize
        max_length: Optional maximum length (truncates if exceeded)
        allow_html: If True, allows safe HTML tags; if False, strips all tags
        strip_all_tags: If True, removes ALL HTML tags regardless of allow_html

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return value

    value = value.strip()

    # Handle HTML sanitization
    if strip_all_tags or not allow_html:
        if BLEACH_AVAILABLE:
            # Use Bleach to strip all tags
            value = bleach.clean(value, tags=[], strip=True)
        else:
            # Fallback regex
            import re
            value = re.sub(r'<[^>]+>', '', value)
    elif allow_html:
        # Allow safe HTML tags only
        value = sanitize_html(value)

    # Truncate if needed
    if max_length and len(value) > max_length:
        value = value[:max_length]

    return value


def sanitize_text_field(value, max_length=10000):
    """
    Sanitize a text field (like decision context, consequences).
    Allows limited HTML formatting.
    """
    return sanitize_string(value, max_length=max_length, allow_html=True)


def sanitize_title(value, max_length=255):
    """
    Sanitize a title field. No HTML allowed.
    """
    return sanitize_string(value, max_length=max_length, allow_html=False, strip_all_tags=True)


def sanitize_name(value, max_length=255):
    """
    Sanitize a name field (user name, organization name). No HTML allowed.
    """
    return sanitize_string(value, max_length=max_length, allow_html=False, strip_all_tags=True)


def sanitize_email(email):
    """
    Sanitize and validate an email address.
    Returns the sanitized email or None if invalid.
    """
    if not email:
        return None

    # Strip whitespace and convert to lowercase
    email = str(email).strip().lower()

    # Basic sanitization - remove any HTML
    if BLEACH_AVAILABLE:
        email = bleach.clean(email, tags=[], strip=True)
    else:
        import re
        email = re.sub(r'<[^>]+>', '', email)

    # Validate format
    if not validate_email(email):
        return None

    return email


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


def sanitize_request_data(data, schema):
    """
    Sanitize request data according to a schema.

    Schema format:
    {
        'field_name': {'type': 'title|text|email|name|string', 'max_length': 255, 'required': True}
    }

    Returns:
        Tuple of (sanitized_data, errors_list)
    """
    if not isinstance(data, dict):
        return {}, ['Invalid request data']

    sanitized = {}
    errors = []

    for field, rules in schema.items():
        value = data.get(field)
        field_type = rules.get('type', 'string')
        max_length = rules.get('max_length')
        required = rules.get('required', False)

        # Check required fields
        if required and not value:
            errors.append(f'{field} is required')
            continue

        if value is None:
            continue

        # Sanitize based on type
        if field_type == 'title':
            sanitized[field] = sanitize_title(value, max_length or 255)
        elif field_type == 'text':
            sanitized[field] = sanitize_text_field(value, max_length or 10000)
        elif field_type == 'email':
            sanitized_email = sanitize_email(value)
            if required and not sanitized_email:
                errors.append(f'{field} is not a valid email')
            else:
                sanitized[field] = sanitized_email
        elif field_type == 'name':
            sanitized[field] = sanitize_name(value, max_length or 255)
        else:
            sanitized[field] = sanitize_string(value, max_length=max_length, allow_html=False)

    return sanitized, errors


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
