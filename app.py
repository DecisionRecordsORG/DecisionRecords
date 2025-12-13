import os
import json
import secrets
import logging
import sys
import traceback
import psycopg2
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g, send_from_directory
from authlib.integrations.requests_client import OAuth2Session
from models import db, User, MasterAccount, SSOConfig, EmailConfig, Subscription, ArchitectureDecision, DecisionHistory, AuthConfig, WebAuthnCredential, AccessRequest, EmailVerification, ITInfrastructure, SystemConfig, DomainApproval, save_history, Tenant, TenantMembership, TenantSettings, Space, DecisionSpace, GlobalRole, MaturityState, AuditLog, RoleRequest, RequestedRole, RequestStatus
from datetime import datetime, timedelta
from auth import login_required, admin_required, get_current_user, get_or_create_user, get_oidc_config, extract_domain_from_email, is_master_account, authenticate_master, master_required, steward_or_admin_required, get_current_tenant, get_current_membership
from governance import log_admin_action
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
from analytics import track_endpoint

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
# IMPORTANT: When FLASK_ENV=testing, use isolated SQLite database to protect production
if os.environ.get('FLASK_ENV') == 'testing':
    database_url = 'sqlite:///test_database.db'
    logger.info("TESTING MODE: Using isolated SQLite test database")
else:
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
# Note: PERMANENT_SESSION_LIFETIME is set dynamically per session type (admin vs user)
# Default max is 24 hours, but actual expiry is stored in session['_expires_at']
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Rate limiting configuration - disabled in testing mode
if os.environ.get('FLASK_ENV') == 'testing':
    app.config['RATELIMIT_ENABLED'] = False
    limiter = None
    RATE_LIMITING_ENABLED = False
    logger.info("TESTING MODE: Rate limiting disabled for E2E tests")
else:
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

# ==================== Global Error Handlers ====================
# SECURITY: Prevent stack traces and sensitive information from leaking to clients
# All errors are logged server-side but only generic messages are returned to clients

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler to prevent stack trace leakage."""
    # Log the full error details server-side
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())

    # Capture to PostHog if enabled
    from analytics import capture_exception
    capture_exception(e, endpoint_name='unhandled_exception')

    # Return generic error to client - NEVER expose internal details
    if request.path.startswith('/api/'):
        return jsonify({'error': 'An internal server error occurred'}), 500
    else:
        return "An error occurred", 500

@app.errorhandler(500)
def handle_500(e):
    """Handle 500 Internal Server Error."""
    logger.error(f"500 Error: {str(e)}")

    # Capture to PostHog if enabled
    from analytics import capture_exception
    capture_exception(e, endpoint_name='http_500_error')

    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return "Internal server error", 500

@app.errorhandler(404)
def handle_404(e):
    """Handle 404 Not Found."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Resource not found'}), 404
    # For non-API routes, let Angular handle routing
    if SERVE_ANGULAR:
        return send_from_directory(app.static_folder, 'index.html')
    return "Not found", 404

@app.errorhandler(403)
def handle_403(e):
    """Handle 403 Forbidden."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Access forbidden'}), 403
    return "Access forbidden", 403

@app.errorhandler(401)
def handle_401(e):
    """Handle 401 Unauthorized."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Authentication required'}), 401
    return "Authentication required", 401

@app.errorhandler(400)
def handle_400(e):
    """Handle 400 Bad Request."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Bad request'}), 400
    return "Bad request", 400

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

                # Run migrations for any new columns added to existing tables
                # SQLAlchemy's create_all() doesn't modify existing tables
                logger.info("Running schema migrations...")
                try:
                    with db.engine.connect() as conn:
                        # Check and add auto_approved column to domain_approvals
                        result = conn.execute(db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'domain_approvals' AND column_name = 'auto_approved'
                        """))
                        if not result.fetchone():
                            logger.info("Adding auto_approved column to domain_approvals...")
                            conn.execute(db.text("""
                                ALTER TABLE domain_approvals
                                ADD COLUMN auto_approved BOOLEAN DEFAULT FALSE
                            """))
                            conn.commit()
                            logger.info("auto_approved column added successfully")
                        else:
                            logger.info("auto_approved column already exists")

                        # Check and fix setup_tokens table schema
                        result = conn.execute(db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'setup_tokens' AND column_name = 'token_hash'
                        """))
                        if not result.fetchone():
                            logger.info("Fixing setup_tokens table schema...")
                            # Drop the old table and let SQLAlchemy recreate it with correct schema
                            conn.execute(db.text("DROP TABLE IF EXISTS setup_tokens CASCADE"))
                            conn.commit()
                            logger.info("Old setup_tokens table dropped, will be recreated")
                            # Recreate the table with correct schema
                            from models import SetupToken
                            SetupToken.__table__.create(db.engine, checkfirst=True)
                            logger.info("setup_tokens table recreated with correct schema")
                        else:
                            logger.info("setup_tokens table has correct schema")

                        # Check and add tenant_prefix column to auth_configs
                        result = conn.execute(db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'auth_configs' AND column_name = 'tenant_prefix'
                        """))
                        if not result.fetchone():
                            logger.info("Adding tenant_prefix column to auth_configs...")
                            conn.execute(db.text("""
                                ALTER TABLE auth_configs
                                ADD COLUMN tenant_prefix VARCHAR(10)
                            """))
                            conn.commit()
                            logger.info("tenant_prefix column added successfully")
                        else:
                            logger.info("tenant_prefix column already exists")

                        # Check and add decision_number column to architecture_decisions
                        result = conn.execute(db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'architecture_decisions' AND column_name = 'decision_number'
                        """))
                        if not result.fetchone():
                            logger.info("Adding decision_number column to architecture_decisions...")
                            conn.execute(db.text("""
                                ALTER TABLE architecture_decisions
                                ADD COLUMN decision_number INTEGER
                            """))
                            conn.commit()
                            logger.info("decision_number column added successfully")
                        else:
                            logger.info("decision_number column already exists")

                        # Check and add purpose column to setup_tokens
                        result = conn.execute(db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'setup_tokens' AND column_name = 'purpose'
                        """))
                        if not result.fetchone():
                            logger.info("Adding purpose column to setup_tokens...")
                            conn.execute(db.text("""
                                ALTER TABLE setup_tokens
                                ADD COLUMN purpose VARCHAR(50) DEFAULT 'initial_setup'
                            """))
                            conn.commit()
                            logger.info("purpose column added successfully")
                        else:
                            logger.info("purpose column already exists")

                        # Check and add email column to setup_tokens
                        result = conn.execute(db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'setup_tokens' AND column_name = 'email'
                        """))
                        if not result.fetchone():
                            logger.info("Adding email column to setup_tokens...")
                            conn.execute(db.text("""
                                ALTER TABLE setup_tokens
                                ADD COLUMN email VARCHAR(320)
                            """))
                            conn.commit()
                            logger.info("email column added successfully")
                        else:
                            logger.info("email column already exists")

                        # Check and add has_seen_admin_onboarding column to users
                        result = conn.execute(db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'users' AND column_name = 'has_seen_admin_onboarding'
                        """))
                        if not result.fetchone():
                            logger.info("Adding has_seen_admin_onboarding column to users...")
                            conn.execute(db.text("""
                                ALTER TABLE users
                                ADD COLUMN has_seen_admin_onboarding BOOLEAN DEFAULT FALSE
                            """))
                            conn.commit()
                            logger.info("has_seen_admin_onboarding column added successfully")
                        else:
                            logger.info("has_seen_admin_onboarding column already exists")

                        # Check and add email_verified column to users
                        result = conn.execute(db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'users' AND column_name = 'email_verified'
                        """))
                        if not result.fetchone():
                            logger.info("Adding email_verified column to users...")
                            conn.execute(db.text("""
                                ALTER TABLE users
                                ADD COLUMN email_verified BOOLEAN DEFAULT FALSE
                            """))
                            conn.commit()
                            logger.info("email_verified column added successfully")
                        else:
                            logger.info("email_verified column already exists")

                        # Check and add auth_type column to users
                        result = conn.execute(db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'users' AND column_name = 'auth_type'
                        """))
                        if not result.fetchone():
                            logger.info("Adding auth_type column to users...")
                            conn.execute(db.text("""
                                ALTER TABLE users
                                ADD COLUMN auth_type VARCHAR(20) DEFAULT 'local'
                            """))
                            conn.commit()
                            logger.info("auth_type column added successfully")
                        else:
                            logger.info("auth_type column already exists")

                        # === Deletion Controls Migrations (v1.5.2) ===

                        # Add deletion_expires_at to architecture_decisions
                        result = conn.execute(db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'architecture_decisions' AND column_name = 'deletion_expires_at'
                        """))
                        if not result.fetchone():
                            logger.info("Adding deletion_expires_at column to architecture_decisions...")
                            conn.execute(db.text("""
                                ALTER TABLE architecture_decisions
                                ADD COLUMN deletion_expires_at TIMESTAMP
                            """))
                            conn.commit()
                            logger.info("deletion_expires_at column added successfully")

                        # Add GDPR deletion fields to users
                        for col_name, col_type in [
                            ('deletion_requested_at', 'TIMESTAMP'),
                            ('deletion_scheduled_at', 'TIMESTAMP'),
                            ('deleted_at', 'TIMESTAMP'),
                            ('is_anonymized', 'BOOLEAN DEFAULT FALSE')
                        ]:
                            result = conn.execute(db.text(f"""
                                SELECT column_name FROM information_schema.columns
                                WHERE table_name = 'users' AND column_name = '{col_name}'
                            """))
                            if not result.fetchone():
                                logger.info(f"Adding {col_name} column to users...")
                                conn.execute(db.text(f"""
                                    ALTER TABLE users ADD COLUMN {col_name} {col_type}
                                """))
                                conn.commit()
                                logger.info(f"{col_name} column added successfully")

                        # Add deletion rate limiting fields to tenant_memberships
                        for col_name, col_type in [
                            ('deletion_rate_limited_at', 'TIMESTAMP'),
                            ('deletion_count_window_start', 'TIMESTAMP'),
                            ('deletion_count', 'INTEGER DEFAULT 0')
                        ]:
                            result = conn.execute(db.text(f"""
                                SELECT column_name FROM information_schema.columns
                                WHERE table_name = 'tenant_memberships' AND column_name = '{col_name}'
                            """))
                            if not result.fetchone():
                                logger.info(f"Adding {col_name} column to tenant_memberships...")
                                conn.execute(db.text(f"""
                                    ALTER TABLE tenant_memberships ADD COLUMN {col_name} {col_type}
                                """))
                                conn.commit()
                                logger.info(f"{col_name} column added successfully")

                        # Add soft-delete fields to tenants
                        for col_name, col_type in [
                            ('deleted_at', 'TIMESTAMP'),
                            ('deleted_by_admin', 'VARCHAR(255)'),
                            ('deletion_expires_at', 'TIMESTAMP')
                        ]:
                            result = conn.execute(db.text(f"""
                                SELECT column_name FROM information_schema.columns
                                WHERE table_name = 'tenants' AND column_name = '{col_name}'
                            """))
                            if not result.fetchone():
                                logger.info(f"Adding {col_name} column to tenants...")
                                conn.execute(db.text(f"""
                                    ALTER TABLE tenants ADD COLUMN {col_name} {col_type}
                                """))
                                conn.commit()
                                logger.info(f"{col_name} column added successfully")

                except Exception as migration_error:
                    logger.warning(f"Schema migration check failed (non-critical): {str(migration_error)}")
                logger.info("Schema migrations completed")

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

def set_session_expiry(is_admin=False):
    """Set session expiry based on user type (admin vs regular user)."""
    if is_admin:
        timeout_hours = SystemConfig.get_int(
            SystemConfig.KEY_ADMIN_SESSION_TIMEOUT_HOURS,
            default=SystemConfig.DEFAULT_ADMIN_SESSION_TIMEOUT
        )
    else:
        timeout_hours = SystemConfig.get_int(
            SystemConfig.KEY_USER_SESSION_TIMEOUT_HOURS,
            default=SystemConfig.DEFAULT_USER_SESSION_TIMEOUT
        )
    session['_expires_at'] = (datetime.utcnow() + timedelta(hours=timeout_hours)).isoformat()
    session.permanent = True


def is_session_expired():
    """Check if current session has expired."""
    expires_at = session.get('_expires_at')
    if not expires_at:
        # Legacy sessions without expiry - expire them immediately to force re-login
        # This ensures all users get the new session timeout settings
        return True
    try:
        expiry_time = datetime.fromisoformat(expires_at)
        return datetime.utcnow() > expiry_time
    except (ValueError, TypeError):
        return True  # Invalid expiry format - expire the session


@app.before_request
def check_session_expiry():
    """Check if session has expired and clear it if so."""
    if request.endpoint and request.endpoint.startswith('static'):
        return  # Skip static files

    if ('user_id' in session or 'master_id' in session) and is_session_expired():
        # Session has expired - clear it
        session.clear()
        if request.is_json:
            # API request - return 401
            return  # Let the login_required decorator handle it
        # Browser request - redirect will happen naturally


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


# ==================== Feedback & Sponsorship ====================

def _api_submit_feedback_impl():
    """Submit feedback from users.

    Rate limited to 5 requests per minute to prevent spam.
    All inputs are sanitized to prevent XSS and injection attacks.
    """
    from notifications import send_feedback_email
    from security import sanitize_name, sanitize_email, sanitize_text_field

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    feedback = data.get('feedback', '').strip()
    contact_consent = data.get('contact_consent', data.get('contactConsent', False))

    if not name or not email or not feedback:
        return jsonify({'error': 'Name, email, and feedback are required'}), 400

    # Sanitize inputs
    name = sanitize_name(name, max_length=100)
    email = sanitize_email(email)
    feedback = sanitize_text_field(feedback, max_length=5000)
    contact_consent = bool(contact_consent)

    if not email:
        return jsonify({'error': 'Invalid email address'}), 400

    if len(feedback) < 10:
        return jsonify({'error': 'Feedback must be at least 10 characters'}), 400

    # Get email config (use any enabled config)
    email_config = EmailConfig.query.filter_by(enabled=True).first()
    if not email_config:
        logger.warning("Feedback received but no email config available")
        return jsonify({'error': 'Email service temporarily unavailable'}), 503

    # Send the feedback email
    success = send_feedback_email(email_config, name, email, feedback, contact_consent=contact_consent)

    if success:
        logger.info(f"Feedback submitted successfully from {email}")
        return jsonify({'message': 'Thank you for your feedback! We will review it shortly.'})
    else:
        logger.error(f"Failed to send feedback email from {email}")
        return jsonify({'error': 'Failed to submit feedback. Please try again later.'}), 500


# Apply rate limiting if available (5 requests/minute to prevent spam)
if RATE_LIMITING_ENABLED:
    api_submit_feedback = app.route('/api/feedback', methods=['POST'])(
        limiter.limit("5 per minute")(_api_submit_feedback_impl)
    )
else:
    api_submit_feedback = app.route('/api/feedback', methods=['POST'])(
        _api_submit_feedback_impl
    )


def _api_submit_sponsorship_impl():
    """Submit sponsorship inquiry.

    Rate limited to 3 requests per minute to prevent spam.
    All inputs are sanitized to prevent XSS and injection attacks.
    """
    from notifications import send_sponsorship_inquiry_email
    from security import sanitize_name, sanitize_email, sanitize_text_field, sanitize_title

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    org_name = data.get('organisation_name', '').strip()
    contact_email = data.get('contact_email', '').strip()

    if not org_name or not contact_email:
        return jsonify({'error': 'Organisation name and contact email are required'}), 400

    # Get optional fields
    contact_name = data.get('contact_name', '').strip() or None
    area_of_interest = data.get('area_of_interest', '').strip() or None
    message = data.get('message', '').strip() or None

    # Sanitize all inputs
    org_name = sanitize_title(org_name, max_length=200)
    contact_email = sanitize_email(contact_email)
    if contact_name:
        contact_name = sanitize_name(contact_name, max_length=100)
    if area_of_interest:
        area_of_interest = sanitize_title(area_of_interest, max_length=100)
    if message:
        message = sanitize_text_field(message, max_length=2000)

    if not contact_email:
        return jsonify({'error': 'Invalid email address'}), 400

    # Get email config (use any enabled config)
    email_config = EmailConfig.query.filter_by(enabled=True).first()
    if not email_config:
        logger.warning("Sponsorship inquiry received but no email config available")
        return jsonify({'error': 'Email service temporarily unavailable'}), 503

    # Send the sponsorship inquiry email
    success = send_sponsorship_inquiry_email(
        email_config, org_name, contact_email,
        contact_name=contact_name,
        area_of_interest=area_of_interest,
        message=message
    )

    if success:
        logger.info(f"Sponsorship inquiry submitted from {org_name} ({contact_email})")
        return jsonify({'message': 'Thank you for reaching out! We will be in touch shortly.'})
    else:
        logger.error(f"Failed to send sponsorship inquiry email from {contact_email}")
        return jsonify({'error': 'Failed to submit inquiry. Please try again later.'}), 500


# Apply rate limiting if available (3 requests/minute to prevent spam)
if RATE_LIMITING_ENABLED:
    api_submit_sponsorship = app.route('/api/sponsorship', methods=['POST'])(
        limiter.limit("3 per minute")(_api_submit_sponsorship_impl)
    )
else:
    api_submit_sponsorship = app.route('/api/sponsorship', methods=['POST'])(
        _api_submit_sponsorship_impl
    )


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
@track_endpoint('auth_local')
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
        set_session_expiry(is_admin=True)  # 1 hour default for super admin
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

    data = request.get_json() or {}
    # Sanitize email input to prevent injection attacks
    email = sanitize_email(data.get('email', ''))
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
    set_session_expiry(is_admin=False)  # 8 hours default for regular users
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
    data = request.get_json() or {}
    password = data.get('password', '')
    current_password = data.get('current_password', '')

    # Password policy validation
    if not password or len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    import re
    if not re.search(r'[A-Z]', password):
        return jsonify({'error': 'Password must contain at least one uppercase letter'}), 400
    if not re.search(r'[a-z]', password):
        return jsonify({'error': 'Password must contain at least one lowercase letter'}), 400
    if not re.search(r'\d', password):
        return jsonify({'error': 'Password must contain at least one number'}), 400

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
        set_session_expiry(is_admin=False)  # 8 hours default for regular users

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
@track_endpoint('api_decisions_list')
def api_list_decisions():
    """List all architecture decisions for the user's domain."""
    # SECURITY: Master accounts should NOT access tenant data
    # This prevents a compromised super admin from accessing sensitive business data
    if is_master_account():
        return jsonify({'error': 'Super admin accounts cannot access tenant data'}), 403

    decisions = ArchitectureDecision.query.filter_by(
        domain=g.current_user.sso_domain,
        deleted_at=None
    ).order_by(ArchitectureDecision.id.desc()).all()
    return jsonify([d.to_dict() for d in decisions])


@app.route('/api/decisions', methods=['POST'])
@login_required
@track_endpoint('api_decisions_create')
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

    # Get or generate tenant prefix and next decision number
    domain = g.current_user.sso_domain
    auth_config = AuthConfig.query.filter_by(domain=domain).first()

    # Ensure tenant has a prefix
    if auth_config and not auth_config.tenant_prefix:
        auth_config.tenant_prefix = AuthConfig.generate_unique_prefix()
        db.session.flush()

    # Get next decision number for this domain
    max_number = db.session.query(db.func.max(ArchitectureDecision.decision_number)).filter(
        ArchitectureDecision.domain == domain
    ).scalar() or 0
    next_number = max_number + 1

    decision = ArchitectureDecision(
        title=sanitized['title'],
        context=sanitized['context'],
        decision=sanitized['decision'],
        status=status,
        consequences=sanitized['consequences'],
        decision_number=next_number,
        domain=domain,  # SECURITY: Always use authenticated user's domain
        created_by_id=g.current_user.id,
        updated_by_id=g.current_user.id
    )

    # Handle infrastructure associations
    infrastructure_ids = data.get('infrastructure_ids', [])
    if infrastructure_ids:
        infrastructure_items = ITInfrastructure.query.filter(
            ITInfrastructure.id.in_(infrastructure_ids),
            ITInfrastructure.domain == domain
        ).all()
        decision.infrastructure = infrastructure_items

    db.session.add(decision)
    db.session.commit()

    # Send notifications - try domain-specific config first, fall back to system config
    email_config = EmailConfig.query.filter_by(domain=g.current_user.sso_domain, enabled=True).first()
    if not email_config:
        email_config = EmailConfig.query.filter_by(domain='system', enabled=True).first()
    notify_subscribers_new_decision(db, decision, email_config)

    return jsonify(decision.to_dict()), 201


@app.route('/api/decisions/<int:decision_id>', methods=['GET'])
@login_required
def api_get_decision(decision_id):
    """Get a single architecture decision with its history."""
    # SECURITY: Master accounts should NOT access tenant data
    if is_master_account():
        return jsonify({'error': 'Super admin accounts cannot access tenant data'}), 403

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

    # Sanitize input data to prevent XSS attacks
    sanitized, errors = sanitize_request_data(data, {
        'title': {'type': 'title', 'max_length': 255},
        'context': {'type': 'text', 'max_length': 50000},
        'decision': {'type': 'text', 'max_length': 50000},
        'consequences': {'type': 'text', 'max_length': 50000},
        'status': {'type': 'string', 'max_length': 50},
        'change_reason': {'type': 'text', 'max_length': 500},
    })

    if errors:
        return jsonify({'error': errors[0]}), 400

    # Validate status if provided
    if 'status' in sanitized and sanitized['status'] not in ArchitectureDecision.VALID_STATUSES:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(ArchitectureDecision.VALID_STATUSES)}'}), 400

    # Check if there are actual changes
    has_changes = False
    status_changed = False
    old_status = decision.status

    for field in ['title', 'context', 'decision', 'status', 'consequences']:
        if field in sanitized and sanitized[field] != getattr(decision, field):
            has_changes = True
            if field == 'status':
                status_changed = True
            break

    if not has_changes:
        return jsonify(decision.to_dict_with_history())

    # Save current state to history before updating
    change_reason = sanitized.get('change_reason', None)
    save_history(decision, change_reason, g.current_user)

    # Update fields with sanitized data
    if 'title' in sanitized:
        decision.title = sanitized['title']
    if 'context' in sanitized:
        decision.context = sanitized['context']
    if 'decision' in sanitized:
        decision.decision = sanitized['decision']
    if 'status' in sanitized:
        decision.status = sanitized['status']
    if 'consequences' in sanitized:
        decision.consequences = sanitized['consequences']

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

    # Send notifications - try domain-specific config first, fall back to system config
    email_config = EmailConfig.query.filter_by(domain=g.current_user.sso_domain, enabled=True).first()
    if not email_config:
        email_config = EmailConfig.query.filter_by(domain='system', enabled=True).first()
    notify_subscribers_decision_updated(db, decision, email_config, change_reason, status_changed)

    return jsonify(decision.to_dict_with_history())


