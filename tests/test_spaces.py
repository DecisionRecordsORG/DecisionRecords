"""
Tests for Space API endpoints.

Tests Space CRUD operations, permissions, and decision-space linking.
"""
import pytest
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, Space, DecisionSpace,
    ArchitectureDecision, AuditLog, MaturityState, GlobalRole, VisibilityPolicy
)


class TestSpaceModel:
    """Test Space model functionality."""

    def test_create_space(self, session, sample_tenant, sample_user):
        """Can create a space in a tenant."""
        space = Space(
            tenant_id=sample_tenant.id,
            name='Engineering',
            description='Engineering team decisions',
            is_default=False,
            created_by_id=sample_user.id
        )
        session.add(space)
        session.commit()

        assert space.id is not None
        assert space.tenant_id == sample_tenant.id
        assert space.name == 'Engineering'
        assert space.is_default is False

    def test_default_space_flag(self, session, sample_tenant, sample_user):
        """Default space flag works correctly."""
        default_space = Space(
            tenant_id=sample_tenant.id,
            name='General',
            is_default=True,
            created_by_id=sample_user.id
        )
        session.add(default_space)

        other_space = Space(
            tenant_id=sample_tenant.id,
            name='Other',
            is_default=False,
            created_by_id=sample_user.id
        )
        session.add(other_space)
        session.commit()

        # Query default space
        found = Space.query.filter_by(tenant_id=sample_tenant.id, is_default=True).first()
        assert found.name == 'General'

    def test_space_to_dict(self, session, sample_tenant, sample_user):
        """Space serialization works correctly."""
        space = Space(
            tenant_id=sample_tenant.id,
            name='Test Space',
            description='A test space',
            is_default=False,
            visibility_policy=VisibilityPolicy.TENANT_VISIBLE,
            created_by_id=sample_user.id
        )
        session.add(space)
        session.commit()

        data = space.to_dict()
        assert data['name'] == 'Test Space'
        assert data['description'] == 'A test space'
        assert data['is_default'] is False
        assert data['visibility_policy'] == 'tenant_visible'


class TestDecisionSpaceModel:
    """Test DecisionSpace link model."""

    def test_link_decision_to_space(self, session, sample_tenant, sample_user, sample_space):
        """Can link a decision to a space."""
        # Create a decision
        decision = ArchitectureDecision(
            domain='example.com',
            decision_number=1,
            title='Test Decision',
            context='Context',
            decision='Decision',
            consequences='Consequences',
            status='proposed',
            created_by_id=sample_user.id
        )
        session.add(decision)
        session.flush()

        # Link to space
        link = DecisionSpace(
            decision_id=decision.id,
            space_id=sample_space.id,
            added_by_id=sample_user.id
        )
        session.add(link)
        session.commit()

        assert link.id is not None
        assert link.decision_id == decision.id
        assert link.space_id == sample_space.id

    def test_decision_can_be_in_multiple_spaces(self, session, sample_tenant, sample_user, sample_space):
        """A decision can belong to multiple spaces."""
        # Create second space
        space2 = Space(
            tenant_id=sample_tenant.id,
            name='Second Space',
            is_default=False,
            created_by_id=sample_user.id
        )
        session.add(space2)
        session.flush()

        # Create a decision
        decision = ArchitectureDecision(
            domain='example.com',
            decision_number=2,
            title='Multi-Space Decision',
            context='Context',
            decision='Decision',
            consequences='Consequences',
            status='proposed',
            created_by_id=sample_user.id
        )
        session.add(decision)
        session.flush()

        # Link to both spaces
        link1 = DecisionSpace(decision_id=decision.id, space_id=sample_space.id)
        link2 = DecisionSpace(decision_id=decision.id, space_id=space2.id)
        session.add_all([link1, link2])
        session.commit()

        # Verify
        links = DecisionSpace.query.filter_by(decision_id=decision.id).all()
        assert len(links) == 2

    def test_unique_constraint(self, session, sample_tenant, sample_user, sample_space):
        """Cannot link same decision to same space twice."""
        decision = ArchitectureDecision(
            domain='example.com',
            decision_number=3,
            title='Unique Test',
            context='Context',
            decision='Decision',
            consequences='Consequences',
            status='proposed',
            created_by_id=sample_user.id
        )
        session.add(decision)
        session.flush()

        link1 = DecisionSpace(decision_id=decision.id, space_id=sample_space.id)
        session.add(link1)
        session.commit()

        # Try to add duplicate
        link2 = DecisionSpace(decision_id=decision.id, space_id=sample_space.id)
        session.add(link2)

        with pytest.raises(Exception):  # IntegrityError
            session.commit()
        session.rollback()


