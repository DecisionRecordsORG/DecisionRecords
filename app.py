import os
import json
import secrets
import logging
import sys
import traceback

# psycopg2 is only needed for PostgreSQL - make import optional for SQLite local dev
try:
    import psycopg2
except ImportError:
    psycopg2 = None

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g, send_from_directory
from authlib.integrations.requests_client import OAuth2Session
from models import db, User, MasterAccount, SSOConfig, EmailConfig, Subscription, ArchitectureDecision, DecisionHistory, AuthConfig, WebAuthnCredential, AccessRequest, EmailVerification, ITInfrastructure, SystemConfig, DomainApproval, save_history, Tenant, TenantMembership, TenantSettings, Space, DecisionSpace, GlobalRole, MaturityState, AuditLog, RoleRequest, RequestedRole, RequestStatus, SlackWorkspace, SlackUserMapping, SetupToken, TeamsWorkspace, TeamsUserMapping, TeamsConversationReference, AIApiKey, AIInteractionLog, LLMProvider, AIChannel, AIAction, LoginHistory, log_login_attempt
from datetime import datetime, timedelta, timezone
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
    sanitize_request_data, sanitize_string
)
from feature_flags import (
    require_slack, require_teams, require_enterprise, require_feature,
    get_enabled_features, is_slack_enabled, is_teams_enabled, is_enterprise,
    is_feature_enabled, is_analytics_enabled, EDITION, Edition
)

# Enterprise Edition imports - loaded conditionally based on edition
if is_enterprise():
    from ee.backend.azure.keyvault_client import keyvault_client
    from ee.backend.analytics.analytics import track_endpoint, capture_exception
    from ee.backend.cloudflare.cloudflare_security import (
        setup_cloudflare_security, require_cloudflare_access,
        get_cloudflare_config_for_api, invalidate_cloudflare_cache
    )
else:
    # Community Edition - use stubs for keyvault_client
    class KeyVaultClientStub:
        """Stub for keyvault_client that uses environment variables only."""
        def get_database_url(self):
            return os.environ.get('DATABASE_URL', 'sqlite:///instance/decisions.db')

        def get_flask_secret_key(self):
            return os.environ.get('SECRET_KEY')

        def get_secret(self, name, fallback_env_var=None, default=None):
            if fallback_env_var:
                return os.environ.get(fallback_env_var, default)
            return os.environ.get(name.upper().replace('-', '_'), default)

        def get_smtp_credentials(self):
            """Get SMTP credentials from environment variables (CE stub)."""
            username = os.environ.get('SMTP_USERNAME')
            password = os.environ.get('SMTP_PASSWORD')
            return username, password

    keyvault_client = KeyVaultClientStub()
    def track_endpoint(name): return lambda f: f  # No-op decorator
    def capture_exception(e, **kwargs): pass  # No-op
    def setup_cloudflare_security(app): pass
    def require_cloudflare_access(f): return f
    def get_cloudflare_config_for_api(): return {}
    def invalidate_cloudflare_cache(): pass

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

# ==================== CORS Configuration for Marketing Site ====================
# The marketing website runs on a separate domain and needs to call authentication
# endpoints on the app domain. Configure CORS for these specific endpoints.
from flask_cors import CORS

# Marketing site origins (production + local development)
MARKETING_ORIGINS = [
    'https://decisionrecords.org',       # Production marketing site
    'http://localhost:4201',              # Local marketing site development
    'http://127.0.0.1:4201',              # Alternative localhost
]

# Enable CORS globally but with restricted origins
# This allows the marketing site to call auth endpoints for signup/signin
CORS(app, resources={
    r"/api/auth/*": {"origins": MARKETING_ORIGINS, "supports_credentials": True},
    r"/api/system/config": {"origins": MARKETING_ORIGINS},
    r"/api/blog/*": {"origins": MARKETING_ORIGINS},
    r"/api/contact": {"origins": MARKETING_ORIGINS},
}, supports_credentials=True)

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

# Session cookie domain - allows cookies to be shared across subdomains
# Required for OAuth flow: callback on decisionrecords.org, app on app.decisionrecords.org
_cookie_domain = os.environ.get('SESSION_COOKIE_DOMAIN')
if _cookie_domain:
    app.config['SESSION_COOKIE_DOMAIN'] = _cookie_domain
    logger.info(f"Session cookie domain set to: {_cookie_domain}")

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

# ==================== Cloudflare Security ====================
# Validates requests come through Cloudflare (blocks direct IP access)
# Production only - disabled in testing mode

if os.environ.get('FLASK_ENV') != 'testing':
    setup_cloudflare_security(app)
    logger.info("Cloudflare origin validation enabled")
else:
    logger.info("TESTING MODE: Cloudflare security checks disabled")

# ==================== Log Forwarding (OpenTelemetry) ====================
# Forwards logs to configured OTLP endpoint (Grafana, Datadog, etc.) - Enterprise only

if is_enterprise():
    try:
        from ee.backend.analytics.log_forwarding import setup_log_forwarding
        setup_log_forwarding(app)
    except ImportError as e:
        logger.warning(f"Log forwarding module not available: {e}")
    except Exception as e:
        logger.error(f"Failed to initialize log forwarding: {e}")

# ==================== Enterprise Edition Module Registration ====================
# EE modules are packaged as Flask Blueprints for clean separation.
# Each module (Slack, Teams, AI, Analytics, etc.) is self-contained in ee/backend/
# Community Edition builds exclude the ee/ directory entirely.

if is_enterprise():
    try:
        from ee.backend import register_all_blueprints, init_ee_services
        registered_modules = register_all_blueprints(app)
        if registered_modules:
            logger.info(f"Enterprise Edition modules registered: {', '.join(registered_modules)}")
        init_ee_services(app)
    except ImportError as e:
        logger.warning(f"EE module registration not available: {e}")
        # Fallback: try individual module registration
        try:
            from ee.backend.ai.api import ai_api
            app.register_blueprint(ai_api)
            logger.info("AI API Blueprint registered at /api/ai (fallback)")
        except ImportError:
            pass

# ==================== Analytics Tracking Middleware ====================
# Automatic event tracking for all API endpoints based on configured mappings (Enterprise only)

if is_enterprise():
    try:
        from ee.backend.analytics.analytics import init_tracking_middleware
        init_tracking_middleware(app)
    except Exception as e:
        logger.warning(f"Failed to initialize analytics tracking middleware: {e}")

# ==================== OAuth Base URL Helper ====================
# For OAuth callbacks, we need to generate redirect_uri that matches what's registered
# with the OAuth provider. When app runs on a subdomain but OAuth is registered on the
# root domain (via Cloudflare Worker routing), we need to override the base URL.

def get_oauth_base_url():
    """Get the base URL for OAuth callback URIs.

    Priority:
    1. OAUTH_BASE_URL environment variable (for production with Cloudflare Worker routing)
    2. request.host_url (for local development and standard setups)

    In production, OAUTH_BASE_URL should be set to 'https://decisionrecords.org' since
    OAuth callbacks are registered on the root domain, which the Cloudflare Worker
    routes to the app on app.decisionrecords.org.
    """
    oauth_base_url = os.environ.get('OAUTH_BASE_URL')
    if oauth_base_url:
        return oauth_base_url.rstrip('/')

    # Fallback to request.host_url (force https in production)
    base_url = request.host_url.rstrip('/')
    if not base_url.startswith('https://') and 'localhost' not in base_url:
        base_url = base_url.replace('http://', 'https://')
    return base_url


def get_app_base_url():
    """Get the base URL for the application (for post-authentication redirects).

    Priority:
    1. APP_BASE_URL environment variable (for production with separate app subdomain)
    2. request.host_url (for local development and standard setups)

    In production, APP_BASE_URL should be set to 'https://app.decisionrecords.org'
    so that after OAuth authentication (which happens on the root domain), users
    are redirected to the correct app subdomain.
    """
    app_base_url = os.environ.get('APP_BASE_URL')
    if app_base_url:
        return app_base_url.rstrip('/')

    # Fallback to request.host_url (force https in production)
    base_url = request.host_url.rstrip('/')
    if not base_url.startswith('https://') and 'localhost' not in base_url:
        base_url = base_url.replace('http://', 'https://')
    return base_url


# ==================== Global Error Handlers ====================
# SECURITY: Prevent stack traces and sensitive information from leaking to clients
# All errors are logged server-side but only generic messages are returned to clients

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler to prevent stack trace leakage."""
    # Log the full error details server-side with request context
    logger.error(f"Unhandled exception: {str(e)} | Path: {request.path} | Method: {request.method}")
    logger.error(traceback.format_exc())

    # Capture to PostHog if enabled (Enterprise only)
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

    # Capture to PostHog if enabled (Enterprise only)
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


# Common attack path patterns to silently block (WordPress, PHP, etc.)
ATTACK_PATH_PATTERNS = (
    '.php',           # PHP files (xmlrpc.php, wp-login.php, etc.)
    '.env',           # Environment files
    '.git',           # Git directory
    '.config',        # Config files
    'phpinfo',        # PHP info pages
    'phpunit',        # PHPUnit exploits
    'wp-',            # WordPress paths
    'wordpress',      # WordPress paths
    'admin/.env',     # Admin env files
    'vendor/',        # PHP vendor directories
    'eval-stdin',     # PHP eval exploits
    '/cgi-bin/',      # CGI exploits
    'shell',          # Shell access attempts
    '.asp',           # ASP files
    '.jsp',           # JSP files
    'phpmyadmin',     # phpMyAdmin
    'mysql',          # MySQL admin attempts
    'adminer',        # Adminer DB tool
    'debug',          # Debug endpoints
    '/.well-known/security.txt',  # Not an attack but unnecessary
)


@app.before_request
def block_attack_paths():
    """Silently return 404 for common attack/scanner paths.

    This prevents unnecessary error logging and PostHog exception tracking
    for automated vulnerability scanners probing for WordPress, PHP, etc.
    """
    path_lower = request.path.lower()

    # Check if path matches any attack pattern
    for pattern in ATTACK_PATH_PATTERNS:
        if pattern in path_lower:
            # Return 404 silently - don't log, don't track
            return '', 404

    return None  # Continue to normal request handling


# Initialize database
db.init_app(app)

# Database initialization flag
_db_initialized = False

# EE:START - Blog Seed Data
# Blog posts to auto-seed (source of truth for blog metadata)
# Content is stored in Angular component; this is metadata only
BLOG_POSTS_SEED = [
    {
        'slug': 'claude-code-integration-with-decision-records',
        'title': 'Claude Code Integration With Decision Records',
        'excerpt': "Two commands. That's all it takes to give Claude Code persistent access to your team's architecture decisions. Here's the complete setup guide.",
        'author': 'Decision Records',
        'category': 'Technical',
        'read_time': '6 min read',
        'image': '/assets/blog/claude-code-integration.svg',
        'meta_description': 'Learn how to integrate Claude Code with Decision Records to give your AI assistant persistent access to architecture decisions. Complete setup guide with copy-paste commands.',
        'featured': True,
        'publish_date': datetime(2025, 1, 4, tzinfo=timezone.utc),
    },
    {
        'slug': 'how-should-teams-document-important-decisions',
        'title': 'How Should Teams Document Important Decisions?',
        'excerpt': 'Most teams make important decisions but lose the context behind them. We all agree documentation matters. But in practice, we want it to be brief and unobtrusive.',
        'author': 'Decision Records',
        'category': 'Documentation',
        'read_time': '5 min read',
        'image': '/assets/blog/documenting-decisions.svg',
        'meta_description': 'Learn how teams can effectively document important decisions without creating overhead.',
        'featured': False,
        'publish_date': datetime(2024, 12, 1, tzinfo=timezone.utc),
    },
    {
        'slug': 'how-to-track-decisions-at-a-startup',
        'title': 'How to Track Decisions at a Startup',
        'excerpt': "Startups make decisions constantly. Pricing changes, product bets, hiring trade-offs, positioning shifts. The assumption is simple: we'll remember. That assumption rarely holds.",
        'author': 'Decision Records',
        'category': 'Startups',
        'read_time': '7 min read',
        'image': '/assets/blog/startup-decisions.svg',
        'meta_description': 'Practical guide to tracking decisions at fast-moving startups without slowing down.',
        'featured': False,
        'publish_date': datetime(2024, 12, 15, tzinfo=timezone.utc),
    },
    {
        'slug': 'decision-habit-framework-fashion-brands',
        'title': 'A Decision Habit Framework for Fast-Moving Fashion Brands',
        'excerpt': 'Fashion brands are not slow by accident. They are fast by necessity. The risk is not how decisions are made—it is how quickly decision context disappears.',
        'author': 'Decision Records',
        'category': 'Retail',
        'read_time': '5 min read',
        'image': '/assets/blog/fashion-decisions.svg',
        'meta_description': 'A decision documentation framework designed for the fast pace of fashion retail.',
        'featured': False,
        'publish_date': datetime(2024, 12, 20, tzinfo=timezone.utc),
    },
]


def seed_blog_posts():
    """Seed blog posts that don't exist in the database yet."""
    from models import BlogPost

    created_count = 0
    for post_data in BLOG_POSTS_SEED:
        existing = BlogPost.query.filter_by(slug=post_data['slug']).first()
        if not existing:
            post = BlogPost(**post_data)
            db.session.add(post)
            logger.info(f"Seeding blog post: {post_data['slug']}")
            created_count += 1

    if created_count > 0:
        db.session.commit()
        logger.info(f"Seeded {created_count} new blog post(s)")
    else:
        logger.info("All blog posts already exist in database")
