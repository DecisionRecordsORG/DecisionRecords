# Security Features Documentation

Comprehensive overview of security implementations in the Architecture Decisions application.

## Table of Contents
- [Security Architecture](#security-architecture)
- [Authentication & Authorization](#authentication--authorization)
- [CSRF Protection](#csrf-protection)
- [Input Sanitization](#input-sanitization)
- [Tenant Isolation](#tenant-isolation)
- [Rate Limiting](#rate-limiting)
- [Security Headers](#security-headers)
- [Secure Credential Management](#secure-credential-management)
- [Security Best Practices](#security-best-practices)

## Security Architecture

### Defense in Depth Strategy

```
┌─────────────────────────────────────────┐
│           Layer 1: Network              │
│        (Azure WAF, NSG, VNet)           │
├─────────────────────────────────────────┤
│         Layer 2: Application            │
│    (CSRF, Headers, Rate Limiting)       │
├─────────────────────────────────────────┤
│         Layer 3: Authentication         │
│     (WebAuthn, SSO, Session Mgmt)       │
├─────────────────────────────────────────┤
│          Layer 4: Authorization         │
│      (RBAC, Tenant Isolation)           │
├─────────────────────────────────────────┤
│           Layer 5: Data                 │
│    (Encryption, Sanitization, Vault)    │
└─────────────────────────────────────────┘
```

## Authentication & Authorization

### Authentication Methods

#### 1. WebAuthn/Passkeys (Passwordless)
- **Standard**: FIDO2/WebAuthn compliant
- **Security**: Public key cryptography
- **MFA**: Built-in multi-factor authentication
- **Implementation**: `/webauthn_auth.py`

```python
# Registration flow
@app.route('/api/webauthn/register/begin')
def webauthn_register_begin():
    # Generate challenge and public key parameters
    options = create_registration_options(user)
    return jsonify(options)

@app.route('/api/webauthn/register/complete')
def webauthn_register_complete():
    # Verify and store credential
    credential = verify_registration(response)
    store_credential(user, credential)
```

#### 2. SSO Integration
- **Protocol**: OIDC (OpenID Connect)
- **Providers**: Any OIDC-compliant provider
- **Configuration**: Per-tenant SSO settings

#### 3. Local Authentication
- **Method**: Email + Password
- **Security**: Bcrypt hashing, secure sessions
- **Optional**: Can be disabled per tenant

### Authorization Levels

| Level | Description | Capabilities |
|-------|-------------|--------------|
| **Super Admin** | System-wide administrator | All operations, all tenants |
| **Tenant Admin** | Organization administrator | Manage users, settings within tenant |
| **User** | Regular user | CRUD own decisions, view shared |
| **Anonymous** | Unauthenticated | Public landing page only |

## CSRF Protection

### Implementation

#### Backend (Python/Flask)
```python
# security.py
def generate_csrf_token():
    """Generate a new CSRF token."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token(token):
    """Validate the provided CSRF token."""
    return token and token == session.get('csrf_token')

@csrf_protect
def sensitive_operation():
    # Automatically validates CSRF token
    pass
```

#### Frontend (Angular)
```typescript
// csrf.interceptor.ts
export const csrfInterceptor: HttpInterceptorFn = (req, next) => {
  // Add CSRF token to state-changing requests
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(req.method)) {
    req = req.clone({
      setHeaders: { 'X-CSRF-Token': csrfToken }
    });
  }
  
  return next(req).pipe(
    tap(event => {
      // Capture new token from response
      if (event instanceof HttpResponse) {
        const newToken = event.headers.get('X-CSRF-Token');
        if (newToken) csrfToken = newToken;
      }
    })
  );
};
```

## Input Sanitization

### HTML Sanitization
Uses `bleach` library for safe HTML content:

```python
def sanitize_html(value, allowed_tags=None, allowed_attrs=None):
    """
    Sanitize HTML content to prevent XSS attacks.
    
    Default allowed tags: p, br, strong, em, u, a, ul, ol, li, 
                         blockquote, code, pre, h3, h4, h5, h6
    """
    return bleach.clean(
        value,
        tags=allowed_tags or DEFAULT_ALLOWED_TAGS,
        attributes=allowed_attrs or DEFAULT_ALLOWED_ATTRS,
        strip=True
    )
```

### Field-Specific Sanitization

```python
# Different sanitization for different field types
def sanitize_email(email):
    """Validate and sanitize email addresses."""
    email = email.strip().lower()
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValueError('Invalid email format')
    return email

def sanitize_title(value, max_length=255):
    """Sanitize title fields - no HTML, limited length."""
    return sanitize_string(value, max_length=max_length, allow_html=False)

def sanitize_text_field(value, max_length=10000):
    """Sanitize text fields - allow basic HTML."""
    return sanitize_string(value, max_length=max_length, allow_html=True)
```

### Request Data Sanitization

```python
def sanitize_request_data(data, schema):
    """
    Sanitize request data based on schema.
    
    Example schema:
    {
        'title': {'type': 'title', 'required': True},
        'description': {'type': 'text', 'required': False},
        'email': {'type': 'email', 'required': True}
    }
    """
    sanitized = {}
    errors = []
    
    for field, rules in schema.items():
        value = data.get(field)
        
        # Validate required fields
        if rules.get('required') and not value:
            errors.append(f'{field} is required')
            continue
        
        # Apply type-specific sanitization
        if rules['type'] == 'email':
            sanitized[field] = sanitize_email(value)
        elif rules['type'] == 'title':
            sanitized[field] = sanitize_title(value)
        elif rules['type'] == 'text':
            sanitized[field] = sanitize_text_field(value)
    
    return sanitized, errors
```

## Tenant Isolation

### Data Access Control

```python
class TenantContext:
    """
    Context manager for tenant-scoped operations.
    Ensures queries are filtered by tenant domain.
    """
    
    @staticmethod
    def get_current_tenant():
        """Get the current tenant from authenticated user."""
        if is_master_account():
            return None  # Master can see all
        return g.current_user.sso_domain if g.current_user else None

def filter_by_tenant(query, model_class):
    """
    Filter query by current tenant.
    
    Usage:
    decisions = filter_by_tenant(
        ArchitectureDecision.query, 
        ArchitectureDecision
    ).all()
    """
    tenant = TenantContext.get_current_tenant()
    if tenant and hasattr(model_class, 'domain'):
        return query.filter_by(domain=tenant)
    return query
```

### Tenant Validation Decorator

```python
@require_tenant_match(ArchitectureDecision)
def update_decision(decision_id):
    """
    Decorator ensures the decision belongs to user's tenant
    before allowing access.
    """
    decision = ArchitectureDecision.query.get_or_404(decision_id)
    # Automatically validated by decorator
    return update_resource(decision)
```

## Rate Limiting

### Configuration

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"],
    storage_uri="redis://localhost:6379"
)

# API-specific limits
@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Login endpoint with strict rate limiting."""
    pass

@app.route('/api/decisions', methods=['POST'])
@limiter.limit("30 per hour")
def create_decision():
    """Create decision with reasonable rate limit."""
    pass
```

### Custom Rate Limit Keys

```python
def get_rate_limit_key():
    """
    Custom rate limit key based on user/tenant.
    """
    if hasattr(g, 'current_user') and g.current_user:
        # Per-user limiting
        return f"user:{g.current_user.id}"
    elif request.headers.get('X-Tenant-Domain'):
        # Per-tenant limiting
        return f"tenant:{request.headers.get('X-Tenant-Domain')}"
    else:
        # Fall back to IP
        return get_remote_address()
```

## Security Headers

### Flask-Talisman Configuration

```python
from flask_talisman import Talisman

# Content Security Policy
csp = {
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    'style-src': "'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src': "'self' https://fonts.gstatic.com",
    'img-src': "'self' data: https:",
    'connect-src': "'self'"
}

Talisman(app, 
    force_https=True,
    strict_transport_security=True,
    content_security_policy=csp,
    content_security_policy_nonce_in=['script-src'],
    feature_policy={
        'geolocation': "'none'",
        'camera': "'none'",
        'microphone': "'none'"
    }
)
```

### Custom Security Headers

```python
@app.after_request
def apply_security_headers(response):
    """Apply security headers to all responses."""
    headers = {
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), camera=(), microphone=()'
    }
    
    for header, value in headers.items():
        response.headers[header] = value
    
    return response
```

## Secure Credential Management

### Azure Key Vault Integration

All application secrets are stored in Azure Key Vault for secure, centralized management:

| Secret Name | Purpose |
|-------------|---------|
| `flask-secret-key` | Flask session signing and CSRF tokens |
| `database-url` | PostgreSQL connection string (optional) |
| `smtp-username` | SMTP authentication username |
| `smtp-password` | SMTP authentication password |

```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

class KeyVaultClient:
    """Secure credential management with Azure Key Vault."""

    def __init__(self):
        self.vault_url = os.environ.get('AZURE_KEYVAULT_URL',
                                        'https://adr-keyvault-eu.vault.azure.net/')
        self._client = None
        self._initialized = False

    def get_secret(self, secret_name, fallback_env_var=None, default=None):
        """
        Get a secret from Key Vault with fallback to environment variable.

        Priority:
        1. Azure Key Vault
        2. Environment variable
        3. Default value
        """
        # Try Key Vault first
        if self._initialize() and self._client:
            try:
                return self._client.get_secret(secret_name).value
            except Exception:
                pass

        # Fallback to environment variable
        if fallback_env_var:
            env_value = os.environ.get(fallback_env_var)
            if env_value:
                return env_value

        return default

    def get_flask_secret_key(self):
        """Get Flask SECRET_KEY from Key Vault or environment."""
        return self.get_secret('flask-secret-key', fallback_env_var='SECRET_KEY')

    def get_database_url(self):
        """Get database URL from Key Vault or environment."""
        return self.get_secret('database-url', fallback_env_var='DATABASE_URL',
                              default='sqlite:///architecture_decisions.db')

    def get_smtp_credentials(self):
        """Retrieve SMTP credentials from Key Vault."""
        username = self.get_secret('smtp-username')
        password = self.get_secret('smtp-password')
        return username, password
```

### Secrets Priority Chain

The application uses a secure fallback chain for all secrets:

```
┌─────────────────────────────────────────────────────────────┐
│                     Priority 1: Key Vault                    │
│     (Most secure - managed identity, audit logging)          │
└──────────────────────────┬──────────────────────────────────┘
                           │ If not found
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 Priority 2: Environment Variable             │
│      (Secure for container deployments via ARM template)     │
└──────────────────────────┬──────────────────────────────────┘
                           │ If not found
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Priority 3: Default Value                  │
│           (Only for non-sensitive development)               │
└─────────────────────────────────────────────────────────────┘
```

### Adding Secrets to Key Vault

```bash
# Flask SECRET_KEY (required for session persistence)
az keyvault secret set \
  --vault-name adr-keyvault-eu \
  --name flask-secret-key \
  --value "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"

# Database URL (optional - can use environment variable)
az keyvault secret set \
  --vault-name adr-keyvault-eu \
  --name database-url \
  --value "postgresql://user:pass@host:5432/db?sslmode=require"

# SMTP credentials
az keyvault secret set --vault-name adr-keyvault-eu --name smtp-username --value "your-username"
az keyvault secret set --vault-name adr-keyvault-eu --name smtp-password --value "your-password"
```

## Security Best Practices

### 1. Password Security
- **Never store plain text passwords**
- Use bcrypt with appropriate cost factor
- Implement password complexity requirements
- Support passwordless authentication (WebAuthn)

### 2. Session Management
```python
# Secure session configuration
app.config.update(
    SESSION_COOKIE_SECURE=True,  # HTTPS only
    SESSION_COOKIE_HTTPONLY=True,  # No JS access
    SESSION_COOKIE_SAMESITE='Lax',  # CSRF protection
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
    SESSION_COOKIE_NAME='__Host-session'  # Cookie prefix
)
```

### 3. SQL Injection Prevention
```python
# Always use parameterized queries
# GOOD
user = User.query.filter_by(email=email).first()

# BAD - Never do this!
user = db.session.execute(f"SELECT * FROM users WHERE email = '{email}'")

# For complex queries, use SQLAlchemy
from sqlalchemy import text
result = db.session.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {"email": email}
)
```

### 4. File Upload Security
```python
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def secure_upload(file):
    if file and allowed_file(file.filename):
        # Sanitize filename
        filename = secure_filename(file.filename)
        # Add UUID to prevent collisions
        filename = f"{uuid.uuid4()}_{filename}"
        # Validate file size
        if len(file.read()) > MAX_FILE_SIZE:
            raise ValueError("File too large")
        file.seek(0)  # Reset after reading
        # Save to secure location
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
```

### 5. Logging and Monitoring
```python
def log_security_event(event_type, message, user_id=None, severity='INFO'):
    """Log security events for audit trail."""
    log_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'message': message,
        'user_id': user_id or (g.current_user.id if hasattr(g, 'current_user') else None),
        'ip': request.remote_addr,
        'user_agent': request.user_agent.string,
        'path': request.path,
        'method': request.method
    }
    
    if severity == 'CRITICAL':
        logger.critical(json.dumps(log_data))
        # Send alert to admin
        notify_admin_critical_event(log_data)
    elif severity == 'WARNING':
        logger.warning(json.dumps(log_data))
    else:
        logger.info(json.dumps(log_data))
```

### 6. Error Handling
```python
@app.errorhandler(Exception)
def handle_error(error):
    """Generic error handler - never expose internal details."""
    logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
    
    # Don't expose internal errors to users
    if app.config.get('DEBUG'):
        return jsonify({'error': str(error)}), 500
    else:
        return jsonify({'error': 'An internal error occurred'}), 500
```

## Security Checklist

### Development
- [ ] Use environment variables for secrets
- [ ] Enable debug mode only in development
- [ ] Implement proper error handling
- [ ] Add input validation and sanitization
- [ ] Use parameterized database queries

### Deployment
- [ ] Enable HTTPS/TLS
- [ ] Configure security headers
- [ ] Set up rate limiting
- [ ] Enable audit logging
- [ ] Configure firewall rules
- [ ] Use managed identities
- [ ] Regular security updates
- [ ] Implement backup strategy

### Monitoring
- [ ] Set up security alerts
- [ ] Monitor failed login attempts
- [ ] Track rate limit violations
- [ ] Review audit logs regularly
- [ ] Monitor for suspicious patterns

## Sanitized Endpoints Summary

All user-facing API endpoints that accept input have been reviewed and sanitized:

| Endpoint | Input Fields | Sanitization Applied |
|----------|--------------|---------------------|
| `POST /api/decisions` | title, context, decision, consequences | `sanitize_request_data` with schema |
| `PUT /api/decisions/:id` | title, context, decision, consequences, status, change_reason | `sanitize_request_data` with schema |
| `POST /api/auth/login` | email | `sanitize_email` |
| `POST /api/auth/send-verification` | email, name, reason | `sanitize_email`, `sanitize_name`, `sanitize_text_field` |
| `POST /api/auth/direct-signup` | email, name | `sanitize_email`, `sanitize_name` |
| `POST /api/auth/access-request` | email, name, reason | `sanitize_email`, `sanitize_name`, `sanitize_text_field` |
| `POST /api/admin/sso` | domain, provider_name, client_id, discovery_url | `sanitize_title` |
| `PUT /api/admin/sso/:id` | provider_name, client_id, discovery_url | `sanitize_title` |
| `POST/PUT /api/admin/email` | smtp_server, smtp_username, from_email, from_name | `sanitize_title`, `sanitize_email`, `sanitize_name` |
| `POST/PUT /api/admin/email/system` | smtp_server, from_email, from_name | `sanitize_title`, `sanitize_email`, `sanitize_name` |

---

*Last Updated: December 2024 (v1.4.0)*