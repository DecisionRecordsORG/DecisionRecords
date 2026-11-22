"""
Tenant scoping of the Microsoft Teams bot (Enterprise Edition).

Card and form data is chosen by the person sending it. These tests send
actions that name another organisation's decision or space and check that
nothing is shown and nothing changes, that a status change needs an account of
the decision's own organisation, and that correctly scoped actions still work.
"""
import asyncio
import json
import os
import sys

import pytest
from flask import Flask
from unittest.mock import AsyncMock

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if not os.path.exists(os.path.join(_ROOT, 'models.py')):
    _ROOT = os.getcwd()
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from models import (  # noqa: E402
    db, User, Tenant, TenantMembership, Space, DecisionSpace,
    ArchitectureDecision, DecisionHistory, GlobalRole, MaturityState,
    TeamsWorkspace, TeamsUserMapping
)

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

MS_TENANT_A = '11111111-1111-1111-1111-111111111111'
MS_TENANT_B = '22222222-2222-2222-2222-222222222222'
ALICE_OID = 'aaaaaaaa-0000-0000-0000-000000000001'
OUTSIDER_OID = 'aaaaaaaa-0000-0000-0000-000000000002'
SECRET_TITLE = 'Acquire Initech in Q3'
OWN_TITLE = 'Use PostgreSQL for billing'


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _tenant(domain):
    tenant = Tenant(domain=domain, name=domain, status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.flush()
    space = Space(tenant_id=tenant.id, name=f'General {domain}', is_default=True)
    db.session.add(space)
    db.session.flush()
    return tenant, space


def _user(email, tenant=None):
    domain = email.split('@')[1]
    user = User(email=email, sso_domain=domain, auth_type='teams', email_verified=True)
    user.set_name(first_name='Test', last_name='Person')
    db.session.add(user)
    db.session.flush()
    if tenant is not None:
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER))
    return user


def _decision(tenant, space, user, title, number=1, status='proposed'):
    decision = ArchitectureDecision(
        tenant_id=tenant.id, domain=tenant.domain, decision_number=number, title=title,
        context='Context', decision='Decision', consequences='Consequences',
        status=status, created_by_id=user.id, owner_id=user.id
    )
    db.session.add(decision)
    db.session.flush()
    db.session.add(DecisionSpace(decision_id=decision.id, space_id=space.id))
    return decision


class World:
    pass


@pytest.fixture
def world(app):
    """Two organisations, each with a Teams workspace, a space and a decision."""
    w = World()
    w.tenant_a, w.space_a = _tenant('alpha.example')
    w.tenant_b, w.space_b = _tenant('beta.example')
    w.alice = _user('alice@alpha.example', w.tenant_a)
    w.bob = _user('bob@beta.example', w.tenant_b)
    # An account of a third organisation that is linked in workspace A
    w.outsider = _user('olga@gamma.example')
    w.own = _decision(w.tenant_a, w.space_a, w.alice, OWN_TITLE)
    w.other = _decision(w.tenant_b, w.space_b, w.bob, SECRET_TITLE)

    w.workspace_a = TeamsWorkspace(ms_tenant_id=MS_TENANT_A, is_active=True, tenant_id=w.tenant_a.id)
    w.workspace_b = TeamsWorkspace(ms_tenant_id=MS_TENANT_B, is_active=True, tenant_id=w.tenant_b.id)
    db.session.add_all([w.workspace_a, w.workspace_b])
    db.session.flush()
    db.session.add(TeamsUserMapping(
        teams_workspace_id=w.workspace_a.id, aad_object_id=ALICE_OID,
        aad_user_principal_name=w.alice.email, user_id=w.alice.id, link_method='auto_linked'))
    db.session.add(TeamsUserMapping(
        teams_workspace_id=w.workspace_a.id, aad_object_id=OUTSIDER_OID,
        aad_user_principal_name=w.outsider.email, user_id=w.outsider.id, link_method='auto_linked'))
    db.session.commit()

    w.service = TeamsService(w.workspace_a)
    w.sent = []

    async def capture(activity, card):
        w.sent.append(card)
        return True

    w.service.send_reply = capture
    w.service.update_message = capture
    w.service.get_member_info = AsyncMock(side_effect=lambda activity: dict(activity.get('from') or {}))
    w.service.get_user_by_entra_id = AsyncMock(return_value={})
    w.service._send_creation_notification = AsyncMock(return_value=True)
    return w


