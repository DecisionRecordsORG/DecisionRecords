# Authentication & SSO Documentation

This guide covers the comprehensive authentication system implemented in the Architecture Decisions application, including WebAuthn/Passkeys, SSO integration, and local authentication.

## Table of Contents
- [Overview](#overview)
- [Authentication Methods](#authentication-methods)
- [WebAuthn/Passkeys Implementation](#webauthnpasskeys-implementation)
- [SSO Integration](#sso-integration)
- [Slack OIDC Authentication](#slack-oidc-authentication)
- [Local Authentication](#local-authentication)
- [Multi-Tenant Authentication](#multi-tenant-authentication)
- [Security Features](#security-features)
- [API Endpoints](#api-endpoints)
- [Frontend Integration](#frontend-integration)
- [Troubleshooting](#troubleshooting)

## Overview

The Architecture Decisions application provides a multi-layered authentication system supporting:

### Authentication Types
- **WebAuthn/Passkeys**: Modern passwordless authentication
- **SSO Integration**: Support for SAML and OAuth providers
- **Slack OIDC**: "Sign in with Slack" using OpenID Connect
- **Local Authentication**: Traditional username/password with enhanced security
- **Super Admin Authentication**: Special administrative access

### Key Features
- **Multi-tenant isolation**: Domain-based authentication separation
- **CSRF Protection**: Automatic token management
- **Session management**: Secure session handling with timeout
- **Rate limiting**: Protection against brute force attacks
- **Audit logging**: Comprehensive authentication event logging

## Authentication Methods

### 1. WebAuthn/Passkeys (Primary)
Modern passwordless authentication using FIDO2/WebAuthn standards.

#### Benefits
- **Phishing resistant**: Cryptographic security tied to domain
- **No passwords**: Eliminates password-related security risks
- **Biometric support**: Fingerprint, face recognition, PIN
- **Cross-platform**: Works on desktop, mobile, and hardware tokens

### 2. SSO Integration
Enterprise SSO support for organizational authentication.

#### Supported Protocols
- **SAML 2.0**: Enterprise identity providers
- **OAuth 2.0/OpenID Connect**: Modern SSO providers
- **Active Directory**: Windows domain integration

### 3. Local Authentication
Traditional fallback authentication with enhanced security.

#### Features
- **Strong password requirements**: Enforced complexity rules
- **Account lockout**: Protection against brute force
- **Password reset**: Secure email-based reset flow
- **MFA support**: Optional two-factor authentication

## WebAuthn/Passkeys Implementation

### Backend Implementation

#### Core WebAuthn Service
```python
# webauthn_service.py
from webauthn import generate_registration_options, verify_registration_response
from webauthn import generate_authentication_options, verify_authentication_response

class WebAuthnService:
    """WebAuthn/Passkeys authentication service."""
    
    def __init__(self, app):
        self.app = app
        self.rp_id = app.config.get('WEBAUTHN_RP_ID', 'localhost')
        self.rp_name = app.config.get('WEBAUTHN_RP_NAME', 'Architecture Decisions')
        self.origin = app.config.get('WEBAUTHN_ORIGIN', 'http://localhost:4200')
    
    def generate_registration_options(self, user_id, username):
        """Generate options for passkey registration."""
        try:
            options = generate_registration_options(
                rp_id=self.rp_id,
                rp_name=self.rp_name,
                user_id=user_id.encode(),
                user_name=username,
                user_display_name=username,
                supported_pub_key_algs=[
                    {'type': 'public-key', 'alg': -7},  # ES256
                    {'type': 'public-key', 'alg': -257}  # RS256
                ]
            )
            return options
        except Exception as e:
            self.app.logger.error(f"WebAuthn registration options failed: {e}")
            raise
    
    def verify_registration(self, credential, expected_challenge, user_id):
        """Verify passkey registration response."""
        try:
            verification = verify_registration_response(
                credential=credential,
                expected_challenge=expected_challenge,
                expected_origin=self.origin,
                expected_rp_id=self.rp_id
            )
            
            if verification.verified:
                return {
                    'credential_id': verification.credential_id,
                    'credential_public_key': verification.credential_public_key,
                    'sign_count': verification.sign_count
                }
            return None
        except Exception as e:
            self.app.logger.error(f"WebAuthn registration verification failed: {e}")
            return None
```

#### Database Models
```python
# models.py
class WebAuthnCredential(db.Model):
    """Store WebAuthn credentials for users."""
    __tablename__ = 'webauthn_credentials'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    credential_id = db.Column(db.Text, nullable=False, unique=True)
    public_key = db.Column(db.LargeBinary, nullable=False)
    sign_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    name = db.Column(db.String(100))  # User-friendly name for the credential
    
    user = db.relationship('User', backref='webauthn_credentials')
    
    def to_dict(self):
        return {
            'id': self.id,
            'credential_id': self.credential_id.hex(),
            'name': self.name or 'Unnamed Passkey',
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None
        }
```

#### Registration Endpoints
```python
# app.py
@app.route('/api/webauthn/register/begin', methods=['POST'])
@login_required
def webauthn_register_begin():
    """Begin WebAuthn registration process."""
    try:
        user = get_current_user()
        
        # Generate registration options
        options = webauthn_service.generate_registration_options(
            user_id=str(user.id),
            username=user.email
        )
        
        # Store challenge in session
        session['webauthn_challenge'] = options.challenge
        session['webauthn_user_id'] = user.id
        
        return jsonify({
            'options': {
                'publicKey': {
                    'challenge': options.challenge,
                    'rp': {'id': options.rp.id, 'name': options.rp.name},
                    'user': {
                        'id': options.user.id,
                        'name': options.user.name,
                        'displayName': options.user.display_name
                    },
                    'pubKeyCredParams': options.pub_key_cred_params,
                    'timeout': options.timeout,
                    'attestation': options.attestation,
                    'authenticatorSelection': options.authenticator_selection
                }
            }
        })
    except Exception as e:
        logger.error(f"WebAuthn registration begin failed: {e}")
        return jsonify({'error': 'Registration initialization failed'}), 500

@app.route('/api/webauthn/register/complete', methods=['POST'])
@login_required
def webauthn_register_complete():
    """Complete WebAuthn registration process."""
    try:
        user = get_current_user()
        data = request.get_json()
        
        # Verify the registration
        credential_data = webauthn_service.verify_registration(
            credential=data['credential'],
            expected_challenge=session.get('webauthn_challenge'),
            user_id=session.get('webauthn_user_id')
        )
        
        if not credential_data:
            return jsonify({'error': 'Invalid credential'}), 400
        
        # Save credential to database
        credential = WebAuthnCredential(
            user_id=user.id,
            credential_id=credential_data['credential_id'].hex(),
            public_key=credential_data['credential_public_key'],
            sign_count=credential_data['sign_count'],
            name=data.get('name', 'Unnamed Passkey')
        )
        db.session.add(credential)
        db.session.commit()
        
        # Clear session
        session.pop('webauthn_challenge', None)
        session.pop('webauthn_user_id', None)
        
        return jsonify({
            'success': True,
            'credential': credential.to_dict()
        })
    except Exception as e:
        logger.error(f"WebAuthn registration complete failed: {e}")
        return jsonify({'error': 'Registration failed'}), 500
```

### Frontend Implementation

#### WebAuthn Service
```typescript
// webauthn.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class WebAuthnService {
  constructor(private http: HttpClient) {}

  async registerPasskey(name?: string): Promise<any> {
    try {
      // Begin registration
      const beginResponse = await this.http.post('/api/webauthn/register/begin', {}).toPromise();
      const options = beginResponse.options;

      // Convert base64 strings to ArrayBuffers
      options.publicKey.challenge = this.base64ToArrayBuffer(options.publicKey.challenge);
      options.publicKey.user.id = this.base64ToArrayBuffer(options.publicKey.user.id);

      // Create credential
      const credential = await navigator.credentials.create(options);
      
      // Complete registration
      const completeResponse = await this.http.post('/api/webauthn/register/complete', {
        credential: this.credentialToJSON(credential),
        name: name
      }).toPromise();

      return completeResponse;
    } catch (error) {
      console.error('Passkey registration failed:', error);
      throw error;
    }
  }

  async authenticatePasskey(): Promise<any> {
    try {
      // Begin authentication
      const beginResponse = await this.http.post('/api/webauthn/auth/begin', {}).toPromise();
      const options = beginResponse.options;

      // Convert base64 strings to ArrayBuffers
      options.publicKey.challenge = this.base64ToArrayBuffer(options.publicKey.challenge);
      options.publicKey.allowCredentials.forEach(cred => {
        cred.id = this.base64ToArrayBuffer(cred.id);
      });

      // Get assertion
      const credential = await navigator.credentials.get(options);
      
      // Complete authentication
      const completeResponse = await this.http.post('/api/webauthn/auth/complete', {
        credential: this.credentialToJSON(credential)
      }).toPromise();

      return completeResponse;
    } catch (error) {
      console.error('Passkey authentication failed:', error);
      throw error;
    }
  }

  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  }

  private credentialToJSON(credential: any): any {
    return {
      id: credential.id,
      type: credential.type,
      response: {
        clientDataJSON: this.arrayBufferToBase64(credential.response.clientDataJSON),
        attestationObject: credential.response.attestationObject ? 
          this.arrayBufferToBase64(credential.response.attestationObject) : undefined,
        authenticatorData: credential.response.authenticatorData ?
          this.arrayBufferToBase64(credential.response.authenticatorData) : undefined,
        signature: credential.response.signature ?
          this.arrayBufferToBase64(credential.response.signature) : undefined,
        userHandle: credential.response.userHandle ?
          this.arrayBufferToBase64(credential.response.userHandle) : null
      }
    };
  }

  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }
}
```

## SSO Integration

### SAML Configuration
```python
# sso.py
from authlib.integrations.flask_client import OAuth

class SSOManager:
    """Manage SSO integrations."""
    
    def __init__(self, app):
        self.app = app
        self.oauth = OAuth(app)
        self.configure_providers()
    
    def configure_providers(self):
        """Configure SSO providers from environment."""
        
        # Azure AD / Microsoft SSO
        if self.app.config.get('AZURE_CLIENT_ID'):
            self.oauth.register(
                name='azure',
                client_id=self.app.config.get('AZURE_CLIENT_ID'),
                client_secret=self.app.config.get('AZURE_CLIENT_SECRET'),
                server_metadata_url='https://login.microsoftonline.com/{}/v2.0/.well-known/openid-configuration'.format(
                    self.app.config.get('AZURE_TENANT_ID')
                ),
                client_kwargs={
                    'scope': 'openid email profile'
                }
            )
        
        # Google SSO
        if self.app.config.get('GOOGLE_CLIENT_ID'):
            self.oauth.register(
                name='google',
                client_id=self.app.config.get('GOOGLE_CLIENT_ID'),
                client_secret=self.app.config.get('GOOGLE_CLIENT_SECRET'),
                discovery_document='https://accounts.google.com/.well-known/openid-configuration',
                client_kwargs={
                    'scope': 'openid email profile'
                }
            )
```

### SSO Endpoints
```python
@app.route('/api/sso/<provider>/login')
def sso_login(provider):
    """Initiate SSO login."""
    try:
        if provider not in sso_manager.oauth._clients:
            return jsonify({'error': 'SSO provider not configured'}), 400
        
        client = sso_manager.oauth.create_client(provider)
        redirect_uri = url_for('sso_callback', provider=provider, _external=True)
        
        return client.authorize_redirect(redirect_uri)
    except Exception as e:
        logger.error(f"SSO login failed for {provider}: {e}")
        return jsonify({'error': 'SSO login failed'}), 500

@app.route('/api/sso/<provider>/callback')
def sso_callback(provider):
    """Handle SSO callback."""
    try:
        client = sso_manager.oauth.create_client(provider)
        token = client.authorize_access_token()
        user_info = token.get('userinfo')
        
        if not user_info:
            user_info = client.parse_id_token(token)
        
        # Find or create user
        email = user_info.get('email')
        if not email:
            return jsonify({'error': 'Email not provided by SSO'}), 400
        
        user = User.query.filter_by(email=email).first()
        if not user:
            # Create new user from SSO
            user = User(
                email=email,
                name=user_info.get('name', email),
                sso_provider=provider,
                sso_subject=user_info.get('sub')
            )
            db.session.add(user)
            db.session.commit()
        
        # Log the user in
        session['user_id'] = user.id
        session['authenticated'] = True
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        logger.error(f"SSO callback failed for {provider}: {e}")
        return jsonify({'error': 'SSO authentication failed'}), 500
```

## Slack OIDC Authentication

Sign in with Slack provides a frictionless authentication experience for Slack-first organizations, especially startups. Users can authenticate using their existing Slack account, with tenant assignment based on email domain.

### Overview

- **Protocol**: OpenID Connect (OIDC) via Slack
- **Scopes**: `openid profile email`
- **Tenant Assignment**: Based on email domain (e.g., sara@klarna.com → tenant "klarna.com")
- **First User Behavior**: First user from a domain becomes provisional admin

### User Flow

1. User clicks "Sign in with Slack" on the login page
2. User is redirected to Slack's authorization page
3. User authenticates with their Slack account
4. Slack redirects back with authorization code
5. Backend exchanges code for tokens and fetches user info (email, name)
6. User is created/logged in based on email domain
7. Tenant is auto-created if first user from that domain
8. Session is established and user is redirected to their tenant

### Backend Implementation

#### OIDC Endpoints (slack_security.py)
```python
# Slack OIDC Endpoints
SLACK_OIDC_AUTHORIZE_URL = 'https://slack.com/openid/connect/authorize'
SLACK_OIDC_TOKEN_URL = 'https://slack.com/api/openid.connect.token'
SLACK_OIDC_USERINFO_URL = 'https://slack.com/api/openid.connect.userInfo'
SLACK_OIDC_SCOPES = 'openid profile email'
```

#### State Parameter Management
```python
def generate_slack_oidc_state(return_url=None, extra_data=None):
    """
    Generate encrypted state for OIDC flow with CSRF protection.
    State expires after 10 minutes.
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

    fernet = Fernet(_get_encryption_key())
    return fernet.encrypt(json.dumps(state_data).encode()).decode()

def verify_slack_oidc_state(state):
    """Verify and decode state parameter. Returns None if invalid/expired."""
    # Verifies type is 'slack_oidc' and checks expiration
```

#### API Routes (app.py)
```python
# Check if Slack OIDC is enabled
GET /api/auth/slack-oidc-status
# Returns: {"enabled": true/false, "reason": "..."}

# Initiate OIDC flow
GET /auth/slack/oidc
# Redirects to Slack authorization URL

# Handle callback
GET /auth/slack/oidc/callback
# Exchanges code for token, creates/logs in user
```

### Configuration

#### Global Configuration
Slack OIDC is automatically enabled when Slack credentials are configured:
- `slack-client-id` in Azure Key Vault
- `slack-client-secret` in Azure Key Vault

#### Tenant Configuration (TenantSettings)
Tenant admins can control Slack OIDC availability:

```python
# TenantSettings model
allow_slack_oidc = db.Column(db.Boolean, default=True)  # Enable/disable for tenant
auth_method = db.Column(db.String(20), default='local')  # Can be 'slack_oidc'
```

#### Auth Method Options
| Value | Description |
|-------|-------------|
| `local` | Password and passkey authentication |
| `sso` | Enterprise SSO only |
| `webauthn` | Passkeys only |
| `slack_oidc` | Slack sign-in only (SSO alternative) |

When `auth_method='slack_oidc'`, only Slack sign-in is allowed for the tenant. This provides SSO-like control without configuring a separate identity provider.

### Frontend Integration

#### Sign-in Button Components
The "Sign in with Slack" button appears on:
- Homepage (email entry view)
- Tenant login page
- Slack account linking page (for users not logged in)

#### Button Implementation
```typescript
// Check if Slack OIDC is enabled
ngOnInit() {
  this.checkSlackOidcStatus();
}

checkSlackOidcStatus(): void {
  this.http.get<{enabled: boolean}>('/api/auth/slack-oidc-status')
    .subscribe({
      next: (status) => {
        this.slackOidcEnabled = status.enabled;
      }
    });
}

signInWithSlack(): void {
  window.location.href = '/auth/slack/oidc';
}
```

#### Admin Settings
Tenant admins can configure Slack OIDC in Settings > Auth Configuration:
- Radio button: "Sign in with Slack Only" (`auth_method='slack_oidc'`)
- Toggle: "Allow Sign in with Slack" (`allow_slack_oidc`)

### Security Considerations

1. **State Parameter**: Encrypted with Fernet, includes CSRF token, expires in 10 minutes
2. **Domain Blocking**: Public email domains (gmail.com, yahoo.com, etc.) are rejected
3. **Rate Limiting**: Callback endpoint is rate-limited (20/min)
4. **Token Handling**: Access tokens used momentarily for user info, not stored
5. **Existing Infrastructure**: Reuses proven Slack OAuth encryption from workspace integration

### Blocked Email Domains
The following public email domains are blocked to ensure enterprise-only usage:
- gmail.com
- yahoo.com
- hotmail.com
- outlook.com
- aol.com
- icloud.com
- protonmail.com
- mail.com
- live.com
- msn.com

### Use Cases

#### Startup Onboarding
1. IT admin installs Slack app for their workspace
2. Team members can immediately sign in with Slack
3. First user becomes provisional admin
4. No SSO configuration required

#### Enterprise Slack-Only Mode
1. Admin sets `auth_method='slack_oidc'` for tenant
2. All users must authenticate via Slack
3. When employees leave Slack workspace, they lose Decision Records access
4. Provides SSO-like security without separate IdP configuration

### Testing

#### Backend Tests
```bash
# Run Slack OIDC unit tests
python -m pytest tests/test_slack_oidc.py -v
```

Tests cover:
- State generation and verification
- Expired state rejection
- OIDC status endpoint
- Callback handling
- User creation flow
- Blocked domain rejection

#### E2E Tests
```bash
# Run Slack OIDC E2E tests
npx playwright test e2e/tests/slack-oidc.spec.ts
```

Tests cover:
- Button visibility based on configuration
- Redirect to OIDC endpoint
- Admin settings for auth method
- Tenant-level enable/disable

### Rollback

To disable Slack OIDC:
1. Remove Slack credentials from Key Vault, OR
2. Set `allow_slack_oidc=False` on tenant settings

Users who signed up via Slack OIDC can still use other authentication methods (password, passkey, SSO) if configured.

## Local Authentication

### Password Security
```python
# auth.py
import bcrypt
import re

class PasswordPolicy:
    """Enforce strong password requirements."""
    
    MIN_LENGTH = 12
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_NUMBERS = True
    REQUIRE_SPECIAL = True
    
    @classmethod
    def validate_password(cls, password):
        """Validate password against policy."""
        errors = []
        
        if len(password) < cls.MIN_LENGTH:
            errors.append(f'Password must be at least {cls.MIN_LENGTH} characters long')
        
        if cls.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter')
        
        if cls.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            errors.append('Password must contain at least one lowercase letter')
        
        if cls.REQUIRE_NUMBERS and not re.search(r'\d', password):
            errors.append('Password must contain at least one number')
        
        if cls.REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append('Password must contain at least one special character')
        
        return errors

def hash_password(password):
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt)

def verify_password(password, hashed):
    """Verify password against hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed)
```

### Login Rate Limiting
```python
# security.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Local authentication login with rate limiting."""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Find user
        user = User.query.filter_by(email=email).first()
        if not user or not verify_password(password, user.password_hash):
            # Log failed attempt
            logger.warning(f"Failed login attempt for {email} from {request.remote_addr}")
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            return jsonify({'error': 'Account temporarily locked'}), 423
        
        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Create session
        session['user_id'] = user.id
        session['authenticated'] = True
        
        return jsonify({
            'success': True,
            'user': user.to_dict(),
            'csrf_token': generate_csrf_token()
        })
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return jsonify({'error': 'Login failed'}), 500
```

## Multi-Tenant Authentication

### Tenant Context Management
```python
# tenant.py
from flask import g

class TenantContext:
    """Manage multi-tenant context."""
    
    @staticmethod
    def get_current_tenant():
        """Get current tenant from request context."""
        return getattr(g, 'current_tenant', None)
    
    @staticmethod
    def set_current_tenant(tenant):
        """Set current tenant in request context."""
        g.current_tenant = tenant
    
    @staticmethod
    def require_tenant():
        """Decorator to require tenant context."""
        def decorator(f):
            @functools.wraps(f)
            def decorated_function(*args, **kwargs):
                tenant = TenantContext.get_current_tenant()
                if not tenant:
                    return jsonify({'error': 'Tenant context required'}), 400
                return f(*args, **kwargs)
            return decorated_function
        return decorator

@app.before_request
def load_tenant_context():
    """Load tenant context from domain or header."""
    try:
        # Try to get tenant from subdomain
        host = request.headers.get('Host', '')
        if '.' in host:
            subdomain = host.split('.')[0]
            if subdomain != 'www':
                tenant = Tenant.query.filter_by(domain=subdomain).first()
                if tenant:
                    TenantContext.set_current_tenant(tenant.domain)
                    return
        
        # Try to get tenant from custom header
        tenant_header = request.headers.get('X-Tenant-Domain')
        if tenant_header:
            tenant = Tenant.query.filter_by(domain=tenant_header).first()
            if tenant:
                TenantContext.set_current_tenant(tenant.domain)
    except Exception as e:
        logger.error(f"Failed to load tenant context: {e}")
```

## Security Features

### CSRF Protection
```python
# csrf.py
import secrets
from functools import wraps

def generate_csrf_token():
    """Generate CSRF token."""
    token = secrets.token_urlsafe(32)
    session['csrf_token'] = token
    return token

def validate_csrf_token(token):
    """Validate CSRF token."""
    return token and token == session.get('csrf_token')

def csrf_required(f):
    """Decorator to require CSRF token."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            token = request.headers.get('X-CSRF-Token')
            if not validate_csrf_token(token):
                return jsonify({'error': 'Invalid CSRF token'}), 403
        return f(*args, **kwargs)
    return decorated_function
```

### Session Management
```python
# sessions.py
from datetime import datetime, timedelta

@app.before_request
def check_session_timeout():
    """Check for session timeout."""
    if 'user_id' in session:
        last_activity = session.get('last_activity')
        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            timeout_duration = timedelta(hours=24)  # 24 hour timeout
            
            if datetime.utcnow() - last_activity > timeout_duration:
                session.clear()
                return jsonify({'error': 'Session expired'}), 401
        
        # Update last activity
        session['last_activity'] = datetime.utcnow().isoformat()
```

## API Endpoints

### Authentication Routes
```python
# Authentication endpoints summary

# Local Authentication
POST /api/auth/login              # Local login
POST /api/auth/logout             # Logout
POST /api/auth/register           # User registration
POST /api/auth/password/reset     # Password reset request
POST /api/auth/password/confirm   # Password reset confirmation

# WebAuthn/Passkeys
POST /api/webauthn/register/begin    # Start passkey registration
POST /api/webauthn/register/complete # Complete passkey registration
POST /api/webauthn/auth/begin        # Start passkey authentication
POST /api/webauthn/auth/complete     # Complete passkey authentication
GET  /api/webauthn/credentials       # List user's passkeys
DELETE /api/webauthn/credentials/:id # Delete passkey

# SSO
GET  /api/sso/:provider/login     # Initiate SSO login
GET  /api/sso/:provider/callback  # SSO callback
GET  /api/sso/providers           # List available SSO providers

# Slack OIDC
GET  /api/auth/slack-oidc-status  # Check if Slack OIDC is enabled
GET  /auth/slack/oidc             # Initiate Slack OIDC login
GET  /auth/slack/oidc/callback    # Handle Slack OIDC callback

# Session Management
GET  /api/auth/me                 # Get current user
POST /api/auth/refresh            # Refresh session
GET  /api/auth/csrf               # Get CSRF token
```

## Frontend Integration

### Authentication Guard
```typescript
// auth.guard.ts
import { Injectable } from '@angular/core';
import { CanActivate, Router } from '@angular/router';
import { AuthService } from './auth.service';

@Injectable({
  providedIn: 'root'
})
export class AuthGuard implements CanActivate {
  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  async canActivate(): Promise<boolean> {
    try {
      const isAuthenticated = await this.authService.checkAuth();
      if (!isAuthenticated) {
        this.router.navigate(['/login']);
        return false;
      }
      return true;
    } catch (error) {
      this.router.navigate(['/login']);
      return false;
    }
  }
}
```

### Authentication Service
```typescript
// auth.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private currentUserSubject = new BehaviorSubject<any>(null);
  public currentUser = this.currentUserSubject.asObservable();

  constructor(private http: HttpClient) {
    this.loadCurrentUser();
  }

  async login(email: string, password: string): Promise<any> {
    const response = await this.http.post('/api/auth/login', {
      email,
      password
    }).toPromise();
    
    this.currentUserSubject.next(response.user);
    return response;
  }

  async loginWithPasskey(): Promise<any> {
    const response = await this.webAuthnService.authenticatePasskey();
    this.currentUserSubject.next(response.user);
    return response;
  }

  async logout(): Promise<void> {
    await this.http.post('/api/auth/logout', {}).toPromise();
    this.currentUserSubject.next(null);
  }

  async checkAuth(): Promise<boolean> {
    try {
      const response = await this.http.get('/api/auth/me').toPromise();
      this.currentUserSubject.next(response.user);
      return true;
    } catch (error) {
      this.currentUserSubject.next(null);
      return false;
    }
  }

  private loadCurrentUser(): void {
    this.checkAuth();
  }
}
```

## Troubleshooting

### Common Issues

#### 1. WebAuthn Registration Fails
**Symptoms**: Browser shows "NotSupportedError" or "SecurityError"

**Causes**:
- HTTPS required in production
- Invalid origin configuration
- User agent doesn't support WebAuthn

**Solutions**:
```bash
# Check WebAuthn configuration
curl -X GET https://your-domain.com/.well-known/webauthn

# Verify HTTPS is enabled
curl -I https://your-domain.com/

# Check browser compatibility
# WebAuthn requires secure context (HTTPS or localhost)
```

#### 2. SSO Configuration Issues
**Symptoms**: "SSO provider not configured" error

**Solutions**:
```bash
# Verify environment variables
echo $AZURE_CLIENT_ID
echo $AZURE_CLIENT_SECRET
echo $AZURE_TENANT_ID

# Check SSO provider registration
curl -X GET https://your-domain.com/api/sso/providers
```

#### 3. Session Timeouts
**Symptoms**: Users logged out unexpectedly

**Configuration**:
```python
# Adjust session timeout in app.py
SESSION_TIMEOUT_HOURS = 24  # Default 24 hours
SESSION_PERMANENT = True
PERMANENT_SESSION_LIFETIME = timedelta(hours=SESSION_TIMEOUT_HOURS)
```

#### 4. CSRF Token Issues
**Symptoms**: "Invalid CSRF token" errors

**Solutions**:
```typescript
// Ensure CSRF interceptor is configured
// Check that X-CSRF-Token header is being sent
// Verify token is refreshed on page reload
```

### Debugging Steps

#### 1. Check Authentication Logs
```bash
# View authentication logs
az container logs --resource-group adr-resources-eu --name adr-app-eu | grep -i auth

# Look for failed login attempts
grep "Failed login attempt" /var/log/app.log
```

#### 2. Verify Database State
```python
# Check user authentication methods
user = User.query.filter_by(email='user@example.com').first()
print(f"WebAuthn credentials: {len(user.webauthn_credentials)}")
print(f"SSO provider: {user.sso_provider}")
print(f"Local auth enabled: {bool(user.password_hash)}")
```

#### 3. Test API Endpoints
```bash
# Test login endpoint
curl -X POST https://your-domain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'

# Test WebAuthn registration
curl -X POST https://your-domain.com/api/webauthn/register/begin \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Security Monitoring

#### 1. Failed Login Monitoring
```python
# Monitor failed login attempts
@app.after_request
def log_failed_auth(response):
    if request.endpoint in ['login', 'webauthn_auth_complete'] and response.status_code == 401:
        logger.warning(f"Failed auth attempt from {request.remote_addr} to {request.endpoint}")
    return response
```

#### 2. Session Monitoring
```python
# Track active sessions
@app.before_request
def monitor_sessions():
    if 'user_id' in session:
        user_id = session['user_id']
        # Log session activity for monitoring
        logger.info(f"Active session for user {user_id} from {request.remote_addr}")
```

## Best Practices

### 1. Security
- Always use HTTPS in production
- Implement proper session timeout
- Monitor authentication failures
- Regular security audits
- Keep WebAuthn libraries updated

### 2. User Experience
- Provide clear error messages
- Support multiple authentication methods
- Implement graceful fallbacks
- Test across different browsers/devices

### 3. Deployment
- Secure environment variable management
- Regular backup of authentication data
- Monitor authentication metrics
- Implement proper logging

---

 The "Sign in with Google" feature has been successfully deployed to production at https://decisionrecords.org.

  Summary of Changes:

  | Component               | Changes                                                |
  |-------------------------|--------------------------------------------------------|
  | google_oauth.py         | New OAuth module with state management, token exchange |
  | app.py                  | Added 3 routes + database migration                    |
  | models.py               | Added allow_google_oauth field                         |
  | Frontend (4 components) | Google sign-in buttons with brand styling              |
  | Tests                   | 32 backend tests + E2E tests                           |

  Important: To Enable Google OAuth

  The feature is deployed but will show as disabled until you add Google credentials to Azure Key Vault:

  # 1. Create OAuth credentials in Google Cloud Console
  #    - Go to https://console.cloud.google.com
  #    - Create a new project or select existing
  #    - Enable Google+ API
  #    - Create OAuth 2.0 credentials (Web application)
  #    - Add callback URL: https://decisionrecords.org/auth/google/callback

  # 2. Add credentials to Key Vault
  az keyvault secret set \
    --vault-name adr-keyvault-eu \
    --name "google-client-id" \
    --value "your-client-id.apps.googleusercontent.com"

  az keyvault secret set \
    --vault-name adr-keyvault-eu \
    --name "google-client-secret" \
    --value "your-client-secret"

  Once the credentials are added, the "Sign in with Google" button will appear on login pages. Note that Gmail and other public email domains are blocked - only
  Google Workspace accounts with corporate domains can sign in.

*Last Updated: December 2025*