from functools import wraps
from flask import session, redirect, url_for, request, jsonify, g
from authlib.integrations.requests_client import OAuth2Session
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_current_user():
    """Get the current logged-in user from the session."""
    from models import db, User, MasterAccount

    # Check if it's a master account session
    if session.get('is_master'):
        master_id = session.get('master_id')
        if master_id:
            return MasterAccount.query.get(master_id)
        return None

    # Regular user session
    user_id = session.get('user_id')
    if not user_id:
        return None

    return User.query.get(user_id)


def is_master_account():
    """Check if the current session is a master account."""
    return session.get('is_master', False)


def login_required(f):
    """Decorator to require authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for master account session
        if session.get('is_master') and session.get('master_id'):
            from models import MasterAccount
            g.current_user = MasterAccount.query.get(session.get('master_id'))
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


def authenticate_master(username, password):
    """Authenticate a master account with username and password."""
    from models import db, MasterAccount

    master = MasterAccount.query.filter_by(username=username).first()
    if master and master.check_password(password):
        master.last_login = datetime.utcnow()
        db.session.commit()
        return master
    return None


def get_or_create_user(email, name, sso_subject, sso_domain):
    """Get existing user or create a new one after SSO authentication."""
    from models import db, User

    user = User.query.filter_by(email=email).first()

    if user:
        # Update last login
        user.last_login = datetime.utcnow()
        # Update name if changed
        if name and user.name != name:
            user.name = name
        db.session.commit()
    else:
        # Create new user
        # First user for a domain becomes admin
        existing_domain_users = User.query.filter_by(sso_domain=sso_domain).count()
        is_admin = existing_domain_users == 0

        user = User(
            email=email,
            name=name,
            sso_subject=sso_subject,
            sso_domain=sso_domain,
            is_admin=is_admin,
            last_login=datetime.utcnow()
        )
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
