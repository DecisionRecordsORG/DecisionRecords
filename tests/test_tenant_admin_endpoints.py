"""
Who counts as a tenant administrator, and two endpoints the organisation
settings page calls on every visit.

A person's role in their organisation is on their membership
(`tenant_memberships.global_role`). The `users.is_admin` column is older: it
is set for the first account of an organisation and by the legacy "make
admin" switch, and is not changed when a member is promoted through a role
request. Someone whose administrator role exists only on the membership must
be treated as the administrator they are.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import feature_flags
from models import (
    db, User, Tenant, TenantMembership, AccessRequest, GlobalRole, MaturityState,
    DEFAULT_MASTER_PASSWORD, DEFAULT_MASTER_USERNAME
)
from tests.app_test_utils import load_test_app

DOMAIN = 'acme.test'
OTHER = 'globex.test'
PASSWORD = 'Str0ngPassword'
DISMISS = '/api/user/dismiss-admin-onboarding'
AI_CONFIG = '/api/tenant/ai/config'

community_only = pytest.mark.skipif(
    feature_flags.is_enterprise(), reason='Community Edition behaviour')


@pytest.fixture
def real_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-tenant-admin')

    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def make_member(local, role, *, legacy_admin=False, domain=DOMAIN, membership=True):
    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        tenant = Tenant(domain=domain, name=domain, status='active', maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(tenant)
        db.session.flush()
    user = User(email=f'{local}@{domain}', sso_domain=domain, auth_type='local', email_verified=True,
                is_admin=legacy_admin)
    user.set_name(first_name=local.capitalize(), last_name='Member')
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.flush()
    if membership:
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    db.session.commit()
    return user


def sign_in(test_app, local, domain=DOMAIN):
    client = test_app.test_client()
    response = client.post('/api/auth/login', json={'email': f'{local}@{domain}', 'password': PASSWORD})
    assert response.status_code == 200, response.get_json()
    client.environ_base['HTTP_X_CSRF_TOKEN'] = response.headers['X-CSRF-Token']
    return client


def super_admin(test_app):
    client = test_app.test_client()
    response = client.post('/auth/local', json={
        'username': DEFAULT_MASTER_USERNAME, 'password': DEFAULT_MASTER_PASSWORD})
    assert response.status_code == 200, response.get_json()
    client.environ_base['HTTP_X_CSRF_TOKEN'] = response.headers.get('X-CSRF-Token', '')
    return client


# Role on the membership, value of the legacy users.is_admin column
ADMIN_ROLES = [GlobalRole.ADMIN, GlobalRole.PROVISIONAL_ADMIN, GlobalRole.STEWARD]


# ==================== Dismissing the first-admin onboarding dialog ====================

class TestDismissAdminOnboarding:
    """The dialog is shown to whoever /api/user/me reports as is_admin; the same people can dismiss it."""

    @pytest.mark.parametrize('role', ADMIN_ROLES, ids=lambda role: role.value)
    def test_role_on_the_membership_alone_is_enough(self, real_app, role):
        _, test_app = real_app
        user_id = make_member('pat', role, legacy_admin=False).id
        client = sign_in(test_app, 'pat')
        assert client.get('/api/user/me').get_json()['is_admin'] is True  # the app shows the dialog

        response = client.post(DISMISS)

        assert response.status_code == 200, response.get_json()
        assert response.get_json()['user']['has_seen_admin_onboarding'] is True
        assert db.session.get(User, user_id).has_seen_admin_onboarding is True
        # It stays dismissed on the next visit
        assert client.get('/api/user/me').get_json()['has_seen_admin_onboarding'] is True

    def test_ordinary_member_is_refused(self, real_app):
        _, test_app = real_app
        user_id = make_member('pat', GlobalRole.USER).id

        response = sign_in(test_app, 'pat').post(DISMISS)

        assert response.status_code == 403
        assert response.get_json() == {'error': 'Not an admin'}
        assert db.session.get(User, user_id).has_seen_admin_onboarding is not True

    def test_account_without_a_membership_falls_back_to_the_legacy_column(self, real_app):
        _, test_app = real_app
        make_member('legacy', GlobalRole.USER, legacy_admin=True, membership=False)
        make_member('plain', GlobalRole.USER, legacy_admin=False, membership=False)

        assert sign_in(test_app, 'legacy').post(DISMISS).status_code == 200
        assert sign_in(test_app, 'plain').post(DISMISS).status_code == 403

    def test_dismissing_changes_only_the_caller(self, real_app):
        _, test_app = real_app
        make_member('pat', GlobalRole.ADMIN)
        other_id = make_member('sam', GlobalRole.ADMIN, domain=OTHER).id
        colleague_id = make_member('kim', GlobalRole.ADMIN).id

        sign_in(test_app, 'pat').post(DISMISS)

        assert db.session.get(User, other_id).has_seen_admin_onboarding is not True
        assert db.session.get(User, colleague_id).has_seen_admin_onboarding is not True

    def test_anonymous_and_super_admin(self, real_app):
        _, test_app = real_app

        assert test_app.test_client().post(DISMISS).status_code == 401
        assert super_admin(test_app).post(DISMISS).status_code == 400


# ==================== @admin_required ====================

class TestAdminRequired:
    """Routes for tenant administrators accept an administrator whose role is on the membership."""

    USERS = '/api/admin/users'
    PENDING = '/api/admin/access-requests/pending'

    @pytest.mark.parametrize('role', [GlobalRole.ADMIN, GlobalRole.PROVISIONAL_ADMIN], ids=lambda role: role.value)
    @pytest.mark.parametrize('legacy_admin', [False, True], ids=['membership only', 'membership and legacy column'])
    def test_administrator_is_admitted(self, real_app, role, legacy_admin):
        _, test_app = real_app
        make_member('pat', role, legacy_admin=legacy_admin)
        client = sign_in(test_app, 'pat')

        assert client.get(self.USERS).status_code == 200
        assert client.get(self.PENDING).status_code == 200

    def test_ordinary_member_is_refused(self, real_app):
        _, test_app = real_app
        make_member('pat', GlobalRole.USER)

        response = sign_in(test_app, 'pat').get(self.USERS)

        assert response.status_code == 403
        assert response.get_json() == {'error': 'Admin access required'}

    def test_steward_is_refused_as_before(self, real_app):
        """Stewards are not let into the administrator routes by this change (see the report in the PR)."""
        _, test_app = real_app
        make_member('pat', GlobalRole.STEWARD)
        client = sign_in(test_app, 'pat')

        assert client.get(self.USERS).status_code == 403
        assert client.get(self.PENDING).status_code == 403

    def test_legacy_column_still_admits(self, real_app):
        """Nobody who has access today loses it."""
        _, test_app = real_app
        make_member('first', GlobalRole.USER, legacy_admin=True)
        make_member('nomembership', GlobalRole.USER, legacy_admin=True, membership=False)

        assert sign_in(test_app, 'first').get(self.USERS).status_code == 200
        assert sign_in(test_app, 'nomembership').get(self.USERS).status_code == 200

    def test_administrator_sees_only_their_own_organisation(self, real_app):
        _, test_app = real_app
        make_member('pat', GlobalRole.ADMIN)
        make_member('sam', GlobalRole.ADMIN, domain=OTHER)
        db.session.add(AccessRequest(email=f'new@{OTHER}', name='New Comer', domain=OTHER, reason='x'))
        db.session.commit()
        request_id = AccessRequest.query.one().id
        client = sign_in(test_app, 'pat')

        users = client.get(self.USERS).get_json()
        pending = client.get(self.PENDING).get_json()
        approval = client.post(f'/api/admin/access-requests/{request_id}/approve', json={})

        assert {user['email'] for user in users} == {f'pat@{DOMAIN}'}
        assert pending == []
        assert approval.status_code == 403
        assert User.query.filter_by(email=f'new@{OTHER}').first() is None

    def test_role_in_another_organisation_does_not_count(self, real_app):
        """An administrator membership elsewhere is not an administrator of the account's own organisation."""
        _, test_app = real_app
        user = make_member('pat', GlobalRole.USER)
        make_member('sam', GlobalRole.ADMIN, domain=OTHER)
        other = Tenant.query.filter_by(domain=OTHER).first()
        db.session.add(TenantMembership(user_id=user.id, tenant_id=other.id, global_role=GlobalRole.ADMIN))
        db.session.commit()

        assert sign_in(test_app, 'pat').get(self.USERS).status_code == 403

    def test_membership_only_administrator_can_approve_a_request(self, real_app):
        _, test_app = real_app
        make_member('pat', GlobalRole.ADMIN, legacy_admin=False)
        db.session.add(AccessRequest(email=f'new@{DOMAIN}', name='New Comer', domain=DOMAIN, reason='x'))
        db.session.commit()
        request_id = AccessRequest.query.one().id

        response = sign_in(test_app, 'pat').post(f'/api/admin/access-requests/{request_id}/approve', json={})

        assert response.status_code == 200, response.get_json()
        assert User.query.filter_by(email=f'new@{DOMAIN}').count() == 1

    def test_anonymous_and_super_admin(self, real_app):
        _, test_app = real_app
        make_member('pat', GlobalRole.ADMIN)

        assert test_app.test_client().get(self.USERS).status_code == 401
        assert super_admin(test_app).get(self.USERS).status_code == 200


