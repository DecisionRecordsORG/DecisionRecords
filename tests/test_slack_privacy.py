"""
Slack: what is deleted when the connection ends, who may call the webhooks,
and the status change made from the Slack modal. Through the real application.

  - The three webhook routes refuse a request without a valid Slack signature.
  - "Disconnect Slack" deletes the workspace's records: the installation with
    its access token, and every link between a Slack user and an account.
  - Slack's `app_uninstalled` event, and `tokens_revoked` for the bot token,
    do the same.
  - A status change from the Slack modal follows the web app's rules: the
    decision must belong to the workspace's organisation, the status must be
    one of the four, the person must be a linked member, and the previous
    state is saved to the decision's history.
"""

import hashlib
import hmac
import json
import os
import time
from unittest.mock import MagicMock
from urllib.parse import urlencode

import pytest

from models import (
    db, User, Tenant, TenantMembership, GlobalRole, MaturityState, SlackWorkspace, SlackUserMapping,
    ArchitectureDecision, DecisionHistory,
)
from tests.app_test_utils import load_test_app

try:
    from ee.backend.slack import slack_security, slack_service
    from ee.backend.slack.slack_security import encrypt_token
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not EE_AVAILABLE or os.environ.get('DECISION_RECORDS_EDITION', 'community') != 'enterprise',
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

PASSWORD = 'a-long-test-password'
SIGNING_SECRET = 'test-signing-secret-for-slack-privacy'
EVENTS = '/api/slack/webhook/events'
INTERACTIONS = '/api/slack/webhook/interactions'
COMMANDS = '/api/slack/webhook/commands'


