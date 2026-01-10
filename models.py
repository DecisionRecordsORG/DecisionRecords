import os
import enum
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ============================================================================
# ENUMS for v1.5 Governance Model
# ============================================================================

class MaturityState(enum.Enum):
    """Tenant maturity states that control admin permissions."""
    BOOTSTRAP = 'bootstrap'  # Single admin, limited powers
    MATURE = 'mature'        # Full admin capabilities

class GlobalRole(enum.Enum):
    """User roles within a tenant."""
    USER = 'user'
    PROVISIONAL_ADMIN = 'provisional_admin'
    STEWARD = 'steward'
    ADMIN = 'admin'

class VisibilityPolicy(enum.Enum):
    """Space visibility policies."""
    TENANT_VISIBLE = 'tenant_visible'  # All tenant members see decisions
    SPACE_FOCUSED = 'space_focused'    # Default view scoped to space

class RequestStatus(enum.Enum):
    """Role request status."""
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class RequestedRole(enum.Enum):
    """Roles that can be requested."""
    STEWARD = 'steward'
    ADMIN = 'admin'


# ============================================================================
# ENUMS for AI/LLM Integration
# ============================================================================

class LLMProvider(enum.Enum):
    """Supported LLM providers for AI features."""
    NONE = 'none'
    OPENAI = 'openai'
    ANTHROPIC = 'anthropic'
    AZURE_OPENAI = 'azure_openai'
    CUSTOM = 'custom'


class AIChannel(enum.Enum):
    """Channels through which AI interactions occur."""
    SLACK = 'slack'
    MCP = 'mcp'
    API = 'api'
    WEB = 'web'


class AIAction(enum.Enum):
    """Types of AI actions for logging."""
    SEARCH = 'search'
    READ = 'read'
    CREATE = 'create'
    UPDATE = 'update'
    SUMMARIZE = 'summarize'


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
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Default configuration keys
    KEY_EMAIL_VERIFICATION_REQUIRED = 'email_verification_required'
    KEY_SUPER_ADMIN_EMAIL = 'super_admin_notification_email'
    KEY_SUPPORT_EMAIL = 'support_email'  # Email address for contact form submissions
    KEY_ADMIN_SESSION_TIMEOUT_HOURS = 'admin_session_timeout_hours'
    KEY_USER_SESSION_TIMEOUT_HOURS = 'user_session_timeout_hours'

    # Licensing configuration keys
    KEY_MAX_USERS_PER_TENANT = 'max_users_per_tenant'
    KEY_LICENSE_ACCEPTED = 'license_accepted'  # Whether BSL 1.1 license has been accepted
    KEY_LICENSE_ACCEPTED_BY = 'license_accepted_by'  # Email of who accepted
    KEY_LICENSE_ACCEPTED_AT = 'license_accepted_at'  # When license was accepted

    # Analytics configuration keys
    KEY_ANALYTICS_ENABLED = 'analytics_enabled'
    KEY_ANALYTICS_HOST = 'analytics_host'
    KEY_ANALYTICS_API_KEY = 'analytics_api_key'  # For self-hosted (fallback storage)
    KEY_ANALYTICS_PERSON_PROFILING = 'analytics_person_profiling'
    KEY_ANALYTICS_EVENT_MAPPINGS = 'analytics_event_mappings'
    KEY_ANALYTICS_EXCEPTION_CAPTURE = 'analytics_exception_capture'

    # Default values
    DEFAULT_ADMIN_SESSION_TIMEOUT = 1  # 1 hour for super admin
    DEFAULT_USER_SESSION_TIMEOUT = 8   # 8 hours for regular users
    DEFAULT_MAX_USERS_PER_TENANT = 5   # Free tier limit (0 = unlimited)
    DEFAULT_SUPPORT_EMAIL = 'admin@decisionrecords.org'  # Default support email

    # Analytics defaults
    DEFAULT_ANALYTICS_ENABLED = False  # OFF by default (opt-in)
    DEFAULT_ANALYTICS_HOST = 'https://eu.i.posthog.com'
    DEFAULT_ANALYTICS_PERSON_PROFILING = False  # Privacy-first
    DEFAULT_ANALYTICS_EXCEPTION_CAPTURE = False  # OFF by default

    # Cloudflare security configuration keys
    KEY_CLOUDFLARE_ORIGIN_CHECK_ENABLED = 'cloudflare_origin_check_enabled'
    KEY_CLOUDFLARE_ACCESS_ENABLED = 'cloudflare_access_enabled'
    KEY_CLOUDFLARE_ACCESS_TEAM_DOMAIN = 'cloudflare_access_team_domain'
    KEY_CLOUDFLARE_ACCESS_AUD = 'cloudflare_access_aud'
    KEY_CLOUDFLARE_ACCESS_PROTECTED_PATHS = 'cloudflare_access_protected_paths'

    # Cloudflare defaults
    DEFAULT_CLOUDFLARE_ORIGIN_CHECK_ENABLED = True  # ON by default - block direct IP access
    DEFAULT_CLOUDFLARE_ACCESS_ENABLED = False  # OFF by default until configured
    DEFAULT_CLOUDFLARE_ACCESS_PROTECTED_PATHS = '/superadmin,/superadmin/*'  # Comma-separated

    # Log forwarding configuration keys (OpenTelemetry/OTLP)
    KEY_LOG_FORWARDING_ENABLED = 'log_forwarding_enabled'
    KEY_LOG_FORWARDING_ENDPOINT_URL = 'log_forwarding_endpoint_url'
    KEY_LOG_FORWARDING_AUTH_TYPE = 'log_forwarding_auth_type'
    KEY_LOG_FORWARDING_AUTH_HEADER_NAME = 'log_forwarding_auth_header_name'
    KEY_LOG_FORWARDING_API_KEY = 'log_forwarding_api_key'  # Fallback storage (prefer Key Vault)
    KEY_LOG_FORWARDING_LOG_LEVEL = 'log_forwarding_log_level'
    KEY_LOG_FORWARDING_SERVICE_NAME = 'log_forwarding_service_name'
    KEY_LOG_FORWARDING_ENVIRONMENT = 'log_forwarding_environment'
    KEY_LOG_FORWARDING_CUSTOM_HEADERS = 'log_forwarding_custom_headers'

    # Log forwarding defaults
    DEFAULT_LOG_FORWARDING_ENABLED = False
    DEFAULT_LOG_FORWARDING_AUTH_TYPE = 'api_key'  # api_key, bearer, header, none
    DEFAULT_LOG_FORWARDING_LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
    DEFAULT_LOG_FORWARDING_SERVICE_NAME = 'architecture-decisions'
    DEFAULT_LOG_FORWARDING_ENVIRONMENT = 'production'

    # AI/LLM Integration configuration keys (Super Admin level)
    KEY_AI_FEATURES_ENABLED = 'ai_features_enabled'  # Master switch for all AI features
    KEY_AI_SLACK_BOT_ENABLED = 'ai_slack_bot_enabled'  # Slack natural language queries
    KEY_AI_MCP_SERVER_ENABLED = 'ai_mcp_server_enabled'  # MCP server for developer tools
    KEY_AI_EXTERNAL_API_ENABLED = 'ai_external_api_enabled'  # API for custom GPTs/agents
    KEY_AI_ASSISTED_CREATION_ENABLED = 'ai_assisted_creation_enabled'  # LLM-assisted decision creation
    KEY_AI_LLM_PROVIDER = 'ai_llm_provider'  # none, openai, anthropic, azure_openai, custom
    KEY_AI_LLM_MODEL = 'ai_llm_model'  # Model identifier (e.g., gpt-4o, claude-3-sonnet)
    KEY_AI_LLM_API_KEY_SECRET = 'ai_llm_api_key_secret'  # Key Vault secret name for LLM API key
    KEY_AI_LLM_ENDPOINT = 'ai_llm_endpoint'  # Custom endpoint URL (for Azure/custom providers)

    # AI/LLM defaults - all OFF by default (opt-in only)
    DEFAULT_AI_FEATURES_ENABLED = False
    DEFAULT_AI_SLACK_BOT_ENABLED = False
    DEFAULT_AI_MCP_SERVER_ENABLED = False
    DEFAULT_AI_EXTERNAL_API_ENABLED = False
    DEFAULT_AI_ASSISTED_CREATION_ENABLED = False
    DEFAULT_AI_LLM_PROVIDER = 'none'

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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
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


