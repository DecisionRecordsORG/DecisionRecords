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
import re
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
            from models import db

            # Master accounts bypass tenant checks
            if is_master_account():
                return f(*args, **kwargs)

            # Get the resource ID from the route parameter
            resource_id = kwargs.get(id_field) or kwargs.get(f'{model_class.__name__.lower()}_id')

            if resource_id:
                resource = db.session.get(model_class, resource_id)
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

CSRF_SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
CSRF_SESSION_EXEMPT_PATHS = {
    '/logout',
    '/api/auth/logout',
    # OAuth token and revocation endpoints (Enterprise). They are called by
    # applications, authenticate by what is in the request body (a code with
    # its PKCE verifier, or a token) and never read the session, so a session
    # cookie that happens to arrive with the request gives it nothing to forge.
    '/oauth/token',
    '/oauth/revoke',
}
CSRF_SESSION_EXEMPT_PREFIXES = (
    '/api/test/',
)

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


def get_request_csrf_token():
    """Extract a CSRF token from the current request."""
    return (
        request.headers.get('X-CSRF-Token')
        or request.form.get('csrf_token')
        or (request.get_json(silent=True) or {}).get('csrf_token')
    )


def should_enforce_csrf():
    """Return True when the current request must present a CSRF token."""
    if request.method in CSRF_SAFE_METHODS:
        return False

    if request.path in CSRF_SESSION_EXEMPT_PATHS:
        return False

    if any(request.path.startswith(prefix) for prefix in CSRF_SESSION_EXEMPT_PREFIXES):
        return False

    return 'user_id' in session or 'master_id' in session


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
        if not should_enforce_csrf():
            return f(*args, **kwargs)

        token = get_request_csrf_token()
        if not validate_csrf_token(token):
            logger.warning(f"CSRF token missing or invalid for {request.path}")
            return jsonify({'error': 'CSRF token missing or invalid'}), 403

        return f(*args, **kwargs)
    return decorated_function


# ==================== Redirect Target Validation ====================

MAX_REDIRECT_PATH_LENGTH = 2000

# Unreserved, sub-delimiter and path/query/fragment characters from RFC 3986.
# Deliberately excludes backslashes, whitespace, control characters and
# anything outside ASCII: browsers normalise several of those into "/" or drop
# them, which is how "/\host" and "/<tab>/host" become "//host".
_REDIRECT_PATH_ALLOWED = re.compile(r"/[A-Za-z0-9\-._~!$&'()*+,;=:@/?#%]*")
_PERCENT_ESCAPE = re.compile(r'%(.{0,2})')
# Escapes that would smuggle a separator, a dot segment or another escape
# into the path once decoded by a proxy or the browser.
_FORBIDDEN_PATH_ESCAPES = {0x2F, 0x5C, 0x2E, 0x25}


def safe_redirect_path(value, default='/'):
    """Return `value` if it is a same-site relative path, otherwise `default`.

    Use this for every redirect target that originates from a request
    (query string, form field, OAuth state). Only an absolute path on this
    site is accepted: it must start with a single "/", so it can be appended
    to a trusted base URL or sent as a relative Location without changing
    host. Schemes, "//host", backslashes, whitespace, control characters,
    malformed or separator-hiding percent escapes and over-long values are
    all rejected rather than repaired.
    """
    if not isinstance(value, str) or not value:
        return default

    if len(value) > MAX_REDIRECT_PATH_LENGTH:
        return default

    if not _REDIRECT_PATH_ALLOWED.fullmatch(value):
        return default

    path = value.split('#', 1)[0].split('?', 1)[0]

    # No empty segments: rules out "//host" and "/.//host" style targets.
    if '//' in path:
        return default

    for match in _PERCENT_ESCAPE.finditer(value):
        digits = match.group(1)
        if not re.fullmatch(r'[0-9A-Fa-f]{2}', digits):
            return default
        code = int(digits, 16)
        if code < 0x20 or code == 0x7F:
            return default
        if match.start() < len(path) and code in _FORBIDDEN_PATH_ESCAPES:
            return default

    return value


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
