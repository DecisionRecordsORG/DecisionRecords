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
from sqlalchemy.engine import make_url


def fixture_database_url():
    """Database the ``app`` fixture creates and drops its schema in.

    In-memory SQLite by default. CI also runs the suite with TEST_DATABASE_URL
    pointing at a PostgreSQL service, because SQLite does not load the
    PostgreSQL driver, enforce foreign keys or check column types.

    Every test drops all tables afterwards, so a database whose name does not
    contain "test" is refused rather than emptied.
    """
    url = os.environ.get('TEST_DATABASE_URL', '').strip()
    if not url:
        return 'sqlite:///:memory:'
    database_name = make_url(url).database or ''
    if 'test' not in database_name.lower():
        raise RuntimeError(
            'TEST_DATABASE_URL must name a database containing "test" '
            f'(got {database_name!r}): the test fixtures drop every table.'
        )
    return url


@pytest.fixture
def app():
    """Create application for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = fixture_database_url()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'

    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        drop_schema()


def drop_schema():
    """Drop every table of the current app's database, holding nothing while doing it.

    The session's connection is released first: on PostgreSQL an open
    transaction holds locks that make DROP TABLE wait forever. The engine's
    pool is emptied before and after, so no connection this test opened (in
    any thread) is left on the server. This protects the fixture from its own
    connections only. It does not make a second writer safe, and it does not
    retry: nothing else may be using the test database (see
    `no_retention_thread_outlives_a_test` below).
    """
    db.session.remove()
    db.engine.dispose()
    db.drop_all()
    db.session.remove()
    db.engine.dispose()


@pytest.fixture(autouse=True)
def no_retention_thread_outlives_a_test():
    """Fail the test that leaves a retention thread running.

    The thread checks the database a minute after it starts and then again
    and again. Left running, it queries the shared PostgreSQL test database
    while later tests create and drop their tables, and CI fails far from the
    test that caused it with a deadlock in some other test's teardown.
    """
    import retention
    yield
    alive = retention.scheduler_threads()
    if alive:
        retention.stop_scheduler()
        for thread in alive:
            thread.join(5)
        pytest.fail(f'{len(alive)} retention scheduler thread(s) were left running by this test')


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
        sess['_csrf_token'] = 'test-csrf-token'
    client.environ_base['HTTP_X_CSRF_TOKEN'] = 'test-csrf-token'
    return client


@pytest.fixture
def admin_client(app, admin_user):
    """Create admin authenticated test client."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = admin_user.id
        sess['_csrf_token'] = 'test-csrf-token'
    client.environ_base['HTTP_X_CSRF_TOKEN'] = 'test-csrf-token'
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
        sess['master_username'] = sample_master.username
        sess['_csrf_token'] = 'test-csrf-token'
    client.environ_base['HTTP_X_CSRF_TOKEN'] = 'test-csrf-token'
    return client