# EE:END - Blog Seed Data


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
                if database_url.startswith('postgresql://') and psycopg2 is not None:
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
                    # Fallback to SQLAlchemy for SQLite or when psycopg2 not available
                    with db.engine.connect() as connection:
                        connection.execute(db.text("SELECT 1"))
                    logger.info("Database connection successful using SQLAlchemy")
                
                # Create tables
                logger.info("Creating database tables...")
                db.create_all()
                logger.info("Database tables created")

                # Run migrations for any schema changes
                # The migration system handles both SQLite and PostgreSQL
                logger.info("Running schema migrations...")
                try:
                    from migrations import run_migrations
                    migrations_applied = run_migrations(db)
                    logger.info(f"Migration check completed ({migrations_applied} migrations applied)")
                except Exception as migration_error:
                    logger.warning(f"Schema migration check failed (non-critical): {str(migration_error)}")
                    # Continue anyway - migrations are for schema updates, not blocking

                # Seed blog posts (auto-adds any missing posts from BLOG_POSTS_SEED)
                logger.info("Checking blog posts...")
                try:
                    seed_blog_posts()
                except Exception as blog_error:
                    logger.warning(f"Blog post seeding failed (non-critical): {str(blog_error)}")
                    db.session.rollback()

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
                        # Default to OFF for Community Edition (self-hosters may not have SMTP)
                        # Default to ON for Enterprise Edition
                        default_value = 'true' if is_enterprise() else 'false'
                        config = SystemConfig(
                            key=SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED,
                            value=default_value,
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

                # Seed blog posts if none exist
                logger.info("Checking blog posts...")
                try:
                    from models import BlogPost
                    if BlogPost.query.count() == 0:
                        logger.info("Seeding default blog posts...")
                        posts = [
                            BlogPost(
                                slug='how-should-teams-document-important-decisions',
                                title='How Should Teams Document Important Decisions?',
                                excerpt='Most teams make important decisions but lose the context behind them. We all agree documentation matters. But in practice, we want it to be brief and unobtrusive.',
                                author='Decision Records',
                                category='Documentation',
                                read_time='5 min read',
                                image='/assets/blog/documenting-decisions.svg',
                                meta_description='Most teams make important decisions but lose the context behind them. This article explains how teams should document decisions to preserve shared understanding as they grow.',
                                published=True,
                                featured=True,
                                publish_date=datetime(2025, 11, 1)
                            ),
                            BlogPost(
                                slug='how-to-track-decisions-at-a-startup',
                                title='How to Track Decisions at a Startup',
                                excerpt="Startups make decisions constantly. Pricing changes, product bets, hiring trade-offs, positioning shifts. The assumption is simple: we'll remember. That assumption rarely holds.",
                                author='Decision Records',
                                category='Startups',
                                read_time='7 min read',
                                image='/assets/blog/startup-decisions.svg',
                                meta_description='Learn how startups can track important decisions without slowing down. A practical guide to lightweight decision records that preserve context and support fast-moving teams.',
                                published=True,
                                featured=False,
                                publish_date=datetime(2025, 11, 8)
                            ),
                            BlogPost(
                                slug='decision-habit-framework-fashion-brands',
                                title='A Decision Habit Framework for Fast-Moving Fashion Brands',
                                excerpt='Fashion brands are not slow by accident. They are fast by necessity. The risk is not how decisions are made—it is how quickly decision context disappears.',
                                author='Decision Records',
                                category='Retail',
                                read_time='5 min read',
                                image='/assets/blog/fashion-decisions.svg',
                                meta_description='Fashion brands make decisions under pressure every day. Learn how a lightweight decision habit can preserve context without slowing momentum.',
                                published=True,
                                featured=False,
                                publish_date=datetime(2025, 11, 15)
                            ),
                        ]
                        for post in posts:
                            db.session.add(post)
                        db.session.commit()
                        logger.info(f"Seeded {len(posts)} blog posts")
                    else:
                        logger.info("Blog posts already exist")
                    # Update existing posts to November 2025 if they have December 2024 dates
                    posts_to_update = BlogPost.query.filter(
                        BlogPost.publish_date < datetime(2025, 1, 1)
                    ).all()
                    if posts_to_update:
                        logger.info(f"Updating {len(posts_to_update)} blog posts to November 2025 dates...")
                        date_mapping = {
                            'how-should-teams-document-important-decisions': datetime(2025, 11, 1),
                            'how-to-track-decisions-at-a-startup': datetime(2025, 11, 8),
                            'decision-habit-framework-fashion-brands': datetime(2025, 11, 15),
                        }
                        for post in posts_to_update:
                            if post.slug in date_mapping:
                                post.publish_date = date_mapping[post.slug]
                        db.session.commit()
                        logger.info("Blog post dates updated")
                except Exception as blog_error:
                    logger.warning(f"Blog post seeding failed (non-critical): {str(blog_error)}")
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
    session['_expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=timeout_hours)).isoformat()
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
        # Both datetimes must be timezone-aware for proper comparison
        now = datetime.now(timezone.utc)
        # Ensure expiry_time is also timezone-aware (it should be from isoformat)
        if expiry_time.tzinfo is None:
            # If stored without timezone (shouldn't happen), treat as UTC
            expiry_time = expiry_time.replace(tzinfo=timezone.utc)
        return now > expiry_time
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
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200
    else:
        return jsonify({
            'status': 'unhealthy',
            'error': app_error_state['error'],
            'details': app_error_state['details'],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 503

@app.route('/ping')
@app.route('/api/health')
def ping():
    """Simple ping endpoint for load balancer health checks - always returns 200.
    Also available at /api/health for consistency with documentation.
    """
    return jsonify({
        'status': 'ok',
        'server': 'running',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200


@app.route('/api/version')
def get_version():
    """Get application version information."""
    from version import get_build_info
    return jsonify(get_build_info()), 200


@app.route('/api/version/check')
def check_version():
    """
    Check for available updates.
    Compares current version with latest GitHub release.
    Returns update status and release information.
    """
    from version import check_for_updates
    return jsonify(check_for_updates()), 200


@app.route('/api/features')
def get_features():
    """Get enabled feature flags for frontend UI conditional rendering."""
    return jsonify(get_enabled_features()), 200


# EE:START - Blog API
# ==================== Blog API (Enterprise Edition) ====================

@app.route('/api/blog/posts')
def get_blog_posts():
    """Get all published blog posts for the blog listing page.

    Returns posts ordered by featured status (featured first), then by publish date (newest first).
    """
    from models import BlogPost

    posts = BlogPost.query.filter_by(published=True).order_by(
        BlogPost.featured.desc(),
        BlogPost.publish_date.desc()
    ).all()

    return jsonify([post.to_dict() for post in posts]), 200


@app.route('/api/blog/posts/<slug>')
def get_blog_post(slug):
    """Get a single blog post by slug.

    Returns 404 if post not found or not published.
    """
    from models import BlogPost

    post = BlogPost.query.filter_by(slug=slug, published=True).first()
    if not post:
        return jsonify({'error': 'Blog post not found'}), 404

    return jsonify(post.to_dict()), 200
# EE:END - Blog API


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

    # Get support email from SystemConfig (fallback to default)
    support_email = SystemConfig.get(
        SystemConfig.KEY_SUPPORT_EMAIL,
        SystemConfig.DEFAULT_SUPPORT_EMAIL
    )

    # Send the feedback email
    success = send_feedback_email(email_config, name, email, feedback, contact_consent=contact_consent, recipient_email=support_email)

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

    # Capture request metadata for login history
    ip_address = request.headers.get('CF-Connecting-IP', request.remote_addr)
    user_agent = request.headers.get('User-Agent')

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
        # Log successful master login
        log_login_attempt(
            email=username,
            login_method=LoginHistory.METHOD_MASTER,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent
        )
        session['master_id'] = master.id
        session['is_master'] = True
        set_session_expiry(is_admin=True)  # 1 hour default for super admin
        if request.is_json:
            return jsonify({'message': 'Login successful'}), 200
        return redirect(url_for('index'))
    else:
        # Log failed master login
        log_login_attempt(
            email=username,
            login_method=LoginHistory.METHOD_MASTER,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason='Invalid username or password'
        )
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

    # Capture request metadata for login history
    ip_address = request.headers.get('CF-Connecting-IP', request.remote_addr)
    user_agent = request.headers.get('User-Agent')

    data = request.get_json() or {}
    # Sanitize email input to prevent injection attacks
    email = sanitize_email(data.get('email', ''))
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    # Extract domain for logging
    tenant_domain = extract_domain_from_email(email) if email else None

    user = User.query.filter_by(email=email).first()
    if not user:
        log_login_attempt(
            email=email,
            login_method=LoginHistory.METHOD_PASSWORD,
            success=False,
            tenant_domain=tenant_domain,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason='User not found'
        )
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user.has_password():
        log_login_attempt(
            email=email,
            login_method=LoginHistory.METHOD_PASSWORD,
            success=False,
            user_id=user.id,
            tenant_domain=user.sso_domain,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason='No password set'
        )
        return jsonify({
            'error': 'No password set for this account',
            'has_passkey': len(user.webauthn_credentials) > 0
        }), 401

    if not user.check_password(password):
        log_login_attempt(
            email=email,
            login_method=LoginHistory.METHOD_PASSWORD,
            success=False,
            user_id=user.id,
            tenant_domain=user.sso_domain,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason='Invalid password'
        )
        return jsonify({'error': 'Invalid email or password'}), 401

    # Login successful - log it
    log_login_attempt(
        email=email,
        login_method=LoginHistory.METHOD_PASSWORD,
        success=True,
        user_id=user.id,
        tenant_domain=user.sso_domain,
        ip_address=ip_address,
        user_agent=user_agent
    )

    session['user_id'] = user.id
    set_session_expiry(is_admin=False)  # 8 hours default for regular users
    user.last_login = datetime.now(timezone.utc)
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
    # Capture request metadata for login history
    ip_address = request.headers.get('CF-Connecting-IP', request.remote_addr)
    user_agent = request.headers.get('User-Agent')

    config_id = session.pop('sso_config_id', None)
    stored_state = session.pop('oauth_state', None)

    if not config_id:
        return redirect('/')

    sso_config = db.session.get(SSOConfig, config_id)
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
            log_login_attempt(
                email='unknown',
                login_method=LoginHistory.METHOD_SSO,
                success=False,
                tenant_domain=sso_config.domain,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason='Email not provided by SSO provider'
            )
            return render_template('error.html', message='Email not provided by SSO provider'), 400

        # Verify email domain matches SSO config domain
        email_domain = extract_domain_from_email(email)
        if email_domain != sso_config.domain.lower():
            log_login_attempt(
                email=email,
                login_method=LoginHistory.METHOD_SSO,
                success=False,
                tenant_domain=sso_config.domain,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason='Email domain mismatch'
            )
            return render_template('error.html', message='Email domain does not match SSO configuration'), 403

        # Get or create user
        user = get_or_create_user(email, name, subject, sso_config.domain)

        # Log successful SSO login
        log_login_attempt(
            email=email,
            login_method=LoginHistory.METHOD_SSO,
            success=True,
            user_id=user.id,
            tenant_domain=sso_config.domain,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Set session
        session['user_id'] = user.id
        set_session_expiry(is_admin=False)  # 8 hours default for regular users

        return redirect(url_for('index'))

    except Exception as e:
        app.logger.error(f"SSO callback error: {e}")
        log_login_attempt(
            email='unknown',
            login_method=LoginHistory.METHOD_SSO,
            success=False,
            tenant_domain=sso_config.domain if sso_config else None,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=f'SSO error: {str(e)[:200]}'
        )
        return render_template('error.html', message='Authentication failed'), 500


@app.route('/logout')
def logout():
    """Log out the current user."""
    session.clear()
    # Redirect to marketing site where Google/Slack OAuth is available
    marketing_url = get_oauth_base_url()  # Returns decisionrecords.org
    response = redirect(marketing_url)
    # Explicitly delete session cookie with correct domain for cross-subdomain logout
    cookie_domain = app.config.get('SESSION_COOKIE_DOMAIN')
    response.delete_cookie(
        app.config.get('SESSION_COOKIE_NAME', 'session'),
        domain=cookie_domain,
        path='/'
    )
    return response


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """API endpoint for logout - returns JSON instead of redirect."""
    session.clear()
    # Include redirect URL for frontend to use (marketing site with OAuth options)
    marketing_url = get_oauth_base_url()
    response = jsonify({
        'message': 'Logged out successfully',
        'redirect_url': marketing_url
    })
    # Explicitly delete session cookie with correct domain for cross-subdomain logout
    cookie_domain = app.config.get('SESSION_COOKIE_DOMAIN')
    response.delete_cookie(
        app.config.get('SESSION_COOKIE_NAME', 'session'),
        domain=cookie_domain,
        path='/'
    )
    return response


@app.route('/api/auth/csrf-token', methods=['GET'])
def api_get_csrf_token():
    """Get a CSRF token for the current session.

    The frontend should call this endpoint and include the token
    in the X-CSRF-Token header for all state-changing requests.
    """
    token = generate_csrf_token()
    return jsonify({'csrf_token': token})


# EE:START - Slack OIDC Authentication
# ==================== Slack OIDC Authentication (Enterprise Edition) ====================
# Sign in with Slack using OpenID Connect (OIDC)
# This provides a frictionless signup/login experience for Slack users

@app.route('/api/auth/slack-oidc-status', methods=['GET'])
@track_endpoint('api_auth_slack_oidc_status')
def slack_oidc_status():
    """Check if Slack OIDC sign-in is enabled.

    Returns whether Slack sign-in is available for the frontend to show/hide the button.
    This is a public endpoint (no login required) since users need to see it before login.
    """
    # Check if Slack feature is enabled globally
    if not is_slack_enabled():
        return jsonify({'enabled': False, 'reason': 'slack_disabled'})

    # Check if Slack credentials are configured
    try:
        from ee.backend.slack.slack_security import get_slack_client_id
        client_id = get_slack_client_id()
        if not client_id:
            return jsonify({'enabled': False, 'reason': 'not_configured'})
    except Exception as e:
        logger.error(f"Error checking Slack OIDC status: {e}")
        return jsonify({'enabled': False, 'reason': 'configuration_error'})

    return jsonify({'enabled': True})


@app.route('/auth/slack/oidc')
@track_endpoint('auth_slack_oidc_initiate')
def slack_oidc_initiate():
    """Initiate Slack OIDC login flow.

    Redirects the user to Slack's authorization page to sign in.
    After authentication, Slack redirects back to /auth/slack/oidc/callback
    with the authorization code.
    """
    from ee.backend.slack.slack_security import (
        get_slack_client_id,
        generate_slack_oidc_state,
        SLACK_OIDC_AUTHORIZE_URL,
        SLACK_OIDC_SCOPES
    )

    # Check if Slack sign-in is enabled
    if not is_slack_enabled():
        logger.warning("Slack OIDC attempted but Slack is disabled")
        return redirect('/?error=slack_disabled')

    # Get Slack client ID
    client_id = get_slack_client_id()
    if not client_id:
        logger.error("Slack client ID not configured for OIDC")
        return redirect('/?error=slack_not_configured')

    # Get optional return_url from query params (where to redirect after login)
    return_url = request.args.get('return_url', '/')

    # Generate encrypted state for CSRF protection
    try:
        state = generate_slack_oidc_state(return_url=return_url)
    except Exception as e:
        logger.error(f"Failed to generate Slack OIDC state: {e}")
        return redirect('/?error=internal_error')

    # Build redirect URI using OAuth base URL (supports Cloudflare Worker routing)
    base_url = get_oauth_base_url()
    redirect_uri = f"{base_url}/auth/slack/oidc/callback"

    # Build Slack authorization URL
    import urllib.parse
    auth_params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': SLACK_OIDC_SCOPES,
        'redirect_uri': redirect_uri,
        'state': state,
        'nonce': secrets.token_urlsafe(16)  # Required by OIDC spec
    }
    auth_url = f"{SLACK_OIDC_AUTHORIZE_URL}?{urllib.parse.urlencode(auth_params)}"

    return redirect(auth_url)


@app.route('/auth/slack/oidc/callback')
@track_endpoint('auth_slack_oidc_callback')
def slack_oidc_callback():
    """Handle Slack OIDC callback.

    This endpoint receives the authorization code from Slack after the user
    authenticates. It exchanges the code for tokens, fetches user info,
    and creates/logs in the user based on their email domain.

    The tenant is derived from the email domain (existing logic).
    First user of a domain becomes provisional admin (existing logic).
    """
    import requests
    from ee.backend.slack.slack_security import (
        get_slack_client_id,
        get_slack_client_secret,
        verify_slack_oidc_state,
        SLACK_OIDC_TOKEN_URL,
        SLACK_OIDC_USERINFO_URL
    )

    # Capture request metadata for login history
    ip_address = request.headers.get('CF-Connecting-IP', request.remote_addr)
    user_agent = request.headers.get('User-Agent')

    # Get callback parameters
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    error_description = request.args.get('error_description', '')

    # Handle Slack errors
    if error:
        logger.warning(f"Slack OIDC error: {error} - {error_description}")
        return redirect(f'/?error=slack_auth_error&message={error}')

    if not code:
        logger.warning("Slack OIDC callback missing code")
        return redirect('/?error=missing_code')

    # Verify state parameter (CSRF protection)
    state_data = verify_slack_oidc_state(state)
    if not state_data:
        logger.warning("Invalid or expired Slack OIDC state")
        return redirect('/?error=invalid_state')

    return_url = state_data.get('return_url', '/')

    # Get Slack credentials
    client_id = get_slack_client_id()
    client_secret = get_slack_client_secret()

    if not client_id or not client_secret:
        logger.error("Slack credentials not configured for OIDC callback")
        return redirect('/?error=slack_not_configured')

    # Build redirect URI (must match the one used in authorization)
    base_url = get_oauth_base_url()
    redirect_uri = f"{base_url}/auth/slack/oidc/callback"

    try:
        # Exchange code for tokens
        token_response = requests.post(
            SLACK_OIDC_TOKEN_URL,
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            },
            timeout=30
        )

        if not token_response.ok:
            logger.error(f"Slack token exchange failed: {token_response.status_code}")
            return redirect('/?error=token_exchange_failed')

        token_data = token_response.json()
        if not token_data.get('ok', True) or 'error' in token_data:
            logger.error(f"Slack token error: {token_data.get('error')}")
            return redirect('/?error=token_exchange_failed')

        access_token = token_data.get('access_token')
        if not access_token:
            logger.error("No access token in Slack OIDC response")
            return redirect('/?error=no_access_token')

        # Fetch user info
        userinfo_response = requests.get(
            SLACK_OIDC_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30
        )

        if not userinfo_response.ok:
            logger.error(f"Slack userinfo failed: {userinfo_response.status_code}")
            return redirect('/?error=userinfo_failed')

        userinfo = userinfo_response.json()
        if not userinfo.get('ok', True) or 'error' in userinfo:
            logger.error(f"Slack userinfo error: {userinfo.get('error')}")
            return redirect('/?error=userinfo_failed')

        # Extract user details
        email = userinfo.get('email')
        name = userinfo.get('name') or userinfo.get('given_name', '')
        slack_user_id = userinfo.get('sub')  # Slack user ID from OIDC

        if not email:
            logger.warning("No email in Slack OIDC userinfo")
            return redirect('/?error=no_email')

        # Extract domain from email
        domain = extract_domain_from_email(email)

        # Check for public email domains (gmail, yahoo, etc.)
        if DomainApproval.is_public_domain(domain):
            logger.warning(f"Public email domain rejected for Slack OIDC: {domain}")
            return redirect('/?error=public_email&message=Please use your work email address')

        # Check for disposable email domains
        if DomainApproval.is_disposable_domain(domain):
            logger.warning(f"Disposable email domain rejected for Slack OIDC: {domain}")
            return redirect('/?error=disposable_email&message=Disposable email addresses are not allowed')

        # Check if this is the first user for this domain
        existing_domain_users = User.query.filter_by(sso_domain=domain).count()
        is_first_user = existing_domain_users == 0

        # Get or create user
        user = get_or_create_user(email, name, slack_user_id, domain)

        # Create Tenant if it doesn't exist (v1.5 governance)
        tenant = Tenant.query.filter_by(domain=domain).first()
        if not tenant:
            tenant = Tenant(
                domain=domain,
                name=domain,  # Default name is domain
                status='active',
                maturity_state=MaturityState.BOOTSTRAP
            )
            db.session.add(tenant)
            db.session.flush()
            logger.info(f"Created tenant for Slack OIDC domain: {domain}")

            # Create default auth config for new tenant
            auth_config = AuthConfig.query.filter_by(domain=domain).first()
            if not auth_config:
                auth_config = AuthConfig(
                    domain=domain,
                    auth_method='slack_oidc',  # Since they signed up via Slack
                    allow_password=True,
                    allow_passkey=True,
                    allow_slack_oidc=True,
                    allow_registration=True,
                    require_approval=True,
                    rp_name='Decision Records'
                )
                db.session.add(auth_config)
                logger.info(f"Created AuthConfig for Slack OIDC domain: {domain}")

            # Auto-approve corporate domain
            domain_approval = DomainApproval.query.filter_by(domain=domain).first()
            if not domain_approval:
                domain_approval = DomainApproval(
                    domain=domain,
                    status='approved',
                    requested_by_email=email,
                    requested_by_name=name,
                    auto_approved=True,
                    reviewed_at=datetime.now(timezone.utc)
                )
                db.session.add(domain_approval)
                logger.info(f"Auto-approved corporate domain via Slack OIDC: {domain}")

        # Ensure TenantMembership exists
        membership = TenantMembership.query.filter_by(
            user_id=user.id,
            tenant_id=tenant.id
        ).first()

        if not membership:
            # Create membership with appropriate role
            # First user becomes provisional admin
            role = GlobalRole.PROVISIONAL_ADMIN if is_first_user else GlobalRole.USER
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=role
            )
            db.session.add(membership)
            logger.info(f"Created TenantMembership for Slack OIDC user {email} in tenant {domain} with role {role.value}")

        db.session.commit()

        # Update auth_type to indicate Slack OIDC login
        if not user.auth_type or user.auth_type == 'local':
            user.auth_type = 'sso'  # Use 'sso' as it's the closest existing type
            db.session.commit()

        # Log successful Slack OIDC login
        log_login_attempt(
            email=email,
            login_method=LoginHistory.METHOD_SLACK_OIDC,
            success=True,
            user_id=user.id,
            tenant_domain=domain,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Set session
        session['user_id'] = user.id
        set_session_expiry(is_admin=user.is_admin)

        logger.info(f"Slack OIDC login successful for {email}")

        # Get app base URL for post-auth redirect (handles subdomain routing)
        app_base = get_app_base_url()

        # Redirect to return URL or tenant home
        # Add slack_welcome param to trigger welcome modal in frontend
        if return_url and return_url != '/' and not return_url.startswith('/?'):
            # User had a specific destination, append welcome flag
            separator = '&' if '?' in return_url else '?'
            # Ensure return_url is absolute if APP_BASE_URL is set
            if return_url.startswith('/') and app_base:
                return redirect(f'{app_base}{return_url}{separator}slack_welcome=1')
            return redirect(f'{return_url}{separator}slack_welcome=1')

        # Redirect to tenant dashboard with welcome modal trigger
        return redirect(f'{app_base}/{domain}?slack_welcome=1')

    except requests.RequestException as e:
        logger.error(f"Slack OIDC request error: {e}")
        log_login_attempt(
            email='unknown',
            login_method=LoginHistory.METHOD_SLACK_OIDC,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=f'Network error: {str(e)[:200]}'
        )
        return redirect('/?error=network_error')
    except Exception as e:
        logger.error(f"Slack OIDC callback error: {e}")
        log_login_attempt(
            email='unknown',
            login_method=LoginHistory.METHOD_SLACK_OIDC,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=f'Callback error: {str(e)[:200]}'
        )
        return redirect('/?error=internal_error')
# EE:END - Slack OIDC Authentication


# EE:START - Google OAuth Authentication
# ==================== Google OAuth Authentication (Enterprise Edition) ====================
# Sign in with Google using OAuth 2.0
# This provides an alternative auth option for users whose orgs restrict Slack OIDC

@app.route('/api/auth/google-status', methods=['GET'])
@track_endpoint('api_auth_google_status')
def google_oauth_status():
    """Check if Google OAuth sign-in is enabled.

    Returns whether Google sign-in is available for the frontend to show/hide the button.
    This is a public endpoint (no login required) since users need to see it before login.
    """
    try:
        from ee.backend.oauth_providers.google_oauth import is_google_oauth_configured
        if not is_google_oauth_configured():
            return jsonify({'enabled': False, 'reason': 'not_configured'})
    except Exception as e:
        logger.error(f"Error checking Google OAuth status: {e}")
        return jsonify({'enabled': False, 'reason': 'configuration_error'})

    return jsonify({'enabled': True})


@app.route('/auth/google')
@track_endpoint('auth_google_initiate')
def google_oauth_initiate():
    """Initiate Google OAuth login flow.

    Redirects the user to Google's authorization page to sign in.
    After authentication, Google redirects back to /auth/google/callback
    with the authorization code.
    """
    from ee.backend.oauth_providers.google_oauth import (
        get_google_client_id,
        generate_google_oauth_state,
        is_google_oauth_configured,
        GOOGLE_OAUTH_AUTHORIZE_URL,
        GOOGLE_OAUTH_SCOPES
    )

    # Check if Google sign-in is enabled
    if not is_google_oauth_configured():
        logger.warning("Google OAuth attempted but not configured")
        return redirect('/?error=google_not_configured')

    # Get Google client ID
    client_id = get_google_client_id()
    if not client_id:
        logger.error("Google client ID not configured for OAuth")
        return redirect('/?error=google_not_configured')

    # Get optional return_url from query params (where to redirect after login)
    return_url = request.args.get('return_url', '/')

    # Generate encrypted state for CSRF protection
    try:
        state = generate_google_oauth_state(return_url=return_url)
    except Exception as e:
        logger.error(f"Failed to generate Google OAuth state: {e}")
        return redirect('/?error=internal_error')

    # Build redirect URI using OAuth base URL (supports Cloudflare Worker routing)
    base_url = get_oauth_base_url()
    redirect_uri = f"{base_url}/auth/google/callback"

    # Build Google authorization URL
    import urllib.parse
    auth_params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': GOOGLE_OAUTH_SCOPES,
        'redirect_uri': redirect_uri,
        'state': state,
        'access_type': 'offline',  # Get refresh token
        'prompt': 'select_account'  # Always show account selector
    }
    auth_url = f"{GOOGLE_OAUTH_AUTHORIZE_URL}?{urllib.parse.urlencode(auth_params)}"

    return redirect(auth_url)


@app.route('/auth/google/callback')
@track_endpoint('auth_google_callback')
def google_oauth_callback():
    """Handle Google OAuth callback.

    This endpoint receives the authorization code from Google after the user
    authenticates. It exchanges the code for tokens, fetches user info,
    and creates/logs in the user based on their email domain.

    IMPORTANT: Gmail accounts are blocked - only corporate/workspace Google accounts allowed.
    The tenant is derived from the email domain (existing logic).
    First user of a domain becomes provisional admin (existing logic).
    """
    import requests as http_requests
    from ee.backend.oauth_providers.google_oauth import (
        get_google_client_id,
        get_google_client_secret,
        verify_google_oauth_state,
        GOOGLE_OAUTH_TOKEN_URL,
        GOOGLE_OAUTH_USERINFO_URL
    )

    # Capture request metadata for login history
    ip_address = request.headers.get('CF-Connecting-IP', request.remote_addr)
    user_agent = request.headers.get('User-Agent')

    # Get callback parameters
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    error_description = request.args.get('error_description', '')

    # Handle Google errors
    if error:
        logger.warning(f"Google OAuth error: {error} - {error_description}")
        return redirect(f'/?error=google_auth_error&message={error}')

    if not code:
        logger.warning("Google OAuth callback missing code")
        return redirect('/?error=missing_code')

    # Verify state parameter (CSRF protection)
    state_data = verify_google_oauth_state(state)
    if not state_data:
        logger.warning("Invalid or expired Google OAuth state")
        return redirect('/?error=invalid_state')

    return_url = state_data.get('return_url', '/')

    # Get Google credentials
    client_id = get_google_client_id()
    client_secret = get_google_client_secret()

    if not client_id or not client_secret:
        logger.error("Google credentials not configured for OAuth callback")
        return redirect('/?error=google_not_configured')

    # Build redirect URI (must match the one used in authorization)
    base_url = get_oauth_base_url()
    redirect_uri = f"{base_url}/auth/google/callback"

    try:
        # Exchange code for tokens
        token_response = http_requests.post(
            GOOGLE_OAUTH_TOKEN_URL,
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            },
            timeout=30
        )

        if not token_response.ok:
            logger.error(f"Google token exchange failed: {token_response.status_code}")
            return redirect('/?error=token_exchange_failed')

        token_data = token_response.json()
        if 'error' in token_data:
            logger.error(f"Google token error: {token_data.get('error')}")
            return redirect('/?error=token_exchange_failed')

        access_token = token_data.get('access_token')
        if not access_token:
            logger.error("No access token in Google OAuth response")
            return redirect('/?error=no_access_token')

        # Fetch user info
        userinfo_response = http_requests.get(
            GOOGLE_OAUTH_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30
        )

        if not userinfo_response.ok:
            logger.error(f"Google userinfo failed: {userinfo_response.status_code}")
            return redirect('/?error=userinfo_failed')

        userinfo = userinfo_response.json()

        # Extract user details
        email = userinfo.get('email')
        name = userinfo.get('name') or userinfo.get('given_name', '')
        google_user_id = userinfo.get('sub')  # Google user ID

        if not email:
            logger.warning("No email in Google OAuth userinfo")
            return redirect('/?error=no_email')

        # Extract domain from email
        domain = extract_domain_from_email(email)

        # Check for public email domains (gmail, yahoo, etc.)
        # IMPORTANT: Gmail accounts cannot sign up even though they authenticate with Google
        if DomainApproval.is_public_domain(domain):
            logger.warning(f"Public email domain rejected for Google OAuth: {domain}")
            return redirect('/?error=public_email&message=Please use your work email address. Personal Gmail accounts are not allowed.')

        # Check for disposable email domains
        if DomainApproval.is_disposable_domain(domain):
            logger.warning(f"Disposable email domain rejected for Google OAuth: {domain}")
            return redirect('/?error=disposable_email&message=Disposable email addresses are not allowed')

        # Check if this is the first user for this domain
        existing_domain_users = User.query.filter_by(sso_domain=domain).count()
        is_first_user = existing_domain_users == 0

        # Get or create user
        user = get_or_create_user(email, name, google_user_id, domain)

        # Create Tenant if it doesn't exist (v1.5 governance)
        tenant = Tenant.query.filter_by(domain=domain).first()
        if not tenant:
            tenant = Tenant(
                domain=domain,
                name=domain,  # Default name is domain
                status='active',
                maturity_state=MaturityState.BOOTSTRAP
            )
            db.session.add(tenant)
            db.session.flush()
            logger.info(f"Created tenant for Google OAuth domain: {domain}")

            # Create default auth config for new tenant
            auth_config = AuthConfig.query.filter_by(domain=domain).first()
            if not auth_config:
                auth_config = AuthConfig(
                    domain=domain,
                    auth_method='local',  # Default to local, allowing multiple auth methods
                    allow_password=True,
                    allow_passkey=True,
                    allow_slack_oidc=True,
                    allow_google_oauth=True,
                    allow_registration=True,
                    require_approval=True,
                    rp_name='Decision Records'
                )
                db.session.add(auth_config)
                logger.info(f"Created AuthConfig for Google OAuth domain: {domain}")

            # Auto-approve corporate domain
            domain_approval = DomainApproval.query.filter_by(domain=domain).first()
            if not domain_approval:
                domain_approval = DomainApproval(
                    domain=domain,
                    status='approved',
                    requested_by_email=email,
                    requested_by_name=name,
                    auto_approved=True,
                    reviewed_at=datetime.now(timezone.utc)
                )
                db.session.add(domain_approval)
                logger.info(f"Auto-approved corporate domain via Google OAuth: {domain}")

        # Ensure TenantMembership exists
        membership = TenantMembership.query.filter_by(
            user_id=user.id,
            tenant_id=tenant.id
        ).first()

        if not membership:
            # Create membership with appropriate role
            # First user becomes provisional admin
            role = GlobalRole.PROVISIONAL_ADMIN if is_first_user else GlobalRole.USER
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=role
            )
            db.session.add(membership)
            logger.info(f"Created TenantMembership for Google OAuth user {email} in tenant {domain} with role {role.value}")

        db.session.commit()

        # Update auth_type to indicate Google OAuth login
        if not user.auth_type or user.auth_type == 'local':
            user.auth_type = 'sso'  # Use 'sso' as it's the closest existing type
            db.session.commit()

        # Log successful Google OAuth login
        log_login_attempt(
            email=email,
            login_method=LoginHistory.METHOD_GOOGLE_OAUTH,
            success=True,
            user_id=user.id,
            tenant_domain=domain,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Set session
        session['user_id'] = user.id
        set_session_expiry(is_admin=user.is_admin)

        logger.info(f"Google OAuth login successful for {email}")

        # Get app base URL for post-auth redirect (handles subdomain routing)
        app_base = get_app_base_url()

        # Redirect to return URL or tenant home
        if return_url and return_url != '/' and not return_url.startswith('/?'):
            # Ensure return_url is absolute if APP_BASE_URL is set
            if return_url.startswith('/') and app_base:
                return redirect(f'{app_base}{return_url}')
            return redirect(return_url)

        # Redirect to tenant dashboard
        return redirect(f'{app_base}/{domain}')

    except http_requests.RequestException as e:
        logger.error(f"Google OAuth request error: {e}")
        log_login_attempt(
            email='unknown',
            login_method=LoginHistory.METHOD_GOOGLE_OAUTH,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=f'Network error: {str(e)[:200]}'
        )
        return redirect('/?error=network_error')
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        log_login_attempt(
            email='unknown',
            login_method=LoginHistory.METHOD_GOOGLE_OAUTH,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=f'Callback error: {str(e)[:200]}'
        )
        return redirect('/?error=internal_error')
# EE:END - Google OAuth Authentication


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

    # Sanitize and validate input - only title is required
    sanitized, errors = sanitize_request_data(data, {
        'title': {'type': 'title', 'max_length': 255, 'required': True},
        'context': {'type': 'text', 'max_length': 50000, 'required': False},
        'decision': {'type': 'text', 'max_length': 50000, 'required': False},
        'consequences': {'type': 'text', 'max_length': 50000, 'required': False},
        'status': {'type': 'string', 'max_length': 50},
        'change_reason': {'type': 'text', 'max_length': 500},
        'owner_email': {'type': 'email', 'required': False},
    })

    # Handle owner_id separately (not part of sanitization)
    owner_id = data.get('owner_id')
    owner_email = sanitized.get('owner_email')

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

    # Validate owner_id if provided (must be a user in the same tenant)
    validated_owner_id = None
    if owner_id:
        owner_user = User.query.filter_by(id=owner_id, sso_domain=domain).first()
        if owner_user:
            validated_owner_id = owner_id
        # If owner_id is invalid, we silently ignore it (don't fail the request)

    decision = ArchitectureDecision(
        title=sanitized['title'],
        context=sanitized.get('context', ''),
        decision=sanitized.get('decision', ''),
        status=status,
        consequences=sanitized.get('consequences', ''),
        decision_number=next_number,
        domain=domain,  # SECURITY: Always use authenticated user's domain
        created_by_id=g.current_user.id,
        updated_by_id=g.current_user.id,
        owner_id=validated_owner_id,
        owner_email=owner_email
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

    # Notify decision owner if assigned (and it's not the creator)
    if decision.owner_id or decision.owner_email:
        try:
            from notifications import notify_decision_owner
            owner_email = decision.owner_email
            owner_name = None
            if decision.owner_id and decision.owner:
                owner_email = decision.owner.email
                owner_name = decision.owner.name
                # Don't notify if owner is the creator
                if decision.owner_id == decision.created_by_id:
                    owner_email = None
            if owner_email:
                base_url = request.host_url.rstrip('/')
                notify_decision_owner(email_config, decision, owner_email, owner_name, base_url)
        except Exception as e:
            logger.warning(f"Failed to notify decision owner: {e}")

    # Send Slack notification if configured (Enterprise only)
    if is_slack_enabled():
        try:
            from ee.backend.slack.slack_service import notify_decision_created
            notify_decision_created(decision)
        except Exception as e:
            logger.warning(f"Failed to send Slack notification for new decision: {e}")

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
        'owner_email': {'type': 'email', 'required': False},
    })

    # Handle owner_id separately
    owner_id = data.get('owner_id')
    owner_email = sanitized.get('owner_email')

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

    # Check for owner changes and track if owner is being assigned/changed
    owner_changed = False
    old_owner_id = decision.owner_id
    old_owner_email = decision.owner_email
    if 'owner_id' in data and owner_id != decision.owner_id:
        has_changes = True
        owner_changed = True
    if 'owner_email' in data and owner_email != decision.owner_email:
        has_changes = True
        owner_changed = True

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

    # Handle owner updates
    if 'owner_id' in data:
        if owner_id:
            # Validate owner_id is in the same tenant
            owner_user = User.query.filter_by(id=owner_id, sso_domain=g.current_user.sso_domain).first()
            if owner_user:
                decision.owner_id = owner_id
        else:
            decision.owner_id = None
    if 'owner_email' in data:
        decision.owner_email = owner_email

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

    # Notify new decision owner if owner was changed
    if owner_changed and (decision.owner_id or decision.owner_email):
        # Only notify if it's a new owner (not same as old)
        new_owner_email = decision.owner_email
        new_owner_name = None
        should_notify = True

        if decision.owner_id and decision.owner:
            new_owner_email = decision.owner.email
            new_owner_name = decision.owner.name
            # Don't notify if owner is the person making the update
            if decision.owner_id == g.current_user.id:
                should_notify = False
            # Don't notify if owner hasn't actually changed (same user)
            if decision.owner_id == old_owner_id:
                should_notify = False
        elif decision.owner_email and decision.owner_email == old_owner_email:
            should_notify = False

        if should_notify and new_owner_email:
            try:
                from notifications import notify_decision_owner
                base_url = request.host_url.rstrip('/')
                notify_decision_owner(email_config, decision, new_owner_email, new_owner_name, base_url)
            except Exception as e:
                logger.warning(f"Failed to notify decision owner on update: {e}")

    # Send Slack notification if status changed (Enterprise only)
    if status_changed and is_slack_enabled():
        try:
            from ee.backend.slack.slack_service import notify_decision_status_changed
            notify_decision_status_changed(decision)
        except Exception as e:
            logger.warning(f"Failed to send Slack notification for status change: {e}")

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
        if datetime.now(timezone.utc).replace(tzinfo=None) < membership.deletion_rate_limited_at + timedelta(hours=1):
            return jsonify({
                'error': 'Deletion rate limited',
                'message': 'Your deletion privileges have been temporarily suspended due to multiple rapid deletions. Please contact an administrator.',
                'rate_limited_until': (membership.deletion_rate_limited_at + timedelta(hours=1)).isoformat()
            }), 429

    # Rate limiting check: >3 deletions in 5 minutes triggers lockout
    RATE_LIMIT_COUNT = 3
    RATE_LIMIT_WINDOW_MINUTES = 5

    now = datetime.now(timezone.utc)
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
    deletion_time = datetime.now(timezone.utc)
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
        master = db.session.get(MasterAccount, session.get('master_id'))
        if master:
            return jsonify(master.to_dict())

    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    user = db.session.get(User, session.get('user_id'))
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
    from_name = sanitize_name(data.get('from_name', 'Decision Records'), max_length=100)

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
        'Decision Records - Test Email',
        '<h1>Test Email</h1><p>This is a test email from Decision Records.</p>',
        'Test Email\n\nThis is a test email from Decision Records.'
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
    # Uses global keyvault_client (EE) or KeyVaultClientStub (CE)
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
    # Uses global keyvault_client (EE) or KeyVaultClientStub (CE)
    data = request.get_json()

    # Username and password are not required since they come from Key Vault
    required_fields = ['smtp_server', 'smtp_port', 'from_email']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Sanitize inputs to prevent XSS attacks
    smtp_server = sanitize_title(data['smtp_server'], max_length=255)
    from_email_sanitized = sanitize_email(data['from_email'])
    from_name = sanitize_name(data.get('from_name', 'Decision Records'), max_length=100)

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
        'Decision Records - Test Email',
        '<h1>Test Email</h1><p>This is a test email from Decision Records system config.</p>',
        'Test Email\n\nThis is a test email from Decision Records system config.'
    )

    if success:
        return jsonify({'message': f'Test email sent to {test_email}'})
    else:
        return jsonify({'error': 'Failed to send test email'}), 500


# ==================== API Routes - System Settings (Super Admin) ====================

@app.route('/api/admin/settings/session', methods=['GET'])
@master_required
@track_endpoint('api_admin_settings_session_get')
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
@track_endpoint('api_admin_settings_session_save')
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
@track_endpoint('api_admin_settings_licensing_get')
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
@track_endpoint('api_admin_settings_licensing_save')
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


@app.route('/api/admin/settings/support', methods=['GET'])
@master_required
@track_endpoint('api_admin_settings_support_get')
def api_get_support_settings():
    """Get support/contact email settings (super admin only)."""
    return jsonify({
        'support_email': SystemConfig.get(
            SystemConfig.KEY_SUPPORT_EMAIL,
            default=SystemConfig.DEFAULT_SUPPORT_EMAIL
        ),
        'defaults': {
            'support_email': SystemConfig.DEFAULT_SUPPORT_EMAIL
        }
    })


@app.route('/api/admin/settings/support', methods=['POST', 'PUT'])
@master_required
@track_endpoint('api_admin_settings_support_save')
def api_save_support_settings():
    """Update support/contact email settings (super admin only)."""
    from security import sanitize_email

    data = request.get_json() or {}

    support_email = data.get('support_email', '').strip()

    if support_email:
        # Validate email format
        sanitized = sanitize_email(support_email)
        if not sanitized:
            return jsonify({'error': 'Invalid email address format'}), 400

        SystemConfig.set(
            SystemConfig.KEY_SUPPORT_EMAIL,
            sanitized,
            description='Email address for contact form submissions'
        )

    return jsonify({
        'message': 'Support settings updated successfully',
        'support_email': SystemConfig.get(
            SystemConfig.KEY_SUPPORT_EMAIL,
            default=SystemConfig.DEFAULT_SUPPORT_EMAIL
        )
    })


@app.route('/api/admin/settings/ai', methods=['GET'])
@master_required
@track_endpoint('api_admin_settings_ai_get')
def api_get_ai_system_settings():
    """Get system-level AI settings (super admin only)."""
    return jsonify({
        'ai_features_enabled': SystemConfig.get(SystemConfig.KEY_AI_FEATURES_ENABLED, 'false').lower() == 'true',
        'external_api_enabled': SystemConfig.get(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'false').lower() == 'true',
        'mcp_server_enabled': SystemConfig.get(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'false').lower() == 'true',
        'slack_bot_enabled': SystemConfig.get(SystemConfig.KEY_AI_SLACK_BOT_ENABLED, 'false').lower() == 'true'
    })


@app.route('/api/admin/settings/ai', methods=['POST', 'PUT'])
@master_required
@track_endpoint('api_admin_settings_ai_save')
def api_save_ai_system_settings():
    """Update system-level AI settings (super admin only)."""
    data = request.get_json() or {}

    if 'ai_features_enabled' in data:
        SystemConfig.set(
            SystemConfig.KEY_AI_FEATURES_ENABLED,
            'true' if data['ai_features_enabled'] else 'false',
            description='Master switch for all AI features'
        )

    if 'external_api_enabled' in data:
        SystemConfig.set(
            SystemConfig.KEY_AI_EXTERNAL_API_ENABLED,
            'true' if data['external_api_enabled'] else 'false',
            description='Enable external API access (MCP, REST API)'
        )

    if 'mcp_server_enabled' in data:
        SystemConfig.set(
            SystemConfig.KEY_AI_MCP_SERVER_ENABLED,
            'true' if data['mcp_server_enabled'] else 'false',
            description='Enable MCP server for dev tools'
        )

    if 'slack_bot_enabled' in data:
        SystemConfig.set(
            SystemConfig.KEY_AI_SLACK_BOT_ENABLED,
            'true' if data['slack_bot_enabled'] else 'false',
            description='Enable Slack AI bot features'
        )

    return jsonify({
        'message': 'AI settings updated successfully',
        'ai_features_enabled': SystemConfig.get(SystemConfig.KEY_AI_FEATURES_ENABLED, 'false').lower() == 'true',
        'external_api_enabled': SystemConfig.get(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'false').lower() == 'true',
        'mcp_server_enabled': SystemConfig.get(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'false').lower() == 'true',
        'slack_bot_enabled': SystemConfig.get(SystemConfig.KEY_AI_SLACK_BOT_ENABLED, 'false').lower() == 'true'
    })


# EE:START - Analytics Settings (PostHog)
@app.route('/api/admin/settings/analytics', methods=['GET'])
@master_required
@track_endpoint('api_admin_settings_analytics_get')
def api_get_analytics_settings():
    """Get analytics settings (super admin only).

    Returns:
        - enabled: Whether analytics is enabled
        - host: PostHog host URL
        - person_profiling: Whether person profiles are enabled
        - exception_capture: Whether exception capture is enabled
        - api_key_configured: Whether an API key is set
        - event_mappings: Current endpoint -> event name mappings
        - default_mappings: Default mappings for reference
        - categories: Static category definitions (deprecated)
        - discovered_endpoints: Dynamically discovered API endpoints
    """
    from ee.backend.analytics.analytics import get_config_for_api
    from flask import current_app
    return jsonify(get_config_for_api(app=current_app))


@app.route('/api/admin/settings/analytics', methods=['POST', 'PUT'])
@master_required
@track_endpoint('api_admin_settings_analytics_save')
def api_save_analytics_settings():
    """Update analytics settings (super admin only)."""
    import json as json_lib
    from ee.backend.analytics.analytics import invalidate_cache, DEFAULT_EVENT_MAPPINGS

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
            # Allow any endpoint name - supports custom mappings for new endpoints
            valid_mappings = {}
            for key, value in mappings.items():
                # Sanitize key and value
                sanitized_key = sanitize_text_field(key, max_length=100)
                sanitized_value = sanitize_text_field(value, max_length=100) if value else None
                if sanitized_key and sanitized_value:
                    valid_mappings[sanitized_key] = sanitized_value
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
@track_endpoint('api_admin_settings_analytics_api_key')
def api_save_analytics_api_key():
    """Save analytics API key (super admin only).

    For self-hosted deployments that don't use Key Vault.
    In cloud deployments, the key should be in Key Vault.
    """
    from ee.backend.analytics.analytics import invalidate_cache

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
@track_endpoint('api_admin_settings_analytics_test')
def api_test_analytics():
    """Send a test event to PostHog (super admin only)."""
    from ee.backend.analytics.analytics import _get_analytics_config, invalidate_cache

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
                'timestamp': datetime.now(timezone.utc).isoformat()
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
@track_endpoint('api_admin_settings_analytics_reset')
def api_reset_analytics_mappings():
    """Reset event mappings to defaults (super admin only)."""
    from ee.backend.analytics.analytics import invalidate_cache, DEFAULT_EVENT_MAPPINGS
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


@app.route('/api/admin/settings/analytics/mapping', methods=['PUT'])
@master_required
@track_endpoint('api_admin_settings_analytics_mapping_update')
def api_update_analytics_mapping():
    """Add or update a single event mapping (super admin only).

    Request body:
        {
            "endpoint": "api_my_endpoint",
            "event_name": "my_action_completed"
        }

    Set event_name to null/empty to remove a mapping.
    """
    import json as json_lib
    from ee.backend.analytics.analytics import invalidate_cache, DEFAULT_EVENT_MAPPINGS

    data = request.get_json() or {}

    endpoint = sanitize_text_field(data.get('endpoint', ''), max_length=100)
    event_name = sanitize_text_field(data.get('event_name', ''), max_length=100)

    if not endpoint:
        return jsonify({'error': 'Endpoint name is required'}), 400

    # Get current mappings
    current_mappings_json = SystemConfig.get(SystemConfig.KEY_ANALYTICS_EVENT_MAPPINGS)
    if current_mappings_json:
        try:
            current_mappings = json.loads(current_mappings_json)
        except json.JSONDecodeError:
            current_mappings = DEFAULT_EVENT_MAPPINGS.copy()
    else:
        current_mappings = DEFAULT_EVENT_MAPPINGS.copy()

    # Update or remove the mapping
    if event_name:
        current_mappings[endpoint] = event_name
        action = 'updated'
    else:
        current_mappings.pop(endpoint, None)
        action = 'removed'

    # Save updated mappings
    SystemConfig.set(
        SystemConfig.KEY_ANALYTICS_EVENT_MAPPINGS,
        json_lib.dumps(current_mappings),
        description='Custom event name mappings for PostHog'
    )

    # Invalidate cache
    invalidate_cache()

    return jsonify({
        'message': f'Event mapping {action} successfully',
        'endpoint': endpoint,
        'event_name': event_name if event_name else None
    })


@app.route('/api/admin/settings/analytics/mapping/<endpoint_name>', methods=['DELETE'])
@master_required
@track_endpoint('api_admin_settings_analytics_mapping_delete')
def api_delete_analytics_mapping(endpoint_name):
    """Remove an event mapping (super admin only)."""
    import json as json_lib
    from ee.backend.analytics.analytics import invalidate_cache, DEFAULT_EVENT_MAPPINGS

    endpoint = sanitize_text_field(endpoint_name, max_length=100)

    # Get current mappings
    current_mappings_json = SystemConfig.get(SystemConfig.KEY_ANALYTICS_EVENT_MAPPINGS)
    if current_mappings_json:
        try:
            current_mappings = json.loads(current_mappings_json)
        except json.JSONDecodeError:
            current_mappings = DEFAULT_EVENT_MAPPINGS.copy()
    else:
        current_mappings = DEFAULT_EVENT_MAPPINGS.copy()

    # Remove the mapping
    if endpoint in current_mappings:
        del current_mappings[endpoint]

        # Save updated mappings
        SystemConfig.set(
            SystemConfig.KEY_ANALYTICS_EVENT_MAPPINGS,
            json_lib.dumps(current_mappings),
            description='Custom event name mappings for PostHog'
        )

        # Invalidate cache
        invalidate_cache()

        return jsonify({
            'message': 'Event mapping removed successfully',
            'endpoint': endpoint
        })
    else:
        return jsonify({'error': 'Mapping not found'}), 404
# EE:END - Analytics Settings (PostHog)


# EE:START - Cloudflare Settings
# ==================== API Routes - Cloudflare Security Settings (Enterprise Edition) ====================

@app.route('/api/admin/settings/cloudflare', methods=['GET'])
@master_required
@track_endpoint('api_admin_settings_cloudflare_get')
def api_get_cloudflare_settings():
    """Get Cloudflare security settings (super admin only)."""
    from cloudflare_security import get_cloudflare_config_for_api
    return jsonify(get_cloudflare_config_for_api())


@app.route('/api/admin/settings/cloudflare', methods=['POST', 'PUT'])
@master_required
@track_endpoint('api_admin_settings_cloudflare_save')
def api_save_cloudflare_settings():
    """Update Cloudflare security settings (super admin only)."""
    from cloudflare_security import invalidate_cloudflare_cache

    data = request.get_json() or {}

    # Update origin check setting
    if 'origin_check_enabled' in data:
        SystemConfig.set(
            SystemConfig.KEY_CLOUDFLARE_ORIGIN_CHECK_ENABLED,
            'true' if data['origin_check_enabled'] else 'false',
            description='Enable Cloudflare origin IP validation'
        )

    # Update access settings
    if 'access_enabled' in data:
        SystemConfig.set(
            SystemConfig.KEY_CLOUDFLARE_ACCESS_ENABLED,
            'true' if data['access_enabled'] else 'false',
            description='Enable Cloudflare Access JWT validation for protected paths'
        )

    if 'access_team_domain' in data:
        team_domain = sanitize_string(data['access_team_domain'], max_length=200)
        # Validate domain format (should end with .cloudflareaccess.com or similar)
        if team_domain and not team_domain.endswith('.cloudflareaccess.com'):
            # Allow custom domains but log a warning
            logger.warning(f"Non-standard Cloudflare Access domain: {team_domain}")
        SystemConfig.set(
            SystemConfig.KEY_CLOUDFLARE_ACCESS_TEAM_DOMAIN,
            team_domain,
            description='Cloudflare Access team domain (e.g., myteam.cloudflareaccess.com)'
        )

    if 'protected_paths' in data:
        # Validate and normalize paths
        if isinstance(data['protected_paths'], list):
            paths = [sanitize_string(p.strip(), max_length=100) for p in data['protected_paths'] if p.strip()]
            paths_str = ','.join(paths)
        else:
            paths_str = sanitize_string(data['protected_paths'], max_length=500)
        SystemConfig.set(
            SystemConfig.KEY_CLOUDFLARE_ACCESS_PROTECTED_PATHS,
            paths_str,
            description='Comma-separated paths protected by Cloudflare Access'
        )

    # Invalidate cache to apply changes immediately
    invalidate_cloudflare_cache()

    return jsonify({'message': 'Cloudflare settings updated'})


@app.route('/api/admin/settings/cloudflare/access-aud', methods=['PUT'])
@master_required
@track_endpoint('api_admin_settings_cloudflare_aud')
def api_save_cloudflare_access_aud():
    """Save Cloudflare Access AUD (super admin only).

    The AUD (audience) tag is sensitive and stored separately.
    """
    from cloudflare_security import invalidate_cloudflare_cache

    data = request.get_json() or {}
    aud = data.get('access_aud', '').strip()

    if not aud:
        return jsonify({'error': 'Access AUD is required'}), 400

    # Validate AUD format (should be a hex string, typically 64 chars)
    if len(aud) < 32 or not all(c in '0123456789abcdef' for c in aud.lower()):
        return jsonify({'error': 'Invalid AUD format. Expected a 32+ character hex string'}), 400

    SystemConfig.set(
        SystemConfig.KEY_CLOUDFLARE_ACCESS_AUD,
        aud,
        description='Cloudflare Access application audience tag (AUD)'
    )

    # Invalidate cache
    invalidate_cloudflare_cache()

    return jsonify({'message': 'Cloudflare Access AUD saved'})


@app.route('/api/admin/settings/cloudflare/test', methods=['POST'])
@master_required
@track_endpoint('api_admin_settings_cloudflare_test')
def api_test_cloudflare_settings():
    """Test Cloudflare Access configuration (super admin only).

    Tests:
    1. Can fetch public keys from the team domain
    2. Configuration is complete
    """
    from cloudflare_security import get_cloudflare_access_keys, _get_cloudflare_config

    config = _get_cloudflare_config()

    # Check if Access is configured
    if not config['access_enabled']:
        return jsonify({
            'success': False,
            'message': 'Cloudflare Access is not enabled',
            'details': {
                'access_enabled': False
            }
        })

    if not config['access_team_domain']:
        return jsonify({
            'success': False,
            'message': 'Team domain is not configured',
            'details': {
                'team_domain_configured': False
            }
        })

    if not config['access_aud']:
        return jsonify({
            'success': False,
            'message': 'Access AUD is not configured',
            'details': {
                'access_aud_configured': False
            }
        })

    # Try to fetch public keys
    try:
        keys = get_cloudflare_access_keys(config['access_team_domain'])
        key_count = len(keys.get('keys', []))

        return jsonify({
            'success': True,
            'message': f'Successfully fetched {key_count} public key(s) from Cloudflare Access',
            'details': {
                'team_domain': config['access_team_domain'],
                'key_count': key_count,
                'protected_paths': config['protected_paths']
            }
        })
    except Exception as e:
        logger.error(f"Failed to test Cloudflare Access: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to fetch keys: {str(e)}',
            'details': {
                'team_domain': config['access_team_domain'],
                'error': str(e)
            }
        }), 400
