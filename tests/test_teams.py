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
        build_menu_card, build_help_card, build_error_card
    )
    from ee.backend.teams.teams_service import TeamsService
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    build_space_selector_card = None
    build_decision_list_card = None
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
        """Card should contain buttons for each space."""
        card = build_space_selector_card(sample_spaces)

        assert card['type'] == 'AdaptiveCard'
        assert 'actions' in card

        # Should have "All Spaces" + 3 spaces = 4 actions
        assert len(card['actions']) == 4

        # First action should be "All Spaces"
        assert card['actions'][0]['data']['action'] == 'list_by_space'
        assert card['actions'][0]['data']['space_id'] is None

    def test_includes_space_names_in_buttons(self, app, session, sample_spaces):
        """Each space button should have the space name."""
        card = build_space_selector_card(sample_spaces)

        # Check space names appear (skip first "All Spaces" action)
        space_titles = [a['title'] for a in card['actions'][1:]]
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

    def test_without_all_spaces_option(self, app, session, sample_spaces):
        """Can exclude 'All Spaces' option."""
        card = build_space_selector_card(sample_spaces, include_all=False)

        # Should only have 3 space actions
        assert len(card['actions']) == 3

        # No "All Spaces" action
        titles = [a['title'] for a in card['actions']]
        assert not any('All Spaces' in t for t in titles)

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

        # Should have 1 "All Spaces" + 8 space buttons = 9 max
        assert len(card['actions']) == 9

    def test_empty_spaces_list(self, app, session):
        """Should handle empty spaces list."""
        card = build_space_selector_card([])

        # Should still have "All Spaces" option
        assert len(card['actions']) == 1


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
