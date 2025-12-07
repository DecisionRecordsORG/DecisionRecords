import os
import json
import secrets
import logging
import sys
import traceback
import psycopg2
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g, send_from_directory
from authlib.integrations.requests_client import OAuth2Session
from models import db, User, MasterAccount, SSOConfig, EmailConfig, Subscription, ArchitectureDecision, DecisionHistory, AuthConfig, WebAuthnCredential, AccessRequest, EmailVerification, ITInfrastructure, SystemConfig, DomainApproval, save_history
from datetime import datetime, timedelta
from auth import login_required, admin_required, get_current_user, get_or_create_user, get_oidc_config, extract_domain_from_email, is_master_account, authenticate_master, master_required
from notifications import notify_subscribers_new_decision, notify_subscribers_decision_updated
from webauthn_auth import (
    create_registration_options, verify_registration,
    create_authentication_options, verify_authentication,
    get_user_credentials, delete_credential, get_auth_config
)
from security import (
    validate_tenant_ownership, filter_by_tenant, log_security_event,
    generate_csrf_token, apply_security_headers,
    sanitize_title, sanitize_text_field, sanitize_name, sanitize_email,
    sanitize_request_data
)
from keyvault_client import keyvault_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Determine if we're serving Angular frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist', 'frontend', 'browser')
SERVE_ANGULAR = os.path.exists(FRONTEND_DIR)

app = Flask(__name__, static_folder=FRONTEND_DIR if SERVE_ANGULAR else 'static')

# Global error state
app_error_state = {
    'healthy': False,
    'error': None,
    'details': None
}

# ==================== Secure Configuration via Azure Key Vault ====================
# Priority: Key Vault -> Environment Variable -> Default
# This ensures secrets are never hardcoded and can be rotated without redeployment

# Database URL (Key Vault or environment variable)
database_url = keyvault_client.get_database_url()
logger.info(f"Database URL configured: {database_url.split('@')[1] if '@' in database_url else database_url}")
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SECRET_KEY for session signing (Key Vault or environment variable)
# This MUST be persistent across restarts for sessions to remain valid
secret_key = keyvault_client.get_flask_secret_key()
if secret_key:
    logger.info("SECRET_KEY loaded from Key Vault or environment variable")
    app.config['SECRET_KEY'] = secret_key
else:
    # Generate random key - sessions will NOT persist across restarts
    logger.warning("SECRET_KEY not found in Key Vault or environment. Using random key - sessions will not persist across restarts!")
    app.config['SECRET_KEY'] = secrets.token_hex(32)

# ==================== Security Configuration ====================

# Session security settings
# SESSION_COOKIE_SECURE should only be True when using HTTPS
# Check for explicit HTTPS environment variable, or if behind HTTPS-terminating proxy
_use_https = os.environ.get('USE_HTTPS', 'false').lower() == 'true'
app.config['SESSION_COOKIE_SECURE'] = _use_https
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to session cookie
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection - prevent cross-site cookie sending
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Session expiry

# Rate limiting configuration
app.config['RATELIMIT_ENABLED'] = True
app.config['RATELIMIT_STORAGE_URL'] = os.environ.get('REDIS_URL', 'memory://')
app.config['RATELIMIT_DEFAULT'] = '200 per minute'  # Default rate limit
app.config['RATELIMIT_HEADERS_ENABLED'] = True  # Include rate limit info in response headers

# Initialize rate limiter (if available)
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per minute"],
        storage_uri=app.config['RATELIMIT_STORAGE_URL'],
    )
    RATE_LIMITING_ENABLED = True
    logger.info("Rate limiting enabled")
except ImportError:
    limiter = None
    RATE_LIMITING_ENABLED = False
    logger.warning("Flask-Limiter not installed, rate limiting disabled")

# Initialize Flask-Talisman for CSP (Content Security Policy)
try:
    from flask_talisman import Talisman

    # CSP configuration for Angular SPA with Material UI
    # Note: Angular Material uses inline event handlers (onload) for stylesheet loading
    # which requires 'unsafe-inline' in script-src. We cannot use nonces with this.
    csp = {
        'default-src': "'self'",
        # Angular production build and Material require:
        # - 'unsafe-inline': for Angular Material's stylesheet onload handlers
        # - 'unsafe-eval': only needed for dev; can be removed in strict production
        'script-src': ["'self'", "'unsafe-inline'"],
        'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        'font-src': ["'self'", "https://fonts.gstatic.com"],
        'img-src': ["'self'", "data:", "https:"],
        'connect-src': ["'self'"],  # API calls - restrict to same origin
        'frame-ancestors': "'none'",  # Prevent clickjacking
        'form-action': "'self'",
        'base-uri': "'self'",
        'object-src': "'none'",
    }

    # Enable Talisman with CSP
    # Note: force_https is handled by Azure App Gateway, so we disable it here
    # Note: We do NOT use content_security_policy_nonce_in because Angular Material
    #       uses inline event handlers that are incompatible with nonce-based CSP
    talisman = Talisman(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=[],  # Disabled - incompatible with Angular Material
        force_https=False,  # Azure handles HTTPS termination
        session_cookie_secure=_use_https,  # Only secure cookies over HTTPS
        frame_options='DENY',
        x_content_type_options=True,
        x_xss_protection=True,
        referrer_policy='strict-origin-when-cross-origin',
    )
    CSP_ENABLED = True
    logger.info("Content Security Policy (CSP) enabled via Flask-Talisman")
except ImportError:
    talisman = None
    CSP_ENABLED = False
    logger.warning("Flask-Talisman not installed, CSP disabled")

# Initialize database
db.init_app(app)

# Database initialization flag
_db_initialized = False

def init_database():
    """Initialize database tables and master account on first request"""
    global _db_initialized, app_error_state
    if not _db_initialized:
        try:
            logger.info("Attempting to initialize database...")
            with app.app_context():
                # Test database connection first using psycopg2 directly
                database_url = app.config['SQLALCHEMY_DATABASE_URI']
                logger.info(f"Testing database connection...")
                
                # Parse the DATABASE_URL to extract connection parameters
                # Format: postgresql://user:password@host:port/dbname?sslmode=require
                if database_url.startswith('postgresql://'):
                    url_parts = database_url.replace('postgresql://', '').split('/')
                    auth_host = url_parts[0]
                    db_name = url_parts[1].split('?')[0] if '?' in url_parts[1] else url_parts[1]
                    
                    user_pass, host_port = auth_host.split('@')
                    user, password = user_pass.split(':')
                    host = host_port.split(':')[0] if ':' in host_port else host_port
                    port = int(host_port.split(':')[1]) if ':' in host_port else 5432
                    
                    # Use psycopg2 connection as per Azure documentation
                    conn = psycopg2.connect(
                        user=user,
                        password=password,
                        host=host,
                        port=port,
                        database=db_name,
                        sslmode='require'
                    )
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    conn.close()
                    logger.info("Database connection successful using psycopg2")
                else:
                    # Fallback to SQLAlchemy if URL format is different
                    with db.engine.connect() as connection:
                        connection.execute(db.text("SELECT 1"))
                    logger.info("Database connection successful using SQLAlchemy")
                
                # Create tables
                logger.info("Creating database tables...")
                db.create_all()
                logger.info("Database tables created")

                # Create default master account
                logger.info("Creating default master account...")
                MasterAccount.create_default_master(db.session)
                logger.info("Default master account created")

                # Initialize default system config if not exists in a separate transaction
                logger.info("Checking system configuration...")
                try:
                    if not SystemConfig.query.filter_by(key=SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED).first():
                        logger.info("Creating default system config...")
                        # Use a manual approach to avoid transaction issues
                        config = SystemConfig(
                            key=SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED,
                            value='true',
                            description='Require email verification for new user signups'
                        )
                        db.session.add(config)
                        db.session.commit()
                        logger.info("Default system config initialized")
                    else:
                        logger.info("System config already exists")
                except Exception as config_error:
                    logger.warning(f"System config initialization failed (non-critical): {str(config_error)}")
                    # Don't fail the entire initialization for this
                    db.session.rollback()
                
                _db_initialized = True
                app_error_state['healthy'] = True
                app_error_state['error'] = None
                app_error_state['details'] = None
                logger.info("Database initialization completed successfully")
                
        except Exception as e:
            error_msg = f"Database initialization failed: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            app_error_state['healthy'] = False
            app_error_state['error'] = error_msg
            app_error_state['details'] = traceback.format_exc()
            # Don't raise - let the app run but in error state

@app.before_request
def initialize_db():
    """Initialize database before handling requests"""
    # Initialize database for any request except static files
    if not _db_initialized and not (request.endpoint and request.endpoint.startswith('static')):
        try:
            init_database()
        except Exception as e:
            logger.error(f"Critical error during database initialization: {str(e)}")
            logger.error(traceback.format_exc())
            # Don't crash - just mark as unhealthy
            app_error_state['healthy'] = False
            app_error_state['error'] = f"Critical database error: {str(e)}"
            app_error_state['details'] = traceback.format_exc()


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    # Apply security headers
    response = apply_security_headers(response)

    # Add CSRF token to response header for SPA to use
    if 'user_id' in session or 'master_id' in session:
        response.headers['X-CSRF-Token'] = generate_csrf_token()

    # Remove server identification headers (security best practice)
    response.headers.pop('Server', None)

    return response


# ==================== Health Check ====================

