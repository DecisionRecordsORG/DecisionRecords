"""
Tests for two rules of the AI interfaces (Enterprise Edition): MCP in
ee/backend/ai/mcp/server.py and the external AI API in ee/backend/ai/api/routes.py.

1. People in results are given by id and display name only: never the account
   record (sign-in method, passkey state, ...) and never an email address.
2. An API key stops working when its owner's account was anonymised or deleted,
   when the organisation was deleted, or when the owner is no longer a member.
   A key of a current member works as before.

Note: These tests require Enterprise Edition modules from ee/backend/ai/
"""
import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, SystemConfig, GlobalRole, MaturityState,
    ArchitectureDecision, DecisionComment, AIApiKey, save_history
)

# Enterprise Edition imports - skip tests if not available
try:
    from ee.backend.ai import AIApiKeyService
    from ee.backend.ai.mcp.server import MCPToolHandler, handle_mcp_message, INVALID_KEY_ERROR
    from ee.backend.ai.people import display_name, user_ref, owner_ref, comment_author_name
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    AIApiKeyService = None
    MCPToolHandler = None
    handle_mcp_message = None
    INVALID_KEY_ERROR = None
    display_name = user_ref = owner_ref = comment_author_name = None

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

# Fields of User.to_dict() that describe the account, not the person's name.
ACCOUNT_FIELDS = (
    'email', 'auth_type', 'has_passkey', 'has_password', 'has_seen_admin_onboarding',
    'sso_domain', 'is_admin', 'email_verified', 'last_login', 'first_name', 'last_name',
    'deletion_requested_at', 'deletion_scheduled_at',
)


def _enable_ai(tenant):
    SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
    SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
    SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
    tenant.ai_features_enabled = True
    tenant.ai_external_access_enabled = True
    tenant.ai_log_interactions = False
    db.session.commit()


def _user(email, first_name=None, last_name=None, domain='example.com'):
    user = User(email=email, sso_domain=domain, auth_type='local', email_verified=True)
    if first_name or last_name:
        user.set_name(first_name=first_name, last_name=last_name)
    db.session.add(user)
    db.session.commit()
    return user


def _decision(tenant, creator, number=1, **fields):
    decision = ArchitectureDecision(
        title=fields.pop('title', f'Decision {number}'),
        context='Context',
        decision='What was decided',
        consequences='Consequences',
        status='proposed',
        domain=tenant.domain,
        tenant_id=tenant.id,
        created_by_id=creator.id,
        decision_number=number,
        **fields,
    )
    db.session.add(decision)
    db.session.commit()
    return decision


def _tools_call(key, name, arguments):
    payload, status = handle_mcp_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }, key)
    return payload, status


def _structured(payload):
    result = payload['result']
    assert result.get('isError') is not True, result
    return result['structuredContent']


def _no_email_anywhere(value, emails):
    text = json.dumps(value)
    for email in emails:
        assert email not in text, f'{email} appears in the result'


# ============================================================================
# DISPLAY NAMES
# ============================================================================

class TestDisplayName:
    """ee/backend/ai/people.py: the one place that decides how a person is named."""

    def test_full_name_is_used(self, app, session):
        user = _user('ada@example.com', 'Ada', 'Lovelace')
        assert display_name(user) == 'Ada Lovelace'
        assert user_ref(user) == {'id': user.id, 'name': 'Ada Lovelace'}

    def test_without_a_name_the_part_before_the_at_sign_is_used(self, app, session):
        user = _user('grace.hopper@example.com')
        assert display_name(user) == 'grace.hopper'

    def test_an_address_stored_as_the_name_is_not_returned(self, app, session):
        user = _user('alan@example.com')
        user.name = 'alan@example.com'
        session.commit()
        assert display_name(user) == 'alan'

    def test_no_user_gives_none(self, app, session):
        assert display_name(None) is None
        assert user_ref(None) is None

    def test_owner_with_an_account(self, app, session, sample_tenant):
        creator = _user('creator@example.com', 'Cre', 'Ator')
        owner = _user('owner@example.com', 'Own', 'Er')
        decision = _decision(sample_tenant, creator, owner_id=owner.id)
        assert owner_ref(decision) == {'id': owner.id, 'name': 'Own Er'}

    def test_owner_known_by_address_only(self, app, session, sample_tenant):
        creator = _user('creator@example.com', 'Cre', 'Ator')
        decision = _decision(sample_tenant, creator, owner_email='outside.owner@partner.test')
        assert owner_ref(decision) == {'id': None, 'name': 'outside.owner'}

    def test_no_owner(self, app, session, sample_tenant):
        creator = _user('creator@example.com', 'Cre', 'Ator')
        assert owner_ref(_decision(sample_tenant, creator)) is None

    def test_comment_author_falls_back_without_an_address(self, app, session, sample_tenant):
        creator = _user('creator@example.com', 'Cre', 'Ator')
        decision = _decision(sample_tenant, creator)
        comment = DecisionComment(
            decision_id=decision.id, tenant_id=sample_tenant.id, user_id=None,
            author_display='gone@example.com', body='Text',
        )
        session.add(comment)
        session.commit()
        assert comment_author_name(comment) == 'gone'

        comment.author_display = None
        assert comment_author_name(comment) == 'Unknown'


