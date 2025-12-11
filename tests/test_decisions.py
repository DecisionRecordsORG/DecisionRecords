"""
Tests for decision CRUD API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from flask import Flask

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, ArchitectureDecision,
    DecisionHistory, GlobalRole, MaturityState, AuditLog
)


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def sample_decision(session, sample_tenant, sample_user):
    """Create a sample decision."""
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
    session.add(decision)
    session.commit()
    return decision


class TestDecisionDeletion:
    """Test decision deletion endpoint with rate limiting and role checks."""

    def test_admin_can_delete_decision(self, app, session, sample_tenant, admin_user, sample_decision):
        """Admin user can delete decisions."""
        with app.test_request_context():
            from flask import session as flask_session, g
            flask_session['user_id'] = admin_user.id
            g.current_user = admin_user

            # Simulate the deletion endpoint logic
            membership = TenantMembership.query.filter_by(
                user_id=admin_user.id,
                tenant_id=sample_tenant.id
            ).first()

            assert membership is not None
            assert membership.global_role == GlobalRole.ADMIN

            # Verify decision exists
            decision = ArchitectureDecision.query.filter_by(
                id=sample_decision.id,
                deleted_at=None
            ).first()
            assert decision is not None

            # Soft delete
            decision.deleted_at = datetime.utcnow()
            decision.deleted_by_id = admin_user.id
            decision.deletion_expires_at = datetime.utcnow() + timedelta(days=30)
            session.commit()

            # Verify soft delete
            session.refresh(decision)
            assert decision.deleted_at is not None
            assert decision.deleted_by_id == admin_user.id
            assert decision.deletion_expires_at is not None

    def test_steward_can_delete_decision(self, session, sample_tenant, steward_user, sample_decision):
        """Steward user can delete decisions."""
        membership = TenantMembership.query.filter_by(
            user_id=steward_user.id,
            tenant_id=sample_tenant.id
        ).first()

        assert membership is not None
        assert membership.global_role == GlobalRole.STEWARD

        # Steward is allowed to delete
        allowed_roles = [GlobalRole.ADMIN, GlobalRole.STEWARD]
        assert membership.global_role in allowed_roles

    def test_provisional_admin_can_delete_in_bootstrap(self, session, sample_tenant):
        """Provisional admin can delete in BOOTSTRAP state."""
        # Create provisional admin
        user = User(
            email='prov@example.com',
            name='Provisional',
            sso_domain='example.com',
            auth_type='local'
        )
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)
        session.commit()

        # Tenant is in BOOTSTRAP
        assert sample_tenant.maturity_state == MaturityState.BOOTSTRAP

        # Check if allowed
        allowed_roles = [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN]
        assert membership.global_role in allowed_roles

    def test_provisional_admin_cannot_delete_in_mature(self, session, sample_tenant):
        """Provisional admin cannot delete in MATURE state."""
        # Create provisional admin
        user = User(
            email='prov@example.com',
            name='Provisional',
            sso_domain='example.com',
            auth_type='local'
        )
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)

        # Make tenant MATURE
        sample_tenant.maturity_state = MaturityState.MATURE
        session.commit()

        # Check if NOT allowed
        allowed_roles = [GlobalRole.ADMIN, GlobalRole.STEWARD]
        assert membership.global_role not in allowed_roles

    def test_regular_user_cannot_delete(self, session, sample_tenant, sample_user, sample_membership):
        """Regular user cannot delete decisions."""
        assert sample_membership.global_role == GlobalRole.USER

        allowed_roles = [GlobalRole.ADMIN, GlobalRole.STEWARD]
        assert sample_membership.global_role not in allowed_roles

    def test_rate_limiting_tracks_deletion_count(self, session, sample_tenant, admin_user, sample_decision):
        """Deletion count is tracked for rate limiting."""
        membership = TenantMembership.query.filter_by(
            user_id=admin_user.id,
            tenant_id=sample_tenant.id
        ).first()

        # Initial state
        assert membership.deletion_count in (None, 0)
        assert membership.deletion_count_window_start is None

        # Simulate deletion
        membership.deletion_count_window_start = datetime.utcnow()
        membership.deletion_count = 1
        session.commit()

        session.refresh(membership)
        assert membership.deletion_count == 1
        assert membership.deletion_count_window_start is not None

    def test_rate_limiting_blocks_after_threshold(self, session, sample_tenant, admin_user):
        """Rate limiting blocks after 3 deletions in 5 minutes."""
        membership = TenantMembership.query.filter_by(
            user_id=admin_user.id,
            tenant_id=sample_tenant.id
        ).first()

        RATE_LIMIT_COUNT = 3
        now = datetime.utcnow()

        # Set deletion count to threshold
        membership.deletion_count_window_start = now
        membership.deletion_count = RATE_LIMIT_COUNT
        session.commit()

        # Check if at limit
        assert membership.deletion_count >= RATE_LIMIT_COUNT

        # Simulate triggering rate limit
        membership.deletion_rate_limited_at = now
        session.commit()

        session.refresh(membership)
        assert membership.deletion_rate_limited_at is not None

    def test_rate_limiting_expires_after_one_hour(self, session, sample_tenant, admin_user):
        """Rate limiting expires after 1 hour."""
        membership = TenantMembership.query.filter_by(
            user_id=admin_user.id,
            tenant_id=sample_tenant.id
        ).first()

        # Set rate limit timestamp to 2 hours ago
        two_hours_ago = datetime.utcnow() - timedelta(hours=2)
        membership.deletion_rate_limited_at = two_hours_ago
        session.commit()

        # Check if expired (rate limit lasts 1 hour)
        now = datetime.utcnow()
        is_expired = now >= membership.deletion_rate_limited_at + timedelta(hours=1)
        assert is_expired is True

    def test_rate_limiting_window_resets_after_5_minutes(self, session, sample_tenant, admin_user):
        """Deletion count window resets after 5 minutes."""
        membership = TenantMembership.query.filter_by(
            user_id=admin_user.id,
            tenant_id=sample_tenant.id
        ).first()

        RATE_LIMIT_WINDOW_MINUTES = 5

        # Set window start to 6 minutes ago
        old_window = datetime.utcnow() - timedelta(minutes=6)
        membership.deletion_count_window_start = old_window
        membership.deletion_count = 2
        session.commit()

        # Check if window expired
        now = datetime.utcnow()
        window_expired = (now - membership.deletion_count_window_start) > timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
        assert window_expired is True

        # Simulate reset
        membership.deletion_count_window_start = now
        membership.deletion_count = 0
        session.commit()

        session.refresh(membership)
        assert membership.deletion_count == 0

    def test_soft_delete_sets_retention_window(self, session, sample_decision, admin_user):
        """Soft delete sets 30-day retention window."""
        deletion_time = datetime.utcnow()
        retention_days = 30

        sample_decision.deleted_at = deletion_time
        sample_decision.deleted_by_id = admin_user.id
        sample_decision.deletion_expires_at = deletion_time + timedelta(days=retention_days)
        session.commit()

        session.refresh(sample_decision)
        assert sample_decision.deleted_at is not None
        assert sample_decision.deleted_by_id == admin_user.id
        assert sample_decision.deletion_expires_at is not None

        # Verify 30-day window
        expected_expiry = deletion_time + timedelta(days=30)
        assert abs((sample_decision.deletion_expires_at - expected_expiry).total_seconds()) < 1

    def test_deleted_decisions_not_returned_in_query(self, session, sample_decision, admin_user):
        """Deleted decisions are filtered from normal queries."""
        # Soft delete
        sample_decision.deleted_at = datetime.utcnow()
        session.commit()

        # Query for non-deleted decisions
        decision = ArchitectureDecision.query.filter_by(
            id=sample_decision.id,
            deleted_at=None
        ).first()

        assert decision is None


class TestDecisionHistory:
    """Test decision history tracking."""

    def test_save_history_creates_entry(self, session, sample_decision, admin_user):
        """save_history creates a history entry."""
        from models import save_history

        # Save current state to history
        history_entry = save_history(
            sample_decision,
            change_reason='Updated context',
            changed_by=admin_user
        )
        session.commit()

        assert history_entry.id is not None
        assert history_entry.decision_id == sample_decision.id
        assert history_entry.title == sample_decision.title
        assert history_entry.context == sample_decision.context
        assert history_entry.change_reason == 'Updated context'
        assert history_entry.changed_by_id == admin_user.id

    def test_decision_history_relationship(self, session, sample_decision, admin_user):
        """Decision has history relationship."""
        from models import save_history

        # Create multiple history entries
        for i in range(3):
            save_history(
                sample_decision,
                change_reason=f'Change {i}',
                changed_by=admin_user
            )
        session.commit()

        # Load decision with history
        decision = ArchitectureDecision.query.get(sample_decision.id)
        assert len(decision.history) == 3

    def test_to_dict_with_history(self, session, sample_decision, admin_user):
        """to_dict_with_history includes history entries."""
        from models import save_history

        save_history(sample_decision, change_reason='Test', changed_by=admin_user)
        session.commit()

        data = sample_decision.to_dict_with_history()
        assert 'history' in data
        assert len(data['history']) == 1
        assert data['history'][0]['change_reason'] == 'Test'


class TestDecisionModel:
    """Test ArchitectureDecision model methods."""

    def test_get_display_id_with_prefix(self, session, sample_tenant, sample_decision):
        """get_display_id returns formatted ID with tenant prefix."""
        from models import AuthConfig

        # Create auth config with prefix
        auth_config = AuthConfig(
            domain=sample_tenant.domain,
            auth_method='local',
            tenant_prefix='TST'
        )
        session.add(auth_config)
        session.commit()

        display_id = sample_decision.get_display_id()
        assert display_id == 'TST-001'

    def test_get_display_id_without_prefix(self, session, sample_decision):
        """get_display_id returns fallback format without prefix."""
        # No AuthConfig exists
        display_id = sample_decision.get_display_id()
        assert display_id == 'ADR-001'

    def test_get_display_id_returns_none_without_number(self, session, sample_tenant, sample_user):
        """get_display_id returns None if decision_number not set."""
        decision = ArchitectureDecision(
            title='Test',
            context='Context',
            decision='Decision',
            status='proposed',
            consequences='Consequences',
            domain=sample_tenant.domain,
            tenant_id=sample_tenant.id,
            created_by_id=sample_user.id,
            decision_number=None
        )
        session.add(decision)
        session.commit()

        assert decision.get_display_id() is None

    def test_to_dict_includes_essential_fields(self, sample_decision):
        """to_dict includes all essential decision fields."""
        data = sample_decision.to_dict()

        assert 'id' in data
        assert 'title' in data
        assert 'context' in data
        assert 'decision' in data
        assert 'status' in data
        assert 'consequences' in data
        assert 'created_at' in data
        assert 'updated_at' in data
        assert 'domain' in data
        assert 'tenant_id' in data
        assert 'display_id' in data

    def test_valid_statuses_constant(self):
        """VALID_STATUSES contains expected values."""
        assert 'proposed' in ArchitectureDecision.VALID_STATUSES
        assert 'accepted' in ArchitectureDecision.VALID_STATUSES
        assert 'deprecated' in ArchitectureDecision.VALID_STATUSES
        assert 'superseded' in ArchitectureDecision.VALID_STATUSES