# EE:END - Cloudflare Settings


# EE:START - Log Forwarding Settings
# ==================== API Routes - Log Forwarding Settings (Enterprise Edition) ====================

@app.route('/api/admin/settings/log-forwarding', methods=['GET'])
@master_required
@track_endpoint('api_admin_settings_logforwarding_get')
def api_get_log_forwarding_settings():
    """Get log forwarding settings (super admin only)."""
    from ee.backend.analytics.log_forwarding import get_config_for_api
    return jsonify(get_config_for_api())


@app.route('/api/admin/settings/log-forwarding', methods=['POST', 'PUT'])
@master_required
@track_endpoint('api_admin_settings_logforwarding_save')
def api_save_log_forwarding_settings():
    """Update log forwarding settings (super admin only)."""
    from ee.backend.analytics.log_forwarding import validate_settings, invalidate_cache, reconfigure

    data = request.get_json() or {}

    # Validate settings
    is_valid, errors = validate_settings(data)
    if not is_valid:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    # Update enabled setting
    if 'enabled' in data:
        SystemConfig.set(
            SystemConfig.KEY_LOG_FORWARDING_ENABLED,
            'true' if data['enabled'] else 'false',
            description='Enable OpenTelemetry log forwarding'
        )

    # Update endpoint URL
    if 'endpoint_url' in data:
        endpoint_url = sanitize_string(data['endpoint_url'], max_length=500)
        SystemConfig.set(
            SystemConfig.KEY_LOG_FORWARDING_ENDPOINT_URL,
            endpoint_url,
            description='OTLP endpoint URL'
        )

    # Update auth type
    if 'auth_type' in data:
        auth_type = sanitize_string(data['auth_type'], max_length=20)
        SystemConfig.set(
            SystemConfig.KEY_LOG_FORWARDING_AUTH_TYPE,
            auth_type,
            description='Authentication type (api_key, bearer, header, none)'
        )

    # Update auth header name
    if 'auth_header_name' in data:
        auth_header_name = sanitize_string(data['auth_header_name'], max_length=100)
        SystemConfig.set(
            SystemConfig.KEY_LOG_FORWARDING_AUTH_HEADER_NAME,
            auth_header_name,
            description='Custom auth header name'
        )

    # Update log level
    if 'log_level' in data:
        log_level = sanitize_string(data['log_level'], max_length=10)
        SystemConfig.set(
            SystemConfig.KEY_LOG_FORWARDING_LOG_LEVEL,
            log_level.upper(),
            description='Minimum log level to forward'
        )

    # Update service name
    if 'service_name' in data:
        service_name = sanitize_string(data['service_name'], max_length=100)
        SystemConfig.set(
            SystemConfig.KEY_LOG_FORWARDING_SERVICE_NAME,
            service_name,
            description='Service identifier in logs'
        )

    # Update environment
    if 'environment' in data:
        environment = sanitize_string(data['environment'], max_length=50)
        SystemConfig.set(
            SystemConfig.KEY_LOG_FORWARDING_ENVIRONMENT,
            environment,
            description='Environment tag in logs'
        )

    # Update custom headers
    if 'custom_headers' in data:
        custom_headers = data['custom_headers']
        # Validate JSON if string
        if isinstance(custom_headers, str):
            try:
                import json
                json.loads(custom_headers)
            except json.JSONDecodeError:
                return jsonify({'error': 'Custom headers must be valid JSON'}), 400
        else:
            import json
            custom_headers = json.dumps(custom_headers)
        SystemConfig.set(
            SystemConfig.KEY_LOG_FORWARDING_CUSTOM_HEADERS,
            custom_headers,
            description='Additional HTTP headers (JSON)'
        )

    # Invalidate cache and reconfigure
    reconfigure(app)

    return jsonify({'message': 'Log forwarding settings updated'})


