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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Common public email domains that should be auto-rejected or require careful review
    PUBLIC_DOMAINS = [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com',
        'aol.com', 'icloud.com', 'mail.com', 'protonmail.com', 'proton.me',
        'ymail.com', 'gmx.com', 'zoho.com', 'tutanota.com', 'fastmail.com',
        'msn.com', 'me.com', 'mac.com', 'inbox.com', 'mail.ru'
    ]

    @staticmethod
    def is_public_domain(domain):
        """Check if domain is a common public email provider."""
        return domain.lower() in DomainApproval.PUBLIC_DOMAINS

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
            'rejection_reason': self.rejection_reason,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
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

    def to_dict(self):
        return {
            'id': self.id,
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