# ============================================================================
# v1.5 GOVERNANCE MODELS
# ============================================================================

class Tenant(db.Model):
    """
    Tenant represents an organization/domain in the multi-tenant system.

    Key invariants:
    - A Tenant is identified by domain, not by a user
    - A Tenant always has at least one default Space
    - No tenant is ever "owned" by a user
    """
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False, unique=True, index=True)
    name = db.Column(db.String(255), nullable=True)  # Display name (defaults to domain)
    status = db.Column(db.String(20), default='active')  # active, suspended
    maturity_state = db.Column(db.Enum(MaturityState), default=MaturityState.BOOTSTRAP)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Maturity thresholds (can be overridden by super admin)
    maturity_age_days = db.Column(db.Integer, default=14)
    maturity_user_threshold = db.Column(db.Integer, default=5)

    # Soft-delete fields for tenant deletion
    deleted_at = db.Column(db.DateTime, nullable=True)  # When tenant was soft-deleted
    deleted_by_admin = db.Column(db.String(255), nullable=True)  # Super admin who deleted (username or identifier)
    deletion_expires_at = db.Column(db.DateTime, nullable=True)  # When deletion becomes permanent (default: 30 days)

    # AI/LLM Integration settings (Tenant Admin level)
    # These only apply if Super Admin has enabled the corresponding feature globally
    ai_features_enabled = db.Column(db.Boolean, default=False)  # Master switch for tenant
    ai_slack_queries_enabled = db.Column(db.Boolean, default=False)  # Allow Slack AI queries
    ai_assisted_creation_enabled = db.Column(db.Boolean, default=False)  # Allow AI-assisted decision creation
    ai_external_access_enabled = db.Column(db.Boolean, default=False)  # Allow external AI API access
    ai_require_anonymization = db.Column(db.Boolean, default=True)  # Require PII anonymization before LLM
    ai_log_interactions = db.Column(db.Boolean, default=True)  # Log all AI interactions for audit

    # Relationships (defined after related models exist)
    # memberships - backref from TenantMembership
    # spaces - backref from Space
    # decisions - backref from ArchitectureDecision
    # settings - backref from TenantSettings

    def get_admin_count(self):
        """Count of full admins (not provisional)."""
        return TenantMembership.query.filter_by(
            tenant_id=self.id,
            global_role=GlobalRole.ADMIN
        ).count()

    def get_steward_count(self):
        """Count of stewards."""
        return TenantMembership.query.filter_by(
            tenant_id=self.id,
            global_role=GlobalRole.STEWARD
        ).count()

    def get_member_count(self):
        """Total member count."""
        return TenantMembership.query.filter_by(tenant_id=self.id).count()

    def compute_maturity_state(self):
        """
        Derive maturity state from current conditions.

        Exit conditions for MATURE (any one triggers):
        - 2+ ADMINs
        - 1 ADMIN + 1 STEWARD
        - User count >= threshold
        - Age >= threshold days
        """
        admin_count = self.get_admin_count()
        steward_count = self.get_steward_count()
        member_count = self.get_member_count()

        has_multi_admin = admin_count >= 2 or (admin_count >= 1 and steward_count >= 1)
        # Handle None thresholds (use defaults if not set)
        user_threshold = self.maturity_user_threshold if self.maturity_user_threshold is not None else 5
        age_days = self.maturity_age_days if self.maturity_age_days is not None else 90
        has_enough_users = member_count >= user_threshold
        # Use timezone-naive datetimes for comparison (SQLAlchemy returns naive from DB)
        created_at = self.created_at or datetime.now(timezone.utc).replace(tzinfo=None)
        is_old_enough = (datetime.now(timezone.utc).replace(tzinfo=None) - created_at).days >= age_days

        if has_multi_admin or has_enough_users or is_old_enough:
            return MaturityState.MATURE
        return MaturityState.BOOTSTRAP

    def update_maturity(self):
        """Update maturity state if conditions have changed. Returns True if changed."""
        new_state = self.compute_maturity_state()
        if new_state != self.maturity_state:
            self.maturity_state = new_state
            return True
        return False

    def is_mature(self):
        """Check if tenant has reached maturity."""
        return self.maturity_state == MaturityState.MATURE

    def to_dict(self):
        return {
            'id': self.id,
            'domain': self.domain,
            'name': self.name or self.domain,
            'status': self.status,
            'maturity_state': self.maturity_state.value,
            'created_at': self.created_at.isoformat(),
            'maturity_age_days': self.maturity_age_days,
            'maturity_user_threshold': self.maturity_user_threshold,
            'admin_count': self.get_admin_count(),
            'steward_count': self.get_steward_count(),
            'member_count': self.get_member_count(),
        }