@app.route('/api/admin/settings/log-forwarding/api-key', methods=['PUT'])
@master_required
@track_endpoint('api_admin_settings_logforwarding_api_key')
def api_save_log_forwarding_api_key():
    """Save log forwarding API key (super admin only).

    For cloud deployments, API keys should be stored in Key Vault.
    This endpoint stores in SystemConfig as fallback for self-hosted.
    """
    from ee.backend.analytics.log_forwarding import invalidate_cache

    data = request.get_json() or {}
    api_key = data.get('api_key', '').strip()

    if not api_key:
        return jsonify({'error': 'API key is required'}), 400

    # Store in SystemConfig (for self-hosted deployments)
    # In cloud deployments, prefer Key Vault via Azure portal
    SystemConfig.set(
        SystemConfig.KEY_LOG_FORWARDING_API_KEY,
        api_key,
        description='OTLP API key/token (prefer Key Vault for cloud deployments)'
    )

    invalidate_cache()

    return jsonify({'message': 'Log forwarding API key saved'})


@app.route('/api/admin/settings/log-forwarding/test', methods=['POST'])
@master_required
@track_endpoint('api_admin_settings_logforwarding_test')
def api_test_log_forwarding():
    """Test log forwarding connection (super admin only)."""
    from ee.backend.analytics.log_forwarding import test_connection

    success, message = test_connection()

    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400
