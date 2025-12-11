"""
Tests for authentication endpoints and auth decorators.
"""
import pytest
from datetime import datetime, timedelta
from flask import Flask, g, session as flask_session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User, MasterAccount, WebAuthnCredential, TenantMembership, Tenant, GlobalRole
from auth import (
    get_current_user, is_master_account, validate_setup_token,
    complete_setup_and_login, authenticate_master, extract_domain_from_email
)


class TestGetCurrentUser:
    """Test get_current_user function."""

    def test_returns_user_when_logged_in(self, app, sample_user):
        """Returns user object when user_id in session."""
        with app.test_request_context():
            flask_session['user_id'] = sample_user.id
            user = get_current_user()
            assert user is not None
            assert user.id == sample_user.id
            assert user.email == sample_user.email

    def test_returns_none_when_not_logged_in(self, app):
        """Returns None when no user_id in session."""
        with app.test_request_context():
            user = get_current_user()
            assert user is None

    def test_returns_master_account_when_is_master(self, app, session):
        """Returns MasterAccount when is_master session flag set."""
        master = MasterAccount(username='testmaster', name='Test Master')
        master.set_password('testpass')
        session.add(master)
        session.commit()

        with app.test_request_context():
            flask_session['is_master'] = True
            flask_session['master_id'] = master.id
            user = get_current_user()
            assert user is not None
            assert isinstance(user, MasterAccount)
            assert user.username == 'testmaster'

    def test_returns_none_for_invalid_user_id(self, app):
        """Returns None when user_id doesn't exist."""
        with app.test_request_context():
            flask_session['user_id'] = 99999
            user = get_current_user()
            assert user is None


class TestIsMasterAccount:
    """Test is_master_account function."""

    def test_returns_true_when_master(self, app):
        """Returns True when is_master flag set."""
        with app.test_request_context():
            flask_session['is_master'] = True
            assert is_master_account() is True

    def test_returns_false_when_not_master(self, app):
        """Returns False when is_master not set."""
        with app.test_request_context():
            assert is_master_account() is False

    def test_returns_false_for_regular_user(self, app, sample_user):
        """Returns False for regular user session."""
        with app.test_request_context():
            flask_session['user_id'] = sample_user.id
            assert is_master_account() is False


class TestAuthenticateMaster:
    """Test master account authentication."""

    def test_authenticates_valid_credentials(self, session):
        """Authenticates master account with correct credentials."""
        master = MasterAccount(username='testmaster', name='Test Master')
        master.set_password('correctpassword')
        session.add(master)
        session.commit()

        result = authenticate_master('testmaster', 'correctpassword')
        assert result is not None
        assert result.username == 'testmaster'
        assert result.last_login is not None

    def test_rejects_invalid_password(self, session):
        """Rejects authentication with wrong password."""
        master = MasterAccount(username='testmaster', name='Test Master')
        master.set_password('correctpassword')
        session.add(master)
        session.commit()

        result = authenticate_master('testmaster', 'wrongpassword')
        assert result is None

    def test_rejects_nonexistent_username(self, session):
        """Rejects authentication for non-existent user."""
        result = authenticate_master('nonexistent', 'password')
        assert result is None

    def test_updates_last_login(self, session):
        """Updates last_login timestamp on successful auth."""
        master = MasterAccount(username='testmaster', name='Test Master')
        master.set_password('password')
        session.add(master)
        session.commit()

        old_login = master.last_login
        result = authenticate_master('testmaster', 'password')

        assert result.last_login is not None
        if old_login:
            assert result.last_login > old_login


class TestExtractDomainFromEmail:
    """Test email domain extraction."""

    def test_extracts_domain_from_email(self):
        """Extracts domain from valid email."""
        domain = extract_domain_from_email('user@example.com')
        assert domain == 'example.com'

    def test_extracts_domain_case_insensitive(self):
        """Converts domain to lowercase."""
        domain = extract_domain_from_email('user@EXAMPLE.COM')
        assert domain == 'example.com'

    def test_extracts_subdomain(self):
        """Handles subdomains correctly."""
        domain = extract_domain_from_email('user@mail.example.com')
        assert domain == 'mail.example.com'

    def test_returns_none_for_invalid_email(self):
        """Returns None for email without @."""
        domain = extract_domain_from_email('notanemail')
        assert domain is None

    def test_handles_empty_string(self):
        """Handles empty string gracefully."""
        domain = extract_domain_from_email('')
        assert domain is None


