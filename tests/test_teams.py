"""
Tests for Microsoft Teams integration (Enterprise Edition).

Tests cover:
1. Teams Cards - Adaptive card building functions
2. Teams Service - Message handling, button actions, space filtering
3. Button Action Handling - Processing Action.Submit clicks

Note: These tests require Enterprise Edition modules from ee/backend/teams/
"""
import pytest
from datetime import datetime, timezone
from flask import Flask
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, Space, DecisionSpace,
    ArchitectureDecision, GlobalRole, MaturityState, VisibilityPolicy,
    TeamsWorkspace, TeamsUserMapping
)

# Enterprise Edition imports - skip tests if not available
try:
    from ee.backend.teams.teams_cards import (
        build_space_selector_card, build_decision_list_card,
        build_menu_card, build_help_card, build_error_card,
        build_create_decision_form_card, build_greeting_card,
        build_decision_detail_card, build_create_prompt_card
    )
    from ee.backend.teams.teams_service import TeamsService
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    build_space_selector_card = None
    build_decision_list_card = None
    build_create_decision_form_card = None
    TeamsService = None

pytestmark = pytest.mark.skipif(not EE_AVAILABLE, reason="Enterprise Edition modules not available")


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def app():
    """Create application for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'

    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def session(app):
    """Create database session for testing."""
    with app.app_context():
        yield db.session


@pytest.fixture
def sample_tenant(session):
    """Create a sample tenant."""
    tenant = Tenant(
        domain='example.com',
        name='Example Corp',
        status='active',
        maturity_state=MaturityState.BOOTSTRAP
    )
    session.add(tenant)
    session.commit()
    return tenant


@pytest.fixture
def sample_user(session, sample_tenant):
    """Create a sample user with tenant membership."""
    user = User(
        email='test@example.com',
        sso_domain='example.com',
        auth_type='local',
        email_verified=True
    )
    user.set_name(first_name='Test', last_name='User')
    session.add(user)
    session.flush()

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=sample_tenant.id,
        global_role=GlobalRole.USER
    )
    session.add(membership)
    session.commit()
    return user


@pytest.fixture
def sample_spaces(session, sample_tenant, sample_user):
    """Create multiple spaces for testing."""
    spaces = []

    # Default space
    default_space = Space(
        tenant_id=sample_tenant.id,
        name='Default',
        description='The default space',
        is_default=True,
        visibility_policy=VisibilityPolicy.TENANT_VISIBLE,
        created_by_id=sample_user.id
    )
    session.add(default_space)
    spaces.append(default_space)

    # Engineering space
    eng_space = Space(
        tenant_id=sample_tenant.id,
        name='Engineering',
        description='Engineering decisions',
        is_default=False,
        visibility_policy=VisibilityPolicy.TENANT_VISIBLE,
        created_by_id=sample_user.id
    )
    session.add(eng_space)
    spaces.append(eng_space)

    # Platform space
    platform_space = Space(
        tenant_id=sample_tenant.id,
        name='Platform',
        description='Platform team decisions',
        is_default=False,
        visibility_policy=VisibilityPolicy.TENANT_VISIBLE,
        created_by_id=sample_user.id
    )
    session.add(platform_space)
    spaces.append(platform_space)

    session.commit()
    return spaces


@pytest.fixture
def sample_decisions(session, sample_tenant, sample_user, sample_spaces):
    """Create sample decisions in different spaces."""
    decisions = []

    # Decision in Engineering space
    eng_decision = ArchitectureDecision(
        title='Use Kubernetes for orchestration',
        context='We need container orchestration',
        decision='We will use Kubernetes',
        status='accepted',
        consequences='Learning curve, but scalable',
        domain=sample_tenant.domain,
        tenant_id=sample_tenant.id,
        created_by_id=sample_user.id,
        decision_number=1
    )
    session.add(eng_decision)
    session.flush()

    # Link to Engineering space
    eng_link = DecisionSpace(
        decision_id=eng_decision.id,
        space_id=sample_spaces[1].id  # Engineering
    )
    session.add(eng_link)
    decisions.append(eng_decision)

    # Decision in Platform space
    platform_decision = ArchitectureDecision(
        title='Use PostgreSQL for database',
        context='Need a relational database',
        decision='PostgreSQL for its features',
        status='proposed',
        consequences='Good tooling support',
        domain=sample_tenant.domain,
        tenant_id=sample_tenant.id,
        created_by_id=sample_user.id,
        decision_number=2
    )
    session.add(platform_decision)
    session.flush()

    # Link to Platform space
    platform_link = DecisionSpace(
        decision_id=platform_decision.id,
        space_id=sample_spaces[2].id  # Platform
    )
    session.add(platform_link)
    decisions.append(platform_decision)

    # Decision in Default space
    default_decision = ArchitectureDecision(
        title='Adopt ADR format',
        context='Need structured decisions',
        decision='Use arc42 ADR format',
        status='accepted',
        consequences='Better documentation',
        domain=sample_tenant.domain,
        tenant_id=sample_tenant.id,
        created_by_id=sample_user.id,
        decision_number=3
    )
    session.add(default_decision)
    session.flush()

    # Link to Default space
    default_link = DecisionSpace(
        decision_id=default_decision.id,
        space_id=sample_spaces[0].id  # Default
    )
    session.add(default_link)
    decisions.append(default_decision)

    session.commit()
    return decisions


@pytest.fixture
def teams_workspace(session, sample_tenant):
    """Create a Teams workspace for testing."""
    workspace = TeamsWorkspace(
        ms_tenant_id='test-ms-tenant-id',
        ms_tenant_name='Test Tenant',
        is_active=True,
        tenant_id=sample_tenant.id
    )
    session.add(workspace)
    session.commit()
    return workspace


# ============================================================================
# TEAMS CARDS TESTS
# ============================================================================

class TestBuildSpaceSelectorCard:
    """Tests for build_space_selector_card function."""

    def test_builds_card_with_spaces(self, app, session, sample_spaces):
        """Card should contain buttons for each space (no 'All Spaces' option)."""
        card = build_space_selector_card(sample_spaces)

        assert card['type'] == 'AdaptiveCard'
        assert 'actions' in card

        # Should have 3 spaces = 3 actions (no "All Spaces")
        assert len(card['actions']) == 3

        # All actions should have list_by_space action with space_id
        for action in card['actions']:
            assert action['data']['action'] == 'list_by_space'
            assert action['data']['space_id'] is not None

    def test_includes_space_names_in_buttons(self, app, session, sample_spaces):
        """Each space button should have the space name."""
        card = build_space_selector_card(sample_spaces)

        # Check space names appear
        space_titles = [a['title'] for a in card['actions']]
        assert any('Default' in t for t in space_titles)
        assert any('Engineering' in t for t in space_titles)
        assert any('Platform' in t for t in space_titles)

    def test_marks_default_space_with_star(self, app, session, sample_spaces):
        """Default space should have a star icon."""
        card = build_space_selector_card(sample_spaces)

        # Find the default space action
        default_action = next(
            (a for a in card['actions'] if a.get('data', {}).get('space_id') == sample_spaces[0].id),
            None
        )
        assert default_action is not None
        assert '⭐' in default_action['title']

    def test_default_space_is_first(self, app, session, sample_spaces):
        """Default space should be listed first for convenience."""
        card = build_space_selector_card(sample_spaces)

        # First action should be the default space
        first_action = card['actions'][0]
        assert first_action['data']['space_id'] == sample_spaces[0].id
        assert '⭐' in first_action['title']

    def test_limits_to_8_spaces(self, app, session, sample_tenant, sample_user):
        """Should limit to 8 spaces to avoid card overflow."""
        # Create 10 spaces
        spaces = []
        for i in range(10):
            space = Space(
                tenant_id=sample_tenant.id,
                name=f'Space {i}',
                is_default=(i == 0),
                visibility_policy=VisibilityPolicy.TENANT_VISIBLE,
                created_by_id=sample_user.id
            )
            session.add(space)
            spaces.append(space)
        session.commit()

        card = build_space_selector_card(spaces)

        # Should have 8 space buttons max
        assert len(card['actions']) == 8

    def test_empty_spaces_list(self, app, session):
        """Should handle empty spaces list (no actions)."""
        card = build_space_selector_card([])

        # No spaces = no actions
        assert len(card['actions']) == 0


class TestBuildDecisionListCardWithSpace:
    """Tests for build_decision_list_card with space filtering."""

    def test_shows_space_filter_context(self, app, session, sample_decisions):
        """Card should show which space is being filtered."""
        card = build_decision_list_card(
            sample_decisions,
            title="Decisions",
            space_name="Engineering"
        )

        # Should contain space filter text in body
        body_texts = [b.get('text', '') for b in card['body']]
        assert any('Engineering' in t for t in body_texts)
        assert any('Filtered by space' in t for t in body_texts)

    def test_no_filter_context_when_no_space(self, app, session, sample_decisions):
        """Card should not show filter context when no space specified."""
        card = build_decision_list_card(
            sample_decisions,
            title="All Decisions",
            space_name=None
        )

        # Should not contain "Filtered by space"
        body_texts = [b.get('text', '') for b in card['body']]
        assert not any('Filtered by space' in t for t in body_texts)

    def test_has_change_space_button(self, app, session, sample_decisions):
        """Card should have a 'Change Space' button."""
        card = build_decision_list_card(sample_decisions)

        # Find the change space action
        change_space_action = next(
            (a for a in card['actions'] if a.get('data', {}).get('action') == 'select_space'),
            None
        )
        assert change_space_action is not None
        assert 'Change Space' in change_space_action['title']


class TestBuildCreateDecisionFormCard:
    """Tests for build_create_decision_form_card with space and Teams People Picker owner selection."""

    def test_basic_form_has_required_fields(self, app, session):
        """Create form should have title, context, decision, consequences, status fields."""
        card = build_create_decision_form_card()

        assert card['type'] == 'AdaptiveCard'
        assert 'body' in card

        # Extract input IDs
        input_ids = [item.get('id') for item in card['body'] if item.get('type', '').startswith('Input')]
        assert 'title' in input_ids
        assert 'context' in input_ids
        assert 'decision' in input_ids
        assert 'consequences' in input_ids
        assert 'status' in input_ids

    def test_form_with_space_selection(self, app, session, sample_spaces):
        """Create form should include space selector when spaces provided."""
        card = build_create_decision_form_card(spaces=sample_spaces)

        # Extract input IDs
        input_ids = [item.get('id') for item in card['body'] if item.get('type', '').startswith('Input')]
        assert 'space_id' in input_ids

        # Find the space selector
        space_selector = next(
            (item for item in card['body'] if item.get('id') == 'space_id'),
            None
        )
        assert space_selector is not None
        assert space_selector['type'] == 'Input.ChoiceSet'

        # Should have choices for all spaces
        choices = space_selector['choices']
        assert len(choices) == 3
        choice_titles = [c['title'] for c in choices]
        assert any('Default' in t for t in choice_titles)
        assert any('Engineering' in t for t in choice_titles)
        assert any('Platform' in t for t in choice_titles)

    def test_default_space_preselected(self, app, session, sample_spaces):
        """Default space should be pre-selected in space dropdown."""
        card = build_create_decision_form_card(spaces=sample_spaces)

        # Find the space selector
        space_selector = next(
            (item for item in card['body'] if item.get('id') == 'space_id'),
            None
        )
        assert space_selector is not None

        # The value should be the default space's ID
        default_space = next(s for s in sample_spaces if s.is_default)
        assert space_selector['value'] == str(default_space.id)

    def test_form_has_teams_people_picker(self, app, session):
        """Create form should have Teams People Picker for owner selection."""
        card = build_create_decision_form_card()

        # Extract input IDs
        input_ids = [item.get('id') for item in card['body'] if item.get('type', '').startswith('Input')]
        assert 'owner_entra_id' in input_ids

        # Find the owner People Picker
        owner_picker = next(
            (item for item in card['body'] if item.get('id') == 'owner_entra_id'),
            None
        )
        assert owner_picker is not None
        assert owner_picker['type'] == 'Input.ChoiceSet'

        # Should have Data.Query for dynamic user search
        assert 'choices.data' in owner_picker
        assert owner_picker['choices.data']['type'] == 'Data.Query'
        assert owner_picker['choices.data']['dataset'] == 'graph.microsoft.com/users'

    def test_form_with_both_spaces_and_people_picker(self, app, session, sample_spaces):
        """Create form should include both space selection and People Picker."""
        card = build_create_decision_form_card(spaces=sample_spaces)

        # Extract input IDs
        input_ids = [item.get('id') for item in card['body'] if item.get('type', '').startswith('Input')]
        assert 'space_id' in input_ids
        assert 'owner_entra_id' in input_ids

    def test_form_has_submit_action(self, app, session):
        """Create form should have submit action with correct action type."""
        card = build_create_decision_form_card()

        assert 'actions' in card
        assert len(card['actions']) == 1

        submit_action = card['actions'][0]
        assert submit_action['type'] == 'Action.Submit'
        assert submit_action['data']['action'] == 'submit_decision'

    def test_form_without_spaces_has_no_space_selector(self, app, session):
        """Create form without spaces should not have space selector."""
        card = build_create_decision_form_card(spaces=None)

        input_ids = [item.get('id') for item in card['body'] if item.get('type', '').startswith('Input')]
        assert 'space_id' not in input_ids

    def test_people_picker_always_present(self, app, session):
        """Create form should always have People Picker (no need to pass users)."""
        card = build_create_decision_form_card()

        # People Picker should be present by default
        input_ids = [item.get('id') for item in card['body'] if item.get('type', '').startswith('Input')]
        assert 'owner_entra_id' in input_ids


class TestMenuCardDialogs:
    """Tests for menu card dialog triggers (task/fetch)."""

    def test_create_decision_uses_task_fetch(self, app, session):
        """Create Decision button should trigger task/fetch dialog."""
        card = build_menu_card()

        # Find the Create Decision action
        create_action = next(
            (a for a in card['actions'] if 'Create' in a.get('title', '')),
            None
        )
        assert create_action is not None
        assert create_action['type'] == 'Action.Submit'

        # Should have msteams task/fetch trigger
        assert 'msteams' in create_action['data']
        assert create_action['data']['msteams']['type'] == 'task/fetch'
        assert create_action['data']['action'] == 'show_create_form'


class TestGreetingCardDialogs:
    """Tests for greeting card dialog triggers."""

    def test_create_decision_uses_task_fetch(self, app, session):
        """Create Decision button in greeting should trigger task/fetch dialog."""
        card = build_greeting_card(user_name='Test User')

        # Find the Create Decision action
        create_action = next(
            (a for a in card['actions'] if 'Create' in a.get('title', '')),
            None
        )
        assert create_action is not None
        assert create_action['type'] == 'Action.Submit'

        # Should have msteams task/fetch trigger
        assert 'msteams' in create_action['data']
        assert create_action['data']['msteams']['type'] == 'task/fetch'
        assert create_action['data']['action'] == 'show_create_form'


class TestDecisionDetailCard:
    """Tests for decision detail card."""

    def test_no_change_status_button(self, app, session, sample_tenant, sample_user):
        """Decision detail card should NOT have Change Status button (use Decisions Tab instead)."""
        # Create a decision
        decision = ArchitectureDecision(
            title='Test Decision',
            context='Test context',
            decision='Test decision text',
            status='proposed',
            consequences='Test consequences',
            domain=sample_tenant.domain,
            tenant_id=sample_tenant.id,
            created_by_id=sample_user.id,
            decision_number=1
        )
        decision.tenant = sample_tenant
        session.add(decision)
        session.commit()

        card = build_decision_detail_card(decision)

        # Should NOT have any action with 'Change Status' or 'open_status_modal'
        for action in card.get('actions', []):
            assert 'Status' not in action.get('title', '')
            assert action.get('data', {}).get('action') != 'open_status_modal'

    def test_has_view_full_decision_link(self, app, session, sample_tenant, sample_user):
        """Decision detail card should have View Full Decision link."""
        decision = ArchitectureDecision(
            title='Test Decision',
            context='Test context',
            decision='Test decision text',
            status='proposed',
            consequences='Test consequences',
            domain=sample_tenant.domain,
            tenant_id=sample_tenant.id,
            created_by_id=sample_user.id,
            decision_number=1
        )
        decision.tenant = sample_tenant
        session.add(decision)
        session.commit()

        card = build_decision_detail_card(decision)

        # Should have View Full Decision action
        view_action = next(
            (a for a in card.get('actions', []) if 'View' in a.get('title', '')),
            None
        )
        assert view_action is not None
        assert view_action['type'] == 'Action.OpenUrl'
        assert 'url' in view_action


class TestCreatePromptCard:
    """Tests for build_create_prompt_card function."""

    def test_prompt_card_has_dialog_button(self, app, session):
        """Create prompt card should have a button that triggers task/fetch dialog."""
        card = build_create_prompt_card()

        assert card['type'] == 'AdaptiveCard'
        assert 'actions' in card
        assert len(card['actions']) == 1

        # Button should trigger task/fetch dialog
        action = card['actions'][0]
        assert action['type'] == 'Action.Submit'
        assert 'msteams' in action['data']
        assert action['data']['msteams']['type'] == 'task/fetch'
        assert action['data']['action'] == 'show_create_form'

    def test_prompt_card_has_instructional_text(self, app, session):
        """Create prompt card should have instructional text."""
        card = build_create_prompt_card()

        # Should have body with text
        assert 'body' in card
        body_texts = [b.get('text', '') for b in card['body'] if b.get('type') == 'TextBlock']
        assert any('Create' in t for t in body_texts)
        assert any('button' in t.lower() or 'click' in t.lower() for t in body_texts)