# EE:END - Log Forwarding Settings


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
        'rp_name': 'Decision Records',
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

    # Check if tenant can process access requests (has full admins or stewards who can approve)
    # This is INDEPENDENT of require_approval setting:
    # - require_approval: tenant setting - whether new users must be approved (admin's choice)
    # - can_process_access_requests: capability - whether the tenant has admins who CAN approve
    #
    # Edge case: If require_approval=true but can_process_access_requests=false (only provisional admin),
    # the backend will auto-approve users since no one can approve them. The frontend should
    # show "Join" instead of "Request Access" UI in this case.
    can_process_access_requests = False
    if has_users:
        tenant = Tenant.query.filter_by(domain=domain).first()
        if tenant:
            approving_admin_count = TenantMembership.query.filter(
                TenantMembership.tenant_id == tenant.id,
                TenantMembership.global_role.in_([GlobalRole.ADMIN, GlobalRole.STEWARD])
            ).count()
            can_process_access_requests = approving_admin_count > 0

    # Effective approval requirement: respects tenant setting, but if no one can approve, it's false
    require_approval_setting = auth_config.require_approval if auth_config else True
    effective_require_approval = require_approval_setting and can_process_access_requests

    return jsonify({
        'domain': domain,
        'has_users': has_users,
        'user_count': user_count,
        'auth_method': auth_config.auth_method if auth_config else 'webauthn',
        'allow_registration': auth_config.allow_registration if auth_config else True,
        'require_approval': require_approval_setting,  # Tenant's configured setting
        'effective_require_approval': effective_require_approval,  # Actual behavior (accounts for capability)
        'can_process_access_requests': can_process_access_requests,  # Whether tenant has approvers
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
    verify_url = f"{base_url}/api/auth/verify-email/{token}"

    if purpose == 'signup':
        subject = 'Verify your email - Decision Records'
        html_body = f"""
        <h1>Welcome to Decision Records</h1>
        <p>Please verify your email address by clicking the button below:</p>
        <p><a href="{verify_url}" style="background-color: #3f51b5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">Verify Email</a></p>
        <p>Or copy and paste this link into your browser:</p>
        <p>{verify_url}</p>
        <p>This link will expire in 24 hours.</p>
        <p>If you didn't request this, you can safely ignore this email.</p>
        """
        text_body = f"Welcome to Decision Records\n\nVerify your email by visiting: {verify_url}\n\nThis link expires in 24 hours."
    elif purpose == 'access_request':
        subject = 'Verify your email to request access - Decision Records'
        html_body = f"""
        <h1>Request Access to Decision Records</h1>
        <p>Please verify your email address to submit your access request:</p>
        <p><a href="{verify_url}" style="background-color: #3f51b5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">Verify and Submit Request</a></p>
        <p>Or copy and paste this link into your browser:</p>
        <p>{verify_url}</p>
        <p>This link will expire in 24 hours.</p>
        <p>If you didn't request this, you can safely ignore this email.</p>
        """
        text_body = f"Request Access\n\nVerify your email by visiting: {verify_url}\n\nThis link expires in 24 hours."
    else:
        subject = 'Verify your email - Decision Records'
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
    # Support both legacy 'name' field and new first_name/last_name fields
    first_name = sanitize_name(data.get('first_name', ''), max_length=100)
    last_name = sanitize_name(data.get('last_name', ''), max_length=100)
    legacy_name = sanitize_name(data.get('name', ''), max_length=255)

    # Derive name from first_name/last_name or use legacy name field
    if first_name or last_name:
        name = f"{first_name} {last_name}".strip()
    else:
        name = legacy_name

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

        # Check if tenant has any full admins who can approve requests
        # If only provisional admins exist, auto-approve new users since no one can approve them
        if require_approval:
            tenant = Tenant.query.filter_by(domain=domain).first()
            if tenant:
                full_admin_count = TenantMembership.query.filter(
                    TenantMembership.tenant_id == tenant.id,
                    TenantMembership.global_role.in_([GlobalRole.ADMIN, GlobalRole.STEWARD])
                ).count()
                if full_admin_count == 0:
                    # No full admins or stewards - provisional admin only tenant
                    # Auto-approve since no one can approve access requests
                    require_approval = False
                    logger.info(f"Auto-approving signup for {domain} - tenant has only provisional admin")

        if require_approval:
            purpose = 'access_request'
        else:
            purpose = 'signup'

    # Rate limiting: Check for recent verification emails
    recent_verification = EmailVerification.query.filter(
        EmailVerification.email == email,
        EmailVerification.created_at > datetime.now(timezone.utc) - timedelta(minutes=2)
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
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

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
    if pending.created_at > datetime.now(timezone.utc) - timedelta(minutes=2):
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
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

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


@app.route('/api/auth/request-setup-link', methods=['POST'])
@track_endpoint('api_auth_request_setup_link')
def api_request_setup_link():
    """Request a new setup link for users who haven't set up their credentials yet.

    This endpoint allows users to request a new setup link if their previous one
    expired or they didn't receive it. This is for users who have verified their
    email but haven't completed credential setup.
    """
    data = request.get_json() or {}
    email = data.get('email', '').lower().strip()

    if not email or '@' not in email:
        return jsonify({'error': 'Valid email address is required'}), 400

    # Generic success message (always return this to prevent email enumeration)
    success_message = 'If your account exists and needs setup, a link has been sent to your email.'

    # Find user by email
    user = User.query.filter_by(email=email).first()

    if not user:
        # Don't reveal that no user exists
        logger.info(f"Setup link requested for non-existent email: {email}")
        return jsonify({'message': success_message})

    # Check if user already has credentials
    has_passkey = len(user.webauthn_credentials) > 0 if user.webauthn_credentials else False
    has_password = user.has_password()

    if has_passkey or has_password:
        # User already has credentials - don't send setup link
        logger.info(f"Setup link requested for user with existing credentials: {email}")
        return jsonify({'message': success_message})

    # Rate limiting: Check for recent setup tokens (5 minutes)
    recent_token = SetupToken.query.filter(
        SetupToken.user_id == user.id,
        SetupToken.created_at > datetime.now(timezone.utc) - timedelta(minutes=5)
    ).first()

    if recent_token:
        logger.info(f"Rate limited setup link request for: {email}")
        return jsonify({'message': success_message})

    # Get email config for sending
    email_config = EmailConfig.query.filter_by(domain=user.sso_domain, enabled=True).first()
    if not email_config:
        email_config = EmailConfig.query.filter_by(enabled=True).first()

    if not email_config:
        logger.warning(f"No email config available to send setup link for: {email}")
        return jsonify({'message': success_message})

    # Generate new setup token
    setup_token = SetupToken.create_for_user(user)
    setup_token_str = setup_token._token_string
    setup_url = f"{request.host_url.rstrip('/')}/{user.sso_domain}/setup?token={setup_token_str}"

    # Send setup email
    from notifications import send_setup_token_email
    success = send_setup_token_email(
        email_config=email_config,
        user_name=user.name or user.email.split('@')[0],
        user_email=user.email,
        setup_url=setup_url,
        expires_in_hours=SetupToken.TOKEN_VALIDITY_HOURS
    )

    if success:
        logger.info(f"Setup link sent to: {email}")
    else:
        logger.error(f"Failed to send setup link to: {email}")

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
    # Support both legacy 'name' field and new first_name/last_name fields
    first_name = sanitize_name(data.get('first_name', ''), max_length=100)
    last_name = sanitize_name(data.get('last_name', ''), max_length=100)
    legacy_name = sanitize_name(data.get('name', ''), max_length=255)

    # Derive name from first_name/last_name or use legacy name field
    if first_name or last_name:
        name = f"{first_name} {last_name}".strip()
    else:
        name = legacy_name
        # Parse first_name and last_name from legacy name
        if name:
            parts = name.strip().split(None, 1)
            first_name = parts[0] if parts else ''
            last_name = parts[1] if len(parts) > 1 else ''

    password = data.get('password', '').strip() if data.get('password') else None
    auth_preference = data.get('auth_preference', 'passkey')  # 'passkey' or 'password'

    if not email or not first_name:
        return jsonify({'error': 'Email and first name are required'}), 400

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
            reviewed_at=datetime.now(timezone.utc)
        )
        db.session.add(domain_approval)
        app.logger.info(f"Auto-approved corporate domain: {domain}")

    # Domain is approved (either previously or just now)

    # Create user account directly (first user becomes admin)
    user = User(
        email=email,
        sso_domain=domain,
        auth_type='webauthn' if auth_preference == 'passkey' else 'local',
        is_admin=True,  # First user becomes admin
        email_verified=True  # Mark as verified since verification is disabled
    )
    # Set name using helper method for first_name/last_name handling
    user.set_name(first_name=first_name, last_name=last_name)
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
            rp_name='Decision Records'
        )
        db.session.add(auth_config)

    db.session.commit()

    # Determine redirect and auth handling based on auth preference
    if auth_preference == 'passkey':
        # SECURITY: For passkey signups, use a database-backed setup token
        # This prevents account hijacking if user doesn't complete passkey setup
        # The token only allows access to credential setup endpoints
        from models import SetupToken

        # Create a proper database-backed setup token
        setup_token = SetupToken.create_for_user(user)
        setup_token_str = setup_token._token_string

        # Do NOT set user_id - user is NOT fully logged in yet
        redirect_url = f'/{domain}/setup?token={setup_token_str}'
        setup_passkey = True

        app.logger.info(f"Created setup token for user {email} - credential setup required")
    else:
        # Password auth - user already has credentials, log them in fully
        session['user_id'] = user.id
        set_session_expiry(is_admin=False)  # 8 hours default for regular users
        user.last_login = datetime.now(timezone.utc)
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
    verification.verified_at = datetime.now(timezone.utc)

    # Process based on purpose
    if verification.purpose == 'signup':
        # Create user account (if doesn't exist)
        user = User.query.filter_by(email=verification.email).first()
        is_new_user = user is None
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
            db.session.flush()  # Get user ID before creating membership

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
                        rp_name='Decision Records'
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
                        reviewed_at=datetime.now(timezone.utc)
                    )
                    db.session.add(domain_approval)
                    app.logger.info(f"Auto-approved corporate domain via email verification: {verification.domain}")

            # Create Tenant if it doesn't exist (v1.5 governance)
            tenant = Tenant.query.filter_by(domain=verification.domain).first()
            if not tenant:
                tenant = Tenant(
                    domain=verification.domain,
                    name=verification.domain,  # Default name is domain
                    status='active',
                    maturity_state=MaturityState.BOOTSTRAP
                )
                db.session.add(tenant)
                db.session.flush()
                app.logger.info(f"Created tenant for domain: {verification.domain}")

            # Create TenantMembership for the user
            membership = TenantMembership.query.filter_by(
                user_id=user.id,
                tenant_id=tenant.id
            ).first()
            if not membership:
                role = GlobalRole.PROVISIONAL_ADMIN if is_first_user else GlobalRole.USER
                membership = TenantMembership(
                    user_id=user.id,
                    tenant_id=tenant.id,
                    global_role=role
                )
                db.session.add(membership)
                app.logger.info(f"Created TenantMembership for {verification.email} with role {role.value}")
        else:
            user.email_verified = True
            if verification.name:
                user.name = verification.name

        db.session.commit()

        # Generate SetupToken for user to set up credentials
        setup_token = SetupToken.create_for_user(user)
        setup_token_str = setup_token._token_string
        setup_url = f'/{verification.domain}/setup?token={setup_token_str}'

        app.logger.info(f"Email verified for {verification.email}, redirecting to setup page")

        if request.method == 'POST':
            return jsonify({
                'message': 'Email verified successfully',
                'email': verification.email,
                'domain': verification.domain,
                'purpose': 'signup',
                'redirect': setup_url,
                'setup_token': setup_token_str
            })
        return redirect(setup_url)

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
    # Support both legacy 'name' field and new first_name/last_name fields
    first_name = sanitize_name(data.get('first_name', ''), max_length=100)
    last_name = sanitize_name(data.get('last_name', ''), max_length=100)
    legacy_name = sanitize_name(data.get('name', ''), max_length=255)

    # Derive name from first_name/last_name or use legacy name field
    if first_name or last_name:
        name = f"{first_name} {last_name}".strip()
    else:
        name = legacy_name
        # Parse first_name and last_name from legacy name
        if name:
            parts = name.strip().split(None, 1)
            first_name = parts[0] if parts else ''
            last_name = parts[1] if len(parts) > 1 else ''

    reason = sanitize_text_field(data.get('reason', ''), max_length=1000)
    domain = data.get('domain', '').lower().strip()

    if not email or not first_name:
        return jsonify({'error': 'Email and first name are required'}), 400

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

    # Check if tenant has any full admins who can approve requests
    # If only provisional admins exist, auto-approve new users since no one can approve them
    if require_approval:
        tenant = Tenant.query.filter_by(domain=domain).first()
        if tenant:
            full_admin_count = TenantMembership.query.filter(
                TenantMembership.tenant_id == tenant.id,
                TenantMembership.global_role.in_([GlobalRole.ADMIN, GlobalRole.STEWARD])
            ).count()
            if full_admin_count == 0:
                # No full admins or stewards - provisional admin only tenant
                # Auto-approve since no one can approve access requests
                require_approval = False
                logger.info(f"Auto-approving access request for {domain} - tenant has only provisional admin")

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
            sso_domain=domain,
            auth_type='webauthn',
            is_admin=False
        )
        # Set name using helper method for first_name/last_name handling
        new_user.set_name(first_name=first_name, last_name=last_name)
        db.session.add(new_user)
        db.session.flush()  # Get the user ID before creating token

        # Generate setup token for the new user
        setup_token = SetupToken.create_for_user(new_user)
        setup_token_str = setup_token._token_string
        setup_url = f"{request.host_url.rstrip('/')}/{domain}/setup?token={setup_token_str}"

        db.session.commit()

        # Send setup email to user (if email is configured)
        email_config = EmailConfig.query.filter_by(domain='system', enabled=True).first()
        email_sent = False
        if email_config:
            try:
                send_account_setup_email(
                    email_config,
                    name,
                    email,
                    setup_url,
                    SetupToken.TOKEN_VALIDITY_HOURS,
                    tenant_name=domain
                )
                email_sent = True
                app.logger.info(f"Auto-approved user {email} for tenant {domain}, setup email sent")
            except Exception as e:
                app.logger.warning(f"Failed to send setup email to {email}: {e}")
        else:
            app.logger.warning(f"Auto-approved user {email} for tenant {domain}, but no email config")

        # Build response based on whether email was sent
        response_data = {
            'auto_approved': True,
            'email': email,
            'domain': domain
        }

        if email_sent:
            response_data['message'] = 'Your account has been created! Check your email for a link to set up your login credentials.'
        else:
            # Email not configured/sent - provide setup URL directly for Community Edition
            # This allows users to complete setup without requiring email
            response_data['message'] = 'Your account has been created! Click the button below to set up your login credentials.'
            response_data['setup_url'] = setup_url  # Include setup URL when email fails

        return jsonify(response_data)

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
        SetupToken.created_at > datetime.now(timezone.utc) - timedelta(minutes=2)
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
        setup_token.used_at = datetime.now(timezone.utc)
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
    session['setup_expires'] = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
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

    setup_token.used_at = datetime.now(timezone.utc)
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
    setup_token.used_at = datetime.now(timezone.utc)

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
        access_request.processed_at = datetime.now(timezone.utc)
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
        sso_domain=access_request.domain,
        auth_type='webauthn',
        is_admin=False
    )
    # Parse name from access request into first_name/last_name
    new_user.set_name(full_name=access_request.name)
    db.session.add(new_user)
    db.session.flush()  # Get the user ID before creating token

    # Update request status
    access_request.status = 'approved'
    access_request.processed_by_id = g.current_user.id if not is_master_account() else None
    access_request.processed_at = datetime.now(timezone.utc)

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
    access_request.processed_at = datetime.now(timezone.utc)

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
    role_request.reviewed_at = datetime.now(timezone.utc)
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
    role_request.reviewed_at = datetime.now(timezone.utc)
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
    role_request.reviewed_at = datetime.now(timezone.utc)
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
    target_user = db.session.get(User, role_request.user_id)

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
    role_request.reviewed_at = datetime.now(timezone.utc)
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
        admin_user = db.session.get(User, membership.user_id)
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
    # Capture request metadata for login history
    ip_address = request.headers.get('CF-Connecting-IP', request.remote_addr)
    user_agent = request.headers.get('User-Agent')

    data = request.get_json() or {}

    credential = data.get('credential')

    if not credential:
        return jsonify({'error': 'Credential is required'}), 400

    user, error = verify_authentication(credential)

    if error:
        # Try to extract email from session for logging
        email = session.get('webauthn_email', 'unknown')
        log_login_attempt(
            email=email,
            login_method=LoginHistory.METHOD_WEBAUTHN,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=error[:255] if error else 'WebAuthn verification failed'
        )
        return jsonify({'error': error}), 400

    # Log successful WebAuthn login
    log_login_attempt(
        email=user.email,
        login_method=LoginHistory.METHOD_WEBAUTHN,
        success=True,
        user_id=user.id,
        tenant_domain=user.sso_domain,
        ip_address=ip_address,
        user_agent=user_agent
    )

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
            'rp_name': 'Decision Records',
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
    if auth_method not in ['sso', 'webauthn', 'slack_oidc', 'local']:
        return jsonify({'error': 'auth_method must be "sso", "webauthn", "slack_oidc", or "local"'}), 400

    # If setting to SSO, check if SSO config exists for this domain
    if auth_method == 'sso':
        sso_config = SSOConfig.query.filter_by(domain=domain, enabled=True).first()
        if not sso_config:
            return jsonify({'error': 'Cannot set auth method to SSO without a valid SSO configuration'}), 400

    # If setting to slack_oidc, check if Slack feature is enabled
    if auth_method == 'slack_oidc' and not is_slack_enabled():
        return jsonify({'error': 'Slack integration is not enabled'}), 400

    config = AuthConfig.query.filter_by(domain=domain).first()

    if not config:
        config = AuthConfig(
            domain=domain,
            auth_method=auth_method,
            allow_registration=data.get('allow_registration', True),
            require_approval=data.get('require_approval', True),
            rp_name=data.get('rp_name', 'Decision Records'),
            allow_slack_oidc=data.get('allow_slack_oidc', True),
            allow_google_oauth=data.get('allow_google_oauth', True),
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
        if 'allow_slack_oidc' in data:
            config.allow_slack_oidc = bool(data['allow_slack_oidc'])
        if 'allow_google_oauth' in data:
            config.allow_google_oauth = bool(data['allow_google_oauth'])
        if 'allow_password' in data:
            config.allow_password = bool(data['allow_password'])
        if 'allow_passkey' in data:
            config.allow_passkey = bool(data['allow_passkey'])

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


@app.route('/api/system/license', methods=['GET'])
def api_get_license_status():
    """Get license acceptance status (public endpoint for setup flow)."""
    accepted = SystemConfig.get_bool(SystemConfig.KEY_LICENSE_ACCEPTED, default=False)
    accepted_by = SystemConfig.get(SystemConfig.KEY_LICENSE_ACCEPTED_BY, default='')
    accepted_at = SystemConfig.get(SystemConfig.KEY_LICENSE_ACCEPTED_AT, default='')

    return jsonify({
        'accepted': accepted,
        'accepted_by': accepted_by if accepted else None,
        'accepted_at': accepted_at if accepted else None,
        'license_type': 'BSL-1.1',
        'license_url': 'https://github.com/DecisionRecordsORG/DecisionRecords/blob/main/LICENSE'
    })


@app.route('/api/system/license/accept', methods=['POST'])
def api_accept_license():
    """Accept the BSL 1.1 license (for first-time setup, no auth required)."""
    # Check if license is already accepted
    if SystemConfig.get_bool(SystemConfig.KEY_LICENSE_ACCEPTED, default=False):
        return jsonify({'error': 'License has already been accepted'}), 400

    data = request.get_json() or {}

    # Require acknowledgement
    if not data.get('accept'):
        return jsonify({'error': 'You must accept the license terms'}), 400

    accepted_by = data.get('accepted_by', 'anonymous')
    now = datetime.now(timezone.utc).isoformat()

    # Store acceptance
    SystemConfig.set(SystemConfig.KEY_LICENSE_ACCEPTED, 'true', 'BSL 1.1 license acceptance')
    SystemConfig.set(SystemConfig.KEY_LICENSE_ACCEPTED_BY, accepted_by, 'Email of license acceptor')
    SystemConfig.set(SystemConfig.KEY_LICENSE_ACCEPTED_AT, now, 'License acceptance timestamp')

    logger.info(f"License accepted by: {accepted_by} at {now}")

    return jsonify({
        'message': 'License accepted successfully',
        'accepted': True,
        'accepted_by': accepted_by,
        'accepted_at': now
    })


@app.route('/api/system/status', methods=['GET'])
def api_get_system_status():
    """
    Get system installation status (public endpoint for setup flow).

    Used by Community Edition landing page to determine:
    - Fresh install: Show setup wizard
    - Configured: Show sign-in flow

    Returns:
        has_tenants: Whether any tenants exist in the system
        has_super_admin: Whether the super admin has been configured
        license_accepted: Whether the BSL 1.1 license has been accepted
        edition: Current edition (community/enterprise)
    """
    from feature_flags import EDITION, is_community

    # Count tenants (excluding any system/default tenants if they exist)
    tenant_count = Tenant.query.count()

    # Check if super admin is configured (MasterAccount exists with password)
    super_admin = MasterAccount.query.first()
    has_super_admin = super_admin is not None and super_admin.password_hash is not None

    # Check license acceptance
    license_accepted = SystemConfig.get_bool(SystemConfig.KEY_LICENSE_ACCEPTED, default=False)

    return jsonify({
        'has_tenants': tenant_count > 0,
        'tenant_count': tenant_count,
        'has_super_admin': has_super_admin,
        'license_accepted': license_accepted,
        'edition': EDITION,
        'is_community': is_community()
    })


@app.route('/api/tenants/public', methods=['GET'])
def api_list_tenants_public():
    """
    List public tenant information (no auth required).

    Used by Community Edition landing page to determine
    which tenant to redirect to for sign-in.

    Only returns basic public info: domain and name.
    Does not include sensitive information or stats.
    """
    # Filter out soft-deleted tenants (deleted_at is not null for deleted ones)
    tenants = Tenant.query.filter(Tenant.deleted_at.is_(None)).order_by(Tenant.created_at.asc()).all()

    return jsonify([{
        'id': t.id,
        'sso_domain': t.domain,  # Using domain as sso_domain for consistency with frontend
        'company_name': t.name or t.domain  # Using name as company_name for consistency
    } for t in tenants])


@app.route('/api/setup/initialize', methods=['POST'])
def api_setup_initialize():
    """
    Initialize a fresh Community Edition installation.

    This endpoint is only available when:
    - Running Community Edition (DECISION_RECORDS_EDITION=community)
    - No tenants exist yet (fresh install)
    - License has been accepted

    Creates:
    - First tenant with provided organization name
    - First admin user with provided email/password
    - Default space for the tenant
    - Auth configuration for the tenant

    Request body:
        organization_name: Name of the organization (becomes tenant name)
        domain: Domain for the tenant (e.g., "mycompany.com")
        admin_email: Email for the first admin user
        admin_password: Password for the first admin user
        admin_name: Optional full name for the admin user
    """
    from feature_flags import is_community

    # Only allow in Community Edition
    if not is_community():
        return jsonify({'error': 'Setup wizard is only available in Community Edition'}), 403

    # Only allow if no tenants exist (fresh install)
    tenant_count = Tenant.query.count()
    if tenant_count > 0:
        return jsonify({'error': 'Setup already completed. A tenant already exists.'}), 400

    # Check if license was accepted
    license_accepted = SystemConfig.get_bool(SystemConfig.KEY_LICENSE_ACCEPTED, default=False)
    if not license_accepted:
        return jsonify({'error': 'Please accept the license agreement first'}), 400

    data = request.get_json() or {}

    # Validate required fields
    organization_name = data.get('organization_name', '').strip()
    domain = data.get('domain', '').strip().lower()
    admin_email = data.get('admin_email', '').strip().lower()
    admin_password = data.get('admin_password', '')
    admin_name = data.get('admin_name', '').strip()

    if not organization_name:
        return jsonify({'error': 'Organization name is required'}), 400
    if not domain:
        return jsonify({'error': 'Domain is required'}), 400
    if not admin_email:
        return jsonify({'error': 'Admin email is required'}), 400
    if not admin_password:
        return jsonify({'error': 'Admin password is required'}), 400
    if len(admin_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    # Validate email format
    if '@' not in admin_email:
        return jsonify({'error': 'Invalid email address'}), 400

    # Clean up domain (remove protocol, paths, www)
    domain = domain.replace('https://', '').replace('http://', '')
    domain = domain.split('/')[0]
    if domain.startswith('www.'):
        domain = domain[4:]

    try:
        # Create the tenant
        tenant = Tenant(
            domain=domain,
            name=organization_name,
            status='active',
            maturity_state=MaturityState.BOOTSTRAP
        )
        db.session.add(tenant)
        db.session.flush()
        app.logger.info(f"Created tenant via setup wizard: {domain}")

        # Create default auth config for the tenant
        auth_config = AuthConfig(
            domain=domain,
            auth_method='local',
            allow_password=True,
            allow_passkey=True,
            allow_registration=True,
            require_approval=False  # Auto-approve new users for CE single-tenant
        )
        db.session.add(auth_config)

        # Create default space for the tenant
        default_space = Space(
            tenant_id=tenant.id,
            name='General',
            description='Default space for all architecture decisions',
            is_default=True
        )
        db.session.add(default_space)

        # Create the first admin user
        user = User(
            email=admin_email,
            sso_domain=domain,
            auth_type='local',  # Password-based auth
            is_admin=True,
            email_verified=True  # Skip verification for setup
        )
        user.set_password(admin_password)

        # Set name if provided
        if admin_name:
            user.set_name(full_name=admin_name)

        db.session.add(user)
        db.session.flush()

        # Create tenant membership for the admin
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            global_role=GlobalRole.ADMIN
        )
        db.session.add(membership)

        db.session.commit()

        app.logger.info(f"Setup wizard completed. Tenant: {domain}, Admin: {admin_email}")

        return jsonify({
            'message': 'Setup completed successfully',
            'tenant': {
                'domain': domain,
                'name': organization_name
            },
            'admin': {
                'email': admin_email
            },
            'next_step': f'/{domain}/login'
        })

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Setup wizard failed: {str(e)}")
        return jsonify({'error': 'Setup failed. Please try again.'}), 500


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


# ============================================================================
# Superadmin History Endpoints
# ============================================================================

@app.route('/api/superadmin/email-verifications/pending', methods=['GET'])
@master_required
def api_list_pending_verifications():
    """List all pending email verifications (super admin only).

    Returns email verification records where verified_at is NULL,
    representing users who started signup but never completed verification.
    """
    pending = EmailVerification.query.filter(
        EmailVerification.verified_at.is_(None)
    ).order_by(EmailVerification.created_at.desc()).all()

    # Add is_expired flag to each result
    result = []
    for v in pending:
        data = v.to_dict()
        data['is_expired'] = v.is_expired()
        result.append(data)

    return jsonify(result)


@app.route('/api/superadmin/login-history', methods=['GET'])
@master_required
def api_list_login_history():
    """List all login history records (super admin only).

    Query params:
    - limit: Number of records to return (default 50, max 500)
    - offset: Number of records to skip (default 0)
    - tenant_domain: Filter by tenant domain
    - success: Filter by success status ('true' or 'false')
    - method: Filter by login method
    """
    limit = min(int(request.args.get('limit', 50)), 500)
    offset = int(request.args.get('offset', 0))
    tenant_domain = request.args.get('tenant_domain')
    success = request.args.get('success')
    method = request.args.get('method')

    query = LoginHistory.query

    if tenant_domain:
        query = query.filter(LoginHistory.tenant_domain == tenant_domain)
    if success is not None and success != '':
        query = query.filter(LoginHistory.success == (success.lower() == 'true'))
    if method:
        query = query.filter(LoginHistory.login_method == method)

    total = query.count()
    items = query.order_by(LoginHistory.created_at.desc()).offset(offset).limit(limit).all()

    return jsonify({
        'total': total,
        'limit': limit,
        'offset': offset,
        'items': [item.to_dict() for item in items]
    })


@app.route('/api/superadmin/login-history/stats', methods=['GET'])
@master_required
def api_login_history_stats():
    """Get login history statistics (super admin only).

    Returns aggregate statistics about login attempts.
    """
    total = LoginHistory.query.count()
    successful = LoginHistory.query.filter_by(success=True).count()
    failed = LoginHistory.query.filter_by(success=False).count()

    # Count by method
    by_method = {}
    method_counts = db.session.query(
        LoginHistory.login_method,
        db.func.count(LoginHistory.id)
    ).group_by(LoginHistory.login_method).all()
    for method, count in method_counts:
        by_method[method] = count

    # Count by tenant (top 10)
    by_tenant = {}
    tenant_counts = db.session.query(
        LoginHistory.tenant_domain,
        db.func.count(LoginHistory.id)
    ).filter(
        LoginHistory.tenant_domain.isnot(None)
    ).group_by(LoginHistory.tenant_domain).order_by(
        db.func.count(LoginHistory.id).desc()
    ).limit(10).all()
    for domain, count in tenant_counts:
        by_tenant[domain] = count

    return jsonify({
        'total': total,
        'successful': successful,
        'failed': failed,
        'by_method': by_method,
        'by_tenant': by_tenant
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
                # Handle both naive and aware datetimes
                now = datetime.now(timezone.utc)
                created = tenant.created_at
                if created.tzinfo is None:
                    # Naive datetime - assume UTC
                    created = created.replace(tzinfo=timezone.utc)
                age_days = (now - created).days
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
        # Handle both naive and aware datetimes
        now = datetime.now(timezone.utc)
        created = tenant.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = (now - created).days
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
    deletion_time = datetime.now(timezone.utc)
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
    if tenant.deletion_expires_at and datetime.now(timezone.utc).replace(tzinfo=None) > tenant.deletion_expires_at:
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
        if data['auth_method'] not in ['local', 'sso', 'webauthn', 'slack_oidc']:
            return jsonify({'error': 'Invalid auth method'}), 400
        # If setting to slack_oidc, check if Slack feature is enabled
        if data['auth_method'] == 'slack_oidc' and not is_slack_enabled():
            return jsonify({'error': 'Slack integration is not enabled'}), 400
        auth_config.auth_method = data['auth_method']

    if 'allow_password' in data:
        auth_config.allow_password = bool(data['allow_password'])

    if 'allow_passkey' in data:
        auth_config.allow_passkey = bool(data['allow_passkey'])

    if 'allow_slack_oidc' in data:
        auth_config.allow_slack_oidc = bool(data['allow_slack_oidc'])

    if 'allow_google_oauth' in data:
        auth_config.allow_google_oauth = bool(data['allow_google_oauth'])

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

        # Security: Block path traversal attempts before any filesystem checks
        # This prevents information disclosure via os.path.isfile probing
        if path and ('..' in path or path.startswith('/')):
            return send_from_directory(FRONTEND_DIR, 'index.html')

        # Check for prerendered routes FIRST (SSR/prerender creates path/index.html)
        # This enables proper meta tags for social sharing on blog posts etc.
        if path:
            prerendered_path = os.path.join(FRONTEND_DIR, path, 'index.html')
            if os.path.isfile(prerendered_path):
                return send_from_directory(os.path.join(FRONTEND_DIR, path), 'index.html')

        # Try to serve static files (JS, CSS, images, etc.) - must be a file, not directory
        if path:
            static_path = os.path.join(FRONTEND_DIR, path)
            if os.path.isfile(static_path):
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
    # Support both legacy name and new first_name/last_name fields
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    legacy_name = data.get('name', '')
    if first_name or last_name:
        name = f"{first_name} {last_name}".strip()
    elif legacy_name:
        name = legacy_name
        parts = name.strip().split(None, 1)
        first_name = parts[0] if parts else email.split('@')[0] if email else 'Test'
        last_name = parts[1] if len(parts) > 1 else ''
    else:
        name = email.split('@')[0] if email else 'Test User'
        first_name = name
        last_name = ''
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
            sso_domain=domain,
            password_hash=generate_password_hash(password),
            auth_type='local'
        )
        user.set_name(first_name=first_name, last_name=last_name)
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
    domain = data.get('domain', email.split('@')[1] if email and '@' in email else 'test.com')

    # Support both legacy name and new first_name/last_name fields
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    legacy_name = data.get('name', '')

    if first_name or last_name:
        # New format: first_name and last_name provided
        pass  # Use them as-is
    elif legacy_name:
        # Legacy format: parse name into first_name/last_name
        parts = legacy_name.strip().split(None, 1)
        first_name = parts[0] if parts else (email.split('@')[0] if email else 'Test')
        last_name = parts[1] if len(parts) > 1 else ''
    else:
        # Default: use email prefix as first name
        first_name = email.split('@')[0] if email else 'Test'
        last_name = 'User'

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
            sso_domain=domain,
            password_hash=None,  # No password - incomplete user
            auth_type=None  # No auth type yet
        )
        user.set_name(first_name=first_name, last_name=last_name)
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
        token_expires = datetime.now(timezone.utc) + timedelta(hours=48)

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


# EE:START - Slack Integration Endpoints
# =============================================================================
# SLACK INTEGRATION ENDPOINTS (Enterprise Edition)
# =============================================================================

@app.route('/api/slack/install')
@require_slack
@login_required
@admin_required
@track_endpoint('api_slack_install')
def slack_install():
    """Start Slack OAuth installation flow."""
    from ee.backend.slack.slack_security import generate_oauth_state

    try:
        client_id = keyvault_client.get_slack_client_id()
        if not client_id:
            logger.error("Slack client ID not found in Key Vault")
            return jsonify({'error': 'Slack integration not configured. Please set up Slack credentials in Key Vault.'}), 500

        user = get_current_user()
        tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404

        # Generate state with tenant_id
        state = generate_oauth_state(tenant.id, user.id)

        # Slack OAuth scopes
        scopes = 'chat:write,commands,users:read,users:read.email,channels:read,groups:read'

        # Build redirect URI using OAuth base URL (supports Cloudflare Worker routing)
        base_url = get_oauth_base_url()
        redirect_uri = f"{base_url}/api/slack/oauth/callback"

        auth_url = (
            f"https://slack.com/oauth/v2/authorize"
            f"?client_id={client_id}"
            f"&scope={scopes}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )

        return redirect(auth_url)
    except Exception as e:
        logger.error(f"Slack install error: {str(e)}")
        return jsonify({'error': f'Failed to start Slack installation: {str(e)}'}), 500


@app.route('/api/slack/oauth/callback')
@require_slack
@track_endpoint('api_slack_oauth_callback')
def slack_oauth_callback():
    """Handle Slack OAuth callback.

    Supports two scenarios:
    1. Installation initiated from Decision Records settings (has state with tenant_id)
    2. Installation from Slack App Directory (no state, workspace stored as pending_claim)
    """
    from ee.backend.slack.slack_security import verify_oauth_state, encrypt_token
    from slack_sdk import WebClient

    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        logger.error(f"Slack OAuth error: {error}")
        return redirect('/settings?slack_error=' + error)

    if not code:
        return redirect('/settings?slack_error=missing_code')

    # Check for state - if present, this is an install from Decision Records
    # If not present, this is an install from Slack App Directory
    tenant_id = None
    user_id = None

    if state:
        state_data = verify_oauth_state(state)
        if not state_data:
            return redirect('/settings?slack_error=invalid_state')
        tenant_id = state_data.get('tenant_id')
        user_id = state_data.get('user_id')

    client_id = keyvault_client.get_slack_client_id()
    client_secret = keyvault_client.get_slack_client_secret()

    if not client_id or not client_secret:
        return redirect('/settings?slack_error=not_configured')

    try:
        # Exchange code for token
        client = WebClient()
        # Build redirect URI (must match the one used in authorization)
        base_url = get_oauth_base_url()
        redirect_uri = f"{base_url}/api/slack/oauth/callback"

        response = client.oauth_v2_access(
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri
        )

        if not response['ok']:
            logger.error(f"Slack OAuth failed: {response.get('error')}")
            return redirect('/settings?slack_error=oauth_failed')

        # Extract workspace info
        workspace_id = response['team']['id']
        workspace_name = response['team']['name']
        bot_token = response['access_token']

        # Extract granted scopes from OAuth response
        granted_scopes = response.get('scope', '').split(',') if response.get('scope') else []
        logger.info(f"Slack OAuth granted scopes: {granted_scopes}")

        # Get current app version for tracking
        from ee.backend.slack.slack_upgrade import CURRENT_APP_VERSION

        # Encrypt and store
        encrypted_token = encrypt_token(bot_token)

        # === Domain Validation ===
        # Verify the Slack workspace's primary email domain matches the tenant's domain
        # This prevents consultants/IT admins from accidentally claiming workspaces
        # for the wrong organization
        workspace_domain = None
        if tenant_id:
            tenant = db.session.get(Tenant, tenant_id)
            if tenant:
                try:
                    # Use the bot token to fetch workspace users and identify primary domain
                    auth_client = WebClient(token=bot_token)

                    # Get the workspace's domain from team info
                    team_info = auth_client.team_info()
                    if team_info['ok']:
                        # Slack team domain (e.g., 'acme' for acme.slack.com)
                        slack_team_domain = team_info.get('team', {}).get('domain', '')

                        # Also check email_domain if set (enterprise grid)
                        email_domain = team_info.get('team', {}).get('email_domain', '')

                        # Try to get primary domain from workspace users
                        # Fetch a sample of users to determine the dominant email domain
                        users_response = auth_client.users_list(limit=100)
                        if users_response['ok']:
                            domain_counts = {}
                            for member in users_response.get('members', []):
                                if member.get('deleted') or member.get('is_bot'):
                                    continue
                                profile = member.get('profile', {})
                                user_email = profile.get('email', '')
                                if user_email and '@' in user_email:
                                    user_domain = user_email.split('@')[1].lower()
                                    # Skip common public domains
                                    if user_domain not in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
                                        domain_counts[user_domain] = domain_counts.get(user_domain, 0) + 1

                            # Find the most common domain
                            if domain_counts:
                                workspace_domain = max(domain_counts, key=domain_counts.get)
                                logger.info(f"Detected workspace primary domain: {workspace_domain} (from {domain_counts[workspace_domain]} users)")

                        # Use email_domain as fallback if set
                        if not workspace_domain and email_domain:
                            workspace_domain = email_domain.lower()
                            logger.info(f"Using Slack email_domain: {workspace_domain}")

                except Exception as e:
                    logger.warning(f"Could not verify workspace domain: {e}")
                    # Continue without validation - will still work, just less secure

                # Validate domain match
                if workspace_domain:
                    tenant_domain = tenant.domain.lower()
                    if workspace_domain != tenant_domain:
                        logger.warning(
                            f"Domain mismatch: Slack workspace domain '{workspace_domain}' "
                            f"does not match tenant domain '{tenant_domain}'. "
                            f"Workspace: {workspace_name} ({workspace_id})"
                        )
                        # Return error with helpful message
                        error_msg = (
                            f"domain_mismatch&workspace_domain={workspace_domain}"
                            f"&tenant_domain={tenant_domain}"
                        )
                        return redirect(f'/settings?slack_error={error_msg}')

        # Check for existing workspace by workspace_id (Slack team_id)
        existing_by_workspace = SlackWorkspace.query.filter_by(workspace_id=workspace_id).first()

        if tenant_id:
            # Installation initiated from Decision Records settings
            # Check if this tenant already has a different workspace
            existing_by_tenant = SlackWorkspace.query.filter_by(tenant_id=tenant_id).first()

            if existing_by_workspace:
                # Workspace already exists
                if existing_by_workspace.tenant_id == tenant_id:
                    # Same tenant, just update (may be an upgrade with new scopes)
                    existing_by_workspace.workspace_name = workspace_name
                    existing_by_workspace.bot_token_encrypted = encrypted_token
                    existing_by_workspace.is_active = True
                    existing_by_workspace.installed_at = datetime.now(timezone.utc)
                    existing_by_workspace.status = SlackWorkspace.STATUS_ACTIVE
                    # Track scopes and version
                    existing_by_workspace.granted_scopes = ','.join(granted_scopes) if granted_scopes else None
                    existing_by_workspace.scopes_updated_at = datetime.now(timezone.utc)
                    existing_by_workspace.app_version = CURRENT_APP_VERSION
                elif existing_by_workspace.tenant_id is None or not existing_by_workspace.is_active:
                    # Unclaimed or disconnected workspace - claim it for this tenant
                    # Note: A disconnected workspace (is_active=False) can be reclaimed
                    old_tenant_id = existing_by_workspace.tenant_id
                    existing_by_workspace.tenant_id = tenant_id
                    existing_by_workspace.workspace_name = workspace_name
                    existing_by_workspace.bot_token_encrypted = encrypted_token
                    existing_by_workspace.is_active = True
                    existing_by_workspace.installed_at = datetime.now(timezone.utc)
                    existing_by_workspace.status = SlackWorkspace.STATUS_ACTIVE
                    existing_by_workspace.claimed_at = datetime.now(timezone.utc)
                    existing_by_workspace.claimed_by_id = user_id
                    # Track scopes and version
                    existing_by_workspace.granted_scopes = ','.join(granted_scopes) if granted_scopes else None
                    existing_by_workspace.scopes_updated_at = datetime.now(timezone.utc)
                    existing_by_workspace.app_version = CURRENT_APP_VERSION
                    if old_tenant_id:
                        logger.info(f"Re-claimed disconnected workspace {workspace_name} from tenant {old_tenant_id} for tenant {tenant_id}")
                    else:
                        logger.info(f"Claimed unclaimed workspace {workspace_name} for tenant {tenant_id}")
                else:
                    # Workspace belongs to another tenant AND is active
                    logger.warning(f"Workspace {workspace_id} already belongs to tenant {existing_by_workspace.tenant_id} and is active")
                    return redirect('/settings?slack_error=workspace_claimed_by_other')

            elif existing_by_tenant:
                # Tenant has a different workspace, update it
                existing_by_tenant.workspace_id = workspace_id
                existing_by_tenant.workspace_name = workspace_name
                existing_by_tenant.bot_token_encrypted = encrypted_token
                existing_by_tenant.is_active = True
                existing_by_tenant.installed_at = datetime.now(timezone.utc)
                existing_by_tenant.status = SlackWorkspace.STATUS_ACTIVE
                # Track scopes and version
                existing_by_tenant.granted_scopes = ','.join(granted_scopes) if granted_scopes else None
                existing_by_tenant.scopes_updated_at = datetime.now(timezone.utc)
                existing_by_tenant.app_version = CURRENT_APP_VERSION
            else:
                # New workspace for this tenant
                workspace = SlackWorkspace(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    workspace_name=workspace_name,
                    bot_token_encrypted=encrypted_token,
                    is_active=True,
                    status=SlackWorkspace.STATUS_ACTIVE,
                    claimed_at=datetime.now(timezone.utc),
                    claimed_by_id=user_id,
                    # Track scopes and version
                    granted_scopes=','.join(granted_scopes) if granted_scopes else None,
                    scopes_updated_at=datetime.now(timezone.utc),
                    app_version=CURRENT_APP_VERSION
                )
                db.session.add(workspace)

            db.session.commit()
            logger.info(f"Slack workspace {workspace_name} connected to tenant {tenant_id}")

            # Get tenant domain for redirect
            tenant = db.session.get(Tenant, tenant_id)
            if tenant:
                return redirect(f'/{tenant.domain}/admin?tab=slack&slack_success=true')
            return redirect('/settings?slack_success=true')

        else:
            # Installation from Slack App Directory (no tenant association)
            if existing_by_workspace:
                # Workspace already exists
                if existing_by_workspace.tenant_id:
                    # Already claimed by a tenant, just update the token and scopes
                    existing_by_workspace.workspace_name = workspace_name
                    existing_by_workspace.bot_token_encrypted = encrypted_token
                    existing_by_workspace.is_active = True
                    existing_by_workspace.installed_at = datetime.now(timezone.utc)
                    # Track scopes and version
                    existing_by_workspace.granted_scopes = ','.join(granted_scopes) if granted_scopes else None
                    existing_by_workspace.scopes_updated_at = datetime.now(timezone.utc)
                    existing_by_workspace.app_version = CURRENT_APP_VERSION
                    db.session.commit()
                    logger.info(f"Updated existing workspace {workspace_name} (already claimed by tenant {existing_by_workspace.tenant_id})")
                    # Redirect to a page showing the workspace is already connected
                    return redirect(f'/slack/installed?workspace={workspace_id}&already_claimed=true')
                else:
                    # Still unclaimed, update token and scopes
                    existing_by_workspace.workspace_name = workspace_name
                    existing_by_workspace.bot_token_encrypted = encrypted_token
                    existing_by_workspace.is_active = True
                    existing_by_workspace.installed_at = datetime.now(timezone.utc)
                    # Track scopes and version
                    existing_by_workspace.granted_scopes = ','.join(granted_scopes) if granted_scopes else None
                    existing_by_workspace.scopes_updated_at = datetime.now(timezone.utc)
                    existing_by_workspace.app_version = CURRENT_APP_VERSION
                    db.session.commit()
                    logger.info(f"Updated existing unclaimed workspace {workspace_name}")
                    return redirect(f'/slack/installed?workspace={workspace_id}')
            else:
                # New unclaimed workspace
                workspace = SlackWorkspace(
                    tenant_id=None,  # No tenant yet
                    workspace_id=workspace_id,
                    workspace_name=workspace_name,
                    bot_token_encrypted=encrypted_token,
                    is_active=True,
                    status=SlackWorkspace.STATUS_PENDING_CLAIM,
                    # Track scopes and version
                    granted_scopes=','.join(granted_scopes) if granted_scopes else None,
                    scopes_updated_at=datetime.now(timezone.utc),
                    app_version=CURRENT_APP_VERSION
                )
                db.session.add(workspace)
                db.session.commit()
                logger.info(f"Created unclaimed Slack workspace {workspace_name} ({workspace_id})")
                return redirect(f'/slack/installed?workspace={workspace_id}')

    except Exception as e:
        logger.error(f"Slack OAuth callback error: {str(e)}")
        db.session.rollback()
        return redirect('/settings?slack_error=callback_failed')


@app.route('/api/slack/webhook/commands', methods=['POST'])
@require_slack
@track_endpoint('api_slack_command')
def slack_commands():
    """Handle Slack slash commands."""
    from ee.backend.slack.slack_security import verify_slack_signature
    from ee.backend.slack.slack_service import SlackService

    # Verify request signature
    if not verify_slack_signature(request):
        return jsonify({'error': 'Invalid signature'}), 403

    # Parse form data (Slack sends form-encoded data)
    team_id = request.form.get('team_id')
    user_id = request.form.get('user_id')
    channel_id = request.form.get('channel_id')
    text = request.form.get('text', '').strip()
    trigger_id = request.form.get('trigger_id')
    response_url = request.form.get('response_url', '')

    # Find workspace
    workspace = SlackWorkspace.query.filter_by(workspace_id=team_id, is_active=True).first()
    if not workspace:
        return jsonify({
            'response_type': 'ephemeral',
            'text': 'This workspace is not connected to Decision Records. Please install the app from your Decision Records settings page.'
        })

    # Check if workspace has a tenant (is claimed)
    if not workspace.tenant_id:
        return jsonify({
            'response_type': 'ephemeral',
            'text': f'This Slack workspace needs to be claimed by a Decision Records organization.\n\nYour Workspace ID is: `{team_id}`\n\nShare this with your Decision Records admin to connect the workspace.'
        })

    # Update last activity
    workspace.last_activity_at = datetime.now(timezone.utc)
    db.session.commit()

    # Create service and handle command
    service = SlackService(workspace)
    response, _ = service.handle_command(text, user_id, trigger_id, response_url, channel_id)

    if response is None:
        return '', 200

    return jsonify(response)


@app.route('/api/slack/webhook/interactions', methods=['POST'])
@require_slack
@track_endpoint('api_slack_interaction')
def slack_interactions():
    """Handle Slack interactive components (modals, buttons)."""
    from ee.backend.slack.slack_security import verify_slack_signature
    from ee.backend.slack.slack_service import SlackService
    import json

    # Verify request signature
    if not verify_slack_signature(request):
        return jsonify({'error': 'Invalid signature'}), 403

    # Parse payload
    payload = json.loads(request.form.get('payload', '{}'))
    payload_type = payload.get('type')
    team_id = payload.get('team', {}).get('id')

    # Find workspace
    workspace = SlackWorkspace.query.filter_by(workspace_id=team_id, is_active=True).first()
    if not workspace:
        return '', 200

    # Update last activity
    workspace.last_activity_at = datetime.now(timezone.utc)
    db.session.commit()

    service = SlackService(workspace)

    result = None
    if payload_type == 'view_submission':
        result = service.handle_modal_submission(payload)
    elif payload_type == 'block_actions':
        result = service.handle_block_action(payload)
    elif payload_type == 'message_action':
        result = service.handle_message_action(payload)
    elif payload_type == 'shortcut':
        # Global shortcuts (type: global in manifest)
        result = service.handle_message_action(payload)

    # Slack expects a 200 response - return result if it's a dict, otherwise empty 200
    if result is not None:
        return jsonify(result), 200
    return '', 200


@app.route('/api/slack/webhook/events', methods=['POST'])
@require_slack
@track_endpoint('api_slack_events')
def slack_events():
    """Handle Slack Events API (app_home_opened, etc.)."""
    from ee.backend.slack.slack_security import verify_slack_signature
    from ee.backend.slack.slack_service import SlackService
    import json

    # Verify request signature
    if not verify_slack_signature(request):
        return jsonify({'error': 'Invalid signature'}), 403

    data = request.get_json()

    # Handle URL verification challenge (required when setting up Events API)
    if data.get('type') == 'url_verification':
        return jsonify({'challenge': data.get('challenge')}), 200

    # Handle actual events
    if data.get('type') == 'event_callback':
        event = data.get('event', {})
        team_id = data.get('team_id')

        # Find workspace
        workspace = SlackWorkspace.query.filter_by(workspace_id=team_id, is_active=True).first()
        if not workspace:
            logger.warning(f"Event from unknown workspace: {team_id}")
            return '', 200

        # Update last activity
        workspace.last_activity_at = datetime.now(timezone.utc)
        db.session.commit()

        service = SlackService(workspace)
        service.handle_event(event)

    return '', 200


@app.route('/api/slack/settings', methods=['GET'])
@require_slack
@login_required
@admin_required
@track_endpoint('api_slack_get_settings')
def slack_get_settings():
    """Get Slack integration settings."""
    from ee.backend.azure.keyvault_client import keyvault_client

    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    workspace = SlackWorkspace.query.filter_by(tenant_id=tenant.id, is_active=True).first()

    if not workspace:
        try:
            client_id = keyvault_client.get_slack_client_id()
        except Exception:
            client_id = None
        return jsonify({
            'installed': False,
            'install_url': '/api/slack/install' if client_id else None
        })

    return jsonify({
        'installed': True,
        'workspace_id': workspace.workspace_id,
        'workspace_name': workspace.workspace_name,
        'default_channel_id': workspace.default_channel_id,
        'default_channel_name': workspace.default_channel_name,
        'notifications_enabled': workspace.notifications_enabled,
        'notify_on_create': workspace.notify_on_create,
        'notify_on_status_change': workspace.notify_on_status_change,
        'installed_at': workspace.installed_at.isoformat() if workspace.installed_at else None,
        'last_activity_at': workspace.last_activity_at.isoformat() if workspace.last_activity_at else None
    })


@app.route('/api/slack/settings', methods=['PUT'])
@require_slack
@login_required
@admin_required
@track_endpoint('api_slack_update_settings')
def slack_update_settings():
    """Update Slack integration settings."""
    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    workspace = SlackWorkspace.query.filter_by(tenant_id=tenant.id, is_active=True).first()
    if not workspace:
        return jsonify({'error': 'Slack not connected'}), 404

    data = request.get_json()

    if 'default_channel_id' in data:
        workspace.default_channel_id = data['default_channel_id']
    if 'default_channel_name' in data:
        workspace.default_channel_name = data['default_channel_name']
    if 'notifications_enabled' in data:
        workspace.notifications_enabled = data['notifications_enabled']
    if 'notify_on_create' in data:
        workspace.notify_on_create = data['notify_on_create']
    if 'notify_on_status_change' in data:
        workspace.notify_on_status_change = data['notify_on_status_change']

    db.session.commit()

    return jsonify({
        'message': 'Settings updated',
        'settings': {
            'installed': True,
            'workspace_id': workspace.workspace_id,
            'workspace_name': workspace.workspace_name,
            'default_channel_id': workspace.default_channel_id,
            'default_channel_name': workspace.default_channel_name,
            'notifications_enabled': workspace.notifications_enabled,
            'notify_on_create': workspace.notify_on_create,
            'notify_on_status_change': workspace.notify_on_status_change,
            'installed_at': workspace.installed_at.isoformat() if workspace.installed_at else None,
            'last_activity_at': workspace.last_activity_at.isoformat() if workspace.last_activity_at else None
        }
    })


@app.route('/api/slack/disconnect', methods=['POST'])
@require_slack
@login_required
@admin_required
@track_endpoint('api_slack_disconnect')
def slack_disconnect():
    """Disconnect Slack workspace."""
    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    workspace = SlackWorkspace.query.filter_by(tenant_id=tenant.id).first()
    if not workspace:
        return jsonify({'error': 'Slack not connected'}), 404

    workspace.is_active = False
    workspace.bot_token_encrypted = ''
    db.session.commit()

    logger.info(f"Slack workspace disconnected from tenant {tenant.id}")

    return jsonify({'message': 'Slack disconnected successfully'})


@app.route('/api/superadmin/slack/reassign', methods=['POST'])
@require_slack
@login_required
@master_required
@track_endpoint('api_superadmin_slack_reassign')
def superadmin_slack_reassign():
    """Super-admin endpoint to reassign a Slack workspace to a different tenant.

    Used for:
    - Fixing incorrectly assigned workspaces
    - Development/testing when same workspace needs to be tested with different tenants

    Request body:
    {
        "workspace_id": "T12345678",
        "target_tenant_domain": "newcompany.com"
    }
    """
    data = request.get_json()
    workspace_id = data.get('workspace_id', '').strip()
    target_domain = data.get('target_tenant_domain', '').strip()

    if not workspace_id:
        return jsonify({'error': 'workspace_id is required'}), 400
    if not target_domain:
        return jsonify({'error': 'target_tenant_domain is required'}), 400

    # Find the workspace
    workspace = SlackWorkspace.query.filter_by(workspace_id=workspace_id).first()
    if not workspace:
        return jsonify({'error': f'Workspace {workspace_id} not found'}), 404

    # Find the target tenant
    target_tenant = Tenant.query.filter_by(domain=target_domain).first()
    if not target_tenant:
        return jsonify({'error': f'Tenant {target_domain} not found'}), 404

    # Get old tenant info for logging
    old_tenant_id = workspace.tenant_id
    old_tenant_domain = None
    if old_tenant_id:
        old_tenant = db.session.get(Tenant, old_tenant_id)
        old_tenant_domain = old_tenant.domain if old_tenant else 'Unknown'

    # Reassign the workspace
    workspace.tenant_id = target_tenant.id
    workspace.is_active = True
    workspace.status = SlackWorkspace.STATUS_ACTIVE
    workspace.claimed_at = datetime.now(timezone.utc)
    db.session.commit()

    logger.warning(
        f"SUPER-ADMIN: Reassigned Slack workspace {workspace_id} "
        f"from tenant '{old_tenant_domain}' ({old_tenant_id}) "
        f"to tenant '{target_domain}' ({target_tenant.id})"
    )

    return jsonify({
        'message': 'Workspace reassigned successfully',
        'workspace_id': workspace_id,
        'old_tenant': old_tenant_domain,
        'new_tenant': target_domain
    })


@app.route('/api/superadmin/slack/workspaces', methods=['GET'])
@require_slack
@login_required
@master_required
@track_endpoint('api_superadmin_slack_list')
def superadmin_slack_list_workspaces():
    """Super-admin endpoint to list all Slack workspaces and their tenant assignments."""
    workspaces = SlackWorkspace.query.all()

    result = []
    for ws in workspaces:
        tenant_domain = None
        if ws.tenant_id:
            tenant = db.session.get(Tenant, ws.tenant_id)
            tenant_domain = tenant.domain if tenant else 'Unknown'

        # Get claimed_by user info
        claimed_by_info = None
        if ws.claimed_by:
            claimed_by_info = {
                'id': ws.claimed_by.id,
                'name': ws.claimed_by.name,
                'email': ws.claimed_by.email
            }

        # Get linked users count and details
        linked_users = []
        total_linked = 0
        for mapping in ws.user_mappings.filter(SlackUserMapping.user_id.isnot(None)).all():
            total_linked += 1
            if mapping.user:
                linked_users.append({
                    'id': mapping.user.id,
                    'name': mapping.user.name,
                    'email': mapping.user.email,
                    'slack_user_id': mapping.slack_user_id,
                    'link_method': mapping.link_method,
                    'linked_at': mapping.linked_at.isoformat() if mapping.linked_at else None
                })

        result.append({
            'id': ws.id,
            'workspace_id': ws.workspace_id,
            'workspace_name': ws.workspace_name,
            'tenant_id': ws.tenant_id,
            'tenant_domain': tenant_domain,
            'is_active': ws.is_active,
            'status': ws.status,
            'installed_at': ws.installed_at.isoformat() if ws.installed_at else None,
            'claimed_at': ws.claimed_at.isoformat() if ws.claimed_at else None,
            'claimed_by': claimed_by_info,
            'linked_users_count': total_linked,
            'linked_users': linked_users
        })

    return jsonify(result)


@app.route('/api/superadmin/slack/workspaces/<int:workspace_id>', methods=['DELETE'])
@require_slack
@login_required
@master_required
@track_endpoint('api_superadmin_slack_delete')
def superadmin_slack_delete_workspace(workspace_id):
    """Super-admin endpoint to remove a Slack workspace assignment (soft delete)."""
    workspace = db.session.get(SlackWorkspace, workspace_id)
    if not workspace:
        return jsonify({'error': 'Workspace not found'}), 404

    old_tenant_id = workspace.tenant_id
    old_tenant_domain = None
    if old_tenant_id:
        tenant = db.session.get(Tenant, old_tenant_id)
        old_tenant_domain = tenant.domain if tenant else 'Unknown'

    # Soft delete - mark as disconnected and remove tenant assignment
    workspace.is_active = False
    workspace.status = SlackWorkspace.STATUS_DISCONNECTED
    workspace.tenant_id = None

    db.session.commit()

    logger.info(f"Super-admin removed Slack workspace {workspace.workspace_name} ({workspace.workspace_id}) from tenant {old_tenant_domain}")

    return jsonify({
        'message': f'Slack workspace {workspace.workspace_name} has been disconnected',
        'workspace_id': workspace.workspace_id,
        'previous_tenant': old_tenant_domain
    })


@app.route('/api/slack/claim', methods=['POST'])
@require_slack
@login_required
@admin_required
@track_endpoint('api_slack_claim')
def slack_claim_workspace():
    """Claim an unclaimed Slack workspace by workspace_id.

    Used when IT admin installed from Slack App Directory and DR admin needs to claim it.
    """
    data = request.get_json()
    workspace_id = data.get('workspace_id', '').strip()

    if not workspace_id:
        return jsonify({'error': 'Workspace ID is required'}), 400

    # Validate workspace_id format (Slack team IDs start with T)
    if not workspace_id.startswith('T') or len(workspace_id) < 9:
        return jsonify({'error': 'Invalid workspace ID format. Slack workspace IDs start with T.'}), 400

    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Check if tenant already has a Slack workspace
    existing_tenant_workspace = SlackWorkspace.query.filter_by(tenant_id=tenant.id).first()
    if existing_tenant_workspace and existing_tenant_workspace.is_active:
        return jsonify({
            'error': 'Your organization already has a Slack workspace connected. Disconnect it first to claim a different workspace.',
            'current_workspace': existing_tenant_workspace.workspace_name
        }), 400

    # Find the workspace to claim
    workspace = SlackWorkspace.query.filter_by(workspace_id=workspace_id).first()

    if not workspace:
        return jsonify({
            'error': 'Workspace not found. Please ensure the Slack app has been installed in your workspace.'
        }), 404

    if workspace.tenant_id and workspace.tenant_id != tenant.id:
        return jsonify({
            'error': 'This workspace has already been claimed by another organization.'
        }), 409

    if workspace.tenant_id == tenant.id:
        return jsonify({
            'message': 'This workspace is already connected to your organization.',
            'workspace': workspace.to_dict()
        }), 200

    # Claim the workspace
    workspace.tenant_id = tenant.id
    workspace.status = SlackWorkspace.STATUS_ACTIVE
    workspace.claimed_at = datetime.now(timezone.utc)
    workspace.claimed_by_id = user.id
    workspace.is_active = True

    # If tenant had an old inactive workspace, remove it
    if existing_tenant_workspace and not existing_tenant_workspace.is_active:
        db.session.delete(existing_tenant_workspace)

    db.session.commit()

    logger.info(f"Workspace {workspace.workspace_name} ({workspace_id}) claimed by tenant {tenant.id} (user {user.id})")

    return jsonify({
        'message': f'Successfully claimed workspace "{workspace.workspace_name}"',
        'workspace': workspace.to_dict()
    })


@app.route('/api/slack/workspace/<workspace_id>', methods=['GET'])
@require_slack
@track_endpoint('api_slack_workspace_info')
def slack_workspace_info(workspace_id):
    """Get public info about a Slack workspace.

    Used by the /slack/installed landing page to show workspace status.
    Only returns limited info for security (no tokens, no tenant details).
    """
    workspace = SlackWorkspace.query.filter_by(workspace_id=workspace_id).first()

    if not workspace:
        return jsonify({'error': 'Workspace not found'}), 404

    return jsonify({
        'workspace_id': workspace.workspace_id,
        'workspace_name': workspace.workspace_name,
        'is_claimed': workspace.tenant_id is not None,
        'status': workspace.status,
        'installed_at': workspace.installed_at.isoformat() if workspace.installed_at else None
    })


@app.route('/api/slack/test', methods=['POST'])
@require_slack
@login_required
@admin_required
@track_endpoint('api_slack_test')
def slack_test():
    """Send a test notification to Slack."""
    from ee.backend.slack.slack_service import SlackService

    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    workspace = SlackWorkspace.query.filter_by(tenant_id=tenant.id, is_active=True).first()
    if not workspace:
        return jsonify({'error': 'Slack not connected'}), 404

    if not workspace.default_channel_id:
        return jsonify({'error': 'No notification channel configured'}), 400

    try:
        service = SlackService(workspace)
        service.send_test_notification()
        return jsonify({'message': 'Test notification sent'})
    except Exception as e:
        logger.error(f"Slack test notification failed: {str(e)}")
        return jsonify({'error': 'Failed to send test notification'}), 500


@app.route('/api/slack/channels', methods=['GET'])
@require_slack
@login_required
@admin_required
@track_endpoint('api_slack_channels')
def slack_channels():
    """Get list of Slack channels for channel selection."""
    from ee.backend.slack.slack_service import SlackService

    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    workspace = SlackWorkspace.query.filter_by(tenant_id=tenant.id, is_active=True).first()
    if not workspace:
        return jsonify({'error': 'Slack not connected'}), 404

    try:
        service = SlackService(workspace)
        channels = service.get_channels()
        return jsonify({'channels': channels})
    except Exception as e:
        logger.error(f"Failed to get Slack channels: {str(e)}")
        return jsonify({'error': 'Failed to get channels'}), 500


@app.route('/api/slack/link/initiate', methods=['GET'])
@require_slack
@track_endpoint('api_slack_link_initiate')
def slack_link_initiate():
    """Initiate user linking from Slack to ADR.

    Redirects to the dedicated Slack link account page.
    """
    token = request.args.get('token')
    if not token:
        return redirect('/slack/link?error=missing_token')

    # Redirect to the dedicated link account page with the token
    return redirect(f'/slack/link?token={token}')


@app.route('/api/slack/link/validate', methods=['POST'])
@require_slack
@track_endpoint('api_slack_link_validate')
def slack_link_validate():
    """Validate a Slack link token and return info for the link page."""
    from ee.backend.slack.slack_security import verify_link_token

    data = request.get_json() or {}
    token = data.get('token')

    if not token:
        return jsonify({'valid': False, 'error': 'No token provided'}), 400

    link_data = verify_link_token(token)
    if not link_data:
        return jsonify({'valid': False, 'error': 'Invalid or expired link token'}), 400

    workspace_id = link_data.get('workspace_id')
    slack_user_id = link_data.get('slack_user_id')
    slack_email = link_data.get('slack_email')

    # Get workspace info
    workspace = SlackWorkspace.query.filter_by(workspace_id=workspace_id, is_active=True).first()
    if not workspace:
        return jsonify({'valid': False, 'error': 'Workspace not found'}), 404

    # Check if user is already logged in
    user = get_current_user()
    is_logged_in = user is not None

    response = {
        'valid': True,
        'workspace_name': workspace.workspace_name or 'Slack Workspace',
        'workspace_id': workspace_id,
        'slack_user_id': slack_user_id,
        'slack_email': slack_email,
        'is_logged_in': is_logged_in
    }

    if is_logged_in:
        response['user_email'] = user.email
        response['user_name'] = user.name or user.email
        response['tenant_domain'] = user.sso_domain

    return jsonify(response)


@app.route('/api/slack/link/complete', methods=['POST'])
@require_slack
@track_endpoint('api_slack_link_complete')
def slack_link_complete():
    """Complete user linking after login.

    Accepts token in request body (for new flow) or from session (legacy).
    """
    from ee.backend.slack.slack_security import verify_link_token

    data = request.get_json() or {}
    token = data.get('token')

    # Try to get link data from token first (new flow)
    link_data = None
    if token:
        link_data = verify_link_token(token)

    # Fall back to session (legacy flow)
    if not link_data:
        link_data = session.pop('slack_link_data', None)

    if not link_data:
        return jsonify({'error': 'No valid link token or session data'}), 400

    workspace_id = link_data.get('workspace_id')
    slack_user_id = link_data.get('slack_user_id')

    workspace = SlackWorkspace.query.filter_by(workspace_id=workspace_id, is_active=True).first()
    if not workspace:
        return jsonify({'error': 'Workspace not found'}), 404

    user = get_current_user()
    if not user:
        return jsonify({'error': 'You must be logged in to link your account'}), 401

    # Create or update mapping
    mapping = SlackUserMapping.query.filter_by(
        slack_workspace_id=workspace.id,
        slack_user_id=slack_user_id
    ).first()

    if mapping:
        mapping.user_id = user.id
        mapping.link_method = 'browser_auth'
        mapping.linked_at = datetime.now(timezone.utc)
    else:
        mapping = SlackUserMapping(
            slack_workspace_id=workspace.id,
            slack_user_id=slack_user_id,
            user_id=user.id,
            link_method='browser_auth',
            linked_at=datetime.now(timezone.utc)
        )
        db.session.add(mapping)

    db.session.commit()

    logger.info(f"User {user.id} linked Slack account {slack_user_id} in workspace {workspace_id}")

    return jsonify({'message': 'Account linked successfully'})
# EE:END - Slack Integration Endpoints


# EE:START - AI/LLM Integration
# ==================== API Routes - AI/LLM Integration (Enterprise Edition) ====================

# Import AI services (Enterprise only)
if is_enterprise():
    from ee.backend.ai import AIConfig, AIApiKeyService, AIInteractionLogger
else:
    # Community Edition stubs
    class AIConfig:
        @staticmethod
        def get_system_ai_config():
            return {'enabled': False, 'edition': 'community'}
        @staticmethod
        def get_system_ai_enabled():
            return False
        @staticmethod
        def get_system_mcp_server_enabled():
            return False

    class AIApiKeyService:
        pass

    class AIInteractionLogger:
        pass


# --- Super Admin AI Configuration ---

@app.route('/api/admin/ai/config', methods=['GET'])
@master_required
@require_enterprise
def api_get_ai_system_config():
    """Get system-level AI configuration (super admin only)."""
    return jsonify(AIConfig.get_system_ai_config())


@app.route('/api/admin/ai/config', methods=['POST', 'PUT'])
@master_required
def api_update_ai_system_config():
    """Update system-level AI configuration (super admin only)."""
    data = request.get_json() or {}

    # Define valid config keys
    valid_keys = {
        'ai_features_enabled': SystemConfig.KEY_AI_FEATURES_ENABLED,
        'ai_slack_bot_enabled': SystemConfig.KEY_AI_SLACK_BOT_ENABLED,
        'ai_mcp_server_enabled': SystemConfig.KEY_AI_MCP_SERVER_ENABLED,
        'ai_external_api_enabled': SystemConfig.KEY_AI_EXTERNAL_API_ENABLED,
        'ai_assisted_creation_enabled': SystemConfig.KEY_AI_ASSISTED_CREATION_ENABLED,
        'llm_provider': SystemConfig.KEY_AI_LLM_PROVIDER,
        'llm_model': SystemConfig.KEY_AI_LLM_MODEL,
        'llm_endpoint': SystemConfig.KEY_AI_LLM_ENDPOINT,
        'llm_api_key_secret': SystemConfig.KEY_AI_LLM_API_KEY_SECRET,
    }

    for key, config_key in valid_keys.items():
        if key in data:
            value = data[key]
            # Convert booleans to string
            if isinstance(value, bool):
                value = 'true' if value else 'false'
            # Validate LLM provider
            if key == 'llm_provider':
                try:
                    LLMProvider(value)
                except ValueError:
                    return jsonify({'error': f'Invalid LLM provider: {value}'}), 400
            AIConfig.set_system_config(config_key, str(value))

    return jsonify({
        'message': 'AI configuration updated',
        **AIConfig.get_system_ai_config()
    })


@app.route('/api/admin/ai/stats', methods=['GET'])
@master_required
def api_get_ai_system_stats():
    """Get system-wide AI usage statistics (super admin only)."""
    # Get stats across all tenants
    from sqlalchemy import func

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date = None
    end_date = None

    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str)
        except ValueError:
            return jsonify({'error': 'Invalid start_date format'}), 400

    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str)
        except ValueError:
            return jsonify({'error': 'Invalid end_date format'}), 400

    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()

    logs = AIInteractionLog.query.filter(
        AIInteractionLog.created_at >= start_date,
        AIInteractionLog.created_at <= end_date
    ).all()

    # Aggregate stats
    by_tenant = {}
    by_channel = {}
    by_action = {}
    total_tokens = 0

    for log in logs:
        by_tenant[log.tenant_id] = by_tenant.get(log.tenant_id, 0) + 1
        by_channel[log.channel] = by_channel.get(log.channel, 0) + 1
        by_action[log.action] = by_action.get(log.action, 0) + 1
        if log.tokens_input:
            total_tokens += log.tokens_input
        if log.tokens_output:
            total_tokens += log.tokens_output

    return jsonify({
        'period_start': start_date.isoformat(),
        'period_end': end_date.isoformat(),
        'total_interactions': len(logs),
        'tenants_using_ai': len(by_tenant),
        'by_channel': by_channel,
        'by_action': by_action,
        'total_tokens': total_tokens,
    })


