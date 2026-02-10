from functools import wraps
from flask import session, redirect, url_for, request, jsonify, g
from authlib.integrations.requests_client import OAuth2Session
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def get_current_user():
    """Get the current logged-in user from the session."""
    from models import db, User, MasterAccount

    # Check if it's a master account session
    if session.get('is_master'):
        master_id = session.get('master_id')
        if master_id:
            return db.session.get(MasterAccount, master_id)
        return None

    # Regular user session
    user_id = session.get('user_id')
    if not user_id:
        return None

    return db.session.get(User, user_id)


def is_master_account():
    """Check if the current session is a master account."""
    return session.get('is_master', False)


def validate_setup_token():
    """
    Validate a setup token for credential setup during incomplete account registration
    or account recovery.

    Returns:
        tuple: (user, error_message) - user object if valid, None and error message if invalid

    Security Note:
        Setup tokens are issued during passkey-preference signup to allow credential setup
        without granting full session access. This prevents account hijacking if users
        don't complete the setup process.

        Recovery tokens allow users who have lost access to their credentials to set up
        new ones. For recovery, users ARE expected to have existing credentials.
    """
    from models import db, User, SetupToken
    from datetime import datetime

    # Check for setup token in session
    setup_token = session.get('setup_token')
    setup_user_id = session.get('setup_user_id')
    setup_expires = session.get('setup_expires')
    setup_purpose = session.get('setup_purpose')

    if not setup_token or not setup_user_id or not setup_expires:
        return None, 'No setup token found'

    # Check if token has expired (30 minute window)
    try:
        expires_at = datetime.fromisoformat(setup_expires)
        if datetime.now(timezone.utc) > expires_at:
            # Clear expired setup session
            session.pop('setup_token', None)
            session.pop('setup_user_id', None)
            session.pop('setup_expires', None)
            session.pop('setup_purpose', None)
            return None, 'Setup token has expired. Please start signup again.'
    except (ValueError, TypeError):
        return None, 'Invalid setup token'

    # Verify user exists and is in incomplete state
    user = db.session.get(User, setup_user_id)
    if not user:
        return None, 'User not found'

    # Check if this is a recovery flow - recovery users ARE expected to have credentials
    is_recovery = setup_purpose == SetupToken.PURPOSE_ACCOUNT_RECOVERY

    # User should not have any credentials yet (incomplete state) - unless this is recovery
    has_passkey = len(user.webauthn_credentials) > 0 if user.webauthn_credentials else False
    has_password = user.has_password()

    if (has_passkey or has_password) and not is_recovery:
        # User already has credentials and this is not a recovery flow
        # Clear setup token and require normal login
        session.pop('setup_token', None)
        session.pop('setup_user_id', None)
        session.pop('setup_expires', None)
        session.pop('setup_purpose', None)
        return None, 'Account setup already complete. Please log in.'

    return user, None


def setup_token_required(f):
    """
    Decorator for endpoints that can be accessed with a setup token.
    Allows incomplete accounts to set up their first credential.

    The decorated function will have g.setup_user set if authenticated via setup token.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user, error = validate_setup_token()
        if error:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': error, 'setup_expired': True}), 401
            return redirect('/')

        g.setup_user = user
        return f(*args, **kwargs)
    return decorated_function


def complete_setup_and_login(user):
    """
    Complete the setup process and convert setup token to full session.
    Called after user successfully creates their first credential.
    """
    from models import db
    from datetime import datetime

    # Clear setup token
    session.pop('setup_token', None)
    session.pop('setup_user_id', None)
    session.pop('setup_expires', None)
    session.pop('setup_purpose', None)

    # Create full session
    session['user_id'] = user.id
    session.permanent = True

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    logger.info(f"Setup completed for user {user.email} - full session created")


def login_required(f):
    """Decorator to require authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for master account session
        if session.get('is_master') and session.get('master_id'):
            from models import db, MasterAccount
            g.current_user = db.session.get(MasterAccount, session.get('master_id'))
            if g.current_user:
                return f(*args, **kwargs)

        # Check for regular user session
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect('/')

        g.current_user = get_current_user()
        if not g.current_user:
            session.clear()
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect('/')

        # Check if user has completed credential setup
        # Users must have at least one auth method (passkey or password)
        if not is_master_account():
            has_passkey = len(g.current_user.webauthn_credentials) > 0 if g.current_user.webauthn_credentials else False
            has_password = g.current_user.has_password()

            if not has_passkey and not has_password:
                # User is in incomplete state - redirect to setup
                # Allow access to setup-related endpoints
                allowed_paths = [
                    '/api/webauthn/register',
                    '/api/auth/set-password',
                    '/api/auth/me',
                    '/api/auth/logout',
                    '/api/subscription',  # Profile page loads subscription
                    '/api/webauthn/credentials',  # Profile page loads credentials
                ]
                if not any(request.path.startswith(p) for p in allowed_paths):
                    domain = g.current_user.sso_domain
                    if request.is_json or request.path.startswith('/api/'):
                        return jsonify({
                            'error': 'Credential setup required',
                            'setup_required': True,
                            'redirect': f'/{domain}/setup'
                        }), 403
                    return redirect(f'/{domain}/setup')

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges for a route."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # Master accounts always have admin access
        if is_master_account():
            return f(*args, **kwargs)

        if not g.current_user.is_admin:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def master_required(f):
    """Decorator to require master account for a route."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not is_master_account():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Master account access required'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def steward_or_admin_required(f):
    """Decorator to require steward or admin privileges for a route."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        from models import Tenant, GlobalRole

        # Master accounts always have access
        if is_master_account():
            return f(*args, **kwargs)

        # Get user's membership for their domain's tenant
        tenant = Tenant.query.filter_by(domain=g.current_user.sso_domain).first()
        if not tenant:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Tenant not found'}), 404
            return redirect(url_for('index'))

        membership = g.current_user.get_membership(tenant_id=tenant.id)
        if not membership:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Not a member of this tenant'}), 403
            return redirect(url_for('index'))

        # Check if user is steward or admin (any admin level)
        if membership.global_role not in [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN]:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Steward or admin access required'}), 403
            return redirect(url_for('index'))

        # Set tenant and membership in g for route handlers
        g.current_tenant = tenant
        g.current_membership = membership
        return f(*args, **kwargs)
    return decorated_function