class TenantMembership(db.Model):
    """
    Links users to tenants with their role.

    Key invariants:
    - A User may belong to only one Tenant per domain (enforced by unique constraint)
    - Role lives on membership, not on user
    - PROVISIONAL_ADMIN only allowed while tenant is in BOOTSTRAP state
    """
    __tablename__ = 'tenant_memberships'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    global_role = db.Column(db.Enum(GlobalRole), default=GlobalRole.USER)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Deletion rate limiting fields
    deletion_rate_limited_at = db.Column(db.DateTime, nullable=True)  # When user was rate-limited
    deletion_count_window_start = db.Column(db.DateTime, nullable=True)  # Start of rate limit window
    deletion_count = db.Column(db.Integer, default=0)  # Number of deletions in current window

    # AI/LLM preferences (User level)
    ai_opt_out = db.Column(db.Boolean, default=False)  # User can opt out of AI features

    # Relationships
    user = db.relationship('User', backref=db.backref('memberships', lazy='dynamic'))
    tenant = db.relationship('Tenant', backref=db.backref('memberships', lazy='dynamic'))

    # Constraints
    __table_args__ = (
        db.UniqueConstraint('user_id', 'tenant_id', name='unique_user_tenant'),
    )

    @property
    def is_admin(self):
        """Backward compatibility - any admin-level role."""
        return self.global_role in [
            GlobalRole.PROVISIONAL_ADMIN,
            GlobalRole.STEWARD,
            GlobalRole.ADMIN
        ]

    @property
    def is_full_admin(self):
        """Only full admin, not provisional."""
        return self.global_role == GlobalRole.ADMIN

    @property
    def can_change_tenant_settings(self):
        """Can modify tenant configuration (full admin only)."""
        return self.global_role == GlobalRole.ADMIN

    @property
    def can_approve_requests(self):
        """Can approve/reject access requests."""
        return self.global_role in [
            GlobalRole.PROVISIONAL_ADMIN,
            GlobalRole.STEWARD,
            GlobalRole.ADMIN
        ]

    @property
    def can_promote_to_steward(self):
        """Can promote users to steward role."""
        return self.global_role in [
            GlobalRole.PROVISIONAL_ADMIN,
            GlobalRole.STEWARD,
            GlobalRole.ADMIN
        ]

    @property
    def can_promote_to_admin(self):
        """Can promote users to admin role (admin only)."""
        return self.global_role == GlobalRole.ADMIN

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tenant_id': self.tenant_id,
            'global_role': self.global_role.value,
            'joined_at': self.joined_at.isoformat(),
            'is_admin': self.is_admin,
            'is_full_admin': self.is_full_admin,
        }


