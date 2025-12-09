import os
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Default master account credentials
DEFAULT_MASTER_USERNAME = os.environ.get('MASTER_USERNAME', 'admin')
DEFAULT_MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', 'changeme')


class SystemConfig(db.Model):
    """Global system configuration managed by super admin."""

    __tablename__ = 'system_config'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.String(500), nullable=True)
    description = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Default configuration keys
    KEY_EMAIL_VERIFICATION_REQUIRED = 'email_verification_required'
    KEY_SUPER_ADMIN_EMAIL = 'super_admin_notification_email'
    KEY_ADMIN_SESSION_TIMEOUT_HOURS = 'admin_session_timeout_hours'
    KEY_USER_SESSION_TIMEOUT_HOURS = 'user_session_timeout_hours'

    # Default values
    DEFAULT_ADMIN_SESSION_TIMEOUT = 1  # 1 hour for super admin
    DEFAULT_USER_SESSION_TIMEOUT = 8   # 8 hours for regular users

    @staticmethod
    def get(key, default=None):
        """Get a configuration value."""
        config = SystemConfig.query.filter_by(key=key).first()
        if config:
            return config.value
        return default

    @staticmethod
    def get_bool(key, default=False):
        """Get a configuration value as boolean."""
        value = SystemConfig.get(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on')

    @staticmethod
    def get_int(key, default=0):
        """Get a configuration value as integer."""
        value = SystemConfig.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def set(key, value, description=None):
        """Set a configuration value."""
        config = SystemConfig.query.filter_by(key=key).first()
        if config:
            config.value = str(value)
            if description:
                config.description = description
        else:
            config = SystemConfig(key=key, value=str(value), description=description)
            db.session.add(config)
        db.session.commit()
        return config

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'updated_at': self.updated_at.isoformat()
        }


class MasterAccount(db.Model):
    """Master account for system administration with local authentication."""

    __tablename__ = 'master_accounts'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=True, default='System Administrator')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        """Hash and set the password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'is_master': True,
            'is_admin': True,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }

    @staticmethod
    def create_default_master(db_session):
        """Create the default master account if it doesn't exist."""
        existing = MasterAccount.query.filter_by(username=DEFAULT_MASTER_USERNAME).first()
        if not existing:
            master = MasterAccount(
                username=DEFAULT_MASTER_USERNAME,
                name='System Administrator'
            )
            master.set_password(DEFAULT_MASTER_PASSWORD)
            db_session.add(master)
            db_session.commit()
            return master
        return existing