@app.route('/health')
def health_check():
    """Health check endpoint that reports application status"""
    if app_error_state['healthy']:
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    else:
        return jsonify({
            'status': 'unhealthy',
            'error': app_error_state['error'],
            'details': app_error_state['details'],
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@app.route('/ping')
def ping():
    """Simple ping endpoint for load balancer health checks - always returns 200"""
    return jsonify({
        'status': 'ok',
        'server': 'running',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/api/version')
def get_version():
    """Get application version information."""
    from version import get_build_info
    return jsonify(get_build_info()), 200

# ==================== Context Processor ====================

@app.context_processor
def inject_user():
    """Make current user available in all templates."""
    return {
        'current_user': get_current_user(),
        'is_master': is_master_account()
    }


# ==================== Auth Routes ====================

@app.route('/login')
def login():
    """Legacy login route - redirect to Angular landing page."""
    return redirect('/')


# Rate limit decorator helper (no-op if limiter not available)
def rate_limit(limit_string):
    """Apply rate limiting if available, otherwise no-op."""
    def decorator(f):
        if RATE_LIMITING_ENABLED and limiter:
            return limiter.limit(limit_string)(f)
        return f
    return decorator


@app.route('/auth/local', methods=['POST'])
@rate_limit("5 per minute")  # Strict limit on login attempts
def local_login():
    """Handle local master account login."""
    # Log login attempt for security auditing
    log_security_event('auth', f"Master login attempt for user", severity='INFO')

    # Support both form data and JSON
    if request.is_json:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
    else:
        username = request.form.get('username')
        password = request.form.get('password')

    if not username or not password:
        if request.is_json:
            return jsonify({'error': 'Username and password are required'}), 400
        return render_template('login.html',
                             sso_configs=SSOConfig.query.filter_by(enabled=True).all(),
                             error='Username and password are required')

    master = authenticate_master(username, password)
    if master:
        session['master_id'] = master.id
        session['is_master'] = True
        session.permanent = True
        if request.is_json:
            return jsonify({'message': 'Login successful'}), 200
        return redirect(url_for('index'))
    else:
        if request.is_json:
            return jsonify({'error': 'Invalid username or password'}), 401
        return render_template('login.html',
                             sso_configs=SSOConfig.query.filter_by(enabled=True).all(),
                             error='Invalid username or password')


@app.route('/api/auth/sso-configs', methods=['GET'])
def api_get_sso_configs():
    """Get available SSO configurations for login page."""
    configs = SSOConfig.query.filter_by(enabled=True).all()
    return jsonify([{
        'id': c.id,
        'domain': c.domain,
        'provider_name': c.provider_name,
        'enabled': c.enabled
    } for c in configs])


@app.route('/api/auth/login', methods=['POST'])
@rate_limit("10 per minute")  # Limit login attempts per IP
def api_tenant_login():
    """Handle tenant user password login."""
    log_security_event('auth', f"Tenant login attempt", severity='INFO')

    data = request.get_json()
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user.has_password():
        return jsonify({
            'error': 'No password set for this account',
            'has_passkey': len(user.webauthn_credentials) > 0
        }), 401

    if not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401

    # Login successful
    session['user_id'] = user.id
    user.last_login = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'redirect': f'/{user.sso_domain}'
    })


@app.route('/api/auth/set-password', methods=['POST'])
@login_required
def api_set_password():
    """Set or update password for current user."""
    data = request.get_json()
    password = data.get('password', '')
    current_password = data.get('current_password', '')

    if not password or len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    user = g.current_user
    if isinstance(user, MasterAccount):
        return jsonify({'error': 'Use the master password change endpoint'}), 400

    # If user already has a password, require current password
    if user.has_password():
        if not current_password:
            return jsonify({'error': 'Current password is required'}), 400
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401

    user.set_password(password)
    db.session.commit()

    return jsonify({'message': 'Password updated successfully'})


@app.route('/auth/sso/<int:config_id>')
def sso_login(config_id):
    """Initiate SSO login flow."""
    sso_config = SSOConfig.query.get_or_404(config_id)

    if not sso_config.enabled:
        return redirect('/')

    # Get OIDC configuration
    oidc_config = get_oidc_config(sso_config.discovery_url)
    if not oidc_config:
        return render_template('error.html', message='Failed to connect to SSO provider'), 500

    # Store config in session for callback
    session['sso_config_id'] = config_id
    session['oauth_state'] = secrets.token_urlsafe(32)

    # Create authorization URL
    client = OAuth2Session(
        client_id=sso_config.client_id,
        client_secret=sso_config.client_secret,
        redirect_uri=url_for('sso_callback', _external=True)
    )

    authorization_url, state = client.create_authorization_url(
        oidc_config['authorization_endpoint'],
        state=session['oauth_state'],
        scope='openid email profile'
    )

    return redirect(authorization_url)


@app.route('/auth/callback')
def sso_callback():
    """Handle SSO callback."""
    config_id = session.pop('sso_config_id', None)
    stored_state = session.pop('oauth_state', None)

    if not config_id:
        return redirect('/')

    sso_config = SSOConfig.query.get(config_id)
    if not sso_config:
        return redirect('/')

    # Get OIDC configuration
    oidc_config = get_oidc_config(sso_config.discovery_url)
    if not oidc_config:
        return render_template('error.html', message='Failed to connect to SSO provider'), 500

    # Exchange code for token
    client = OAuth2Session(
        client_id=sso_config.client_id,
        client_secret=sso_config.client_secret,
        redirect_uri=url_for('sso_callback', _external=True),
        state=stored_state
    )

    try:
        token = client.fetch_token(
            oidc_config['token_endpoint'],
            authorization_response=request.url
        )

        # Get user info
        userinfo_response = client.get(oidc_config['userinfo_endpoint'])
        userinfo = userinfo_response.json()

        email = userinfo.get('email')
        name = userinfo.get('name') or userinfo.get('preferred_username')
        subject = userinfo.get('sub')

        if not email:
            return render_template('error.html', message='Email not provided by SSO provider'), 400

        # Verify email domain matches SSO config domain
        email_domain = extract_domain_from_email(email)
        if email_domain != sso_config.domain.lower():
            return render_template('error.html', message='Email domain does not match SSO configuration'), 403

        # Get or create user
        user = get_or_create_user(email, name, subject, sso_config.domain)

        # Set session
        session['user_id'] = user.id
        session.permanent = True

        return redirect(url_for('index'))

    except Exception as e:
        app.logger.error(f"SSO callback error: {e}")
        return render_template('error.html', message='Authentication failed'), 500


@app.route('/logout')
def logout():
    """Log out the current user."""
    session.clear()
    return redirect('/')


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """API endpoint for logout - returns JSON instead of redirect."""
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/auth/csrf-token', methods=['GET'])
def api_get_csrf_token():
    """Get a CSRF token for the current session.

    The frontend should call this endpoint and include the token
    in the X-CSRF-Token header for all state-changing requests.
    """
    token = generate_csrf_token()
    return jsonify({'csrf_token': token})


# ==================== Web Routes (Legacy - only when not serving Angular) ====================

if not SERVE_ANGULAR:
    @app.route('/')
    @login_required
    def index():
        """Home page - list all architecture decisions."""
        # Check if app is healthy
        if not app_error_state['healthy']:
            # Return error page if database is not working
            return f"""
            <html>
                <head><title>Application Error</title></head>
                <body style='font-family: Arial, sans-serif; padding: 20px;'>
                    <h1 style='color: red;'>Application Error</h1>
                    <h2>Database Connection Failed</h2>
                    <p><strong>Error:</strong> {app_error_state['error']}</p>
                    <h3>Details:</h3>
                    <pre style='background: #f0f0f0; padding: 15px; overflow-x: auto;'>{app_error_state['details']}</pre>
                    <hr>
                    <p><small>Please contact your administrator to resolve this issue.</small></p>
                </body>
            </html>
            """, 503
        return render_template('index.html')


    @app.route('/decision/<int:decision_id>')
    @login_required
    def view_decision(decision_id):
        """View a single architecture decision."""
        return render_template('decision.html', decision_id=decision_id)


    @app.route('/decision/new')
    @login_required
    def new_decision():
        """Create a new architecture decision."""
        return render_template('decision.html', decision_id=None)


    @app.route('/settings')
    @admin_required
    def settings():
        """Settings page for SSO and email configuration."""
        return render_template('settings.html')


    @app.route('/profile')
    @login_required
    def profile():
        """User profile and subscription settings."""
        if is_master_account():
            return redirect(url_for('master_profile'))
        return render_template('profile.html')


    @app.route('/master/profile')
    @master_required
    def master_profile():
        """Master account profile page."""
        return render_template('master_profile.html')


# ==================== API Routes - Decisions ====================

@app.route('/api/decisions', methods=['GET'])
@login_required
def api_list_decisions():
    """List all architecture decisions for the user's domain."""
    if is_master_account():
        # Master accounts can see all decisions across all domains
        decisions = ArchitectureDecision.query.filter_by(
            deleted_at=None
        ).order_by(ArchitectureDecision.id.desc()).all()
    else:
        decisions = ArchitectureDecision.query.filter_by(
            domain=g.current_user.sso_domain,
            deleted_at=None
        ).order_by(ArchitectureDecision.id.desc()).all()
    return jsonify([d.to_dict() for d in decisions])


@app.route('/api/decisions', methods=['POST'])
@login_required
def api_create_decision():
    """Create a new architecture decision."""
    # Master accounts cannot create decisions (they don't belong to any domain)
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot create decisions. Please log in with an SSO account.'}), 403

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Sanitize and validate input
    sanitized, errors = sanitize_request_data(data, {
        'title': {'type': 'title', 'max_length': 255, 'required': True},
        'context': {'type': 'text', 'max_length': 50000, 'required': True},
        'decision': {'type': 'text', 'max_length': 50000, 'required': True},
        'consequences': {'type': 'text', 'max_length': 50000, 'required': True},
        'status': {'type': 'string', 'max_length': 50},
        'change_reason': {'type': 'text', 'max_length': 500},
    })

    if errors:
        return jsonify({'error': errors[0]}), 400

    # Validate status if provided
    status = sanitized.get('status', 'proposed')
    if status not in ArchitectureDecision.VALID_STATUSES:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(ArchitectureDecision.VALID_STATUSES)}'}), 400

    decision = ArchitectureDecision(
        title=sanitized['title'],
        context=sanitized['context'],
        decision=sanitized['decision'],
        status=status,
        consequences=sanitized['consequences'],
        domain=g.current_user.sso_domain,  # SECURITY: Always use authenticated user's domain
        created_by_id=g.current_user.id,
        updated_by_id=g.current_user.id
    )

    # Handle infrastructure associations
    infrastructure_ids = data.get('infrastructure_ids', [])
    if infrastructure_ids:
        infrastructure_items = ITInfrastructure.query.filter(
            ITInfrastructure.id.in_(infrastructure_ids),
            ITInfrastructure.domain == g.current_user.sso_domain
        ).all()
        decision.infrastructure = infrastructure_items

    db.session.add(decision)
    db.session.commit()

    # Send notifications
    email_config = EmailConfig.query.filter_by(domain=g.current_user.sso_domain, enabled=True).first()
    notify_subscribers_new_decision(db, decision, email_config)

    return jsonify(decision.to_dict()), 201


@app.route('/api/decisions/<int:decision_id>', methods=['GET'])
@login_required
def api_get_decision(decision_id):
    """Get a single architecture decision with its history."""
    if is_master_account():
        # Master accounts can see any decision
        decision = ArchitectureDecision.query.filter_by(
            id=decision_id,
            deleted_at=None
        ).first_or_404()
    else:
        decision = ArchitectureDecision.query.filter_by(
            id=decision_id,
            domain=g.current_user.sso_domain,
            deleted_at=None
        ).first_or_404()
    return jsonify(decision.to_dict_with_history())


@app.route('/api/decisions/<int:decision_id>', methods=['PUT'])
@login_required
def api_update_decision(decision_id):
    """Update an architecture decision."""
    # Master accounts cannot update decisions
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot modify decisions. Please log in with an SSO account.'}), 403

    decision = ArchitectureDecision.query.filter_by(
        id=decision_id,
        domain=g.current_user.sso_domain,
        deleted_at=None
    ).first_or_404()

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate status if provided
    if 'status' in data and data['status'] not in ArchitectureDecision.VALID_STATUSES:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(ArchitectureDecision.VALID_STATUSES)}'}), 400

    # Check if there are actual changes
    has_changes = False
    status_changed = False
    old_status = decision.status

    for field in ['title', 'context', 'decision', 'status', 'consequences']:
        if field in data and data[field] != getattr(decision, field):
            has_changes = True
            if field == 'status':
                status_changed = True
            break

    if not has_changes:
        return jsonify(decision.to_dict_with_history())

    # Save current state to history before updating
    change_reason = data.get('change_reason', None)
    save_history(decision, change_reason, g.current_user)

    # Update fields
    if 'title' in data:
        decision.title = data['title']
    if 'context' in data:
        decision.context = data['context']
    if 'decision' in data:
        decision.decision = data['decision']
    if 'status' in data:
        decision.status = data['status']
    if 'consequences' in data:
        decision.consequences = data['consequences']

    # Handle infrastructure associations
    if 'infrastructure_ids' in data:
        infrastructure_ids = data['infrastructure_ids']
        if infrastructure_ids:
            infrastructure_items = ITInfrastructure.query.filter(
                ITInfrastructure.id.in_(infrastructure_ids),
                ITInfrastructure.domain == g.current_user.sso_domain
            ).all()
            decision.infrastructure = infrastructure_items
        else:
            decision.infrastructure = []

    decision.updated_by_id = g.current_user.id

    db.session.commit()

    # Send notifications
    email_config = EmailConfig.query.filter_by(domain=g.current_user.sso_domain, enabled=True).first()
    notify_subscribers_decision_updated(db, decision, email_config, change_reason, status_changed)

    return jsonify(decision.to_dict_with_history())