# ============================================================================
# MCP RESULT SHAPES
# ============================================================================

class TestMcpResultsNamePeopleByIdAndName:
    """What an MCP client receives about the people on a decision."""

    @pytest.fixture
    def world(self, session, sample_tenant):
        _enable_ai(sample_tenant)
        named = _user('named.person@example.com', 'Named', 'Person')
        nameless = _user('nameless.person@example.com')
        for user in (named, nameless):
            session.add(TenantMembership(user_id=user.id, tenant_id=sample_tenant.id, global_role=GlobalRole.USER))
        session.commit()
        _, key = AIApiKeyService.create_key(named, sample_tenant, 'Key', scopes=['read', 'search', 'write'])
        return {'tenant': sample_tenant, 'named': named, 'nameless': nameless, 'key': key}

    def test_get_decision_gives_id_and_name_only(self, app, session, world):
        decision = _decision(world['tenant'], world['named'], owner_id=world['nameless'].id)
        decision.updated_by_id = world['nameless'].id
        session.commit()

        payload, status = _tools_call(world['key'], 'get_decision', {'id': str(decision.id)})
        assert status == 200
        data = _structured(payload)

        assert data['created_by'] == {'id': world['named'].id, 'name': 'Named Person'}
        assert data['updated_by'] == {'id': world['nameless'].id, 'name': 'nameless.person'}
        assert data['owner'] == {'id': world['nameless'].id, 'name': 'nameless.person'}
        for person in (data['created_by'], data['updated_by'], data['owner']):
            assert set(person) == {'id', 'name'}
            for field in ACCOUNT_FIELDS:
                assert field not in person
        _no_email_anywhere(payload, ['named.person@example.com', 'nameless.person@example.com'])

    def test_get_decision_drops_internal_fields(self, app, session, world):
        decision = _decision(world['tenant'], world['named'], owner_email='outside.owner@partner.test')
        data = _structured(_tools_call(world['key'], 'get_decision', {'id': str(decision.id)})[0])

        for removed in ('creator', 'owner_email', 'tenant_id', 'domain'):
            assert removed not in data
        assert data['owner'] == {'id': None, 'name': 'outside.owner'}
        _no_email_anywhere(data, ['outside.owner@partner.test'])
        # What a client reads a decision for is still there
        for kept in ('id', 'display_id', 'title', 'status', 'context', 'decision', 'consequences',
                     'section_headings', 'outgoing_relationships', 'incoming_relationships'):
            assert kept in data

    def test_get_decision_without_people(self, app, session, world):
        decision = _decision(world['tenant'], world['named'])
        data = _structured(_tools_call(world['key'], 'get_decision', {'id': str(decision.id)})[0])
        assert data['updated_by'] is None
        assert data['owner'] is None

    def test_create_decision_result_has_the_same_shape(self, app, session, world):
        payload, _ = _tools_call(world['key'], 'create_decision', {
            'title': 'Adopt a thing', 'context': 'Because', 'decision': 'We do', 'consequences': 'Then',
        })
        _no_email_anywhere(payload, ['named.person@example.com'])
        text = json.dumps(payload)
        for field in ('auth_type', 'has_passkey', 'has_seen_admin_onboarding'):
            assert field not in text

    def test_history_names_the_editor_without_an_address(self, app, session, world):
        decision = _decision(world['tenant'], world['nameless'])
        save_history(decision, 'Edited', world['nameless'])
        session.commit()

        payload, _ = _tools_call(world['key'], 'get_decision_history', {'id': str(decision.id)})
        data = _structured(payload)
        entries = data['history'] if isinstance(data, dict) and 'history' in data else data
        assert entries, data
        assert entries[0]['changed_by'] == 'nameless.person'
        _no_email_anywhere(payload, ['nameless.person@example.com'])

    def test_comments_name_the_author_without_an_address(self, app, session, world):
        decision = _decision(world['tenant'], world['named'])
        session.add(DecisionComment(
            decision_id=decision.id, tenant_id=world['tenant'].id, user_id=world['nameless'].id,
            author_display='nameless.person@example.com', body='A remark',
        ))
        session.commit()

        payload, _ = _tools_call(world['key'], 'list_decision_comments', {'id': str(decision.id)})
        data = _structured(payload)
        assert data['comments'][0]['author'] == 'nameless.person'
        _no_email_anywhere(payload, ['nameless.person@example.com'])

    def test_search_and_list_carry_no_account_data(self, app, session, world):
        _decision(world['tenant'], world['nameless'], title='Findable decision')
        for tool, arguments in (('search_decisions', {'query': 'Findable'}), ('list_decisions', {})):
            payload, _ = _tools_call(world['key'], tool, arguments)
            assert _structured(payload)['decisions']
            _no_email_anywhere(payload, ['named.person@example.com', 'nameless.person@example.com'])