def activity(kind='invoke', name=None, value=None, oid=ALICE_OID, ms_tenant=MS_TENANT_A, channel='msteams'):
    sender = {'id': '29:sender', 'name': 'Alice Example'}
    if oid:
        sender['aadObjectId'] = oid
    body = {
        'type': kind,
        'id': 'activity-1',
        'channelId': channel,
        'serviceUrl': 'https://smba.trafficmanager.net/emea/',
        'channelData': {'tenant': {'id': ms_tenant}},
        'conversation': {'id': 'conversation-1', 'tenantId': ms_tenant},
        'from': sender,
        'recipient': {'id': '28:bot'},
        'value': value,
    }
    if name:
        body['name'] = name
    return body


def run(coro):
    return asyncio.run(coro)


def text_of(card_or_response):
    return json.dumps(card_or_response, default=str)


def status_of(decision_id):
    db.session.expire_all()
    return db.session.get(ArchitectureDecision, decision_id).status


def history_count(decision_id):
    return DecisionHistory.query.filter_by(decision_id=decision_id).count()


# ---------------------------------------------------------------------------
# Viewing a decision
# ---------------------------------------------------------------------------

class TestViewDecisionIsScopedToTheWorkspaceTenant:

    def test_button_action_refuses_another_tenants_decision(self, world):
        run(world.service.handle_message(activity(
            'message', value={'action': 'view_decision', 'decision_id': world.other.id})))
        assert len(world.sent) == 1
        assert SECRET_TITLE not in text_of(world.sent[0])
        assert 'Not Found' in text_of(world.sent[0])

    def test_button_action_shows_own_decision(self, world):
        run(world.service.handle_message(activity(
            'message', value={'action': 'view_decision', 'decision_id': world.own.id})))
        assert OWN_TITLE in text_of(world.sent[0])

    def test_task_fetch_refuses_another_tenants_decision(self, world):
        response = run(world.service.handle_invoke(activity(
            name='task/fetch', value={'data': {'action': 'view_decision', 'decision_id': world.other.id}})))
        assert SECRET_TITLE not in text_of(response)
        assert 'Not Found' in text_of(response)

    def test_task_fetch_shows_own_decision(self, world):
        response = run(world.service.handle_invoke(activity(
            name='task/fetch', value={'data': {'action': 'view_decision', 'decision_id': world.own.id}})))
        assert OWN_TITLE in text_of(response)

    def test_card_action_refuses_another_tenants_decision(self, world):
        response = run(world.service.handle_invoke(activity(
            name='adaptiveCard/action', value={'action': 'view_decision', 'decision_id': world.other.id})))
        assert SECRET_TITLE not in text_of(response)
        assert 'Not Found' in text_of(response)

    def test_card_action_shows_own_decision(self, world):
        response = run(world.service.handle_invoke(activity(
            name='adaptiveCard/action', value={'action': 'view_decision', 'decision_id': world.own.id})))
        assert OWN_TITLE in text_of(response)

    def test_unknown_id_and_other_tenants_id_get_the_same_answer(self, world):
        other = run(world.service.handle_invoke(activity(
            name='task/fetch', value={'data': {'action': 'view_decision', 'decision_id': world.other.id}})))
        unknown = run(world.service.handle_invoke(activity(
            name='task/fetch', value={'data': {'action': 'view_decision', 'decision_id': 987654}})))
        assert other == unknown

    def test_deleted_decision_is_not_shown(self, world):
        from datetime import datetime, timezone
        world.own.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        response = run(world.service.handle_invoke(activity(
            name='task/fetch', value={'data': {'action': 'view_decision', 'decision_id': world.own.id}})))
        assert OWN_TITLE not in text_of(response)

    @pytest.mark.parametrize('bad_id', [None, '', 0, -1, True, 'abc', '1 OR 1=1', {'id': 1}, [1], 1.5])
    def test_ids_that_are_not_positive_integers_find_nothing(self, world, bad_id):
        for name, value in (
            ('task/fetch', {'data': {'action': 'view_decision', 'decision_id': bad_id}}),
            ('adaptiveCard/action', {'action': 'view_decision', 'decision_id': bad_id}),
        ):
            response = run(world.service.handle_invoke(activity(name=name, value=value)))
            assert SECRET_TITLE not in text_of(response)
            assert OWN_TITLE not in text_of(response)

    def test_view_command_only_finds_own_numbers(self, world):
        # Both tenants have a decision number 1: the command shows this tenant's
        run(world.service.handle_message({**activity('message'), 'text': 'view 1'}))
        assert OWN_TITLE in text_of(world.sent[0])
        assert SECRET_TITLE not in text_of(world.sent[0])