@app.route('/api/decisions/<int:decision_id>', methods=['DELETE'])
@login_required
def api_delete_decision(decision_id):
    """Soft delete an architecture decision with retention window and rate limiting.

    Requirements per deletion-controls.md:
    - Only ADMIN/STEWARD can delete (PROVISIONAL_ADMIN if tenant is BOOTSTRAP)
    - Regular users cannot delete decisions
    - Rate limiting: >3 deletions in 5 minutes triggers lockout
    - 30-day retention window before permanent deletion
    """
    # Master accounts cannot delete decisions
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot delete decisions. Please log in with an SSO account.'}), 403

    user = g.current_user
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()

    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Check role - only ADMIN/STEWARD can delete (PROVISIONAL_ADMIN in BOOTSTRAP state)
    membership = TenantMembership.query.filter_by(
        user_id=user.id,
        tenant_id=tenant.id
    ).first()

    if not membership:
        return jsonify({'error': 'You are not a member of this tenant'}), 403

    allowed_roles = [GlobalRole.ADMIN, GlobalRole.STEWARD]
    if tenant.maturity_state == MaturityState.BOOTSTRAP:
        allowed_roles.append(GlobalRole.PROVISIONAL_ADMIN)

    if membership.global_role not in allowed_roles:
        return jsonify({
            'error': 'Permission denied',
            'message': 'Only admins and stewards can delete decisions'
        }), 403

    # Check if user is rate-limited for deletions
    if membership.deletion_rate_limited_at:
        # Rate limit lasts for 1 hour
        if datetime.utcnow() < membership.deletion_rate_limited_at + timedelta(hours=1):
            return jsonify({
                'error': 'Deletion rate limited',
                'message': 'Your deletion privileges have been temporarily suspended due to multiple rapid deletions. Please contact an administrator.',
                'rate_limited_until': (membership.deletion_rate_limited_at + timedelta(hours=1)).isoformat()
            }), 429

    # Rate limiting check: >3 deletions in 5 minutes triggers lockout
    RATE_LIMIT_COUNT = 3
    RATE_LIMIT_WINDOW_MINUTES = 5

    now = datetime.utcnow()
    window_start = membership.deletion_count_window_start

    # Reset window if expired or not set
    if not window_start or (now - window_start) > timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES):
        membership.deletion_count_window_start = now
        membership.deletion_count = 0
        window_start = now

    # Check if already at limit
    if membership.deletion_count >= RATE_LIMIT_COUNT:
        # Trigger rate limiting
        membership.deletion_rate_limited_at = now
        db.session.commit()

        # Notify tenant admins (async notification would be better)
        # For now, just log it
        log_admin_action(
            tenant_id=tenant.id,
            actor_user_id=user.id,
            action_type='rate_limit_triggered',
            target_entity='user',
            target_id=user.id,
            details={
                'reason': 'excessive_deletions',
                'count': membership.deletion_count,
                'window_minutes': RATE_LIMIT_WINDOW_MINUTES
            }
        )

        return jsonify({
            'error': 'Deletion rate limited',
            'message': 'You have deleted too many decisions in a short period. Your deletion privileges have been temporarily suspended for security.',
            'rate_limited_until': (now + timedelta(hours=1)).isoformat()
        }), 429

    # Get the decision
    decision = ArchitectureDecision.query.filter_by(
        id=decision_id,
        domain=user.sso_domain,
        deleted_at=None
    ).first_or_404()

    # Soft delete with retention window
    deletion_time = datetime.utcnow()
    retention_days = 30
    decision.deleted_at = deletion_time
    decision.deleted_by_id = user.id
    decision.deletion_expires_at = deletion_time + timedelta(days=retention_days)

    # Update deletion count for rate limiting
    membership.deletion_count = (membership.deletion_count or 0) + 1

    # Log the deletion
    log_admin_action(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action_type=AuditLog.ACTION_DELETE,
        target_entity='decision',
        target_id=decision.id,
        details={
            'title': decision.title,
            'retention_days': retention_days,
            'deletion_expires_at': decision.deletion_expires_at.isoformat()
        }
    )

    db.session.commit()

    return jsonify({
        'message': 'Decision deleted successfully',
        'deletion_details': {
            'deleted_at': deletion_time.isoformat(),
            'expires_at': decision.deletion_expires_at.isoformat(),
            'retention_days': retention_days,
            'note': f'This decision can be restored within {retention_days} days by an administrator.'
        }
    })


@app.route('/api/decisions/<int:decision_id>/history', methods=['GET'])
@login_required
def api_get_decision_history(decision_id):
    """Get the update history for a decision."""
    # SECURITY: Master accounts should NOT access tenant data
    if is_master_account():
        return jsonify({'error': 'Super admin accounts cannot access tenant data'}), 403

    decision = ArchitectureDecision.query.filter_by(
        id=decision_id,
        domain=g.current_user.sso_domain
    ).first_or_404()

    history = DecisionHistory.query.filter_by(decision_id=decision_id).order_by(DecisionHistory.changed_at.desc()).all()
    return jsonify([h.to_dict() for h in history])


# ==================== API Routes - User ====================

@app.route('/api/user/me', methods=['GET'])
@track_endpoint('api_user_me')
def api_get_current_user():
    """Get current user info. Supports both full sessions and setup tokens."""
    from auth import validate_setup_token

    # Check for setup token first (incomplete account during credential setup)
    setup_user, _ = validate_setup_token()
    if setup_user:
        # Return user info with setup_mode flag
        user_dict = setup_user.to_dict()
        user_dict['setup_mode'] = True
        return jsonify(user_dict)

    # Check for regular session
    if session.get('is_master') and session.get('master_id'):
        from models import MasterAccount
        master = MasterAccount.query.get(session.get('master_id'))
        if master:
            return jsonify(master.to_dict())

    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    user = User.query.get(session.get('user_id'))
    if not user:
        session.clear()
        return jsonify({'error': 'Authentication required'}), 401

    # Get user dict and add v1.5 membership info
    user_dict = user.to_dict()

    # Add membership and role info for v1.5
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if tenant:
        membership = user.get_membership(tenant_id=tenant.id)
        if membership:
            user_dict['global_role'] = membership.global_role.value
            user_dict['membership'] = {
                'id': membership.id,
                'tenant_id': membership.tenant_id,
                'global_role': membership.global_role.value,
                'joined_at': membership.joined_at.isoformat() if membership.joined_at else None
            }
            # Update is_admin based on membership role for v1.5 governance
            user_dict['is_admin'] = membership.is_admin
            # Add tenant maturity info for UI to decide what to show
            user_dict['tenant_info'] = {
                'id': tenant.id,
                'domain': tenant.domain,
                'name': tenant.name,
                'maturity_state': tenant.maturity_state.value,
                'admin_count': TenantMembership.query.filter_by(
                    tenant_id=tenant.id,
                    global_role=GlobalRole.ADMIN
                ).count(),
                'steward_count': TenantMembership.query.filter_by(
                    tenant_id=tenant.id,
                    global_role=GlobalRole.STEWARD
                ).count()
            }

    return jsonify(user_dict)


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

    data = request.get_json() or {}

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


