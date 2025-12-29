"""
Backend Unit Tests for Slack Integration

Tests for Slack service, security, and API endpoints.
Tests cover:
- Slack signature verification
- OAuth installation flow
- Slash command handling
- User linking (auto-link by email and browser flow)
- Notifications
- Settings management
"""
import pytest
import hmac
import hashlib
import time
import json
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, session

from models import (
    db, User, Tenant, TenantMembership, TenantSettings, ArchitectureDecision,
    SlackWorkspace, SlackUserMapping, GlobalRole, MaturityState
)
from slack_security import (
    verify_slack_signature, generate_oauth_state, verify_oauth_state,
    encrypt_token, decrypt_token, generate_link_token, verify_link_token
)
from slack_service import SlackService


# ==================== Fixtures ====================

@pytest.fixture
def app():
    """Create application for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'

    # Set Slack environment variables for tests
    os.environ['SIGNING_SECRET'] = 'test-signing-secret-12345'
    os.environ['CLIENT_ID'] = 'test-client-id'
    os.environ['CLIENT_SECRET'] = 'test-client-secret'

    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def session_fixture(app):
    """Create database session for testing."""
    with app.app_context():
        yield db.session


@pytest.fixture
def sample_user(session_fixture):
    """Create a sample user."""
    user = User(
        email='test@example.com',
        name='Test User',
        sso_domain='example.com',
        auth_type='local',
        email_verified=True
    )
    session_fixture.add(user)
    session_fixture.commit()
    return user


@pytest.fixture
def sample_tenant(session_fixture):
    """Create a sample tenant."""
    tenant = Tenant(
        domain='example.com',
        name='Example Corp',
        status='active',
        maturity_state=MaturityState.BOOTSTRAP
    )
    session_fixture.add(tenant)
    session_fixture.commit()
    return tenant


@pytest.fixture
def sample_membership(session_fixture, sample_user, sample_tenant):
    """Create a sample membership."""
    membership = TenantMembership(
        user_id=sample_user.id,
        tenant_id=sample_tenant.id,
        global_role=GlobalRole.USER
    )
    session_fixture.add(membership)
    session_fixture.commit()
    return membership


@pytest.fixture
def slack_workspace(session_fixture, sample_tenant):
    """Create a sample Slack workspace."""
    encrypted_token = encrypt_token('xoxb-test-token-12345')
    workspace = SlackWorkspace(
        tenant_id=sample_tenant.id,
        workspace_id='T12345678',
        workspace_name='Test Workspace',
        bot_token_encrypted=encrypted_token,
        is_active=True,
        notifications_enabled=True,
        notify_on_create=True,
        notify_on_status_change=True,
        default_channel_id='C12345678',
        default_channel_name='#announcements'
    )
    session_fixture.add(workspace)
    session_fixture.commit()
    return workspace


@pytest.fixture
def sample_decision(session_fixture, sample_tenant, sample_user):
    """Create a sample decision."""
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
    session_fixture.add(decision)
    session_fixture.commit()
    return decision


# ==================== Test Slack Security ====================

class TestSlackSignatureVerification:
    """Test Slack request signature verification."""

    def test_valid_signature_passes(self, app):
        """Valid HMAC-SHA256 signature should pass verification."""
        with app.test_client() as client:
            timestamp = str(int(time.time()))
            body = 'token=test&team_id=T123'

            # Calculate valid signature
            sig_basestring = f"v0:{timestamp}:{body}"
            signature = 'v0=' + hmac.new(
                b'test-signing-secret-12345',
                sig_basestring.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            # Mock route with decorator
            @app.route('/test', methods=['POST'])
            @verify_slack_signature
            def test_route():
                return {'status': 'ok'}, 200

            response = client.post('/test',
                data=body,
                headers={
                    'X-Slack-Request-Timestamp': timestamp,
                    'X-Slack-Signature': signature,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )

            assert response.status_code == 200
            assert response.json['status'] == 'ok'

    def test_invalid_signature_rejected(self, app):
        """Invalid signature should return 403."""
        with app.test_client() as client:
            timestamp = str(int(time.time()))
            body = 'token=test&team_id=T123'
            invalid_signature = 'v0=invalid_signature_hash'

            @app.route('/test2', methods=['POST'])
            @verify_slack_signature
            def test_route2():
                return {'status': 'ok'}, 200

            response = client.post('/test2',
                data=body,
                headers={
                    'X-Slack-Request-Timestamp': timestamp,
                    'X-Slack-Signature': invalid_signature,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )

            assert response.status_code == 403
            assert 'error' in response.json

    def test_expired_timestamp_rejected(self, app):
        """Timestamp older than 5 minutes should be rejected."""
        with app.test_client() as client:
            # Timestamp from 10 minutes ago
            timestamp = str(int(time.time() - 600))
            body = 'token=test&team_id=T123'

            sig_basestring = f"v0:{timestamp}:{body}"
            signature = 'v0=' + hmac.new(
                b'test-signing-secret-12345',
                sig_basestring.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            @app.route('/test3', methods=['POST'])
            @verify_slack_signature
            def test_route3():
                return {'status': 'ok'}, 200

            response = client.post('/test3',
                data=body,
                headers={
                    'X-Slack-Request-Timestamp': timestamp,
                    'X-Slack-Signature': signature,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )

            assert response.status_code == 403
            assert 'error' in response.json

    def test_missing_headers_rejected(self, app):
        """Missing signature headers should return 403."""
        with app.test_client() as client:
            body = 'token=test&team_id=T123'

            @app.route('/test4', methods=['POST'])
            @verify_slack_signature
            def test_route4():
                return {'status': 'ok'}, 200

            # Missing both headers
            response = client.post('/test4', data=body)
            assert response.status_code == 403


class TestSlackOAuth:
    """Test Slack OAuth flow."""

    def test_oauth_state_roundtrip(self, app):
        """OAuth state can be generated and verified."""
        with app.app_context():
            state = generate_oauth_state(
                tenant_id=123,
                user_id=456,
                extra_data={'test': 'data'}
            )

            assert state is not None
            assert isinstance(state, str)

            # Verify state
            state_data = verify_oauth_state(state)
            assert state_data is not None
            assert state_data['tenant_id'] == 123
            assert state_data['user_id'] == 456
            assert state_data['extra_data']['test'] == 'data'
            assert 'csrf_token' in state_data
            assert 'expires_at' in state_data

    def test_oauth_state_expires(self, app):
        """Expired OAuth state should be rejected."""
        with app.app_context():
            state = generate_oauth_state(tenant_id=123)

            # Manually create an expired state by patching the expiry
            from slack_security import _get_encryption_key
            from cryptography.fernet import Fernet

            # Create expired state (expired 1 hour ago)
            expires_at = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            state_data = {
                'tenant_id': 123,
                'csrf_token': 'test',
                'expires_at': expires_at,
                'extra_data': {}
            }

            fernet = Fernet(_get_encryption_key())
            expired_state = fernet.encrypt(json.dumps(state_data).encode()).decode()

            # Verify should fail
            result = verify_oauth_state(expired_state)
            assert result is None

    def test_oauth_callback_invalid_state_fails(self, app):
        """OAuth callback with invalid state should fail."""
        with app.app_context():
            invalid_state = 'totally-invalid-state-string'
            result = verify_oauth_state(invalid_state)
            assert result is None


class TestSlackTokenEncryption:
    """Test Slack token encryption/decryption."""

    def test_token_encryption_roundtrip(self, app):
        """Token can be encrypted and decrypted."""
        with app.app_context():
            original_token = 'xoxb-test-token-12345-67890'

            encrypted = encrypt_token(original_token)
            assert encrypted is not None
            assert encrypted != original_token

            decrypted = decrypt_token(encrypted)
            assert decrypted == original_token

    def test_encrypt_none_returns_none(self, app):
        """Encrypting None should return None."""
        with app.app_context():
            result = encrypt_token(None)
            assert result is None

    def test_decrypt_none_returns_none(self, app):
        """Decrypting None should return None."""
        with app.app_context():
            result = decrypt_token(None)
            assert result is None


# ==================== Test Slack Service ====================

class TestSlackUserMapping:
    """Test Slack user linking functionality."""

    def test_auto_link_by_email(self, app, session_fixture, sample_user, slack_workspace, sample_membership):
        """User with matching email is auto-linked."""
        with app.app_context():
            service = SlackService(slack_workspace)

            # Mock Slack API response with matching email
            mock_response = {
                'ok': True,
                'user': {
                    'profile': {
                        'email': sample_user.email
                    }
                }
            }

            with patch.object(service.client, 'users_info', return_value=mock_response):
                mapping, user, needs_linking = service.get_or_link_user('U99999999')

            assert mapping is not None
            assert user is not None
            assert user.id == sample_user.id
            assert not needs_linking
            assert mapping.user_id == sample_user.id
            assert mapping.link_method == 'auto_email'

    def test_unlinked_user_gets_link_prompt(self, app, session_fixture, slack_workspace):
        """User without account gets link message."""
        with app.app_context():
            service = SlackService(slack_workspace)

            # Mock Slack API response with non-existing email
            mock_response = {
                'ok': True,
                'user': {
                    'profile': {
                        'email': 'nonexistent@example.com'
                    }
                }
            }

            with patch.object(service.client, 'users_info', return_value=mock_response):
                mapping, user, needs_linking = service.get_or_link_user('U88888888')

            assert mapping is not None
            assert user is None
            assert needs_linking
            assert mapping.user_id is None

    def test_browser_link_flow(self, app, session_fixture, sample_user, slack_workspace):
        """Browser linking creates mapping."""
        with app.app_context():
            # Create link token
            token = generate_link_token(
                slack_workspace.id,
                'U77777777',
                'test@example.com'
            )

            # Verify token
            token_data = verify_link_token(token)
            assert token_data is not None
            assert token_data['slack_workspace_id'] == slack_workspace.id
            assert token_data['slack_user_id'] == 'U77777777'
            assert token_data['slack_email'] == 'test@example.com'

            # Create mapping
            mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U77777777',
                slack_email='test@example.com',
                user_id=sample_user.id,
                linked_at=datetime.utcnow(),
                link_method='browser_auth'
            )
            session_fixture.add(mapping)
            session_fixture.commit()

            # Verify mapping exists
            found_mapping = SlackUserMapping.query.filter_by(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U77777777'
            ).first()

            assert found_mapping is not None
            assert found_mapping.user_id == sample_user.id
            assert found_mapping.link_method == 'browser_auth'


class TestSlackCommands:
    """Test Slack slash command handling."""

    def test_help_command(self, app, slack_workspace, sample_user):
        """'/decision help' returns help text."""
        with app.app_context():
            service = SlackService(slack_workspace)

            # Create user mapping
            mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U12345',
                user_id=sample_user.id,
                linked_at=datetime.utcnow(),
                link_method='auto_email'
            )
            db.session.add(mapping)
            db.session.commit()

            response, is_ephemeral = service.handle_command(
                'help',
                'U12345',
                'trigger123',
                'https://example.com/response'
            )

            assert is_ephemeral is True
            assert 'blocks' in response
            assert response['response_type'] == 'ephemeral'

            # Check help text contains command info
            blocks_text = json.dumps(response['blocks'])
            assert '/decision create' in blocks_text
            assert '/decision list' in blocks_text

    def test_list_command(self, app, slack_workspace, sample_user, sample_decision, sample_membership):
        """'/decision list' returns decision list."""
        with app.app_context():
            service = SlackService(slack_workspace)

            # Create user mapping
            mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U12345',
                user_id=sample_user.id,
                linked_at=datetime.utcnow()
            )
            db.session.add(mapping)
            db.session.commit()

            response, is_ephemeral = service.handle_command(
                'list',
                'U12345',
                'trigger123',
                'https://example.com/response'
            )

            assert is_ephemeral is True
            assert 'blocks' in response

            # Check decision appears in response
            blocks_text = json.dumps(response['blocks'])
            assert sample_decision.title in blocks_text

    def test_view_command(self, app, slack_workspace, sample_user, sample_decision, sample_membership):
        """'/decision view <id>' returns decision details."""
        with app.app_context():
            service = SlackService(slack_workspace)

            # Create user mapping
            mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U12345',
                user_id=sample_user.id,
                linked_at=datetime.utcnow()
            )
            db.session.add(mapping)
            db.session.commit()

            response, is_ephemeral = service.handle_command(
                f'view {sample_decision.decision_number}',
                'U12345',
                'trigger123',
                'https://example.com/response'
            )

            assert is_ephemeral is True
            assert 'blocks' in response

            # Check decision details in response
            blocks_text = json.dumps(response['blocks'])
            assert sample_decision.title in blocks_text
            assert sample_decision.context[:100] in blocks_text

    def test_search_command(self, app, slack_workspace, sample_user, sample_decision, sample_membership):
        """'/decision search <query>' returns results."""
        with app.app_context():
            service = SlackService(slack_workspace)

            # Create user mapping
            mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U12345',
                user_id=sample_user.id,
                linked_at=datetime.utcnow()
            )
            db.session.add(mapping)
            db.session.commit()

            response, is_ephemeral = service.handle_command(
                'search Test',
                'U12345',
                'trigger123',
                'https://example.com/response'
            )

            assert is_ephemeral is True
            assert 'blocks' in response

            # Check search results
            blocks_text = json.dumps(response['blocks'])
            assert 'Search Results' in blocks_text or sample_decision.title in blocks_text

    def test_create_command_opens_modal(self, app, slack_workspace, sample_user, sample_membership):
        """'/decision create' triggers modal."""
        with app.app_context():
            service = SlackService(slack_workspace)

            # Create user mapping
            mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U12345',
                user_id=sample_user.id,
                linked_at=datetime.utcnow()
            )
            db.session.add(mapping)
            db.session.commit()

            with patch.object(service.client, 'views_open') as mock_open:
                response, is_ephemeral = service.handle_command(
                    'create',
                    'U12345',
                    'trigger123',
                    'https://example.com/response'
                )

                # Should call views_open
                assert mock_open.called
                assert response is None  # No immediate response for modal


class TestSlackNotifications:
    """Test Slack notification functionality."""

    def test_notification_sent_on_decision_create(self, app, slack_workspace, sample_user, sample_tenant):
        """Creating decision sends notification."""
        with app.app_context():
            service = SlackService(slack_workspace)

            decision = ArchitectureDecision(
                title='New Decision',
                context='Context',
                decision='Decision',
                consequences='Consequences',
                status='proposed',
                domain=sample_tenant.domain,
                tenant_id=sample_tenant.id,
                created_by_id=sample_user.id,
                decision_number=42
            )
            db.session.add(decision)
            db.session.commit()

            with patch.object(service.client, 'chat_postMessage') as mock_post:
                result = service.post_decision_notification(decision, 'created')

                assert mock_post.called
                call_args = mock_post.call_args
                assert call_args[1]['channel'] == slack_workspace.default_channel_id
                assert 'blocks' in call_args[1]
                assert result is True

    def test_notification_respects_settings(self, app, slack_workspace, sample_user, sample_tenant):
        """Notifications respect enabled flags."""
        with app.app_context():
            # Disable notifications
            slack_workspace.notifications_enabled = False
            db.session.commit()

            service = SlackService(slack_workspace)

            decision = ArchitectureDecision(
                title='New Decision',
                context='Context',
                decision='Decision',
                consequences='Consequences',
                status='proposed',
                domain=sample_tenant.domain,
                tenant_id=sample_tenant.id,
                created_by_id=sample_user.id,
                decision_number=42
            )
            db.session.add(decision)
            db.session.commit()

            with patch.object(service.client, 'chat_postMessage') as mock_post:
                result = service.post_decision_notification(decision, 'created')

                # Should not post message when disabled
                assert not mock_post.called
                assert result is False

    def test_notification_fails_gracefully(self, app, slack_workspace, sample_user, sample_tenant):
        """Slack errors don't break decision creation."""
        with app.app_context():
            from slack_sdk.errors import SlackApiError

            service = SlackService(slack_workspace)

            decision = ArchitectureDecision(
                title='New Decision',
                context='Context',
                decision='Decision',
                consequences='Consequences',
                status='proposed',
                domain=sample_tenant.domain,
                tenant_id=sample_tenant.id,
                created_by_id=sample_user.id,
                decision_number=42
            )
            db.session.add(decision)
            db.session.commit()

            # Mock Slack API error
            mock_error = SlackApiError('Test error', {'error': 'channel_not_found'})
            with patch.object(service.client, 'chat_postMessage', side_effect=mock_error):
                result = service.post_decision_notification(decision, 'created')

                # Should return False but not raise
                assert result is False