# ---------------------------------------------------------------------------
# Changing a status
# ---------------------------------------------------------------------------

class TestStatusChangeIsScopedAndNeedsAnAccountOfTheTenant:

    def submit(self, world, decision_id, new_status='accepted', **kwargs):
        return run(world.service.handle_invoke(activity(
            name='task/submit',
            value={'data': {'action': 'submit_status_change', 'decision_id': decision_id,
                            'new_status': new_status}},
            **kwargs)))

    def test_refuses_another_tenants_decision_and_changes_nothing(self, world):
        response = self.submit(world, world.other.id)
        assert status_of(world.other.id) == 'proposed'
        assert history_count(world.other.id) == 0
        assert db.session.get(ArchitectureDecision, world.other.id).updated_by_id is None
        assert SECRET_TITLE not in text_of(response)
        assert 'Decision not found' in text_of(response)

    def test_changes_own_decision_and_records_history(self, world):
        response = self.submit(world, world.own.id)
        assert status_of(world.own.id) == 'accepted'
        assert history_count(world.own.id) == 1
        entry = DecisionHistory.query.filter_by(decision_id=world.own.id).first()
        assert entry.status == 'proposed'
        assert entry.changed_by_id == world.alice.id
        assert db.session.get(ArchitectureDecision, world.own.id).updated_by_id == world.alice.id
        assert 'Status Updated' in text_of(response)

    def test_account_of_another_organisation_cannot_change_status(self, world):
        # Linked in this workspace, but the account belongs to another organisation:
        # the web app would not let it change this decision either.
        response = self.submit(world, world.own.id, oid=OUTSIDER_OID)
        assert status_of(world.own.id) == 'proposed'
        assert history_count(world.own.id) == 0
        assert 'cannot change the status' in text_of(response)

    def test_unidentified_sender_cannot_change_status(self, world):
        response = self.submit(world, world.own.id, oid=None)
        assert status_of(world.own.id) == 'proposed'
        assert history_count(world.own.id) == 0
        assert 'Status Updated' not in text_of(response)

    def test_anonymized_account_cannot_change_status(self, world):
        world.alice.is_anonymized = True
        db.session.commit()
        self.submit(world, world.own.id)
        assert status_of(world.own.id) == 'proposed'

    def test_identity_in_form_data_is_ignored(self, world):
        response = run(world.service.handle_invoke(activity(
            name='task/submit', oid=OUTSIDER_OID,
            value={'data': {'action': 'submit_status_change', 'decision_id': world.own.id,
                            'new_status': 'accepted', 'aadObjectId': ALICE_OID,
                            'user_id': world.alice.id, 'tenant_id': world.tenant_a.id,
                            'domain': 'alpha.example'}})))
        assert status_of(world.own.id) == 'proposed'
        assert 'cannot change the status' in text_of(response)

    @pytest.mark.parametrize('bad_status', ['deleted', 'ACCEPTED', '<b>x</b>', {'a': 1}, ['accepted']])
    def test_unknown_status_is_refused(self, world, bad_status):
        self.submit(world, world.own.id, new_status=bad_status)
        assert status_of(world.own.id) == 'proposed'
        assert history_count(world.own.id) == 0

    def test_status_form_is_not_opened_for_another_tenants_decision(self, world):
        response = run(world.service.handle_invoke(activity(
            name='task/fetch', value={'data': {'action': 'open_status_modal', 'decision_id': world.other.id}})))
        assert SECRET_TITLE not in text_of(response)
        assert 'submit_status_change' not in text_of(response)
        assert 'Not Found' in text_of(response)

    def test_status_form_is_not_opened_for_an_outside_account(self, world):
        response = run(world.service.handle_invoke(activity(
            name='task/fetch', oid=OUTSIDER_OID,
            value={'data': {'action': 'open_status_modal', 'decision_id': world.own.id}})))
        assert 'submit_status_change' not in text_of(response)

    def test_status_form_opens_for_own_decision(self, world):
        response = run(world.service.handle_invoke(activity(
            name='task/fetch', value={'data': {'action': 'open_status_modal', 'decision_id': world.own.id}})))
        assert 'submit_status_change' in text_of(response)