# --- Tenant Admin AI Configuration ---

@app.route('/api/tenant/ai/config', methods=['GET'])
@login_required
def api_get_tenant_ai_config():
    """Get AI configuration for current tenant (admin only)."""
    user = get_current_user()
    tenant = get_current_tenant()

    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    membership = get_current_membership()
    if not membership or membership.global_role not in [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN]:
        return jsonify({'error': 'Permission denied. Admin or Steward role required.'}), 403

    # Get both system and tenant config
    system_config = AIConfig.get_system_ai_config()
    tenant_config = AIConfig.get_tenant_ai_config(tenant)

    # Return flat structure for frontend compatibility
    return jsonify({
        # System-level settings (read-only for tenant admins)
        'system_ai_enabled': system_config['ai_features_enabled'],
        'system_slack_bot_enabled': system_config['ai_slack_bot_enabled'],
        'system_mcp_enabled': system_config['ai_mcp_server_enabled'],
        'system_external_api_enabled': system_config['ai_external_api_enabled'],
        # Tenant-level settings (configurable by tenant admins)
        'ai_features_enabled': tenant_config['ai_features_enabled'],
        'ai_slack_queries_enabled': tenant_config['ai_slack_queries_enabled'],
        'ai_assisted_creation_enabled': tenant_config['ai_assisted_creation_enabled'],
        'ai_external_access_enabled': tenant_config['ai_external_access_enabled'],
        'ai_require_anonymization': tenant_config['ai_require_anonymization'],
        'ai_log_interactions': tenant_config['ai_log_interactions'],
    })


