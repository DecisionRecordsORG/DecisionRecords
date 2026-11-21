"""
Slack create-decision modals: only the title is required (Enterprise Edition).

The web app, Teams and the API require only a title. These tests pin the same
contract for both Slack modals and for the submission handler, including the
payload shape Slack sends for an empty optional input ("value": null).

Also covers the decision link in the confirmation message, which must use the
configured app base URL instead of a hardcoded host.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from models import (
    db, User, Tenant, TenantMembership, ArchitectureDecision,
    SlackWorkspace, GlobalRole, MaturityState
)
from flask import Flask

try:
    from ee.backend.slack.slack_security import encrypt_token
    from ee.backend.slack.slack_service import SlackService
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    encrypt_token = None
    SlackService = None

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

OPTIONAL_TEXT_BLOCKS = ('context_block', 'decision_block', 'consequences_block')


# ==================== Fixtures ====================

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'

    os.environ['SIGNING_SECRET'] = 'test-signing-secret-12345'
    os.environ['CLIENT_ID'] = 'test-client-id'
    os.environ['CLIENT_SECRET'] = 'test-client-secret'

    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def user(app):
    user = User(
        email='test@example.com',
        name='Test User',
        sso_domain='example.com',
        auth_type='local',
        email_verified=True
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def tenant(app, user):
    tenant = Tenant(
        domain='example.com',
        name='Example Corp',
        status='active',
        maturity_state=MaturityState.BOOTSTRAP
    )
    db.session.add(tenant)
    db.session.commit()
    db.session.add(TenantMembership(
        user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER
    ))
    db.session.commit()
    return tenant


@pytest.fixture
def service(app, tenant):
    workspace = SlackWorkspace(
        tenant_id=tenant.id,
        workspace_id='T12345678',
        workspace_name='Test Workspace',
        bot_token_encrypted=encrypt_token('xoxb-test-token-12345'),
        is_active=True,
        notifications_enabled=False,
        notify_on_create=False,
        notify_on_status_change=False,
    )
    db.session.add(workspace)
    db.session.commit()
    return SlackService(workspace)


def _blocks_by_id(view):
    return {block['block_id']: block for block in view['blocks']}


def _submission(user, values, channel_id='C999'):
    return {
        'user': {'id': 'U12345'},
        'view': {
            'callback_id': 'create_decision',
            'private_metadata': f'{user.id}:{channel_id}',
            'state': {'values': values},
        },
    }


def _submit(service, payload):
    """Run the submission handler with Slack calls mocked; returns (response, post_mock)."""
    with patch.object(service.client, 'chat_postMessage') as post, \
            patch.object(service.client, 'conversations_open',
                         MagicMock(return_value={'ok': True, 'channel': {'id': 'D_MOCK'}})):
        response = service._create_decision_from_modal(payload)
    return response, post


# ==================== Modal definitions ====================

class TestCreateModalRequiredFields:
    """Both modal builders: title required, the three text areas optional."""

    def test_create_modal_only_requires_title(self, service, user):
        with patch.object(service.client, 'views_open') as views_open:
            service._open_create_modal('trigger-1', user, 'C999')

        blocks = _blocks_by_id(views_open.call_args.kwargs['view'])
        assert not blocks['title_block'].get('optional', False)
        for block_id in OPTIONAL_TEXT_BLOCKS:
            assert blocks[block_id].get('optional') is True, block_id

    def test_save_as_decision_modal_only_requires_title(self, service, user):
        payload = {
            'trigger_id': 'trigger-2',
            'user': {'id': 'U12345'},
            'message': {'text': 'We should use Postgres'},
        }
        with patch.object(service, 'get_or_link_user', return_value=(MagicMock(), user, False)), \
                patch.object(service.client, 'views_open') as views_open:
            service._open_save_as_decision_modal(payload)

        blocks = _blocks_by_id(views_open.call_args.kwargs['view'])
        assert not blocks['title_block'].get('optional', False)
        for block_id in OPTIONAL_TEXT_BLOCKS:
            assert blocks[block_id].get('optional') is True, block_id
        # The message text still prefills the context
        assert blocks['context_block']['element']['initial_value'] == 'We should use Postgres'


# ==================== Submission handling ====================

class TestCreateFromModalWithEmptyFields:
    """Empty optional inputs are stored as empty strings (columns are NOT NULL)."""

    def test_title_only_with_null_values(self, service, user, tenant):
        """Slack sends "value": null for an optional input left empty."""
        payload = _submission(user, {
            'title_block': {'title': {'type': 'plain_text_input', 'value': 'Title only'}},
            'context_block': {'context': {'type': 'plain_text_input', 'value': None}},
            'decision_block': {'decision': {'type': 'plain_text_input', 'value': None}},
            'consequences_block': {'consequences': {'type': 'plain_text_input', 'value': None}},
            'status_block': {'status': {'type': 'static_select', 'selected_option': None}},
            'owner_block': {'owner': {'type': 'users_select', 'selected_user': None}},
        })

        response, _ = _submit(service, payload)

        assert response == {}
        decision = ArchitectureDecision.query.filter_by(title='Title only').one()
        assert decision.context == ''
        assert decision.decision == ''
        assert decision.consequences == ''
        assert decision.status == 'proposed'
        assert decision.tenant_id == tenant.id

    def test_title_only_with_blocks_missing(self, service, user):
        payload = _submission(user, {
            'title_block': {'title': {'value': 'No other blocks'}},
        })

        response, _ = _submit(service, payload)

        assert response == {}
        decision = ArchitectureDecision.query.filter_by(title='No other blocks').one()
        assert (decision.context, decision.decision, decision.consequences) == ('', '', '')
        assert decision.status == 'proposed'

    def test_whitespace_only_values_are_stored_empty(self, service, user):
        payload = _submission(user, {
            'title_block': {'title': {'value': '  Padded title  '}},
            'context_block': {'context': {'value': '   '}},
            'decision_block': {'decision': {'value': '\n'}},
            'consequences_block': {'consequences': {'value': ''}},
        })

        response, _ = _submit(service, payload)

        assert response == {}
        decision = ArchitectureDecision.query.filter_by(title='Padded title').one()
        assert (decision.context, decision.decision, decision.consequences) == ('', '', '')

    def test_partial_fields_are_kept(self, service, user):
        payload = _submission(user, {
            'title_block': {'title': {'value': 'Partial'}},
            'context_block': {'context': {'value': 'Some context'}},
            'decision_block': {'decision': {'value': None}},
            'consequences_block': {'consequences': {'value': None}},
            'status_block': {'status': {'selected_option': {'value': 'accepted'}}},
        })

        response, _ = _submit(service, payload)

        assert response == {}
        decision = ArchitectureDecision.query.filter_by(title='Partial').one()
        assert decision.context == 'Some context'
        assert decision.decision == ''
        assert decision.status == 'accepted'

    @pytest.mark.parametrize('title_value', [None, '', '   '])
    def test_missing_title_is_rejected(self, service, user, title_value):
        payload = _submission(user, {
            'title_block': {'title': {'value': title_value}},
            'context_block': {'context': {'value': 'Context without a title'}},
        })

        response, post = _submit(service, payload)

        assert response == {
            'response_action': 'errors',
            'errors': {'title_block': 'Title is required'},
        }
        assert ArchitectureDecision.query.count() == 0
        assert not post.called

    def test_owner_notification_handles_empty_context(self, service, user):
        """The owner DM summarises the context; an empty one must not break it."""
        payload = _submission(user, {
            'title_block': {'title': {'value': 'Owned decision'}},
            'context_block': {'context': {'value': None}},
            'owner_block': {'owner': {'selected_user': 'U_OWNER'}},
        })
        with patch.object(service.client, 'users_info',
                          MagicMock(return_value={'ok': True, 'user': {'profile': {'email': 'owner@elsewhere.test'}}})):
            response, post = _submit(service, payload)

        assert response == {}
        assert ArchitectureDecision.query.filter_by(title='Owned decision').count() == 1
        owner_dm = [c for c in post.call_args_list if 'assigned' in c.kwargs.get('text', '')]
        assert len(owner_dm) == 1
        assert 'Not provided' in str(owner_dm[0].kwargs['blocks'])


# ==================== Decision link ====================

class TestCreatedDecisionLink:
    """The confirmation links to the app using the configured base URL."""

    def _confirmation_text(self, service, user):
        payload = _submission(user, {'title_block': {'title': {'value': 'Linked'}}})
        response, post = _submit(service, payload)
        assert response == {}
        decision = ArchitectureDecision.query.filter_by(title='Linked').one()
        return decision, str(post.call_args_list[0].kwargs['blocks'])

    def test_link_uses_configured_app_base_url(self, service, user, monkeypatch):
        monkeypatch.setenv('APP_BASE_URL', 'https://records.example.test/')

        decision, blocks = self._confirmation_text(service, user)

        assert f'https://records.example.test/example.com/decision/{decision.id}' in blocks
        assert 'https://decisionrecords.org/' not in blocks

    def test_default_link_points_at_the_app_host(self, service, user, monkeypatch):
        monkeypatch.delenv('APP_BASE_URL', raising=False)

        decision, blocks = self._confirmation_text(service, user)

        assert f'https://app.decisionrecords.org/example.com/decision/{decision.id}' in blocks
        assert 'https://decisionrecords.org/' not in blocks


class TestAppBaseUrlHelper:
    """One helper for every Slack and Teams link into the app."""

    def test_reads_environment_and_strips_trailing_slash(self, monkeypatch):
        from ee.backend.app_urls import get_app_base_url
        monkeypatch.setenv('APP_BASE_URL', 'https://records.example.test/')
        assert get_app_base_url() == 'https://records.example.test'

    @pytest.mark.parametrize('value', [None, '', '   '])
    def test_defaults_to_the_app_host(self, monkeypatch, value):
        from ee.backend.app_urls import get_app_base_url
        if value is None:
            monkeypatch.delenv('APP_BASE_URL', raising=False)
        else:
            monkeypatch.setenv('APP_BASE_URL', value)
        assert get_app_base_url() == 'https://app.decisionrecords.org'

    def test_teams_cards_use_the_helper(self, monkeypatch):
        from ee.backend.teams import teams_cards
        monkeypatch.setenv('APP_BASE_URL', 'https://records.example.test')
        assert teams_cards._get_base_url() == 'https://records.example.test'
        monkeypatch.delenv('APP_BASE_URL')
        assert teams_cards._get_base_url() == 'https://app.decisionrecords.org'