# ---------------------------------------------------------------------------
# Spaces named in card and form data
# ---------------------------------------------------------------------------

class TestSpacesAreScopedToTheWorkspaceTenant:

    def test_list_by_space_refuses_another_tenants_space(self, world):
        run(world.service.handle_message(activity(
            'message', value={'action': 'list_by_space', 'space_id': world.space_b.id,
                              'space_name': 'General beta.example'})))
        text = text_of(world.sent[0])
        assert SECRET_TITLE not in text
        assert 'beta.example' not in text

    def test_list_by_space_lists_own_space_under_its_stored_name(self, world):
        run(world.service.handle_message(activity(
            'message', value={'action': 'list_by_space', 'space_id': world.space_a.id,
                              'space_name': 'A name chosen by the sender'})))
        text = text_of(world.sent[0])
        assert OWN_TITLE in text
        assert 'General alpha.example' in text
        assert 'A name chosen by the sender' not in text

    def create(self, world, space_id, name='task/submit'):
        data = {'action': 'submit_decision', 'title': 'Adopt feature flags', 'context': 'c',
                'decision': 'd', 'consequences': 'q', 'status': 'proposed', 'space_id': space_id}
        if name == 'message':
            return run(world.service.handle_message(activity('message', value=data)))
        value = {'data': data}
        return run(world.service.handle_invoke(activity(name=name, value=value)))

    @pytest.mark.parametrize('route', ['task/submit', 'composeExtension/submitAction', 'message'])
    def test_create_refuses_another_tenants_space(self, world, route):
        before = ArchitectureDecision.query.count()
        links_before = DecisionSpace.query.filter_by(space_id=world.space_b.id).count()
        self.create(world, world.space_b.id, route)
        assert ArchitectureDecision.query.count() == before
        assert DecisionSpace.query.filter_by(space_id=world.space_b.id).count() == links_before

    @pytest.mark.parametrize('route', ['task/submit', 'composeExtension/submitAction', 'message'])
    def test_create_in_own_space_works_and_belongs_to_the_tenant(self, world, route):
        self.create(world, str(world.space_a.id), route)
        created = ArchitectureDecision.query.filter_by(title='Adopt feature flags').one()
        assert created.tenant_id == world.tenant_a.id
        assert created.domain == 'alpha.example'
        assert created.created_by_id == world.alice.id
        assert created.owner_id == world.alice.id
        assert DecisionSpace.query.filter_by(decision_id=created.id, space_id=world.space_a.id).count() == 1

    def test_create_refuses_unknown_status(self, world):
        before = ArchitectureDecision.query.count()
        run(world.service.handle_invoke(activity(name='task/submit', value={'data': {
            'action': 'submit_decision', 'title': 'x', 'status': 'not-a-status'}})))
        assert ArchitectureDecision.query.count() == before

    def test_owner_from_the_people_picker_must_be_known_in_this_tenant(self, world):
        # An object ID that is not linked here and that the directory resolves
        # to an account of another organisation does not become the owner.
        world.service.get_user_by_entra_id = AsyncMock(return_value={'email': 'bob@beta.example'})
        run(world.service.handle_invoke(activity(name='task/submit', value={'data': {
            'action': 'submit_decision', 'title': 'Owned decision',
            'owner_entra_id': 'bbbbbbbb-0000-0000-0000-000000000009'}})))
        created = ArchitectureDecision.query.filter_by(title='Owned decision').one()
        assert created.owner_id == world.alice.id

    def test_owner_value_that_is_not_an_object_id_is_not_looked_up(self, world):
        run(world.service.handle_invoke(activity(name='task/submit', value={'data': {
            'action': 'submit_decision', 'title': 'Owned decision', 'owner_entra_id': '../me'}})))
        world.service.get_user_by_entra_id.assert_not_called()
        assert ArchitectureDecision.query.filter_by(title='Owned decision').one().owner_id == world.alice.id