# ==================== Tenant AI settings in Community Edition ====================

@community_only
class TestTenantAiConfigInCommunity:
    """The organisation settings page asks for the AI settings on every visit."""

    EXPECTED = {
        'available': False,
        'system_ai_enabled': False,
        'system_slack_bot_enabled': False,
        'system_mcp_enabled': False,
        'system_external_api_enabled': False,
        'ai_features_enabled': False,
        'ai_slack_queries_enabled': False,
        'ai_assisted_creation_enabled': False,
        'ai_external_access_enabled': False,
        'ai_require_anonymization': False,
        'ai_log_interactions': False,
    }

    @pytest.mark.parametrize('role', ADMIN_ROLES, ids=lambda role: role.value)
    def test_reading_answers_not_available_instead_of_failing(self, real_app, role):
        _, test_app = real_app
        make_member('pat', role)

        response = sign_in(test_app, 'pat').get(AI_CONFIG)

        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json() == self.EXPECTED

    def test_ordinary_member_is_still_refused(self, real_app):
        _, test_app = real_app
        make_member('pat', GlobalRole.USER)

        response = sign_in(test_app, 'pat').get(AI_CONFIG)

        assert response.status_code == 403

    def test_anonymous_caller_is_refused(self, real_app):
        _, test_app = real_app

        assert test_app.test_client().get(AI_CONFIG).status_code == 401

    def test_saving_is_refused_cleanly_and_changes_nothing(self, real_app):
        _, test_app = real_app
        make_member('pat', GlobalRole.ADMIN)

        response = sign_in(test_app, 'pat').put(AI_CONFIG, json={'ai_features_enabled': True})

        assert response.status_code == 403
        assert response.get_json() == {'error': 'AI features are not enabled at system level'}
        assert Tenant.query.filter_by(domain=DOMAIN).first().ai_features_enabled is not True
