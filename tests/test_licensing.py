"""
Unit and integration tests for licensing features.

Tests cover:
- SystemConfig licensing constants
- User limit enforcement
- Licensing API endpoints
"""

import pytest
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from flask.testing import FlaskClient


class TestSystemConfigLicensing:
    """Unit tests for SystemConfig licensing constants and methods."""

    def test_licensing_constants_exist(self):
        """Test that licensing configuration keys are defined."""
        from models import SystemConfig

        assert hasattr(SystemConfig, 'KEY_MAX_USERS_PER_TENANT')
        assert SystemConfig.KEY_MAX_USERS_PER_TENANT == 'max_users_per_tenant'

    def test_default_max_users_per_tenant(self):
        """Test that default max users per tenant is 5."""
        from models import SystemConfig

        assert hasattr(SystemConfig, 'DEFAULT_MAX_USERS_PER_TENANT')
        assert SystemConfig.DEFAULT_MAX_USERS_PER_TENANT == 5


class TestUserLimitLogic:
    """Unit tests for user limit enforcement logic."""

    @pytest.fixture
    def app(self):
        """Create test Flask application."""
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        os.environ['SECRET_KEY'] = 'test-secret-key'

        from app import app, db
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, app) -> FlaskClient:
        """Create test client."""
        return app.test_client()

    def test_can_tenant_accept_users_unlimited(self, app):
        """Test that unlimited mode (0) always allows users."""
        from app import can_tenant_accept_users
        from models import SystemConfig, db

        with app.app_context():
            # Set to unlimited
            SystemConfig.set(SystemConfig.KEY_MAX_USERS_PER_TENANT, 0)
            db.session.commit()

            can_accept, message, current, max_allowed = can_tenant_accept_users('nonexistent.com')
            assert can_accept is True
            assert 'Unlimited' in message
            assert max_allowed == 0

    def test_can_tenant_accept_users_under_limit(self, app):
        """Test accepting users when under the limit."""
        from app import can_tenant_accept_users
        from models import SystemConfig, User, Tenant, TenantMembership, GlobalRole, db

        with app.app_context():
            # Set limit to 5
            SystemConfig.set(SystemConfig.KEY_MAX_USERS_PER_TENANT, 5)

            # Create a tenant with 3 users (using TenantMembership)
            tenant = Tenant(domain='test.com', name='Test Tenant')
            db.session.add(tenant)
            db.session.flush()  # Get tenant.id

            for i in range(3):
                user = User(email=f'user{i}@test.com', name=f'User {i}', sso_domain='test.com')
                db.session.add(user)
                db.session.flush()  # Get user.id
                # Create TenantMembership to properly associate user with tenant
                membership = TenantMembership(tenant_id=tenant.id, user_id=user.id, global_role=GlobalRole.USER)
                db.session.add(membership)

            db.session.commit()

            can_accept, message, current, max_allowed = can_tenant_accept_users('test.com')
            assert can_accept is True
            assert current == 3
            assert max_allowed == 5

    def test_can_tenant_accept_users_at_limit(self, app):
        """Test rejecting users when at the limit."""
        from app import can_tenant_accept_users
        from models import SystemConfig, User, Tenant, TenantMembership, GlobalRole, db

        with app.app_context():
            # Set limit to 3
            SystemConfig.set(SystemConfig.KEY_MAX_USERS_PER_TENANT, 3)

            # Create a tenant with 3 users (at limit, using TenantMembership)
            tenant = Tenant(domain='full.com', name='Full Tenant')
            db.session.add(tenant)
            db.session.flush()  # Get tenant.id

            for i in range(3):
                user = User(email=f'user{i}@full.com', name=f'User {i}', sso_domain='full.com')
                db.session.add(user)
                db.session.flush()  # Get user.id
                # Create TenantMembership to properly associate user with tenant
                membership = TenantMembership(tenant_id=tenant.id, user_id=user.id, global_role=GlobalRole.USER)
                db.session.add(membership)

            db.session.commit()

            can_accept, message, current, max_allowed = can_tenant_accept_users('full.com')
            assert can_accept is False
            assert 'maximum user limit' in message
            assert current == 3
            assert max_allowed == 3

    def test_can_tenant_accept_multiple_users(self, app):
        """Test checking if multiple users can be added."""
        from app import can_tenant_accept_users
        from models import SystemConfig, User, Tenant, TenantMembership, GlobalRole, db

        with app.app_context():
            # Set limit to 5
            SystemConfig.set(SystemConfig.KEY_MAX_USERS_PER_TENANT, 5)

            # Create a tenant with 3 users (using TenantMembership)
            tenant = Tenant(domain='partial.com', name='Partial Tenant')
            db.session.add(tenant)
            db.session.flush()  # Get tenant.id

            for i in range(3):
                user = User(email=f'user{i}@partial.com', name=f'User {i}', sso_domain='partial.com')
                db.session.add(user)
                db.session.flush()  # Get user.id
                # Create TenantMembership to properly associate user with tenant
                membership = TenantMembership(tenant_id=tenant.id, user_id=user.id, global_role=GlobalRole.USER)
                db.session.add(membership)

            db.session.commit()

            # Can add 2 more (3 + 2 = 5)
            can_accept, _, _, _ = can_tenant_accept_users('partial.com', count=2)
            assert can_accept is True

            # Cannot add 3 more (3 + 3 = 6 > 5)
            can_accept, _, _, _ = can_tenant_accept_users('partial.com', count=3)
            assert can_accept is False


