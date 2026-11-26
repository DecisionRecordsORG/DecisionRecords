"""
Accounts and tenants created through the Microsoft Teams bot (Enterprise Edition).

The bot creates an account, and for a new organisation a tenant, the first
time someone uses it. These tests check that it respects the tenant user
limit like every sign-in path, and that a tenant created through the bot is
set up the same way as one created through the Teams sign-in
(POST /api/teams/sso/validate).
"""
import asyncio
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if not os.path.exists(os.path.join(_ROOT, 'models.py')):
    _ROOT = os.getcwd()
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from models import (  # noqa: E402
    db, User, Tenant, TenantMembership, Space, AuthConfig, DomainApproval,
    GlobalRole, MaturityState, SystemConfig, TeamsWorkspace, TeamsUserMapping
)
from tests.app_test_utils import load_test_app  # noqa: E402

try:
    from ee.backend.teams.teams_service import TeamsService
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    TeamsService = None

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

LIMIT = 3
DOMAIN = 'alpha.example'
MS_TENANT = '11111111-1111-1111-1111-111111111111'
AUTH_CONFIG_FIELDS = (
    'auth_method', 'allow_password', 'allow_passkey', 'allow_slack_oidc', 'allow_google_oauth',
    'allow_microsoft_oauth', 'allow_registration', 'require_approval', 'rp_name',
)


@pytest.fixture
def real_app(monkeypatch):
    """The real application, so the limit check is the one sign-in uses."""
    monkeypatch.setenv('APP_BASE_URL', 'https://app.example.test')
    monkeypatch.delenv('OAUTH_BASE_URL', raising=False)
    app_module, test_app = load_test_app(secret_key='test-secret-key-teams-provisioning')
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def set_limit(value):
    SystemConfig.set(SystemConfig.KEY_MAX_USERS_PER_TENANT, value)


