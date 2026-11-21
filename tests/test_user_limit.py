"""
The per-tenant user limit holds on every path that adds an account to a tenant.

The limit is one global setting (`max_users_per_tenant`, 0 = unlimited). An
installation that never stored a value follows the built-in default; a stored
value is never overwritten.

Each path that can add an account to an existing tenant is driven through the
real app in four situations: one place left, no place left, unlimited, and a
different tenant that is full. The first account of a new tenant always fits.
"""
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, AuthConfig, EmailConfig, AccessRequest,
    EmailVerification, SSOConfig, GlobalRole, MaturityState, SystemConfig
)
from tests.app_test_utils import load_test_app
from tests.test_auth_session_oauth import PROVIDER_FACTORIES, sign_in as provider_sign_in

PASSWORD = 'Str0ngPassword'
DOMAIN = 'acme.test'
OTHER_DOMAIN = 'globex.test'
LIMIT = 3
NEWCOMER = f'newcomer@{DOMAIN}'
SEND_SETUP = 'notifications.send_account_setup_email'


@pytest.fixture
def real_app(monkeypatch):
    monkeypatch.setenv('APP_BASE_URL', 'https://app.example.test')
    monkeypatch.delenv('OAUTH_BASE_URL', raising=False)
    app_module, test_app = load_test_app(secret_key='test-secret-key-user-limit')

    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def set_limit(value):
    SystemConfig.set(SystemConfig.KEY_MAX_USERS_PER_TENANT, value)