@app.route('/api/decisions/<int:decision_id>', methods=['DELETE'])
@login_required
def api_delete_decision(decision_id):
    """Soft delete an architecture decision."""
    # Master accounts cannot delete decisions
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot delete decisions. Please log in with an SSO account.'}), 403

    decision = ArchitectureDecision.query.filter_by(
        id=decision_id,
        domain=g.current_user.sso_domain,
        deleted_at=None
    ).first_or_404()

    # Soft delete
    decision.deleted_at = datetime.utcnow()
    decision.deleted_by_id = g.current_user.id

    db.session.commit()

    return jsonify({'message': 'Decision deleted successfully'})


@app.route('/api/decisions/<int:decision_id>/history', methods=['GET'])
@login_required
def api_get_decision_history(decision_id):
    """Get the update history for a decision."""
    if is_master_account():
        # Master accounts can view any decision history
        decision = ArchitectureDecision.query.filter_by(
            id=decision_id
        ).first_or_404()
    else:
        decision = ArchitectureDecision.query.filter_by(
            id=decision_id,
            domain=g.current_user.sso_domain
        ).first_or_404()

    history = DecisionHistory.query.filter_by(decision_id=decision_id).order_by(DecisionHistory.changed_at.desc()).all()
    return jsonify([h.to_dict() for h in history])


# ==================== API Routes - User ====================

@app.route('/api/user/me', methods=['GET'])
@login_required
def api_get_current_user():
    """Get current user info."""
    return jsonify(g.current_user.to_dict())


@app.route('/api/user/subscription', methods=['GET'])
@login_required
def api_get_subscription():
    """Get current user's subscription settings."""
    # Master accounts don't have subscriptions
    if is_master_account():
        return jsonify({'error': 'Master accounts do not support subscriptions'}), 400

    subscription = Subscription.query.filter_by(user_id=g.current_user.id).first()
    if not subscription:
        return jsonify({
            'notify_on_create': False,
            'notify_on_update': False,
            'notify_on_status_change': False
        })
    return jsonify(subscription.to_dict())


@app.route('/api/user/subscription', methods=['PUT'])
@login_required
def api_update_subscription():
    """Update current user's subscription settings."""
    # Master accounts don't have subscriptions
    if is_master_account():
        return jsonify({'error': 'Master accounts do not support subscriptions'}), 400

    data = request.get_json()

    subscription = Subscription.query.filter_by(user_id=g.current_user.id).first()

    if not subscription:
        subscription = Subscription(user_id=g.current_user.id)
        db.session.add(subscription)

    if 'notify_on_create' in data:
        subscription.notify_on_create = bool(data['notify_on_create'])
    if 'notify_on_update' in data:
        subscription.notify_on_update = bool(data['notify_on_update'])
    if 'notify_on_status_change' in data:
        subscription.notify_on_status_change = bool(data['notify_on_status_change'])

    db.session.commit()

    return jsonify(subscription.to_dict())


# ==================== API Routes - Admin (SSO Config) ====================

@app.route('/api/admin/sso', methods=['GET'])
@admin_required
def api_list_sso_configs():
    """List SSO configurations for user's domain (or all for master)."""
    if is_master_account():
        configs = SSOConfig.query.all()
    else:
        # Tenant admins only see their domain's SSO config
        configs = SSOConfig.query.filter_by(domain=g.current_user.sso_domain).all()
    return jsonify([c.to_dict() for c in configs])


@app.route('/api/admin/sso', methods=['POST'])
@admin_required
def api_create_sso_config():
    """Create a new SSO configuration (admin only)."""
    data = request.get_json()

    required_fields = ['domain', 'provider_name', 'client_id', 'client_secret', 'discovery_url']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Tenant admins can only create SSO for their own domain
    if not is_master_account():
        if data['domain'].lower() != g.current_user.sso_domain:
            return jsonify({'error': 'You can only configure SSO for your own domain'}), 403

    # Check if domain already exists
    existing = SSOConfig.query.filter_by(domain=data['domain'].lower()).first()
    if existing:
        return jsonify({'error': 'SSO configuration for this domain already exists'}), 400

    # Validate discovery URL
    oidc_config = get_oidc_config(data['discovery_url'])
    if not oidc_config:
        return jsonify({'error': 'Invalid discovery URL or unable to reach SSO provider'}), 400

    config = SSOConfig(
        domain=data['domain'].lower(),
        provider_name=data['provider_name'],
        client_id=data['client_id'],
        client_secret=data['client_secret'],
        discovery_url=data['discovery_url'],
        enabled=data.get('enabled', True)
    )

    db.session.add(config)
    db.session.commit()

    return jsonify(config.to_dict()), 201


@app.route('/api/admin/sso/<int:config_id>', methods=['PUT'])
@admin_required
def api_update_sso_config(config_id):
    """Update an SSO configuration (admin only)."""
    config = SSOConfig.query.get_or_404(config_id)

    # Tenant admins can only update their own domain's SSO
    if not is_master_account():
        if config.domain != g.current_user.sso_domain:
            return jsonify({'error': 'You can only update SSO for your own domain'}), 403

    data = request.get_json()

    if 'provider_name' in data:
        config.provider_name = data['provider_name']
    if 'client_id' in data:
        config.client_id = data['client_id']
    if 'client_secret' in data and data['client_secret']:
        config.client_secret = data['client_secret']
    if 'discovery_url' in data:
        # Validate new discovery URL
        oidc_config = get_oidc_config(data['discovery_url'])
        if not oidc_config:
            return jsonify({'error': 'Invalid discovery URL or unable to reach SSO provider'}), 400
        config.discovery_url = data['discovery_url']
    if 'enabled' in data:
        config.enabled = bool(data['enabled'])

    db.session.commit()

    return jsonify(config.to_dict())


@app.route('/api/admin/sso/<int:config_id>', methods=['DELETE'])
@admin_required
def api_delete_sso_config(config_id):
    """Delete an SSO configuration (admin only)."""
    config = SSOConfig.query.get_or_404(config_id)

    # Tenant admins can only delete their own domain's SSO
    if not is_master_account():
        if config.domain != g.current_user.sso_domain:
            return jsonify({'error': 'You can only delete SSO for your own domain'}), 403

    db.session.delete(config)
    db.session.commit()
    return jsonify({'message': 'SSO configuration deleted'})


# ==================== API Routes - Admin (Email Config) ====================

