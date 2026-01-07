"""Tests for login history tracking functionality.

Tests the LoginHistory model and log_login_attempt helper function.
Note: API endpoint tests are located in test_api_integration.py
"""
import pytest
from datetime import datetime, timezone
from models import db, LoginHistory, log_login_attempt, EmailVerification


class TestLoginHistoryModel:
    """Tests for the LoginHistory model."""

    def test_create_login_history_entry(self, app, session):
        """Test creating a login history entry."""
        entry = LoginHistory(
            email='test@example.com',
            login_method=LoginHistory.METHOD_PASSWORD,
            success=True,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        session.add(entry)
        session.commit()

        assert entry.id is not None
        assert entry.email == 'test@example.com'
        assert entry.login_method == 'password'
        assert entry.success is True
        assert entry.created_at is not None

    def test_login_history_to_dict(self, app, session):
        """Test LoginHistory.to_dict() method."""
        entry = LoginHistory(
            email='test@example.com',
            login_method=LoginHistory.METHOD_WEBAUTHN,
            success=False,
            failure_reason='Invalid credential',
            ip_address='10.0.0.1'
        )
        session.add(entry)
        session.commit()

        data = entry.to_dict()
        assert data['email'] == 'test@example.com'
        assert data['login_method'] == 'webauthn'
        assert data['success'] is False
        assert data['failure_reason'] == 'Invalid credential'
        assert data['ip_address'] == '10.0.0.1'

    def test_log_login_attempt_success(self, app, session):
        """Test log_login_attempt helper function for successful login."""
        entry = log_login_attempt(
            email='user@example.com',
            login_method=LoginHistory.METHOD_SSO,
            success=True,
            user_id=123,
            tenant_domain='example.com',
            ip_address='172.16.0.1',
            user_agent='Test Agent'
        )

        assert entry.id is not None
        assert entry.email == 'user@example.com'
        assert entry.user_id == 123
        assert entry.tenant_domain == 'example.com'
        assert entry.success is True

    def test_log_login_attempt_failure(self, app, session):
        """Test log_login_attempt helper function for failed login."""
        entry = log_login_attempt(
            email='hacker@example.com',
            login_method=LoginHistory.METHOD_PASSWORD,
            success=False,
            failure_reason='Invalid password',
            ip_address='192.168.1.100'
        )

        assert entry.success is False
        assert entry.failure_reason == 'Invalid password'
        assert entry.user_id is None

    def test_login_history_method_constants(self, app):
        """Test login method constants are defined correctly."""
        assert LoginHistory.METHOD_PASSWORD == 'password'
        assert LoginHistory.METHOD_WEBAUTHN == 'webauthn'
        assert LoginHistory.METHOD_SSO == 'sso'
        assert LoginHistory.METHOD_SLACK_OIDC == 'slack_oidc'
        assert LoginHistory.METHOD_GOOGLE_OAUTH == 'google_oauth'
        assert LoginHistory.METHOD_TEAMS_OIDC == 'teams_oidc'
        assert LoginHistory.METHOD_MASTER == 'master'

    def test_user_agent_truncation(self, app, session):
        """Test that long user agent strings are truncated."""
        long_user_agent = 'X' * 600  # Longer than 500 char limit
        entry = log_login_attempt(
            email='test@example.com',
            login_method=LoginHistory.METHOD_PASSWORD,
            success=True,
            user_agent=long_user_agent
        )

        assert len(entry.user_agent) == 500

    def test_login_history_indexes(self, app, session):
        """Test that login history entries can be queried efficiently."""
        # Create entries for different scenarios
        log_login_attempt('user1@example.com', LoginHistory.METHOD_PASSWORD, True, tenant_domain='acme.com')
        log_login_attempt('user2@example.com', LoginHistory.METHOD_WEBAUTHN, True, tenant_domain='acme.com')
        log_login_attempt('user3@example.com', LoginHistory.METHOD_PASSWORD, False, tenant_domain='corp.com')

        # Query by email (indexed)
        results = LoginHistory.query.filter_by(email='user1@example.com').all()
        assert len(results) == 1

        # Query by tenant_domain (indexed)
        results = LoginHistory.query.filter_by(tenant_domain='acme.com').all()
        assert len(results) == 2

        # Query by success (indexed)
        results = LoginHistory.query.filter_by(success=False).all()
        assert len(results) == 1

    def test_login_history_with_user_reference(self, app, session, sample_user):
        """Test login history can reference a user."""
        entry = log_login_attempt(
            email=sample_user.email,
            login_method=LoginHistory.METHOD_PASSWORD,
            success=True,
            user_id=sample_user.id,
            tenant_domain=sample_user.sso_domain
        )

        assert entry.user_id == sample_user.id

        # Query should find the entry
        found = LoginHistory.query.filter_by(user_id=sample_user.id).first()
        assert found is not None
        assert found.email == sample_user.email


class TestEmailVerificationModel:
    """Tests for EmailVerification model used by pending verifications."""

    def test_create_pending_verification(self, app, session):
        """Test creating an email verification record."""
        verification = EmailVerification(
            email='newuser@example.com',
            name='New User',
            token='unique-token-123',
            purpose='signup',
            domain='example.com',
            expires_at=datetime.now(timezone.utc)
        )
        session.add(verification)
        session.commit()

        assert verification.id is not None
        assert verification.verified_at is None
        assert not verification.is_verified()

    def test_verification_expiry(self, app, session):
        """Test that expired verifications are detected."""
        from datetime import timedelta

        # Create expired verification
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        verification = EmailVerification(
            email='expired@example.com',
            token='expired-token',
            purpose='signup',
            domain='example.com',
            expires_at=past
        )
        session.add(verification)
        session.commit()

        assert verification.is_expired()

    def test_pending_verifications_query(self, app, session):
        """Test querying for pending (unverified) email verifications."""
        # Create pending verification
        pending = EmailVerification(
            email='pending@example.com',
            token='token1',
            purpose='signup',
            domain='example.com',
            expires_at=datetime.now(timezone.utc)
        )
        session.add(pending)

        # Create verified verification
        verified = EmailVerification(
            email='verified@example.com',
            token='token2',
            purpose='signup',
            domain='example.com',
            expires_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc)
        )
        session.add(verified)
        session.commit()

        # Query for pending (unverified) verifications
        pending_verifications = EmailVerification.query.filter(
            EmailVerification.verified_at.is_(None)
        ).all()

        assert len(pending_verifications) == 1
        assert pending_verifications[0].email == 'pending@example.com'