def make_member(email, role=GlobalRole.USER, *, membership=True):
    domain = email.split('@')[1]
    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        tenant = Tenant(domain=domain, name=domain, status='active',
                        maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(tenant)
        db.session.flush()
    user = User(email=email, sso_domain=domain, auth_type='local', email_verified=True,
                is_admin=role != GlobalRole.USER)
    user.set_name(first_name='Org', last_name='Member')
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.flush()
    if membership:
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    db.session.commit()
    return user


def make_tenant_with(count, domain=DOMAIN, admin_role=GlobalRole.ADMIN):
    """A tenant with `count` accounts: one administrator and ordinary members."""
    make_member(f'owner@{domain}', admin_role)
    for index in range(count - 1):
        make_member(f'member{index}@{domain}')


def configure_email():
    db.session.add(EmailConfig(
        domain='system', smtp_server='smtp.example.test', smtp_port=587,
        smtp_username='mailer', smtp_password='secret', from_email='noreply@example.test',
        enabled=True))
    db.session.commit()


def admin_client(test_app, domain=DOMAIN):
    client = test_app.test_client()
    response = client.post('/api/auth/login', json={'email': f'owner@{domain}', 'password': PASSWORD})
    assert response.status_code == 200, response.get_json()
    client.environ_base['HTTP_X_CSRF_TOKEN'] = response.headers['X-CSRF-Token']
    return client


def account_exists(email=NEWCOMER):
    return User.query.filter_by(email=email).first() is not None


def assert_limit_json(response, max_users=LIMIT):
    assert response.status_code == 403, response.get_data(as_text=True)
    body = response.get_json()
    assert body['error'] == 'User limit reached'
    assert f'maximum user limit of {max_users}' in body['message']
    assert body['max_users'] == max_users
    assert body['current_users'] == max_users


def assert_limit_redirect(response, domain=DOMAIN):
    assert response.status_code == 302, response.get_data(as_text=True)
    assert response.headers['Location'].endswith(f'/{domain}/login?error=user_limit')


# ==================== Paths that add an account ====================
#
# Each driver tries to add `email` to its tenant through one path and returns
# the response. `refused` asserts the response is that path's limit refusal.

class SocialSignIn:
    """Slack, Google, Microsoft and Teams sign-in create the account on first use."""

    def __init__(self, provider_name):
        self.provider_name = provider_name
        self.name = f'{provider_name} sign-in'

    def prepare(self, real_app, monkeypatch, domain):
        self.provider = PROVIDER_FACTORIES[self.provider_name]().install(monkeypatch)

    def attempt(self, real_app, email):
        _, test_app = real_app
        return provider_sign_in(test_app.test_client(), self.provider, email)

    def refused(self, response, domain):
        assert_limit_redirect(response, domain)

    def admitted(self, response):
        assert response.status_code == 302, response.get_data(as_text=True)
        assert 'error=' not in response.headers['Location']


class TenantSso:
    """A tenant's own OIDC provider creates the account on first sign-in."""
    name = 'tenant SSO'

    def prepare(self, real_app, monkeypatch, domain):
        app_module, _ = real_app
        db.session.add(SSOConfig(
            domain=domain, provider_name='Okta', client_id='client', client_secret='secret',
            discovery_url='https://idp.example.test/.well-known/openid-configuration', enabled=True))
        db.session.commit()
        self.config_id = SSOConfig.query.filter_by(domain=domain).first().id
        self.oidc_client = Mock()
        monkeypatch.setattr(app_module, 'get_oidc_config', lambda url: {
            'token_endpoint': 'https://idp.example.test/token',
            'userinfo_endpoint': 'https://idp.example.test/userinfo',
        })
        monkeypatch.setattr(app_module, 'OAuth2Session', lambda **kwargs: self.oidc_client)

    def attempt(self, real_app, email):
        _, test_app = real_app
        self.oidc_client.get.return_value.json.return_value = {
            'email': email, 'name': 'New Comer', 'sub': 'idp-subject-1'}
        client = test_app.test_client()
        with client.session_transaction() as sess:
            sess['sso_config_id'] = self.config_id
            sess['oauth_state'] = 'state'
        return client.get('/auth/callback?code=abc&state=state')

    def refused(self, response, domain):
        assert response.status_code == 403
        assert f'maximum user limit of {LIMIT}' in response.get_data(as_text=True)

    def admitted(self, response):
        assert response.status_code == 302, response.get_data(as_text=True)


class TeamsTabSignIn:
    """The Teams tab token endpoint creates the account on first use."""
    name = 'Teams tab sign-in'

    def prepare(self, real_app, monkeypatch, domain):
        import feature_flags
        self.claims = {}
        module = types.ModuleType('ee.backend.oauth_providers.microsoft_oauth')
        module.validate_teams_sso_token = lambda token: dict(self.claims)
        module.generate_teams_tab_auth_token = lambda user_id, tenant_domain: 'tab-token'
        for parent in ('ee', 'ee.backend', 'ee.backend.oauth_providers'):
            if parent not in sys.modules:
                stub = types.ModuleType(parent)
                stub.__path__ = []
                monkeypatch.setitem(sys.modules, parent, stub)
        monkeypatch.setitem(sys.modules, module.__name__, module)
        monkeypatch.setitem(feature_flags.FEATURES, 'teams_integration', True)
        app_module, _ = real_app
        monkeypatch.setattr(app_module, 'generate_teams_tab_auth_token',
                            module.generate_teams_tab_auth_token, raising=False)

    def attempt(self, real_app, email):
        _, test_app = real_app
        self.claims = {'email': email, 'name': 'New Comer', 'oid': 'ms-object-1'}
        return test_app.test_client().post('/api/teams/sso/validate', json={'token': 'teams-token'})

    def refused(self, response, domain):
        assert_limit_json(response)
        assert response.get_json()['valid'] is False

    def admitted(self, response):
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['valid'] is True


class AutomaticAdmission:
    """An access request to a tenant that admits without approval."""
    name = 'access request admitted automatically'

    def prepare(self, real_app, monkeypatch, domain):
        if not EmailConfig.query.filter_by(domain='system').first():
            configure_email()
        if not AuthConfig.query.filter_by(domain=domain).first():
            db.session.add(AuthConfig(domain=domain, require_approval=False))
            db.session.commit()

    def attempt(self, real_app, email):
        _, test_app = real_app
        with patch(SEND_SETUP, return_value=True):
            return test_app.test_client().post('/api/auth/access-request', json={
                'email': email, 'first_name': 'New', 'last_name': 'Comer',
                'domain': email.split('@')[1], 'reason': 'I work here'})

    def refused(self, response, domain):
        assert_limit_json(response)
        assert AccessRequest.query.count() == 0

    def admitted(self, response):
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['auto_approved'] is True


class AdminApproval:
    """An administrator approves a pending access request."""
    name = 'access request approved by an administrator'

    def prepare(self, real_app, monkeypatch, domain):
        pass

    def attempt(self, real_app, email):
        _, test_app = real_app
        domain = email.split('@')[1]
        access_request = AccessRequest(email=email, name='New Comer', domain=domain, reason='x')
        db.session.add(access_request)
        db.session.commit()
        self.request_id = access_request.id
        return admin_client(test_app, domain).post(
            f'/api/admin/access-requests/{access_request.id}/approve')

    def refused(self, response, domain):
        assert_limit_json(response)
        assert 'contact your organization administrator' not in response.get_json()['message']
        assert db.session.get(AccessRequest, self.request_id).status == 'pending'

    def admitted(self, response):
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['message'] == 'Access request approved'


class VerifiedSignUp:
    """Opening an emailed sign-up link creates the account."""
    name = 'email-verified sign-up'
    method = 'post'

    def prepare(self, real_app, monkeypatch, domain):
        pass

    def attempt(self, real_app, email):
        _, test_app = real_app
        self.token = f'token-{email}'
        db.session.add(EmailVerification(
            email=email, name='New Comer', token=self.token, purpose='signup',
            domain=email.split('@')[1],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2)))
        db.session.commit()
        client = test_app.test_client()
        return getattr(client, self.method)(f'/api/auth/verify-email/{self.token}')

    def refused(self, response, domain):
        if self.method == 'post':
            assert_limit_json(response)
        else:
            assert_limit_redirect(response, domain)
        # The link is left unused so it works once a place is free
        assert EmailVerification.query.filter_by(token=self.token).first().verified_at is None

    def admitted(self, response):
        assert response.status_code in (200, 302), response.get_data(as_text=True)
        assert EmailVerification.query.filter_by(token=self.token).first().verified_at is not None


