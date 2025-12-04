from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Default master account credentials
DEFAULT_MASTER_USERNAME = 'admin'
DEFAULT_MASTER_PASSWORD = 'changeme'


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
    """User model for authenticated users via SSO or WebAuthn."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=True)
    sso_subject = db.Column(db.String(255), nullable=True)  # Subject ID from SSO provider (null for local users)
    sso_domain = db.Column(db.String(255), nullable=False)  # Domain for multi-tenancy
    auth_type = db.Column(db.String(20), nullable=False, default='sso')  # 'sso' or 'webauthn'
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    decisions_created = db.relationship('ArchitectureDecision', backref='creator', lazy=True, foreign_keys='ArchitectureDecision.created_by_id')
    subscriptions = db.relationship('Subscription', backref='user', lazy=True, uselist=False)
    webauthn_credentials = db.relationship('WebAuthnCredential', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'sso_domain': self.sso_domain,
            'auth_type': self.auth_type,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'has_passkey': len(self.webauthn_credentials) > 0 if self.webauthn_credentials else False,
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
    auth_method = db.Column(db.String(20), nullable=False, default='webauthn')  # 'sso' or 'webauthn'
    allow_registration = db.Column(db.Boolean, default=True)  # Allow new user registration for webauthn
    rp_name = db.Column(db.String(255), nullable=False, default='Architecture Decisions')  # Relying Party name for WebAuthn
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'domain': self.domain,
            'auth_method': self.auth_method,
            'allow_registration': self.allow_registration,
            'rp_name': self.rp_name,
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