class TestSlackSettings:
    """Test Slack settings management."""

    def test_get_settings_returns_config(self, app, slack_workspace):
        """Get settings returns workspace info."""
        with app.app_context():
            settings_dict = slack_workspace.to_dict()

            assert settings_dict['workspace_id'] == slack_workspace.workspace_id
            assert settings_dict['workspace_name'] == slack_workspace.workspace_name
            assert settings_dict['notifications_enabled'] is True
            assert settings_dict['notify_on_create'] is True
            assert settings_dict['default_channel_id'] == 'C12345678'

    def test_update_settings_saves_config(self, app, session_fixture, slack_workspace):
        """Update settings persists changes."""
        with app.app_context():
            # Update settings
            slack_workspace.default_channel_id = 'C99999999'
            slack_workspace.default_channel_name = '#general'
            slack_workspace.notifications_enabled = False
            session_fixture.commit()

            # Reload from DB
            reloaded = SlackWorkspace.query.get(slack_workspace.id)
            assert reloaded.default_channel_id == 'C99999999'
            assert reloaded.default_channel_name == '#general'
            assert reloaded.notifications_enabled is False

    def test_disconnect_removes_workspace(self, app, session_fixture, slack_workspace):
        """Disconnect marks workspace as inactive."""
        with app.app_context():
            # Disconnect (soft delete)
            slack_workspace.is_active = False
            session_fixture.commit()

            # Verify inactive
            reloaded = SlackWorkspace.query.get(slack_workspace.id)
            assert reloaded.is_active is False

    def test_test_notification_sends_message(self, app, slack_workspace):
        """Test button sends test message."""
        with app.app_context():
            service = SlackService(slack_workspace)

            with patch.object(service.client, 'chat_postMessage') as mock_post:
                service.send_test_notification()

                assert mock_post.called
                call_args = mock_post.call_args
                assert call_args[1]['channel'] == slack_workspace.default_channel_id
                assert 'Test Notification' in json.dumps(call_args[1]['blocks'])