class TenantSettings(db.Model):
    """
    Tenant-specific settings. One-to-one with Tenant.
    Replaces AuthConfig for v1.5+.
    """
    __tablename__ = 'tenant_settings'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, unique=True)

    # Auth settings
    # auth_method values: 'local', 'sso', 'webauthn', 'slack_oidc'
    # - 'local': All enabled methods (password, passkey, Slack)
    # - 'sso': Only configured SSO providers
    # - 'webauthn': Passkeys only
    # - 'slack_oidc': Slack sign-in only (SSO alternative for Slack-first companies)
    auth_method = db.Column(db.String(20), default='local')
    allow_password = db.Column(db.Boolean, default=True)
    allow_passkey = db.Column(db.Boolean, default=True)
    allow_slack_oidc = db.Column(db.Boolean, default=True)  # Allow "Sign in with Slack"
    allow_google_oauth = db.Column(db.Boolean, default=True)  # Allow "Sign in with Google"
    rp_name = db.Column(db.String(255), default='Architecture Decisions')

    # Registration settings
    allow_registration = db.Column(db.Boolean, default=True)
    require_approval = db.Column(db.Boolean, default=False)

    # Display settings
    tenant_prefix = db.Column(db.String(3), unique=True, nullable=True)  # For decision IDs

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('settings', uselist=False))

    # NOTE: No 'delete tenant' setting - that's Super Admin only

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'auth_method': self.auth_method,
            'allow_password': self.allow_password,
            'allow_passkey': self.allow_passkey,
            'allow_slack_oidc': self.allow_slack_oidc,
            'allow_google_oauth': self.allow_google_oauth,
            'allow_registration': self.allow_registration,
            'require_approval': self.require_approval,
            'rp_name': self.rp_name,
            'tenant_prefix': self.tenant_prefix,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class Space(db.Model):
    """
    Organizational space within a tenant.

    Key invariants:
    - Every tenant has exactly one default space
    - Spaces organize, they don't isolate
    - Space deletion removes links, not decisions
    - Admins/Stewards can see ALL decisions regardless of space
    """
    __tablename__ = 'spaces'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_default = db.Column(db.Boolean, default=False)
    visibility_policy = db.Column(db.Enum(VisibilityPolicy), default=VisibilityPolicy.TENANT_VISIBLE)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('spaces', lazy='dynamic'))
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'description': self.description,
            'is_default': self.is_default,
            'visibility_policy': self.visibility_policy.value,
            'created_by_id': self.created_by_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DecisionSpace(db.Model):
    """
    Links decisions to spaces (many-to-many).

    Key invariants:
    - A decision can be in zero or more spaces
    - Removing from space doesn't delete the decision
    """
    __tablename__ = 'decision_spaces'

    id = db.Column(db.Integer, primary_key=True)
    decision_id = db.Column(db.Integer, db.ForeignKey('architecture_decisions.id'), nullable=False)
    space_id = db.Column(db.Integer, db.ForeignKey('spaces.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    added_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    space = db.relationship('Space', backref=db.backref('decision_links', lazy='dynamic', cascade='all, delete-orphan'))
    added_by = db.relationship('User', foreign_keys=[added_by_id])

    __table_args__ = (
        db.UniqueConstraint('decision_id', 'space_id', name='unique_decision_space'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'decision_id': self.decision_id,
            'space_id': self.space_id,
            'added_at': self.added_at.isoformat(),
            'added_by_id': self.added_by_id,
        }


class AuditLog(db.Model):
    """
    Immutable audit log for admin/steward actions.

    Key invariants:
    - Entries are immutable (no update/delete)
    - All admin/steward actions MUST generate entries
    """
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)
    target_entity = db.Column(db.String(50), nullable=True)  # 'user', 'tenant_settings', etc.
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships (read-only)
    tenant = db.relationship('Tenant', backref=db.backref('audit_logs', lazy='dynamic'))
    actor = db.relationship('User', foreign_keys=[actor_user_id])

    # Action type constants
    ACTION_PROMOTE_USER = 'promote_user'
    ACTION_DEMOTE_USER = 'demote_user'
    ACTION_CHANGE_SETTING = 'change_setting'
    ACTION_APPROVE_REQUEST = 'approve_request'
    ACTION_REJECT_REQUEST = 'reject_request'
    ACTION_CREATE_SPACE = 'create_space'
    ACTION_DELETE_SPACE = 'delete_space'
    ACTION_DELETE = 'delete'  # Generic delete action (for decisions, tenants, etc.)
    ACTION_ROLE_REQUESTED = 'role_requested'
    ACTION_MATURITY_CHANGE = 'maturity_change'
    ACTION_USER_JOINED = 'user_joined'
    ACTION_USER_LEFT = 'user_left'
    ACTION_ROLE_REQUEST_CREATED = 'role_request_created'
    ACTION_ROLE_REQUEST_APPROVED = 'role_request_approved'
    ACTION_ROLE_REQUEST_REJECTED = 'role_request_rejected'

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'actor_user_id': self.actor_user_id,
            'action_type': self.action_type,
            'target_entity': self.target_entity,
            'target_id': self.target_id,
            'details': self.details,
            'created_at': self.created_at.isoformat(),
        }


class LoginHistory(db.Model):
    """
    Tracks all login attempts across the system for security monitoring.

    Records both successful and failed login attempts with metadata
    for audit trail and security analysis.
    """
    __tablename__ = 'login_history'

    # Login method constants
    METHOD_PASSWORD = 'password'
    METHOD_WEBAUTHN = 'webauthn'
    METHOD_SSO = 'sso'
    METHOD_SLACK_OIDC = 'slack_oidc'
    METHOD_GOOGLE_OAUTH = 'google_oauth'
    METHOD_TEAMS_OIDC = 'teams_oidc'
    METHOD_MASTER = 'master'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    tenant_domain = db.Column(db.String(255), nullable=True, index=True)
    login_method = db.Column(db.String(20), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 can be up to 45 chars
    user_agent = db.Column(db.String(500), nullable=True)
    success = db.Column(db.Boolean, nullable=False, default=False)
    failure_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'tenant_domain': self.tenant_domain,
            'login_method': self.login_method,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'success': self.success,
            'failure_reason': self.failure_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


def log_login_attempt(email, login_method, success, user_id=None, tenant_domain=None,
                      ip_address=None, user_agent=None, failure_reason=None):
    """
    Log a login attempt to the LoginHistory table.

    Args:
        email: Email address used for login attempt
        login_method: One of LoginHistory.METHOD_* constants
        success: Whether the login was successful
        user_id: User ID if known (may be None for failed attempts)
        tenant_domain: Domain of the tenant (None for master account logins)
        ip_address: Client IP address
        user_agent: Client user agent string (truncated to 500 chars)
        failure_reason: Reason for failure if success=False

    Returns:
        The created LoginHistory entry
    """
    entry = LoginHistory(
        user_id=user_id,
        email=email,
        tenant_domain=tenant_domain,
        login_method=login_method,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        success=success,
        failure_reason=failure_reason
    )
    db.session.add(entry)
    db.session.commit()
    return entry


class User(db.Model):
    """User model for authenticated users via SSO, WebAuthn, or local password."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=True)  # Legacy field, use first_name + last_name
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)  # For local/password authentication
    sso_subject = db.Column(db.String(255), nullable=True)  # Subject ID from SSO provider (null for local users)
    sso_domain = db.Column(db.String(255), nullable=False)  # Domain for multi-tenancy
    auth_type = db.Column(db.String(20), nullable=False, default='local')  # 'sso', 'webauthn', or 'local'
    is_admin = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)  # Email verification status
    has_seen_admin_onboarding = db.Column(db.Boolean, default=False)  # Track if admin has seen the onboarding modal
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)

    # GDPR deletion fields
    deletion_requested_at = db.Column(db.DateTime, nullable=True)  # When user requested deletion
    deletion_scheduled_at = db.Column(db.DateTime, nullable=True)  # When deletion will execute (7 days after request)
    deleted_at = db.Column(db.DateTime, nullable=True)  # When account was actually deleted/anonymized
    is_anonymized = db.Column(db.Boolean, default=False)  # True if user data has been anonymized

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

    def get_full_name(self):
        """Get full name, preferring first_name + last_name over legacy name field."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.name or ''

    def set_name(self, first_name=None, last_name=None, full_name=None):
        """Set user's name. Prefer first_name/last_name, but handle legacy full_name too."""
        if first_name is not None or last_name is not None:
            self.first_name = first_name
            self.last_name = last_name
            # Also update legacy name field for backwards compatibility
            self.name = self.get_full_name()
        elif full_name:
            # Parse full name into first and last (best effort)
            parts = full_name.strip().split(None, 1)  # Split on first whitespace
            self.first_name = parts[0] if parts else ''
            self.last_name = parts[1] if len(parts) > 1 else ''
            self.name = full_name

    # v1.5 Membership helpers
    def get_membership(self, tenant_id=None):
        """Get user's membership for a tenant. If tenant_id not specified, uses sso_domain."""
        if tenant_id:
            return TenantMembership.query.filter_by(
                user_id=self.id,
                tenant_id=tenant_id
            ).first()
        # Fallback: look up tenant by domain then get membership
        tenant = Tenant.query.filter_by(domain=self.sso_domain).first()
        if tenant:
            return TenantMembership.query.filter_by(
                user_id=self.id,
                tenant_id=tenant.id
            ).first()
        return None

    def get_role(self, tenant_id=None):
        """Get user's role in a tenant."""
        membership = self.get_membership(tenant_id)
        return membership.global_role if membership else None

    def is_admin_of(self, tenant_id=None):
        """Check if user has admin privileges (any admin-level role) in tenant."""
        membership = self.get_membership(tenant_id)
        return membership.is_admin if membership else False

    def is_full_admin_of(self, tenant_id=None):
        """Check if user is a full admin (not provisional) in tenant."""
        membership = self.get_membership(tenant_id)
        return membership.is_full_admin if membership else False

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.get_full_name(),  # Use helper for consistent name formatting
            'first_name': self.first_name,
            'last_name': self.last_name,
            'sso_domain': self.sso_domain,
            'auth_type': self.auth_type,
            'is_admin': self.is_admin,
            'email_verified': self.email_verified,
            'has_seen_admin_onboarding': self.has_seen_admin_onboarding,
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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    # auth_method: 'local', 'sso', 'webauthn', 'slack_oidc'
    auth_method = db.Column(db.String(20), nullable=False, default='local')
    allow_password = db.Column(db.Boolean, default=True)  # Allow password login
    allow_passkey = db.Column(db.Boolean, default=True)  # Allow passkey/WebAuthn login
    allow_slack_oidc = db.Column(db.Boolean, default=True)  # Allow "Sign in with Slack" option
    allow_google_oauth = db.Column(db.Boolean, default=True)  # Allow "Sign in with Google" option
    allow_registration = db.Column(db.Boolean, default=True)  # Allow new user registration
    require_approval = db.Column(db.Boolean, default=False)  # Require admin approval for new users to join tenant (default: auto-approve)
    rp_name = db.Column(db.String(255), nullable=False, default='Architecture Decisions')  # Relying Party name for WebAuthn
    tenant_prefix = db.Column(db.String(3), unique=True, nullable=True)  # 3-letter prefix for decision IDs (consonants only)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
            'allow_slack_oidc': self.allow_slack_oidc,
            'allow_google_oauth': self.allow_google_oauth,
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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    db.Column('created_at', db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
)


class ITInfrastructure(db.Model):
    """IT Infrastructure items that architecture decisions can be mapped to."""

    __tablename__ = 'it_infrastructure'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # application, network, database, server, service, api, storage, cloud, container, other
    description = db.Column(db.Text, nullable=True)
    domain = db.Column(db.String(255), nullable=False, index=True)  # Multi-tenancy
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Multi-tenancy - v1.5 uses tenant_id FK, domain kept for backward compatibility during migration
    domain = db.Column(db.String(255), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)  # v1.5: FK to tenant (nullable during migration)

    # User tracking
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)  # Soft delete timestamp
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    deletion_expires_at = db.Column(db.DateTime, nullable=True)  # When soft-delete becomes permanent (default: 30 days)

    # Decision owner (the person who made the decision, may differ from creator)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    owner_email = db.Column(db.String(255), nullable=True)  # For external owners not in system

    # Relationships
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id])
    owner = db.relationship('User', foreign_keys=[owner_id])
    history = db.relationship('DecisionHistory', backref='decision_record', lazy=True, order_by='DecisionHistory.changed_at.desc()')
    infrastructure = db.relationship('ITInfrastructure', secondary=decision_infrastructure, backref=db.backref('decisions', lazy='dynamic'))
    # v1.5 relationships
    tenant = db.relationship('Tenant', backref=db.backref('decisions', lazy='dynamic'))
    space_links = db.relationship('DecisionSpace', backref='decision', lazy='dynamic', cascade='all, delete-orphan')

    # Valid status values
    VALID_STATUSES = ['proposed', 'accepted', 'archived', 'superseded']

    @property
    def spaces(self):
        """Get all spaces this decision belongs to."""
        return [link.space for link in self.space_links]

    def get_display_id(self):
        """Get the display ID in format PREFIX-NNN (e.g., GYH-034)."""
        if self.decision_number is None:
            return None
        # Get tenant prefix from AuthConfig
        auth_config = AuthConfig.query.filter_by(domain=self.domain).first()
        if auth_config and auth_config.tenant_prefix:
            return f"{auth_config.tenant_prefix}-{self.decision_number:03d}"
        return f"ADR-{self.decision_number:03d}"  # Fallback format

    def to_dict(self, include_spaces=False):
        result = {
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
            'tenant_id': self.tenant_id,  # v1.5
            'created_by': self.creator.to_dict() if self.creator else None,
            'updated_by': self.updated_by.to_dict() if self.updated_by else None,
            'owner': self.owner.to_dict() if self.owner else None,
            'owner_id': self.owner_id,
            'owner_email': self.owner_email,
            'infrastructure': [i.to_dict() for i in self.infrastructure] if self.infrastructure else [],
        }
        if include_spaces:
            result['spaces'] = [s.to_dict() for s in self.spaces]
        return result

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
    changed_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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