@pytest.fixture
def api_app(monkeypatch):
    app_module, test_app = load_test_app(secret_key='test-secret-key-slack-privacy-12345')
    monkeypatch.setattr(slack_security, '_slack_signing_secret', SIGNING_SECRET)
    # No call leaves the machine: every Slack API client is a stand-in
    monkeypatch.setattr(slack_service, 'WebClient', MagicMock())
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def organisation(domain, team_id, slack_users=('U1', 'U2')):
    """A tenant with an admin, a member, a connected Slack workspace and linked Slack users."""
    tenant = Tenant(domain=domain, name=domain, status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.flush()
    people = {}
    for local, role in (('admin', GlobalRole.ADMIN), ('member', GlobalRole.USER)):
        user = User(email=f'{local}@{domain}', sso_domain=domain, auth_type='local', email_verified=True,
                    is_admin=role == GlobalRole.ADMIN)
        user.set_name(first_name=local.capitalize(), last_name='Person')
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.flush()
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
        people[local] = user
    workspace = SlackWorkspace(
        tenant_id=tenant.id, workspace_id=team_id, workspace_name=f'{domain} Slack',
        bot_token_encrypted=encrypt_token('xoxb-test-token'), status=SlackWorkspace.STATUS_ACTIVE,
        is_active=True, default_channel_id='C1', default_channel_name='#decisions')
    db.session.add(workspace)
    db.session.flush()
    for slack_user, person in zip(slack_users, (people['admin'], people['member'])):
        db.session.add(SlackUserMapping(slack_workspace_id=workspace.id, slack_user_id=slack_user,
                                        slack_email=person.email, user_id=person.id, link_method='auto_email'))
    decision = ArchitectureDecision(
        title=f'Decision of {domain}', context='c', decision='d', consequences='q', status='proposed',
        domain=domain, tenant_id=tenant.id, decision_number=1, created_by_id=people['admin'].id)
    db.session.add(decision)
    db.session.commit()
    return {'tenant': tenant, 'workspace': workspace, 'decision': decision, **people}


def signed(body, timestamp=None, secret=SIGNING_SECRET):
    timestamp = str(timestamp or int(time.time()))
    signature = 'v0=' + hmac.new(secret.encode(), f'v0:{timestamp}:{body}'.encode(), hashlib.sha256).hexdigest()
    return {'X-Slack-Request-Timestamp': timestamp, 'X-Slack-Signature': signature}


def post_event(client, payload, headers=None):
    body = json.dumps(payload)
    return client.post(EVENTS, data=body, content_type='application/json',
                       headers=signed(body) if headers is None else headers)


def post_interaction(client, payload, headers=None):
    body = urlencode({'payload': json.dumps(payload)})
    return client.post(INTERACTIONS, data=body, content_type='application/x-www-form-urlencoded',
                       headers=signed(body) if headers is None else headers)


def sign_in(api_app, user):
    client = api_app.test_client()
    response = client.post('/api/auth/login', json={'email': user.email, 'password': PASSWORD})
    assert response.status_code == 200, response.data
    token = response.headers.get('X-CSRF-Token') or client.get('/api/auth/csrf-token').get_json()['csrf_token']
    client.environ_base['HTTP_X_CSRF_TOKEN'] = token
    return client


def slack_rows(team_id):
    workspace = SlackWorkspace.query.filter_by(workspace_id=team_id).first()
    mappings = SlackUserMapping.query.filter_by(slack_workspace_id=workspace.id).count() if workspace else 0
    return (1 if workspace else 0, mappings)


class TestWebhookSignature:

    UNINSTALL = {'type': 'event_callback', 'team_id': 'T-ONE', 'event': {'type': 'app_uninstalled'}}

    @pytest.mark.parametrize('headers', [
        {},
        {'X-Slack-Request-Timestamp': str(int(time.time())), 'X-Slack-Signature': 'v0=' + '0' * 64},
        {'X-Slack-Request-Timestamp': 'not-a-number', 'X-Slack-Signature': 'v0=abc'},
    ])
    def test_events_without_a_valid_signature_are_refused_and_change_nothing(self, api_app, headers):
        organisation('one.test', 'T-ONE')

        response = post_event(api_app.test_client(), self.UNINSTALL, headers=headers)

        assert response.status_code == 403
        assert slack_rows('T-ONE') == (1, 2)

    def test_a_signature_made_with_another_secret_is_refused(self, api_app):
        organisation('one.test', 'T-ONE')
        body = json.dumps(self.UNINSTALL)

        response = api_app.test_client().post(
            EVENTS, data=body, content_type='application/json', headers=signed(body, secret='someone-elses-secret'))

        assert response.status_code == 403
        assert slack_rows('T-ONE') == (1, 2)

    def test_an_old_request_cannot_be_replayed(self, api_app):
        organisation('one.test', 'T-ONE')
        body = json.dumps(self.UNINSTALL)

        response = api_app.test_client().post(
            EVENTS, data=body, content_type='application/json', headers=signed(body, timestamp=int(time.time()) - 600))

        assert response.status_code == 403
        assert slack_rows('T-ONE') == (1, 2)

    def test_a_signature_for_another_body_is_refused(self, api_app):
        organisation('one.test', 'T-ONE')
        harmless = json.dumps({'type': 'event_callback', 'team_id': 'T-ONE', 'event': {'type': 'app_home_opened'}})

        response = api_app.test_client().post(
            EVENTS, data=json.dumps(self.UNINSTALL), content_type='application/json', headers=signed(harmless))

        assert response.status_code == 403
        assert slack_rows('T-ONE') == (1, 2)

    def test_without_a_signing_secret_everything_is_refused(self, api_app, monkeypatch):
        organisation('one.test', 'T-ONE')
        monkeypatch.setattr(slack_security, '_slack_signing_secret', '')
        monkeypatch.setattr(slack_security, 'get_slack_signing_secret', lambda: None)

        response = post_event(api_app.test_client(), self.UNINSTALL)

        assert response.status_code == 403
        assert slack_rows('T-ONE') == (1, 2)

    def test_unsigned_commands_and_interactions_are_refused(self, api_app):
        org = organisation('one.test', 'T-ONE')
        client = api_app.test_client()
        modal = change_status_payload(org, 'U1', org['admin'], 'accepted')

        command = client.post(COMMANDS, data={'team_id': 'T-ONE', 'user_id': 'U1', 'text': 'list'})
        interaction = post_interaction(client, modal, headers={})

        assert command.status_code == 403 and interaction.status_code == 403
        db.session.expire_all()
        assert db.session.get(ArchitectureDecision, org['decision'].id).status == 'proposed'

    def test_a_signed_command_is_accepted_and_its_form_is_still_readable(self, api_app):
        organisation('one.test', 'T-ONE')
        body = urlencode({'team_id': 'T-ONE', 'user_id': 'U1', 'channel_id': 'C1', 'text': 'help',
                          'trigger_id': 'trigger', 'response_url': 'https://hooks.slack.invalid/x'})

        response = api_app.test_client().post(
            COMMANDS, data=body, content_type='application/x-www-form-urlencoded', headers=signed(body))

        assert response.status_code == 200

    def test_the_url_verification_challenge_is_answered_when_signed(self, api_app):
        response = post_event(api_app.test_client(), {'type': 'url_verification', 'challenge': 'abc123'})

        assert response.status_code == 200 and response.get_json() == {'challenge': 'abc123'}


class TestUninstallEvents:

    def test_app_uninstalled_deletes_the_workspace_and_its_user_links(self, api_app):
        org = organisation('one.test', 'T-ONE')
        organisation('two.test', 'T-TWO', slack_users=('U8', 'U9'))
        decision_id = org['decision'].id

        response = post_event(api_app.test_client(), {
            'type': 'event_callback', 'team_id': 'T-ONE', 'event': {'type': 'app_uninstalled'}})

        assert response.status_code == 200
        assert slack_rows('T-ONE') == (0, 0)
        assert SlackUserMapping.query.filter(SlackUserMapping.slack_user_id.in_(['U1', 'U2'])).count() == 0
        # Another organisation's workspace, the accounts and the decisions are untouched
        assert slack_rows('T-TWO') == (1, 2)
        assert User.query.count() == 4
        assert db.session.get(ArchitectureDecision, decision_id) is not None

    def test_tokens_revoked_for_the_bot_token_does_the_same(self, api_app):
        organisation('one.test', 'T-ONE')

        response = post_event(api_app.test_client(), {
            'type': 'event_callback', 'team_id': 'T-ONE',
            'event': {'type': 'tokens_revoked', 'tokens': {'oauth': [], 'bot': ['UBOT']}}})

        assert response.status_code == 200
        assert slack_rows('T-ONE') == (0, 0)

    def test_tokens_revoked_for_a_persons_own_token_removes_nothing(self, api_app):
        organisation('one.test', 'T-ONE')

        response = post_event(api_app.test_client(), {
            'type': 'event_callback', 'team_id': 'T-ONE',
            'event': {'type': 'tokens_revoked', 'tokens': {'oauth': ['U1'], 'bot': []}}})

        assert response.status_code == 200
        assert slack_rows('T-ONE') == (1, 2)

    def test_an_inactive_or_unclaimed_workspace_is_removed_too(self, api_app):
        org = organisation('one.test', 'T-ONE')
        org['workspace'].is_active = False
        org['workspace'].tenant_id = None
        db.session.commit()

        post_event(api_app.test_client(), {
            'type': 'event_callback', 'team_id': 'T-ONE', 'event': {'type': 'app_uninstalled'}})

        assert slack_rows('T-ONE') == (0, 0)

    def test_an_event_for_an_unknown_workspace_is_acknowledged(self, api_app):
        organisation('one.test', 'T-ONE')

        response = post_event(api_app.test_client(), {
            'type': 'event_callback', 'team_id': 'T-NOBODY', 'event': {'type': 'app_uninstalled'}})

        assert response.status_code == 200
        assert slack_rows('T-ONE') == (1, 2)

    def test_the_event_can_arrive_twice(self, api_app):
        organisation('one.test', 'T-ONE')
        event = {'type': 'event_callback', 'team_id': 'T-ONE', 'event': {'type': 'app_uninstalled'}}

        first = post_event(api_app.test_client(), event)
        second = post_event(api_app.test_client(), event)

        assert (first.status_code, second.status_code) == (200, 200)

    def test_which_events_end_an_installation(self):
        ends = slack_service.ends_slack_installation
        assert ends({'type': 'app_uninstalled'}) is True
        assert ends({'type': 'tokens_revoked', 'tokens': {'bot': ['B1']}}) is True
        assert ends({'type': 'tokens_revoked', 'tokens': {'oauth': ['U1']}}) is False
        assert ends({'type': 'tokens_revoked'}) is False
        assert ends({'type': 'app_home_opened'}) is False
        assert ends({}) is False and ends(None) is False


class TestDisconnect:

    def test_an_admin_disconnecting_deletes_the_workspace_and_its_user_links(self, api_app):
        org = organisation('one.test', 'T-ONE')
        organisation('two.test', 'T-TWO', slack_users=('U8', 'U9'))

        response = sign_in(api_app, org['admin']).post('/api/slack/disconnect')

        assert response.status_code == 200
        assert response.get_json() == {'message': 'Slack disconnected successfully'}
        assert slack_rows('T-ONE') == (0, 0)
        assert slack_rows('T-TWO') == (1, 2)
        # The access token is gone with the row: nothing of it is left anywhere
        assert SlackWorkspace.query.filter(SlackWorkspace.workspace_id == 'T-ONE').count() == 0

    def test_settings_then_say_slack_is_not_connected_and_it_can_be_connected_again(self, api_app):
        org = organisation('one.test', 'T-ONE')
        client = sign_in(api_app, org['admin'])

        client.post('/api/slack/disconnect')

        assert client.get('/api/slack/settings').get_json().get('installed') is False
        assert client.post('/api/slack/disconnect').status_code == 404
        # The workspace id is free again: a new installation starts empty
        db.session.add(SlackWorkspace(tenant_id=org['tenant'].id, workspace_id='T-ONE',
                                      bot_token_encrypted=encrypt_token('xoxb-new'), is_active=True))
        db.session.commit()
        assert slack_rows('T-ONE') == (1, 0)

    def test_a_member_who_is_not_an_admin_cannot_disconnect(self, api_app):
        org = organisation('one.test', 'T-ONE')

        response = sign_in(api_app, org['member']).post('/api/slack/disconnect')

        assert response.status_code == 403
        assert slack_rows('T-ONE') == (1, 2)

    def test_signed_out_cannot_disconnect(self, api_app):
        organisation('one.test', 'T-ONE')

        response = api_app.test_client().post('/api/slack/disconnect')

        assert response.status_code in (401, 403)
        assert slack_rows('T-ONE') == (1, 2)


def change_status_payload(org, slack_user, metadata_user, status, decision=None, team_id='T-ONE'):
    decision = decision or org['decision']
    selected = {'selected_option': {'value': status}} if status is not None else {'selected_option': None}
    return {
        'type': 'view_submission',
        'team': {'id': team_id},
        'user': {'id': slack_user},
        'view': {
            'callback_id': 'change_status',
            'private_metadata': f'{decision.id}:{metadata_user.id}:C1',
            'state': {'values': {'status_block': {'new_status': selected}}},
        },
    }


class TestStatusChangeFromTheModal:
    """Tracker item S9 in ee/docs/plans/teams-store-readiness.md."""

    def submit(self, api_app, payload):
        response = post_interaction(api_app.test_client(), payload)
        assert response.status_code == 200
        db.session.expire_all()
        return response.get_json()

    def test_a_linked_member_changes_the_status_and_history_is_written(self, api_app):
        org = organisation('one.test', 'T-ONE')

        answer = self.submit(api_app, change_status_payload(org, 'U2', org['member'], 'accepted'))

        assert answer == {'response_action': 'clear'}
        decision = db.session.get(ArchitectureDecision, org['decision'].id)
        assert decision.status == 'accepted'
        assert decision.updated_by_id == org['member'].id
        history = DecisionHistory.query.filter_by(decision_id=decision.id).one()
        assert history.status == 'proposed', 'the state before the change is what history keeps'
        assert history.changed_by_id == org['member'].id
        assert history.change_reason == 'Status changed from Slack'

    @pytest.mark.parametrize('status', ['proposed', 'accepted', 'archived', 'superseded'])
    def test_each_of_the_four_statuses_can_be_chosen(self, api_app, status):
        org = organisation('one.test', 'T-ONE')
        org['decision'].status = 'accepted' if status == 'proposed' else 'proposed'
        db.session.commit()

        self.submit(api_app, change_status_payload(org, 'U1', org['admin'], status))

        assert db.session.get(ArchitectureDecision, org['decision'].id).status == status
        assert DecisionHistory.query.filter_by(decision_id=org['decision'].id).count() == 1

    @pytest.mark.parametrize('status', ['deprecated', 'ACCEPTED', 'done', '', 'accepted; drop table'])
    def test_any_other_status_is_refused_and_nothing_is_written(self, api_app, status):
        org = organisation('one.test', 'T-ONE')

        answer = self.submit(api_app, change_status_payload(org, 'U1', org['admin'], status))

        assert answer['response_action'] == 'errors'
        assert db.session.get(ArchitectureDecision, org['decision'].id).status == 'proposed'
        assert DecisionHistory.query.count() == 0

    def test_a_decision_of_another_organisation_cannot_be_changed(self, api_app):
        one = organisation('one.test', 'T-ONE')
        two = organisation('two.test', 'T-TWO', slack_users=('U8', 'U9'))

        answer = self.submit(api_app, change_status_payload(one, 'U1', one['admin'], 'archived',
                                                            decision=two['decision']))

        assert answer == {'response_action': 'errors', 'errors': {'status_block': 'Decision not found'}}
        assert db.session.get(ArchitectureDecision, two['decision'].id).status == 'proposed'
        assert DecisionHistory.query.count() == 0

    def test_a_deleted_decision_cannot_be_changed(self, api_app):
        from datetime import datetime, timezone
        org = organisation('one.test', 'T-ONE')
        org['decision'].deleted_at = datetime.now(timezone.utc)
        db.session.commit()

        answer = self.submit(api_app, change_status_payload(org, 'U1', org['admin'], 'accepted'))

        assert answer['errors'] == {'status_block': 'Decision not found'}
        assert db.session.get(ArchitectureDecision, org['decision'].id).status == 'proposed'

    def test_the_account_named_in_the_modal_must_be_the_slack_user_who_submits(self, api_app):
        """The acting person comes from who pressed the button, not from the modal's metadata."""
        org = organisation('one.test', 'T-ONE')

        answer = self.submit(api_app, change_status_payload(org, 'U2', org['admin'], 'accepted'))

        assert answer['response_action'] == 'errors'
        assert db.session.get(ArchitectureDecision, org['decision'].id).status == 'proposed'
        assert DecisionHistory.query.count() == 0

    def test_a_slack_user_who_is_not_linked_is_refused(self, api_app):
        org = organisation('one.test', 'T-ONE')

        answer = self.submit(api_app, change_status_payload(org, 'U-STRANGER', org['admin'], 'accepted'))

        assert answer['response_action'] == 'errors'
        assert db.session.get(ArchitectureDecision, org['decision'].id).status == 'proposed'

    def test_a_person_who_left_the_organisation_is_refused(self, api_app):
        org = organisation('one.test', 'T-ONE')
        TenantMembership.query.filter_by(user_id=org['member'].id).delete()
        db.session.commit()

        answer = self.submit(api_app, change_status_payload(org, 'U2', org['member'], 'accepted'))

        assert answer['response_action'] == 'errors'
        assert db.session.get(ArchitectureDecision, org['decision'].id).status == 'proposed'
        assert DecisionHistory.query.count() == 0

    def test_choosing_the_status_it_already_has_writes_no_history(self, api_app):
        org = organisation('one.test', 'T-ONE')

        answer = self.submit(api_app, change_status_payload(org, 'U1', org['admin'], 'proposed'))

        assert answer == {'response_action': 'clear'}
        assert DecisionHistory.query.count() == 0

    def test_no_status_chosen_or_broken_metadata_is_refused(self, api_app):
        org = organisation('one.test', 'T-ONE')
        missing = change_status_payload(org, 'U1', org['admin'], None)
        broken = change_status_payload(org, 'U1', org['admin'], 'accepted')
        broken['view']['private_metadata'] = 'not-a-number'

        assert self.submit(api_app, missing)['response_action'] == 'errors'
        assert self.submit(api_app, broken)['response_action'] == 'errors'
        assert db.session.get(ArchitectureDecision, org['decision'].id).status == 'proposed'

    def test_the_modal_is_not_opened_for_another_organisations_decision(self, api_app):
        one = organisation('one.test', 'T-ONE')
        two = organisation('two.test', 'T-TWO', slack_users=('U8', 'U9'))
        service = slack_service.SlackService(db.session.get(SlackWorkspace, one['workspace'].id))

        service._open_change_status_modal('trigger', two['decision'].id, one['admin'], 'C1')
        assert not service.client.views_open.called

        service._open_change_status_modal('trigger', one['decision'].id, one['admin'], 'C1')
        assert service.client.views_open.called


class TestSharedStatusRoutineStaysStrictForAiClients:
    """The Slack modal may set `superseded`; an AI client still may not."""

    def test_superseded_is_refused_by_default(self, api_app):
        from ee.backend.ai.decision_status import change_decision_status, DecisionStatusError
        org = organisation('one.test', 'T-ONE')

        with pytest.raises(DecisionStatusError) as refused:
            change_decision_status(org['decision'], 'superseded', org['admin'])

        assert refused.value.code == DecisionStatusError.SUPERSEDED_NOT_SETTABLE
        assert org['decision'].status == 'proposed'