@app.route('/api/admin/email', methods=['GET'])
@admin_required
def api_get_email_config():
    """Get email configuration for user's domain (admin only)."""
    config = EmailConfig.query.filter_by(domain=g.current_user.sso_domain).first()
    if not config:
        return jsonify(None)
    return jsonify(config.to_dict())


@app.route('/api/admin/email', methods=['POST', 'PUT'])
@admin_required
def api_save_email_config():
    """Create or update email configuration (admin only)."""
    data = request.get_json()

    required_fields = ['smtp_server', 'smtp_port', 'smtp_username', 'from_email']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    config = EmailConfig.query.filter_by(domain=g.current_user.sso_domain).first()

    if not config:
        if not data.get('smtp_password'):
            return jsonify({'error': 'SMTP password is required for new configuration'}), 400

        config = EmailConfig(
            domain=g.current_user.sso_domain,
            smtp_server=data['smtp_server'],
            smtp_port=int(data['smtp_port']),
            smtp_username=data['smtp_username'],
            smtp_password=data['smtp_password'],
            from_email=data['from_email'],
            from_name=data.get('from_name', 'Architecture Decisions'),
            use_tls=data.get('use_tls', True),
            enabled=data.get('enabled', True)
        )
        db.session.add(config)
    else:
        config.smtp_server = data['smtp_server']
        config.smtp_port = int(data['smtp_port'])
        config.smtp_username = data['smtp_username']
        if data.get('smtp_password'):
            config.smtp_password = data['smtp_password']
        config.from_email = data['from_email']
        config.from_name = data.get('from_name', 'Architecture Decisions')
        config.use_tls = data.get('use_tls', True)
        config.enabled = data.get('enabled', True)

    db.session.commit()

    return jsonify(config.to_dict())


@app.route('/api/admin/email/test', methods=['POST'])
@admin_required
def api_test_email():
    """Send a test email (admin only)."""
    from notifications import send_email

    # Master accounts need to specify domain
    if is_master_account():
        data = request.get_json() or {}
        domain = data.get('domain')
        if not domain:
            return jsonify({'error': 'Domain is required for master account'}), 400
        config = EmailConfig.query.filter_by(domain=domain).first()
        test_email = data.get('email', 'admin@localhost')
    else:
        config = EmailConfig.query.filter_by(domain=g.current_user.sso_domain).first()
        test_email = g.current_user.email

    if not config:
        return jsonify({'error': 'Email configuration not found'}), 404

    success = send_email(
        config,
        test_email,
        'Architecture Decisions - Test Email',
        '<h1>Test Email</h1><p>This is a test email from Architecture Decisions.</p>',
        'Test Email\n\nThis is a test email from Architecture Decisions.'
    )

    if success:
        return jsonify({'message': 'Test email sent successfully'})
    else:
        return jsonify({'error': 'Failed to send test email'}), 500


# ==================== API Routes - System Email Config (Super Admin) ====================

@app.route('/api/admin/email/system', methods=['GET'])
@master_required
def api_get_system_email_config():
    """Get system-wide email configuration (super admin only)."""
    from keyvault_client import keyvault_client
    
    config = EmailConfig.query.filter_by(domain='system').first()
    if not config:
        return jsonify(None)
    
    # Get the config dict but override credentials with Key Vault status
    config_dict = config.to_dict()
    
    # Check if Key Vault credentials are available
    username, password = keyvault_client.get_smtp_credentials()
    config_dict['smtp_username'] = '***PROTECTED***' if username else ''
    config_dict['smtp_password'] = '***PROTECTED***' if password else ''
    config_dict['using_keyvault'] = bool(username and password)
    
    return jsonify(config_dict)


@app.route('/api/admin/email/system', methods=['POST', 'PUT'])
@master_required
def api_save_system_email_config():
    """Create or update system-wide email configuration (super admin only)."""
    from keyvault_client import keyvault_client
    data = request.get_json()

    # Username and password are not required since they come from Key Vault
    required_fields = ['smtp_server', 'smtp_port', 'from_email']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Validate Key Vault credentials are available
    username, password = keyvault_client.get_smtp_credentials()
    if not username or not password:
        return jsonify({'error': 'SMTP credentials not configured in Azure Key Vault. Please contact system administrator.'}), 400

    config = EmailConfig.query.filter_by(domain='system').first()

    if not config:
        config = EmailConfig(domain='system')
        db.session.add(config)

    config.smtp_server = data['smtp_server']
    config.smtp_port = int(data['smtp_port'])
    # Store placeholder values - actual credentials come from Key Vault
    config.smtp_username = 'from-keyvault'
    config.smtp_password = 'from-keyvault'
    config.from_email = data['from_email']
    config.from_name = data.get('from_name', 'Architecture Decisions')
    config.use_tls = bool(data.get('use_tls', True))
    config.enabled = bool(data.get('enabled', True))

    db.session.commit()

    # Return response with protected credentials
    config_dict = config.to_dict()
    config_dict['smtp_username'] = '***PROTECTED***'
    config_dict['smtp_password'] = '***PROTECTED***'
    config_dict['using_keyvault'] = True

    return jsonify(config_dict)


@app.route('/api/admin/email/system/test', methods=['POST'])
@master_required
def api_test_system_email():
    """Send a test email using system config (super admin only)."""
    from notifications import send_email

    config = EmailConfig.query.filter_by(domain='system').first()
    if not config:
        return jsonify({'error': 'System email configuration not found'}), 404

    # Get super admin notification email for test
    test_email = SystemConfig.get(SystemConfig.KEY_SUPER_ADMIN_EMAIL, default='')
    if not test_email:
        return jsonify({'error': 'Super admin email not configured. Please set notification email in Email Configuration.'}), 400

    success = send_email(
        config,
        test_email,
        'Architecture Decisions - Test Email',
        '<h1>Test Email</h1><p>This is a test email from Architecture Decisions system config.</p>',
        'Test Email\n\nThis is a test email from Architecture Decisions system config.'
    )

    if success:
        return jsonify({'message': f'Test email sent to {test_email}'})
    else:
        return jsonify({'error': 'Failed to send test email'}), 500


# ==================== API Routes - Admin (Users) ====================

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_list_users():
    """List all users in the admin's domain (or all users for master)."""
    if is_master_account():
        # Master can see all users
        users = User.query.all()
    else:
        users = User.query.filter_by(sso_domain=g.current_user.sso_domain).all()
    return jsonify([u.to_dict() for u in users])


@app.route('/api/admin/users/<int:user_id>/admin', methods=['PUT'])
@admin_required
def api_toggle_user_admin(user_id):
    """Toggle admin status for a user (admin only)."""
    if not is_master_account() and user_id == g.current_user.id:
        return jsonify({'error': 'Cannot modify your own admin status'}), 400

    if is_master_account():
        user = User.query.get_or_404(user_id)
    else:
        user = User.query.filter_by(id=user_id, sso_domain=g.current_user.sso_domain).first_or_404()

    data = request.get_json()
    user.is_admin = bool(data.get('is_admin', False))

    db.session.commit()

    return jsonify(user.to_dict())


# ==================== API Routes - Master Account ====================

@app.route('/api/master/password', methods=['PUT'])
@master_required
def api_change_master_password():
    """Change master account password."""
    data = request.get_json()

    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({'error': 'Current and new password are required'}), 400

    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    if not g.current_user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 400

    g.current_user.set_password(new_password)
    db.session.commit()

    return jsonify({'message': 'Password changed successfully'})


@app.route('/api/master/info', methods=['GET'])
@master_required
def api_get_master_info():
    """Get master account info."""
    return jsonify(g.current_user.to_dict())


@app.route('/api/admin/email/domains', methods=['GET'])
@admin_required
def api_list_email_configs():
    """List all email configurations (master only can see all)."""
    if is_master_account():
        configs = EmailConfig.query.all()
    else:
        configs = EmailConfig.query.filter_by(domain=g.current_user.sso_domain).all()
    return jsonify([c.to_dict() for c in configs])


# ==================== API Routes - WebAuthn ====================

@app.route('/api/auth/auth-config/<domain>', methods=['GET'])
def api_get_auth_config_public(domain):
    """Get authentication method for a domain (public endpoint for login page)."""
    auth_config = get_auth_config(domain.lower())
    if auth_config:
        return jsonify({
            'domain': auth_config.domain,
            'auth_method': auth_config.auth_method,
            'allow_registration': auth_config.allow_registration,
            'rp_name': auth_config.rp_name,
        })
    # Default to WebAuthn if no config exists
    return jsonify({
        'domain': domain.lower(),
        'auth_method': 'webauthn',
        'allow_registration': True,
        'rp_name': 'Architecture Decisions',
    })


@app.route('/api/auth/tenant/<domain>', methods=['GET'])
def api_get_tenant_status(domain):
    """Get tenant status - whether users exist and auth configuration."""
    domain = domain.lower()

    # Check if any users exist for this domain
    user_count = User.query.filter_by(sso_domain=domain).count()
    has_users = user_count > 0

    # Get auth config
    auth_config = get_auth_config(domain)

    # Check if SSO is configured for this domain
    sso_config = SSOConfig.query.filter_by(domain=domain, enabled=True).first()

    # Check global email verification setting
    email_verification_required = SystemConfig.get_bool(SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED, default=True)

    return jsonify({
        'domain': domain,
        'has_users': has_users,
        'user_count': user_count,
        'auth_method': auth_config.auth_method if auth_config else 'webauthn',
        'allow_registration': auth_config.allow_registration if auth_config else True,
        'require_approval': auth_config.require_approval if auth_config else True,
        'has_sso': sso_config is not None,
        'sso_provider': sso_config.provider_name if sso_config else None,
        'sso_id': sso_config.id if sso_config else None,
        'email_verification_required': email_verification_required,
    })