class RoleRequest(db.Model):
    """Role elevation requests from users wanting steward or admin privileges."""

    __tablename__ = 'role_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    requested_role = db.Column(db.Enum(RequestedRole), nullable=False)
    reason = db.Column(db.Text, nullable=True)  # Why they need this role
    status = db.Column(db.Enum(RequestStatus), nullable=False, default=RequestStatus.PENDING)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('role_requests', lazy='dynamic'))
    tenant = db.relationship('Tenant', backref=db.backref('role_requests', lazy='dynamic'))
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])

    # Constraints - one pending request per user per tenant
    __table_args__ = (
        db.Index('idx_user_tenant_status', 'user_id', 'tenant_id', 'status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user': self.user.to_dict() if self.user else None,
            'tenant_id': self.tenant_id,
            'requested_role': self.requested_role.value,
            'reason': self.reason,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'reviewed_by': self.reviewed_by.to_dict() if self.reviewed_by else None,
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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

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
        return datetime.now(timezone.utc).replace(tzinfo=None) > self.expires_at

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
            'created_at': datetime.now(timezone.utc).isoformat()
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
            'used_at': datetime.now(timezone.utc)
        })
        db.session.flush()

        expires_at = datetime.now(timezone.utc) + timedelta(hours=validity_hours)
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
            'hours_remaining': max(0, int((self.expires_at - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() / 3600)) if not self.is_expired() else 0,
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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # For access requests, store the reason
    access_request_reason = db.Column(db.Text, nullable=True)

    def is_expired(self):
        return datetime.now(timezone.utc).replace(tzinfo=None) > self.expires_at

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


# ============================================================================
# SLACK INTEGRATION MODELS
# ============================================================================

class SlackWorkspace(db.Model):
    """Slack workspace installation for a tenant."""

    __tablename__ = 'slack_workspaces'

    # Status values
    STATUS_PENDING_CLAIM = 'pending_claim'
    STATUS_ACTIVE = 'active'
    STATUS_DISCONNECTED = 'disconnected'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, unique=True, index=True)
    workspace_id = db.Column(db.String(50), nullable=False, unique=True, index=True)  # Slack team_id
    workspace_name = db.Column(db.String(255), nullable=True)

    # Encrypted bot token (xoxb-...)
    bot_token_encrypted = db.Column(db.Text, nullable=False)

    # Claim tracking
    status = db.Column(db.String(20), default=STATUS_PENDING_CLAIM)
    claimed_at = db.Column(db.DateTime, nullable=True)
    claimed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Notification settings
    default_channel_id = db.Column(db.String(50), nullable=True)
    default_channel_name = db.Column(db.String(255), nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True)
    notify_on_create = db.Column(db.Boolean, default=True)
    notify_on_status_change = db.Column(db.Boolean, default=True)

    # Status
    is_active = db.Column(db.Boolean, default=True)
    installed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity_at = db.Column(db.DateTime, nullable=True)

    # App version tracking (for upgrade management)
    granted_scopes = db.Column(db.Text, nullable=True)  # Comma-separated list of granted OAuth scopes
    scopes_updated_at = db.Column(db.DateTime, nullable=True)  # When scopes were last updated
    app_version = db.Column(db.String(20), nullable=True)  # Version at time of install/upgrade

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('slack_workspace', uselist=False))
    claimed_by = db.relationship('User', foreign_keys=[claimed_by_id])
    user_mappings = db.relationship('SlackUserMapping', backref='workspace', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, include_upgrade_info=False):
        result = {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'workspace_id': self.workspace_id,
            'workspace_name': self.workspace_name,
            'status': self.status,
            'claimed_at': self.claimed_at.isoformat() if self.claimed_at else None,
            'default_channel_id': self.default_channel_id,
            'default_channel_name': self.default_channel_name,
            'notifications_enabled': self.notifications_enabled,
            'notify_on_create': self.notify_on_create,
            'notify_on_status_change': self.notify_on_status_change,
            'is_active': self.is_active,
            'installed_at': self.installed_at.isoformat() if self.installed_at else None,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None,
            'app_version': self.app_version,
            'granted_scopes': self.granted_scopes.split(',') if self.granted_scopes else [],
        }

        if include_upgrade_info:
            from slack_upgrade import get_upgrade_info, get_workspace_scopes
            scopes = get_workspace_scopes(self)
            result['upgrade_info'] = get_upgrade_info(scopes)

        return result