class VerifiedSignUpByLink(VerifiedSignUp):
    name = 'email-verified sign-up (link opened in the browser)'
    method = 'get'


PATHS = [
    SocialSignIn('google'), SocialSignIn('microsoft'), SocialSignIn('slack'), SocialSignIn('teams'),
    TenantSso(), TeamsTabSignIn(), AutomaticAdmission(), AdminApproval(),
    VerifiedSignUp(), VerifiedSignUpByLink(),
]


@pytest.fixture(params=PATHS, ids=lambda path: path.name)
def path(request):
    return request.param


class TestLimitHoldsOnEveryPath:

    def test_last_place_can_be_taken(self, real_app, monkeypatch, path):
        set_limit(LIMIT)
        make_tenant_with(LIMIT - 1)
        path.prepare(real_app, monkeypatch, DOMAIN)

        path.admitted(path.attempt(real_app, NEWCOMER))

        assert account_exists()

    def test_full_tenant_refuses_a_new_account(self, real_app, monkeypatch, path):
        set_limit(LIMIT)
        make_tenant_with(LIMIT)
        path.prepare(real_app, monkeypatch, DOMAIN)

        path.refused(path.attempt(real_app, NEWCOMER), DOMAIN)

        assert not account_exists()
        assert User.query.filter_by(sso_domain=DOMAIN).count() == LIMIT

    def test_unlimited_admits_beyond_any_number(self, real_app, monkeypatch, path):
        set_limit(0)
        make_tenant_with(LIMIT + 2)
        path.prepare(real_app, monkeypatch, DOMAIN)

        path.admitted(path.attempt(real_app, NEWCOMER))

        assert account_exists()

    def test_another_full_tenant_does_not_block_this_one(self, real_app, monkeypatch, path):
        set_limit(LIMIT)
        make_tenant_with(LIMIT, domain=OTHER_DOMAIN)
        make_tenant_with(1)
        path.prepare(real_app, monkeypatch, DOMAIN)

        path.admitted(path.attempt(real_app, NEWCOMER))

        assert account_exists()


SIGN_IN_PATHS = [p for p in PATHS if isinstance(p, (SocialSignIn, TenantSso, TeamsTabSignIn))]


class TestExistingAccountsAreNeverRefused:

    @pytest.mark.parametrize('path', SIGN_IN_PATHS, ids=lambda path: path.name)
    def test_member_of_a_full_tenant_can_still_sign_in(self, real_app, monkeypatch, path):
        set_limit(LIMIT)
        make_tenant_with(LIMIT)
        path.prepare(real_app, monkeypatch, DOMAIN)

        path.admitted(path.attempt(real_app, f'member0@{DOMAIN}'))

    @pytest.mark.parametrize('path', SIGN_IN_PATHS, ids=lambda path: path.name)
    def test_account_admitted_without_a_membership_can_sign_in_to_a_full_tenant(
            self, real_app, monkeypatch, path):
        set_limit(LIMIT)
        make_tenant_with(LIMIT - 1)
        make_member(f'approved@{DOMAIN}', membership=False)
        path.prepare(real_app, monkeypatch, DOMAIN)

        path.admitted(path.attempt(real_app, f'approved@{DOMAIN}'))

    def test_approving_a_request_for_an_existing_account_is_not_refused(self, real_app):
        _, test_app = real_app
        set_limit(LIMIT)
        make_tenant_with(LIMIT)
        access_request = AccessRequest(email=f'member0@{DOMAIN}', name='Org Member', domain=DOMAIN)
        db.session.add(access_request)
        db.session.commit()

        response = admin_client(test_app).post(
            f'/api/admin/access-requests/{access_request.id}/approve')

        assert response.status_code == 200, response.get_json()


