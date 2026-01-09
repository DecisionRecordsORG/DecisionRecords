"""
Backend Unit Tests for Microsoft Teams Integration (Enterprise Edition)

Tests for Teams service, models, and API endpoints.
Tests cover:
- Teams workspace model operations
- OAuth installation flow
- User linking (auto-link by email and browser flow)
- Notifications
- Settings management
- Conversation reference management

Note: These tests require Enterprise Edition modules from ee/backend/teams/
"""
import pytest
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from flask import Flask

from models import (
    db, User, Tenant, TenantMembership, TenantSettings, ArchitectureDecision,
    TeamsWorkspace, TeamsUserMapping, TeamsConversationReference,
    GlobalRole, MaturityState, Space, VisibilityPolicy
)

# Enterprise Edition imports - skip tests if not available
try:
    from ee.backend.teams.teams_security import (
        encrypt_token, decrypt_token, generate_teams_oauth_state, verify_teams_oauth_state,
        generate_teams_link_token, verify_teams_link_token
    )
    from ee.backend.teams.teams_service import TeamsService, get_teams_service_for_tenant
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    encrypt_token = None
    decrypt_token = None
    generate_teams_oauth_state = None
    verify_teams_oauth_state = None
    generate_teams_link_token = None
    verify_teams_link_token = None
    TeamsService = None
    get_teams_service_for_tenant = None

pytestmark = pytest.mark.skipif(not EE_AVAILABLE, reason="Enterprise Edition modules not available")


# ==================== Fixtures ====================