class TestLicensingAPIEndpoints:
    """Integration tests for licensing API endpoints."""

    @pytest.fixture
    def app(self):
        """Create test Flask application."""
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        os.environ['SECRET_KEY'] = 'test-secret-key'

        from app import app, db
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, app) -> FlaskClient:
        """Create test client."""
        return app.test_client()

    @pytest.fixture
    def master_session(self, client, app):
        """Create a session logged in as master admin."""
        from models import MasterAccount, db
        from werkzeug.security import generate_password_hash

        with app.app_context():
            # Create master account
            master = MasterAccount(
                username='admin',
                password_hash=generate_password_hash('testpass')
            )
            db.session.add(master)
            db.session.commit()

        # Login as master
        response = client.post('/auth/local', json={
            'username': 'admin',
            'password': 'testpass'
        })
        assert response.status_code == 200
        return client

    def test_get_licensing_settings_requires_auth(self, client):
        """Test that licensing settings endpoint requires authentication."""
        response = client.get('/api/admin/settings/licensing')
        assert response.status_code == 401

    def test_get_licensing_settings_success(self, master_session, app):
        """Test getting licensing settings as master admin."""
        with app.app_context():
            response = master_session.get('/api/admin/settings/licensing')
            assert response.status_code == 200

            data = response.get_json()
            assert 'max_users_per_tenant' in data
            assert 'defaults' in data
            assert data['defaults']['max_users_per_tenant'] == 5

    def test_save_licensing_settings_success(self, master_session, app):
        """Test saving licensing settings as master admin."""
        with app.app_context():
            response = master_session.post('/api/admin/settings/licensing', json={
                'max_users_per_tenant': 10
            })
            assert response.status_code == 200

            data = response.get_json()
            assert data['max_users_per_tenant'] == 10
            assert 'message' in data

    def test_save_licensing_settings_invalid_value(self, master_session, app):
        """Test saving invalid licensing settings."""
        with app.app_context():
            # Negative value
            response = master_session.post('/api/admin/settings/licensing', json={
                'max_users_per_tenant': -1
            })
            assert response.status_code == 400

            # Too high value
            response = master_session.post('/api/admin/settings/licensing', json={
                'max_users_per_tenant': 20000
            })
            assert response.status_code == 400

    def test_save_licensing_settings_unlimited(self, master_session, app):
        """Test setting unlimited users (0)."""
        with app.app_context():
            response = master_session.post('/api/admin/settings/licensing', json={
                'max_users_per_tenant': 0
            })
            assert response.status_code == 200

            data = response.get_json()
            assert data['max_users_per_tenant'] == 0


class TestAccessRequestUserLimit:
    """Integration tests for user limit enforcement in access requests."""

    @pytest.fixture
    def app(self):
        """Create test Flask application."""
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        os.environ['SECRET_KEY'] = 'test-secret-key'

        from app import app, db
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, app) -> FlaskClient:
        """Create test client."""
        return app.test_client()

    @pytest.fixture
    def setup_tenant_at_limit(self, app, client):
        """Create a tenant with users at the limit."""
        from models import SystemConfig, User, Tenant, TenantMembership, GlobalRole, AuthConfig, MasterAccount, AccessRequest, db
        from werkzeug.security import generate_password_hash

        with app.app_context():
            # Set limit to 2
            SystemConfig.set(SystemConfig.KEY_MAX_USERS_PER_TENANT, 2)

            # Create tenant
            tenant = Tenant(domain='limited.com', name='Limited Tenant')
            db.session.add(tenant)
            db.session.flush()  # Get tenant.id

            # Create auth config with approval required
            auth_config = AuthConfig(domain='limited.com', require_approval=True)
            db.session.add(auth_config)

            # Create 2 users (at limit) with TenantMemberships
            admin_user = User(
                email='admin@limited.com',
                name='Admin User',
                sso_domain='limited.com',
                is_admin=True
            )
            db.session.add(admin_user)
            db.session.flush()
            # Create membership for admin
            admin_membership = TenantMembership(tenant_id=tenant.id, user_id=admin_user.id, global_role=GlobalRole.ADMIN)
            db.session.add(admin_membership)

            regular_user = User(
                email='user@limited.com',
                name='Regular User',
                sso_domain='limited.com'
            )
            db.session.add(regular_user)
            db.session.flush()
            # Create membership for regular user
            user_membership = TenantMembership(tenant_id=tenant.id, user_id=regular_user.id, global_role=GlobalRole.USER)
            db.session.add(user_membership)

            # Create master account
            master = MasterAccount(
                username='admin',
                password_hash=generate_password_hash('testpass')
            )
            db.session.add(master)

            # Create pending access request
            access_request = AccessRequest(
                email='newuser@limited.com',
                name='New User',
                domain='limited.com',
                reason='I want to join'
            )
            db.session.add(access_request)

            db.session.commit()

            return {
                'tenant': tenant,
                'admin_user': admin_user,
                'access_request_id': access_request.id
            }

    def test_access_request_approval_blocked_at_limit(self, client, app, setup_tenant_at_limit):
        """Test that approving access request is blocked when tenant is at limit."""
        # Login as master
        response = client.post('/auth/local', json={
            'username': 'admin',
            'password': 'testpass'
        })
        assert response.status_code == 200

        with app.app_context():
            # Try to approve the access request
            request_id = setup_tenant_at_limit['access_request_id']
            response = client.post(f'/api/admin/access-requests/{request_id}/approve')

            assert response.status_code == 403
            data = response.get_json()
            assert 'User limit reached' in data.get('error', '')
            assert data.get('current_users') == 2
            assert data.get('max_users') == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
