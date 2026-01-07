"""
Pytest fixtures for Architecture Decisions tests.
"""
import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User, Tenant, TenantMembership, TenantSettings, Space, DecisionSpace, \
    AuditLog, ArchitectureDecision, MaturityState, GlobalRole, VisibilityPolicy, \
    LoginHistory, log_login_attempt, EmailVerification, MasterAccount
from flask import Flask


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
def session(app):
    """Create database session for testing."""
    with app.app_context():
        yield db.session


@pytest.fixture
def sample_user(session):
    """Create a sample user."""
    user = User(
        email='test@example.com',
        sso_domain='example.com',
        auth_type='local',
        email_verified=True
    )
    user.set_name(first_name='Test', last_name='User')
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def sample_tenant(session):
    """Create a sample tenant."""
    tenant = Tenant(
        domain='example.com',
        name='Example Corp',
        status='active',
        maturity_state=MaturityState.BOOTSTRAP
    )
    session.add(tenant)
    session.commit()
    return tenant


@pytest.fixture
def sample_tenant_with_settings(session, sample_tenant):
    """Create a tenant with settings."""
    settings = TenantSettings(
        tenant_id=sample_tenant.id,
        auth_method='local',
        allow_password=True,
        allow_passkey=True,
        allow_registration=True,
        require_approval=False,
        tenant_prefix='EXM'
    )
    session.add(settings)
    session.commit()
    return sample_tenant


@pytest.fixture
def sample_membership(session, sample_user, sample_tenant):
    """Create a sample membership."""
    membership = TenantMembership(
        user_id=sample_user.id,
        tenant_id=sample_tenant.id,
        global_role=GlobalRole.USER
    )
    session.add(membership)
    session.commit()
    return membership


@pytest.fixture
def admin_user(session, sample_tenant):
    """Create an admin user with membership."""
    user = User(
        email='admin@example.com',
        sso_domain='example.com',
        auth_type='local',
        email_verified=True
    )
    user.set_name(first_name='Admin', last_name='User')
    session.add(user)
    session.flush()

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=sample_tenant.id,
        global_role=GlobalRole.ADMIN
    )
    session.add(membership)
    session.commit()
    return user


@pytest.fixture
def steward_user(session, sample_tenant):
    """Create a steward user with membership."""
    user = User(
        email='steward@example.com',
        sso_domain='example.com',
        auth_type='local',
        email_verified=True
    )
    user.set_name(first_name='Steward', last_name='User')
    session.add(user)
    session.flush()

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=sample_tenant.id,
        global_role=GlobalRole.STEWARD
    )
    session.add(membership)
    session.commit()
    return user


@pytest.fixture
def sample_space(session, sample_tenant, sample_user):
    """Create a sample space."""
    space = Space(
        tenant_id=sample_tenant.id,
        name='Default Space',
        description='The default space',
        is_default=True,
        visibility_policy=VisibilityPolicy.TENANT_VISIBLE,
        created_by_id=sample_user.id
    )
    session.add(space)
    session.commit()
    return space


@pytest.fixture
def sample_decision(session, sample_tenant, sample_user):
    """Create a sample decision."""
    from models import ArchitectureDecision
    decision = ArchitectureDecision(
        title='Test Decision',
        context='Test context for the decision',
        decision='The decision text',
        status='proposed',
        consequences='Expected consequences',
        domain=sample_tenant.domain,
        tenant_id=sample_tenant.id,
        created_by_id=sample_user.id,
        decision_number=1
    )
    session.add(decision)
    session.commit()
    return decision


@pytest.fixture
def client(app):
    """Create test client for making HTTP requests."""
    return app.test_client()


@pytest.fixture
def authenticated_client(app, sample_user):
    """Create authenticated test client."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = sample_user.id
    return client


@pytest.fixture
def admin_client(app, admin_user):
    """Create admin authenticated test client."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = admin_user.id
    return client


@pytest.fixture
def sample_master(session):
    """Create a sample master account for testing."""
    master = MasterAccount(username='testadmin')
    master.set_password('testpassword')
    session.add(master)
    session.commit()
    return master


@pytest.fixture
def master_session(app, sample_master):
    """Create a logged-in master session for testing superadmin endpoints."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['master_id'] = sample_master.id
        sess['is_master'] = True
    return client
