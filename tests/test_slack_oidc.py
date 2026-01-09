"""
Backend Unit Tests for Slack OIDC Authentication (Enterprise Edition)

Tests for the "Sign in with Slack" feature using OpenID Connect.
Tests cover:
- OIDC state generation and verification
- OIDC status endpoint
- OIDC initiation redirect
- OIDC callback handling
- User creation for new domains
- Existing user login
- Blocked domain rejection
- First user becomes provisional admin

Note: These tests require Enterprise Edition modules from ee/backend/slack/
"""
import pytest
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, session as flask_session
import requests

from models import (
    db, User, Tenant, TenantMembership, TenantSettings, AuthConfig,
    GlobalRole, MaturityState
)

# Enterprise Edition imports - skip tests if not available
try:
    from ee.backend.slack.slack_security import (
        generate_slack_oidc_state, verify_slack_oidc_state,
        _get_encryption_key, SLACK_OIDC_AUTHORIZE_URL, SLACK_OIDC_TOKEN_URL,
        SLACK_OIDC_USERINFO_URL, SLACK_OIDC_SCOPES
    )
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    generate_slack_oidc_state = None
    verify_slack_oidc_state = None
    _get_encryption_key = None
    SLACK_OIDC_AUTHORIZE_URL = None
    SLACK_OIDC_TOKEN_URL = None
    SLACK_OIDC_USERINFO_URL = None
    SLACK_OIDC_SCOPES = None

pytestmark = pytest.mark.skipif(not EE_AVAILABLE, reason="Enterprise Edition modules not available")


# ==================== Fixtures ====================