@app.route('/api/auth/user-exists/<email>', methods=['GET'])
def api_check_user_exists(email):
    """Check if a user exists by email."""
    user = User.query.filter_by(email=email.lower()).first()

    if user:
        return jsonify({
            'exists': True,
            'has_passkey': len(user.webauthn_credentials) > 0 if user.webauthn_credentials else False,
            'has_password': user.has_password(),
            'auth_type': user.auth_type,
            'email_verified': user.email_verified
        })
    else:
        return jsonify({
            'exists': False,
            'has_passkey': False,
            'has_password': False,
            'auth_type': None,
            'email_verified': False
        })


# ==================== Email Verification ====================

def generate_verification_token():
    """Generate a secure random token for email verification."""
    return secrets.token_urlsafe(32)


def send_verification_email(email, token, purpose, domain):
    """Send email verification message."""
    from notifications import send_email

    # Get email config for this domain or a global one
    email_config = EmailConfig.query.filter_by(domain=domain, enabled=True).first()
    if not email_config:
        # Try to find any enabled email config (for new tenants)
        email_config = EmailConfig.query.filter_by(enabled=True).first()

    if not email_config:
        app.logger.warning(f"No email config available for verification to {email}")
        return False

    base_url = request.host_url.rstrip('/')
    verify_url = f"{base_url}/verify-email/{token}"

    if purpose == 'signup':
        subject = 'Verify your email - Architecture Decisions'
        html_body = f"""
        <h1>Welcome to Architecture Decisions</h1>
        <p>Please verify your email address by clicking the button below:</p>
        <p><a href="{verify_url}" style="background-color: #3f51b5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">Verify Email</a></p>
        <p>Or copy and paste this link into your browser:</p>
        <p>{verify_url}</p>
        <p>This link will expire in 24 hours.</p>
        <p>If you didn't request this, you can safely ignore this email.</p>
        """
        text_body = f"Welcome to Architecture Decisions\n\nVerify your email by visiting: {verify_url}\n\nThis link expires in 24 hours."
    elif purpose == 'access_request':
        subject = 'Verify your email to request access - Architecture Decisions'
        html_body = f"""
        <h1>Request Access to Architecture Decisions</h1>
        <p>Please verify your email address to submit your access request:</p>
        <p><a href="{verify_url}" style="background-color: #3f51b5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">Verify and Submit Request</a></p>
        <p>Or copy and paste this link into your browser:</p>
        <p>{verify_url}</p>
        <p>This link will expire in 24 hours.</p>
        <p>If you didn't request this, you can safely ignore this email.</p>
        """
        text_body = f"Request Access\n\nVerify your email by visiting: {verify_url}\n\nThis link expires in 24 hours."
    else:
        subject = 'Verify your email - Architecture Decisions'
        html_body = f"""
        <h1>Email Verification</h1>
        <p>Please verify your email address by clicking the link below:</p>
        <p><a href="{verify_url}">{verify_url}</a></p>
        <p>This link will expire in 24 hours.</p>
        """
        text_body = f"Verify your email by visiting: {verify_url}\n\nThis link expires in 24 hours."

    return send_email(email_config, email, subject, html_body, text_body)


@app.route('/api/auth/send-verification', methods=['POST'])
def api_send_verification():
    """Send email verification link."""
    data = request.get_json()

    email = data.get('email', '').lower().strip()
    name = data.get('name', '').strip()
    purpose = data.get('purpose', 'signup')  # signup, access_request, login
    reason = data.get('reason', '')  # For access requests

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    if '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400

    domain = email.split('@')[1].lower()

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        if existing_user.email_verified:
            return jsonify({
                'error': 'This email is already registered. Please login instead.',
                'redirect': f'/{domain}/login'
            }), 400
        else:
            # User exists but not verified, allow re-sending verification
            pass

    # Check tenant status
    has_users = User.query.filter_by(sso_domain=domain).count() > 0
    auth_config = get_auth_config(domain)

    # Determine purpose based on context
    if has_users and not existing_user:
        # Existing tenant, new user - must request access unless auto-signup is enabled
        require_approval = auth_config.require_approval if auth_config else True
        if require_approval:
            purpose = 'access_request'
        else:
            purpose = 'signup'

    # Rate limiting: Check for recent verification emails
    recent_verification = EmailVerification.query.filter(
        EmailVerification.email == email,
        EmailVerification.created_at > datetime.utcnow() - timedelta(minutes=2)
    ).first()

    if recent_verification:
        return jsonify({'error': 'Please wait before requesting another verification email'}), 429

    # Invalidate any existing pending verifications for this email
    EmailVerification.query.filter(
        EmailVerification.email == email,
        EmailVerification.verified_at.is_(None)
    ).delete()
    db.session.commit()

    # Create new verification token
    token = generate_verification_token()
    expires_at = datetime.utcnow() + timedelta(hours=24)

    verification = EmailVerification(
        email=email,
        name=name,
        token=token,
        purpose=purpose,
        domain=domain,
        expires_at=expires_at,
        access_request_reason=reason if purpose == 'access_request' else None
    )
    db.session.add(verification)
    db.session.commit()

    # Send verification email
    email_sent = send_verification_email(email, token, purpose, domain)

    if email_sent:
        return jsonify({
            'message': 'Verification email sent',
            'email': email,
            'purpose': purpose
        })
    else:
        return jsonify({
            'message': 'Verification created but email could not be sent. Please contact an administrator.',
            'email': email,
            'purpose': purpose,
            'token': token if app.debug else None  # Only expose token in debug mode
        })


@app.route('/api/auth/direct-signup', methods=['POST'])
def api_direct_signup():
    """Direct signup (when email verification is disabled)."""
    # Check if email verification is disabled
    verification_required = SystemConfig.get_bool(SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED, default=True)
    if verification_required:
        return jsonify({'error': 'Email verification is required. Please use the standard signup flow.'}), 403

    data = request.get_json()
    email = data.get('email', '').lower().strip()
    name = data.get('name', '').strip()
    password = data.get('password', '').strip() if data.get('password') else None
    auth_preference = data.get('auth_preference', 'passkey')  # 'passkey' or 'password'

    if not email or not name:
        return jsonify({'error': 'Email and name are required'}), 400

    # Only require password if user chose password auth
    if auth_preference == 'password':
        if not password or len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400

    domain = email.split('@')[1].lower()

    # Check if this is a public email domain
    if DomainApproval.is_public_domain(domain):
        return jsonify({
            'error': f'{domain} is a public email provider. Please use your work email address.',
            'is_public_domain': True
        }), 400

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({
            'error': 'This email is already registered. Please login instead.',
            'redirect': f'/{domain}/login'
        }), 400

    # Check tenant status - this should only be used for new tenants
    has_users = User.query.filter_by(sso_domain=domain).count() > 0
    if has_users:
        return jsonify({
            'error': 'This organization already has users. Please use the login page.',
            'redirect': f'/{domain}/login'
        }), 400

    # Check domain approval status - but allow signup even if pending
    domain_approval = DomainApproval.query.filter_by(domain=domain).first()
    domain_pending = False

    if domain_approval and domain_approval.status == 'rejected':
        return jsonify({
            'error': 'Your organization domain has been rejected.',
            'domain_rejected': True,
            'reason': domain_approval.rejection_reason
        }), 403

    if not domain_approval:
        # New domain - create approval request
        domain_approval = DomainApproval(
            domain=domain,
            status='pending',
            requested_by_email=email,
            requested_by_name=name
        )
        db.session.add(domain_approval)
        domain_pending = True
        # TODO: Send notification to super admin about new domain
    elif domain_approval.status == 'pending':
        domain_pending = True

    # Create user account directly (first user becomes admin)
    user = User(
        email=email,
        name=name,
        sso_domain=domain,
        auth_type='webauthn' if auth_preference == 'passkey' else 'local',
        is_admin=True,  # First user becomes admin
        email_verified=True  # Mark as verified since verification is disabled
    )
    if auth_preference == 'password' and password:
        user.set_password(password)
    db.session.add(user)

    # Create default auth config for new tenant
    auth_config = AuthConfig.query.filter_by(domain=domain).first()
    if not auth_config:
        auth_config = AuthConfig(
            domain=domain,
            auth_method='local',
            allow_password=True,
            allow_passkey=True,
            allow_registration=True,
            require_approval=True,
            rp_name='Architecture Decisions'
        )
        db.session.add(auth_config)

    db.session.commit()

    # Log the user in
    session['user_id'] = user.id
    user.last_login = datetime.utcnow()
    db.session.commit()

    # Determine redirect based on auth preference and domain status
    if auth_preference == 'passkey':
        # Always go to profile for passkey setup first
        if domain_pending:
            redirect_url = f'/{domain}/profile?setup=passkey&pending=1'
        else:
            redirect_url = f'/{domain}/profile?setup=passkey'
        setup_passkey = True
    else:
        # Password auth - go to pending page or dashboard
        if domain_pending:
            redirect_url = f'/{domain}/pending'
        else:
            redirect_url = f'/{domain}'
        setup_passkey = False

    return jsonify({
        'message': 'Account created successfully',
        'email': email,
        'domain': domain,
        'user': user.to_dict(),
        'redirect': redirect_url,
        'setup_passkey': setup_passkey,
        'domain_pending': domain_pending
    })


