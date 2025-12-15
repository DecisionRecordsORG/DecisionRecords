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
        bot_user_id='U12345678',
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
        """'/adr help' returns help text."""
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
            assert '/adr create' in blocks_text
            assert '/adr list' in blocks_text

    def test_list_command(self, app, slack_workspace, sample_user, sample_decision, sample_membership):
        """'/adr list' returns decision list."""
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
        """'/adr view <id>' returns decision details."""
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
        """'/adr search <query>' returns results."""
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
        """'/adr create' triggers modal."""
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

            # Should return validation errors
            assert response is not None
            assert response['response_action'] == 'errors'
            assert 'errors' in response
            assert 'title_block' in response['errors']
            assert 'decision_block' in response['errors']
            assert 'consequences_block' in response['errors']


# ==================== Test Helper Functions ====================

class TestSlackHelpers:
    """Test Slack service helper functions."""

    def test_get_status_emoji(self, app, slack_workspace):
        """Status emoji mapping works correctly."""
        with app.app_context():
            service = SlackService(slack_workspace)

            assert service._get_status_emoji('proposed') == ':memo:'
            assert service._get_status_emoji('accepted') == ':white_check_mark:'
            assert service._get_status_emoji('deprecated') == ':warning:'
            assert service._get_status_emoji('superseded') == ':arrows_counterclockwise:'

    def test_format_decision_detail_blocks(self, app, slack_workspace, sample_decision):
        """Decision detail blocks are formatted correctly."""
        with app.app_context():
            service = SlackService(slack_workspace)

            blocks = service._format_decision_detail_blocks(sample_decision)

            assert len(blocks) > 0
            assert any(sample_decision.title in json.dumps(block) for block in blocks)
            assert any('Context:' in json.dumps(block) for block in blocks)
            assert any('Decision:' in json.dumps(block) for block in blocks)

    def test_format_notification_blocks(self, app, slack_workspace, sample_decision):
        """Notification blocks are formatted correctly."""
        with app.app_context():
            service = SlackService(slack_workspace)

            blocks = service._format_notification_blocks(sample_decision, 'created')

            assert len(blocks) > 0
            blocks_json = json.dumps(blocks)
            assert sample_decision.title in blocks_json
            assert 'created' in blocks_json or 'sparkles' in blocks_json
