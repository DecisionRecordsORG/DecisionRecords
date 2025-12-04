import os
import json
import secrets
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g, send_from_directory
from authlib.integrations.requests_client import OAuth2Session
from models import db, User, MasterAccount, SSOConfig, EmailConfig, Subscription, ArchitectureDecision, DecisionHistory, AuthConfig, WebAuthnCredential, AccessRequest, save_history
from auth import login_required, admin_required, get_current_user, get_or_create_user, get_oidc_config, extract_domain_from_email, is_master_account, authenticate_master, master_required
from notifications import notify_subscribers_new_decision, notify_subscribers_decision_updated
from webauthn_auth import (
    create_registration_options, verify_registration,
    create_authentication_options, verify_authentication,
    get_user_credentials, delete_credential, get_auth_config
)
from datetime import datetime

# Determine if we're serving Angular frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist', 'frontend', 'browser')
SERVE_ANGULAR = os.path.exists(FRONTEND_DIR)

app = Flask(__name__, static_folder=FRONTEND_DIR if SERVE_ANGULAR else 'static')

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///architecture_decisions.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Initialize database
db.init_app(app)

# Create tables and master account on startup
with app.app_context():
    db.create_all()
    # Create default master account
    MasterAccount.create_default_master(db.session)


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
    """Login page - shows available SSO providers and local login."""
    if 'user_id' in session or session.get('is_master'):
        return redirect(url_for('index'))
    sso_configs = SSOConfig.query.filter_by(enabled=True).all()
    return render_template('login.html', sso_configs=sso_configs)


@app.route('/auth/local', methods=['POST'])
def local_login():
    """Handle local master account login."""
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


@app.route('/auth/sso/<int:config_id>')
def sso_login(config_id):
    """Initiate SSO login flow."""
    sso_config = SSOConfig.query.get_or_404(config_id)

    if not sso_config.enabled:
        return redirect(url_for('login'))

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
        return redirect(url_for('login'))

    sso_config = SSOConfig.query.get(config_id)
    if not sso_config:
        return redirect(url_for('login'))

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
    return redirect(url_for('login'))


# ==================== Web Routes ====================

@app.route('/')
@login_required
def index():
    """Home page - list all architecture decisions."""
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

    # Validate required fields
    required_fields = ['title', 'context', 'decision', 'consequences']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Validate status if provided
    status = data.get('status', 'proposed')
    if status not in ArchitectureDecision.VALID_STATUSES:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(ArchitectureDecision.VALID_STATUSES)}'}), 400

    decision = ArchitectureDecision(
        title=data['title'],
        context=data['context'],
        decision=data['decision'],
        status=status,
        consequences=data['consequences'],
        domain=g.current_user.sso_domain,
        created_by_id=g.current_user.id,
        updated_by_id=g.current_user.id
    )

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
    """List all SSO configurations (admin only)."""
    configs = SSOConfig.query.all()
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

    return jsonify({
        'domain': domain,
        'has_users': has_users,
        'user_count': user_count,
        'auth_method': auth_config.auth_method if auth_config else 'webauthn',
        'allow_registration': auth_config.allow_registration if auth_config else True,
        'has_sso': sso_config is not None,
        'sso_provider': sso_config.provider_name if sso_config else None,
        'sso_id': sso_config.id if sso_config else None,
    })


@app.route('/api/auth/user-exists/<email>', methods=['GET'])
def api_check_user_exists(email):
    """Check if a user exists by email."""
    user = User.query.filter_by(email=email.lower()).first()

    if user:
        return jsonify({
            'exists': True,
            'has_passkey': len(user.webauthn_credentials) > 0 if user.webauthn_credentials else False,
            'auth_type': user.auth_type
        })
    else:
        return jsonify({
            'exists': False,
            'has_passkey': False,
            'auth_type': None
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
def api_webauthn_register_options():
    """Generate WebAuthn registration options."""
    data = request.get_json()

    email = data.get('email')
    name = data.get('name')
    domain = data.get('domain')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    # Extract domain from email if not provided
    if not domain:
        from auth import extract_domain_from_email
        domain = extract_domain_from_email(email)

    if not domain:
        return jsonify({'error': 'Could not determine domain from email'}), 400

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
            rp_name=data.get('rp_name', 'Architecture Decisions'),
        )
        db.session.add(config)
    else:
        config.auth_method = auth_method
        if 'allow_registration' in data:
            config.allow_registration = bool(data['allow_registration'])
        if 'rp_name' in data:
            config.rp_name = data['rp_name']

    db.session.commit()

    return jsonify(config.to_dict())


# ==================== Angular Frontend Serving ====================

if SERVE_ANGULAR:
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_angular(path):
        """Serve Angular frontend or fallback to index.html for SPA routing."""
        # Exclude API routes and auth routes
        if path.startswith('api/') or path.startswith('auth/') or path in ['login', 'logout']:
            return app.send_static_file('index.html')

        # Try to serve static files
        if path and os.path.exists(os.path.join(FRONTEND_DIR, path)):
            return send_from_directory(FRONTEND_DIR, path)

        # Fallback to index.html for SPA routing
        return send_from_directory(FRONTEND_DIR, 'index.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