class TestFirstAccountOfANewTenant:
    """Creating a tenant is never blocked, whatever the limit."""

    @pytest.mark.parametrize('provider_name', ['google', 'microsoft', 'slack', 'teams'])
    def test_social_sign_in_creates_a_new_tenant_at_the_lowest_limit(
            self, real_app, monkeypatch, provider_name):
        _, test_app = real_app
        set_limit(1)
        make_tenant_with(1, domain=OTHER_DOMAIN)
        provider = PROVIDER_FACTORIES[provider_name]().install(monkeypatch)

        response = provider_sign_in(test_app.test_client(), provider, f'founder@{DOMAIN}')

        assert response.status_code == 302
        assert 'error=' not in response.headers['Location']
        assert account_exists(f'founder@{DOMAIN}')

    def test_verified_sign_up_creates_a_new_tenant_at_the_lowest_limit(self, real_app):
        _, test_app = real_app
        set_limit(1)
        db.session.add(EmailVerification(
            email=f'founder@{DOMAIN}', name='Founder', token='first-token', purpose='signup',
            domain=DOMAIN, expires_at=datetime.now(timezone.utc) + timedelta(hours=2)))
        db.session.commit()

        response = test_app.test_client().post('/api/auth/verify-email/first-token')

        assert response.status_code == 200, response.get_json()
        assert account_exists(f'founder@{DOMAIN}')

    def test_setup_wizard_and_direct_sign_up_only_create_first_accounts(self, real_app):
        """Direct sign-up refuses a domain that already has accounts, so it cannot exceed the limit."""
        _, test_app = real_app
        SystemConfig.set(SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED, 'false')
        set_limit(LIMIT)
        make_tenant_with(1)

        response = test_app.test_client().post('/api/auth/direct-signup', json={
            'email': NEWCOMER, 'first_name': 'New', 'password': PASSWORD,
            'auth_preference': 'password'})

        assert response.status_code == 400
        assert 'already has users' in response.get_json()['error']
        assert not account_exists()


class TestSignUpLinkIsNotSentToAFullTenant:
    """Asking for a sign-up link says straight away when the tenant is full."""

    def ask(self, test_app, email=NEWCOMER):
        return test_app.test_client().post('/api/auth/send-verification', json={
            'email': email, 'first_name': 'New', 'last_name': 'Comer'})

    def test_full_tenant_that_admits_without_approval_refuses(self, real_app):
        _, test_app = real_app
        set_limit(LIMIT)
        make_tenant_with(LIMIT, admin_role=GlobalRole.PROVISIONAL_ADMIN)

        response = self.ask(test_app)

        assert_limit_json(response)
        assert EmailVerification.query.count() == 0

    def test_tenant_with_a_place_left_gets_a_link(self, real_app):
        app_module, test_app = real_app
        set_limit(LIMIT)
        make_tenant_with(LIMIT - 1, admin_role=GlobalRole.PROVISIONAL_ADMIN)

        with patch.object(app_module, 'send_verification_email', return_value=True):
            response = self.ask(test_app)

        assert response.status_code == 200, response.get_json()
        assert response.get_json()['purpose'] == 'signup'

    def test_full_tenant_that_requires_approval_still_takes_the_request(self, real_app):
        """Approval is where the limit applies: an administrator may free a place first."""
        app_module, test_app = real_app
        set_limit(LIMIT)
        make_tenant_with(LIMIT)

        with patch.object(app_module, 'send_verification_email', return_value=True):
            response = self.ask(test_app)

        assert response.status_code == 200, response.get_json()
        assert response.get_json()['purpose'] == 'access_request'