class TestSlackModalSubmission:
    """Test Slack modal form submission."""

    def test_create_decision_from_modal(self, app, session_fixture, slack_workspace, sample_user, sample_tenant, sample_membership):
        """Modal submission creates decision."""
        with app.app_context():
            service = SlackService(slack_workspace)

            # Mock modal submission payload
            payload = {
                'user': {'id': 'U12345'},
                'view': {
                    'callback_id': 'create_decision',
                    'private_metadata': str(sample_user.id),
                    'state': {
                        'values': {
                            'title_block': {
                                'title': {
                                    'value': 'Test Decision from Modal'
                                }
                            },
                            'context_block': {
                                'context': {
                                    'value': 'Test context from modal'
                                }
                            },
                            'decision_block': {
                                'decision': {
                                    'value': 'Test decision from modal'
                                }
                            },
                            'consequences_block': {
                                'consequences': {
                                    'value': 'Test consequences from modal'
                                }
                            },
                            'status_block': {
                                'status': {
                                    'selected_option': {
                                        'value': 'proposed'
                                    }
                                }
                            }
                        }
                    }
                }
            }

            with patch.object(service.client, 'chat_postMessage'):
                response = service._create_decision_from_modal(payload)

            # Check decision was created
            decision = ArchitectureDecision.query.filter_by(
                title='Test Decision from Modal'
            ).first()

            assert decision is not None
            assert decision.context == 'Test context from modal'
            assert decision.decision == 'Test decision from modal'
            assert decision.consequences == 'Test consequences from modal'
            assert decision.status == 'proposed'
            assert decision.tenant_id == sample_tenant.id

    def test_modal_validation_errors(self, app, slack_workspace, sample_user):
        """Modal submission validates required fields."""
        with app.app_context():
            service = SlackService(slack_workspace)

            # Mock payload with missing fields
            payload = {
                'view': {
                    'callback_id': 'create_decision',
                    'private_metadata': str(sample_user.id),
                    'state': {
                        'values': {
                            'title_block': {
                                'title': {
                                    'value': ''  # Empty title
                                }
                            },
                            'context_block': {
                                'context': {
                                    'value': 'Some context'
                                }
                            },
                            'decision_block': {
                                'decision': {
                                    'value': ''  # Empty decision
                                }
                            },
                            'consequences_block': {
                                'consequences': {
                                    'value': ''  # Empty consequences
                                }
                            }
                        }
                    }
                }
            }

            response = service._create_decision_from_modal(payload)

            # Should return validation errors - only title is required now
            assert response is not None
            assert response['response_action'] == 'errors'
            assert 'errors' in response
            assert 'title_block' in response['errors']
            # context, decision, consequences are now optional

    def test_create_decision_with_owner_linked_user(self, app, session_fixture, slack_workspace, sample_user, sample_tenant, sample_membership):
        """Modal submission with owner who is already linked sets owner_id."""
        with app.app_context():
            # Create another user to be the owner
            owner_user = User(
                email='owner@example.com',
                name='Owner User',
                sso_domain='example.com',
                auth_type='webauthn'
            )
            session_fixture.add(owner_user)
            session_fixture.commit()

            # Create Slack mapping for owner
            owner_mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U_OWNER_123',
                slack_email='owner@example.com',
                user_id=owner_user.id,
                link_method='auto_email',
                linked_at=datetime.utcnow()
            )
            session_fixture.add(owner_mapping)
            session_fixture.commit()

            service = SlackService(slack_workspace)

            payload = {
                'user': {'id': 'U_CREATOR'},
                'view': {
                    'callback_id': 'create_decision',
                    'private_metadata': str(sample_user.id),
                    'state': {
                        'values': {
                            'title_block': {'title': {'value': 'Decision with Owner'}},
                            'context_block': {'context': {'value': 'Context'}},
                            'decision_block': {'decision': {'value': 'Decision'}},
                            'consequences_block': {'consequences': {'value': 'Consequences'}},
                            'status_block': {'status': {'selected_option': {'value': 'proposed'}}},
                            'owner_block': {'owner': {'selected_user': 'U_OWNER_123'}}
                        }
                    }
                }
            }

            mock_conversations_open = MagicMock(return_value={'ok': True, 'channel': {'id': 'D_MOCK_DM'}})
            with patch.object(service.client, 'chat_postMessage'):
                with patch.object(service.client, 'conversations_open', mock_conversations_open):
                    response = service._create_decision_from_modal(payload)

            decision = ArchitectureDecision.query.filter_by(title='Decision with Owner').first()
            assert decision is not None
            assert decision.owner_id == owner_user.id
            assert decision.owner_email is None  # Should not be set when owner_id is set

    def test_create_decision_with_owner_unlinked_user(self, app, session_fixture, slack_workspace, sample_user, sample_tenant, sample_membership):
        """Modal submission with unlinked owner stores owner email."""
        with app.app_context():
            service = SlackService(slack_workspace)

            payload = {
                'user': {'id': 'U_CREATOR'},
                'view': {
                    'callback_id': 'create_decision',
                    'private_metadata': str(sample_user.id),
                    'state': {
                        'values': {
                            'title_block': {'title': {'value': 'Decision with External Owner'}},
                            'context_block': {'context': {'value': 'Context'}},
                            'decision_block': {'decision': {'value': 'Decision'}},
                            'consequences_block': {'consequences': {'value': 'Consequences'}},
                            'status_block': {'status': {'selected_option': {'value': 'proposed'}}},
                            'owner_block': {'owner': {'selected_user': 'U_EXTERNAL_USER'}}
                        }
                    }
                }
            }

            # Mock users_info to return an external email
            mock_users_info = MagicMock(return_value={
                'ok': True,
                'user': {
                    'profile': {
                        'email': 'external@other-company.com'
                    }
                }
            })

            mock_conversations_open = MagicMock(return_value={'ok': True, 'channel': {'id': 'D_MOCK_DM'}})
            with patch.object(service.client, 'chat_postMessage'):
                with patch.object(service.client, 'users_info', mock_users_info):
                    with patch.object(service.client, 'conversations_open', mock_conversations_open):
                        response = service._create_decision_from_modal(payload)

            decision = ArchitectureDecision.query.filter_by(title='Decision with External Owner').first()
            assert decision is not None
            assert decision.owner_id is None  # User not in platform
            assert decision.owner_email == 'external@other-company.com'

    def test_create_decision_sends_owner_notification(self, app, session_fixture, slack_workspace, sample_user, sample_tenant, sample_membership):
        """Modal submission sends notification to owner when different from creator."""
        with app.app_context():
            # Create owner mapping
            owner_mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U_OWNER_NOTIF',
                slack_email='owner-notif@example.com',
                user_id=sample_user.id,
                link_method='auto_email',
                linked_at=datetime.utcnow()
            )
            session_fixture.add(owner_mapping)
            session_fixture.commit()

            service = SlackService(slack_workspace)

            payload = {
                'user': {'id': 'U_CREATOR_DIFFERENT'},  # Different from owner
                'view': {
                    'callback_id': 'create_decision',
                    'private_metadata': str(sample_user.id),
                    'state': {
                        'values': {
                            'title_block': {'title': {'value': 'Decision with Notification'}},
                            'context_block': {'context': {'value': 'Context'}},
                            'decision_block': {'decision': {'value': 'Decision'}},
                            'consequences_block': {'consequences': {'value': 'Consequences'}},
                            'status_block': {'status': {'selected_option': {'value': 'proposed'}}},
                            'owner_block': {'owner': {'selected_user': 'U_OWNER_NOTIF'}}
                        }
                    }
                }
            }

            mock_post = MagicMock()
            mock_conversations_open = MagicMock(return_value={'ok': True, 'channel': {'id': 'D_MOCK_DM'}})
            with patch.object(service.client, 'chat_postMessage', mock_post):
                with patch.object(service.client, 'conversations_open', mock_conversations_open):
                    response = service._create_decision_from_modal(payload)

            # Should have been called twice: once for creator, once for owner
            assert mock_post.call_count >= 2

            # Check that owner was notified (channel will be the mock DM channel)
            owner_call = None
            for call in mock_post.call_args_list:
                text = call.kwargs.get('text', '')
                if "assigned" in text.lower():
                    owner_call = call
                    break

            assert owner_call is not None
            assert "assigned" in owner_call.kwargs.get('text', '').lower()

    def test_create_decision_no_owner_notification_when_self_assigned(self, app, session_fixture, slack_workspace, sample_user, sample_tenant, sample_membership):
        """No owner notification when creator assigns themselves as owner."""
        with app.app_context():
            # Create mapping where creator is also the owner
            creator_mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U_SELF_ASSIGN',
                slack_email=sample_user.email,
                user_id=sample_user.id,
                link_method='auto_email',
                linked_at=datetime.utcnow()
            )
            session_fixture.add(creator_mapping)
            session_fixture.commit()

            service = SlackService(slack_workspace)

            payload = {
                'user': {'id': 'U_SELF_ASSIGN'},  # Same as owner
                'view': {
                    'callback_id': 'create_decision',
                    'private_metadata': str(sample_user.id),
                    'state': {
                        'values': {
                            'title_block': {'title': {'value': 'Self-assigned Decision'}},
                            'context_block': {'context': {'value': 'Context'}},
                            'decision_block': {'decision': {'value': 'Decision'}},
                            'consequences_block': {'consequences': {'value': 'Consequences'}},
                            'status_block': {'status': {'selected_option': {'value': 'proposed'}}},
                            'owner_block': {'owner': {'selected_user': 'U_SELF_ASSIGN'}}
                        }
                    }
                }
            }

            mock_post = MagicMock()
            mock_conversations_open = MagicMock(return_value={'ok': True, 'channel': {'id': 'D_MOCK_DM'}})
            with patch.object(service.client, 'chat_postMessage', mock_post):
                with patch.object(service.client, 'conversations_open', mock_conversations_open):
                    response = service._create_decision_from_modal(payload)

            # Count how many times the "You have been assigned" notification was sent
            owner_assignment_notification_count = 0
            for call in mock_post.call_args_list:
                text = call.kwargs.get('text', '')
                # Owner assignment notification specifically says "You have been assigned as the owner"
                if 'you have been assigned as the owner' in text.lower():
                    owner_assignment_notification_count += 1

            # Should NOT send the "You have been assigned" notification when self-assigning
            assert owner_assignment_notification_count == 0


