import os
import secrets
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
from authlib.integrations.requests_client import OAuth2Session
from models import db, User, SSOConfig, EmailConfig, Subscription, ArchitectureDecision, DecisionHistory, save_history
from auth import login_required, admin_required, get_current_user, get_or_create_user, get_oidc_config, extract_domain_from_email
from notifications import notify_subscribers_new_decision, notify_subscribers_decision_updated
from datetime import datetime

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///architecture_decisions.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Initialize database
db.init_app(app)

# Create tables on startup
with app.app_context():
    db.create_all()


# ==================== Context Processor ====================

@app.context_processor
def inject_user():
    """Make current user available in all templates."""
    return {'current_user': get_current_user()}


# ==================== Auth Routes ====================

@app.route('/login')
def login():
    """Login page - shows available SSO providers."""
    if 'user_id' in session:
        return redirect(url_for('index'))
    sso_configs = SSOConfig.query.filter_by(enabled=True).all()
    return render_template('login.html', sso_configs=sso_configs)


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
    return render_template('profile.html')


# ==================== API Routes - Decisions ====================

@app.route('/api/decisions', methods=['GET'])
@login_required
def api_list_decisions():
    """List all architecture decisions for the user's domain."""
    decisions = ArchitectureDecision.query.filter_by(
        domain=g.current_user.sso_domain,
        deleted_at=None
    ).order_by(ArchitectureDecision.id.desc()).all()
    return jsonify([d.to_dict() for d in decisions])


@app.route('/api/decisions', methods=['POST'])
@login_required
def api_create_decision():
    """Create a new architecture decision."""
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

    config = EmailConfig.query.filter_by(domain=g.current_user.sso_domain).first()
    if not config:
        return jsonify({'error': 'Email configuration not found'}), 404

    success = send_email(
        config,
        g.current_user.email,
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
    """List all users in the admin's domain."""
    users = User.query.filter_by(sso_domain=g.current_user.sso_domain).all()
    return jsonify([u.to_dict() for u in users])


@app.route('/api/admin/users/<int:user_id>/admin', methods=['PUT'])
@admin_required
def api_toggle_user_admin(user_id):
    """Toggle admin status for a user (admin only)."""
    if user_id == g.current_user.id:
        return jsonify({'error': 'Cannot modify your own admin status'}), 400

    user = User.query.filter_by(id=user_id, sso_domain=g.current_user.sso_domain).first_or_404()

    data = request.get_json()
    user.is_admin = bool(data.get('is_admin', False))

    db.session.commit()

    return jsonify(user.to_dict())


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