class User(db.Model):
    """User model for authenticated users via SSO, WebAuthn, or local password."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)  # For local/password authentication
    sso_subject = db.Column(db.String(255), nullable=True)  # Subject ID from SSO provider (null for local users)
    sso_domain = db.Column(db.String(255), nullable=False)  # Domain for multi-tenancy
    auth_type = db.Column(db.String(20), nullable=False, default='local')  # 'sso', 'webauthn', or 'local'
    is_admin = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)  # Email verification status
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    decisions_created = db.relationship('ArchitectureDecision', backref='creator', lazy=True, foreign_keys='ArchitectureDecision.created_by_id')
    subscriptions = db.relationship('Subscription', backref='user', lazy=True, uselist=False)
    webauthn_credentials = db.relationship('WebAuthnCredential', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash and set the password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def has_password(self):
        """Check if user has a password set."""
        return self.password_hash is not None

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'sso_domain': self.sso_domain,
            'auth_type': self.auth_type,
            'is_admin': self.is_admin,
            'email_verified': self.email_verified,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'has_passkey': len(self.webauthn_credentials) > 0 if self.webauthn_credentials else False,
            'has_password': self.has_password(),
        }


class SSOConfig(db.Model):
    """SSO configuration for OpenID Connect providers."""

    __tablename__ = 'sso_configs'

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False, unique=True)  # e.g., "company.com"
    provider_name = db.Column(db.String(100), nullable=False)  # e.g., "Google", "Okta", "Azure AD"
    client_id = db.Column(db.String(255), nullable=False)
    client_secret = db.Column(db.String(255), nullable=False)
    discovery_url = db.Column(db.String(500), nullable=False)  # OpenID Connect discovery URL
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_secret=False):
        data = {
            'id': self.id,
            'domain': self.domain,
            'provider_name': self.provider_name,
            'client_id': self.client_id,
            'discovery_url': self.discovery_url,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        if include_secret:
            data['client_secret'] = self.client_secret
        return data


class EmailConfig(db.Model):
    """Email configuration for notifications."""

    __tablename__ = 'email_configs'

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False, unique=True)  # Associated SSO domain
    smtp_server = db.Column(db.String(255), nullable=False)
    smtp_port = db.Column(db.Integer, nullable=False, default=587)
    smtp_username = db.Column(db.String(255), nullable=False)
    smtp_password = db.Column(db.String(255), nullable=False)
    from_email = db.Column(db.String(255), nullable=False)
    from_name = db.Column(db.String(255), nullable=False, default='Architecture Decisions')
    use_tls = db.Column(db.Boolean, default=True)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_password=False):
        data = {
            'id': self.id,
            'domain': self.domain,
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'smtp_username': self.smtp_username,
            'from_email': self.from_email,
            'from_name': self.from_name,
            'use_tls': self.use_tls,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        if include_password:
            data['smtp_password'] = self.smtp_password
        return data


class AuthConfig(db.Model):
    """Authentication configuration for a domain."""

    __tablename__ = 'auth_configs'

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False, unique=True)
    auth_method = db.Column(db.String(20), nullable=False, default='local')  # 'sso', 'webauthn', or 'local'
    allow_password = db.Column(db.Boolean, default=True)  # Allow password login
    allow_passkey = db.Column(db.Boolean, default=True)  # Allow passkey/WebAuthn login
    allow_registration = db.Column(db.Boolean, default=True)  # Allow new user registration
    require_approval = db.Column(db.Boolean, default=True)  # Require admin approval for new users to join tenant
    rp_name = db.Column(db.String(255), nullable=False, default='Architecture Decisions')  # Relying Party name for WebAuthn
    tenant_prefix = db.Column(db.String(3), unique=True, nullable=True)  # 3-letter prefix for decision IDs (consonants only)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Consonants only for tenant prefix (no vowels to avoid offensive words)
    CONSONANTS = 'BCDFGHJKLMNPQRSTVWXYZ'

    @staticmethod
    def generate_unique_prefix():
        """Generate a unique 3-letter prefix using consonants only."""
        import random
        max_attempts = 100
        for _ in range(max_attempts):
            prefix = ''.join(random.choices(AuthConfig.CONSONANTS, k=3))
            existing = AuthConfig.query.filter_by(tenant_prefix=prefix).first()
            if not existing:
                return prefix
        raise ValueError("Could not generate unique prefix after {} attempts".format(max_attempts))

    def to_dict(self):
        return {
            'id': self.id,
            'domain': self.domain,
            'auth_method': self.auth_method,
            'allow_password': self.allow_password,
            'allow_passkey': self.allow_passkey,
            'allow_registration': self.allow_registration,
            'require_approval': self.require_approval,
            'rp_name': self.rp_name,
            'tenant_prefix': self.tenant_prefix,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class DomainApproval(db.Model):
    """Domain approval for preventing public email domains (gmail, etc)."""

    __tablename__ = 'domain_approvals'

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False, unique=True)
    status = db.Column(db.String(20), nullable=False, default='pending')  # 'pending', 'approved', 'rejected'
    requested_by_email = db.Column(db.String(255), nullable=True)  # Email of first user who tried to signup
    requested_by_name = db.Column(db.String(255), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('master_accounts.id'), nullable=True)
    rejection_reason = db.Column(db.String(500), nullable=True)
    auto_approved = db.Column(db.Boolean, default=False)  # True if auto-approved (corporate domain)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)  # When approved/rejected

    @staticmethod
    def is_public_domain(domain):
        """Check if domain is a free/public email provider using external blocklist."""
        try:
            from free_email_domains import whitelist as free_domains
            return domain.lower() in free_domains
        except ImportError:
            # Fallback to basic list if package not installed
            basic_public = [
                'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com',
                'aol.com', 'icloud.com', 'mail.com', 'protonmail.com', 'proton.me'
            ]
            return domain.lower() in basic_public

    @staticmethod
    def is_disposable_domain(domain):
        """Check if domain is a disposable/temporary email provider."""
        try:
            from disposable_email_domains import blocklist as disposable_domains
            return domain.lower() in disposable_domains
        except ImportError:
            return False

    @staticmethod
    def is_blocked_domain(domain):
        """Check if domain should be blocked (public or disposable)."""
        return DomainApproval.is_public_domain(domain) or DomainApproval.is_disposable_domain(domain)

    @staticmethod
    def is_approved(domain):
        """Check if domain is approved for signup."""
        approval = DomainApproval.query.filter_by(domain=domain.lower()).first()
        return approval and approval.status == 'approved'

    @staticmethod
    def needs_approval(domain):
        """Check if domain needs approval (not yet approved)."""
        domain = domain.lower()
        approval = DomainApproval.query.filter_by(domain=domain).first()
        if not approval:
            return True  # New domain needs approval
        return approval.status == 'pending'

    def to_dict(self):
        return {
            'id': self.id,
            'domain': self.domain,
            'status': self.status,
            'requested_by_email': self.requested_by_email,
            'requested_by_name': self.requested_by_name,
            'is_public_domain': self.is_public_domain(self.domain),
            'is_disposable_domain': self.is_disposable_domain(self.domain),
            'auto_approved': self.auto_approved,
            'rejection_reason': self.rejection_reason,
            'created_at': self.created_at.isoformat(),
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class WebAuthnCredential(db.Model):
    """WebAuthn credentials for passwordless authentication."""

    __tablename__ = 'webauthn_credentials'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    credential_id = db.Column(db.LargeBinary, nullable=False, unique=True)  # Raw credential ID bytes
    public_key = db.Column(db.LargeBinary, nullable=False)  # COSE public key
    sign_count = db.Column(db.Integer, nullable=False, default=0)
    device_name = db.Column(db.String(255), nullable=True)  # User-friendly name for the device
    transports = db.Column(db.String(255), nullable=True)  # JSON array of transports
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        import base64
        return {
            'id': self.id,
            'credential_id': base64.urlsafe_b64encode(self.credential_id).decode('utf-8').rstrip('='),
            'device_name': self.device_name or 'Security Key',
            'created_at': self.created_at.isoformat(),
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
        }


class Subscription(db.Model):
    """User subscriptions for email notifications."""

    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    notify_on_create = db.Column(db.Boolean, default=True)
    notify_on_update = db.Column(db.Boolean, default=False)
    notify_on_status_change = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'notify_on_create': self.notify_on_create,
            'notify_on_update': self.notify_on_update,
            'notify_on_status_change': self.notify_on_status_change,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


# Association table for many-to-many relationship between Decisions and Infrastructure
decision_infrastructure = db.Table('decision_infrastructure',
    db.Column('decision_id', db.Integer, db.ForeignKey('architecture_decisions.id'), primary_key=True),
    db.Column('infrastructure_id', db.Integer, db.ForeignKey('it_infrastructure.id'), primary_key=True),
    db.Column('created_at', db.DateTime, nullable=False, default=datetime.utcnow)
)


class ITInfrastructure(db.Model):
    """IT Infrastructure items that architecture decisions can be mapped to."""

    __tablename__ = 'it_infrastructure'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # application, network, database, server, service, api, storage, cloud, container, other
    description = db.Column(db.Text, nullable=True)
    domain = db.Column(db.String(255), nullable=False, index=True)  # Multi-tenancy
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    # Valid infrastructure types
    VALID_TYPES = ['application', 'network', 'database', 'server', 'service', 'api', 'storage', 'cloud', 'container', 'other']

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'description': self.description,
            'domain': self.domain,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'created_by': self.created_by.to_dict() if self.created_by else None,
        }


class ArchitectureDecision(db.Model):
    """Main table for Architecture Decision Records (ADRs)."""

    __tablename__ = 'architecture_decisions'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    context = db.Column(db.Text, nullable=False)
    decision = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='proposed')
    consequences = db.Column(db.Text, nullable=False)
    decision_number = db.Column(db.Integer, nullable=True)  # Sequential number per tenant for display ID
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Multi-tenancy
    domain = db.Column(db.String(255), nullable=False, index=True)

    # User tracking
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)  # Soft delete
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id])
    history = db.relationship('DecisionHistory', backref='decision_record', lazy=True, order_by='DecisionHistory.changed_at.desc()')
    infrastructure = db.relationship('ITInfrastructure', secondary=decision_infrastructure, backref=db.backref('decisions', lazy='dynamic'))

    # Valid status values
    VALID_STATUSES = ['proposed', 'accepted', 'deprecated', 'superseded']

    def get_display_id(self):
        """Get the display ID in format PREFIX-NNN (e.g., GYH-034)."""
        if self.decision_number is None:
            return None
        # Get tenant prefix from AuthConfig
        auth_config = AuthConfig.query.filter_by(domain=self.domain).first()
        if auth_config and auth_config.tenant_prefix:
            return f"{auth_config.tenant_prefix}-{self.decision_number:03d}"
        return f"ADR-{self.decision_number:03d}"  # Fallback format

    def to_dict(self):
        return {
            'id': self.id,
            'display_id': self.get_display_id(),
            'decision_number': self.decision_number,
            'title': self.title,
            'context': self.context,
            'decision': self.decision,
            'status': self.status,
            'consequences': self.consequences,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'domain': self.domain,
            'created_by': self.creator.to_dict() if self.creator else None,
            'updated_by': self.updated_by.to_dict() if self.updated_by else None,
            'infrastructure': [i.to_dict() for i in self.infrastructure] if self.infrastructure else [],
        }

    def to_dict_with_history(self):
        data = self.to_dict()
        data['history'] = [h.to_dict() for h in self.history]
        return data


class DecisionHistory(db.Model):
    """Table for tracking update history of Architecture Decisions."""

    __tablename__ = 'decision_history'

    id = db.Column(db.Integer, primary_key=True)
    decision_id = db.Column(db.Integer, db.ForeignKey('architecture_decisions.id'), nullable=False)

    # Snapshot of the decision at the time of change
    title = db.Column(db.String(255), nullable=False)
    context = db.Column(db.Text, nullable=False)
    decision_text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False)
    consequences = db.Column(db.Text, nullable=False)

    # Metadata about the change
    changed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    change_reason = db.Column(db.String(500), nullable=True)
    changed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    changed_by = db.relationship('User', foreign_keys=[changed_by_id])

    def to_dict(self):
        return {
            'id': self.id,
            'decision_id': self.decision_id,
            'title': self.title,
            'context': self.context,
            'decision': self.decision_text,
            'status': self.status,
            'consequences': self.consequences,
            'changed_at': self.changed_at.isoformat(),
            'change_reason': self.change_reason,
            'changed_by': self.changed_by.to_dict() if self.changed_by else None,
        }


class AccessRequest(db.Model):
    """Access requests for users wanting to join an existing tenant."""

    __tablename__ = 'access_requests'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    domain = db.Column(db.String(255), nullable=False, index=True)
    reason = db.Column(db.Text, nullable=True)  # Optional reason for requesting access
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Admin who processed the request
    processed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Relationships
    processed_by = db.relationship('User', foreign_keys=[processed_by_id])

    # Valid statuses
    VALID_STATUSES = ['pending', 'approved', 'rejected']

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'domain': self.domain,
            'reason': self.reason,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'processed_by': self.processed_by.to_dict() if self.processed_by else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'rejection_reason': self.rejection_reason,
        }


class SetupToken(db.Model):
    """Setup tokens for users to set up their credentials (passkey/password).

    Tokens are encrypted using Fernet symmetric encryption for security.
    The encrypted token contains the user_id and expiry timestamp.
    """

    __tablename__ = 'setup_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Nullable for pre-user tokens
    email = db.Column(db.String(320), nullable=True)  # For tokens created before user exists
    token_hash = db.Column(db.String(255), nullable=False, unique=True, index=True)  # Hash of the token for lookup
    purpose = db.Column(db.String(20), nullable=False, default='initial_setup')  # 'initial_setup', 'account_recovery', 'admin_invite'
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id])

    # Token validity
    TOKEN_VALIDITY_HOURS = 48  # Default for admin invites
    RECOVERY_VALIDITY_HOURS = 2  # Shorter for account recovery
    VERIFICATION_VALIDITY_HOURS = 2  # For email verification

    # Valid purposes
    PURPOSE_INITIAL_SETUP = 'initial_setup'
    PURPOSE_ACCOUNT_RECOVERY = 'account_recovery'
    PURPOSE_ADMIN_INVITE = 'admin_invite'
    VALID_PURPOSES = [PURPOSE_INITIAL_SETUP, PURPOSE_ACCOUNT_RECOVERY, PURPOSE_ADMIN_INVITE]

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def is_used(self):
        return self.used_at is not None

    def is_valid(self):
        return not self.is_expired() and not self.is_used()

    @staticmethod
    def _get_encryption_key():
        """Get or generate the encryption key for setup tokens."""
        import os
        import base64
        from hashlib import sha256

        # Use app secret key as base for encryption key
        secret = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
        # Derive a 32-byte key using SHA-256
        key_bytes = sha256(secret.encode()).digest()
        return base64.urlsafe_b64encode(key_bytes)

    @staticmethod
    def _encrypt_token_data(user_id: int, expires_at: datetime) -> str:
        """Encrypt user_id and expiry into a token string."""
        import json
        from cryptography.fernet import Fernet

        key = SetupToken._get_encryption_key()
        fernet = Fernet(key)

        payload = json.dumps({
            'user_id': user_id,
            'expires_at': expires_at.isoformat(),
            'created_at': datetime.utcnow().isoformat()
        })

        encrypted = fernet.encrypt(payload.encode())
        return encrypted.decode()

    @staticmethod
    def _decrypt_token_data(token: str) -> dict:
        """Decrypt token to get user_id and expiry."""
        import json
        from cryptography.fernet import Fernet, InvalidToken

        key = SetupToken._get_encryption_key()
        fernet = Fernet(key)

        try:
            decrypted = fernet.decrypt(token.encode())
            return json.loads(decrypted.decode())
        except (InvalidToken, json.JSONDecodeError):
            return None

    @staticmethod
    def _hash_token(token: str) -> str:
        """Create a hash of the token for secure storage and lookup."""
        from hashlib import sha256
        return sha256(token.encode()).hexdigest()

    @staticmethod
    def generate_token(user_id: int, expires_at: datetime) -> str:
        """Generate an encrypted secure token."""
        return SetupToken._encrypt_token_data(user_id, expires_at)

    @staticmethod
    def validate_token(token: str):
        """Validate a token and return the SetupToken record if valid."""
        # Decrypt the token to get payload
        payload = SetupToken._decrypt_token_data(token)
        if not payload:
            return None, 'Invalid token format'

        # Look up by hash
        token_hash = SetupToken._hash_token(token)
        setup_token = SetupToken.query.filter_by(token_hash=token_hash).first()

        if not setup_token:
            return None, 'Token not found or already invalidated'

        if setup_token.is_used():
            return None, 'Token has already been used'

        if setup_token.is_expired():
            return None, 'Token has expired'

        return setup_token, None

    @staticmethod
    def create_for_user(user, validity_hours=None, purpose=None):
        """Create a new setup token for a user."""
        from datetime import timedelta

        # Set default purpose
        if purpose is None:
            purpose = SetupToken.PURPOSE_INITIAL_SETUP

        # Set default validity based on purpose
        if validity_hours is None:
            if purpose == SetupToken.PURPOSE_ACCOUNT_RECOVERY:
                validity_hours = SetupToken.RECOVERY_VALIDITY_HOURS
            else:
                validity_hours = SetupToken.TOKEN_VALIDITY_HOURS

        # Invalidate any existing tokens for this user with the same purpose
        SetupToken.query.filter_by(user_id=user.id, purpose=purpose, used_at=None).update({
            'used_at': datetime.utcnow()
        })
        db.session.flush()

        expires_at = datetime.utcnow() + timedelta(hours=validity_hours)
        token_string = SetupToken.generate_token(user.id, expires_at)
        token_hash = SetupToken._hash_token(token_string)

        setup_token = SetupToken(
            user_id=user.id,
            email=user.email,
            token_hash=token_hash,
            purpose=purpose,
            expires_at=expires_at
        )
        db.session.add(setup_token)
        db.session.commit()

        # Return both the record and the actual token string
        # The token string is returned only once at creation time
        setup_token._token_string = token_string
        return setup_token

    def to_dict(self, include_token=False):
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'purpose': self.purpose,
            'expires_at': self.expires_at.isoformat(),
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'created_at': self.created_at.isoformat(),
            'is_valid': self.is_valid(),
            'hours_remaining': max(0, int((self.expires_at - datetime.utcnow()).total_seconds() / 3600)) if not self.is_expired() else 0,
        }
        # Only include actual token if explicitly requested (e.g., at creation time)
        if include_token and hasattr(self, '_token_string'):
            result['token'] = self._token_string
        return result


class EmailVerification(db.Model):
    """Email verification tokens for validating user email addresses."""

    __tablename__ = 'email_verifications'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=True)  # Store name for new signups
    token = db.Column(db.String(255), nullable=False, unique=True)
    purpose = db.Column(db.String(50), nullable=False, default='signup')  # 'signup', 'login', 'access_request'
    domain = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # For access requests, store the reason
    access_request_reason = db.Column(db.Text, nullable=True)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def is_verified(self):
        return self.verified_at is not None

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'purpose': self.purpose,
            'domain': self.domain,
            'expires_at': self.expires_at.isoformat(),
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'created_at': self.created_at.isoformat(),
        }


def save_history(decision, change_reason=None, changed_by=None):
    """Save the current state of a decision to history before updating."""
    history_entry = DecisionHistory(
        decision_id=decision.id,
        title=decision.title,
        context=decision.context,
        decision_text=decision.decision,
        status=decision.status,
        consequences=decision.consequences,
        change_reason=change_reason,
        changed_by_id=changed_by.id if changed_by else None
    )
    db.session.add(history_entry)
    return history_entry