@app.route('/api/user/dismiss-admin-onboarding', methods=['POST'])
@login_required
def api_dismiss_admin_onboarding():
    """Mark the admin onboarding modal as seen."""
    # Master accounts don't need this
    if is_master_account():
        return jsonify({'error': 'Not applicable for master accounts'}), 400

    user = g.current_user
    if not user.is_admin:
        return jsonify({'error': 'Not an admin'}), 403

    user.has_seen_admin_onboarding = True
    db.session.commit()

    return jsonify({'message': 'Admin onboarding dismissed', 'user': user.to_dict()})


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

    # Sanitize inputs to prevent XSS attacks
    domain = sanitize_title(data['domain'], max_length=255).lower()
    provider_name = sanitize_title(data['provider_name'], max_length=100)
    client_id = sanitize_title(data['client_id'], max_length=500)
    discovery_url = sanitize_title(data['discovery_url'], max_length=1000)

    # Tenant admins can only create SSO for their own domain
    if not is_master_account():
        if domain != g.current_user.sso_domain:
            return jsonify({'error': 'You can only configure SSO for your own domain'}), 403

    # Check if domain already exists
    existing = SSOConfig.query.filter_by(domain=domain).first()
    if existing:
        return jsonify({'error': 'SSO configuration for this domain already exists'}), 400

    # Validate discovery URL
    oidc_config = get_oidc_config(discovery_url)
    if not oidc_config:
        return jsonify({'error': 'Invalid discovery URL or unable to reach SSO provider'}), 400

    config = SSOConfig(
        domain=domain,
        provider_name=provider_name,
        client_id=client_id,
        client_secret=data['client_secret'],  # Don't sanitize secrets - they may contain special chars
        discovery_url=discovery_url,
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

    data = request.get_json() or {}

    # Sanitize inputs to prevent XSS attacks
    if 'provider_name' in data:
        config.provider_name = sanitize_title(data['provider_name'], max_length=100)
    if 'client_id' in data:
        config.client_id = sanitize_title(data['client_id'], max_length=500)
    if 'client_secret' in data and data['client_secret']:
        config.client_secret = data['client_secret']  # Don't sanitize secrets
    if 'discovery_url' in data:
        # Sanitize and validate new discovery URL
        sanitized_url = sanitize_title(data['discovery_url'], max_length=1000)
        oidc_config = get_oidc_config(sanitized_url)
        if not oidc_config:
            return jsonify({'error': 'Invalid discovery URL or unable to reach SSO provider'}), 400
        config.discovery_url = sanitized_url
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
    """Create or update email configuration (admin only).

    Security: SMTP password is encrypted before storage and can never be retrieved.
    Once saved, the only option is to provide a new password.
    """
    from crypto import encrypt_password

    data = request.get_json()

    required_fields = ['smtp_server', 'smtp_port', 'smtp_username', 'from_email']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Sanitize inputs to prevent XSS attacks
    smtp_server = sanitize_title(data['smtp_server'], max_length=255)
    smtp_username = sanitize_title(data['smtp_username'], max_length=255)
    from_email_sanitized = sanitize_email(data['from_email'])
    from_name = sanitize_name(data.get('from_name', 'Architecture Decisions'), max_length=100)

    if not from_email_sanitized:
        return jsonify({'error': 'Invalid from_email address'}), 400

    config = EmailConfig.query.filter_by(domain=g.current_user.sso_domain).first()

    if not config:
        if not data.get('smtp_password'):
            return jsonify({'error': 'SMTP password is required for new configuration'}), 400

        # Encrypt the password before storing
        encrypted_password = encrypt_password(data['smtp_password'])

        config = EmailConfig(
            domain=g.current_user.sso_domain,
            smtp_server=smtp_server,
            smtp_port=int(data['smtp_port']),
            smtp_username=smtp_username,
            smtp_password=encrypted_password,
            from_email=from_email_sanitized,
            from_name=from_name,
            use_tls=data.get('use_tls', True),
            enabled=data.get('enabled', True)
        )
        db.session.add(config)
    else:
        config.smtp_server = smtp_server
        config.smtp_port = int(data['smtp_port'])
        config.smtp_username = smtp_username
        if data.get('smtp_password'):
            # Encrypt the new password before storing
            config.smtp_password = encrypt_password(data['smtp_password'])
        config.from_email = from_email_sanitized
        config.from_name = from_name
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

    # Sanitize inputs to prevent XSS attacks
    smtp_server = sanitize_title(data['smtp_server'], max_length=255)
    from_email_sanitized = sanitize_email(data['from_email'])
    from_name = sanitize_name(data.get('from_name', 'Architecture Decisions'), max_length=100)

    if not from_email_sanitized:
        return jsonify({'error': 'Invalid from_email address'}), 400

    # Validate Key Vault credentials are available
    username, password = keyvault_client.get_smtp_credentials()
    if not username or not password:
        return jsonify({'error': 'SMTP credentials not configured in Azure Key Vault. Please contact system administrator.'}), 400

    config = EmailConfig.query.filter_by(domain='system').first()

    if not config:
        config = EmailConfig(domain='system')
        db.session.add(config)

    config.smtp_server = smtp_server
    config.smtp_port = int(data['smtp_port'])
    # Store placeholder values - actual credentials come from Key Vault
    config.smtp_username = 'from-keyvault'
    config.smtp_password = 'from-keyvault'
    config.from_email = from_email_sanitized
    config.from_name = from_name
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


# ==================== API Routes - System Settings (Super Admin) ====================

@app.route('/api/admin/settings/session', methods=['GET'])
@master_required
def api_get_session_settings():
    """Get session timeout settings (super admin only)."""
    return jsonify({
        'admin_session_timeout_hours': SystemConfig.get_int(
            SystemConfig.KEY_ADMIN_SESSION_TIMEOUT_HOURS,
            default=SystemConfig.DEFAULT_ADMIN_SESSION_TIMEOUT
        ),
        'user_session_timeout_hours': SystemConfig.get_int(
            SystemConfig.KEY_USER_SESSION_TIMEOUT_HOURS,
            default=SystemConfig.DEFAULT_USER_SESSION_TIMEOUT
        ),
        'defaults': {
            'admin_session_timeout_hours': SystemConfig.DEFAULT_ADMIN_SESSION_TIMEOUT,
            'user_session_timeout_hours': SystemConfig.DEFAULT_USER_SESSION_TIMEOUT
        }
    })


@app.route('/api/admin/settings/session', methods=['POST', 'PUT'])
@master_required
def api_save_session_settings():
    """Update session timeout settings (super admin only)."""
    data = request.get_json() or {}

    admin_timeout = data.get('admin_session_timeout_hours')
    user_timeout = data.get('user_session_timeout_hours')

    # Validate values
    if admin_timeout is not None:
        try:
            admin_timeout = int(admin_timeout)
            if admin_timeout < 1 or admin_timeout > 24:
                return jsonify({'error': 'Admin session timeout must be between 1 and 24 hours'}), 400
            SystemConfig.set(
                SystemConfig.KEY_ADMIN_SESSION_TIMEOUT_HOURS,
                admin_timeout,
                description='Session timeout in hours for super admin accounts'
            )
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid admin session timeout value'}), 400

    if user_timeout is not None:
        try:
            user_timeout = int(user_timeout)
            if user_timeout < 1 or user_timeout > 168:  # Max 1 week
                return jsonify({'error': 'User session timeout must be between 1 and 168 hours'}), 400
            SystemConfig.set(
                SystemConfig.KEY_USER_SESSION_TIMEOUT_HOURS,
                user_timeout,
                description='Session timeout in hours for regular user accounts'
            )
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid user session timeout value'}), 400

    return jsonify({
        'message': 'Session settings updated successfully',
        'admin_session_timeout_hours': SystemConfig.get_int(
            SystemConfig.KEY_ADMIN_SESSION_TIMEOUT_HOURS,
            default=SystemConfig.DEFAULT_ADMIN_SESSION_TIMEOUT
        ),
        'user_session_timeout_hours': SystemConfig.get_int(
            SystemConfig.KEY_USER_SESSION_TIMEOUT_HOURS,
            default=SystemConfig.DEFAULT_USER_SESSION_TIMEOUT
        )
    })


@app.route('/api/admin/settings/licensing', methods=['GET'])
@master_required
def api_get_licensing_settings():
    """Get licensing settings (super admin only)."""
    return jsonify({
        'max_users_per_tenant': SystemConfig.get_int(
            SystemConfig.KEY_MAX_USERS_PER_TENANT,
            default=SystemConfig.DEFAULT_MAX_USERS_PER_TENANT
        ),
        'defaults': {
            'max_users_per_tenant': SystemConfig.DEFAULT_MAX_USERS_PER_TENANT
        }
    })


@app.route('/api/admin/settings/licensing', methods=['POST', 'PUT'])
@master_required
def api_save_licensing_settings():
    """Update licensing settings (super admin only)."""
    data = request.get_json() or {}

    max_users = data.get('max_users_per_tenant')

    if max_users is not None:
        try:
            max_users = int(max_users)
            if max_users < 0 or max_users > 10000:
                return jsonify({'error': 'Max users per tenant must be between 0 and 10000 (0 = unlimited)'}), 400
            SystemConfig.set(
                SystemConfig.KEY_MAX_USERS_PER_TENANT,
                max_users,
                description='Maximum users allowed per tenant (0 = unlimited)'
            )
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid max users value'}), 400

    return jsonify({
        'message': 'Licensing settings updated successfully',
        'max_users_per_tenant': SystemConfig.get_int(
            SystemConfig.KEY_MAX_USERS_PER_TENANT,
            default=SystemConfig.DEFAULT_MAX_USERS_PER_TENANT
        )
    })


@app.route('/api/admin/settings/analytics', methods=['GET'])
@master_required
def api_get_analytics_settings():
    """Get analytics settings (super admin only)."""
    from analytics import get_config_for_api
    return jsonify(get_config_for_api())


@app.route('/api/admin/settings/analytics', methods=['POST', 'PUT'])
@master_required
def api_save_analytics_settings():
    """Update analytics settings (super admin only)."""
    import json as json_lib
    from analytics import invalidate_cache, DEFAULT_EVENT_MAPPINGS

    data = request.get_json() or {}

    # Update enabled flag
    if 'enabled' in data:
        enabled = bool(data['enabled'])
        SystemConfig.set(
            SystemConfig.KEY_ANALYTICS_ENABLED,
            'true' if enabled else 'false',
            description='Enable/disable PostHog analytics'
        )

    # Update host
    if 'host' in data:
        host = sanitize_text_field(data['host'], max_length=200)
        if host and host.startswith('http'):
            SystemConfig.set(
                SystemConfig.KEY_ANALYTICS_HOST,
                host,
                description='PostHog host URL'
            )

    # Update person profiling
    if 'person_profiling' in data:
        person_profiling = bool(data['person_profiling'])
        SystemConfig.set(
            SystemConfig.KEY_ANALYTICS_PERSON_PROFILING,
            'true' if person_profiling else 'false',
            description='Enable/disable person profile creation in PostHog'
        )

    # Update exception capture
    if 'exception_capture' in data:
        exception_capture = bool(data['exception_capture'])
        SystemConfig.set(
            SystemConfig.KEY_ANALYTICS_EXCEPTION_CAPTURE,
            'true' if exception_capture else 'false',
            description='Enable/disable exception capture to PostHog'
        )

    # Update event mappings
    if 'event_mappings' in data:
        mappings = data['event_mappings']
        if isinstance(mappings, dict):
            # Validate all keys exist in defaults
            valid_mappings = {}
            for key, value in mappings.items():
                if key in DEFAULT_EVENT_MAPPINGS:
                    valid_mappings[key] = sanitize_text_field(value, max_length=100) if value else DEFAULT_EVENT_MAPPINGS[key]
            SystemConfig.set(
                SystemConfig.KEY_ANALYTICS_EVENT_MAPPINGS,
                json_lib.dumps(valid_mappings),
                description='Custom event name mappings for PostHog'
            )

    # Invalidate cache to pick up new settings
    invalidate_cache()

    return jsonify({
        'message': 'Analytics settings updated successfully'
    })


@app.route('/api/admin/settings/analytics/api-key', methods=['PUT'])
@master_required
def api_save_analytics_api_key():
    """Save analytics API key (super admin only).

    For self-hosted deployments that don't use Key Vault.
    In cloud deployments, the key should be in Key Vault.
    """
    from analytics import invalidate_cache

    data = request.get_json() or {}
    api_key = data.get('api_key')

    if not api_key:
        return jsonify({'error': 'API key is required'}), 400

    # Basic validation (PostHog keys start with 'phc_')
    if not api_key.startswith('phc_'):
        return jsonify({'error': 'Invalid PostHog API key format. Keys should start with "phc_"'}), 400

    # Store in SystemConfig (for self-hosted deployments)
    SystemConfig.set(
        SystemConfig.KEY_ANALYTICS_API_KEY,
        api_key,
        description='PostHog API key (for self-hosted deployments)'
    )

    # Invalidate cache to pick up new key
    invalidate_cache()

    return jsonify({
        'message': 'Analytics API key saved successfully'
    })


@app.route('/api/admin/settings/analytics/test', methods=['POST'])
@master_required
def api_test_analytics():
    """Send a test event to PostHog (super admin only)."""
    from analytics import _get_analytics_config, invalidate_cache

    # Force config refresh
    invalidate_cache()
    config = _get_analytics_config()

    if not config['api_key']:
        return jsonify({'error': 'No API key configured. Please set an API key first.'}), 400

    if not config['posthog_client']:
        return jsonify({'error': 'PostHog client not initialized. Check API key and host configuration.'}), 400

    try:
        # Send a test event
        config['posthog_client'].capture(
            distinct_id='master_admin',
            event='analytics_test_event',
            properties={
                'test': True,
                'source': 'admin_settings_test',
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        # Flush to ensure event is sent immediately
        config['posthog_client'].flush()

        return jsonify({
            'message': 'Test event sent successfully! Check your PostHog dashboard.',
            'event_name': 'analytics_test_event',
            'host': config['host']
        })
    except Exception as e:
        logger.error(f"Failed to send test analytics event: {e}")
        return jsonify({'error': f'Failed to send test event: {str(e)}'}), 500


@app.route('/api/admin/settings/analytics/reset-mappings', methods=['POST'])
@master_required
def api_reset_analytics_mappings():
    """Reset event mappings to defaults (super admin only)."""
    from analytics import invalidate_cache, DEFAULT_EVENT_MAPPINGS
    import json as json_lib

    # Clear the custom mappings
    SystemConfig.set(
        SystemConfig.KEY_ANALYTICS_EVENT_MAPPINGS,
        json_lib.dumps(DEFAULT_EVENT_MAPPINGS),
        description='Custom event name mappings for PostHog'
    )

    # Invalidate cache
    invalidate_cache()

    return jsonify({
        'message': 'Event mappings reset to defaults',
        'event_mappings': DEFAULT_EVENT_MAPPINGS
    })


def get_tenant_user_count(domain):
    """Get the current user count for a tenant."""
    # Try v1.5 model first (TenantMembership)
    tenant = Tenant.query.filter_by(domain=domain).first()
    if tenant:
        return tenant.get_member_count()

    # Fallback to legacy model (User.sso_domain)
    return User.query.filter_by(sso_domain=domain).count()


def can_tenant_accept_users(domain, count=1):
    """Check if a tenant can accept more users.

    Args:
        domain: The tenant domain
        count: Number of users to add (default 1)

    Returns:
        tuple: (can_accept: bool, message: str, current_count: int, max_allowed: int)
    """
    max_users = SystemConfig.get_int(
        SystemConfig.KEY_MAX_USERS_PER_TENANT,
        default=SystemConfig.DEFAULT_MAX_USERS_PER_TENANT
    )

    # 0 means unlimited
    if max_users == 0:
        return (True, 'Unlimited users allowed', 0, 0)

    current_count = get_tenant_user_count(domain)

    if current_count + count > max_users:
        return (
            False,
            f'Tenant has reached the maximum user limit of {max_users}. Current users: {current_count}.',
            current_count,
            max_users
        )

    return (True, 'User limit not reached', current_count, max_users)


@app.route('/api/tenants/<domain>/limits', methods=['GET'])
@master_required
def api_get_tenant_limits(domain):
    """Get tenant limit status (super admin only)."""
    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    can_accept, message, current_count, max_allowed = can_tenant_accept_users(domain)

    return jsonify({
        'domain': domain,
        'user_count': current_count,
        'max_users_per_tenant': max_allowed,
        'can_accept_users': can_accept,
        'message': message,
        'remaining_slots': max(0, max_allowed - current_count) if max_allowed > 0 else -1
    })


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

    data = request.get_json() or {}
    user.is_admin = bool(data.get('is_admin', False))

    db.session.commit()

    return jsonify(user.to_dict())


# ==================== API Routes - Master Account ====================

@app.route('/api/master/password', methods=['PUT'])
@master_required
def api_change_master_password():
    """Change master account password."""
    data = request.get_json() or {}

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


def _api_get_tenant_status_impl(domain):
    """Get tenant status - whether users exist and auth configuration.

    Security note: Rate-limited to prevent domain enumeration attacks.
    """
    domain = domain.lower()

    # Check if this is a public/free email domain (gmail, yahoo, etc.)
    if DomainApproval.is_public_domain(domain):
        return jsonify({
            'error': f'{domain} is a public email provider. Please use your work email address.',
            'is_public_domain': True
        }), 400

    # Check if this is a disposable/temporary email domain
    if DomainApproval.is_disposable_domain(domain):
        return jsonify({
            'error': 'Disposable email addresses are not allowed. Please use your work email address.',
            'is_disposable_domain': True
        }), 400

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


# Apply rate limiting if available (20 requests/minute - slightly more lenient for tenant checks)
if RATE_LIMITING_ENABLED:
    api_get_tenant_status = app.route('/api/auth/tenant/<domain>', methods=['GET'])(
        limiter.limit("20 per minute")(_api_get_tenant_status_impl)
    )
else:
    api_get_tenant_status = app.route('/api/auth/tenant/<domain>', methods=['GET'])(
        _api_get_tenant_status_impl
    )


def _api_check_user_exists_impl(email):
    """Check if a user exists by email.

    Security note: This endpoint is rate-limited to prevent account enumeration.
    Rate limit: 10 requests per minute per IP address.

    This is a balance between security and usability:
    - Legitimate users may try 2-5 times when troubleshooting login issues
    - Corporate users behind NAT may share IP addresses
    - Attackers attempting bulk enumeration will be significantly slowed
    """
    email = email.lower()

    # Log the request for security monitoring (only log domain, not full email for privacy)
    domain = email.split('@')[1] if '@' in email else 'invalid'
    logger.info(f"User existence check for domain: {domain}")

    user = User.query.filter_by(email=email).first()

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


# Apply rate limiting if available (10 requests/minute to prevent account enumeration)
if RATE_LIMITING_ENABLED:
    api_check_user_exists = app.route('/api/auth/user-exists/<email>', methods=['GET'])(
        limiter.limit("10 per minute")(_api_check_user_exists_impl)
    )
else:
    api_check_user_exists = app.route('/api/auth/user-exists/<email>', methods=['GET'])(
        _api_check_user_exists_impl
    )


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
    data = request.get_json() or {}

    # Sanitize inputs to prevent XSS and injection attacks
    email = sanitize_email(data.get('email', ''))
    name = sanitize_name(data.get('name', ''), max_length=255)
    purpose = data.get('purpose', 'signup')  # signup, access_request, login
    reason = sanitize_text_field(data.get('reason', ''), max_length=1000)  # For access requests

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    if '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400

    domain = email.split('@')[1].lower()

    # Check if this is a public/free email domain (gmail, yahoo, etc.)
    if DomainApproval.is_public_domain(domain):
        return jsonify({
            'error': f'{domain} is a public email provider. Please use your work email address.',
            'is_public_domain': True
        }), 400

    # Check if this is a disposable/temporary email domain
    if DomainApproval.is_disposable_domain(domain):
        return jsonify({
            'error': 'Disposable email addresses are not allowed. Please use your work email address.',
            'is_disposable_domain': True
        }), 400

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

    # Create new verification token (2-hour validity per PLAN-v1.4)
    token = generate_verification_token()
    expires_at = datetime.utcnow() + timedelta(hours=2)

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


@app.route('/api/auth/resend-verification', methods=['POST'])
def api_resend_verification():
    """Resend email verification link for pending verifications.

    This endpoint allows users to request a new verification email if their
    previous one expired or they didn't receive it.
    """
    data = request.get_json() or {}
    email = data.get('email', '').lower().strip()

    if not email or '@' not in email:
        return jsonify({'error': 'Valid email address is required'}), 400

    # Generic success message (always return this to prevent email enumeration)
    success_message = 'If a pending verification exists for this email, a new link has been sent.'

    # Check for existing pending verification
    pending = EmailVerification.query.filter(
        EmailVerification.email == email,
        EmailVerification.verified_at.is_(None)
    ).order_by(EmailVerification.created_at.desc()).first()

    if not pending:
        # Don't reveal that no verification exists
        logger.info(f"Resend verification requested for email without pending verification: {email}")
        return jsonify({'message': success_message})

    # Rate limiting: Check for recent verification emails (2 minutes)
    if pending.created_at > datetime.utcnow() - timedelta(minutes=2):
        logger.info(f"Rate limited resend verification for: {email}")
        return jsonify({'message': success_message})

    # Create new token, invalidate old one
    old_purpose = pending.purpose
    old_name = pending.name
    old_domain = pending.domain
    old_reason = pending.access_request_reason

    # Delete old pending verification
    db.session.delete(pending)
    db.session.commit()

    # Create new verification token (2-hour validity)
    token = generate_verification_token()
    expires_at = datetime.utcnow() + timedelta(hours=2)

    new_verification = EmailVerification(
        email=email,
        name=old_name,
        token=token,
        purpose=old_purpose,
        domain=old_domain,
        expires_at=expires_at,
        access_request_reason=old_reason
    )
    db.session.add(new_verification)
    db.session.commit()

    # Send verification email
    email_sent = send_verification_email(email, token, old_purpose, old_domain)

    if email_sent:
        logger.info(f"Resent verification email to: {email}")
    else:
        logger.error(f"Failed to resend verification email to: {email}")

    # Always return success to prevent email enumeration
    return jsonify({'message': success_message})


@app.route('/api/auth/direct-signup', methods=['POST'])
def api_direct_signup():
    """Direct signup (when email verification is disabled)."""
    # Check if email verification is disabled
    verification_required = SystemConfig.get_bool(SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED, default=True)
    if verification_required:
        return jsonify({'error': 'Email verification is required. Please use the standard signup flow.'}), 403

    data = request.get_json() or {}
    # Sanitize inputs to prevent XSS and injection attacks
    email = sanitize_email(data.get('email', ''))
    name = sanitize_name(data.get('name', ''), max_length=255)
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

    # Check if this is a public/free email domain (gmail, yahoo, etc.)
    if DomainApproval.is_public_domain(domain):
        return jsonify({
            'error': f'{domain} is a public email provider. Please use your work email address.',
            'is_public_domain': True
        }), 400

    # Check if this is a disposable/temporary email domain
    if DomainApproval.is_disposable_domain(domain):
        return jsonify({
            'error': 'Disposable email addresses are not allowed. Please use your work email address.',
            'is_disposable_domain': True
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

    # Check domain approval status
    domain_approval = DomainApproval.query.filter_by(domain=domain).first()

    if domain_approval and domain_approval.status == 'rejected':
        return jsonify({
            'error': 'Your organization domain has been rejected.',
            'domain_rejected': True,
            'reason': domain_approval.rejection_reason
        }), 403

    if not domain_approval:
        # New corporate domain - auto-approve since we already blocked public/disposable
        domain_approval = DomainApproval(
            domain=domain,
            status='approved',  # Auto-approve corporate domains
            requested_by_email=email,
            requested_by_name=name,
            auto_approved=True,
            reviewed_at=datetime.utcnow()
        )
        db.session.add(domain_approval)
        app.logger.info(f"Auto-approved corporate domain: {domain}")

    # Domain is approved (either previously or just now)

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

    # Determine redirect and auth handling based on auth preference
    if auth_preference == 'passkey':
        # SECURITY: For passkey signups, use a setup token instead of full session
        # This prevents account hijacking if user doesn't complete passkey setup
        # The token only allows access to credential setup endpoints
        import secrets
        setup_token = secrets.token_urlsafe(32)

        # Store setup token in session with limited scope
        session['setup_token'] = setup_token
        session['setup_user_id'] = user.id
        session['setup_expires'] = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
        session.permanent = False  # Session-only cookie

        # Do NOT set user_id - user is NOT fully logged in yet
        redirect_url = f'/{domain}/setup?token={setup_token}'
        setup_passkey = True

        app.logger.info(f"Created setup token for user {email} - credential setup required")
    else:
        # Password auth - user already has credentials, log them in fully
        session['user_id'] = user.id
        set_session_expiry(is_admin=False)  # 8 hours default for regular users
        user.last_login = datetime.utcnow()
        db.session.commit()
        redirect_url = f'/{domain}'
        setup_passkey = False

    return jsonify({
        'message': 'Account created successfully',
        'email': email,
        'domain': domain,
        'user': user.to_dict(),
        'redirect': redirect_url,
        'setup_passkey': setup_passkey
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
                        allow_password=True,
                        allow_passkey=True,
                        allow_registration=True,
                        require_approval=True,
                        rp_name='Architecture Decisions'
                    )
                    db.session.add(auth_config)

                # Auto-approve corporate domain (already validated during email request)
                domain_approval = DomainApproval.query.filter_by(domain=verification.domain).first()
                if not domain_approval:
                    domain_approval = DomainApproval(
                        domain=verification.domain,
                        status='approved',
                        requested_by_email=verification.email,
                        requested_by_name=verification.name,
                        auto_approved=True,
                        reviewed_at=datetime.utcnow()
                    )
                    db.session.add(domain_approval)
                    app.logger.info(f"Auto-approved corporate domain via email verification: {verification.domain}")
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
    data = request.get_json() or {}

    # Sanitize inputs to prevent XSS and injection attacks
    email = sanitize_email(data.get('email', ''))
    name = sanitize_name(data.get('name', ''), max_length=255)
    reason = sanitize_text_field(data.get('reason', ''), max_length=1000)
    domain = data.get('domain', '').lower().strip()

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

    # Check if tenant has auto-approval enabled (require_approval=False)
    auth_config = AuthConfig.query.filter_by(domain=domain).first()
    require_approval = auth_config.require_approval if auth_config else True

    if not require_approval:
        # Auto-approval enabled: create user immediately and send setup email
        from models import SetupToken
        from notifications import send_account_setup_email

        # Check user limit before auto-approving
        can_accept, limit_message, current_count, max_allowed = can_tenant_accept_users(domain)
        if not can_accept:
            return jsonify({
                'error': 'User limit reached',
                'message': f'{limit_message} Please contact your organization administrator.',
                'current_users': current_count,
                'max_users': max_allowed
            }), 403

        # Create the user account
        new_user = User(
            email=email,
            name=name,
            sso_domain=domain,
            auth_type='webauthn',
            is_admin=False
        )
        db.session.add(new_user)
        db.session.flush()  # Get the user ID before creating token

        # Generate setup token for the new user
        setup_token = SetupToken.create_for_user(new_user)
        setup_token_str = setup_token._token_string
        setup_url = f"{request.host_url.rstrip('/')}/{domain}/setup?token={setup_token_str}"

        db.session.commit()

        # Send setup email to user
        email_config = EmailConfig.query.filter_by(domain='system', enabled=True).first()
        if email_config:
            send_account_setup_email(
                email_config,
                name,
                email,
                setup_url,
                SetupToken.TOKEN_VALIDITY_HOURS,
                tenant_name=domain
            )
            app.logger.info(f"Auto-approved user {email} for tenant {domain}, setup email sent")
        else:
            app.logger.warning(f"Auto-approved user {email} for tenant {domain}, but no email config to send setup link")

        return jsonify({
            'message': 'Your account has been created! Check your email for a link to set up your login credentials.',
            'auto_approved': True,
            'email': email,
            'domain': domain
        })

    # require_approval=True: Create access request for admin review
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


@app.route('/api/auth/request-recovery', methods=['POST'])
def api_request_account_recovery():
    """Self-service: User requests their own account recovery link.

    This endpoint allows users who have lost access to their passkey/password
    to request a recovery email. For security, the response is always the same
    whether or not the email exists (to prevent email enumeration).
    """
    from datetime import datetime, timedelta
    from models import SetupToken
    from notifications import send_account_recovery_email

    data = request.get_json() or {}
    email = data.get('email', '').lower().strip()

    if not email or '@' not in email:
        return jsonify({'error': 'Valid email address is required'}), 400

    # Generic success message (always return this to prevent email enumeration)
    success_message = 'If an account exists with this email, a recovery link has been sent.'

    # Find the user
    user = User.query.filter_by(email=email).first()

    if not user:
        # Don't reveal that user doesn't exist
        logger.info(f"Account recovery requested for non-existent email: {email}")
        return jsonify({'message': success_message})

    # Check if user belongs to a tenant
    if not user.sso_domain:
        logger.warning(f"Account recovery requested for user without domain: {email}")
        return jsonify({'message': success_message})

    # Rate limiting: Check for existing recent recovery tokens
    recent_token = SetupToken.query.filter(
        SetupToken.user_id == user.id,
        SetupToken.purpose == SetupToken.PURPOSE_ACCOUNT_RECOVERY,
        SetupToken.created_at > datetime.utcnow() - timedelta(minutes=2)
    ).first()

    if recent_token:
        logger.info(f"Rate limited recovery request for: {email}")
        return jsonify({'message': success_message})

    # Get email configuration
    email_config = EmailConfig.query.filter_by(domain='system', enabled=True).first()
    if not email_config:
        email_config = EmailConfig.query.filter_by(domain=user.sso_domain, enabled=True).first()

    if not email_config:
        # No email config, but still return success message
        logger.warning(f"Account recovery requested but no email config for domain: {user.sso_domain}")
        return jsonify({'message': success_message})

    # Generate recovery token (2-hour expiry)
    setup_token = SetupToken.create_for_user(
        user,
        validity_hours=SetupToken.RECOVERY_VALIDITY_HOURS,
        purpose=SetupToken.PURPOSE_ACCOUNT_RECOVERY
    )
    token_string = setup_token._token_string
    # Use the existing setup route - it now handles both initial setup and recovery
    recovery_url = f"{request.host_url.rstrip('/')}/{user.sso_domain}/setup?token={token_string}"

    # Send the recovery email
    success = send_account_recovery_email(
        email_config=email_config,
        user_name=user.name or user.email.split('@')[0],
        user_email=user.email,
        recovery_url=recovery_url,
        expires_in_hours=SetupToken.RECOVERY_VALIDITY_HOURS
    )

    if success:
        logger.info(f"Account recovery email sent to: {email}")
    else:
        logger.error(f"Failed to send account recovery email to: {email}")

    # Always return success to prevent email enumeration
    return jsonify({'message': success_message})


@app.route('/api/auth/setup-token/validate', methods=['POST'])
def api_validate_setup_token():
    """Validate a setup token and create a setup session for the user."""
    from datetime import datetime, timedelta
    from models import SetupToken
    import secrets

    data = request.get_json() or {}
    token = data.get('token', '')

    if not token:
        return jsonify({'error': 'No token provided', 'valid': False}), 400

    # Validate the encrypted token
    setup_token, error = SetupToken.validate_token(token)

    if error:
        # Determine specific error type
        if 'expired' in error.lower():
            return jsonify({'error': error, 'valid': False, 'expired': True}), 400
        if 'used' in error.lower():
            return jsonify({'error': error, 'valid': False, 'used': True}), 400
        return jsonify({'error': error, 'valid': False}), 400

    user = setup_token.user
    is_recovery = setup_token.purpose == SetupToken.PURPOSE_ACCOUNT_RECOVERY

    # Check if user already has credentials set up
    has_passkey = len(user.webauthn_credentials) > 0 if user.webauthn_credentials else False
    has_password = user.has_password()

    # For initial setup tokens, block if user already has credentials
    # For recovery tokens, allow resetting credentials
    if (has_passkey or has_password) and not is_recovery:
        # Mark token as used since user already has credentials
        setup_token.used_at = datetime.utcnow()
        db.session.commit()
        return jsonify({
            'error': 'Your account is already set up. Please log in instead.',
            'valid': False,
            'already_setup': True,
            'redirect': f'/{user.sso_domain}/login'
        }), 400

    # Create a setup session for the user
    session_token = secrets.token_urlsafe(32)
    session['setup_token'] = session_token
    session['setup_user_id'] = user.id
    session['setup_expires'] = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
    session['setup_purpose'] = setup_token.purpose  # Track if this is recovery or initial setup

    # Determine the redirect based on token purpose
    if is_recovery:
        redirect_url = f'/{user.sso_domain}/recover?token={token}'
        message = 'Recovery token validated. You can now reset your credentials.'
    else:
        redirect_url = f'/{user.sso_domain}/setup?token={token}'
        message = 'Setup token validated. You can now set up your credentials.'

    return jsonify({
        'valid': True,
        'purpose': setup_token.purpose,
        'is_recovery': is_recovery,
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'sso_domain': user.sso_domain,
            'has_passkey': has_passkey,
            'has_password': has_password,
        },
        'expires_at': setup_token.expires_at.isoformat(),
        'message': message,
        'redirect': redirect_url
    })


@app.route('/api/auth/setup-token/use', methods=['POST'])
def api_use_setup_token():
    """Mark a setup token as used after successful credential setup."""
    from datetime import datetime
    from models import SetupToken

    data = request.get_json() or {}
    token = data.get('token', '')

    if not token:
        return jsonify({'error': 'No token provided'}), 400

    # Validate and find the token
    setup_token, error = SetupToken.validate_token(token)

    if not setup_token:
        # Even if validation fails, try to mark by hash if token format is recognizable
        token_hash = SetupToken._hash_token(token)
        setup_token = SetupToken.query.filter_by(token_hash=token_hash).first()
        if not setup_token:
            return jsonify({'error': 'Invalid setup token'}), 404

    if setup_token.is_used():
        return jsonify({'message': 'Token already marked as used'})

    setup_token.used_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Token marked as used'})


@app.route('/api/auth/setup-password', methods=['POST'])
def api_setup_password():
    """Set password for a user during account setup (uses setup token for auth)."""
    import re
    from datetime import datetime
    from models import SetupToken

    data = request.get_json() or {}
    token = data.get('token', '')
    password = data.get('password', '')

    if not token:
        return jsonify({'error': 'Setup token is required'}), 400

    # Validate the setup token
    setup_token, error = SetupToken.validate_token(token)
    if not setup_token:
        return jsonify({'error': error or 'Invalid setup token'}), 401

    # Password policy validation
    if not password or len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if not re.search(r'[A-Z]', password):
        return jsonify({'error': 'Password must contain at least one uppercase letter'}), 400
    if not re.search(r'[a-z]', password):
        return jsonify({'error': 'Password must contain at least one lowercase letter'}), 400
    if not re.search(r'\d', password):
        return jsonify({'error': 'Password must contain at least one number'}), 400

    # Get the user from the token
    user = setup_token.user
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Set the password
    user.set_password(password)
    user.auth_type = 'local'

    # Mark token as used
    setup_token.used_at = datetime.utcnow()

    db.session.commit()

    # Log the user in
    session['user_id'] = user.id
    session['user_type'] = 'user'

    return jsonify({
        'message': 'Password set successfully',
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'sso_domain': user.sso_domain,
            'has_password': True,
            'has_passkey': len(user.webauthn_credentials) > 0 if user.webauthn_credentials else False
        }
    })


@app.route('/api/admin/users/<int:user_id>/setup-link', methods=['POST'])
@admin_required
def api_generate_setup_link(user_id):
    """Generate a new setup link for a user (admin only)."""
    from models import SetupToken

    user = User.query.get_or_404(user_id)

    # Check permission - admin can only generate links for users in their domain
    if not is_master_account() and user.sso_domain != g.current_user.sso_domain:
        return jsonify({'error': 'Not authorized to generate setup links for this user'}), 403

    # Check if user already has credentials
    has_passkey = len(user.webauthn_credentials) > 0 if user.webauthn_credentials else False
    has_password = user.has_password()

    if has_passkey or has_password:
        return jsonify({
            'error': 'User already has credentials set up',
            'has_passkey': has_passkey,
            'has_password': has_password
        }), 400

    # Generate new setup token (48hr expiry by default)
    setup_token = SetupToken.create_for_user(user)
    token_string = setup_token._token_string  # Get the actual token string
    setup_url = f"{request.host_url.rstrip('/')}/{user.sso_domain}/setup?token={token_string}"

    return jsonify({
        'message': 'Setup link generated successfully',
        'setup_url': setup_url,
        'token': token_string,  # Also return raw token for copying
        'expires_at': setup_token.expires_at.isoformat(),
        'hours_valid': SetupToken.TOKEN_VALIDITY_HOURS
    })


@app.route('/api/admin/users/<int:user_id>/send-setup-email', methods=['POST'])
@admin_required
def api_send_setup_email(user_id):
    """Send a setup token email to a user (admin only).

    This endpoint generates a new setup token and sends it via email.
    Only admins can call this, and it uses the system's configured SMTP settings.
    """
    from models import SetupToken
    from notifications import send_setup_token_email

    user = User.query.get_or_404(user_id)

    # Check permission - admin can only send emails for users in their domain
    if not is_master_account() and user.sso_domain != g.current_user.sso_domain:
        return jsonify({'error': 'Not authorized to send emails for this user'}), 403

    # Check if user already has credentials
    has_passkey = len(user.webauthn_credentials) > 0 if user.webauthn_credentials else False
    has_password = user.has_password()

    if has_passkey or has_password:
        return jsonify({
            'error': 'User already has credentials set up',
            'has_passkey': has_passkey,
            'has_password': has_password
        }), 400

    # Get email configuration - prioritize system config (super admin), fall back to domain config
    email_config = EmailConfig.query.filter_by(domain='system', enabled=True).first()
    if not email_config:
        email_config = EmailConfig.query.filter_by(domain=user.sso_domain, enabled=True).first()

    if not email_config:
        return jsonify({
            'error': 'Email not configured. Please configure SMTP settings in the admin panel first.'
        }), 400

    # Generate new setup token (48hr expiry by default)
    setup_token = SetupToken.create_for_user(user)
    token_string = setup_token._token_string
    setup_url = f"{request.host_url.rstrip('/')}/{user.sso_domain}/setup?token={token_string}"

    # Send the email
    success = send_setup_token_email(
        email_config=email_config,
        user_name=user.name or user.email.split('@')[0],
        user_email=user.email,
        setup_url=setup_url,
        expires_in_hours=SetupToken.TOKEN_VALIDITY_HOURS
    )

    if success:
        return jsonify({
            'message': f'Setup email sent successfully to {user.email}',
            'setup_url': setup_url,
            'expires_at': setup_token.expires_at.isoformat(),
            'hours_valid': SetupToken.TOKEN_VALIDITY_HOURS
        })
    else:
        return jsonify({
            'error': 'Failed to send email. Please check SMTP configuration.',
            'setup_url': setup_url  # Still return the URL so admin can manually share
        }), 500


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
    from models import SetupToken

    access_request = AccessRequest.query.get_or_404(request_id)

    # Check permission
    if not is_master_account() and access_request.domain != g.current_user.sso_domain:
        return jsonify({'error': 'Not authorized to approve this request'}), 403

    if access_request.status != 'pending':
        return jsonify({'error': f'Request is already {access_request.status}'}), 400

    # Check user limit before approving (only if creating a new user)
    existing_user_check = User.query.filter_by(email=access_request.email).first()
    if not existing_user_check:
        can_accept, limit_message, current_count, max_allowed = can_tenant_accept_users(access_request.domain)
        if not can_accept:
            return jsonify({
                'error': 'User limit reached',
                'message': limit_message,
                'current_users': current_count,
                'max_users': max_allowed
            }), 403

    # Check if user already exists (could have been created via another path)
    existing_user = User.query.filter_by(email=access_request.email).first()
    if existing_user:
        access_request.status = 'approved'
        access_request.processed_by_id = g.current_user.id if not is_master_account() else None
        access_request.processed_at = datetime.utcnow()
        db.session.commit()

        # Generate setup token for existing user if they don't have credentials
        setup_url = None
        setup_token_str = None
        has_passkey = len(existing_user.webauthn_credentials) > 0 if existing_user.webauthn_credentials else False
        has_password = existing_user.has_password()
        if not has_passkey and not has_password:
            setup_token = SetupToken.create_for_user(existing_user)
            setup_token_str = setup_token._token_string
            setup_url = f"{request.host_url.rstrip('/')}/{access_request.domain}/setup?token={setup_token_str}"

        return jsonify({
            'message': 'User already exists, request marked as approved',
            'user': existing_user.to_dict(),
            'setup_url': setup_url,
            'setup_token': setup_token_str,
            'token_expires_in_hours': SetupToken.TOKEN_VALIDITY_HOURS if setup_token_str else None
        })

    # Create the user account
    new_user = User(
        email=access_request.email,
        name=access_request.name,
        sso_domain=access_request.domain,
        auth_type='webauthn',
        is_admin=False
    )
    db.session.add(new_user)
    db.session.flush()  # Get the user ID before creating token

    # Update request status
    access_request.status = 'approved'
    access_request.processed_by_id = g.current_user.id if not is_master_account() else None
    access_request.processed_at = datetime.utcnow()

    # Generate setup token for the new user (48hr expiry)
    setup_token = SetupToken.create_for_user(new_user)
    setup_token_str = setup_token._token_string
    setup_url = f"{request.host_url.rstrip('/')}/{access_request.domain}/setup?token={setup_token_str}"

    db.session.commit()

    # TODO: Send email to user informing them they've been approved
    # notify_user_access_approved(access_request, new_user, setup_url)

    return jsonify({
        'message': 'Access request approved',
        'user': new_user.to_dict(),
        'setup_url': setup_url,
        'setup_token': setup_token_str,
        'token_expires_in_hours': SetupToken.TOKEN_VALIDITY_HOURS
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


# ==================== API Routes - Role Requests ====================

@app.route('/api/tenant/<domain>/role-requests', methods=['POST'])
@login_required
def api_create_role_request(domain):
    """Create a role elevation request (user requests steward or admin privileges)."""
    from governance import check_and_upgrade_provisional_admins

    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    # Verify domain matches user's domain
    if user.sso_domain.lower() != domain.lower():
        return jsonify({'error': 'Cannot request role for different domain'}), 403

    # Get tenant
    tenant = Tenant.query.filter_by(domain=domain.lower()).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Get user's membership
    membership = user.get_membership(tenant.id)
    if not membership:
        return jsonify({'error': 'You are not a member of this tenant'}), 403

    # Sanitize and validate input
    data = request.get_json() or {}
    requested_role_str = data.get('requested_role', '').lower()
    reason = sanitize_text_field(data.get('reason', ''))

    # Validate requested role
    if requested_role_str not in ['steward', 'admin']:
        return jsonify({'error': 'Invalid role. Must be steward or admin'}), 400

    requested_role = RequestedRole.STEWARD if requested_role_str == 'steward' else RequestedRole.ADMIN

    # Check if user already has this role or higher
    current_role = membership.global_role
    if current_role == GlobalRole.ADMIN:
        return jsonify({'error': 'You already have admin privileges'}), 400
    if current_role == GlobalRole.STEWARD and requested_role == RequestedRole.STEWARD:
        return jsonify({'error': 'You already have steward privileges'}), 400

    # Check for existing pending request
    existing_request = RoleRequest.query.filter_by(
        user_id=user.id,
        tenant_id=tenant.id,
        status=RequestStatus.PENDING
    ).first()

    if existing_request:
        return jsonify({
            'error': 'You already have a pending role request',
            'existing_request': existing_request.to_dict()
        }), 400

    # Create the role request
    role_request = RoleRequest(
        user_id=user.id,
        tenant_id=tenant.id,
        requested_role=requested_role,
        reason=reason,
        status=RequestStatus.PENDING
    )
    db.session.add(role_request)

    # Log the request creation
    log_admin_action(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action_type=AuditLog.ACTION_ROLE_REQUEST_CREATED,
        target_entity='role_request',
        target_id=role_request.id,
        details={
            'requested_role': requested_role.value,
            'reason': reason
        }
    )

    db.session.commit()

    return jsonify({
        'message': 'Role request submitted successfully',
        'request': role_request.to_dict()
    }), 201


@app.route('/api/tenant/<domain>/role-requests', methods=['GET'])
@steward_or_admin_required
def api_list_role_requests(domain):
    """List role requests for a tenant (admin/steward only)."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    # Verify domain matches user's domain
    if user.sso_domain.lower() != domain.lower():
        return jsonify({'error': 'Access denied'}), 403

    # Get tenant
    tenant = Tenant.query.filter_by(domain=domain.lower()).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Get filter parameter (default to pending)
    status_filter = request.args.get('status', 'pending').lower()

    # Build query
    query = RoleRequest.query.filter_by(tenant_id=tenant.id)

    if status_filter == 'pending':
        query = query.filter_by(status=RequestStatus.PENDING)
    elif status_filter == 'approved':
        query = query.filter_by(status=RequestStatus.APPROVED)
    elif status_filter == 'rejected':
        query = query.filter_by(status=RequestStatus.REJECTED)
    elif status_filter != 'all':
        return jsonify({'error': 'Invalid status filter. Use: all, pending, approved, or rejected'}), 400

    requests = query.order_by(RoleRequest.created_at.desc()).all()

    return jsonify([r.to_dict() for r in requests])


@app.route('/api/tenant/<domain>/role-requests/<int:request_id>/approve', methods=['POST'])
@steward_or_admin_required
def api_approve_role_request(domain, request_id):
    """Approve a role request and promote the user."""
    from governance import can_promote_to_role, check_and_upgrade_provisional_admins

    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    # Verify domain matches user's domain
    if user.sso_domain.lower() != domain.lower():
        return jsonify({'error': 'Access denied'}), 403

    # Get tenant
    tenant = Tenant.query.filter_by(domain=domain.lower()).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Get the role request
    role_request = RoleRequest.query.get_or_404(request_id)

    # Verify request belongs to this tenant
    if role_request.tenant_id != tenant.id:
        return jsonify({'error': 'Role request not found in this tenant'}), 404

    # Check if already processed
    if role_request.status != RequestStatus.PENDING:
        return jsonify({'error': f'Request is already {role_request.status.value}'}), 400

    # Get reviewer's membership
    reviewer_membership = user.get_membership(tenant.id)
    if not reviewer_membership:
        return jsonify({'error': 'You are not a member of this tenant'}), 403

    # Map requested role to GlobalRole
    target_role = GlobalRole.STEWARD if role_request.requested_role == RequestedRole.STEWARD else GlobalRole.ADMIN

    # Check if reviewer can promote to this role
    can_promote, reason = can_promote_to_role(reviewer_membership, target_role)
    if not can_promote:
        return jsonify({'error': reason}), 403

    # Get the target user's membership
    target_membership = TenantMembership.query.filter_by(
        user_id=role_request.user_id,
        tenant_id=tenant.id
    ).first()

    if not target_membership:
        return jsonify({'error': 'User is not a member of this tenant'}), 404

    # Store old role for audit log
    old_role = target_membership.global_role

    # Update the user's role
    target_membership.global_role = target_role

    # Update request status
    role_request.status = RequestStatus.APPROVED
    role_request.reviewed_at = datetime.utcnow()
    role_request.reviewed_by_id = user.id

    # Log the approval and promotion
    log_admin_action(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action_type=AuditLog.ACTION_ROLE_REQUEST_APPROVED,
        target_entity='role_request',
        target_id=role_request.id,
        details={
            'target_user_id': role_request.user_id,
            'old_role': old_role.value,
            'new_role': target_role.value,
            'requested_role': role_request.requested_role.value
        }
    )

    log_admin_action(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action_type=AuditLog.ACTION_PROMOTE_USER,
        target_entity='user',
        target_id=role_request.user_id,
        details={
            'old_role': old_role.value,
            'new_role': target_role.value,
            'via_role_request': True,
            'request_id': role_request.id
        }
    )

    db.session.commit()

    # Check if this promotion triggers maturity upgrade
    check_and_upgrade_provisional_admins(tenant, trigger_user_id=user.id)

    return jsonify({
        'message': f'Role request approved. User promoted to {target_role.value}',
        'request': role_request.to_dict(),
        'new_role': target_role.value
    })


@app.route('/api/tenant/<domain>/role-requests/<int:request_id>/reject', methods=['POST'])
@steward_or_admin_required
def api_reject_role_request(domain, request_id):
    """Reject a role request."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    # Verify domain matches user's domain
    if user.sso_domain.lower() != domain.lower():
        return jsonify({'error': 'Access denied'}), 403

    # Get tenant
    tenant = Tenant.query.filter_by(domain=domain.lower()).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Get the role request
    role_request = RoleRequest.query.get_or_404(request_id)

    # Verify request belongs to this tenant
    if role_request.tenant_id != tenant.id:
        return jsonify({'error': 'Role request not found in this tenant'}), 404

    # Check if already processed
    if role_request.status != RequestStatus.PENDING:
        return jsonify({'error': f'Request is already {role_request.status.value}'}), 400

    # Get rejection reason
    data = request.get_json() or {}
    rejection_reason = sanitize_text_field(data.get('reason', ''))

    # Update request status
    role_request.status = RequestStatus.REJECTED
    role_request.reviewed_at = datetime.utcnow()
    role_request.reviewed_by_id = user.id
    role_request.rejection_reason = rejection_reason

    # Log the rejection
    log_admin_action(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action_type=AuditLog.ACTION_ROLE_REQUEST_REJECTED,
        target_entity='role_request',
        target_id=role_request.id,
        details={
            'target_user_id': role_request.user_id,
            'requested_role': role_request.requested_role.value,
            'rejection_reason': rejection_reason
        }
    )

    db.session.commit()

    return jsonify({
        'message': 'Role request rejected',
        'request': role_request.to_dict()
    })


# ==================== API Routes - Admin Role Requests (Convenience Routes) ====================
# These routes use /api/admin/ prefix and derive the tenant from the logged-in user

@app.route('/api/admin/role-requests', methods=['GET'])
@steward_or_admin_required
def api_admin_list_role_requests():
    """List role requests for admin's domain."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    # Get tenant from user's domain
    tenant = Tenant.query.filter_by(domain=user.sso_domain.lower()).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Get filter parameter (default to all)
    status_filter = request.args.get('status', 'all').lower()

    # Build query
    query = RoleRequest.query.filter_by(tenant_id=tenant.id)

    if status_filter == 'pending':
        query = query.filter_by(status=RequestStatus.PENDING)
    elif status_filter == 'approved':
        query = query.filter_by(status=RequestStatus.APPROVED)
    elif status_filter == 'rejected':
        query = query.filter_by(status=RequestStatus.REJECTED)
    elif status_filter != 'all':
        return jsonify({'error': 'Invalid status filter. Use: all, pending, approved, or rejected'}), 400

    requests = query.order_by(RoleRequest.created_at.desc()).all()

    return jsonify([r.to_dict() for r in requests])


@app.route('/api/admin/role-requests', methods=['POST'])
@login_required
def api_admin_create_role_request():
    """Create a role elevation request (user requests steward or admin privileges)."""
    from governance import check_and_upgrade_provisional_admins

    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    # Get tenant from user's domain
    tenant = Tenant.query.filter_by(domain=user.sso_domain.lower()).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Get user's membership
    membership = user.get_membership(tenant.id)
    if not membership:
        return jsonify({'error': 'You are not a member of this tenant'}), 403

    # Sanitize and validate input
    data = request.get_json() or {}
    requested_role_str = data.get('requested_role', '').lower()
    reason = sanitize_text_field(data.get('reason', ''))

    # Validate requested role
    if requested_role_str not in ['steward', 'admin']:
        return jsonify({'error': 'Invalid role. Must be steward or admin'}), 400

    requested_role = RequestedRole.STEWARD if requested_role_str == 'steward' else RequestedRole.ADMIN

    # Check if user already has this role or higher
    current_role = membership.global_role
    if current_role == GlobalRole.ADMIN:
        return jsonify({'error': 'You already have admin privileges'}), 400
    if current_role == GlobalRole.STEWARD and requested_role == RequestedRole.STEWARD:
        return jsonify({'error': 'You already have steward privileges'}), 400

    # Check for existing pending request for same role
    existing_request = RoleRequest.query.filter_by(
        user_id=user.id,
        tenant_id=tenant.id,
        requested_role=requested_role,
        status=RequestStatus.PENDING
    ).first()

    if existing_request:
        return jsonify({'error': 'You already have a pending request for this role'}), 400

    # Create the request
    role_request = RoleRequest(
        user_id=user.id,
        tenant_id=tenant.id,
        requested_role=requested_role,
        reason=reason
    )
    db.session.add(role_request)

    # Log the request
    log_admin_action(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action_type=AuditLog.ACTION_ROLE_REQUESTED,
        target_entity='role_request',
        target_id=role_request.id,
        details={
            'requested_role': requested_role.value,
            'reason': reason
        }
    )

    db.session.commit()

    # Check if provisional admin should be upgraded
    check_and_upgrade_provisional_admins(tenant)

    return jsonify({
        'message': 'Role request submitted successfully',
        'request': role_request.to_dict()
    }), 201


@app.route('/api/admin/role-requests/<int:request_id>/approve', methods=['POST'])
@steward_or_admin_required
def api_admin_approve_role_request(request_id):
    """Approve a role request and promote the user."""
    from governance import can_promote_to_role, check_and_upgrade_provisional_admins

    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    # Get tenant from user's domain
    tenant = Tenant.query.filter_by(domain=user.sso_domain.lower()).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Get the role request
    role_request = RoleRequest.query.get_or_404(request_id)

    # Verify request belongs to this tenant
    if role_request.tenant_id != tenant.id:
        return jsonify({'error': 'Role request not found in this tenant'}), 404

    # Check if already processed
    if role_request.status != RequestStatus.PENDING:
        return jsonify({'error': f'Request is already {role_request.status.value}'}), 400

    # Get reviewer's membership
    reviewer_membership = user.get_membership(tenant.id)
    if not reviewer_membership:
        return jsonify({'error': 'You are not a member of this tenant'}), 403

    # Map requested role to GlobalRole
    target_role = GlobalRole.STEWARD if role_request.requested_role == RequestedRole.STEWARD else GlobalRole.ADMIN

    # Check if reviewer can promote to this role
    can_promote, reason = can_promote_to_role(reviewer_membership, target_role)
    if not can_promote:
        return jsonify({'error': reason}), 403

    # Get target user's membership
    target_membership = TenantMembership.query.filter_by(
        user_id=role_request.user_id,
        tenant_id=tenant.id
    ).first()

    if not target_membership:
        return jsonify({'error': 'Target user is not a member of this tenant'}), 400

    # Store old role for audit log
    old_role = target_membership.global_role

    # Update the user's role
    target_membership.global_role = target_role

    # Update request status
    role_request.status = RequestStatus.APPROVED
    role_request.reviewed_at = datetime.utcnow()
    role_request.reviewed_by_id = user.id

    # Log the approval and role change
    log_admin_action(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action_type=AuditLog.ACTION_APPROVE_REQUEST,
        target_entity='role_request',
        target_id=role_request.id,
        details={
            'target_user_id': role_request.user_id,
            'old_role': old_role.value,
            'new_role': target_role.value,
            'requested_role': role_request.requested_role.value
        }
    )

    db.session.commit()

    # Check if any provisional admins should be upgraded
    check_and_upgrade_provisional_admins(tenant)

    # Get updated user
    target_user = User.query.get(role_request.user_id)

    return jsonify({
        'message': f'Role request approved. User is now a {target_role.value}.',
        'request': role_request.to_dict(),
        'user': target_user.to_dict() if target_user else None
    })


@app.route('/api/admin/role-requests/<int:request_id>/reject', methods=['POST'])
@steward_or_admin_required
def api_admin_reject_role_request(request_id):
    """Reject a role request."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    # Get tenant from user's domain
    tenant = Tenant.query.filter_by(domain=user.sso_domain.lower()).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Get the role request
    role_request = RoleRequest.query.get_or_404(request_id)

    # Verify request belongs to this tenant
    if role_request.tenant_id != tenant.id:
        return jsonify({'error': 'Role request not found in this tenant'}), 404

    # Check if already processed
    if role_request.status != RequestStatus.PENDING:
        return jsonify({'error': f'Request is already {role_request.status.value}'}), 400

    # Get rejection reason
    data = request.get_json() or {}
    rejection_reason = sanitize_text_field(data.get('reason', ''))

    # Update request status
    role_request.status = RequestStatus.REJECTED
    role_request.reviewed_at = datetime.utcnow()
    role_request.reviewed_by_id = user.id
    role_request.rejection_reason = rejection_reason

    # Log the rejection
    log_admin_action(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action_type=AuditLog.ACTION_REJECT_REQUEST,
        target_entity='role_request',
        target_id=role_request.id,
        details={
            'target_user_id': role_request.user_id,
            'requested_role': role_request.requested_role.value,
            'rejection_reason': rejection_reason
        }
    )

    db.session.commit()

    return jsonify({
        'message': 'Role request rejected',
        'request': role_request.to_dict()
    })


@app.route('/api/admin/tenant-admins', methods=['GET'])
@login_required
def api_get_tenant_admins():
    """Get list of admins and stewards for the current user's tenant.

    This endpoint is available to all authenticated users so they can see
    who to contact for role elevation requests.

    Security: Only returns basic info (name, role) - no email to prevent enumeration.
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    # Get tenant from user's domain
    tenant = Tenant.query.filter_by(domain=user.sso_domain.lower()).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Get admins and stewards for this tenant
    admin_memberships = TenantMembership.query.filter(
        TenantMembership.tenant_id == tenant.id,
        TenantMembership.global_role.in_([GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN])
    ).all()

    admins = []
    for membership in admin_memberships:
        admin_user = User.query.get(membership.user_id)
        if admin_user:
            admins.append({
                'name': admin_user.name or 'Unnamed Admin',
                'role': membership.global_role.value,
                # Don't expose email to prevent enumeration - users can see names only
            })

    return jsonify({
        'admins': admins,
        'total': len(admins)
    })


@app.route('/api/webauthn/register/options', methods=['POST'])
@rate_limit("10 per minute")
def api_webauthn_register_options():
    """Generate WebAuthn registration options."""
    from auth import validate_setup_token

    data = request.get_json() or {}

    # Check for setup token flow (incomplete account setting up first credential)
    setup_user, _ = validate_setup_token()
    if setup_user:
        # User is in setup mode - generate options for their account
        email = setup_user.email
        name = setup_user.name
        domain = setup_user.sso_domain

        log_security_event('auth', f"WebAuthn setup registration for {email} (setup token)", severity='INFO')

        try:
            options = create_registration_options(email, name, domain)
            return jsonify(json.loads(options))
        except Exception as e:
            app.logger.error(f"WebAuthn setup registration options error: {e}")
            return jsonify({'error': 'Failed to generate registration options'}), 500

    # Standard registration flow
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
    from auth import validate_setup_token, complete_setup_and_login

    data = request.get_json() or {}

    credential = data.get('credential')
    device_name = data.get('device_name')

    if not credential:
        return jsonify({'error': 'Credential is required'}), 400

    # Check for setup token flow
    setup_user, _ = validate_setup_token()

    user, error = verify_registration(credential, device_name)

    if error:
        return jsonify({'error': error}), 400

    # If this was a setup token flow, complete the setup
    if setup_user and setup_user.id == user.id:
        complete_setup_and_login(user)
        log_security_event('auth', f"Passkey setup completed for {user.email} (first credential)", severity='INFO')
    else:
        # Standard registration - log the user in
        session['user_id'] = user.id
        set_session_expiry(is_admin=False)  # 8 hours default for regular users

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
    data = request.get_json() or {}

    credential = data.get('credential')

    if not credential:
        return jsonify({'error': 'Credential is required'}), 400

    user, error = verify_authentication(credential)

    if error:
        return jsonify({'error': error}), 400

    # Log the user in
    session['user_id'] = user.id
    set_session_expiry(is_admin=False)  # 8 hours default for regular users

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

    data = request.get_json() or {}
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
    data = request.get_json() or {}

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
    data = request.get_json() or {}

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
    data = request.get_json() or {}

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
    data = request.get_json() or {}

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
    """List all tenants (organizations) with their stats (super admin only).

    A tenant is considered active if it has:
    - An approved DomainApproval record, OR
    - Users registered for the domain (for backwards compatibility with domains
      created before the approval system was added)
    """
    tenants = {}

    # Get domains from approved DomainApproval records
    approved_domains = DomainApproval.query.filter_by(status='approved').all()
    for approval in approved_domains:
        tenants[approval.domain] = {
            'domain': approval.domain,
            'user_count': 0,
            'admin_count': 0,
            'steward_count': 0,
            'has_sso': False,
            'status': 'approved',
            'auto_approved': approval.auto_approved,
            'created_at': approval.reviewed_at.isoformat() if approval.reviewed_at else (approval.updated_at.isoformat() if approval.updated_at else approval.created_at.isoformat()),
            'maturity_state': None,
            'age_days': None
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
                # Domain has users but no approval record - this is a legacy domain
                # or was created through SSO before approval system existed
                tenants[domain] = {
                    'domain': domain,
                    'user_count': 0,
                    'admin_count': 0,
                    'steward_count': 0,
                    'has_sso': False,
                    'status': 'active',  # Mark as active since users exist
                    'auto_approved': False,
                    'created_at': created_at.isoformat() if created_at else None,
                    'maturity_state': None,
                    'age_days': None
                }
            tenants[domain]['user_count'] = user_count
            tenants[domain]['admin_count'] = int(admin_count) if admin_count else 0

    # Get v1.5 Tenant data (maturity state, member counts)
    tenant_records = Tenant.query.all()
    for tenant in tenant_records:
        if tenant.domain in tenants:
            # Get member counts by role
            admin_count = TenantMembership.query.filter_by(
                tenant_id=tenant.id,
                global_role=GlobalRole.ADMIN
            ).count()
            steward_count = TenantMembership.query.filter_by(
                tenant_id=tenant.id,
                global_role=GlobalRole.STEWARD
            ).count()
            member_count = TenantMembership.query.filter_by(tenant_id=tenant.id).count()

            # Calculate age (handle None created_at for legacy tenants)
            if tenant.created_at:
                age_days = (datetime.utcnow() - tenant.created_at).days
            else:
                age_days = None

            tenants[tenant.domain]['maturity_state'] = tenant.maturity_state.value
            tenants[tenant.domain]['admin_count'] = admin_count
            tenants[tenant.domain]['steward_count'] = steward_count
            tenants[tenant.domain]['user_count'] = member_count
            tenants[tenant.domain]['age_days'] = age_days

    # Check SSO config for all domains
    for domain in tenants:
        tenants[domain]['has_sso'] = SSOConfig.query.filter_by(domain=domain, enabled=True).first() is not None

    return jsonify(sorted(tenants.values(), key=lambda x: x['domain']))


@app.route('/api/tenants/<domain>/maturity', methods=['GET'])
@master_required
def api_get_tenant_maturity(domain):
    """Get tenant maturity details (super admin only).

    Returns maturity state, thresholds, and stats for governance analysis.
    """
    domain = domain.lower()

    # Get tenant record
    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        return jsonify({'error': f'Tenant not found for domain: {domain}'}), 404

    # Get member counts by role
    admin_count = TenantMembership.query.filter_by(
        tenant_id=tenant.id,
        global_role=GlobalRole.ADMIN
    ).count()
    steward_count = TenantMembership.query.filter_by(
        tenant_id=tenant.id,
        global_role=GlobalRole.STEWARD
    ).count()
    provisional_admin_count = TenantMembership.query.filter_by(
        tenant_id=tenant.id,
        global_role=GlobalRole.PROVISIONAL_ADMIN
    ).count()
    user_count = TenantMembership.query.filter_by(
        tenant_id=tenant.id,
        global_role=GlobalRole.USER
    ).count()
    total_members = TenantMembership.query.filter_by(tenant_id=tenant.id).count()

    # Calculate age (handle None created_at)
    if tenant.created_at:
        age_days = (datetime.utcnow() - tenant.created_at).days
    else:
        age_days = 0

    # Calculate what the computed maturity state would be
    computed_state = tenant.compute_maturity_state()
    state_changed = computed_state != tenant.maturity_state

    return jsonify({
        'domain': tenant.domain,
        'tenant_id': tenant.id,
        'maturity_state': tenant.maturity_state.value,
        'computed_maturity_state': computed_state.value,
        'state_needs_update': state_changed,
        'thresholds': {
            'age_days': tenant.maturity_age_days,
            'user_threshold': tenant.maturity_user_threshold
        },
        'current_stats': {
            'age_days': age_days,
            'total_members': total_members,
            'admin_count': admin_count,
            'steward_count': steward_count,
            'provisional_admin_count': provisional_admin_count,
            'user_count': user_count
        },
        'maturity_conditions': {
            'has_multi_admin': admin_count >= 2 or (admin_count >= 1 and steward_count >= 1),
            'has_enough_users': total_members >= (tenant.maturity_user_threshold if tenant.maturity_user_threshold is not None else 5),
            'is_old_enough': age_days >= (tenant.maturity_age_days if tenant.maturity_age_days is not None else 90)
        },
        'created_at': tenant.created_at.isoformat() if tenant.created_at else None
    })


@app.route('/api/tenants/<domain>/maturity', methods=['PUT'])
@master_required
def api_update_tenant_maturity_thresholds(domain):
    """Update tenant maturity thresholds (super admin only).

    Allows super admin to customize maturity thresholds for a specific tenant.
    """
    domain = domain.lower()
    data = request.get_json() or {}

    # Get tenant record
    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        return jsonify({'error': f'Tenant not found for domain: {domain}'}), 404

    # Validate inputs
    if 'age_days' in data:
        age_days = data.get('age_days')
        if not isinstance(age_days, int) or age_days < 0 or age_days > 365:
            return jsonify({'error': 'age_days must be an integer between 0 and 365'}), 400
        tenant.maturity_age_days = age_days

    if 'user_threshold' in data:
        user_threshold = data.get('user_threshold')
        if not isinstance(user_threshold, int) or user_threshold < 1 or user_threshold > 1000:
            return jsonify({'error': 'user_threshold must be an integer between 1 and 1000'}), 400
        tenant.maturity_user_threshold = user_threshold

    # Check if thresholds update would trigger state change
    old_state = tenant.maturity_state
    state_changed = tenant.update_maturity()

    try:
        db.session.commit()

        # Log the action if state changed
        if state_changed:
            # Note: Super admin actions don't have a user_id in tenant context
            # We'll log with tenant_id and note it was a super admin action in details
            log_admin_action(
                tenant_id=tenant.id,
                actor_user_id=None,  # Super admin is not a tenant member
                action_type=AuditLog.ACTION_MATURITY_CHANGE,
                target_entity='tenant',
                target_id=tenant.id,
                details={
                    'old_state': old_state.value,
                    'new_state': tenant.maturity_state.value,
                    'trigger': 'threshold_update',
                    'actor': 'super_admin',
                    'thresholds': {
                        'age_days': tenant.maturity_age_days,
                        'user_threshold': tenant.maturity_user_threshold
                    }
                }
            )
            db.session.commit()

        return jsonify({
            'message': 'Maturity thresholds updated successfully',
            'tenant': tenant.to_dict(),
            'state_changed': state_changed,
            'old_state': old_state.value if state_changed else None,
            'new_state': tenant.maturity_state.value if state_changed else None
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Failed to update thresholds for {domain}: {str(e)}')
        return jsonify({'error': 'Failed to update thresholds. Please try again or contact support.'}), 500


@app.route('/api/tenants/<domain>/maturity/force-upgrade', methods=['POST'])
@master_required
def api_force_tenant_maturity_upgrade(domain):
    """Force tenant to MATURE state (super admin only).

    Override automatic maturity calculation and force tenant to mature state.
    This is useful for manually promoting tenants that need admin capabilities
    before meeting automatic criteria.
    """
    domain = domain.lower()

    # Get tenant record
    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        return jsonify({'error': f'Tenant not found for domain: {domain}'}), 404

    # Check if already mature
    if tenant.maturity_state == MaturityState.MATURE:
        return jsonify({
            'message': 'Tenant is already in MATURE state',
            'tenant': tenant.to_dict()
        })

    # Force upgrade to mature
    old_state = tenant.maturity_state
    tenant.maturity_state = MaturityState.MATURE

    try:
        # Log the forced upgrade
        log_admin_action(
            tenant_id=tenant.id,
            actor_user_id=None,  # Super admin is not a tenant member
            action_type=AuditLog.ACTION_MATURITY_CHANGE,
            target_entity='tenant',
            target_id=tenant.id,
            details={
                'old_state': old_state.value,
                'new_state': MaturityState.MATURE.value,
                'trigger': 'forced_upgrade',
                'actor': 'super_admin',
                'reason': 'Manual override by super admin'
            }
        )
        db.session.commit()

        return jsonify({
            'message': 'Tenant forced to MATURE state successfully',
            'tenant': tenant.to_dict(),
            'old_state': old_state.value,
            'new_state': tenant.maturity_state.value
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Failed to force upgrade for {domain}: {str(e)}')
        return jsonify({'error': 'Failed to force upgrade. Please try again or contact support.'}), 500


@app.route('/api/tenants/<domain>', methods=['DELETE'])
@master_required
def api_delete_tenant(domain):
    """Soft-delete a tenant with 30-day retention window (super admin only).

    This marks the tenant for deletion but preserves all data for 30 days:
    - Tenant record is marked as deleted (not removed)
    - All decisions are soft-deleted with retention window
    - Audit logs are preserved (never deleted)
    - Data can be restored during the retention window

    After 30 days, a scheduled job should permanently delete the data.

    Requires confirmation parameter to prevent accidental deletion.
    """
    domain = domain.lower()
    data = request.get_json(silent=True) or {}

    # Require explicit confirmation
    if not data.get('confirm_delete'):
        return jsonify({
            'error': 'Deletion requires explicit confirmation',
            'message': 'Include {"confirm_delete": true} in request body to proceed'
        }), 400

    # Get tenant record
    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        return jsonify({'error': f'Tenant not found for domain: {domain}'}), 404

    # Check if already deleted
    if tenant.deleted_at:
        return jsonify({
            'error': f'Tenant {domain} is already marked for deletion',
            'deletion_expires_at': tenant.deletion_expires_at.isoformat() if tenant.deletion_expires_at else None
        }), 400

    tenant_id = tenant.id
    deletion_time = datetime.utcnow()
    retention_days = 30  # Configurable retention window
    deletion_expires_at = deletion_time + timedelta(days=retention_days)

    try:
        # Get counts for reporting
        member_count = TenantMembership.query.filter_by(tenant_id=tenant_id).count()
        space_count = Space.query.filter_by(tenant_id=tenant_id).count()
        decision_count = ArchitectureDecision.query.filter_by(tenant_id=tenant_id).count()

        # Soft delete all decisions with retention window
        decisions = ArchitectureDecision.query.filter_by(tenant_id=tenant_id).all()
        for decision in decisions:
            if not decision.deleted_at:
                decision.deleted_at = deletion_time
                decision.deleted_by_id = None  # Super admin deletion
                decision.deletion_expires_at = deletion_expires_at

        # Soft-delete the tenant (keep the record but mark as deleted)
        tenant.deleted_at = deletion_time
        tenant.deleted_by_admin = session.get('master_username', 'super_admin')
        tenant.deletion_expires_at = deletion_expires_at
        tenant.status = 'deleted'

        # Note: Skipping audit log for super admin actions as there's no user_id
        # Super admin actions are logged via session username in tenant.deleted_by_admin

        # Update domain approval status
        domain_approval = DomainApproval.query.filter_by(domain=domain).first()
        if domain_approval:
            domain_approval.status = 'rejected'
            domain_approval.rejection_reason = 'Tenant deleted by super admin'
            domain_approval.reviewed_at = deletion_time

        db.session.commit()

        return jsonify({
            'message': f'Tenant {domain} scheduled for deletion',
            'soft_deleted': {
                'domain': domain,
                'tenant_id': tenant_id,
                'deleted_at': deletion_time.isoformat(),
                'deletion_expires_at': deletion_expires_at.isoformat(),
                'retention_days': retention_days,
                'affected': {
                    'members': member_count,
                    'spaces': space_count,
                    'decisions_soft_deleted': decision_count
                },
                'note': f'Data will be permanently deleted after {retention_days} days. Contact support to restore.'
            }
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Failed to delete tenant {domain}: {str(e)}')
        return jsonify({'error': 'Failed to delete tenant. Please try again or contact support.'}), 500


@app.route('/api/tenants/<domain>/restore', methods=['POST'])
@master_required
def api_restore_tenant(domain):
    """Restore a soft-deleted tenant (super admin only).

    Can only restore tenants within their retention window.
    """
    domain = domain.lower()

    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        return jsonify({'error': f'Tenant not found for domain: {domain}'}), 404

    if not tenant.deleted_at:
        return jsonify({'error': f'Tenant {domain} is not deleted'}), 400

    # Check if retention window has expired
    if tenant.deletion_expires_at and datetime.utcnow() > tenant.deletion_expires_at:
        return jsonify({
            'error': 'Retention window has expired',
            'message': 'This tenant cannot be restored as the retention period has passed'
        }), 400

    try:
        # Restore tenant
        tenant.deleted_at = None
        tenant.deleted_by_admin = None
        tenant.deletion_expires_at = None
        tenant.status = 'active'

        # Restore all soft-deleted decisions
        decisions = ArchitectureDecision.query.filter_by(tenant_id=tenant.id).all()
        restored_count = 0
        for decision in decisions:
            if decision.deleted_at:
                decision.deleted_at = None
                decision.deleted_by_id = None
                decision.deletion_expires_at = None
                restored_count += 1

        # Log the restoration
        log_admin_action(
            tenant_id=tenant.id,
            actor_user_id=None,
            action_type='restore',
            target_entity='tenant',
            target_id=tenant.id,
            details={
                'domain': domain,
                'actor': 'super_admin',
                'decisions_restored': restored_count
            }
        )

        # Update domain approval
        domain_approval = DomainApproval.query.filter_by(domain=domain).first()
        if domain_approval and domain_approval.status == 'rejected':
            domain_approval.status = 'approved'
            domain_approval.rejection_reason = None

        db.session.commit()

        return jsonify({
            'message': f'Tenant {domain} restored successfully',
            'restored': {
                'domain': domain,
                'tenant_id': tenant.id,
                'decisions_restored': restored_count
            }
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Failed to restore tenant {domain}: {str(e)}')
        return jsonify({'error': 'Failed to restore tenant. Please try again or contact support.'}), 500


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
    data = request.get_json() or {}

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

    data = request.get_json() or {}

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

    data = request.get_json() or {}

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


# ==================== API Routes - Spaces ====================

@app.route('/api/spaces', methods=['GET'])
@login_required
def api_list_spaces():
    """List all spaces for the user's tenant."""
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot access tenant data'}), 403

    tenant = get_current_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    spaces = Space.query.filter_by(tenant_id=tenant.id).order_by(Space.is_default.desc(), Space.name).all()
    return jsonify([s.to_dict() for s in spaces])


@app.route('/api/spaces', methods=['POST'])
@steward_or_admin_required
def api_create_space():
    """Create a new space (steward or admin only)."""
    data = request.get_json() or {}

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Space name is required'}), 400

    if len(name) > 255:
        return jsonify({'error': 'Space name cannot exceed 255 characters'}), 400

    description = data.get('description', '').strip() if data.get('description') else None

    # Check for duplicate name in tenant
    existing = Space.query.filter_by(tenant_id=g.current_tenant.id, name=name).first()
    if existing:
        return jsonify({'error': 'A space with this name already exists'}), 400

    space = Space(
        tenant_id=g.current_tenant.id,
        name=name,
        description=description,
        is_default=False,
        created_by_id=g.current_user.id
    )
    db.session.add(space)

    # Log the action
    log_admin_action(
        tenant_id=g.current_tenant.id,
        actor_user_id=g.current_user.id,
        action_type=AuditLog.ACTION_CREATE_SPACE,
        target_entity='space',
        target_id=None,  # Will be set after flush
        details={'name': name}
    )

    db.session.commit()

    return jsonify(space.to_dict()), 201


@app.route('/api/spaces/<int:space_id>', methods=['GET'])
@login_required
def api_get_space(space_id):
    """Get a specific space."""
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot access tenant data'}), 403

    tenant = get_current_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    space = Space.query.filter_by(id=space_id, tenant_id=tenant.id).first()
    if not space:
        return jsonify({'error': 'Space not found'}), 404

    # Include decision count
    result = space.to_dict()
    result['decision_count'] = space.decision_links.count()

    return jsonify(result)


@app.route('/api/spaces/<int:space_id>', methods=['PUT'])
@steward_or_admin_required
def api_update_space(space_id):
    """Update a space (steward or admin only)."""
    space = Space.query.filter_by(id=space_id, tenant_id=g.current_tenant.id).first()
    if not space:
        return jsonify({'error': 'Space not found'}), 404

    data = request.get_json() or {}
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Can't rename default space to something else
    if space.is_default and data.get('name') and data.get('name') != space.name:
        return jsonify({'error': 'Cannot rename the default space'}), 400

    if data.get('name'):
        name = data['name'].strip()
        if not name:
            return jsonify({'error': 'Space name cannot be empty'}), 400
        if len(name) > 255:
            return jsonify({'error': 'Space name cannot exceed 255 characters'}), 400

        # Check for duplicate
        existing = Space.query.filter(
            Space.tenant_id == g.current_tenant.id,
            Space.name == name,
            Space.id != space_id
        ).first()
        if existing:
            return jsonify({'error': 'A space with this name already exists'}), 400

        space.name = name

    if 'description' in data:
        space.description = data['description'].strip() if data['description'] else None

    db.session.commit()

    return jsonify(space.to_dict())


@app.route('/api/spaces/<int:space_id>', methods=['DELETE'])
@admin_required
def api_delete_space(space_id):
    """Delete a space (admin only). Cannot delete default space."""
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot access tenant data'}), 403

    tenant = get_current_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    space = Space.query.filter_by(id=space_id, tenant_id=tenant.id).first()
    if not space:
        return jsonify({'error': 'Space not found'}), 404

    if space.is_default:
        return jsonify({'error': 'Cannot delete the default space'}), 400

    # Log the action before deletion
    log_admin_action(
        tenant_id=tenant.id,
        actor_user_id=g.current_user.id,
        action_type=AuditLog.ACTION_DELETE_SPACE,
        target_entity='space',
        target_id=space.id,
        details={'name': space.name}
    )

    # Delete removes links but not decisions (cascade configured in model)
    db.session.delete(space)
    db.session.commit()

    return jsonify({'message': 'Space deleted successfully'})


@app.route('/api/spaces/<int:space_id>/decisions', methods=['GET'])
@login_required
def api_list_space_decisions(space_id):
    """List decisions in a specific space."""
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot access tenant data'}), 403

    tenant = get_current_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    space = Space.query.filter_by(id=space_id, tenant_id=tenant.id).first()
    if not space:
        return jsonify({'error': 'Space not found'}), 404

    # Get decisions linked to this space
    decision_ids = [link.decision_id for link in space.decision_links.all()]
    decisions = ArchitectureDecision.query.filter(
        ArchitectureDecision.id.in_(decision_ids),
        ArchitectureDecision.deleted_at == None
    ).order_by(ArchitectureDecision.id.desc()).all()

    return jsonify([d.to_dict() for d in decisions])


@app.route('/api/decisions/<int:decision_id>/spaces', methods=['GET'])
@login_required
def api_get_decision_spaces(decision_id):
    """Get spaces that a decision belongs to."""
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot access tenant data'}), 403

    tenant = get_current_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    decision = ArchitectureDecision.query.filter_by(
        id=decision_id,
        domain=g.current_user.sso_domain,
        deleted_at=None
    ).first()
    if not decision:
        return jsonify({'error': 'Decision not found'}), 404

    # Get linked spaces
    links = DecisionSpace.query.filter_by(decision_id=decision_id).all()
    space_ids = [link.space_id for link in links]
    spaces = Space.query.filter(Space.id.in_(space_ids)).all() if space_ids else []

    return jsonify([s.to_dict() for s in spaces])


@app.route('/api/decisions/<int:decision_id>/spaces', methods=['PUT'])
@login_required
def api_update_decision_spaces(decision_id):
    """Update which spaces a decision belongs to."""
    if is_master_account():
        return jsonify({'error': 'Master accounts cannot access tenant data'}), 403

    tenant = get_current_tenant()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    decision = ArchitectureDecision.query.filter_by(
        id=decision_id,
        domain=g.current_user.sso_domain,
        deleted_at=None
    ).first()
    if not decision:
        return jsonify({'error': 'Decision not found'}), 404

    data = request.get_json() or {}
    if not data or 'space_ids' not in data:
        return jsonify({'error': 'space_ids is required'}), 400

    space_ids = data['space_ids']
    if not isinstance(space_ids, list):
        return jsonify({'error': 'space_ids must be a list'}), 400

    # Validate all space_ids belong to the tenant
    valid_spaces = Space.query.filter(
        Space.id.in_(space_ids),
        Space.tenant_id == tenant.id
    ).all()
    valid_ids = {s.id for s in valid_spaces}

    invalid_ids = set(space_ids) - valid_ids
    if invalid_ids:
        return jsonify({'error': f'Invalid space IDs: {list(invalid_ids)}'}), 400

    # Remove existing links
    DecisionSpace.query.filter_by(decision_id=decision_id).delete()

    # Add new links
    for space_id in space_ids:
        link = DecisionSpace(
            decision_id=decision_id,
            space_id=space_id,
            added_by_id=g.current_user.id
        )
        db.session.add(link)

    db.session.commit()

    # Return updated spaces
    spaces = Space.query.filter(Space.id.in_(space_ids)).all() if space_ids else []
    return jsonify([s.to_dict() for s in spaces])


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


# ==================== Test-Only API Endpoints ====================
# These endpoints are ONLY available when FLASK_ENV=testing
# They allow E2E tests to set up test data without manual intervention

@app.route('/api/test/reset-database', methods=['POST'])
def reset_test_database():
    """Reset database to clean state. TEST ONLY."""
    if os.environ.get('FLASK_ENV') != 'testing':
        return jsonify({'error': 'Not available'}), 403

    try:
        # Use SQLAlchemy's drop_all/create_all for a clean slate
        # This handles missing tables gracefully
        db.drop_all()
        db.create_all()

        # Create default super admin using the same credentials as create_default_master
        from models import DEFAULT_MASTER_USERNAME, DEFAULT_MASTER_PASSWORD
        admin = MasterAccount(
            username=DEFAULT_MASTER_USERNAME,
            name='System Administrator'
        )
        admin.set_password(DEFAULT_MASTER_PASSWORD)
        db.session.add(admin)
        db.session.commit()

        logger.info("Test database reset complete")
        return jsonify({'message': 'Database reset successful'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database reset failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/test/create-user', methods=['POST'])
def create_test_user():
    """Create a user with specified role. TEST ONLY."""
    if os.environ.get('FLASK_ENV') != 'testing':
        return jsonify({'error': 'Not available'}), 403

    try:
        data = request.get_json(force=True)  # Force parse even without content-type
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
    except Exception as e:
        logger.error(f"JSON parse error: {str(e)}")
        return jsonify({'error': f'Invalid JSON: {str(e)}'}), 400

    email = data.get('email')
    password = data.get('password')
    name = data.get('name', email.split('@')[0] if email else 'Test User')
    role = data.get('role', 'user')
    domain = data.get('domain', email.split('@')[1] if email and '@' in email else 'test.com')

    if not email or not password:
        return jsonify({'error': 'email and password required'}), 400

    try:
        from werkzeug.security import generate_password_hash

        # Get or create tenant
        tenant = Tenant.query.filter_by(domain=domain).first()
        if not tenant:
            tenant = Tenant(
                domain=domain,
                name=f"{domain.split('.')[0].title()} Organization",
                maturity_state='BOOTSTRAP'
            )
            db.session.add(tenant)
            db.session.flush()

            # Create default space for tenant
            default_space = Space(
                tenant_id=tenant.id,
                name='General',
                description='Default space for all architecture decisions',
                is_default=True
            )
            db.session.add(default_space)

        # Create user
        user = User(
            email=email,
            name=name,
            sso_domain=domain,
            password_hash=generate_password_hash(password),
            auth_type='local'
        )
        db.session.add(user)
        db.session.flush()

        # Map role string to GlobalRole enum
        role_map = {
            'user': GlobalRole.USER,
            'admin': GlobalRole.ADMIN,
            'steward': GlobalRole.STEWARD,
            'provisional_admin': GlobalRole.PROVISIONAL_ADMIN
        }
        global_role = role_map.get(role, GlobalRole.USER)

        # Create tenant membership
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            global_role=global_role
        )
        db.session.add(membership)
        db.session.commit()

        logger.info(f"Test user created: {email} with role {role}")
        return jsonify({
            'message': 'User created',
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'role': role,
                'domain': domain
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create test user failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/test/set-tenant-maturity', methods=['POST'])
def set_test_tenant_maturity():
    """Set tenant maturity state. TEST ONLY."""
    if os.environ.get('FLASK_ENV') != 'testing':
        return jsonify({'error': 'Not available'}), 403

    data = request.get_json() or {}
    domain = data.get('domain')
    state = data.get('state', 'BOOTSTRAP').upper()

    if not domain:
        return jsonify({'error': 'domain required'}), 400

    if state not in ['BOOTSTRAP', 'MATURE']:
        return jsonify({'error': 'state must be BOOTSTRAP or MATURE'}), 400

    try:
        tenant = Tenant.query.filter_by(domain=domain).first()
        if not tenant:
            return jsonify({'error': f'Tenant {domain} not found'}), 404

        tenant.maturity_state = MaturityState[state]
        db.session.commit()

        logger.info(f"Tenant {domain} maturity set to {state}")
        return jsonify({
            'message': 'Maturity state updated',
            'tenant': {
                'id': tenant.id,
                'domain': tenant.domain,
                'maturity_state': tenant.maturity_state.value if tenant.maturity_state else None
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Set tenant maturity failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/test/create-incomplete-user', methods=['POST'])
def create_incomplete_test_user():
    """Create an incomplete user (no credentials) with setup token. TEST ONLY."""
    if os.environ.get('FLASK_ENV') != 'testing':
        return jsonify({'error': 'Not available'}), 403

    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
    except Exception as e:
        logger.error(f"JSON parse error: {str(e)}")
        return jsonify({'error': f'Invalid JSON: {str(e)}'}), 400

    email = data.get('email')
    name = data.get('name', email.split('@')[0] if email else 'Test User')
    domain = data.get('domain', email.split('@')[1] if email and '@' in email else 'test.com')

    if not email:
        return jsonify({'error': 'email required'}), 400

    try:
        import secrets
        from datetime import datetime, timedelta

        # Get or create tenant
        tenant = Tenant.query.filter_by(domain=domain).first()
        if not tenant:
            tenant = Tenant(
                domain=domain,
                name=f"{domain.split('.')[0].title()} Organization",
                maturity_state='BOOTSTRAP'
            )
            db.session.add(tenant)
            db.session.flush()

            # Create default space for tenant
            default_space = Space(
                tenant_id=tenant.id,
                name='General',
                description='Default space for all architecture decisions',
                is_default=True
            )
            db.session.add(default_space)

        # Create user WITHOUT password (incomplete state)
        user = User(
            email=email,
            name=name,
            sso_domain=domain,
            password_hash=None,  # No password - incomplete user
            auth_type=None  # No auth type yet
        )
        db.session.add(user)
        db.session.flush()

        # Create tenant membership
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        db.session.add(membership)

        # Generate setup token
        setup_token = secrets.token_urlsafe(32)
        token_expires = datetime.utcnow() + timedelta(hours=48)

        # Store token in SetupToken table if it exists, otherwise use session approach
        try:
            setup_token_record = SetupToken(
                user_id=user.id,
                token=setup_token,
                expires_at=token_expires,
                is_recovery=False
            )
            db.session.add(setup_token_record)
        except Exception:
            # If SetupToken model doesn't exist, we'll just return the token
            pass

        db.session.commit()

        # Build setup URL (this is what the URL change tests verify)
        setup_url = f'/{domain}/setup?token={setup_token}'

        logger.info(f"Incomplete test user created: {email}")
        return jsonify({
            'message': 'Incomplete user created',
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'domain': domain,
                'has_password': False,
                'has_passkey': False
            },
            'setup_url': setup_url,
            'setup_token': setup_token
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create incomplete test user failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