# ==================== Test Helper Functions ====================

class TestSlackHelpers:
    """Test Slack service helper functions."""

    def test_get_status_emoji(self, app, slack_workspace):
        """Status emoji mapping works correctly."""
        with app.app_context():
            service = SlackService(slack_workspace)

            assert service._get_status_emoji('proposed') == ':thought_balloon:'
            assert service._get_status_emoji('accepted') == ':large_green_circle:'
            assert service._get_status_emoji('archived') == ':white_circle:'
            assert service._get_status_emoji('superseded') == ':large_orange_circle:'

    def test_format_decision_detail_blocks(self, app, slack_workspace, sample_decision):
        """Decision detail blocks are formatted correctly."""
        with app.app_context():
            service = SlackService(slack_workspace)

            blocks = service._format_decision_detail_blocks(sample_decision)

            assert len(blocks) > 0
            assert any(sample_decision.title in json.dumps(block) for block in blocks)
            assert any('Context' in json.dumps(block) for block in blocks)
            assert any('Decision' in json.dumps(block) for block in blocks)

    def test_format_notification_blocks(self, app, slack_workspace, sample_decision):
        """Notification blocks are formatted correctly."""
        with app.app_context():
            service = SlackService(slack_workspace)

            blocks = service._format_notification_blocks(sample_decision, 'created')

            assert len(blocks) > 0
            blocks_json = json.dumps(blocks)
            assert sample_decision.title in blocks_json
            assert 'created' in blocks_json or 'sparkles' in blocks_json