# ---------------------------------------------------------------------------
# The activity itself
# ---------------------------------------------------------------------------

class TestActivityMustBelongToTheWorkspace:

    def test_activity_of_another_microsoft_tenant_is_refused(self, world):
        response = run(world.service.handle_invoke(activity(
            name='task/submit', ms_tenant=MS_TENANT_B,
            value={'data': {'action': 'submit_status_change', 'decision_id': world.own.id,
                            'new_status': 'accepted'}})))
        assert response == {'status': 403}
        assert status_of(world.own.id) == 'proposed'

    def test_activity_without_a_microsoft_tenant_is_refused(self, world):
        body = activity(name='task/fetch', value={'data': {'action': 'view_decision',
                                                           'decision_id': world.own.id}})
        body['channelData'] = {}
        response = run(world.service.handle_invoke(body))
        assert OWN_TITLE not in text_of(response)

    def test_activity_from_another_channel_is_refused(self, world):
        response = run(world.service.handle_invoke(activity(
            name='task/fetch', channel='directline',
            value={'data': {'action': 'view_decision', 'decision_id': world.own.id}})))
        assert OWN_TITLE not in text_of(response)

    def test_message_of_another_microsoft_tenant_gets_no_reply(self, world):
        result = run(world.service.handle_message(activity(
            'message', ms_tenant=MS_TENANT_B,
            value={'action': 'view_decision', 'decision_id': world.own.id})))
        assert result is False
        assert world.sent == []

    @pytest.mark.parametrize('value', [None, 'text', 5, ['a'], {'data': 'text'}, {'data': None}])
    def test_malformed_invoke_values_are_handled(self, world, value):
        for name in ('task/fetch', 'task/submit', 'adaptiveCard/action', 'composeExtension/submitAction'):
            response = run(world.service.handle_invoke(activity(name=name, value=value)))
            assert SECRET_TITLE not in text_of(response)
        assert status_of(world.other.id) == 'proposed'

    def test_workspace_of_a_deleted_tenant_shows_nothing(self, world):
        from datetime import datetime, timezone
        world.tenant_a.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        response = run(world.service.handle_invoke(activity(
            name='task/fetch', value={'data': {'action': 'view_decision', 'decision_id': world.own.id}})))
        assert OWN_TITLE not in text_of(response)


class TestAnotherWorkspacesMappingDoesNotIdentifyAnyone:

    def test_object_id_linked_in_another_workspace_is_not_reused(self, world):
        # Bob is linked in workspace B. The same object ID arriving in
        # workspace A must not act as Bob there.
        shared_oid = 'cccccccc-0000-0000-0000-000000000003'
        db.session.add(TeamsUserMapping(
            teams_workspace_id=world.workspace_b.id, aad_object_id=shared_oid,
            user_id=world.bob.id, link_method='auto_linked'))
        db.session.commit()

        _, user, _ = world.service.get_or_provision_user(shared_oid, None, 'Someone')
        assert user is None or user.id != world.bob.id

    def test_unlinked_workspace_is_not_linked_through_another_workspaces_mapping(self, world):
        shared_oid = 'cccccccc-0000-0000-0000-000000000004'
        db.session.add(TeamsUserMapping(
            teams_workspace_id=world.workspace_b.id, aad_object_id=shared_oid,
            user_id=world.bob.id, link_method='auto_linked'))
        unlinked = TeamsWorkspace(ms_tenant_id='33333333-3333-3333-3333-333333333333', is_active=True)
        db.session.add(unlinked)
        db.session.commit()

        _, user, needs_linking = TeamsService(unlinked).get_or_provision_user(shared_oid, None, 'Someone')
        assert user is None
        assert needs_linking is True
        assert db.session.get(TeamsWorkspace, unlinked.id).tenant_id is None