def make_tenant(domain=DOMAIN, accounts=0):
    tenant = Tenant(domain=domain, name=domain, status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.flush()
    db.session.add(Space(tenant_id=tenant.id, name='General', is_default=True))
    for index in range(accounts):
        user = User(email=f'member{index}@{domain}', sso_domain=domain, auth_type='local', email_verified=True)
        db.session.add(user)
        db.session.flush()
        role = GlobalRole.ADMIN if index == 0 else GlobalRole.USER
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    db.session.commit()
    return tenant


def make_workspace(tenant=None, ms_tenant_id=MS_TENANT):
    workspace = TeamsWorkspace(ms_tenant_id=ms_tenant_id, is_active=True,
                               tenant_id=tenant.id if tenant else None)
    db.session.add(workspace)
    db.session.commit()
    return workspace


def oid(number):
    return f'aaaaaaaa-0000-0000-0000-{number:012d}'


class TestUserLimitHoldsForTheBot:

    def test_full_tenant_refuses_a_new_account(self, real_app):
        set_limit(LIMIT)
        tenant = make_tenant(accounts=LIMIT)
        service = TeamsService(make_workspace(tenant))

        mapping, user, needs_linking = service.get_or_provision_user(oid(1), f'newcomer@{DOMAIN}', 'New Comer')

        assert user is None
        assert needs_linking is True
        assert service.provision_refusal['error'] == 'User limit reached'
        assert service.provision_refusal['max_users'] == LIMIT
        assert User.query.filter_by(email=f'newcomer@{DOMAIN}').first() is None
        assert User.query.filter_by(sso_domain=DOMAIN).count() == LIMIT
        assert TenantMembership.query.filter_by(tenant_id=tenant.id).count() == LIMIT
        assert TeamsUserMapping.query.filter(TeamsUserMapping.user_id.isnot(None)).count() == 0

    def test_full_tenant_refuses_an_account_without_an_address(self, real_app):
        set_limit(LIMIT)
        tenant = make_tenant(accounts=LIMIT)
        service = TeamsService(make_workspace(tenant))

        _, user, _ = service.get_or_provision_user(oid(1), None, 'No Address')

        assert user is None
        assert User.query.count() == LIMIT

    def test_last_place_can_be_taken(self, real_app):
        set_limit(LIMIT)
        tenant = make_tenant(accounts=LIMIT - 1)
        service = TeamsService(make_workspace(tenant))

        _, user, needs_linking = service.get_or_provision_user(oid(1), f'newcomer@{DOMAIN}', 'New Comer')

        assert user is not None and needs_linking is False
        assert service.provision_refusal is None
        assert User.query.filter_by(sso_domain=DOMAIN).count() == LIMIT

        # and the next one is refused
        _, second, _ = service.get_or_provision_user(oid(2), f'second@{DOMAIN}', 'Second Comer')
        assert second is None

    def test_unlimited_admits_beyond_any_number(self, real_app):
        set_limit(0)
        tenant = make_tenant(accounts=LIMIT + 2)
        service = TeamsService(make_workspace(tenant))

        _, user, _ = service.get_or_provision_user(oid(1), f'newcomer@{DOMAIN}', 'New Comer')

        assert user is not None

    def test_existing_member_of_a_full_tenant_is_linked(self, real_app):
        set_limit(LIMIT)
        tenant = make_tenant(accounts=LIMIT)
        service = TeamsService(make_workspace(tenant))

        _, user, needs_linking = service.get_or_provision_user(oid(1), f'Member1@{DOMAIN}', 'Member One')

        assert user is not None and needs_linking is False
        assert user.email == f'member1@{DOMAIN}'
        assert User.query.count() == LIMIT

    def test_account_of_another_organisation_cannot_join_a_full_tenant(self, real_app):
        set_limit(LIMIT)
        tenant = make_tenant(accounts=LIMIT)
        make_tenant('gamma.example', accounts=1)
        service = TeamsService(make_workspace(tenant))
        outsider = User.query.filter_by(email='member0@gamma.example').one()

        _, user, _ = service.get_or_provision_user(oid(1), 'member0@gamma.example', 'Guest')

        assert user is None
        assert TenantMembership.query.filter_by(tenant_id=tenant.id, user_id=outsider.id).count() == 0

    def test_person_refused_at_the_limit_is_told_why_and_can_do_nothing(self, real_app):
        set_limit(LIMIT)
        tenant = make_tenant(accounts=LIMIT)
        service = TeamsService(make_workspace(tenant))
        activity = {
            'type': 'invoke', 'name': 'adaptiveCard/action', 'channelId': 'msteams',
            'channelData': {'tenant': {'id': MS_TENANT}},
            'conversation': {'id': 'c1', 'tenantId': MS_TENANT},
            'from': {'id': '29:x', 'aadObjectId': oid(1), 'name': 'New Comer',
                     'userPrincipalName': f'newcomer@{DOMAIN}'},
            'value': {'action': 'list_decisions'},
        }

        response = asyncio.run(service.handle_invoke(activity))

        assert f'maximum user limit of {LIMIT}' in json.dumps(response)
        assert User.query.count() == LIMIT


class TestNewTenantThroughTheBotMatchesTeamsSignIn:

    def sign_in(self, real_app, monkeypatch, email, name, object_id):
        """Create an account through POST /api/teams/sso/validate with a token taken as valid."""
        import feature_flags
        from ee.backend.oauth_providers import microsoft_oauth
        from ee.backend.teams import teams_security
        app_module, test_app = real_app
        # What the validator returns for a verified token. The route reads the
        # identity from raw_claims (issuer for the token's tenant, oid, tid and
        # the sign-in name) and issues the tab token itself.
        raw_claims = {
            'iss': f'https://login.microsoftonline.com/{MS_TENANT}/v2.0',
            'oid': object_id, 'tid': MS_TENANT, 'name': name, 'preferred_username': email,
        }
        claims = {'email': email, 'name': name, 'oid': object_id, 'tid': MS_TENANT,
                  'raw_claims': raw_claims}
        monkeypatch.setattr(microsoft_oauth, 'validate_teams_sso_token',
                            lambda token, *args, **kwargs: dict(claims))
        monkeypatch.setattr(teams_security, 'get_teams_bot_app_id', lambda: 'test-teams-app-id')
        monkeypatch.setitem(feature_flags.FEATURES, 'teams_integration', True)
        response = test_app.test_client().post('/api/teams/sso/validate', json={'token': 'teams-token'})
        assert response.status_code == 200, response.get_data(as_text=True)

    def describe(self, domain, first_email, second_email):
        """Everything about a tenant that should not depend on how it was created."""
        tenant = Tenant.query.filter_by(domain=domain).one()
        auth_config = AuthConfig.query.filter_by(domain=domain).one()
        approval = DomainApproval.query.filter_by(domain=domain).one()
        first = User.query.filter_by(email=first_email).one()
        second = User.query.filter_by(email=second_email).one()

        def role(user):
            return TenantMembership.query.filter_by(user_id=user.id, tenant_id=tenant.id).one().global_role

        return {
            'tenant_status': tenant.status,
            'maturity_state': tenant.maturity_state,
            'auth_config': {field: getattr(auth_config, field) for field in AUTH_CONFIG_FIELDS},
            'approval_status': approval.status,
            'approval_auto': approval.auto_approved,
            'approval_reviewed': approval.reviewed_at is not None,
            'approval_requested_by_first_user': approval.requested_by_email == first_email,
            'first_role': role(first),
            'first_is_admin': first.is_admin,
            'first_sso_domain_is_tenant': first.sso_domain == domain,
            'second_role': role(second),
            'second_is_admin': second.is_admin,
        }

    def test_same_configuration_as_teams_sign_in(self, real_app, monkeypatch):
        # Through Teams sign-in
        self.sign_in(real_app, monkeypatch, 'first@signin.example', 'First Person', oid(1))
        self.sign_in(real_app, monkeypatch, 'second@signin.example', 'Second Person', oid(2))

        # Through the bot, from a workspace not yet linked to an organisation
        workspace = make_workspace(ms_tenant_id='22222222-2222-2222-2222-222222222222')
        service = TeamsService(workspace)
        _, first, _ = service.get_or_provision_user(oid(3), 'first@bot.example', 'First Person')
        _, second, _ = service.get_or_provision_user(oid(4), 'second@bot.example', 'Second Person')
        assert first is not None and second is not None

        through_sign_in = self.describe('signin.example', 'first@signin.example', 'second@signin.example')
        through_bot = self.describe('bot.example', 'first@bot.example', 'second@bot.example')

        assert through_bot == through_sign_in
        # and the values themselves, so the comparison cannot pass on two wrong sides
        assert through_bot['maturity_state'] == MaturityState.BOOTSTRAP
        assert through_bot['first_role'] == GlobalRole.PROVISIONAL_ADMIN
        assert through_bot['first_is_admin'] is True
        assert through_bot['second_role'] == GlobalRole.USER
        assert through_bot['second_is_admin'] is False
        assert through_bot['auth_config']['require_approval'] is True
        assert through_bot['approval_status'] == 'approved'

    def test_new_tenant_is_linked_and_has_a_default_space(self, real_app):
        workspace = make_workspace()
        service = TeamsService(workspace)

        _, user, _ = service.get_or_provision_user(oid(1), 'first@bot.example', 'First Person')

        tenant = Tenant.query.filter_by(domain='bot.example').one()
        assert db.session.get(TeamsWorkspace, workspace.id).tenant_id == tenant.id
        assert Space.query.filter_by(tenant_id=tenant.id, is_default=True).count() == 1
        assert user.auth_type == 'teams'
        assert user.aad_object_id == oid(1)
        assert user.email_verified is True

    def test_existing_tenant_keeps_its_configuration(self, real_app):
        tenant = make_tenant('bot.example', accounts=1)
        db.session.add(AuthConfig(domain='bot.example', auth_method='sso', allow_password=False,
                                  require_approval=False))
        db.session.commit()
        service = TeamsService(make_workspace())

        _, user, _ = service.get_or_provision_user(oid(1), 'later@bot.example', 'Later Person')

        auth_config = AuthConfig.query.filter_by(domain='bot.example').one()
        assert (auth_config.auth_method, auth_config.allow_password, auth_config.require_approval) == \
            ('sso', False, False)
        membership = TenantMembership.query.filter_by(user_id=user.id, tenant_id=tenant.id).one()
        assert membership.global_role == GlobalRole.USER
        assert user.is_admin is False

    @pytest.mark.parametrize('domain', ['gmail.com', 'outlook.com'])
    def test_personal_mail_domains_get_no_tenant(self, real_app, domain):
        service = TeamsService(make_workspace())

        _, user, needs_linking = service.get_or_provision_user(oid(1), f'someone@{domain}', 'Some One')

        assert user is None and needs_linking is True
        assert Tenant.query.filter_by(domain=domain).first() is None
        assert User.query.count() == 0

    def test_a_tenants_own_onmicrosoft_domain_gets_an_organisation(self, real_app):
        tenant = TeamsService.find_or_create_tenant_for_domain('contoso.onmicrosoft.com')
        assert tenant is not None and tenant.domain == 'contoso.onmicrosoft.com'

    def test_the_bare_onmicrosoft_domain_gets_no_organisation(self, real_app):
        assert TeamsService.find_or_create_tenant_for_domain('onmicrosoft.com') is None
        assert Tenant.query.count() == 0

    def test_deleted_tenant_is_not_joined(self, real_app):
        from datetime import datetime, timezone
        tenant = make_tenant('bot.example', accounts=1)
        tenant.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        service = TeamsService(make_workspace())

        _, user, _ = service.get_or_provision_user(oid(1), 'later@bot.example', 'Later Person')

        assert user is None
        assert User.query.filter_by(email='later@bot.example').first() is None

    def test_workspace_of_a_deleted_tenant_provisions_nobody(self, real_app):
        from datetime import datetime, timezone
        tenant = make_tenant('bot.example', accounts=1)
        service = TeamsService(make_workspace(tenant))
        tenant.deleted_at = datetime.now(timezone.utc)
        db.session.commit()

        _, user, needs_linking = service.get_or_provision_user(oid(1), 'later@bot.example', 'Later Person')

        assert user is None and needs_linking is True
        assert User.query.filter_by(email='later@bot.example').first() is None