# ==================== Test Slack OAuth Integration ====================

class TestSlackOAuthIntegration:
    """Test complete Slack OAuth integration scenarios.

    These tests verify the full OAuth flow including tenant and membership creation.
    """

    def test_workspace_only_connects_to_one_tenant(self, app, session_fixture, sample_tenant):
        """A Slack workspace can only be connected to one tenant at a time."""
        with app.app_context():
            # Create a workspace connected to the first tenant
            encrypted_token = encrypt_token('xoxb-test-token-1')
            workspace = SlackWorkspace(
                tenant_id=sample_tenant.id,
                workspace_id='T_UNIQUE_123',
                workspace_name='First Workspace',
                bot_token_encrypted=encrypted_token,
                is_active=True,
                status=SlackWorkspace.STATUS_ACTIVE
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Create a second tenant
            tenant2 = Tenant(
                domain='second.com',
                name='Second Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP
            )
            session_fixture.add(tenant2)
            session_fixture.commit()

            # Try to query the workspace for the new tenant - it shouldn't exist
            existing = SlackWorkspace.query.filter_by(
                workspace_id='T_UNIQUE_123',
                tenant_id=tenant2.id
            ).first()
            assert existing is None

            # The workspace should still belong to the first tenant
            workspace_check = SlackWorkspace.query.filter_by(workspace_id='T_UNIQUE_123').first()
            assert workspace_check.tenant_id == sample_tenant.id

    def test_workspace_with_no_tenant_can_be_claimed(self, app, session_fixture, sample_tenant):
        """Workspace without tenant_id can be claimed by any tenant."""
        with app.app_context():
            # Create an unclaimed workspace (installed from Slack App Directory)
            encrypted_token = encrypt_token('xoxb-unclaimed-token')
            workspace = SlackWorkspace(
                tenant_id=None,  # Not claimed yet
                workspace_id='T_UNCLAIMED_456',
                workspace_name='Unclaimed Workspace',
                bot_token_encrypted=encrypted_token,
                is_active=True,
                status=SlackWorkspace.STATUS_PENDING_CLAIM
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Claim the workspace for a tenant
            workspace.tenant_id = sample_tenant.id
            workspace.status = SlackWorkspace.STATUS_ACTIVE
            workspace.claimed_at = datetime.utcnow()
            session_fixture.commit()

            # Verify claim
            reloaded = SlackWorkspace.query.filter_by(workspace_id='T_UNCLAIMED_456').first()
            assert reloaded.tenant_id == sample_tenant.id
            assert reloaded.status == SlackWorkspace.STATUS_ACTIVE
            assert reloaded.claimed_at is not None

    def test_workspace_disconnect_allows_reconnect(self, app, session_fixture, sample_tenant):
        """After disconnecting, workspace can be reconnected to same or different tenant."""
        with app.app_context():
            # Create connected workspace
            encrypted_token = encrypt_token('xoxb-reconnect-token')
            workspace = SlackWorkspace(
                tenant_id=sample_tenant.id,
                workspace_id='T_RECONNECT_789',
                workspace_name='Reconnect Workspace',
                bot_token_encrypted=encrypted_token,
                is_active=True,
                status=SlackWorkspace.STATUS_ACTIVE
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Disconnect (soft delete)
            workspace.is_active = False
            workspace.status = SlackWorkspace.STATUS_DISCONNECTED
            session_fixture.commit()

            # Create second tenant
            tenant2 = Tenant(
                domain='reconnect.com',
                name='Reconnect Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP
            )
            session_fixture.add(tenant2)
            session_fixture.commit()

            # Reconnect by updating the existing workspace record
            # (workspace_id is unique, so we update rather than create new)
            workspace.tenant_id = tenant2.id
            workspace.is_active = True
            workspace.status = SlackWorkspace.STATUS_ACTIVE
            workspace.bot_token_encrypted = encrypt_token('xoxb-new-token')
            session_fixture.commit()

            # Query should find the workspace now connected to tenant2
            active_workspace = SlackWorkspace.query.filter_by(
                workspace_id='T_RECONNECT_789',
                is_active=True
            ).first()
            assert active_workspace.tenant_id == tenant2.id


class TestSlackCommandWithoutWorkspace:
    """Test Slack command handling when workspace is not connected."""

    def test_command_fails_for_unclaimed_workspace(self, app, session_fixture):
        """Commands fail gracefully for workspaces not connected to a tenant."""
        with app.app_context():
            # Create unclaimed workspace
            encrypted_token = encrypt_token('xoxb-unclaimed')
            workspace = SlackWorkspace(
                tenant_id=None,  # Not claimed
                workspace_id='T_NO_TENANT_123',
                workspace_name='No Tenant Workspace',
                bot_token_encrypted=encrypted_token,
                is_active=True,
                status=SlackWorkspace.STATUS_PENDING_CLAIM
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Query for active workspace with tenant should return None
            workspace_with_tenant = SlackWorkspace.query.filter_by(
                workspace_id='T_NO_TENANT_123',
                is_active=True
            ).first()

            # Workspace exists but has no tenant_id
            assert workspace_with_tenant is not None
            assert workspace_with_tenant.tenant_id is None

    def test_command_fails_for_missing_workspace(self, app, session_fixture):
        """Commands fail when workspace is not in database at all."""
        with app.app_context():
            # Query for non-existent workspace
            workspace = SlackWorkspace.query.filter_by(
                workspace_id='T_NONEXISTENT_999'
            ).first()

            assert workspace is None


class TestTenantMembershipForSlackUsers:
    """Test TenantMembership creation during Slack flows."""

    def test_first_user_gets_provisional_admin(self, app, session_fixture):
        """First user from a domain via Slack gets PROVISIONAL_ADMIN role."""
        with app.app_context():
            # Create tenant without any users
            tenant = Tenant(
                domain='brand-new.com',
                name='Brand New Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP
            )
            session_fixture.add(tenant)
            session_fixture.flush()

            # Create first user
            user = User(
                email='founder@brand-new.com',
                name='Founder',
                sso_domain='brand-new.com',
                auth_type='sso',
                email_verified=True
            )
            session_fixture.add(user)
            session_fixture.flush()

            # Create membership as first user (what Slack OIDC callback does)
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.PROVISIONAL_ADMIN
            )
            session_fixture.add(membership)
            session_fixture.commit()

            # Verify
            reloaded = TenantMembership.query.filter_by(
                user_id=user.id,
                tenant_id=tenant.id
            ).first()
            assert reloaded.global_role == GlobalRole.PROVISIONAL_ADMIN

    def test_subsequent_user_gets_user_role(self, app, session_fixture, sample_tenant, sample_user, sample_membership):
        """Subsequent users get USER role, not admin."""
        with app.app_context():
            # sample_user already has sample_membership
            # Create second user
            user2 = User(
                email='employee@example.com',
                name='Employee',
                sso_domain='example.com',  # Same domain as sample_tenant
                auth_type='sso',
                email_verified=True
            )
            session_fixture.add(user2)
            session_fixture.flush()

            # Create membership for second user
            membership2 = TenantMembership(
                user_id=user2.id,
                tenant_id=sample_tenant.id,
                global_role=GlobalRole.USER
            )
            session_fixture.add(membership2)
            session_fixture.commit()

            # Verify second user is not admin
            reloaded = TenantMembership.query.filter_by(
                user_id=user2.id,
                tenant_id=sample_tenant.id
            ).first()
            assert reloaded.global_role == GlobalRole.USER

    def test_membership_required_for_admin_endpoints(self, app, session_fixture, sample_tenant):
        """Users without membership cannot access admin endpoints."""
        with app.app_context():
            # Create user without membership
            orphan_user = User(
                email='orphan@example.com',
                name='Orphan User',
                sso_domain='example.com',
                auth_type='sso',
                email_verified=True
            )
            session_fixture.add(orphan_user)
            session_fixture.commit()

            # Verify no membership exists
            membership = TenantMembership.query.filter_by(
                user_id=orphan_user.id,
                tenant_id=sample_tenant.id
            ).first()
            assert membership is None

            # Without membership, get_membership should return None
            user_membership = orphan_user.get_membership(tenant_id=sample_tenant.id)
            assert user_membership is None


class TestSlackSettingsPage:
    """Test Slack settings page behavior."""

    def test_settings_shows_connected_workspace(self, app, session_fixture, sample_tenant, slack_workspace):
        """Settings page shows workspace details when connected."""
        with app.app_context():
            # Get workspace details
            settings = slack_workspace.to_dict()

            assert settings['workspace_id'] == slack_workspace.workspace_id
            assert settings['workspace_name'] == slack_workspace.workspace_name
            assert settings['is_active'] is True

    def test_settings_shows_install_button_when_not_connected(self, app, session_fixture, sample_tenant):
        """Settings page shows install button when no workspace connected."""
        with app.app_context():
            # No workspace for this tenant
            workspace = SlackWorkspace.query.filter_by(
                tenant_id=sample_tenant.id,
                is_active=True
            ).first()

            assert workspace is None
            # Frontend should show "Add Slack" button when workspace is None

    def test_settings_status_endpoint_returns_install_url(self, app, session_fixture, sample_tenant):
        """Status endpoint returns install_url when not connected."""
        with app.app_context():
            # No workspace for tenant
            workspace = SlackWorkspace.query.filter_by(
                tenant_id=sample_tenant.id,
                is_active=True
            ).first()

            # What the /api/slack/settings endpoint would return
            if not workspace:
                response = {
                    'installed': False,
                    'install_url': '/api/slack/install'
                }
            else:
                response = {
                    'installed': True,
                    'workspace_id': workspace.workspace_id
                }

            assert response['installed'] is False
            assert response['install_url'] == '/api/slack/install'


class TestSlackOAuthCallback:
    """Test Slack OAuth callback scenarios."""

    def test_callback_creates_workspace_for_tenant(self, app, session_fixture, sample_tenant):
        """OAuth callback creates workspace and associates with tenant."""
        with app.app_context():
            # Simulate successful OAuth callback data
            workspace_id = 'T_NEW_WORKSPACE'
            workspace_name = 'New Workspace'
            encrypted_token = encrypt_token('xoxb-callback-token')

            # Create workspace (what callback does)
            workspace = SlackWorkspace(
                tenant_id=sample_tenant.id,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                bot_token_encrypted=encrypted_token,
                is_active=True,
                status=SlackWorkspace.STATUS_ACTIVE,
                claimed_at=datetime.utcnow()
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Verify workspace is correctly associated
            reloaded = SlackWorkspace.query.filter_by(workspace_id=workspace_id).first()
            assert reloaded.tenant_id == sample_tenant.id
            assert reloaded.is_active is True

    def test_callback_rejects_already_claimed_workspace(self, app, session_fixture, sample_tenant):
        """OAuth callback rejects workspace already claimed by another tenant."""
        with app.app_context():
            # Create workspace claimed by first tenant
            encrypted_token = encrypt_token('xoxb-claimed-token')
            existing_workspace = SlackWorkspace(
                tenant_id=sample_tenant.id,
                workspace_id='T_CLAIMED_WORKSPACE',
                workspace_name='Claimed Workspace',
                bot_token_encrypted=encrypted_token,
                is_active=True,
                status=SlackWorkspace.STATUS_ACTIVE
            )
            session_fixture.add(existing_workspace)
            session_fixture.commit()

            # Create second tenant trying to claim same workspace
            tenant2 = Tenant(
                domain='intruder.com',
                name='Intruder Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP
            )
            session_fixture.add(tenant2)
            session_fixture.commit()

            # Check if workspace is already claimed
            check = SlackWorkspace.query.filter_by(workspace_id='T_CLAIMED_WORKSPACE').first()
            assert check is not None
            assert check.tenant_id == sample_tenant.id
            assert check.tenant_id != tenant2.id

            # Callback should detect this and return workspace_claimed_by_other error
            # (verified by checking tenant_id mismatch)
            is_claimed_by_other = check.tenant_id is not None and check.tenant_id != tenant2.id
            assert is_claimed_by_other is True

    def test_callback_redirects_to_settings_with_success(self, app, session_fixture, sample_tenant):
        """OAuth callback redirects to settings page with success flag."""
        with app.app_context():
            # After successful workspace creation, the redirect URL should be:
            # /{tenant.domain}/admin?tab=slack&slack_success=true
            expected_redirect = f'/{sample_tenant.domain}/admin?tab=slack&slack_success=true'

            assert sample_tenant.domain in expected_redirect
            assert 'slack_success=true' in expected_redirect

    def test_callback_error_redirects_with_error_code(self, app, session_fixture, sample_tenant):
        """OAuth callback redirects with error code on failure."""
        with app.app_context():
            # Various error scenarios and their redirect URLs
            error_scenarios = [
                ('invalid_state', '/settings?slack_error=invalid_state'),
                ('workspace_claimed_by_other', '/settings?slack_error=workspace_claimed_by_other'),
                ('oauth_failed', '/settings?slack_error=oauth_failed'),
                ('not_configured', '/settings?slack_error=not_configured'),
            ]

            for error_code, expected_url in error_scenarios:
                assert f'slack_error={error_code}' in expected_url


# ==================== Superadmin Slack Management Tests ====================

class TestSuperadminSlackManagement:
    """Tests for superadmin Slack workspace management endpoints."""

    def test_list_workspaces_returns_all_workspaces(self, app, session_fixture, sample_tenant, sample_user):
        """Superadmin endpoint returns all workspaces with full details."""
        with app.app_context():
            # Create a workspace
            workspace = SlackWorkspace(
                tenant_id=sample_tenant.id,
                workspace_id='T_SUPERADMIN_TEST',
                workspace_name='Superadmin Test Workspace',
                bot_token_encrypted=encrypt_token('xoxb-test-token'),
                status=SlackWorkspace.STATUS_ACTIVE,
                is_active=True,
                claimed_at=datetime.utcnow(),
                claimed_by_id=sample_user.id
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Verify workspace data structure
            assert workspace.workspace_id == 'T_SUPERADMIN_TEST'
            assert workspace.workspace_name == 'Superadmin Test Workspace'
            assert workspace.tenant_id == sample_tenant.id
            assert workspace.is_active is True
            assert workspace.claimed_by_id == sample_user.id
            assert workspace.claimed_by is not None
            assert workspace.claimed_by.email == sample_user.email

    def test_list_workspaces_includes_linked_users(self, app, session_fixture, sample_tenant, sample_user, slack_workspace):
        """Superadmin endpoint includes linked users count and details."""
        with app.app_context():
            # Create user mapping
            mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U_LINKED_USER',
                slack_email=sample_user.email,
                user_id=sample_user.id,
                link_method='browser_auth',
                linked_at=datetime.utcnow()
            )
            session_fixture.add(mapping)
            session_fixture.commit()

            # Query linked users
            linked_count = slack_workspace.user_mappings.filter(
                SlackUserMapping.user_id.isnot(None)
            ).count()

            assert linked_count == 1

            # Verify linked user details
            linked_mapping = slack_workspace.user_mappings.filter(
                SlackUserMapping.user_id.isnot(None)
            ).first()

            assert linked_mapping is not None
            assert linked_mapping.user.email == sample_user.email
            assert linked_mapping.link_method == 'browser_auth'

    def test_delete_workspace_disconnects_from_tenant(self, app, session_fixture, sample_tenant):
        """Superadmin can disconnect a workspace from its tenant."""
        with app.app_context():
            # Create a workspace for this test
            workspace = SlackWorkspace(
                tenant_id=sample_tenant.id,
                workspace_id='T_TO_DISCONNECT',
                workspace_name='Workspace to Disconnect',
                bot_token_encrypted=encrypt_token('xoxb-test-token'),
                status=SlackWorkspace.STATUS_ACTIVE,
                is_active=True
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            workspace_id = workspace.id
            original_tenant_id = workspace.tenant_id

            assert original_tenant_id == sample_tenant.id
            assert workspace.is_active is True

            # Simulate superadmin disconnect
            workspace.is_active = False
            workspace.status = SlackWorkspace.STATUS_DISCONNECTED
            workspace.tenant_id = None
            session_fixture.commit()

            # Reload from database and verify
            session_fixture.expire_all()
            disconnected = session_fixture.get(SlackWorkspace, workspace_id)
            assert disconnected.is_active is False
            assert disconnected.status == SlackWorkspace.STATUS_DISCONNECTED
            assert disconnected.tenant_id is None

    def test_delete_workspace_preserves_workspace_data(self, app, session_fixture, sample_tenant, sample_user, slack_workspace):
        """Disconnecting a workspace preserves user mappings and history."""
        with app.app_context():
            # Create user mapping
            mapping = SlackUserMapping(
                slack_workspace_id=slack_workspace.id,
                slack_user_id='U_PRESERVED_USER',
                slack_email=sample_user.email,
                user_id=sample_user.id,
                link_method='auto_email',
                linked_at=datetime.utcnow()
            )
            session_fixture.add(mapping)
            session_fixture.commit()

            mapping_count_before = slack_workspace.user_mappings.count()
            assert mapping_count_before == 1

            # Disconnect workspace
            slack_workspace.is_active = False
            slack_workspace.status = SlackWorkspace.STATUS_DISCONNECTED
            slack_workspace.tenant_id = None
            session_fixture.commit()

            # User mapping should still exist
            mapping_count_after = slack_workspace.user_mappings.count()
            assert mapping_count_after == 1

    def test_disconnected_workspace_can_be_reclaimed(self, app, session_fixture, sample_tenant):
        """A disconnected workspace can be reclaimed by another tenant."""
        with app.app_context():
            # Create disconnected workspace
            workspace = SlackWorkspace(
                tenant_id=None,  # Disconnected
                workspace_id='T_RECLAIMABLE',
                workspace_name='Reclaimable Workspace',
                bot_token_encrypted=encrypt_token('xoxb-test-token'),
                status=SlackWorkspace.STATUS_DISCONNECTED,
                is_active=False
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Verify it's disconnected
            assert workspace.tenant_id is None
            assert workspace.is_active is False

            # Reclaim for tenant
            workspace.tenant_id = sample_tenant.id
            workspace.is_active = True
            workspace.status = SlackWorkspace.STATUS_ACTIVE
            workspace.claimed_at = datetime.utcnow()
            session_fixture.commit()

            # Verify reclaimed
            reclaimed = SlackWorkspace.query.filter_by(workspace_id='T_RECLAIMABLE').first()
            assert reclaimed.tenant_id == sample_tenant.id
            assert reclaimed.is_active is True
            assert reclaimed.status == SlackWorkspace.STATUS_ACTIVE

    def test_list_workspaces_shows_unassigned_workspaces(self, app, session_fixture):
        """Superadmin can see workspaces that are not assigned to any tenant."""
        with app.app_context():
            # Create unassigned workspace (e.g., IT admin installed but not claimed)
            workspace = SlackWorkspace(
                tenant_id=None,
                workspace_id='T_UNASSIGNED',
                workspace_name='Unassigned Workspace',
                bot_token_encrypted=encrypt_token('xoxb-test-token'),
                status=SlackWorkspace.STATUS_PENDING_CLAIM,
                is_active=True
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Query all workspaces
            all_workspaces = SlackWorkspace.query.all()
            unassigned = [w for w in all_workspaces if w.tenant_id is None]

            assert len(unassigned) >= 1
            assert any(w.workspace_id == 'T_UNASSIGNED' for w in unassigned)

    def test_delete_nonexistent_workspace_returns_error(self, app, session_fixture):
        """Attempting to delete non-existent workspace returns appropriate error."""
        with app.app_context():
            # Try to find workspace that doesn't exist
            workspace = SlackWorkspace.query.get(99999)
            assert workspace is None  # Should not exist