# ============================================================================
# STALE KEYS: THE RULE
# ============================================================================

class TestKeyOwnerMustStillBelong:
    """AIApiKeyService.resolve_owner and the MCP entry point that uses it."""

    @pytest.fixture
    def member(self, session, sample_user, sample_tenant, sample_membership, sample_decision):
        _enable_ai(sample_tenant)
        key_record, key = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Key', scopes=['read', 'search', 'write']
        )
        return {'user': sample_user, 'tenant': sample_tenant, 'membership': sample_membership,
                'record': key_record, 'key': key, 'decision': sample_decision}

    @staticmethod
    def _list(key):
        return handle_mcp_message({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, key)

    def _assert_refused(self, key):
        payload, status = self._list(key)
        assert status == 401
        assert payload['error']['code'] == 401
        assert payload['error']['message'] == INVALID_KEY_ERROR

        payload, status = _tools_call(key, 'list_decisions', {})
        assert status == 401
        assert 'result' not in payload

    def test_a_current_member_is_served_as_before(self, app, session, member):
        assert AIApiKeyService.resolve_owner(member['record']) == (member['user'], member['tenant'])

        payload, status = self._list(member['key'])
        assert status == 200
        assert payload['result']['tools']

        payload, status = _tools_call(member['key'], 'get_decision', {'id': str(member['decision'].id)})
        assert status == 200
        assert _structured(payload)['id'] == member['decision'].id

        payload, status = _tools_call(member['key'], 'add_decision_comment', {
            'id': str(member['decision'].id), 'body': 'Still allowed to write',
        })
        assert status == 200
        assert payload['result'].get('isError') is not True

    def test_removed_member_is_refused(self, app, session, member):
        session.delete(member['membership'])
        session.commit()

        assert AIApiKeyService.resolve_owner(member['record']) is None
        self._assert_refused(member['key'])
        # The key itself was not touched: the refusal comes from the membership
        assert db.session.get(AIApiKey, member['record'].id).revoked_at is None

    def test_member_of_another_organisation_only_is_refused(self, app, session, member):
        other = Tenant(domain='other.org', name='Other', status='active', maturity_state=MaturityState.BOOTSTRAP)
        session.add(other)
        session.flush()
        member['membership'].tenant_id = other.id
        session.commit()

        self._assert_refused(member['key'])

    def test_anonymised_user_is_refused(self, app, session, member):
        member['user'].is_anonymized = True
        session.commit()

        assert AIApiKeyService.resolve_owner(member['record']) is None
        self._assert_refused(member['key'])

    def test_deleted_user_is_refused(self, app, session, member):
        member['user'].deleted_at = datetime.now(timezone.utc)
        session.commit()

        self._assert_refused(member['key'])

    def test_deleted_tenant_is_refused(self, app, session, member):
        # The state a super admin's deletion leaves for 30 days: the row and
        # the memberships are still there.
        member['tenant'].deleted_at = datetime.now(timezone.utc)
        member['tenant'].status = 'deleted'
        session.commit()

        assert AIApiKeyService.resolve_owner(member['record']) is None
        self._assert_refused(member['key'])

    def test_restored_tenant_is_served_again(self, app, session, member):
        member['tenant'].deleted_at = datetime.now(timezone.utc)
        session.commit()
        self._assert_refused(member['key'])

        member['tenant'].deleted_at = None
        session.commit()
        assert self._list(member['key'])[1] == 200

    def test_no_write_reaches_a_deleted_tenant(self, app, session, member):
        member['tenant'].deleted_at = datetime.now(timezone.utc)
        session.commit()
        before = ArchitectureDecision.query.filter_by(tenant_id=member['tenant'].id).count()

        _tools_call(member['key'], 'create_decision', {
            'title': 'Should not exist', 'context': 'c', 'decision': 'd', 'consequences': 'q',
        })

        assert ArchitectureDecision.query.filter_by(tenant_id=member['tenant'].id).count() == before

    def test_erasing_the_account_ends_the_key_twice_over(self, app, session, member):
        """Erasure already revokes the keys; the owner check refuses them as well."""
        import retention
        key_id, user_id = member['record'].id, member['user'].id

        assert retention.anonymize_user(user_id) is True

        assert db.session.get(AIApiKey, key_id).revoked_at is not None
        assert TenantMembership.query.filter_by(user_id=user_id).count() == 0
        self._assert_refused(member['key'])


# ============================================================================
# STALE KEYS: THE HTTP ENDPOINTS
# ============================================================================

def _ensure_testing_env():
    if os.environ.get('FLASK_ENV') != 'testing':
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['TESTING'] = 'True'


_ensure_testing_env()


class TestStaleKeysThroughTheRealApp:
    """/api/mcp and /api/ai of app.py with the Enterprise blueprints registered."""

    @pytest.fixture
    def real_app(self):
        _ensure_testing_env()
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, real_app):
        return real_app.test_client()

    @pytest.fixture
    def setup(self, real_app):
        tenant = Tenant(domain='stale.test', name='Stale Test', status='active',
                        maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(tenant)
        db.session.flush()
        _enable_ai(tenant)
        user = _user('nameless.member@stale.test', domain='stale.test')
        membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER)
        db.session.add(membership)
        db.session.commit()
        decision = _decision(tenant, user, owner_email='outside.owner@partner.test')
        save_history(decision, 'Edited', user)
        db.session.commit()
        _, key = AIApiKeyService.create_key(user, tenant, 'Key', scopes=['read', 'search', 'write'])
        return {'tenant': tenant, 'user': user, 'membership': membership, 'decision': decision,
                'headers': {'Authorization': f'Bearer {key}'}}

    @staticmethod
    def _mcp(client, headers):
        return client.post('/api/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, headers=headers)

    def _assert_both_refuse(self, client, setup):
        response = self._mcp(client, setup['headers'])
        assert response.status_code == 401
        assert response.headers.get('WWW-Authenticate', '').startswith('Bearer')
        assert response.get_json()['error']['message'] == INVALID_KEY_ERROR

        for path in ('/api/ai/decisions', f"/api/ai/decisions/{setup['decision'].id}"):
            response = client.get(path, headers=setup['headers'])
            assert response.status_code == 401
            assert response.get_json() == {'error': 'Invalid or expired API key'}

        response = client.post('/api/ai/decisions', headers=setup['headers'], json={
            'title': 'Should not exist', 'context': 'c', 'decision': 'd', 'consequences': 'q',
        })
        assert response.status_code == 401

    def test_current_member_is_served(self, client, setup):
        assert self._mcp(client, setup['headers']).status_code == 200
        assert client.get('/api/ai/decisions', headers=setup['headers']).status_code == 200

    def test_removed_member_is_refused(self, client, setup):
        db.session.delete(setup['membership'])
        db.session.commit()
        self._assert_both_refuse(client, setup)

    def test_anonymised_user_is_refused(self, client, setup):
        setup['user'].is_anonymized = True
        db.session.commit()
        self._assert_both_refuse(client, setup)

    def test_deleted_tenant_is_refused(self, client, setup):
        setup['tenant'].deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        self._assert_both_refuse(client, setup)
        assert ArchitectureDecision.query.filter_by(tenant_id=setup['tenant'].id).count() == 1

    def test_external_api_names_people_without_addresses(self, client, setup):
        response = client.get(f"/api/ai/decisions/{setup['decision'].id}", headers=setup['headers'])
        assert response.status_code == 200
        body = response.get_json()
        text = json.dumps(body)
        assert 'nameless.member@stale.test' not in text
        assert 'outside.owner@partner.test' not in text
        assert 'nameless.member' in text
        assert 'outside.owner' in text

        response = client.get(f"/api/ai/decisions/{setup['decision'].id}/history", headers=setup['headers'])
        assert response.status_code == 200
        text = json.dumps(response.get_json())
        assert 'nameless.member@stale.test' not in text
        assert 'nameless.member' in text