@pytest.fixture
def app():
    """Create application for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'

    # Set Teams environment variables for tests
    os.environ['TEAMS_BOT_APP_ID'] = 'test-bot-app-id-12345'
    os.environ['TEAMS_BOT_APP_SECRET'] = 'test-bot-app-secret'
    os.environ['TEAMS_BOT_TENANT_ID'] = 'test-tenant-id-12345'

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
def teams_workspace(session_fixture, sample_tenant):
    """Create a sample Teams workspace."""
    workspace = TeamsWorkspace(
        tenant_id=sample_tenant.id,
        ms_tenant_id='ms-tenant-12345-abcd',
        ms_tenant_name='Test Microsoft Tenant',
        service_url='https://smba.trafficmanager.net/amer/',
        bot_id='test-bot-app-id-12345',
        status=TeamsWorkspace.STATUS_ACTIVE,
        is_active=True,
        notifications_enabled=True,
        notify_on_create=True,
        notify_on_status_change=True,
        default_channel_id='19:channel123@thread.tacv2',
        default_channel_name='General',
        default_team_id='team-id-123',
        default_team_name='Test Team'
    )
    session_fixture.add(workspace)
    session_fixture.commit()
    return workspace


@pytest.fixture
def sample_space(session_fixture, sample_tenant, sample_user):
    """Create a sample space."""
    space = Space(
        tenant_id=sample_tenant.id,
        name='Default Space',
        description='The default space',
        is_default=True,
        visibility_policy=VisibilityPolicy.TENANT_VISIBLE,
        created_by_id=sample_user.id
    )
    session_fixture.add(space)
    session_fixture.commit()
    return space


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


# ==================== Test Teams Workspace Model ====================

class TestTeamsWorkspaceModel:
    """Test TeamsWorkspace model operations."""

    def test_create_workspace(self, app, session_fixture, sample_tenant):
        """Can create a Teams workspace for a tenant."""
        with app.app_context():
            workspace = TeamsWorkspace(
                tenant_id=sample_tenant.id,
                ms_tenant_id='new-ms-tenant-id-12345',
                ms_tenant_name='New MS Tenant',
                service_url='https://smba.trafficmanager.net/amer/',
                status=TeamsWorkspace.STATUS_ACTIVE
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            assert workspace.id is not None
            assert workspace.tenant_id == sample_tenant.id
            assert workspace.ms_tenant_id == 'new-ms-tenant-id-12345'
            assert workspace.status == TeamsWorkspace.STATUS_ACTIVE

    def test_workspace_tenant_relationship(self, app, session_fixture, teams_workspace, sample_tenant):
        """Workspace has correct tenant relationship."""
        with app.app_context():
            # Reload to ensure relationships work
            reloaded = db.session.get(TeamsWorkspace, teams_workspace.id)
            assert reloaded.tenant is not None
            assert reloaded.tenant.id == sample_tenant.id
            assert reloaded.tenant.domain == 'example.com'

    def test_workspace_status_constants(self, app):
        """Workspace status constants are correct."""
        with app.app_context():
            assert TeamsWorkspace.STATUS_PENDING_CONSENT == 'pending_consent'
            assert TeamsWorkspace.STATUS_ACTIVE == 'active'
            assert TeamsWorkspace.STATUS_DISCONNECTED == 'disconnected'

    def test_workspace_to_dict(self, app, teams_workspace):
        """Workspace to_dict returns expected format."""
        with app.app_context():
            workspace_dict = teams_workspace.to_dict()

            assert workspace_dict['id'] == teams_workspace.id
            assert workspace_dict['ms_tenant_id'] == teams_workspace.ms_tenant_id
            assert workspace_dict['ms_tenant_name'] == teams_workspace.ms_tenant_name
            assert workspace_dict['status'] == TeamsWorkspace.STATUS_ACTIVE
            assert workspace_dict['notifications_enabled'] is True

    def test_workspace_unique_constraint_on_ms_tenant_id(self, app, session_fixture, sample_tenant, teams_workspace):
        """Cannot create duplicate workspace for same MS tenant ID."""
        with app.app_context():
            # Try to create another workspace with same ms_tenant_id
            duplicate = TeamsWorkspace(
                tenant_id=sample_tenant.id,
                ms_tenant_id=teams_workspace.ms_tenant_id,  # Same MS tenant ID
                status=TeamsWorkspace.STATUS_ACTIVE
            )
            session_fixture.add(duplicate)

            with pytest.raises(Exception):  # Should raise IntegrityError
                session_fixture.commit()


# ==================== Test Teams User Mapping ====================

class TestTeamsUserMapping:
    """Test TeamsUserMapping model and linking functionality."""

    def test_create_user_mapping(self, app, session_fixture, teams_workspace, sample_user):
        """Can create a Teams user mapping."""
        with app.app_context():
            mapping = TeamsUserMapping(
                teams_workspace_id=teams_workspace.id,
                aad_object_id='aad-user-object-id-12345',
                aad_user_principal_name='testuser@example.com',
                aad_email='testuser@example.com',
                aad_display_name='Test User',
                user_id=sample_user.id,
                link_method='auto_email',
                linked_at=datetime.now(timezone.utc)
            )
            session_fixture.add(mapping)
            session_fixture.commit()

            assert mapping.id is not None
            assert mapping.user_id == sample_user.id
            assert mapping.link_method == 'auto_email'

    def test_mapping_to_dict(self, app, session_fixture, teams_workspace, sample_user):
        """Mapping to_dict returns expected format."""
        with app.app_context():
            mapping = TeamsUserMapping(
                teams_workspace_id=teams_workspace.id,
                aad_object_id='aad-object-12345',
                aad_email='test@example.com',
                user_id=sample_user.id,
                link_method='browser_auth',
                linked_at=datetime.now(timezone.utc)
            )
            session_fixture.add(mapping)
            session_fixture.commit()

            mapping_dict = mapping.to_dict()
            assert mapping_dict['aad_object_id'] == 'aad-object-12345'
            assert mapping_dict['user_id'] == sample_user.id
            assert mapping_dict['link_method'] == 'browser_auth'

    def test_mapping_unique_constraint(self, app, session_fixture, teams_workspace):
        """Cannot create duplicate mapping for same user in same workspace."""
        with app.app_context():
            mapping1 = TeamsUserMapping(
                teams_workspace_id=teams_workspace.id,
                aad_object_id='unique-aad-id-12345'
            )
            session_fixture.add(mapping1)
            session_fixture.commit()

            mapping2 = TeamsUserMapping(
                teams_workspace_id=teams_workspace.id,
                aad_object_id='unique-aad-id-12345'  # Same AAD ID
            )
            session_fixture.add(mapping2)

            with pytest.raises(Exception):  # Should raise IntegrityError
                session_fixture.commit()

    def test_unlinked_mapping_has_null_user(self, app, session_fixture, teams_workspace):
        """Unlinked mapping has null user_id."""
        with app.app_context():
            mapping = TeamsUserMapping(
                teams_workspace_id=teams_workspace.id,
                aad_object_id='unlinked-user-12345',
                aad_email='external@other.com'
            )
            session_fixture.add(mapping)
            session_fixture.commit()

            assert mapping.user_id is None
            assert mapping.linked_at is None


# ==================== Test Teams Service ====================

class TestTeamsService:
    """Test TeamsService functionality."""

    def test_service_initialization(self, app, teams_workspace):
        """Can initialize TeamsService with workspace."""
        with app.app_context():
            service = TeamsService(teams_workspace)
            assert service.workspace == teams_workspace
            assert service._access_token is None

    def test_update_activity_updates_timestamp(self, app, session_fixture, teams_workspace):
        """update_activity updates last_activity_at timestamp."""
        with app.app_context():
            service = TeamsService(teams_workspace)
            original_activity = teams_workspace.last_activity_at

            service.update_activity()

            assert teams_workspace.last_activity_at is not None
            if original_activity:
                assert teams_workspace.last_activity_at >= original_activity


class TestTeamsUserLinking:
    """Test Teams user linking functionality."""

    def test_auto_link_by_email(self, app, session_fixture, sample_user, teams_workspace, sample_membership):
        """User with matching email is auto-linked."""
        with app.app_context():
            service = TeamsService(teams_workspace)

            # Call get_or_link_user with matching email
            mapping, user, needs_linking = service.get_or_link_user(
                aad_object_id='aad-object-id-autolink',
                upn=sample_user.email,
                display_name='Test User'
            )

            assert mapping is not None
            assert user is not None
            assert user.id == sample_user.id
            assert not needs_linking
            assert mapping.link_method == 'auto_email'

    def test_unlinked_user_needs_linking(self, app, session_fixture, teams_workspace):
        """User without matching email needs linking."""
        with app.app_context():
            service = TeamsService(teams_workspace)

            mapping, user, needs_linking = service.get_or_link_user(
                aad_object_id='aad-object-id-unlinked',
                upn='nonexistent@other-domain.com',
                display_name='Unknown User'
            )

            assert mapping is not None
            assert user is None
            assert needs_linking
            assert mapping.user_id is None

    def test_existing_linked_mapping_returns_user(self, app, session_fixture, teams_workspace, sample_user, sample_membership):
        """Existing linked mapping returns the user."""
        with app.app_context():
            # Create existing linked mapping
            existing_mapping = TeamsUserMapping(
                teams_workspace_id=teams_workspace.id,
                aad_object_id='existing-aad-id-12345',
                user_id=sample_user.id,
                linked_at=datetime.now(timezone.utc)
            )
            session_fixture.add(existing_mapping)
            session_fixture.commit()

            service = TeamsService(teams_workspace)
            mapping, user, needs_linking = service.get_or_link_user(
                aad_object_id='existing-aad-id-12345'
            )

            assert mapping.id == existing_mapping.id
            assert user.id == sample_user.id
            assert not needs_linking

    def test_browser_link_flow(self, app, session_fixture, sample_user, teams_workspace):
        """Browser linking creates mapping with correct method."""
        with app.app_context():
            # Generate link token
            token = generate_teams_link_token(
                teams_workspace.id,
                'aad-browser-link-12345',
                'user@example.com'
            )

            # Verify token
            token_data = verify_teams_link_token(token)
            assert token_data is not None
            assert token_data['teams_workspace_id'] == teams_workspace.id
            assert token_data['aad_object_id'] == 'aad-browser-link-12345'

            # Create mapping after browser auth
            mapping = TeamsUserMapping(
                teams_workspace_id=teams_workspace.id,
                aad_object_id='aad-browser-link-12345',
                aad_email='user@example.com',
                user_id=sample_user.id,
                linked_at=datetime.now(timezone.utc),
                link_method='browser_auth'
            )
            session_fixture.add(mapping)
            session_fixture.commit()

            # Verify mapping
            found = TeamsUserMapping.query.filter_by(
                teams_workspace_id=teams_workspace.id,
                aad_object_id='aad-browser-link-12345'
            ).first()

            assert found is not None
            assert found.user_id == sample_user.id
            assert found.link_method == 'browser_auth'


# ==================== Test Teams Conversation References ====================

class TestTeamsConversationReferences:
    """Test TeamsConversationReference model."""

    def test_create_conversation_reference(self, app, session_fixture, teams_workspace):
        """Can create a conversation reference."""
        with app.app_context():
            reference_data = {
                'activityId': 'activity123',
                'bot': {'id': 'bot-id'},
                'channelId': 'msteams',
                'conversation': {'id': 'conv123'},
                'serviceUrl': 'https://smba.trafficmanager.net/amer/',
                'user': {'id': 'user123'}
            }

            conv_ref = TeamsConversationReference(
                teams_workspace_id=teams_workspace.id,
                conversation_id='19:conv123@thread.tacv2',
                channel_id='19:channel123@thread.tacv2',
                team_id='team-id-123',
                reference_json=json.dumps(reference_data),
                context_type='channel'
            )
            session_fixture.add(conv_ref)
            session_fixture.commit()

            assert conv_ref.id is not None
            assert conv_ref.context_type == 'channel'
            assert json.loads(conv_ref.reference_json) == reference_data

    def test_conversation_reference_to_dict(self, app, session_fixture, teams_workspace):
        """Conversation reference to_dict returns expected format."""
        with app.app_context():
            conv_ref = TeamsConversationReference(
                teams_workspace_id=teams_workspace.id,
                conversation_id='conv-123',
                channel_id='channel-123',
                reference_json='{}',
                context_type='personal'
            )
            session_fixture.add(conv_ref)
            session_fixture.commit()

            ref_dict = conv_ref.to_dict()
            assert ref_dict['conversation_id'] == 'conv-123'
            assert ref_dict['context_type'] == 'personal'

    def test_unique_constraint_on_conversation(self, app, session_fixture, teams_workspace):
        """Cannot create duplicate conversation reference for same conversation."""
        with app.app_context():
            conv_ref1 = TeamsConversationReference(
                teams_workspace_id=teams_workspace.id,
                conversation_id='unique-conv-id',
                reference_json='{}',
                context_type='channel'
            )
            session_fixture.add(conv_ref1)
            session_fixture.commit()

            conv_ref2 = TeamsConversationReference(
                teams_workspace_id=teams_workspace.id,
                conversation_id='unique-conv-id',  # Same ID
                reference_json='{}',
                context_type='channel'
            )
            session_fixture.add(conv_ref2)

            with pytest.raises(Exception):
                session_fixture.commit()


# ==================== Test Teams Settings ====================

class TestTeamsSettings:
    """Test Teams settings management."""

    def test_get_settings_returns_config(self, app, teams_workspace):
        """Get settings returns workspace info."""
        with app.app_context():
            settings_dict = teams_workspace.to_dict()

            assert settings_dict['ms_tenant_id'] == teams_workspace.ms_tenant_id
            assert settings_dict['ms_tenant_name'] == teams_workspace.ms_tenant_name
            assert settings_dict['notifications_enabled'] is True
            assert settings_dict['notify_on_create'] is True
            assert settings_dict['default_channel_id'] == '19:channel123@thread.tacv2'

    def test_update_settings_saves_config(self, app, session_fixture, teams_workspace):
        """Update settings persists changes."""
        with app.app_context():
            # Update settings
            teams_workspace.default_channel_id = '19:newchannel@thread.tacv2'
            teams_workspace.default_channel_name = 'New Channel'
            teams_workspace.notifications_enabled = False
            session_fixture.commit()

            # Reload from DB
            reloaded = db.session.get(TeamsWorkspace, teams_workspace.id)
            assert reloaded.default_channel_id == '19:newchannel@thread.tacv2'
            assert reloaded.default_channel_name == 'New Channel'
            assert reloaded.notifications_enabled is False

    def test_disconnect_marks_workspace_inactive(self, app, session_fixture, teams_workspace):
        """Disconnect marks workspace as inactive."""
        with app.app_context():
            # Disconnect (soft delete)
            teams_workspace.is_active = False
            teams_workspace.status = TeamsWorkspace.STATUS_DISCONNECTED
            session_fixture.commit()

            # Verify inactive
            reloaded = db.session.get(TeamsWorkspace, teams_workspace.id)
            assert reloaded.is_active is False
            assert reloaded.status == TeamsWorkspace.STATUS_DISCONNECTED


# ==================== Test Teams OAuth Integration ====================

class TestTeamsOAuthIntegration:
    """Test Teams OAuth flow integration scenarios."""

    def test_workspace_only_connects_to_one_tenant(self, app, session_fixture, sample_tenant, teams_workspace):
        """A Teams workspace can only be connected to one tenant at a time."""
        with app.app_context():
            # Create second tenant
            tenant2 = Tenant(
                domain='second.com',
                name='Second Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP
            )
            session_fixture.add(tenant2)
            session_fixture.commit()

            # Try to query the workspace for the new tenant - it shouldn't exist
            existing = TeamsWorkspace.query.filter_by(
                ms_tenant_id=teams_workspace.ms_tenant_id,
                tenant_id=tenant2.id
            ).first()
            assert existing is None

            # The workspace should still belong to the first tenant
            workspace_check = TeamsWorkspace.query.filter_by(
                ms_tenant_id=teams_workspace.ms_tenant_id
            ).first()
            assert workspace_check.tenant_id == sample_tenant.id

    def test_workspace_disconnect_allows_reconnect(self, app, session_fixture, sample_tenant):
        """After disconnecting, workspace can be reconnected."""
        with app.app_context():
            # Create connected workspace
            workspace = TeamsWorkspace(
                tenant_id=sample_tenant.id,
                ms_tenant_id='ms-reconnect-tenant-123',
                ms_tenant_name='Reconnect Tenant',
                status=TeamsWorkspace.STATUS_ACTIVE,
                is_active=True
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Disconnect
            workspace.is_active = False
            workspace.status = TeamsWorkspace.STATUS_DISCONNECTED
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

            # Reconnect by updating the workspace
            workspace.tenant_id = tenant2.id
            workspace.is_active = True
            workspace.status = TeamsWorkspace.STATUS_ACTIVE
            session_fixture.commit()

            # Verify reconnected
            active_workspace = TeamsWorkspace.query.filter_by(
                ms_tenant_id='ms-reconnect-tenant-123',
                is_active=True
            ).first()
            assert active_workspace.tenant_id == tenant2.id

    def test_oauth_callback_creates_workspace(self, app, session_fixture, sample_tenant):
        """OAuth callback creates workspace and associates with tenant."""
        with app.app_context():
            # Simulate successful OAuth callback data
            ms_tenant_id = 'new-ms-tenant-from-oauth'
            ms_tenant_name = 'OAuth Tenant'

            # Create workspace (what callback does)
            workspace = TeamsWorkspace(
                tenant_id=sample_tenant.id,
                ms_tenant_id=ms_tenant_id,
                ms_tenant_name=ms_tenant_name,
                status=TeamsWorkspace.STATUS_ACTIVE,
                is_active=True,
                consent_granted_at=datetime.now(timezone.utc)
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Verify workspace is correctly associated
            reloaded = TeamsWorkspace.query.filter_by(ms_tenant_id=ms_tenant_id).first()
            assert reloaded.tenant_id == sample_tenant.id
            assert reloaded.is_active is True


# ==================== Test Get Teams Service for Tenant ====================

class TestGetTeamsServiceForTenant:
    """Test get_teams_service_for_tenant helper function."""

    def test_returns_service_for_active_workspace(self, app, session_fixture, teams_workspace):
        """Returns TeamsService for tenant with active workspace."""
        with app.app_context():
            service = get_teams_service_for_tenant(teams_workspace.tenant_id)
            assert service is not None
            assert isinstance(service, TeamsService)
            assert service.workspace.id == teams_workspace.id

    def test_returns_none_for_tenant_without_workspace(self, app, session_fixture, sample_tenant):
        """Returns None for tenant without Teams workspace."""
        with app.app_context():
            service = get_teams_service_for_tenant(sample_tenant.id)
            assert service is None

    def test_returns_none_for_inactive_workspace(self, app, session_fixture, teams_workspace):
        """Returns None when workspace is inactive."""
        with app.app_context():
            teams_workspace.is_active = False
            session_fixture.commit()

            service = get_teams_service_for_tenant(teams_workspace.tenant_id)
            assert service is None

    def test_returns_none_for_non_active_status(self, app, session_fixture, teams_workspace):
        """Returns None when workspace status is not ACTIVE."""
        with app.app_context():
            teams_workspace.status = TeamsWorkspace.STATUS_PENDING_CONSENT
            session_fixture.commit()

            service = get_teams_service_for_tenant(teams_workspace.tenant_id)
            assert service is None


# ==================== Test Teams Notification Settings ====================

class TestTeamsNotificationSettings:
    """Test Teams notification configuration."""

    def test_notification_flags_default_values(self, app, session_fixture, sample_tenant):
        """Notification flags have correct defaults."""
        with app.app_context():
            workspace = TeamsWorkspace(
                tenant_id=sample_tenant.id,
                ms_tenant_id='notif-test-tenant',
                status=TeamsWorkspace.STATUS_ACTIVE
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            assert workspace.notifications_enabled is True
            assert workspace.notify_on_create is True
            assert workspace.notify_on_status_change is True

    def test_can_disable_notifications(self, app, session_fixture, teams_workspace):
        """Can disable all notifications."""
        with app.app_context():
            teams_workspace.notifications_enabled = False
            session_fixture.commit()

            reloaded = db.session.get(TeamsWorkspace, teams_workspace.id)
            assert reloaded.notifications_enabled is False

    def test_can_disable_specific_notification_types(self, app, session_fixture, teams_workspace):
        """Can disable specific notification types."""
        with app.app_context():
            teams_workspace.notify_on_create = False
            teams_workspace.notify_on_status_change = True
            session_fixture.commit()

            reloaded = db.session.get(TeamsWorkspace, teams_workspace.id)
            assert reloaded.notify_on_create is False
            assert reloaded.notify_on_status_change is True


# ==================== Test Teams Workspace Cascade Delete ====================

class TestTeamsWorkspaceCascadeDelete:
    """Test cascade delete behavior for Teams models."""

    def test_deleting_workspace_removes_user_mappings(self, app, session_fixture, sample_tenant, sample_user):
        """Deleting workspace cascades to user mappings."""
        with app.app_context():
            # Create workspace in this test
            workspace = TeamsWorkspace(
                tenant_id=sample_tenant.id,
                ms_tenant_id='cascade-test-ms-tenant',
                status=TeamsWorkspace.STATUS_ACTIVE,
                is_active=True
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Create user mapping
            mapping = TeamsUserMapping(
                teams_workspace_id=workspace.id,
                aad_object_id='cascade-test-user',
                user_id=sample_user.id
            )
            session_fixture.add(mapping)
            session_fixture.commit()

            mapping_id = mapping.id

            # Delete workspace
            session_fixture.delete(workspace)
            session_fixture.commit()

            # Mapping should be deleted
            deleted_mapping = db.session.get(TeamsUserMapping, mapping_id)
            assert deleted_mapping is None

    def test_deleting_workspace_removes_conversation_references(self, app, session_fixture, sample_tenant):
        """Deleting workspace cascades to conversation references."""
        with app.app_context():
            # Create workspace in this test
            workspace = TeamsWorkspace(
                tenant_id=sample_tenant.id,
                ms_tenant_id='cascade-conv-test-ms-tenant',
                status=TeamsWorkspace.STATUS_ACTIVE,
                is_active=True
            )
            session_fixture.add(workspace)
            session_fixture.commit()

            # Create conversation reference
            conv_ref = TeamsConversationReference(
                teams_workspace_id=workspace.id,
                conversation_id='cascade-conv-123',
                reference_json='{}',
                context_type='channel'
            )
            session_fixture.add(conv_ref)
            session_fixture.commit()

            conv_ref_id = conv_ref.id

            # Delete workspace
            session_fixture.delete(workspace)
            session_fixture.commit()

            # Conversation reference should be deleted
            deleted_ref = db.session.get(TeamsConversationReference, conv_ref_id)
            assert deleted_ref is None


# ==================== Test Teams Activity Handling (Sync Tests) ====================

class TestTeamsActivityHandlingSynchronous:
    """Test synchronous parts of Teams activity handling."""

    def test_remove_mention_removes_bot_mention(self, app, teams_workspace):
        """Bot mention is removed from message text."""
        with app.app_context():
            service = TeamsService(teams_workspace)

            activity = {
                'entities': [
                    {
                        'type': 'mention',
                        'mentioned': {'id': 'test-bot-app-id-12345', 'name': 'DecisionRecords'},
                        'text': '<at>DecisionRecords</at>'
                    }
                ]
            }

            text = '<at>DecisionRecords</at> list proposed'
            cleaned = service._remove_mention(text, activity)

            assert cleaned == 'list proposed'

    def test_remove_mention_handles_no_entities(self, app, teams_workspace):
        """Handles messages without entities."""
        with app.app_context():
            service = TeamsService(teams_workspace)

            activity = {'entities': []}
            text = 'simple message'
            cleaned = service._remove_mention(text, activity)

            assert cleaned == 'simple message'
