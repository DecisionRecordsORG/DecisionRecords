"""
"AI Processing" on the profile page has one source of truth: the membership's
`ai_opt_out`, which every AI access check reads (/api/ai, /api/mcp, creating an
API key, connecting an application).

Before, the switch read `user_consents` (off without a record) while the
checks read `ai_opt_out` (not opted out by default), so someone whose key
worked saw the switch off. Now:

* the switch shows `not ai_opt_out`, so a person who never touched it sees it on;
* switching it off sets `ai_opt_out` and their keys and connected apps are
  refused with a message saying so; switching it on lets them work again;
* nothing is changed in the database by reading it, so no working key or
  connected application stops working because of this change (no migration:
  the value the checks read is the one that already existed).

The consent row remains the record of when the person last used the switch.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, GlobalRole, MaturityState, SystemConfig, UserConsent,
    ArchitectureDecision,
)
from tests.app_test_utils import load_test_app

try:
    from ee.backend.ai import AIApiKeyService
    EE_AVAILABLE = True
except ImportError:
    AIApiKeyService = None
    EE_AVAILABLE = False

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
needs_ee = pytest.mark.skipif(not EE_TESTS_ENABLED, reason='Enterprise Edition AI modules not available')

DOMAIN = 'ai-switch.test'
PASSWORD = 'a-long-test-password'


@pytest.fixture
def real_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-ai-switch')
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


@pytest.fixture
def tenant(real_app):
    tenant = Tenant(domain=DOMAIN, name='AI switch', status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.commit()
    return tenant


def make_member(tenant, local, ai_opt_out=False):
    user = User(email=f'{local}@{DOMAIN}', sso_domain=DOMAIN, auth_type='local', email_verified=True)
    user.set_name(first_name=local.title(), last_name='Member')
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER,
                                    ai_opt_out=ai_opt_out))
    db.session.commit()
    return user


def signed_in(test_app, user):
    client = test_app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['_csrf_token'] = 'test-csrf-token'
        sess['_expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    client.environ_base['HTTP_X_CSRF_TOKEN'] = 'test-csrf-token'
    return client


def membership_of(user):
    return TenantMembership.query.filter_by(user_id=user.id).one()


def switch(client):
    return client.get('/api/user/consents').get_json()['ai_processing']['granted']


class TestTheSwitchShowsTheRealState:

    def test_someone_who_never_touched_it_sees_it_on(self, real_app, tenant):
        user = make_member(tenant, 'pat')

        assert switch(signed_in(real_app, user)) is True
        assert membership_of(user).ai_opt_out is False

    def test_someone_opted_out_sees_it_off(self, real_app, tenant):
        user = make_member(tenant, 'pat', ai_opt_out=True)

        assert switch(signed_in(real_app, user)) is False

    def test_an_old_refusal_record_does_not_hide_working_access(self, real_app, tenant):
        """A consent row that says off, while the checks let the person's tools work, shows on."""
        user = make_member(tenant, 'pat')
        db.session.add(UserConsent(user_id=user.id, consent_type='ai_processing', granted=False,
                                   withdrawn_at=datetime.now(timezone.utc)))
        db.session.commit()

        assert switch(signed_in(real_app, user)) is True
        # Reading changed nothing: access stays as it was
        db.session.expire_all()
        assert membership_of(user).ai_opt_out is False
        assert UserConsent.query.filter_by(user_id=user.id, consent_type='ai_processing').one().granted is False

    def test_a_null_opt_out_counts_as_not_opted_out(self, real_app, tenant):
        user = make_member(tenant, 'pat')
        membership_of(user).ai_opt_out = None
        db.session.commit()

        assert switch(signed_in(real_app, user)) is True

    def test_without_a_membership_the_default_is_on(self, real_app, tenant):
        user = User(email=f'loner@{DOMAIN}', sso_domain=DOMAIN, auth_type='local', email_verified=True)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()

        assert switch(signed_in(real_app, user)) is True
        assert UserConsent.DEFAULT_GRANTED['ai_processing'] is True

    def test_another_organisations_membership_is_not_read(self, real_app, tenant):
        other = Tenant(domain='elsewhere-ai.test', name='Elsewhere', status='active',
                       maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(other)
        db.session.flush()
        user = make_member(tenant, 'pat')
        db.session.add(TenantMembership(user_id=user.id, tenant_id=other.id, ai_opt_out=True))
        db.session.commit()

        assert switch(signed_in(real_app, user)) is True


class TestSwitchingChangesTheRealState:

    def test_off_sets_the_opt_out_and_records_the_choice(self, real_app, tenant):
        user = make_member(tenant, 'pat')
        client = signed_in(real_app, user)

        response = client.post('/api/user/consents', json={'consent_type': 'ai_processing', 'granted': False})

        assert response.status_code == 200
        db.session.expire_all()
        assert membership_of(user).ai_opt_out is True
        record = UserConsent.query.filter_by(user_id=user.id, consent_type='ai_processing').one()
        assert record.granted is False and record.withdrawn_at is not None
        assert switch(client) is False

    def test_on_again_clears_it(self, real_app, tenant):
        user = make_member(tenant, 'pat', ai_opt_out=True)
        client = signed_in(real_app, user)

        client.post('/api/user/consents', json={'consent_type': 'ai_processing', 'granted': True})

        db.session.expire_all()
        assert membership_of(user).ai_opt_out is False
        assert switch(client) is True

    def test_other_switches_do_not_touch_it(self, real_app, tenant):
        user = make_member(tenant, 'pat')
        client = signed_in(real_app, user)

        client.post('/api/user/consents', json={'consent_type': 'analytics', 'granted': False})
        client.post('/api/user/consents', json={'consent_type': 'email_notifications', 'granted': False})

        db.session.expire_all()
        assert membership_of(user).ai_opt_out is False


@needs_ee
class TestKeysAndConnectionsFollowTheSwitch:

    @pytest.fixture
    def ai_on(self, tenant):
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
        tenant.ai_features_enabled = True
        tenant.ai_external_access_enabled = True
        tenant.ai_log_interactions = False
        db.session.commit()
        return tenant

    @pytest.fixture
    def person(self, real_app, ai_on):
        user = make_member(ai_on, 'pat')
        db.session.add(ArchitectureDecision(title='A decision', context='c', decision='d', consequences='q',
                                            status='accepted', domain=DOMAIN, tenant_id=ai_on.id,
                                            decision_number=1, created_by_id=user.id))
        db.session.commit()
        _, key = AIApiKeyService.create_key(user, ai_on, 'Laptop', scopes=['read', 'search'])
        return {'user': user, 'client': signed_in(real_app, user), 'headers': {'Authorization': f'Bearer {key}'}}

    @staticmethod
    def mcp(client, headers):
        return client.post('/api/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, headers=headers)

    def test_a_key_of_someone_who_never_touched_the_switch_works_and_the_switch_says_on(self, real_app, person):
        anonymous = real_app.test_client()

        assert anonymous.get('/api/ai/decisions', headers=person['headers']).status_code == 200
        assert self.mcp(anonymous, person['headers']).status_code == 200
        assert switch(person['client']) is True

    def test_switching_off_refuses_the_key_at_once_and_says_why(self, real_app, person):
        person['client'].post('/api/user/consents', json={'consent_type': 'ai_processing', 'granted': False})
        anonymous = real_app.test_client()

        response = anonymous.get('/api/ai/decisions', headers=person['headers'])
        assert response.status_code == 403
        assert 'switched off AI Processing' in response.get_json()['error']

        response = self.mcp(anonymous, person['headers'])
        assert response.status_code == 403
        assert 'switched off AI Processing' in response.get_json()['error']['message']

    def test_switching_off_refuses_new_keys(self, real_app, person):
        client = person['client']
        client.post('/api/user/consents', json={'consent_type': 'ai_processing', 'granted': False})

        response = client.post('/api/user/ai/keys', json={'name': 'Another'})

        assert response.status_code == 403
        assert 'switched off AI Processing' in response.get_json()['error']

    def test_switching_on_again_lets_the_same_key_work(self, real_app, person):
        client = person['client']
        client.post('/api/user/consents', json={'consent_type': 'ai_processing', 'granted': False})
        client.post('/api/user/consents', json={'consent_type': 'ai_processing', 'granted': True})

        assert real_app.test_client().get('/api/ai/decisions', headers=person['headers']).status_code == 200
        assert client.post('/api/user/ai/keys', json={'name': 'Another'}).status_code == 201

    def test_the_ai_preferences_route_is_the_same_switch(self, real_app, person):
        client = person['client']

        assert client.put('/api/user/ai/preferences', json={'ai_opt_out': True}).status_code == 200

        assert switch(client) is False
        record = UserConsent.query.filter_by(user_id=person['user'].id, consent_type='ai_processing').one()
        assert record.granted is False
        assert real_app.test_client().get('/api/ai/decisions', headers=person['headers']).status_code == 403