class SlackUserMapping(db.Model):
    """Maps Slack users to ADR platform users."""

    __tablename__ = 'slack_user_mappings'

    id = db.Column(db.Integer, primary_key=True)
    slack_workspace_id = db.Column(db.Integer, db.ForeignKey('slack_workspaces.id'), nullable=False, index=True)
    slack_user_id = db.Column(db.String(50), nullable=False, index=True)  # Slack user ID (U...)
    slack_email = db.Column(db.String(320), nullable=True)  # Email from Slack profile

    # Linked ADR user (nullable - may not be linked yet)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # How the user was linked
    link_method = db.Column(db.String(20), nullable=True)  # 'auto_email', 'browser_auth'

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    linked_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('slack_mappings', lazy='dynamic'))

    # Unique constraint: one mapping per slack user per workspace
    __table_args__ = (
        db.UniqueConstraint('slack_workspace_id', 'slack_user_id', name='uq_slack_user_workspace'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'slack_workspace_id': self.slack_workspace_id,
            'slack_user_id': self.slack_user_id,
            'slack_email': self.slack_email,
            'user_id': self.user_id,
            'link_method': self.link_method,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'linked_at': self.linked_at.isoformat() if self.linked_at else None,
        }


# ============================================================================
# MICROSOFT TEAMS INTEGRATION MODELS
# ============================================================================

class TeamsWorkspace(db.Model):
    """Microsoft Teams workspace (tenant) installation for a Decision Records tenant."""

    __tablename__ = 'teams_workspaces'

    # Status values
    STATUS_PENDING_CONSENT = 'pending_consent'
    STATUS_ACTIVE = 'active'
    STATUS_DISCONNECTED = 'disconnected'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, unique=True, index=True)

    # Azure AD / Microsoft 365 tenant info
    ms_tenant_id = db.Column(db.String(50), nullable=False, unique=True, index=True)  # Azure AD tenant ID (GUID)
    ms_tenant_name = db.Column(db.String(255), nullable=True)  # Display name

    # Service URL for proactive messaging (varies by region)
    service_url = db.Column(db.String(500), nullable=True)  # e.g., https://smba.trafficmanager.net/amer/

    # Bot installation info
    bot_id = db.Column(db.String(100), nullable=True)  # Bot's Azure AD app ID

    # Status tracking
    status = db.Column(db.String(20), default=STATUS_PENDING_CONSENT)
    consent_granted_at = db.Column(db.DateTime, nullable=True)
    consent_granted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Notification settings
    default_channel_id = db.Column(db.String(100), nullable=True)  # Teams channel ID
    default_channel_name = db.Column(db.String(255), nullable=True)
    default_team_id = db.Column(db.String(100), nullable=True)  # Parent team ID
    default_team_name = db.Column(db.String(255), nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True)
    notify_on_create = db.Column(db.Boolean, default=True)
    notify_on_status_change = db.Column(db.Boolean, default=True)

    # State
    is_active = db.Column(db.Boolean, default=True)
    installed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity_at = db.Column(db.DateTime, nullable=True)

    # App version tracking
    app_version = db.Column(db.String(20), nullable=True)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('teams_workspace', uselist=False))
    consent_granted_by = db.relationship('User', foreign_keys=[consent_granted_by_id])
    user_mappings = db.relationship('TeamsUserMapping', backref='workspace', lazy='dynamic', cascade='all, delete-orphan')
    conversation_references = db.relationship('TeamsConversationReference', backref='workspace', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'ms_tenant_id': self.ms_tenant_id,
            'ms_tenant_name': self.ms_tenant_name,
            'status': self.status,
            'consent_granted_at': self.consent_granted_at.isoformat() if self.consent_granted_at else None,
            'default_channel_id': self.default_channel_id,
            'default_channel_name': self.default_channel_name,
            'default_team_id': self.default_team_id,
            'default_team_name': self.default_team_name,
            'notifications_enabled': self.notifications_enabled,
            'notify_on_create': self.notify_on_create,
            'notify_on_status_change': self.notify_on_status_change,
            'is_active': self.is_active,
            'installed_at': self.installed_at.isoformat() if self.installed_at else None,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None,
            'app_version': self.app_version,
        }