@app.route('/api/auth/verify-email/<token>', methods=['GET', 'POST'])
def api_verify_email(token):
    """Verify email token and proceed with signup/access request."""
    verification = EmailVerification.query.filter_by(token=token).first()

    if not verification:
        if request.method == 'POST':
            return jsonify({'error': 'Invalid or expired verification link'}), 400
        return redirect('/?error=invalid_token')

    if verification.is_expired():
        if request.method == 'POST':
            return jsonify({'error': 'Verification link has expired. Please request a new one.'}), 400
        return redirect('/?error=expired_token')

    if verification.is_verified():
        # Already verified, redirect to appropriate page
        if request.method == 'POST':
            return jsonify({
                'message': 'Email already verified',
                'email': verification.email,
                'domain': verification.domain,
                'purpose': verification.purpose,
                'redirect': f'/{verification.domain}/login'
            })
        return redirect(f'/{verification.domain}/login')

    # Mark as verified
    verification.verified_at = datetime.utcnow()

    # Process based on purpose
    if verification.purpose == 'signup':
        # Create user account (if doesn't exist)
        user = User.query.filter_by(email=verification.email).first()
        if not user:
            # Determine if this is the first user for the domain
            is_first_user = User.query.filter_by(sso_domain=verification.domain).count() == 0

            user = User(
                email=verification.email,
                name=verification.name,
                sso_domain=verification.domain,
                auth_type='webauthn',
                is_admin=is_first_user,  # First user becomes admin
                email_verified=True
            )
            db.session.add(user)

            # Create default auth config if this is a new tenant
            if is_first_user:
                auth_config = AuthConfig.query.filter_by(domain=verification.domain).first()
                if not auth_config:
                    auth_config = AuthConfig(
                        domain=verification.domain,
                        auth_method='webauthn',
                        allow_registration=True,
                        require_approval=True,
                        rp_name='Architecture Decisions'
                    )
                    db.session.add(auth_config)
        else:
            user.email_verified = True
            if verification.name:
                user.name = verification.name

        db.session.commit()

        if request.method == 'POST':
            return jsonify({
                'message': 'Email verified successfully',
                'email': verification.email,
                'domain': verification.domain,
                'purpose': 'signup',
                'redirect': f'/{verification.domain}/login?verified=1'
            })
        return redirect(f'/{verification.domain}/login?verified=1&email={verification.email}')

    elif verification.purpose == 'access_request':
        # Create access request
        existing_request = AccessRequest.query.filter_by(
            email=verification.email,
            status='pending'
        ).first()

        if not existing_request:
            access_request = AccessRequest(
                email=verification.email,
                name=verification.name or verification.email.split('@')[0],
                domain=verification.domain,
                reason=verification.access_request_reason
            )
            db.session.add(access_request)

        db.session.commit()

        if request.method == 'POST':
            return jsonify({
                'message': 'Access request submitted successfully',
                'email': verification.email,
                'domain': verification.domain,
                'purpose': 'access_request'
            })
        return redirect(f'/{verification.domain}/login?access_requested=1')

    db.session.commit()

    if request.method == 'POST':
        return jsonify({
            'message': 'Email verified',
            'email': verification.email,
            'domain': verification.domain,
            'redirect': f'/{verification.domain}/login'
        })
    return redirect(f'/{verification.domain}/login')


@app.route('/api/auth/verification-status/<token>', methods=['GET'])
def api_verification_status(token):
    """Check verification token status."""
    verification = EmailVerification.query.filter_by(token=token).first()

    if not verification:
        return jsonify({'valid': False, 'error': 'Token not found'}), 404

    return jsonify({
        'valid': True,
        'email': verification.email,
        'domain': verification.domain,
        'purpose': verification.purpose,
        'expired': verification.is_expired(),
        'verified': verification.is_verified()
    })


@app.route('/api/auth/access-request', methods=['POST'])
def api_submit_access_request():
    """Submit an access request to join a tenant."""
    data = request.get_json()

    email = data.get('email', '').lower()
    name = data.get('name')
    reason = data.get('reason', '')
    domain = data.get('domain', '').lower()

    if not email or not name:
        return jsonify({'error': 'Email and name are required'}), 400

    # Extract and validate domain from email
    email_domain = email.split('@')[1] if '@' in email else ''
    if not domain:
        domain = email_domain
    elif domain != email_domain:
        return jsonify({'error': 'Email domain does not match requested tenant'}), 400

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'An account with this email already exists'}), 400

    # Check if there's already a pending request for this email
    existing_request = AccessRequest.query.filter_by(email=email, status='pending').first()
    if existing_request:
        return jsonify({'error': 'You already have a pending access request'}), 400

    # Check if tenant exists (has users)
    if User.query.filter_by(sso_domain=domain).count() == 0:
        return jsonify({'error': 'This organization does not exist yet. Please sign up instead.'}), 400

    # Create access request
    access_request = AccessRequest(
        email=email,
        name=name,
        domain=domain,
        reason=reason
    )
    db.session.add(access_request)
    db.session.commit()

    # TODO: Send email notification to admins of this domain
    # notify_admins_access_request(domain, access_request)

    return jsonify({
        'message': 'Access request submitted successfully',
        'request': access_request.to_dict()
    })


# ==================== API Routes - Admin (Access Requests) ====================

@app.route('/api/admin/access-requests', methods=['GET'])
@admin_required
def api_list_access_requests():
    """List access requests for admin's domain."""
    if is_master_account():
        # Master can see all requests
        requests = AccessRequest.query.order_by(AccessRequest.created_at.desc()).all()
    else:
        # Regular admin sees only their domain's requests
        requests = AccessRequest.query.filter_by(
            domain=g.current_user.sso_domain
        ).order_by(AccessRequest.created_at.desc()).all()

    return jsonify([r.to_dict() for r in requests])


@app.route('/api/admin/access-requests/pending', methods=['GET'])
@admin_required
def api_list_pending_requests():
    """List pending access requests for admin's domain."""
    if is_master_account():
        requests = AccessRequest.query.filter_by(status='pending').order_by(AccessRequest.created_at.desc()).all()
    else:
        requests = AccessRequest.query.filter_by(
            domain=g.current_user.sso_domain,
            status='pending'
        ).order_by(AccessRequest.created_at.desc()).all()

    return jsonify([r.to_dict() for r in requests])


@app.route('/api/admin/access-requests/<int:request_id>/approve', methods=['POST'])
@admin_required
def api_approve_access_request(request_id):
    """Approve an access request and create the user account."""
    from datetime import datetime

    access_request = AccessRequest.query.get_or_404(request_id)

    # Check permission
    if not is_master_account() and access_request.domain != g.current_user.sso_domain:
        return jsonify({'error': 'Not authorized to approve this request'}), 403

    if access_request.status != 'pending':
        return jsonify({'error': f'Request is already {access_request.status}'}), 400

    # Check if user already exists (could have been created via another path)
    existing_user = User.query.filter_by(email=access_request.email).first()
    if existing_user:
        access_request.status = 'approved'
        access_request.processed_by_id = g.current_user.id if not is_master_account() else None
        access_request.processed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'message': 'User already exists, request marked as approved', 'user': existing_user.to_dict()})

    # Create the user account
    new_user = User(
        email=access_request.email,
        name=access_request.name,
        sso_domain=access_request.domain,
        auth_type='webauthn',
        is_admin=False
    )
    db.session.add(new_user)

    # Update request status
    access_request.status = 'approved'
    access_request.processed_by_id = g.current_user.id if not is_master_account() else None
    access_request.processed_at = datetime.utcnow()

    db.session.commit()

    # TODO: Send email to user informing them they've been approved
    # notify_user_access_approved(access_request, new_user)

    return jsonify({
        'message': 'Access request approved',
        'user': new_user.to_dict()
    })


@app.route('/api/admin/access-requests/<int:request_id>/reject', methods=['POST'])
@admin_required
def api_reject_access_request(request_id):
    """Reject an access request."""
    from datetime import datetime

    data = request.get_json() or {}
    rejection_reason = data.get('reason', '')

    access_request = AccessRequest.query.get_or_404(request_id)

    # Check permission
    if not is_master_account() and access_request.domain != g.current_user.sso_domain:
        return jsonify({'error': 'Not authorized to reject this request'}), 403

    if access_request.status != 'pending':
        return jsonify({'error': f'Request is already {access_request.status}'}), 400

    # Update request status
    access_request.status = 'rejected'
    access_request.rejection_reason = rejection_reason
    access_request.processed_by_id = g.current_user.id if not is_master_account() else None
    access_request.processed_at = datetime.utcnow()

    db.session.commit()

    # TODO: Send email to user informing them they've been rejected
    # notify_user_access_rejected(access_request)

    return jsonify({
        'message': 'Access request rejected',
        'request': access_request.to_dict()
    })


@app.route('/api/webauthn/register/options', methods=['POST'])
@rate_limit("10 per minute")
def api_webauthn_register_options():
    """Generate WebAuthn registration options."""
    data = request.get_json()

    email = data.get('email')
    name = data.get('name')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    # SECURITY: Always extract domain from email - never trust user input
    from auth import extract_domain_from_email
    domain = extract_domain_from_email(email)

    if not domain:
        return jsonify({'error': 'Invalid email format'}), 400

    # Log registration attempt
    log_security_event('auth', f"WebAuthn registration attempt for {email}", severity='INFO')

    # Check auth config for this domain
    auth_config = get_auth_config(domain)

    # Check if SSO is configured and required for this domain
    sso_config = SSOConfig.query.filter_by(domain=domain, enabled=True).first()
    if sso_config and (not auth_config or auth_config.auth_method == 'sso'):
        return jsonify({'error': 'This domain requires SSO authentication'}), 400

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user.auth_type == 'sso':
        return jsonify({'error': 'This email is registered with SSO. Please use SSO to log in.'}), 400

    # Check if registration is allowed for new users
    if not existing_user:
        if auth_config and not auth_config.allow_registration:
            return jsonify({'error': 'Registration is not allowed for this domain'}), 400

    try:
        options = create_registration_options(email, name, domain)
        return jsonify(json.loads(options))
    except Exception as e:
        app.logger.error(f"WebAuthn registration options error: {e}")
        return jsonify({'error': 'Failed to generate registration options'}), 500


@app.route('/api/webauthn/register/verify', methods=['POST'])
def api_webauthn_register_verify():
    """Verify WebAuthn registration and create/login user."""
    data = request.get_json()

    credential = data.get('credential')
    device_name = data.get('device_name')

    if not credential:
        return jsonify({'error': 'Credential is required'}), 400

    user, error = verify_registration(credential, device_name)

    if error:
        return jsonify({'error': error}), 400

    # Log the user in
    session['user_id'] = user.id
    session.permanent = True

    return jsonify({
        'message': 'Registration successful',
        'user': user.to_dict()
    })