@app.route('/api/tenant/ai/config', methods=['POST', 'PUT'])
@login_required
def api_update_tenant_ai_config():
    """Update AI configuration for current tenant (admin only)."""
    user = get_current_user()
    tenant = get_current_tenant()

    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    membership = get_current_membership()
    if not membership or membership.global_role not in [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN]:
        return jsonify({'error': 'Permission denied. Admin or Steward role required.'}), 403

    # Check if system-level AI is enabled
    if not AIConfig.get_system_ai_enabled():
        return jsonify({'error': 'AI features are not enabled at system level'}), 403

    data = request.get_json() or {}

    # Update tenant AI settings
    AIConfig.update_tenant_ai_config(
        tenant,
        ai_features_enabled=data.get('ai_features_enabled', tenant.ai_features_enabled),
        ai_slack_queries_enabled=data.get('ai_slack_queries_enabled', tenant.ai_slack_queries_enabled),
        ai_assisted_creation_enabled=data.get('ai_assisted_creation_enabled', tenant.ai_assisted_creation_enabled),
        ai_external_access_enabled=data.get('ai_external_access_enabled', tenant.ai_external_access_enabled),
        ai_require_anonymization=data.get('ai_require_anonymization', tenant.ai_require_anonymization),
        ai_log_interactions=data.get('ai_log_interactions', tenant.ai_log_interactions),
    )

    # Log the action
    log_admin_action(
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action_type='update_ai_config',
        target_entity='tenant',
        target_id=tenant.id,
        details={
            'changes': {k: v for k, v in data.items() if k.startswith('ai_')}
        }
    )

    # Get updated config with system settings for response
    system_config = AIConfig.get_system_ai_config()
    tenant_config = AIConfig.get_tenant_ai_config(tenant)

    return jsonify({
        'message': 'Tenant AI configuration updated',
        'config': {
            # System-level settings (read-only for tenant admins)
            'system_ai_enabled': system_config['ai_features_enabled'],
            'system_slack_bot_enabled': system_config['ai_slack_bot_enabled'],
            'system_mcp_enabled': system_config['ai_mcp_server_enabled'],
            'system_external_api_enabled': system_config['ai_external_api_enabled'],
            # Tenant-level settings
            'ai_features_enabled': tenant_config['ai_features_enabled'],
            'ai_slack_queries_enabled': tenant_config['ai_slack_queries_enabled'],
            'ai_assisted_creation_enabled': tenant_config['ai_assisted_creation_enabled'],
            'ai_external_access_enabled': tenant_config['ai_external_access_enabled'],
            'ai_require_anonymization': tenant_config['ai_require_anonymization'],
            'ai_log_interactions': tenant_config['ai_log_interactions'],
        }
    })


@app.route('/api/tenant/ai/stats', methods=['GET'])
@login_required
def api_get_tenant_ai_stats():
    """Get AI usage statistics for current tenant (admin only)."""
    user = get_current_user()
    tenant = get_current_tenant()

    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    membership = get_current_membership()
    if not membership or membership.global_role not in [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN]:
        return jsonify({'error': 'Permission denied. Admin or Steward role required.'}), 403

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date = None
    end_date = None

    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str)
        except ValueError:
            return jsonify({'error': 'Invalid start_date format'}), 400

    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str)
        except ValueError:
            return jsonify({'error': 'Invalid end_date format'}), 400

    return jsonify(AIInteractionLogger.get_tenant_stats(tenant.id, start_date, end_date))


# --- User AI Preferences ---

@app.route('/api/user/ai/preferences', methods=['GET'])
@login_required
def api_get_user_ai_preferences():
    """Get AI preferences for current user."""
    user = get_current_user()
    tenant = get_current_tenant()

    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    membership = get_current_membership()
    if not membership:
        return jsonify({'error': 'You are not a member of this tenant'}), 403

    # Check if AI is available for this user
    ai_available = AIConfig.is_ai_available_for_user(user, tenant)

    return jsonify({
        'ai_opt_out': membership.ai_opt_out,
        'ai_available': ai_available,
        'tenant_ai_enabled': AIConfig.get_tenant_ai_enabled(tenant),
        'system_ai_enabled': AIConfig.get_system_ai_enabled(),
    })


@app.route('/api/user/ai/preferences', methods=['POST', 'PUT'])
@login_required
def api_update_user_ai_preferences():
    """Update AI preferences for current user."""
    user = get_current_user()
    tenant = get_current_tenant()

    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    data = request.get_json() or {}

    ai_opt_out = data.get('ai_opt_out')
    if ai_opt_out is not None:
        AIConfig.set_user_ai_opt_out(user, tenant, bool(ai_opt_out))

    membership = get_current_membership()
    return jsonify({
        'message': 'AI preferences updated',
        'ai_opt_out': membership.ai_opt_out,
    })


# --- User AI Access Check ---

@app.route('/api/user/ai/access', methods=['GET'])
@login_required
def api_check_ai_access():
    """Check if AI external access is enabled for current user."""
    user = get_current_user()
    tenant = get_current_tenant()

    if not tenant:
        return jsonify({'available': False})

    # Check if external AI is available for this user
    available = AIConfig.is_external_ai_available(user, tenant)

    return jsonify({'available': available})


# --- User AI API Keys ---

@app.route('/api/user/ai/keys', methods=['GET'])
@login_required
def api_list_ai_api_keys():
    """List AI API keys for current user."""
    user = get_current_user()
    tenant = get_current_tenant()

    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Check if external AI access is enabled
    if not AIConfig.get_tenant_external_access_enabled(tenant):
        return jsonify({'error': 'External AI access is not enabled for this organization'}), 403

    keys = AIApiKeyService.list_user_keys(user, tenant)
    return jsonify([AIApiKeyService.serialize_key(k) for k in keys])


@app.route('/api/user/ai/keys', methods=['POST'])
@login_required
def api_create_ai_api_key():
    """Create a new AI API key for current user."""
    user = get_current_user()
    tenant = get_current_tenant()

    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Check if external AI access is enabled
    if not AIConfig.get_tenant_external_access_enabled(tenant):
        return jsonify({'error': 'External AI access is not enabled for this organization'}), 403

    # Check if user has opted out
    if AIConfig.get_user_ai_opt_out(user, tenant):
        return jsonify({'error': 'You have opted out of AI features. Update your preferences to create API keys.'}), 403

    data = request.get_json() or {}
    name = data.get('name', 'API Key')
    scopes = data.get('scopes', ['read', 'search'])
    expires_in_days = data.get('expires_in_days')

    # Validate scopes
    valid_scopes = {'read', 'search', 'write'}
    if not all(s in valid_scopes for s in scopes):
        return jsonify({'error': 'Invalid scopes. Valid values: read, search, write'}), 400

    # Limit number of keys per user
    existing_keys = AIApiKeyService.list_user_keys(user, tenant)
    if len(existing_keys) >= 5:
        return jsonify({'error': 'Maximum number of API keys (5) reached. Please revoke an existing key.'}), 400

    api_key, full_key = AIApiKeyService.create_key(
        user=user,
        tenant=tenant,
        name=name,
        scopes=scopes,
        expires_in_days=expires_in_days
    )

    # Return the full key only on creation - it won't be shown again
    return jsonify({
        'message': 'API key created successfully. Save this key - it will not be shown again.',
        'key': full_key,
        **AIApiKeyService.serialize_key(api_key)
    }), 201


@app.route('/api/user/ai/keys/<key_id>', methods=['DELETE'])
@login_required
def api_revoke_ai_api_key(key_id):
    """Revoke an AI API key."""
    user = get_current_user()

    api_key = AIApiKeyService.get_key_by_id(key_id, user)
    if not api_key:
        return jsonify({'error': 'API key not found'}), 404

    if api_key.revoked_at:
        return jsonify({'error': 'API key is already revoked'}), 400

    AIApiKeyService.revoke_key(api_key)

    return jsonify({'message': 'API key revoked successfully'})


# --- AI Interaction Logs (Tenant Admin) ---

@app.route('/api/tenant/ai/logs', methods=['GET'])
@login_required
def api_get_tenant_ai_logs():
    """Get AI interaction logs for current tenant (admin only)."""
    user = get_current_user()
    tenant = get_current_tenant()

    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    membership = get_current_membership()
    if not membership or membership.global_role not in [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN]:
        return jsonify({'error': 'Permission denied. Admin or Steward role required.'}), 403

    # Check if logging is enabled
    if not tenant.ai_log_interactions:
        return jsonify({'error': 'AI interaction logging is disabled for this organization'}), 400

    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    channel = request.args.get('channel')
    action = request.args.get('action')

    channel_enum = None
    action_enum = None

    if channel:
        try:
            channel_enum = AIChannel(channel)
        except ValueError:
            return jsonify({'error': f'Invalid channel: {channel}'}), 400

    if action:
        try:
            action_enum = AIAction(action)
        except ValueError:
            return jsonify({'error': f'Invalid action: {action}'}), 400

    logs = AIInteractionLogger.get_tenant_logs(
        tenant_id=tenant.id,
        limit=limit,
        offset=offset,
        channel=channel_enum,
        action=action_enum
    )

    return jsonify({
        'logs': [AIInteractionLogger.serialize_log(log) for log in logs],
        'limit': limit,
        'offset': offset,
    })


# --- MCP Server Endpoint (Claude Code Compatible) ---

# MCP Protocol Version supported
MCP_PROTOCOL_VERSION = "2025-11-25"

# Simple in-memory session store (in production, use Redis or similar)
_mcp_sessions = {}

@app.route('/api/mcp', methods=['GET', 'POST'])
def api_mcp_handler():
    """
    MCP (Model Context Protocol) endpoint for developer tools.

    Implements the Streamable HTTP transport for Claude Code, Cursor, and VS Code.
    Supports both POST (client→server) and GET (SSE stream for server→client).

    Authentication is via API key in the Authorization header.

    Supported methods:
    - initialize: Initialize the MCP session
    - tools/list: List available tools
    - tools/call: Execute a tool
    """
    from ee.backend.ai.mcp import handle_mcp_request, get_tools
    from ee.backend.ai.config import AIConfig
    import uuid

    # Check system-level MCP availability
    if not AIConfig.get_system_ai_enabled():
        return _mcp_error_response(None, -32600, 'AI features are not enabled'), 400

    if not AIConfig.get_system_mcp_server_enabled():
        return _mcp_error_response(None, -32600, 'MCP server is not enabled'), 400

    # Handle GET request (SSE stream for server-initiated messages)
    if request.method == 'GET':
        # For now, we don't support server-initiated messages
        # Return 405 to indicate GET is not supported for this endpoint
        return jsonify({
            'error': 'GET method not supported. Use POST for MCP requests.'
        }), 405

    # POST request handling
    # Get API key from Authorization header
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return _mcp_error_response(None, -32600,
            'Missing or invalid Authorization header. Use: Bearer <api_key>'), 401

    api_key = auth_header[7:]  # Remove 'Bearer ' prefix

    if not request.is_json:
        return _mcp_error_response(None, -32700, 'Parse error: Request must be valid JSON'), 400

    request_data = request.get_json()
    request_id = request_data.get('id')
    method = request_data.get('method', '')

    # Handle initialize method specially
    if method == 'initialize':
        # Generate session ID
        session_id = str(uuid.uuid4())
        _mcp_sessions[session_id] = {
            'api_key': api_key,
            'created_at': datetime.now(timezone.utc).isoformat()
        }

        response = jsonify({
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'protocolVersion': MCP_PROTOCOL_VERSION,
                'capabilities': {
                    'tools': {}
                },
                'serverInfo': {
                    'name': 'decision-records',
                    'version': '1.0.0'
                }
            }
        })
        response.headers['MCP-Session-Id'] = session_id
        response.headers['Content-Type'] = 'application/json'
        return response

    # Handle initialized notification (client confirms initialization)
    if method == 'notifications/initialized':
        return '', 202

    # Handle the MCP request
    response_data = handle_mcp_request(request_data, api_key)

    # Build response with proper headers
    response = jsonify(response_data)
    response.headers['Content-Type'] = 'application/json'

    # Include session ID if present in request
    session_id = request.headers.get('MCP-Session-Id')
    if session_id:
        response.headers['MCP-Session-Id'] = session_id

    # Determine status code based on response
    if 'error' in response_data:
        error_code = response_data['error'].get('code', -32000)
        if error_code == -32600:  # Invalid Request
            return response, 400
        elif error_code == -32601:  # Method not found
            return response, 404

    return response


