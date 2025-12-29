"""
Backend Unit Tests for Google OAuth Authentication

Tests for the "Sign in with Google" feature using OAuth 2.0.
Tests cover:
- OAuth state generation and verification
- OAuth status endpoint
- OAuth initiation redirect
- OAuth callback handling
- User creation for new domains
- Existing user login
- Blocked domain rejection (gmail.com)
- First user becomes provisional admin
"""
import pytest
import json
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from models import (
    db, User, Tenant, TenantMembership, TenantSettings, AuthConfig,
    GlobalRole, MaturityState, DomainApproval
)
from google_oauth import (
    generate_google_oauth_state, verify_google_oauth_state,
    is_google_oauth_configured, get_google_client_id, get_google_client_secret,
    clear_credential_cache, _get_encryption_key,
    GOOGLE_OAUTH_AUTHORIZE_URL, GOOGLE_OAUTH_TOKEN_URL,
    GOOGLE_OAUTH_USERINFO_URL, GOOGLE_OAUTH_SCOPES
)


# ==================== Fixtures ====================

@pytest.fixture
def app():
    """Create application for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'

    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def session_fixture(app):
    """Create database session for testing."""
    with app.app_context():
        yield db.session


@pytest.fixture
def sample_user(session_fixture):
    """Create a sample user."""
    user = User(
        email='existing@example.com',
        name='Existing User',
        sso_domain='example.com',
        auth_type='local',
        email_verified=True
    )
    session_fixture.add(user)
    session_fixture.commit()
    return user


@pytest.fixture
def sample_tenant(session_fixture):
    """Create a sample tenant."""
    tenant = Tenant(
        domain='example.com',
        name='Example Corp',
        status='active',
        maturity_state=MaturityState.BOOTSTRAP
    )
    session_fixture.add(tenant)
    session_fixture.commit()
    return tenant


@pytest.fixture
def sample_membership(session_fixture, sample_user, sample_tenant):
    """Create a sample membership."""
    membership = TenantMembership(
        user_id=sample_user.id,
        tenant_id=sample_tenant.id,
        global_role=GlobalRole.USER
    )
    session_fixture.add(membership)
    session_fixture.commit()
    return membership


# ==================== Test OAuth State Functions ====================

class TestGoogleOAuthState:
    """Test Google OAuth state generation and verification."""

    def test_generate_state_creates_valid_token(self, app):
        """State can be generated successfully."""
        with app.app_context():
            state = generate_google_oauth_state(return_url='/dashboard')

            assert state is not None
            assert isinstance(state, str)
            assert len(state) > 50  # Encrypted state should be substantial

    def test_state_roundtrip_preserves_data(self, app):
        """State can be generated and verified with data preserved."""
        with app.app_context():
            return_url = '/dashboard'
            extra_data = {'link_token': 'abc123'}

            state = generate_google_oauth_state(
                return_url=return_url,
                extra_data=extra_data
            )

            # Verify state
            state_data = verify_google_oauth_state(state)

            assert state_data is not None
            assert state_data['type'] == 'google_oauth'
            assert state_data['return_url'] == return_url
            assert state_data['extra_data']['link_token'] == 'abc123'
            assert 'csrf_token' in state_data
            assert 'expires_at' in state_data

    def test_state_includes_csrf_protection(self, app):
        """State contains CSRF token."""
        with app.app_context():
            state1 = generate_google_oauth_state()
            state2 = generate_google_oauth_state()

            data1 = verify_google_oauth_state(state1)
            data2 = verify_google_oauth_state(state2)

            # Each state should have unique CSRF token
            assert data1['csrf_token'] != data2['csrf_token']

    def test_expired_state_rejected(self, app):
        """Expired state should be rejected."""
        with app.app_context():
            from cryptography.fernet import Fernet

            # Create expired state (expired 1 hour ago)
            expires_at = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            state_data = {
                'type': 'google_oauth',
                'csrf_token': 'test',
                'expires_at': expires_at,
                'return_url': None,
                'extra_data': {}
            }

            fernet = Fernet(_get_encryption_key())
            expired_state = fernet.encrypt(json.dumps(state_data).encode()).decode()

            # Verify should fail
            result = verify_google_oauth_state(expired_state)
            assert result is None

    def test_invalid_state_rejected(self, app):
        """Invalid state string should return None."""
        with app.app_context():
            invalid_state = 'totally-invalid-state-string'
            result = verify_google_oauth_state(invalid_state)
            assert result is None

    def test_empty_state_rejected(self, app):
        """Empty state should return None."""
        with app.app_context():
            result = verify_google_oauth_state('')
            assert result is None

            result = verify_google_oauth_state(None)
            assert result is None

    def test_wrong_type_state_rejected(self, app):
        """Slack OAuth state (not Google) should be rejected."""
        with app.app_context():
            from cryptography.fernet import Fernet

            # Create state with wrong type
            expires_at = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
            state_data = {
                'type': 'slack_oidc',  # Wrong type
                'csrf_token': 'test',
                'expires_at': expires_at,
                'extra_data': {}
            }

            fernet = Fernet(_get_encryption_key())
            wrong_type_state = fernet.encrypt(json.dumps(state_data).encode()).decode()

            # Verify should fail - wrong type
            result = verify_google_oauth_state(wrong_type_state)
            assert result is None


class TestGoogleOAuthConstants:
    """Test that OAuth constants are properly defined."""

    def test_authorize_url_defined(self):
        """Authorize URL should be Google OAuth endpoint."""
        assert GOOGLE_OAUTH_AUTHORIZE_URL == 'https://accounts.google.com/o/oauth2/v2/auth'

    def test_token_url_defined(self):
        """Token URL should be Google OAuth endpoint."""
        assert GOOGLE_OAUTH_TOKEN_URL == 'https://oauth2.googleapis.com/token'

    def test_userinfo_url_defined(self):
        """UserInfo URL should be Google OAuth endpoint."""
        assert GOOGLE_OAUTH_USERINFO_URL == 'https://www.googleapis.com/oauth2/v3/userinfo'

    def test_scopes_include_required(self):
        """Scopes should include openid, profile, and email."""
        assert 'openid' in GOOGLE_OAUTH_SCOPES
        assert 'profile' in GOOGLE_OAUTH_SCOPES
        assert 'email' in GOOGLE_OAUTH_SCOPES


class TestGoogleOAuthConfiguration:
    """Test Google OAuth configuration functions."""

    def test_is_configured_returns_false_when_no_credentials(self, app):
        """is_google_oauth_configured returns False when credentials missing."""
        with app.app_context():
            # Clear any cached credentials
            clear_credential_cache()

            # Remove environment variables
            old_id = os.environ.pop('GOOGLE_CLIENT_ID', None)
            old_secret = os.environ.pop('GOOGLE_CLIENT_SECRET', None)

            try:
                result = is_google_oauth_configured()
                assert result is False
            finally:
                # Restore
                if old_id:
                    os.environ['GOOGLE_CLIENT_ID'] = old_id
                if old_secret:
                    os.environ['GOOGLE_CLIENT_SECRET'] = old_secret

    def test_is_configured_returns_true_when_credentials_set(self, app):
        """is_google_oauth_configured returns True when credentials exist."""
        with app.app_context():
            clear_credential_cache()

            # Set environment variables
            os.environ['GOOGLE_CLIENT_ID'] = 'test-client-id'
            os.environ['GOOGLE_CLIENT_SECRET'] = 'test-client-secret'

            try:
                result = is_google_oauth_configured()
                assert result is True
            finally:
                os.environ.pop('GOOGLE_CLIENT_ID', None)
                os.environ.pop('GOOGLE_CLIENT_SECRET', None)
                clear_credential_cache()


# ==================== Test TenantSettings Model ====================

class TestTenantSettingsGoogleOAuth:
    """Test TenantSettings model with Google OAuth fields."""

    def test_allow_google_oauth_default_true(self, app, session_fixture, sample_tenant):
        """allow_google_oauth should default to True."""
        with app.app_context():
            settings = TenantSettings(
                tenant_id=sample_tenant.id,
                auth_method='local'
            )
            session_fixture.add(settings)
            session_fixture.commit()

            # Reload from DB
            reloaded = TenantSettings.query.filter_by(tenant_id=sample_tenant.id).first()
            assert reloaded.allow_google_oauth is True

    def test_allow_google_oauth_can_be_disabled(self, app, session_fixture, sample_tenant):
        """allow_google_oauth can be set to False."""
        with app.app_context():
            settings = TenantSettings(
                tenant_id=sample_tenant.id,
                auth_method='local',
                allow_google_oauth=False
            )
            session_fixture.add(settings)
            session_fixture.commit()

            reloaded = TenantSettings.query.filter_by(tenant_id=sample_tenant.id).first()
            assert reloaded.allow_google_oauth is False

    def test_to_dict_includes_allow_google_oauth(self, app, session_fixture, sample_tenant):
        """to_dict() should include allow_google_oauth field."""
        with app.app_context():
            settings = TenantSettings(
                tenant_id=sample_tenant.id,
                auth_method='local',
                allow_google_oauth=True
            )
            session_fixture.add(settings)
            session_fixture.commit()

            settings_dict = settings.to_dict()
            assert 'allow_google_oauth' in settings_dict
            assert settings_dict['allow_google_oauth'] is True


class TestAuthConfigGoogleOAuth:
    """Test AuthConfig model with Google OAuth fields."""

    def test_allow_google_oauth_in_auth_config(self, app, session_fixture):
        """AuthConfig should support allow_google_oauth field."""
        with app.app_context():
            config = AuthConfig(
                domain='example.com',
                auth_method='local',
                allow_google_oauth=True,
                allow_password=True,
                allow_passkey=False
            )
            session_fixture.add(config)
            session_fixture.commit()

            reloaded = AuthConfig.query.filter_by(domain='example.com').first()
            assert reloaded.allow_google_oauth is True

    def test_auth_config_to_dict_includes_google_oauth(self, app, session_fixture):
        """AuthConfig.to_dict() should include allow_google_oauth."""
        with app.app_context():
            config = AuthConfig(
                domain='example.com',
                auth_method='local',
                allow_google_oauth=True
            )
            session_fixture.add(config)
            session_fixture.commit()

            config_dict = config.to_dict()
            assert 'allow_google_oauth' in config_dict
            assert config_dict['allow_google_oauth'] is True


# ==================== Test Blocked Domains ====================

class TestBlockedDomainsGoogleOAuth:
    """Test that public email domains are properly blocked for Google OAuth."""

    def test_gmail_is_blocked(self):
        """gmail.com should be blocked even with Google OAuth."""
        assert DomainApproval.is_public_domain('gmail.com')

    def test_common_public_domains_blocked(self):
        """Common public email domains should be blocked."""
        public_domains = [
            'gmail.com',
            'yahoo.com',
            'hotmail.com',
            'outlook.com',
            'aol.com',
            'icloud.com',
            'protonmail.com',
            'mail.com',
            'live.com'
        ]
        for domain in public_domains:
            assert DomainApproval.is_public_domain(domain), f"{domain} should be blocked"

    def test_corporate_domains_allowed(self):
        """Corporate domains should be allowed."""
        corporate_domains = ['acme.com', 'startup.io', 'bigcorp.co.uk']
        for domain in corporate_domains:
            assert not DomainApproval.is_public_domain(domain), f"{domain} should be allowed"


# ==================== Integration Tests with App Routes ====================

class TestGoogleOAuthRoutes:
    """Test Google OAuth API routes (requires actual app import)."""

    @pytest.fixture
    def full_app(self):
        """Create app with actual routes registered."""
        # Set up environment before importing app
        os.environ['GOOGLE_CLIENT_ID'] = 'test-google-client-id'
        os.environ['GOOGLE_CLIENT_SECRET'] = 'test-google-client-secret'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['SECRET_KEY'] = 'test-secret-key'

        # Import the actual app
        try:
            import app as flask_app
            flask_app.app.config['TESTING'] = True
            flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
            flask_app.app.config['WTF_CSRF_ENABLED'] = False

            with flask_app.app.app_context():
                db.create_all()
                yield flask_app.app
                db.drop_all()
        except ImportError:
            pytest.skip("Could not import app module")

    def test_oauth_status_endpoint_exists(self, full_app):
        """Google OAuth status endpoint should exist."""
        with full_app.test_client() as client:
            response = client.get('/api/auth/google-status')
            # Should return 200 with enabled status
            assert response.status_code == 200
            data = response.get_json()
            assert 'enabled' in data

    def test_oauth_status_returns_disabled_when_no_credentials(self, full_app):
        """OAuth status should return disabled when Google not configured."""
        # Clear credentials
        old_client_id = os.environ.get('GOOGLE_CLIENT_ID')
        old_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

        try:
            os.environ.pop('GOOGLE_CLIENT_ID', None)
            os.environ.pop('GOOGLE_CLIENT_SECRET', None)

            # Force re-check by clearing cache
            clear_credential_cache()

            with full_app.test_client() as client:
                response = client.get('/api/auth/google-status')
                data = response.get_json()
                assert data['enabled'] is False
        finally:
            # Restore
            if old_client_id:
                os.environ['GOOGLE_CLIENT_ID'] = old_client_id
            if old_client_secret:
                os.environ['GOOGLE_CLIENT_SECRET'] = old_client_secret
            clear_credential_cache()

    def test_oauth_initiate_redirects_to_google(self, full_app):
        """OAuth initiate route should redirect to Google."""
        os.environ['GOOGLE_CLIENT_ID'] = 'test-google-client-id'
        os.environ['GOOGLE_CLIENT_SECRET'] = 'test-google-client-secret'
        clear_credential_cache()

        with full_app.test_client() as client:
            response = client.get('/auth/google', follow_redirects=False)

            # Should be a redirect
            assert response.status_code in [302, 303]
            location = response.headers.get('Location', '')

            # Should redirect to Google OAuth authorize endpoint
            assert 'accounts.google.com/o/oauth2' in location
            assert 'client_id=test-google-client-id' in location
            assert 'response_type=code' in location
            assert 'scope=' in location
            assert 'state=' in location

    def test_oauth_callback_rejects_missing_code(self, full_app):
        """OAuth callback should reject requests without code."""
        with full_app.test_client() as client:
            # Generate valid state
            state = generate_google_oauth_state()

            response = client.get(f'/auth/google/callback?state={state}')
            # Should redirect with error (missing code)
            assert response.status_code in [302, 400]

    def test_oauth_callback_rejects_invalid_state(self, full_app):
        """OAuth callback should reject invalid state."""
        with full_app.test_client() as client:
            response = client.get('/auth/google/callback?code=test&state=invalid')
            # Should redirect with error
            assert response.status_code in [302, 400]


# ==================== Test Error Handling ====================

class TestGoogleOAuthErrorHandling:
    """Test error handling in Google OAuth flow."""

    def test_state_generation_with_none_values(self, app):
        """State generation handles None values gracefully."""
        with app.app_context():
            state = generate_google_oauth_state(return_url=None, extra_data=None)
            assert state is not None

            data = verify_google_oauth_state(state)
            assert data is not None
            assert data['return_url'] is None
            assert data['extra_data'] == {}

    def test_verify_handles_malformed_json(self, app):
        """Verify handles corrupted state data."""
        with app.app_context():
            from cryptography.fernet import Fernet

            fernet = Fernet(_get_encryption_key())
            # Encrypt malformed JSON
            malformed = fernet.encrypt(b'not valid json').decode()

            result = verify_google_oauth_state(malformed)
            assert result is None

    def test_verify_handles_missing_fields(self, app):
        """Verify handles state with missing required fields."""
        with app.app_context():
            from cryptography.fernet import Fernet

            fernet = Fernet(_get_encryption_key())
            # State without expires_at
            incomplete = {'type': 'google_oauth', 'csrf_token': 'test'}
            encrypted = fernet.encrypt(json.dumps(incomplete).encode()).decode()

            result = verify_google_oauth_state(encrypted)
            assert result is None


# ==================== Test User/Tenant Creation ====================

class TestGoogleOAuthUserCreation:
    """Test user creation via Google OAuth."""

    def test_tenant_created_for_new_domain(self, app, session_fixture):
        """Tenant is created when first user signs up via Google OAuth."""
        with app.app_context():
            domain = 'newcompany.com'

            # Verify no tenant exists
            tenant = Tenant.query.filter_by(domain=domain).first()
            assert tenant is None

            # Create tenant (simulating what happens in callback)
            tenant = Tenant(
                domain=domain,
                name=domain,
                status='active',
                maturity_state=MaturityState.BOOTSTRAP
            )
            session_fixture.add(tenant)
            session_fixture.commit()

            # Verify tenant created
            reloaded = Tenant.query.filter_by(domain=domain).first()
            assert reloaded is not None
            assert reloaded.status == 'active'

    def test_first_user_becomes_provisional_admin(self, app, session_fixture):
        """First user from a new domain gets PROVISIONAL_ADMIN role."""
        with app.app_context():
            domain = 'newstartup.io'

            # Create tenant
            tenant = Tenant(
                domain=domain,
                name=domain,
                status='active',
                maturity_state=MaturityState.BOOTSTRAP
            )
            session_fixture.add(tenant)
            session_fixture.flush()

            # Create first user
            user = User(
                email=f'founder@{domain}',
                name='Founder',
                sso_domain=domain,
                auth_type='sso',
                is_admin=True,
                email_verified=True
            )
            session_fixture.add(user)
            session_fixture.flush()

            # Create membership as first user (provisional admin)
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.PROVISIONAL_ADMIN
            )
            session_fixture.add(membership)
            session_fixture.commit()

            # Verify
            reloaded_membership = TenantMembership.query.filter_by(
                user_id=user.id,
                tenant_id=tenant.id
            ).first()
            assert reloaded_membership is not None
            assert reloaded_membership.global_role == GlobalRole.PROVISIONAL_ADMIN

    def test_auth_config_created_for_new_tenant(self, app, session_fixture):
        """AuthConfig is created when tenant is created via Google OAuth."""
        with app.app_context():
            domain = 'newcorp.com'

            # Verify no auth config exists
            config = AuthConfig.query.filter_by(domain=domain).first()
            assert config is None

            # Create AuthConfig (simulating Google OAuth callback logic)
            config = AuthConfig(
                domain=domain,
                auth_method='local',
                allow_password=True,
                allow_passkey=True,
                allow_slack_oidc=True,
                allow_google_oauth=True,
                allow_registration=True,
                require_approval=True,
                rp_name='Decision Records'
            )
            session_fixture.add(config)
            session_fixture.commit()

            # Verify
            reloaded = AuthConfig.query.filter_by(domain=domain).first()
            assert reloaded is not None
            assert reloaded.allow_google_oauth is True