@app.route('/api/webauthn/authenticate/options', methods=['POST'])
def api_webauthn_auth_options():
    """Generate WebAuthn authentication options."""
    data = request.get_json() or {}

    email = data.get('email')

    # If email provided, check if user exists and uses WebAuthn
    if email:
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        if user.auth_type == 'sso':
            return jsonify({'error': 'This account uses SSO. Please use SSO to log in.'}), 400
        if not user.webauthn_credentials:
            return jsonify({'error': 'No passkeys registered for this account'}), 400

    try:
        options = create_authentication_options(email)
        return jsonify(json.loads(options))
    except Exception as e:
        app.logger.error(f"WebAuthn authentication options error: {e}")
        return jsonify({'error': 'Failed to generate authentication options'}), 500


@app.route('/api/webauthn/authenticate/verify', methods=['POST'])
def api_webauthn_auth_verify():
    """Verify WebAuthn authentication and log in user."""
    data = request.get_json()

    credential = data.get('credential')

    if not credential:
        return jsonify({'error': 'Credential is required'}), 400

    user, error = verify_authentication(credential)

    if error:
        return jsonify({'error': error}), 400

    # Log the user in
    session['user_id'] = user.id
    session.permanent = True

    return jsonify({
        'message': 'Authentication successful',
        'user': user.to_dict()
    })


# ==================== API Routes - User Credentials ====================

@app.route('/api/user/credentials', methods=['GET'])
@login_required
def api_get_user_credentials():
    """Get all WebAuthn credentials for the current user."""
    if is_master_account():
        return jsonify({'error': 'Master accounts do not have WebAuthn credentials'}), 400

    credentials = get_user_credentials(g.current_user.id)
    return jsonify(credentials)


@app.route('/api/user/credentials/<credential_id>', methods=['DELETE'])
@login_required
def api_delete_user_credential(credential_id):
    """Delete a WebAuthn credential for the current user."""
    if is_master_account():
        return jsonify({'error': 'Master accounts do not have WebAuthn credentials'}), 400

    success, error = delete_credential(g.current_user.id, credential_id)

    if not success:
        return jsonify({'error': error}), 400

    return jsonify({'message': 'Credential deleted successfully'})


@app.route('/api/user/credentials', methods=['POST'])
@login_required
def api_add_user_credential():
    """Add a new WebAuthn credential for the current user."""
    if is_master_account():
        return jsonify({'error': 'Master accounts do not have WebAuthn credentials'}), 400

    if g.current_user.auth_type != 'webauthn':
        return jsonify({'error': 'Your account uses SSO authentication'}), 400

    data = request.get_json()
    name = data.get('name')

    try:
        options = create_registration_options(
            g.current_user.email,
            g.current_user.name,
            g.current_user.sso_domain
        )
        return jsonify(json.loads(options))
    except Exception as e:
        app.logger.error(f"WebAuthn add credential options error: {e}")
        return jsonify({'error': 'Failed to generate registration options'}), 500


# ==================== API Routes - Admin (Auth Config) ====================

@app.route('/api/admin/auth-config', methods=['GET'])
@admin_required
def api_get_auth_config():
    """Get authentication configuration for user's domain."""
    if is_master_account():
        # Master can see all auth configs
        configs = AuthConfig.query.all()
        return jsonify([c.to_dict() for c in configs])

    config = AuthConfig.query.filter_by(domain=g.current_user.sso_domain).first()
    if not config:
        # Return default config
        return jsonify({
            'domain': g.current_user.sso_domain,
            'auth_method': 'webauthn',
            'allow_registration': True,
            'require_approval': True,
            'rp_name': 'Architecture Decisions',
        })
    return jsonify(config.to_dict())


@app.route('/api/admin/auth-config', methods=['POST', 'PUT'])
@admin_required
def api_save_auth_config():
    """Create or update authentication configuration."""
    data = request.get_json()

    # Master can specify domain, regular admins use their own domain
    if is_master_account():
        domain = data.get('domain')
        if not domain:
            return jsonify({'error': 'Domain is required for master account'}), 400
    else:
        domain = g.current_user.sso_domain

    auth_method = data.get('auth_method', 'webauthn')
    if auth_method not in ['sso', 'webauthn']:
        return jsonify({'error': 'auth_method must be "sso" or "webauthn"'}), 400

    # If setting to SSO, check if SSO config exists for this domain
    if auth_method == 'sso':
        sso_config = SSOConfig.query.filter_by(domain=domain, enabled=True).first()
        if not sso_config:
            return jsonify({'error': 'Cannot set auth method to SSO without a valid SSO configuration'}), 400

    config = AuthConfig.query.filter_by(domain=domain).first()

    if not config:
        config = AuthConfig(
            domain=domain,
            auth_method=auth_method,
            allow_registration=data.get('allow_registration', True),
            require_approval=data.get('require_approval', True),
            rp_name=data.get('rp_name', 'Architecture Decisions'),
        )
        db.session.add(config)
    else:
        config.auth_method = auth_method
        if 'allow_registration' in data:
            config.allow_registration = bool(data['allow_registration'])
        if 'require_approval' in data:
            config.require_approval = bool(data['require_approval'])
        if 'rp_name' in data:
            config.rp_name = data['rp_name']

    db.session.commit()

    return jsonify(config.to_dict())


# ==================== API Routes - System Configuration (Super Admin) ====================

@app.route('/api/system/config', methods=['GET'])
@master_required
def api_get_system_config():
    """Get all system configuration settings (super admin only)."""
    configs = SystemConfig.query.all()
    return jsonify({c.key: {'value': c.value, 'description': c.description, 'updated_at': c.updated_at.isoformat()} for c in configs})


@app.route('/api/system/config/<key>', methods=['GET'])
@master_required
def api_get_system_config_key(key):
    """Get a specific system configuration setting (super admin only)."""
    config = SystemConfig.query.filter_by(key=key).first()
    if config:
        return jsonify(config.to_dict())
    return jsonify({'key': key, 'value': None, 'description': None})


@app.route('/api/system/config', methods=['POST', 'PUT'])
@master_required
def api_set_system_config():
    """Set system configuration settings (super admin only)."""
    data = request.get_json()

    if not data or 'key' not in data:
        return jsonify({'error': 'Key is required'}), 400

    key = data['key']
    value = data.get('value', '')
    description = data.get('description')

    config = SystemConfig.set(key, value, description)
    return jsonify(config.to_dict())


@app.route('/api/system/email-verification', methods=['GET'])
def api_get_email_verification_status():
    """Get email verification requirement status (public endpoint)."""
    is_required = SystemConfig.get_bool(SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED, default=True)
    return jsonify({'required': is_required})


@app.route('/api/system/email-verification', methods=['PUT'])
@master_required
def api_set_email_verification():
    """Toggle email verification requirement (super admin only)."""
    data = request.get_json()

    if 'required' not in data:
        return jsonify({'error': 'required field is required'}), 400

    is_required = bool(data['required'])
    SystemConfig.set(
        SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED,
        'true' if is_required else 'false',
        'Require email verification for new user signups'
    )

    return jsonify({
        'required': is_required,
        'message': f'Email verification is now {"enabled" if is_required else "disabled"}'
    })


@app.route('/api/system/super-admin-email', methods=['GET'])
@master_required
def api_get_super_admin_email():
    """Get super admin notification email address."""
    email = SystemConfig.get(SystemConfig.KEY_SUPER_ADMIN_EMAIL, default='')
    return jsonify({'email': email})


@app.route('/api/system/super-admin-email', methods=['PUT'])
@master_required
def api_set_super_admin_email():
    """Set super admin notification email address."""
    data = request.get_json()

    email = data.get('email', '').strip()
    if email and '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400

    SystemConfig.set(
        SystemConfig.KEY_SUPER_ADMIN_EMAIL,
        email,
        'Email address for super admin notifications (domain approvals, etc.)'
    )

    return jsonify({
        'email': email,
        'message': 'Super admin notification email updated'
    })


# ==================== API Routes - Domain Approval ====================

@app.route('/api/domains/pending', methods=['GET'])
@master_required
def api_list_pending_domains():
    """List all pending domain approvals (super admin only)."""
    approvals = DomainApproval.query.filter_by(status='pending').order_by(DomainApproval.created_at.desc()).all()
    return jsonify([a.to_dict() for a in approvals])


@app.route('/api/domains', methods=['GET'])
@master_required
def api_list_all_domains():
    """List all domain approvals (super admin only)."""
    approvals = DomainApproval.query.order_by(DomainApproval.created_at.desc()).all()
    return jsonify([a.to_dict() for a in approvals])


@app.route('/api/domains/<int:domain_id>/approve', methods=['POST'])
@master_required
def api_approve_domain(domain_id):
    """Approve a domain for signup (super admin only)."""
    approval = DomainApproval.query.get_or_404(domain_id)

    if approval.status != 'pending':
        return jsonify({'error': f'Domain is already {approval.status}'}), 400

    approval.status = 'approved'
    approval.approved_by_id = g.current_user.id
    db.session.commit()

    # TODO: Send notification email to the user who requested

    return jsonify({
        'message': f'Domain {approval.domain} has been approved',
        'domain': approval.to_dict()
    })


@app.route('/api/domains/<int:domain_id>/reject', methods=['POST'])
@master_required
def api_reject_domain(domain_id):
    """Reject a domain for signup (super admin only)."""
    approval = DomainApproval.query.get_or_404(domain_id)
    data = request.get_json() or {}

    if approval.status != 'pending':
        return jsonify({'error': f'Domain is already {approval.status}'}), 400

    approval.status = 'rejected'
    approval.rejection_reason = data.get('reason', 'Domain not allowed')
    db.session.commit()

    # TODO: Send notification email to the user who requested

    return jsonify({
        'message': f'Domain {approval.domain} has been rejected',
        'domain': approval.to_dict()
    })