def _mcp_error_response(request_id, code, message):
    """Helper to create MCP error response."""
    return jsonify({
        'jsonrpc': '2.0',
        'id': request_id,
        'error': {
            'code': code,
            'message': message
        }
    })
# EE:END - AI/LLM Integration


# EE:START - Microsoft Teams Integration
# =============================================================================
# MICROSOFT TEAMS INTEGRATION ENDPOINTS (Enterprise Edition)
# =============================================================================

@app.route('/api/teams/webhook', methods=['POST'])
@require_teams
@track_endpoint('api_teams_webhook')
def teams_webhook():
    """Handle all Bot Framework activities from Teams.

    This is the main webhook endpoint for the Teams bot.
    All messages, invokes, and events come through here.
    """
    import asyncio
    from ee.backend.teams.teams_security import validate_teams_jwt
    from ee.backend.teams.teams_service import TeamsService

    # Validate JWT Bearer token from Bot Framework
    auth_header = request.headers.get('Authorization', '')
    claims = asyncio.run(asyncio.coroutine(lambda: validate_teams_jwt(auth_header))())

    if not claims:
        logger.warning("Invalid Teams webhook authorization")
        return jsonify({'error': 'Unauthorized'}), 401

    activity = request.get_json()
    if not activity:
        return jsonify({'error': 'Invalid request body'}), 400

    activity_type = activity.get('type', '')
    channel_data = activity.get('channelData', {})
    ms_tenant_id = channel_data.get('tenant', {}).get('id')

    # Find the Teams workspace for this tenant
    workspace = None
    if ms_tenant_id:
        workspace = TeamsWorkspace.query.filter_by(
            ms_tenant_id=ms_tenant_id,
            is_active=True
        ).first()

    if not workspace:
        # For installation events, we may not have a workspace yet
        if activity_type != 'installationUpdate':
            logger.warning(f"No Teams workspace found for MS tenant {ms_tenant_id}")
            return jsonify({'error': 'Workspace not configured'}), 404

    try:
        service = TeamsService(workspace) if workspace else None

        if activity_type == 'message':
            if service:
                response = asyncio.run(service.handle_message(activity))
                return _teams_card_response(response)
            return '', 200

        elif activity_type == 'invoke':
            if service:
                response = asyncio.run(service.handle_invoke(activity))
                return jsonify(response), 200
            return jsonify({'status': 200}), 200

        elif activity_type == 'conversationUpdate':
            if service:
                response = asyncio.run(service.handle_conversation_update(activity))
                if isinstance(response, dict) and response.get('type') == 'AdaptiveCard':
                    return _teams_card_response(response)
            return '', 200

        elif activity_type == 'installationUpdate':
            # Bot installed or uninstalled
            action = activity.get('action', '')
            if action == 'add':
                # Store service URL for future proactive messaging
                service_url = activity.get('serviceUrl')
                if ms_tenant_id and service_url:
                    # Create or update workspace entry
                    workspace = TeamsWorkspace.query.filter_by(ms_tenant_id=ms_tenant_id).first()
                    if workspace:
                        workspace.service_url = service_url
                    else:
                        workspace = TeamsWorkspace(
                            ms_tenant_id=ms_tenant_id,
                            service_url=service_url,
                            status=TeamsWorkspace.STATUS_PENDING_CONSENT
                        )
                        db.session.add(workspace)
                    db.session.commit()
            return '', 200

        return '', 200

    except Exception as e:
        logger.error(f"Teams webhook error: {str(e)}")
        capture_exception(e, endpoint_name='teams_webhook')
        return jsonify({'error': 'Internal server error'}), 500


def _teams_card_response(card):
    """Return an Adaptive Card as a Teams response."""
    return jsonify({
        'type': 'message',
        'attachments': [{
            'contentType': 'application/vnd.microsoft.card.adaptive',
            'content': card
        }]
    })


@app.route('/api/teams/oauth/start', methods=['GET'])
@require_teams
@login_required
@admin_required
@track_endpoint('api_teams_oauth_start')
def teams_oauth_start():
    """Start Azure AD OAuth consent flow for Teams integration."""
    from ee.backend.teams.teams_security import (
        get_teams_bot_app_id, generate_teams_oauth_state
    )

    try:
        app_id = get_teams_bot_app_id()
        if not app_id:
            logger.error("Teams Bot app ID not found")
            return jsonify({'error': 'Teams integration not configured'}), 500

        user = get_current_user()
        tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404

        # Generate state with tenant_id
        state = generate_teams_oauth_state(tenant.id, user.id)

        # Build redirect URI using OAuth base URL (supports Cloudflare Worker routing)
        base_url = get_oauth_base_url()
        redirect_uri = f"{base_url}/api/teams/oauth/callback"

        # Azure AD OAuth URL
        # Using 'common' endpoint for multi-tenant consent
        auth_url = (
            f"https://login.microsoftonline.com/common/adminconsent"
            f"?client_id={app_id}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )

        return redirect(auth_url)

    except Exception as e:
        logger.error(f"Teams OAuth start error: {str(e)}")
        return jsonify({'error': f'Failed to start Teams connection: {str(e)}'}), 500


@app.route('/api/teams/oauth/callback')
@require_teams
@track_endpoint('api_teams_oauth_callback')
def teams_oauth_callback():
    """Handle Azure AD admin consent callback."""
    from ee.backend.teams.teams_security import verify_teams_oauth_state

    # Check for error
    error = request.args.get('error')
    if error:
        error_description = request.args.get('error_description', error)
        logger.error(f"Teams OAuth error: {error_description}")
        return redirect(f'/settings?teams_error={error}')

    # Get admin consent parameters
    ms_tenant_id = request.args.get('tenant')
    state = request.args.get('state')

    if not ms_tenant_id:
        return redirect('/settings?teams_error=missing_tenant')

    # Verify state
    state_data = verify_teams_oauth_state(state)
    if not state_data:
        return redirect('/settings?teams_error=invalid_state')

    tenant_id = state_data.get('tenant_id')
    user_id = state_data.get('user_id')

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return redirect('/settings?teams_error=tenant_not_found')

    try:
        # Create or update Teams workspace
        workspace = TeamsWorkspace.query.filter_by(ms_tenant_id=ms_tenant_id).first()

        if workspace:
            # Update existing
            if workspace.tenant_id and workspace.tenant_id != tenant_id:
                return redirect('/settings?teams_error=workspace_already_claimed')
            workspace.tenant_id = tenant_id
            workspace.status = TeamsWorkspace.STATUS_ACTIVE
            workspace.consent_granted_at = datetime.now(timezone.utc)
            workspace.consent_granted_by_id = user_id
        else:
            # Create new
            workspace = TeamsWorkspace(
                tenant_id=tenant_id,
                ms_tenant_id=ms_tenant_id,
                status=TeamsWorkspace.STATUS_ACTIVE,
                consent_granted_at=datetime.now(timezone.utc),
                consent_granted_by_id=user_id,
                app_version='1.0.0'
            )
            db.session.add(workspace)

        db.session.commit()

        logger.info(f"Teams workspace {ms_tenant_id} connected to tenant {tenant_id}")
        return redirect('/settings?tab=teams&teams_success=connected')

    except Exception as e:
        logger.error(f"Teams OAuth callback error: {str(e)}")
        db.session.rollback()
        return redirect('/settings?teams_error=connection_failed')


@app.route('/api/teams/settings', methods=['GET'])
@require_teams
@login_required
@admin_required
@track_endpoint('api_teams_settings_get')
def teams_settings_get():
    """Get Teams integration settings for tenant."""
    from ee.backend.teams.teams_security import get_teams_bot_app_id

    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    workspace = TeamsWorkspace.query.filter_by(tenant_id=tenant.id).first()

    app_id = get_teams_bot_app_id()

    if workspace:
        return jsonify({
            'connected': True,
            'workspace': workspace.to_dict(),
            'install_url': '/api/teams/oauth/start' if app_id else None
        })
    else:
        return jsonify({
            'connected': False,
            'workspace': None,
            'install_url': '/api/teams/oauth/start' if app_id else None
        })


@app.route('/api/teams/settings', methods=['PUT'])
@require_teams
@login_required
@admin_required
@track_endpoint('api_teams_settings_put')
def teams_settings_put():
    """Update Teams notification settings."""
    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    workspace = TeamsWorkspace.query.filter_by(tenant_id=tenant.id).first()
    if not workspace:
        return jsonify({'error': 'Teams workspace not connected'}), 404

    data = request.get_json()

    # Update notification settings
    if 'notifications_enabled' in data:
        workspace.notifications_enabled = data['notifications_enabled']
    if 'notify_on_create' in data:
        workspace.notify_on_create = data['notify_on_create']
    if 'notify_on_status_change' in data:
        workspace.notify_on_status_change = data['notify_on_status_change']
    if 'default_channel_id' in data:
        workspace.default_channel_id = data['default_channel_id']
    if 'default_channel_name' in data:
        workspace.default_channel_name = data['default_channel_name']
    if 'default_team_id' in data:
        workspace.default_team_id = data['default_team_id']
    if 'default_team_name' in data:
        workspace.default_team_name = data['default_team_name']

    db.session.commit()

    return jsonify({'message': 'Settings updated', 'workspace': workspace.to_dict()})


@app.route('/api/teams/disconnect', methods=['POST'])
@require_teams
@login_required
@admin_required
@track_endpoint('api_teams_disconnect')
def teams_disconnect():
    """Disconnect Teams workspace from tenant."""
    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    workspace = TeamsWorkspace.query.filter_by(tenant_id=tenant.id).first()
    if not workspace:
        return jsonify({'error': 'Teams workspace not connected'}), 404

    # Soft delete - mark as inactive and disconnected
    workspace.is_active = False
    workspace.status = TeamsWorkspace.STATUS_DISCONNECTED
    workspace.tenant_id = None
    db.session.commit()

    logger.info(f"Teams workspace disconnected from tenant {tenant.id}")

    return jsonify({'message': 'Teams workspace disconnected'})


@app.route('/api/teams/channels', methods=['GET'])
@require_teams
@login_required
@admin_required
@track_endpoint('api_teams_channels')
def teams_channels():
    """Get list of Teams channels for notification configuration.

    Note: This requires Microsoft Graph API access which may need additional setup.
    For now, returns a placeholder response.
    """
    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    workspace = TeamsWorkspace.query.filter_by(tenant_id=tenant.id).first()
    if not workspace:
        return jsonify({'error': 'Teams workspace not connected'}), 404

    # Get stored conversation references as available channels
    channels = []
    for ref in workspace.conversation_references.filter_by(context_type='channel').all():
        channels.append({
            'id': ref.channel_id,
            'conversation_id': ref.conversation_id,
            'team_id': ref.team_id,
            'name': f"Channel {ref.channel_id[:8]}..."  # Placeholder name
        })

    return jsonify({'channels': channels})


@app.route('/api/teams/test', methods=['POST'])
@require_teams
@login_required
@admin_required
@track_endpoint('api_teams_test')
def teams_test():
    """Send a test notification to the configured Teams channel."""
    import asyncio
    from ee.backend.teams.teams_service import TeamsService
    from ee.backend.teams.teams_cards import build_success_card

    user = get_current_user()
    tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    workspace = TeamsWorkspace.query.filter_by(tenant_id=tenant.id).first()
    if not workspace:
        return jsonify({'error': 'Teams workspace not connected'}), 404

    if not workspace.default_channel_id:
        return jsonify({'error': 'No default channel configured'}), 400

    # Get conversation reference
    conv_ref = TeamsConversationReference.query.filter_by(
        teams_workspace_id=workspace.id,
        channel_id=workspace.default_channel_id
    ).first()

    if not conv_ref:
        return jsonify({'error': 'No conversation reference for configured channel'}), 400

    try:
        import json
        service = TeamsService(workspace)
        reference = json.loads(conv_ref.reference_json)
        card = build_success_card(
            "Test Notification",
            f"This is a test notification from Decision Records. Sent by {user.email}."
        )

        success = asyncio.run(service._send_proactive_message(reference, card))

        if success:
            return jsonify({'message': 'Test notification sent successfully'})
        else:
            return jsonify({'error': 'Failed to send test notification'}), 500

    except Exception as e:
        logger.error(f"Teams test notification error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/teams/link/initiate', methods=['GET'])
@require_teams
@track_endpoint('api_teams_link_initiate')
def teams_link_initiate():
    """Initiate user account linking from Teams.

    Redirects to the dedicated Teams link page with the token.
    """
    token = request.args.get('token')
    if not token:
        return jsonify({'error': 'Missing link token'}), 400

    # Redirect to the Teams link page
    return redirect(f'/teams/link?token={token}')


@app.route('/api/teams/link/validate', methods=['POST'])
@require_teams
@track_endpoint('api_teams_link_validate')
def teams_link_validate():
    """Validate a Teams link token and return workspace info."""
    from ee.backend.teams.teams_security import verify_teams_link_token

    data = request.get_json() or {}
    token = data.get('token')

    if not token:
        return jsonify({'error': 'Missing token'}), 400

    token_data = verify_teams_link_token(token)
    if not token_data:
        return jsonify({'error': 'Invalid or expired token'}), 400

    workspace_id = token_data.get('teams_workspace_id')
    workspace = db.session.get(TeamsWorkspace, workspace_id)

    if not workspace:
        return jsonify({'error': 'Workspace not found'}), 404

    tenant = workspace.tenant if workspace.tenant_id else None

    response = {
        'valid': True,
        'ms_tenant_id': workspace.ms_tenant_id,
        'ms_tenant_name': workspace.ms_tenant_name,
        'tenant_domain': tenant.domain if tenant else None,
        'tenant_name': tenant.name if tenant else None,
        'aad_email': token_data.get('aad_email')
    }

    # Check if user is logged in
    user = get_current_user()
    if user:
        response['user_logged_in'] = True
        response['user_email'] = user.email
        response['user_name'] = user.name or user.email
        response['tenant_domain'] = user.sso_domain

    return jsonify(response)


@app.route('/api/teams/link/complete', methods=['POST'])
@require_teams
@track_endpoint('api_teams_link_complete')
def teams_link_complete():
    """Complete user linking after login."""
    from ee.backend.teams.teams_security import verify_teams_link_token

    data = request.get_json() or {}
    token = data.get('token')

    if not token:
        return jsonify({'error': 'Missing token'}), 400

    token_data = verify_teams_link_token(token)
    if not token_data:
        return jsonify({'error': 'Invalid or expired token'}), 400

    workspace_id = token_data.get('teams_workspace_id')
    aad_object_id = token_data.get('aad_object_id')

    workspace = db.session.get(TeamsWorkspace, workspace_id)
    if not workspace:
        return jsonify({'error': 'Workspace not found'}), 404

    user = get_current_user()
    if not user:
        return jsonify({'error': 'You must be logged in to link your account'}), 401

    # Create or update mapping
    mapping = TeamsUserMapping.query.filter_by(
        teams_workspace_id=workspace.id,
        aad_object_id=aad_object_id
    ).first()

    if mapping:
        mapping.user_id = user.id
        mapping.link_method = 'browser_auth'
        mapping.linked_at = datetime.now(timezone.utc)
    else:
        mapping = TeamsUserMapping(
            teams_workspace_id=workspace.id,
            aad_object_id=aad_object_id,
            aad_email=token_data.get('aad_email'),
            user_id=user.id,
            link_method='browser_auth',
            linked_at=datetime.now(timezone.utc)
        )
        db.session.add(mapping)

    db.session.commit()

    logger.info(f"User {user.id} linked Teams account {aad_object_id} in workspace {workspace.id}")

    return jsonify({'message': 'Account linked successfully'})


# =============================================================================
# TEAMS OIDC (Sign in with Microsoft)
# =============================================================================

@app.route('/api/auth/teams-oidc-status', methods=['GET'])
@track_endpoint('api_auth_teams_oidc_status')
def teams_oidc_status():
    """Check if Teams OIDC is enabled."""
    from ee.backend.teams.teams_security import get_teams_bot_app_id

    app_id = get_teams_bot_app_id()
    commercial_enabled = os.environ.get('COMMERCIAL_FEATURES_ENABLED', '').lower() == 'true'

    return jsonify({
        'enabled': bool(app_id) and commercial_enabled
    })


@app.route('/auth/teams/oidc', methods=['GET'])
@require_teams
@track_endpoint('auth_teams_oidc')
def teams_oidc_start():
    """Start Microsoft OIDC authentication flow."""
    from ee.backend.teams.teams_security import (
        get_teams_bot_app_id, generate_teams_oidc_state,
        TEAMS_OIDC_SCOPES
    )

    app_id = get_teams_bot_app_id()
    if not app_id:
        return jsonify({'error': 'Teams OIDC not configured'}), 500

    # Get return URL from query params
    return_url = request.args.get('return_url', '/')

    # Generate state
    state = generate_teams_oidc_state(return_url=return_url)

    # Build redirect URI using OAuth base URL (supports Cloudflare Worker routing)
    base_url = get_oauth_base_url()
    redirect_uri = f"{base_url}/auth/teams/oidc/callback"

    # Build authorization URL
    auth_url = (
        f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        f"?client_id={app_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&response_mode=query"
        f"&scope={TEAMS_OIDC_SCOPES.replace(' ', '%20')}"
        f"&state={state}"
    )

    return redirect(auth_url)


@app.route('/auth/teams/oidc/callback', methods=['GET'])
@require_teams
@track_endpoint('auth_teams_oidc_callback')
def teams_oidc_callback():
    """Handle Microsoft OIDC callback."""
    from ee.backend.teams.teams_security import (
        verify_teams_oidc_state, exchange_teams_oidc_code,
        get_teams_user_info
    )

    # Capture request metadata for login history
    ip_address = request.headers.get('CF-Connecting-IP', request.remote_addr)
    user_agent = request.headers.get('User-Agent')

    error = request.args.get('error')
    if error:
        error_description = request.args.get('error_description', error)
        logger.error(f"Teams OIDC error: {error_description}")
        log_login_attempt(
            email='unknown',
            login_method=LoginHistory.METHOD_TEAMS_OIDC,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=f'Teams error: {error_description[:200]}'
        )
        return redirect(f'/login?error={error}')

    code = request.args.get('code')
    state = request.args.get('state')

    if not code:
        return redirect('/login?error=missing_code')

    # Verify state
    state_data = verify_teams_oidc_state(state)
    if not state_data:
        return redirect('/login?error=invalid_state')

    return_url = state_data.get('return_url', '/')

    # Build redirect URI (must match the one used in authorization)
    base_url = get_oauth_base_url()
    redirect_uri = f"{base_url}/auth/teams/oidc/callback"

    # Exchange code for tokens
    id_claims, access_token = exchange_teams_oidc_code(code, redirect_uri)

    if not id_claims:
        return redirect('/login?error=token_exchange_failed')

    # Extract user info from ID token claims
    email = id_claims.get('email') or id_claims.get('preferred_username')
    name = id_claims.get('name')
    ms_tenant_id = id_claims.get('tid')

    if not email:
        # Try to get email from Graph API
        user_info = get_teams_user_info(access_token)
        if user_info:
            email = user_info.get('mail') or user_info.get('userPrincipalName')
            name = name or user_info.get('displayName')

    if not email:
        return redirect('/login?error=no_email')

    # Extract domain from email
    email_parts = email.split('@')
    if len(email_parts) != 2:
        return redirect('/login?error=invalid_email')

    domain = email_parts[1].lower()

    # Check if domain is a public email provider
    try:
        from free_email_domains import FREE_EMAIL_DOMAINS
        if domain in FREE_EMAIL_DOMAINS:
            return redirect('/login?error=personal_email')
    except ImportError:
        pass

    # Find or create user
    user = User.query.filter_by(email=email.lower()).first()

    if user:
        # Existing user - log them in
        user.last_login = datetime.now(timezone.utc)
        if not user.name and name:
            user.name = name
        db.session.commit()
    else:
        # New user - check if tenant exists
        tenant = Tenant.query.filter_by(domain=domain).first()

        if not tenant:
            # Create tenant for new domain
            tenant = Tenant(
                domain=domain,
                name=domain.split('.')[0].title()
            )
            db.session.add(tenant)
            db.session.flush()

            # Create default space
            default_space = Space(
                tenant_id=tenant.id,
                name='General',
                is_default=True
            )
            db.session.add(default_space)

        # Create user
        user = User(
            email=email.lower(),
            name=name,
            sso_domain=domain,
            auth_method='teams_oidc',
            email_verified=True,  # Microsoft verified the email
            last_login=datetime.now(timezone.utc)
        )
        db.session.add(user)
        db.session.flush()

        # Add tenant membership
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            role='admin' if TenantMembership.query.filter_by(tenant_id=tenant.id).count() == 0 else 'member'
        )
        db.session.add(membership)
        db.session.commit()

    # Log successful Teams OIDC login
    log_login_attempt(
        email=email,
        login_method=LoginHistory.METHOD_TEAMS_OIDC,
        success=True,
        user_id=user.id,
        tenant_domain=domain,
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Set session
    session['user_id'] = user.id
    session['auth_method'] = 'teams_oidc'
    session.permanent = True

    logger.info(f"User {user.id} logged in via Teams OIDC")

    # Get app base URL for post-auth redirect (handles subdomain routing)
    app_base = get_app_base_url()

    # Redirect to return URL or tenant home
    if return_url and return_url != '/' and not return_url.startswith('/?'):
        # Ensure return_url is absolute if APP_BASE_URL is set
        if return_url.startswith('/') and app_base:
            return redirect(f'{app_base}{return_url}')
        return redirect(return_url)

    # Redirect to tenant dashboard
    return redirect(f'{app_base}/{domain}')
# EE:END - Microsoft Teams Integration


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