def get_current_tenant():
    """Get the current user's tenant based on their domain."""
    from models import Tenant

    if is_master_account():
        return None

    if not g.current_user or not g.current_user.sso_domain:
        return None

    return Tenant.query.filter_by(domain=g.current_user.sso_domain).first()


def get_current_membership():
    """Get the current user's membership in their tenant."""
    tenant = get_current_tenant()
    if not tenant or not g.current_user:
        return None
    return g.current_user.get_membership(tenant_id=tenant.id)


def authenticate_master(username, password):
    """Authenticate a master account with username and password."""
    from models import db, MasterAccount

    master = MasterAccount.query.filter_by(username=username).first()
    if master and master.check_password(password):
        master.last_login = datetime.now(timezone.utc)
        db.session.commit()
        return master
    return None


def get_or_create_user(email, name, sso_subject, sso_domain, first_name=None, last_name=None):
    """Get existing user or create a new one after SSO authentication.

    Args:
        email: User's email address
        name: Full name (legacy, will be parsed if first_name/last_name not provided)
        sso_subject: SSO subject identifier
        sso_domain: User's domain for multi-tenancy
        first_name: Optional first name (preferred over parsing from name)
        last_name: Optional last name (preferred over parsing from name)
    """
    from models import db, User

    user = User.query.filter_by(email=email).first()

    if user:
        # Update last login
        user.last_login = datetime.now(timezone.utc)
        # Always update SSO fields - sso_domain is derived from email so it's authoritative
        # This ensures users can log in via any SSO provider and get proper tenant access
        user.sso_domain = sso_domain
        user.sso_subject = sso_subject
        # Update name if changed
        if first_name or last_name:
            user.set_name(first_name=first_name, last_name=last_name)
        elif name and user.name != name:
            user.set_name(full_name=name)
        db.session.commit()
    else:
        # Create new user
        # First user for a domain becomes admin
        existing_domain_users = User.query.filter_by(sso_domain=sso_domain).count()
        is_admin = existing_domain_users == 0

        user = User(
            email=email,
            sso_subject=sso_subject,
            sso_domain=sso_domain,
            is_admin=is_admin,
            last_login=datetime.now(timezone.utc)
        )
        # Set name using the helper method
        if first_name or last_name:
            user.set_name(first_name=first_name, last_name=last_name)
        elif name:
            user.set_name(full_name=name)
        db.session.add(user)
        db.session.commit()

    return user


def create_oauth_client(sso_config):
    """Create an OAuth2 session for the given SSO configuration."""
    return OAuth2Session(
        client_id=sso_config.client_id,
        client_secret=sso_config.client_secret,
    )


def get_oidc_config(discovery_url):
    """Fetch OpenID Connect configuration from discovery URL."""
    import requests

    try:
        response = requests.get(discovery_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch OIDC config from {discovery_url}: {e}")
        return None


def extract_domain_from_email(email):
    """Extract domain from email address."""
    if '@' in email:
        return email.split('@')[1].lower()
    return None