class TestUserModel:
    """Test User model methods."""

    def test_set_password_hashes_password(self, sample_user):
        """set_password creates password hash."""
        sample_user.set_password('testpassword')
        assert sample_user.password_hash is not None
        assert sample_user.password_hash != 'testpassword'

    def test_check_password_validates_correct_password(self, sample_user):
        """check_password returns True for correct password."""
        sample_user.set_password('testpassword')
        assert sample_user.check_password('testpassword') is True

    def test_check_password_rejects_wrong_password(self, sample_user):
        """check_password returns False for wrong password."""
        sample_user.set_password('testpassword')
        assert sample_user.check_password('wrongpassword') is False

    def test_has_password_returns_true_when_set(self, sample_user):
        """has_password returns True when password is set."""
        sample_user.set_password('password')
        assert sample_user.has_password() is True

    def test_has_password_returns_false_when_not_set(self, sample_user):
        """has_password returns False when password not set."""
        assert sample_user.has_password() is False

    def test_get_membership_returns_correct_membership(self, session, sample_user, sample_tenant, sample_membership):
        """get_membership returns user's membership for tenant."""
        membership = sample_user.get_membership(sample_tenant.id)
        assert membership is not None
        assert membership.user_id == sample_user.id
        assert membership.tenant_id == sample_tenant.id

    def test_get_membership_by_domain(self, session, sample_user, sample_tenant, sample_membership):
        """get_membership can find membership by user's domain."""
        membership = sample_user.get_membership()
        assert membership is not None
        assert membership.tenant_id == sample_tenant.id

    def test_get_membership_returns_none_for_nonexistent(self, sample_user):
        """get_membership returns None if no membership exists."""
        membership = sample_user.get_membership(99999)
        assert membership is None

    def test_is_admin_of_returns_true_for_admin(self, session, sample_tenant, admin_user):
        """is_admin_of returns True for admin users."""
        assert admin_user.is_admin_of(sample_tenant.id) is True

    def test_is_admin_of_returns_false_for_regular_user(self, session, sample_user, sample_tenant, sample_membership):
        """is_admin_of returns False for regular users."""
        assert sample_user.is_admin_of(sample_tenant.id) is False

    def test_is_full_admin_of_returns_true_for_admin(self, session, sample_tenant, admin_user):
        """is_full_admin_of returns True for full admin."""
        assert admin_user.is_full_admin_of(sample_tenant.id) is True

    def test_is_full_admin_of_returns_false_for_steward(self, session, sample_tenant, steward_user):
        """is_full_admin_of returns False for steward."""
        assert steward_user.is_full_admin_of(sample_tenant.id) is False

    def test_to_dict_includes_key_fields(self, sample_user):
        """to_dict includes essential user fields."""
        data = sample_user.to_dict()
        assert 'id' in data
        assert 'email' in data
        assert 'name' in data
        assert 'sso_domain' in data
        assert 'auth_type' in data
        assert 'has_passkey' in data
        assert 'has_password' in data

    def test_to_dict_excludes_sensitive_data(self, sample_user):
        """to_dict does not include password hash."""
        sample_user.set_password('testpass')
        data = sample_user.to_dict()
        assert 'password_hash' not in data
        assert data['has_password'] is True


class TestMasterAccountModel:
    """Test MasterAccount model methods."""

    def test_set_password_hashes_password(self, session):
        """set_password creates password hash."""
        master = MasterAccount(username='test', name='Test')
        master.set_password('password')
        assert master.password_hash is not None
        assert master.password_hash != 'password'

    def test_check_password_validates_correct(self, session):
        """check_password returns True for correct password."""
        master = MasterAccount(username='test', name='Test')
        master.set_password('password')
        assert master.check_password('password') is True

    def test_check_password_rejects_wrong(self, session):
        """check_password returns False for wrong password."""
        master = MasterAccount(username='test', name='Test')
        master.set_password('password')
        assert master.check_password('wrongpass') is False

    def test_to_dict_includes_is_master_flag(self, session):
        """to_dict includes is_master=True flag."""
        master = MasterAccount(username='test', name='Test')
        master.set_password('pass')
        session.add(master)
        session.commit()

        data = master.to_dict()
        assert data['is_master'] is True
        assert data['is_admin'] is True
        assert data['username'] == 'test'

    def test_create_default_master_creates_account(self, session):
        """create_default_master creates default account if not exists."""
        # Note: DEFAULT_MASTER_USERNAME/PASSWORD are read at import time
        # and default to 'admin'/'changeme'
        master = MasterAccount.create_default_master(session)
        assert master is not None
        assert master.username == 'admin'
        assert master.check_password('changeme') is True

    def test_create_default_master_returns_existing(self, session):
        """create_default_master returns existing account if already created."""
        # Create the default 'admin' master account first
        master1 = MasterAccount(username='admin', name='Admin')
        master1.set_password('pass')
        session.add(master1)
        session.commit()

        # Calling create_default_master should return the existing account
        master2 = MasterAccount.create_default_master(session)
        assert master2.id == master1.id