class TestWhoCountsTowardsTheLimit:

    def test_accounts_without_a_membership_count(self, real_app):
        """Accounts admitted through access requests have no membership row."""
        app_module, _ = real_app
        set_limit(LIMIT)
        make_tenant_with(1)
        make_member(f'approved1@{DOMAIN}', membership=False)
        make_member(f'approved2@{DOMAIN}', membership=False)

        can_accept, _, current, max_allowed = app_module.can_tenant_accept_users(DOMAIN)

        assert (can_accept, current, max_allowed) == (False, 3, LIMIT)

    def test_repeated_approvals_stop_at_the_limit(self, real_app):
        _, test_app = real_app
        set_limit(LIMIT)
        make_tenant_with(1)
        client = admin_client(test_app)
        statuses = []
        for index in range(LIMIT):
            access_request = AccessRequest(email=f'joiner{index}@{DOMAIN}', name='Joiner', domain=DOMAIN)
            db.session.add(access_request)
            db.session.commit()
            statuses.append(client.post(
                f'/api/admin/access-requests/{access_request.id}/approve').status_code)

        assert statuses == [200, 200, 403]
        assert User.query.filter_by(sso_domain=DOMAIN).count() == LIMIT

    def test_anonymised_accounts_do_not_count(self, real_app):
        app_module, _ = real_app
        set_limit(LIMIT)
        make_tenant_with(LIMIT)
        leaver = User.query.filter_by(email=f'member0@{DOMAIN}').first()

        assert app_module.can_tenant_accept_users(DOMAIN)[0] is False
        assert app_module.anonymize_user(leaver.id) is True

        can_accept, _, current, _ = app_module.can_tenant_accept_users(DOMAIN)
        assert (can_accept, current) == (True, LIMIT - 1)

    def test_account_pending_deletion_still_counts(self, real_app):
        """A deletion request can be cancelled for 7 days, so the place is still taken."""
        app_module, _ = real_app
        set_limit(LIMIT)
        make_tenant_with(LIMIT)
        leaver = User.query.filter_by(email=f'member0@{DOMAIN}').first()
        leaver.deletion_requested_at = datetime.now(timezone.utc)
        db.session.commit()

        assert app_module.can_tenant_accept_users(DOMAIN)[0] is False

    def test_domain_without_a_tenant_row_counts_its_accounts(self, real_app):
        app_module, _ = real_app
        set_limit(LIMIT)
        for index in range(2):
            user = User(email=f'legacy{index}@legacy.test', sso_domain='legacy.test', auth_type='local')
            db.session.add(user)
        db.session.commit()

        assert app_module.can_tenant_accept_users('legacy.test')[2] == 2
        assert app_module.can_tenant_accept_users('legacy.test', count=2)[0] is False


class TestDefaultLimit:
    """Moving the default from 5 to 25 must not override a value an operator stored."""

    def stored(self):
        return SystemConfig.query.filter_by(key=SystemConfig.KEY_MAX_USERS_PER_TENANT).first()

    def test_default_is_25(self):
        assert SystemConfig.DEFAULT_MAX_USERS_PER_TENANT == 25

    def test_installation_without_a_stored_value_gets_25(self, real_app):
        app_module, test_app = real_app
        assert self.stored() is None
        make_tenant_with(6)

        can_accept, _, current, max_allowed = app_module.can_tenant_accept_users(DOMAIN)

        assert (can_accept, current, max_allowed) == (True, 6, 25)

    def test_starting_up_does_not_store_a_value(self, real_app):
        """Nothing writes the default into the database, so later default changes still apply."""
        app_module, _ = real_app
        from migrations import run_migrations

        app_module._db_initialized = False
        app_module.init_database()
        run_migrations(db)

        assert self.stored() is None

    @pytest.mark.parametrize('stored_value', ['5', '10', '0', '100'])
    def test_stored_value_survives_startup(self, real_app, stored_value):
        """A stored 5 is kept too: it cannot be told apart from a deliberate choice of 5."""
        app_module, _ = real_app
        from migrations import run_migrations
        set_limit(stored_value)

        app_module._db_initialized = False
        app_module.init_database()
        run_migrations(db)

        assert self.stored().value == stored_value
        assert app_module.can_tenant_accept_users(DOMAIN)[3] == int(stored_value)

    def test_super_admin_settings_report_the_default(self, real_app):
        app_module, test_app = real_app
        from models import MasterAccount
        master = MasterAccount.query.first()
        client = test_app.test_client()
        with client.session_transaction() as sess:
            sess['master_id'] = master.id
            sess['is_master'] = True
            sess['_expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        response = client.get('/api/admin/settings/licensing')

        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json() == {
            'max_users_per_tenant': 25, 'defaults': {'max_users_per_tenant': 25}}