@app.route('/api/domains/check/<domain>', methods=['GET'])
def api_check_domain_status(domain):
    """Check if a domain is approved for signup (public endpoint)."""
    domain = domain.lower()

    if DomainApproval.is_public_domain(domain):
        return jsonify({
            'domain': domain,
            'status': 'rejected',
            'is_public_domain': True,
            'message': 'Public email domains are not allowed'
        })

    approval = DomainApproval.query.filter_by(domain=domain).first()
    if not approval:
        return jsonify({
            'domain': domain,
            'status': 'unknown',
            'message': 'Domain not yet registered'
        })

    return jsonify({
        'domain': domain,
        'status': approval.status,
        'message': 'Domain is approved' if approval.status == 'approved' else f'Domain is {approval.status}'
    })


@app.route('/api/tenants', methods=['GET'])
@master_required
def api_list_tenants():
    """List all tenants (organizations) with their stats (super admin only)."""
    tenants = {}

    # Get domains from approved DomainApproval records
    approved_domains = DomainApproval.query.filter_by(status='approved').all()
    for approval in approved_domains:
        tenants[approval.domain] = {
            'domain': approval.domain,
            'user_count': 0,
            'admin_count': 0,
            'has_sso': False,
            'created_at': approval.updated_at.isoformat() if approval.updated_at else approval.created_at.isoformat()
        }

    # Get user stats by domain
    domain_stats = db.session.query(
        User.sso_domain,
        db.func.count(User.id).label('user_count'),
        db.func.sum(db.case((User.is_admin == True, 1), else_=0)).label('admin_count'),
        db.func.min(User.created_at).label('created_at')
    ).group_by(User.sso_domain).all()

    for domain, user_count, admin_count, created_at in domain_stats:
        if domain:
            if domain not in tenants:
                tenants[domain] = {
                    'domain': domain,
                    'user_count': 0,
                    'admin_count': 0,
                    'has_sso': False,
                    'created_at': created_at.isoformat() if created_at else None
                }
            tenants[domain]['user_count'] = user_count
            tenants[domain]['admin_count'] = int(admin_count) if admin_count else 0

    # Check SSO config for all domains
    for domain in tenants:
        tenants[domain]['has_sso'] = SSOConfig.query.filter_by(domain=domain, enabled=True).first() is not None

    return jsonify(sorted(tenants.values(), key=lambda x: x['domain']))


# ==================== API Routes - Tenant Auth Config ====================

@app.route('/api/tenant/<domain>/auth-config', methods=['GET'])
def api_get_tenant_auth_config(domain):
    """Get authentication configuration for a tenant (public endpoint)."""
    auth_config = AuthConfig.query.filter_by(domain=domain.lower()).first()

    if not auth_config:
        # Return defaults
        return jsonify({
            'domain': domain.lower(),
            'auth_method': 'local',
            'allow_password': True,
            'allow_passkey': True,
            'allow_registration': True,
            'has_sso': False,
            'sso_provider': None
        })

    # Check if tenant has SSO configured
    sso_config = SSOConfig.query.filter_by(domain=domain.lower(), enabled=True).first()

    return jsonify({
        'domain': auth_config.domain,
        'auth_method': auth_config.auth_method,
        'allow_password': auth_config.allow_password,
        'allow_passkey': auth_config.allow_passkey,
        'allow_registration': auth_config.allow_registration,
        'has_sso': sso_config is not None,
        'sso_provider': sso_config.provider_name if sso_config else None,
        'sso_id': sso_config.id if sso_config else None
    })


@app.route('/api/tenant/auth-config', methods=['PUT'])
@admin_required
def api_update_tenant_auth_config():
    """Update authentication configuration for tenant (admin only)."""
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot modify tenant auth configs'}), 403

    domain = g.current_user.sso_domain
    data = request.get_json()

    auth_config = AuthConfig.query.filter_by(domain=domain).first()
    if not auth_config:
        auth_config = AuthConfig(domain=domain)
        db.session.add(auth_config)

    if 'auth_method' in data:
        if data['auth_method'] not in ['local', 'sso', 'webauthn']:
            return jsonify({'error': 'Invalid auth method'}), 400
        auth_config.auth_method = data['auth_method']

    if 'allow_password' in data:
        auth_config.allow_password = bool(data['allow_password'])

    if 'allow_passkey' in data:
        auth_config.allow_passkey = bool(data['allow_passkey'])

    if 'allow_registration' in data:
        auth_config.allow_registration = bool(data['allow_registration'])

    if 'require_approval' in data:
        auth_config.require_approval = bool(data['require_approval'])

    db.session.commit()

    return jsonify({
        'message': 'Auth configuration updated',
        'config': auth_config.to_dict()
    })


# ==================== API Routes - IT Infrastructure ====================

@app.route('/api/infrastructure', methods=['GET'])
@login_required
def api_list_infrastructure():
    """List all IT infrastructure items for the user's domain."""
    if is_master_account():
        # Master accounts can see all infrastructure across all domains
        items = ITInfrastructure.query.order_by(ITInfrastructure.name).all()
    else:
        items = ITInfrastructure.query.filter_by(
            domain=g.current_user.sso_domain
        ).order_by(ITInfrastructure.name).all()
    return jsonify([item.to_dict() for item in items])


@app.route('/api/infrastructure', methods=['POST'])
@login_required
def api_create_infrastructure():
    """Create a new IT infrastructure item."""
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot create infrastructure items'}), 403

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400

    if not data.get('type'):
        return jsonify({'error': 'Type is required'}), 400

    # Validate type
    infra_type = data['type'].lower()
    if infra_type not in ITInfrastructure.VALID_TYPES:
        return jsonify({'error': f'Invalid type. Must be one of: {", ".join(ITInfrastructure.VALID_TYPES)}'}), 400

    # Check for duplicate name in same domain
    existing = ITInfrastructure.query.filter_by(
        name=data['name'],
        domain=g.current_user.sso_domain
    ).first()
    if existing:
        return jsonify({'error': 'An infrastructure item with this name already exists'}), 400

    item = ITInfrastructure(
        name=data['name'],
        type=infra_type,
        description=data.get('description', ''),
        domain=g.current_user.sso_domain,
        created_by_id=g.current_user.id
    )

    db.session.add(item)
    db.session.commit()

    return jsonify(item.to_dict()), 201


@app.route('/api/infrastructure/<int:item_id>', methods=['GET'])
@login_required
def api_get_infrastructure(item_id):
    """Get a single IT infrastructure item."""
    if is_master_account():
        item = ITInfrastructure.query.get_or_404(item_id)
    else:
        item = ITInfrastructure.query.filter_by(
            id=item_id,
            domain=g.current_user.sso_domain
        ).first_or_404()
    return jsonify(item.to_dict())


@app.route('/api/infrastructure/<int:item_id>', methods=['PUT'])
@login_required
def api_update_infrastructure(item_id):
    """Update an IT infrastructure item."""
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot modify infrastructure items'}), 403

    item = ITInfrastructure.query.filter_by(
        id=item_id,
        domain=g.current_user.sso_domain
    ).first_or_404()

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate type if provided
    if 'type' in data:
        infra_type = data['type'].lower()
        if infra_type not in ITInfrastructure.VALID_TYPES:
            return jsonify({'error': f'Invalid type. Must be one of: {", ".join(ITInfrastructure.VALID_TYPES)}'}), 400
        item.type = infra_type

    # Check for duplicate name if name is being changed
    if 'name' in data and data['name'] != item.name:
        existing = ITInfrastructure.query.filter_by(
            name=data['name'],
            domain=g.current_user.sso_domain
        ).first()
        if existing:
            return jsonify({'error': 'An infrastructure item with this name already exists'}), 400
        item.name = data['name']

    if 'description' in data:
        item.description = data['description']

    db.session.commit()

    return jsonify(item.to_dict())


@app.route('/api/infrastructure/<int:item_id>', methods=['DELETE'])
@login_required
def api_delete_infrastructure(item_id):
    """Delete an IT infrastructure item."""
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot delete infrastructure items'}), 403

    item = ITInfrastructure.query.filter_by(
        id=item_id,
        domain=g.current_user.sso_domain
    ).first_or_404()

    # Remove associations with decisions first
    item.decisions.filter().all()  # Force load to avoid issues

    db.session.delete(item)
    db.session.commit()

    return jsonify({'message': 'Infrastructure item deleted successfully'})


@app.route('/api/infrastructure/types', methods=['GET'])
def api_get_infrastructure_types():
    """Get available infrastructure types."""
    return jsonify(ITInfrastructure.VALID_TYPES)


# ==================== Angular Frontend Serving ====================

if SERVE_ANGULAR:
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_angular(path):
        """Serve Angular frontend or fallback to index.html for SPA routing."""
        # Check if app is healthy for root path
        if path == '' and not app_error_state['healthy']:
            # Return error page if database is not working
            return f"""
            <html>
                <head><title>Application Error</title></head>
                <body style='font-family: Arial, sans-serif; padding: 20px;'>
                    <h1 style='color: red;'>Application Error</h1>
                    <h2>Database Connection Failed</h2>
                    <p><strong>Error:</strong> {app_error_state['error'] or 'Unknown error'}</p>
                    <h3>Details:</h3>
                    <pre style='background: #f0f0f0; padding: 15px; overflow-x: auto;'>{app_error_state['details'] or 'No details available'}</pre>
                    <hr>
                    <p><small>Please contact your administrator to resolve this issue.</small></p>
                    <p><a href="/health">Check Health Status</a></p>
                </body>
            </html>
            """, 503
            
        # API and auth routes should be handled by Flask, not Angular
        # If we reach here for these paths, it means there's no handler - return 404
        if path.startswith('api/'):
            return jsonify({'error': 'Not found'}), 404

        # Try to serve static files (JS, CSS, images, etc.)
        if path and os.path.exists(os.path.join(FRONTEND_DIR, path)):
            return send_from_directory(FRONTEND_DIR, path)

        # Fallback to index.html for Angular SPA routing
        # This handles all frontend routes like /, /superadmin, /{tenant}/login, etc.
        return send_from_directory(FRONTEND_DIR, 'index.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