class TeamsUserMapping(db.Model):
    """Maps Teams users to Decision Records platform users."""

    __tablename__ = 'teams_user_mappings'

    id = db.Column(db.Integer, primary_key=True)
    teams_workspace_id = db.Column(db.Integer, db.ForeignKey('teams_workspaces.id'), nullable=False, index=True)

    # Azure AD user identifiers
    aad_object_id = db.Column(db.String(50), nullable=False, index=True)  # Azure AD user object ID (GUID)
    aad_user_principal_name = db.Column(db.String(320), nullable=True)  # UPN (often email)
    aad_email = db.Column(db.String(320), nullable=True)  # Email from Graph profile
    aad_display_name = db.Column(db.String(255), nullable=True)

    # Linked Decision Records user (nullable - may not be linked yet)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # How the user was linked
    link_method = db.Column(db.String(20), nullable=True)  # 'auto_email', 'auto_upn', 'browser_auth'

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    linked_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('teams_mappings', lazy='dynamic'))

    # Unique constraint: one mapping per Teams user per workspace
    __table_args__ = (
        db.UniqueConstraint('teams_workspace_id', 'aad_object_id', name='uq_teams_user_workspace'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'teams_workspace_id': self.teams_workspace_id,
            'aad_object_id': self.aad_object_id,
            'aad_user_principal_name': self.aad_user_principal_name,
            'aad_email': self.aad_email,
            'aad_display_name': self.aad_display_name,
            'user_id': self.user_id,
            'link_method': self.link_method,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'linked_at': self.linked_at.isoformat() if self.linked_at else None,
        }


class TeamsConversationReference(db.Model):
    """Stores conversation references for proactive messaging to Teams channels."""

    __tablename__ = 'teams_conversation_references'

    id = db.Column(db.Integer, primary_key=True)
    teams_workspace_id = db.Column(db.Integer, db.ForeignKey('teams_workspaces.id'), nullable=False, index=True)

    # Conversation identifiers
    conversation_id = db.Column(db.String(500), nullable=False)  # Teams conversation ID
    channel_id = db.Column(db.String(100), nullable=True)  # Channel ID if in a channel
    team_id = db.Column(db.String(100), nullable=True)  # Team ID if in a team

    # Serialized ConversationReference object (JSON)
    # Contains: activityId, user, bot, conversation, channelId, serviceUrl
    reference_json = db.Column(db.Text, nullable=False)

    # Context type
    context_type = db.Column(db.String(20), nullable=False)  # 'channel', 'personal', 'group'

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Unique constraint: one reference per conversation per workspace
    __table_args__ = (
        db.UniqueConstraint('teams_workspace_id', 'conversation_id', name='uq_teams_conversation'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'teams_workspace_id': self.teams_workspace_id,
            'conversation_id': self.conversation_id,
            'channel_id': self.channel_id,
            'team_id': self.team_id,
            'context_type': self.context_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class BlogPost(db.Model):
    """Blog posts for the marketing website."""

    __tablename__ = 'blog_posts'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), nullable=False, unique=True, index=True)  # URL-friendly slug
    title = db.Column(db.String(500), nullable=False)
    excerpt = db.Column(db.Text, nullable=False)  # Short description for list view
    author = db.Column(db.String(255), nullable=False, default='Decision Records')
    category = db.Column(db.String(100), nullable=False)  # Documentation, Startups, Enterprise, etc.
    read_time = db.Column(db.String(50), nullable=False, default='5 min read')
    image = db.Column(db.String(500), nullable=True)  # Path to hero/thumbnail image
    meta_description = db.Column(db.String(300), nullable=True)  # SEO meta description
    meta_keywords = db.Column(db.String(500), nullable=True)  # SEO keywords (comma-separated)
    published = db.Column(db.Boolean, default=True)  # Whether post is visible
    featured = db.Column(db.Boolean, default=False)  # Featured posts appear first
    publish_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))  # When to show as published
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Content is stored in Angular component, not DB (for now)
    # This model manages metadata only

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'title': self.title,
            'excerpt': self.excerpt,
            'author': self.author,
            'category': self.category,
            'readTime': self.read_time,
            'image': self.image,
            'metaDescription': self.meta_description,
            'metaKeywords': self.meta_keywords,
            'published': self.published,
            'featured': self.featured,
            'publishDate': self.publish_date.strftime('%B %Y') if self.publish_date else None,
            'publishDateISO': self.publish_date.isoformat() if self.publish_date else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }


# ============================================================================
# AI/LLM INTEGRATION MODELS
# ============================================================================

class AIApiKey(db.Model):
    """
    API keys for external AI tools to access decision records.

    Key security features:
    - Key is hashed (SHA256), only prefix stored for identification
    - Keys shown once on creation, never retrievable
    - Scoped to specific permissions (read, search, create)
    - Automatic expiration support
    - Immediate revocation capability
    """
    __tablename__ = 'ai_api_keys'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    # Key identification (the actual key is never stored, only its hash)
    key_hash = db.Column(db.String(64), nullable=False, unique=True)  # SHA256 hash
    key_prefix = db.Column(db.String(8), nullable=False)  # First 8 chars for display (e.g., "dr_abc12")

    # Metadata
    name = db.Column(db.String(100), nullable=False)  # User-provided name for the key
    description = db.Column(db.String(500), nullable=True)  # Optional description

    # Permissions (JSON array of scopes)
    # Valid scopes: read, search, create, update
    scopes = db.Column(db.JSON, default=lambda: ['read', 'search'])

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)  # None = never expires
    revoked_at = db.Column(db.DateTime, nullable=True)  # Set when key is revoked

    # Relationships
    user = db.relationship('User', backref=db.backref('ai_api_keys', lazy='dynamic'))
    tenant = db.relationship('Tenant', backref=db.backref('ai_api_keys', lazy='dynamic'))

    # Indexes for faster lookups
    __table_args__ = (
        db.Index('idx_ai_api_key_hash', 'key_hash'),
        db.Index('idx_ai_api_key_user', 'user_id'),
        db.Index('idx_ai_api_key_tenant', 'tenant_id'),
    )

    @property
    def is_valid(self):
        """Check if key is currently valid (not expired, not revoked)."""
        if self.revoked_at:
            return False
        if self.expires_at and datetime.now(timezone.utc).replace(tzinfo=None) > self.expires_at:
            return False
        return True

    @property
    def display_key(self):
        """Display-safe key representation (prefix + masked)."""
        return f"{self.key_prefix}..."

    def has_scope(self, scope):
        """Check if key has a specific scope."""
        return scope in (self.scopes or [])

    def update_last_used(self):
        """Update the last_used_at timestamp."""
        self.last_used_at = datetime.now(timezone.utc)

    def revoke(self):
        """Revoke this API key."""
        self.revoked_at = datetime.now(timezone.utc)

    def to_dict(self, include_sensitive=False):
        """Serialize to dictionary."""
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'key_prefix': self.key_prefix,
            'display_key': self.display_key,
            'scopes': self.scopes,
            'is_valid': self.is_valid,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
        }
        if include_sensitive:
            data['user_id'] = self.user_id
            data['tenant_id'] = self.tenant_id
        return data


class AIInteractionLog(db.Model):
    """
    Audit log for all AI interactions with the platform.

    Captures:
    - Who initiated the interaction (user, tenant)
    - What channel was used (Slack, MCP, API, Web)
    - What action was performed (search, read, create, etc.)
    - What data was accessed (decision IDs)
    - LLM usage metrics (provider, model, tokens)
    """
    __tablename__ = 'ai_interaction_logs'

    id = db.Column(db.Integer, primary_key=True)

    # Who
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Null for anonymous/API-only
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    api_key_id = db.Column(db.Integer, db.ForeignKey('ai_api_keys.id'), nullable=True)  # If via API key

    # What channel
    channel = db.Column(db.Enum(AIChannel), nullable=False)

    # What action
    action = db.Column(db.Enum(AIAction), nullable=False)

    # Query/request details (anonymized if configured)
    query_text = db.Column(db.Text, nullable=True)  # The search query or request (may be anonymized)
    query_anonymized = db.Column(db.Boolean, default=False)  # Whether query was anonymized before logging

    # What was accessed
    decision_ids = db.Column(db.JSON, nullable=True)  # Array of decision IDs accessed
    decision_count = db.Column(db.Integer, default=0)  # Number of decisions in response

    # LLM usage (if applicable)
    llm_provider = db.Column(db.String(50), nullable=True)
    llm_model = db.Column(db.String(100), nullable=True)
    tokens_input = db.Column(db.Integer, nullable=True)
    tokens_output = db.Column(db.Integer, nullable=True)

    # Performance
    duration_ms = db.Column(db.Integer, nullable=True)  # Request duration in milliseconds

    # Result
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.String(500), nullable=True)  # If success=False

    # Timestamp
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', backref=db.backref('ai_interactions', lazy='dynamic'))
    tenant = db.relationship('Tenant', backref=db.backref('ai_interactions', lazy='dynamic'))
    api_key = db.relationship('AIApiKey', backref=db.backref('interactions', lazy='dynamic'))

    # Indexes for analytics queries
    __table_args__ = (
        db.Index('idx_ai_log_tenant_created', 'tenant_id', 'created_at'),
        db.Index('idx_ai_log_user_created', 'user_id', 'created_at'),
        db.Index('idx_ai_log_channel', 'channel'),
        db.Index('idx_ai_log_action', 'action'),
    )

    def to_dict(self):
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tenant_id': self.tenant_id,
            'channel': self.channel.value if self.channel else None,
            'action': self.action.value if self.action else None,
            'query_text': self.query_text,
            'query_anonymized': self.query_anonymized,
            'decision_ids': self.decision_ids,
            'decision_count': self.decision_count,
            'llm_provider': self.llm_provider,
            'llm_model': self.llm_model,
            'tokens_input': self.tokens_input,
            'tokens_output': self.tokens_output,
            'duration_ms': self.duration_ms,
            'success': self.success,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