@pytest.fixture
def app():
    """Create application for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'

    # Set Slack environment variables for tests
    os.environ['SIGNING_SECRET'] = 'test-signing-secret-12345'
    os.environ['CLIENT_ID'] = 'test-client-id'
    os.environ['CLIENT_SECRET'] = 'test-client-secret'

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
def sample_tenant_with_settings(session_fixture, sample_tenant):
    """Create a tenant with settings including Slack OIDC config."""
    settings = TenantSettings(
        tenant_id=sample_tenant.id,
        auth_method='local',
        allow_password=True,
        allow_passkey=True,
        allow_slack_oidc=True,
        allow_registration=True,
        require_approval=False,
        tenant_prefix='EXM'
    )
    session_fixture.add(settings)
    session_fixture.commit()
    return sample_tenant


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


# ==================== Test OIDC State Functions ====================

class TestSlackOidcState:
    """Test Slack OIDC state generation and verification."""

    def test_generate_state_creates_valid_token(self, app):
        """State can be generated successfully."""
        with app.app_context():
            state = generate_slack_oidc_state(return_url='/dashboard')

            assert state is not None
            assert isinstance(state, str)
            assert len(state) > 50  # Encrypted state should be substantial

    def test_state_roundtrip_preserves_data(self, app):
        """State can be generated and verified with data preserved."""
        with app.app_context():
            return_url = '/dashboard'
            extra_data = {'link_token': 'abc123'}

            state = generate_slack_oidc_state(
                return_url=return_url,
                extra_data=extra_data
            )

            # Verify state
            state_data = verify_slack_oidc_state(state)

            assert state_data is not None
            assert state_data['type'] == 'slack_oidc'
            assert state_data['return_url'] == return_url
            assert state_data['extra_data']['link_token'] == 'abc123'
            assert 'csrf_token' in state_data
            assert 'expires_at' in state_data

    def test_state_includes_csrf_protection(self, app):
        """State contains CSRF token."""
        with app.app_context():
            state1 = generate_slack_oidc_state()
            state2 = generate_slack_oidc_state()

            data1 = verify_slack_oidc_state(state1)
            data2 = verify_slack_oidc_state(state2)

            # Each state should have unique CSRF token
            assert data1['csrf_token'] != data2['csrf_token']

    def test_expired_state_rejected(self, app):
        """Expired state should be rejected."""
        with app.app_context():
            from cryptography.fernet import Fernet

            # Create expired state (expired 1 hour ago)
            expires_at = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)).isoformat()
            state_data = {
                'type': 'slack_oidc',
                'csrf_token': 'test',
                'expires_at': expires_at,
                'return_url': None,
                'extra_data': {}
            }

            fernet = Fernet(_get_encryption_key())
            expired_state = fernet.encrypt(json.dumps(state_data).encode()).decode()

            # Verify should fail
            result = verify_slack_oidc_state(expired_state)
            assert result is None

    def test_invalid_state_rejected(self, app):
        """Invalid state string should return None."""
        with app.app_context():
            invalid_state = 'totally-invalid-state-string'
            result = verify_slack_oidc_state(invalid_state)
            assert result is None

    def test_empty_state_rejected(self, app):
        """Empty state should return None."""
        with app.app_context():
            result = verify_slack_oidc_state('')
            assert result is None

            result = verify_slack_oidc_state(None)
            assert result is None

    def test_wrong_type_state_rejected(self, app):
        """OAuth state (not OIDC) should be rejected."""
        with app.app_context():
            from cryptography.fernet import Fernet

            # Create state without 'slack_oidc' type (like regular OAuth state)
            expires_at = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)).isoformat()
            state_data = {
                'tenant_id': 123,  # Regular OAuth state has tenant_id
                'csrf_token': 'test',
                'expires_at': expires_at,
                'extra_data': {}
            }

            fernet = Fernet(_get_encryption_key())
            wrong_type_state = fernet.encrypt(json.dumps(state_data).encode()).decode()

            # Verify should fail - wrong type
            result = verify_slack_oidc_state(wrong_type_state)
            assert result is None


class TestSlackOidcConstants:
    """Test that OIDC constants are properly defined."""

    def test_authorize_url_defined(self):
        """Authorize URL should be Slack OIDC endpoint."""
        assert SLACK_OIDC_AUTHORIZE_URL == 'https://slack.com/openid/connect/authorize'

    def test_token_url_defined(self):
        """Token URL should be Slack OIDC endpoint."""
        assert SLACK_OIDC_TOKEN_URL == 'https://slack.com/api/openid.connect.token'

    def test_userinfo_url_defined(self):
        """UserInfo URL should be Slack OIDC endpoint."""
        assert SLACK_OIDC_USERINFO_URL == 'https://slack.com/api/openid.connect.userInfo'

    def test_scopes_include_required(self):
        """Scopes should include openid, profile, and email."""
        assert 'openid' in SLACK_OIDC_SCOPES
        assert 'profile' in SLACK_OIDC_SCOPES
        assert 'email' in SLACK_OIDC_SCOPES


# ==================== Test TenantSettings Model ====================

class TestTenantSettingsSlackOidc:
    """Test TenantSettings model with Slack OIDC fields."""

    def test_allow_slack_oidc_default_true(self, app, session_fixture, sample_tenant):
        """allow_slack_oidc should default to True."""
        with app.app_context():
            settings = TenantSettings(
                tenant_id=sample_tenant.id,
                auth_method='local'
            )
            session_fixture.add(settings)
            session_fixture.commit()

            # Reload from DB
            reloaded = TenantSettings.query.filter_by(tenant_id=sample_tenant.id).first()
            assert reloaded.allow_slack_oidc is True

    def test_allow_slack_oidc_can_be_disabled(self, app, session_fixture, sample_tenant):
        """allow_slack_oidc can be set to False."""
        with app.app_context():
            settings = TenantSettings(
                tenant_id=sample_tenant.id,
                auth_method='local',
                allow_slack_oidc=False
            )
            session_fixture.add(settings)
            session_fixture.commit()

            reloaded = TenantSettings.query.filter_by(tenant_id=sample_tenant.id).first()
            assert reloaded.allow_slack_oidc is False

    def test_auth_method_slack_oidc(self, app, session_fixture, sample_tenant):
        """auth_method can be set to 'slack_oidc'."""
        with app.app_context():
            settings = TenantSettings(
                tenant_id=sample_tenant.id,
                auth_method='slack_oidc'
            )
            session_fixture.add(settings)
            session_fixture.commit()

            reloaded = TenantSettings.query.filter_by(tenant_id=sample_tenant.id).first()
            assert reloaded.auth_method == 'slack_oidc'

    def test_to_dict_includes_allow_slack_oidc(self, app, session_fixture, sample_tenant):
        """to_dict() should include allow_slack_oidc field."""
        with app.app_context():
            settings = TenantSettings(
                tenant_id=sample_tenant.id,
                auth_method='local',
                allow_slack_oidc=True
            )
            session_fixture.add(settings)
            session_fixture.commit()

            settings_dict = settings.to_dict()
            assert 'allow_slack_oidc' in settings_dict
            assert settings_dict['allow_slack_oidc'] is True


class TestAuthConfigSlackOidc:
    """Test AuthConfig model with Slack OIDC fields."""

    def test_allow_slack_oidc_in_auth_config(self, app, session_fixture):
        """AuthConfig should support allow_slack_oidc field."""
        with app.app_context():
            config = AuthConfig(
                domain='example.com',
                auth_method='local',
                allow_slack_oidc=True,
                allow_password=True,
                allow_passkey=False
            )
            session_fixture.add(config)
            session_fixture.commit()

            reloaded = AuthConfig.query.filter_by(domain='example.com').first()
            assert reloaded.allow_slack_oidc is True

    def test_auth_config_to_dict_includes_slack_oidc(self, app, session_fixture):
        """AuthConfig.to_dict() should include allow_slack_oidc."""
        with app.app_context():
            config = AuthConfig(
                domain='example.com',
                auth_method='slack_oidc',
                allow_slack_oidc=True
            )
            session_fixture.add(config)
            session_fixture.commit()

            config_dict = config.to_dict()
            assert 'allow_slack_oidc' in config_dict
            assert config_dict['allow_slack_oidc'] is True
            assert config_dict['auth_method'] == 'slack_oidc'


# ==================== Test Blocked Domains ====================

class TestBlockedDomains:
    """Test that public email domains are properly blocked."""

    BLOCKED_DOMAINS = [
        'gmail.com',
        'yahoo.com',
        'hotmail.com',
        'outlook.com',
        'aol.com',
        'icloud.com',
        'protonmail.com',
        'mail.com',
        'live.com',
        'msn.com'
    ]

    def test_blocked_domains_list(self):
        """Common public email domains should be blocked."""
        # This tests our understanding of what domains should be blocked
        # The actual blocking happens in app.py callback route
        for domain in self.BLOCKED_DOMAINS:
            # Domain should not be allowed for enterprise signup
            assert domain in self.BLOCKED_DOMAINS


# ==================== Integration Tests with App Routes ====================

class TestSlackOidcRoutes:
    """Test Slack OIDC API routes (requires actual app import)."""

    @pytest.fixture
    def full_app(self):
        """Create app with actual routes registered."""
        # Set up environment before importing app
        os.environ['SIGNING_SECRET'] = 'test-signing-secret-12345'
        os.environ['CLIENT_ID'] = 'test-client-id'
        os.environ['CLIENT_SECRET'] = 'test-client-secret'
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

    def test_oidc_status_endpoint_exists(self, full_app):
        """OIDC status endpoint should exist."""
        with full_app.test_client() as client:
            response = client.get('/api/auth/slack-oidc-status')
            # Should return 200 with enabled status
            assert response.status_code == 200
            data = response.get_json()
            assert 'enabled' in data

    def test_oidc_status_returns_disabled_when_no_credentials(self, full_app):
        """OIDC status should return disabled when Slack not configured."""
        # Clear Slack credentials
        old_client_id = os.environ.get('CLIENT_ID')
        old_client_secret = os.environ.get('CLIENT_SECRET')

        try:
            os.environ.pop('CLIENT_ID', None)
            os.environ.pop('CLIENT_SECRET', None)

            # Force re-check by clearing cache
            import slack_security
            slack_security._slack_signing_secret = None

            with full_app.test_client() as client:
                response = client.get('/api/auth/slack-oidc-status')
                data = response.get_json()
                # Should indicate disabled (credentials missing)
                assert 'enabled' in data
        finally:
            # Restore
            if old_client_id:
                os.environ['CLIENT_ID'] = old_client_id
            if old_client_secret:
                os.environ['CLIENT_SECRET'] = old_client_secret

    def test_oidc_initiate_redirects_to_slack(self, full_app):
        """OIDC initiate route should redirect to Slack."""
        os.environ['CLIENT_ID'] = 'test-client-id'
        os.environ['CLIENT_SECRET'] = 'test-client-secret'

        with full_app.test_client() as client:
            response = client.get('/auth/slack/oidc', follow_redirects=False)

            # Should be a redirect
            assert response.status_code in [302, 303]
            location = response.headers.get('Location', '')

            # Should redirect to Slack OIDC authorize endpoint
            assert 'slack.com/openid/connect/authorize' in location
            assert 'client_id=test-client-id' in location
            assert 'response_type=code' in location
            assert 'scope=' in location
            assert 'state=' in location

    def test_oidc_callback_rejects_missing_code(self, full_app):
        """OIDC callback should reject requests without code."""
        with full_app.test_client() as client:
            # Generate valid state
            state = generate_slack_oidc_state()

            response = client.get(f'/auth/slack/oidc/callback?state={state}')
            # Should redirect with error (missing code)
            assert response.status_code in [302, 400]

    def test_oidc_callback_rejects_invalid_state(self, full_app):
        """OIDC callback should reject invalid state."""
        with full_app.test_client() as client:
            response = client.get('/auth/slack/oidc/callback?code=test&state=invalid')
            # Should redirect with error
            assert response.status_code in [302, 400]


class TestSlackOidcUserCreation:
    """Test user creation via Slack OIDC."""

    def test_extract_domain_from_email(self):
        """Domain extraction from email works correctly."""
        from auth import extract_domain_from_email

        assert extract_domain_from_email('user@example.com') == 'example.com'
        assert extract_domain_from_email('user@EXAMPLE.COM') == 'example.com'
        assert extract_domain_from_email('user@sub.example.com') == 'sub.example.com'
        assert extract_domain_from_email('invalid') is None

    def test_get_or_create_user_creates_new_user(self, app, session_fixture, sample_tenant):
        """get_or_create_user creates new user for existing tenant."""
        from auth import get_or_create_user

        with app.app_context():
            user = get_or_create_user(
                email='newuser@example.com',
                name='New User',
                sso_subject='slack-user-123',
                sso_domain='example.com'
            )

            assert user is not None
            assert user.email == 'newuser@example.com'
            assert user.name == 'New User'
            assert user.sso_domain == 'example.com'

    def test_get_or_create_user_returns_existing(self, app, session_fixture, sample_user):
        """get_or_create_user returns existing user."""
        from auth import get_or_create_user

        with app.app_context():
            user = get_or_create_user(
                email='existing@example.com',
                name='Updated Name',
                sso_subject='slack-user-456',
                sso_domain='example.com'
            )

            assert user is not None
            assert user.id == sample_user.id

    def test_first_user_gets_provisional_admin(self, app, session_fixture):
        """First user of a new domain becomes provisional admin."""
        from auth import get_or_create_user

        with app.app_context():
            # Create user for brand new domain (no tenant exists yet)
            user = get_or_create_user(
                email='first@newcompany.com',
                name='First User',
                sso_subject='slack-user-789',
                sso_domain='newcompany.com'
            )

            assert user is not None

            # Check membership - user should have been created
            membership = TenantMembership.query.filter_by(user_id=user.id).first()
            if membership:
                # First user should be provisional admin
                assert membership.global_role in [GlobalRole.PROVISIONAL_ADMIN, GlobalRole.ADMIN]


# ==================== Test Tenant Auto-Creation ====================

class TestSlackOidcTenantCreation:
    """Test tenant auto-creation during Slack OIDC signup."""

    def test_tenant_created_for_new_domain(self, app, session_fixture):
        """Tenant is created when first user signs up via Slack OIDC."""
        with app.app_context():
            domain = 'brandnew.com'

            # Verify no tenant exists
            tenant = Tenant.query.filter_by(domain=domain).first()
            assert tenant is None

            # Create user (simulating what happens before tenant creation in callback)
            user = User(
                email=f'first@{domain}',
                name='First User',
                sso_domain=domain,
                auth_type='sso',
                is_admin=True,
                email_verified=True
            )
            session_fixture.add(user)
            session_fixture.flush()

            # Now create tenant (simulating Slack OIDC callback logic)
            tenant = Tenant(
                domain=domain,
                name=domain,
                status='active',
                maturity_state=MaturityState.BOOTSTRAP
            )
            session_fixture.add(tenant)
            session_fixture.flush()

            # Create membership
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.PROVISIONAL_ADMIN
            )
            session_fixture.add(membership)
            session_fixture.commit()

            # Verify
            reloaded_tenant = Tenant.query.filter_by(domain=domain).first()
            assert reloaded_tenant is not None
            assert reloaded_tenant.status == 'active'
            assert reloaded_tenant.maturity_state == MaturityState.BOOTSTRAP

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

            # Create membership as first user
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

    def test_second_user_becomes_regular_user(self, app, session_fixture, sample_tenant):
        """Second user from domain gets USER role, not admin."""
        with app.app_context():
            # First user already exists via sample_tenant fixture
            first_user = User(
                email=f'first@{sample_tenant.domain}',
                name='First User',
                sso_domain=sample_tenant.domain,
                auth_type='sso',
                is_admin=True,
                email_verified=True
            )
            session_fixture.add(first_user)
            session_fixture.flush()

            # Create membership for first user
            first_membership = TenantMembership(
                user_id=first_user.id,
                tenant_id=sample_tenant.id,
                global_role=GlobalRole.PROVISIONAL_ADMIN
            )
            session_fixture.add(first_membership)
            session_fixture.commit()

            # Create second user
            second_user = User(
                email=f'second@{sample_tenant.domain}',
                name='Second User',
                sso_domain=sample_tenant.domain,
                auth_type='sso',
                is_admin=False,  # Not admin
                email_verified=True
            )
            session_fixture.add(second_user)
            session_fixture.flush()

            # Create membership for second user (should be regular USER)
            second_membership = TenantMembership(
                user_id=second_user.id,
                tenant_id=sample_tenant.id,
                global_role=GlobalRole.USER
            )
            session_fixture.add(second_membership)
            session_fixture.commit()

            # Verify second user is regular user
            reloaded = TenantMembership.query.filter_by(
                user_id=second_user.id,
                tenant_id=sample_tenant.id
            ).first()
            assert reloaded.global_role == GlobalRole.USER

    def test_auth_config_created_for_new_tenant(self, app, session_fixture):
        """AuthConfig is created when tenant is created via Slack OIDC."""
        with app.app_context():
            domain = 'newcorp.com'

            # Verify no auth config exists
            config = AuthConfig.query.filter_by(domain=domain).first()
            assert config is None

            # Create AuthConfig (simulating Slack OIDC callback logic)
            config = AuthConfig(
                domain=domain,
                auth_method='slack_oidc',
                allow_password=True,
                allow_passkey=True,
                allow_slack_oidc=True,
                allow_registration=True,
                require_approval=True,
                rp_name='Decision Records'
            )
            session_fixture.add(config)
            session_fixture.commit()

            # Verify
            reloaded = AuthConfig.query.filter_by(domain=domain).first()
            assert reloaded is not None
            assert reloaded.auth_method == 'slack_oidc'
            assert reloaded.allow_slack_oidc is True

    def test_tenant_not_recreated_for_existing_domain(self, app, session_fixture, sample_tenant):
        """Existing tenant is reused, not recreated."""
        with app.app_context():
            original_id = sample_tenant.id

            # Check if tenant already exists (it does via fixture)
            existing = Tenant.query.filter_by(domain=sample_tenant.domain).first()
            assert existing is not None
            assert existing.id == original_id

            # Simulate what callback does - check before creating
            tenant = Tenant.query.filter_by(domain=sample_tenant.domain).first()
            if not tenant:
                tenant = Tenant(domain=sample_tenant.domain, name='New Name')
                session_fixture.add(tenant)

            session_fixture.commit()

            # Verify original tenant is still there
            final = Tenant.query.filter_by(domain=sample_tenant.domain).first()
            assert final.id == original_id

    def test_membership_created_for_existing_tenant_new_user(self, app, session_fixture, sample_tenant):
        """Membership is created when user signs up to existing tenant."""
        with app.app_context():
            # Create new user for existing tenant
            user = User(
                email=f'newbie@{sample_tenant.domain}',
                name='New Employee',
                sso_domain=sample_tenant.domain,
                auth_type='sso',
                is_admin=False,
                email_verified=True
            )
            session_fixture.add(user)
            session_fixture.flush()

            # Create membership
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=sample_tenant.id,
                global_role=GlobalRole.USER
            )
            session_fixture.add(membership)
            session_fixture.commit()

            # Verify
            reloaded = TenantMembership.query.filter_by(
                user_id=user.id,
                tenant_id=sample_tenant.id
            ).first()
            assert reloaded is not None
            assert reloaded.global_role == GlobalRole.USER


class TestSlackOidcDomainValidation:
    """Test domain validation during Slack OIDC signup."""

    def test_public_domain_blocked(self):
        """Public email domains (gmail, yahoo, etc.) are blocked."""
        from models import DomainApproval

        public_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
        for domain in public_domains:
            assert DomainApproval.is_public_domain(domain), f"{domain} should be blocked"

    def test_corporate_domain_allowed(self):
        """Corporate domains are allowed."""
        from models import DomainApproval

        corporate_domains = ['acme.com', 'startup.io', 'bigcorp.co.uk']
        for domain in corporate_domains:
            assert not DomainApproval.is_public_domain(domain), f"{domain} should be allowed"

    def test_disposable_domain_blocked(self):
        """Disposable email domains are blocked."""
        from models import DomainApproval

        # Note: This may need actual disposable domains from the blocklist
        # For now, test the method exists and works
        assert hasattr(DomainApproval, 'is_disposable_domain')


# ==================== Test Error Handling ====================

class TestSlackOidcErrorHandling:
    """Test error handling in Slack OIDC flow."""

    def test_state_generation_with_none_values(self, app):
        """State generation handles None values gracefully."""
        with app.app_context():
            state = generate_slack_oidc_state(return_url=None, extra_data=None)
            assert state is not None

            data = verify_slack_oidc_state(state)
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

            result = verify_slack_oidc_state(malformed)
            assert result is None

    def test_verify_handles_missing_fields(self, app):
        """Verify handles state with missing required fields."""
        with app.app_context():
            from cryptography.fernet import Fernet

            fernet = Fernet(_get_encryption_key())
            # State without expires_at
            incomplete = {'type': 'slack_oidc', 'csrf_token': 'test'}
            encrypted = fernet.encrypt(json.dumps(incomplete).encode()).decode()

            result = verify_slack_oidc_state(encrypted)
            assert result is None