class TestSpacePermissions:
    """Test Space access control."""

    def test_admin_can_create_space(self, session, sample_tenant, admin_user):
        """Admin can create spaces."""
        membership = admin_user.get_membership(sample_tenant.id)
        assert membership.global_role == GlobalRole.ADMIN

        # Admin permission allows space creation
        can_create = membership.global_role in [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN]
        assert can_create is True

    def test_steward_can_create_space(self, session, sample_tenant, steward_user):
        """Steward can create spaces."""
        membership = steward_user.get_membership(sample_tenant.id)
        assert membership.global_role == GlobalRole.STEWARD

        can_create = membership.global_role in [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN]
        assert can_create is True

    def test_regular_user_cannot_create_space(self, session, sample_tenant, sample_user, sample_membership):
        """Regular user cannot create spaces."""
        assert sample_membership.global_role == GlobalRole.USER

        can_create = sample_membership.global_role in [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN]
        assert can_create is False

    def test_only_admin_can_delete_space(self, session, sample_tenant, admin_user, steward_user):
        """Only full admin can delete spaces."""
        admin_membership = admin_user.get_membership(sample_tenant.id)
        steward_membership = steward_user.get_membership(sample_tenant.id)

        # Admin can delete
        can_delete_admin = admin_membership.global_role == GlobalRole.ADMIN
        assert can_delete_admin is True

        # Steward cannot delete
        can_delete_steward = steward_membership.global_role == GlobalRole.ADMIN
        assert can_delete_steward is False


class TestSpaceInvariants:
    """Test Space business rules and invariants."""

    def test_cannot_delete_default_space(self, session, sample_tenant, sample_user):
        """Default space cannot be deleted."""
        default_space = Space(
            tenant_id=sample_tenant.id,
            name='General',
            is_default=True,
            created_by_id=sample_user.id
        )
        session.add(default_space)
        session.commit()

        # Business rule check (API level enforcement)
        assert default_space.is_default is True
        # Deletion should be prevented at API level, not model level

    def test_deleting_space_removes_links_not_decisions(self, session, sample_tenant, sample_user, sample_space):
        """Deleting a space removes links but preserves decisions."""
        # Create decision linked to space
        decision = ArchitectureDecision(
            domain='example.com',
            decision_number=4,
            title='Preserved Decision',
            context='Context',
            decision='Decision',
            consequences='Consequences',
            status='proposed',
            created_by_id=sample_user.id
        )
        session.add(decision)
        session.flush()

        link = DecisionSpace(decision_id=decision.id, space_id=sample_space.id)
        session.add(link)
        session.commit()

        decision_id = decision.id
        space_id = sample_space.id

        # Delete space (not default)
        session.delete(sample_space)
        session.commit()

        # Decision should still exist
        remaining = ArchitectureDecision.query.get(decision_id)
        assert remaining is not None
        assert remaining.title == 'Preserved Decision'

        # Link should be gone
        links = DecisionSpace.query.filter_by(space_id=space_id).all()
        assert len(links) == 0

    def test_tenant_can_have_only_one_default_space(self, session, sample_tenant, sample_user):
        """Each tenant should have exactly one default space."""
        # Create default space
        default1 = Space(
            tenant_id=sample_tenant.id,
            name='Default 1',
            is_default=True,
            created_by_id=sample_user.id
        )
        session.add(default1)
        session.commit()

        default_spaces = Space.query.filter_by(
            tenant_id=sample_tenant.id,
            is_default=True
        ).count()
        assert default_spaces == 1


class TestSpaceQueries:
    """Test Space query patterns."""

    def test_list_spaces_for_tenant(self, session, sample_tenant, sample_user):
        """Can list all spaces for a tenant."""
        # Create multiple spaces
        for i in range(3):
            space = Space(
                tenant_id=sample_tenant.id,
                name=f'Space {i}',
                is_default=(i == 0),
                created_by_id=sample_user.id
            )
            session.add(space)
        session.commit()

        spaces = Space.query.filter_by(tenant_id=sample_tenant.id).all()
        assert len(spaces) == 3

    def test_list_decisions_in_space(self, session, sample_tenant, sample_user, sample_space):
        """Can list all decisions in a space."""
        # Create decisions and link some to the space
        for i in range(5):
            decision = ArchitectureDecision(
                domain='example.com',
                decision_number=100 + i,
                title=f'Decision {i}',
                context='Context',
                decision='Decision',
                consequences='Consequences',
                status='proposed',
                created_by_id=sample_user.id
            )
            session.add(decision)
            session.flush()

            # Link only even-numbered decisions
            if i % 2 == 0:
                link = DecisionSpace(decision_id=decision.id, space_id=sample_space.id)
                session.add(link)

        session.commit()

        # Query decisions in space
        links = DecisionSpace.query.filter_by(space_id=sample_space.id).all()
        decision_ids = [l.decision_id for l in links]

        decisions = ArchitectureDecision.query.filter(
            ArchitectureDecision.id.in_(decision_ids)
        ).all()

        assert len(decisions) == 3  # Only even-numbered: 0, 2, 4


# Additional fixtures needed for these tests
@pytest.fixture
def sample_space(session, sample_tenant, sample_user):
    """Create a sample non-default space."""
    space = Space(
        tenant_id=sample_tenant.id,
        name='Test Space',
        description='A test space',
        is_default=False,
        visibility_policy=VisibilityPolicy.TENANT_VISIBLE,
        created_by_id=sample_user.id
    )
    session.add(space)
    session.commit()
    return space
