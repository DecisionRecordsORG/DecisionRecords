"""
Tests for v1.5 Governance Models.

Tests the new tenant/membership/space models and their relationships.
"""
import pytest
from datetime import datetime, timedelta, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, TenantSettings, Space, DecisionSpace,
    AuditLog, ArchitectureDecision, MaturityState, GlobalRole, VisibilityPolicy
)


class TestEnums:
    """Test enum values and definitions."""

    def test_maturity_state_values(self):
        """Verify MaturityState enum has expected values."""
        assert MaturityState.BOOTSTRAP.value == 'bootstrap'
        assert MaturityState.MATURE.value == 'mature'
        # Should only have 2 states
        assert len(MaturityState) == 2

    def test_global_role_values(self):
        """Verify GlobalRole enum has expected values."""
        assert GlobalRole.USER.value == 'user'
        assert GlobalRole.PROVISIONAL_ADMIN.value == 'provisional_admin'
        assert GlobalRole.STEWARD.value == 'steward'
        assert GlobalRole.ADMIN.value == 'admin'
        assert len(GlobalRole) == 4

    def test_visibility_policy_values(self):
        """Verify VisibilityPolicy enum has expected values."""
        assert VisibilityPolicy.TENANT_VISIBLE.value == 'tenant_visible'
        assert VisibilityPolicy.SPACE_FOCUSED.value == 'space_focused'
        assert len(VisibilityPolicy) == 2


class TestTenant:
    """Test Tenant model functionality."""

    def test_tenant_creation(self, session, sample_tenant):
        """Test basic tenant creation."""
        assert sample_tenant.id is not None
        assert sample_tenant.domain == 'example.com'
        assert sample_tenant.name == 'Example Corp'
        assert sample_tenant.status == 'active'
        assert sample_tenant.maturity_state == MaturityState.BOOTSTRAP

    def test_tenant_defaults(self, session):
        """Test tenant default values."""
        tenant = Tenant(domain='test.com')
        session.add(tenant)
        session.commit()

        assert tenant.status == 'active'
        assert tenant.maturity_state == MaturityState.BOOTSTRAP
        assert tenant.maturity_age_days == 14
        assert tenant.maturity_user_threshold == 5

    def test_tenant_domain_unique(self, session, sample_tenant):
        """Test that tenant domain is unique."""
        duplicate = Tenant(domain='example.com', name='Duplicate')
        session.add(duplicate)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()

    def test_tenant_to_dict(self, session, sample_tenant):
        """Test tenant serialization."""
        data = sample_tenant.to_dict()
        assert data['id'] == sample_tenant.id
        assert data['domain'] == 'example.com'
        assert data['name'] == 'Example Corp'
        assert data['status'] == 'active'
        assert data['maturity_state'] == 'bootstrap'
        assert 'created_at' in data

    def test_tenant_is_mature_when_bootstrap(self, session, sample_tenant):
        """Test is_mature returns False for bootstrap tenants."""
        assert sample_tenant.is_mature() is False

    def test_tenant_is_mature_when_mature(self, session):
        """Test is_mature returns True for mature tenants."""
        tenant = Tenant(
            domain='mature.com',
            maturity_state=MaturityState.MATURE
        )
        session.add(tenant)
        session.commit()
        assert tenant.is_mature() is True


class TestTenantMaturity:
    """Test tenant maturity computation logic."""

    def test_maturity_with_two_admins(self, session, sample_tenant):
        """Tenant should be MATURE with 2+ admins."""
        # Create two admin users
        for i in range(2):
            user = User(
                email=f'admin{i}@example.com',
                name=f'Admin {i}',
                sso_domain='example.com',
                auth_type='local'
            )
            session.add(user)
            session.flush()
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=sample_tenant.id,
                global_role=GlobalRole.ADMIN
            )
            session.add(membership)
        session.commit()

        assert sample_tenant.get_admin_count() == 2
        computed = sample_tenant.compute_maturity_state()
        assert computed == MaturityState.MATURE

    def test_maturity_with_admin_plus_steward(self, session, sample_tenant):
        """Tenant should be MATURE with 1 admin + 1 steward."""
        # Create admin
        admin = User(
            email='admin@example.com',
            name='Admin',
            sso_domain='example.com',
            auth_type='local'
        )
        session.add(admin)
        session.flush()
        admin_mem = TenantMembership(
            user_id=admin.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.ADMIN
        )
        session.add(admin_mem)

        # Create steward
        steward = User(
            email='steward@example.com',
            name='Steward',
            sso_domain='example.com',
            auth_type='local'
        )
        session.add(steward)
        session.flush()
        steward_mem = TenantMembership(
            user_id=steward.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.STEWARD
        )
        session.add(steward_mem)
        session.commit()

        assert sample_tenant.get_admin_count() == 1
        assert sample_tenant.get_steward_count() == 1
        computed = sample_tenant.compute_maturity_state()
        assert computed == MaturityState.MATURE

    def test_maturity_by_user_count(self, session, sample_tenant):
        """Tenant should be MATURE when user count >= threshold."""
        sample_tenant.maturity_user_threshold = 3

        # Create 3 users
        for i in range(3):
            user = User(
                email=f'user{i}@example.com',
                name=f'User {i}',
                sso_domain='example.com',
                auth_type='local'
            )
            session.add(user)
            session.flush()
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=sample_tenant.id,
                global_role=GlobalRole.USER
            )
            session.add(membership)
        session.commit()

        assert sample_tenant.get_member_count() == 3
        computed = sample_tenant.compute_maturity_state()
        assert computed == MaturityState.MATURE

    def test_maturity_by_age(self, session):
        """Tenant should be MATURE when age >= threshold days."""
        tenant = Tenant(
            domain='old.com',
            maturity_age_days=14,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=15)  # 15 days old
        )
        session.add(tenant)
        session.commit()

        computed = tenant.compute_maturity_state()
        assert computed == MaturityState.MATURE

    def test_maturity_bootstrap_when_young_and_few_users(self, session, sample_tenant):
        """Tenant should stay BOOTSTRAP when young with few users/admins."""
        # Single regular user
        user = User(
            email='lone@example.com',
            name='Lone User',
            sso_domain='example.com',
            auth_type='local'
        )
        session.add(user)
        session.flush()
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.USER
        )
        session.add(membership)
        session.commit()

        computed = sample_tenant.compute_maturity_state()
        assert computed == MaturityState.BOOTSTRAP

    def test_update_maturity_changes_state(self, session, sample_tenant):
        """Test update_maturity() changes and returns True when state changes."""
        # Make tenant mature by age
        sample_tenant.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
        sample_tenant.maturity_age_days = 14
        session.commit()

        result = sample_tenant.update_maturity()
        assert result is True
        assert sample_tenant.maturity_state == MaturityState.MATURE

    def test_update_maturity_returns_false_when_no_change(self, session, sample_tenant):
        """Test update_maturity() returns False when state doesn't change."""
        result = sample_tenant.update_maturity()
        assert result is False
        assert sample_tenant.maturity_state == MaturityState.BOOTSTRAP


class TestTenantMembership:
    """Test TenantMembership model functionality."""

    def test_membership_creation(self, session, sample_membership):
        """Test basic membership creation."""
        assert sample_membership.id is not None
        assert sample_membership.global_role == GlobalRole.USER

    def test_membership_unique_constraint(self, session, sample_user, sample_tenant, sample_membership):
        """Test that user can only have one membership per tenant."""
        duplicate = TenantMembership(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.ADMIN
        )
        session.add(duplicate)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()

    def test_membership_is_admin_for_user(self, session, sample_membership):
        """Regular user should not have admin privileges."""
        assert sample_membership.is_admin is False
        assert sample_membership.is_full_admin is False

    def test_membership_is_admin_for_provisional(self, session, sample_user, sample_tenant):
        """Provisional admin should have is_admin=True but is_full_admin=False."""
        membership = TenantMembership(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)
        session.commit()

        assert membership.is_admin is True
        assert membership.is_full_admin is False

    def test_membership_is_admin_for_steward(self, session, steward_user, sample_tenant):
        """Steward should have is_admin=True but is_full_admin=False."""
        membership = steward_user.memberships.first()
        assert membership.is_admin is True
        assert membership.is_full_admin is False

    def test_membership_is_admin_for_admin(self, session, admin_user, sample_tenant):
        """Admin should have is_admin=True and is_full_admin=True."""
        membership = admin_user.memberships.first()
        assert membership.is_admin is True
        assert membership.is_full_admin is True

    def test_membership_can_approve_requests(self, session, sample_user, sample_tenant):
        """Test can_approve_requests for different roles."""
        # Regular user cannot
        membership = TenantMembership(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.USER
        )
        assert membership.can_approve_requests is False

        # Provisional admin can
        membership.global_role = GlobalRole.PROVISIONAL_ADMIN
        assert membership.can_approve_requests is True

        # Steward can
        membership.global_role = GlobalRole.STEWARD
        assert membership.can_approve_requests is True

        # Admin can
        membership.global_role = GlobalRole.ADMIN
        assert membership.can_approve_requests is True

    def test_membership_can_change_tenant_settings(self, session, sample_user, sample_tenant):
        """Only full admin can change tenant settings."""
        membership = TenantMembership(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.USER
        )
        assert membership.can_change_tenant_settings is False

        membership.global_role = GlobalRole.PROVISIONAL_ADMIN
        assert membership.can_change_tenant_settings is False

        membership.global_role = GlobalRole.STEWARD
        assert membership.can_change_tenant_settings is False

        membership.global_role = GlobalRole.ADMIN
        assert membership.can_change_tenant_settings is True

    def test_membership_to_dict(self, session, sample_membership):
        """Test membership serialization."""
        data = sample_membership.to_dict()
        assert data['global_role'] == 'user'
        assert data['is_admin'] is False
        assert data['is_full_admin'] is False


class TestTenantSettings:
    """Test TenantSettings model functionality."""

    def test_settings_creation(self, session, sample_tenant_with_settings):
        """Test basic settings creation."""
        settings = sample_tenant_with_settings.settings
        assert settings is not None
        assert settings.tenant_prefix == 'EXM'
        assert settings.allow_registration is True
        assert settings.require_approval is False

    def test_settings_defaults(self, session, sample_tenant):
        """Test settings default values."""
        settings = TenantSettings(tenant_id=sample_tenant.id)
        session.add(settings)
        session.commit()

        assert settings.auth_method == 'local'
        assert settings.allow_password is True
        assert settings.allow_passkey is True
        assert settings.allow_registration is True
        assert settings.require_approval is False
        assert settings.rp_name == 'Architecture Decisions'

    def test_settings_one_to_one(self, session, sample_tenant_with_settings):
        """Test that tenant can only have one settings record."""
        duplicate = TenantSettings(tenant_id=sample_tenant_with_settings.id)
        session.add(duplicate)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()

    def test_settings_to_dict(self, session, sample_tenant_with_settings):
        """Test settings serialization."""
        data = sample_tenant_with_settings.settings.to_dict()
        assert data['tenant_prefix'] == 'EXM'
        assert data['allow_registration'] is True
        assert data['require_approval'] is False


class TestSpace:
    """Test Space model functionality."""

    def test_space_creation(self, session, sample_space):
        """Test basic space creation."""
        assert sample_space.id is not None
        assert sample_space.name == 'Default Space'
        assert sample_space.is_default is True
        assert sample_space.visibility_policy == VisibilityPolicy.TENANT_VISIBLE

    def test_space_defaults(self, session, sample_tenant, sample_user):
        """Test space default values."""
        space = Space(
            tenant_id=sample_tenant.id,
            name='Test Space',
            created_by_id=sample_user.id
        )
        session.add(space)
        session.commit()

        assert space.is_default is False
        assert space.visibility_policy == VisibilityPolicy.TENANT_VISIBLE

    def test_space_to_dict(self, session, sample_space):
        """Test space serialization."""
        data = sample_space.to_dict()
        assert data['name'] == 'Default Space'
        assert data['is_default'] is True
        assert data['visibility_policy'] == 'tenant_visible'


class TestDecisionSpace:
    """Test DecisionSpace (decision-to-space linking) functionality."""

    def test_link_decision_to_space(self, session, sample_tenant, sample_user, sample_space):
        """Test linking a decision to a space."""
        # Create decision
        decision = ArchitectureDecision(
            title='Test Decision',
            context='Test context',
            decision='Test decision',
            consequences='Test consequences',
            domain='example.com',
            tenant_id=sample_tenant.id,
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
        """Test that a decision can belong to multiple spaces."""
        # Create decision
        decision = ArchitectureDecision(
            title='Multi-Space Decision',
            context='Test context',
            decision='Test decision',
            consequences='Test consequences',
            domain='example.com',
            tenant_id=sample_tenant.id,
            created_by_id=sample_user.id
        )
        session.add(decision)
        session.flush()

        # Create second space
        space2 = Space(
            tenant_id=sample_tenant.id,
            name='Second Space',
            created_by_id=sample_user.id
        )
        session.add(space2)
        session.flush()

        # Link to both spaces
        link1 = DecisionSpace(decision_id=decision.id, space_id=sample_space.id)
        link2 = DecisionSpace(decision_id=decision.id, space_id=space2.id)
        session.add_all([link1, link2])
        session.commit()

        assert decision.space_links.count() == 2
        assert len(decision.spaces) == 2

    def test_unique_decision_space_link(self, session, sample_tenant, sample_user, sample_space):
        """Test that same decision-space link can't be created twice."""
        decision = ArchitectureDecision(
            title='Test Decision',
            context='Test context',
            decision='Test decision',
            consequences='Test consequences',
            domain='example.com',
            tenant_id=sample_tenant.id,
            created_by_id=sample_user.id
        )
        session.add(decision)
        session.flush()

        link1 = DecisionSpace(decision_id=decision.id, space_id=sample_space.id)
        session.add(link1)
        session.commit()

        link2 = DecisionSpace(decision_id=decision.id, space_id=sample_space.id)
        session.add(link2)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()


class TestAuditLog:
    """Test AuditLog model functionality."""

    def test_audit_log_creation(self, session, sample_tenant, admin_user):
        """Test creating an audit log entry."""
        log = AuditLog(
            tenant_id=sample_tenant.id,
            actor_user_id=admin_user.id,
            action_type=AuditLog.ACTION_CHANGE_SETTING,
            target_entity='tenant_settings',
            target_id=sample_tenant.id,
            details={'setting': 'require_approval', 'old_value': False, 'new_value': True}
        )
        session.add(log)
        session.commit()

        assert log.id is not None
        assert log.action_type == 'change_setting'
        assert log.details['setting'] == 'require_approval'

    def test_audit_log_action_constants(self):
        """Verify all action type constants are defined."""
        assert AuditLog.ACTION_PROMOTE_USER == 'promote_user'
        assert AuditLog.ACTION_DEMOTE_USER == 'demote_user'
        assert AuditLog.ACTION_CHANGE_SETTING == 'change_setting'
        assert AuditLog.ACTION_APPROVE_REQUEST == 'approve_request'
        assert AuditLog.ACTION_REJECT_REQUEST == 'reject_request'
        assert AuditLog.ACTION_CREATE_SPACE == 'create_space'
        assert AuditLog.ACTION_DELETE_SPACE == 'delete_space'
        assert AuditLog.ACTION_MATURITY_CHANGE == 'maturity_change'
        assert AuditLog.ACTION_USER_JOINED == 'user_joined'
        assert AuditLog.ACTION_USER_LEFT == 'user_left'

    def test_audit_log_to_dict(self, session, sample_tenant, admin_user):
        """Test audit log serialization."""
        log = AuditLog(
            tenant_id=sample_tenant.id,
            actor_user_id=admin_user.id,
            action_type=AuditLog.ACTION_PROMOTE_USER,
            target_entity='user',
            target_id=123,
            details={'new_role': 'steward'}
        )
        session.add(log)
        session.commit()

        data = log.to_dict()
        assert data['action_type'] == 'promote_user'
        assert data['target_entity'] == 'user'
        assert data['details']['new_role'] == 'steward'


class TestUserMembershipHelpers:
    """Test User model membership helper methods."""

    def test_get_membership(self, session, sample_user, sample_tenant, sample_membership):
        """Test User.get_membership() returns correct membership."""
        membership = sample_user.get_membership(sample_tenant.id)
        assert membership is not None
        assert membership.id == sample_membership.id

    def test_get_membership_by_domain(self, session, sample_user, sample_tenant, sample_membership):
        """Test User.get_membership() works without tenant_id (uses domain)."""
        membership = sample_user.get_membership()
        assert membership is not None
        assert membership.id == sample_membership.id

    def test_get_membership_returns_none_for_non_member(self, session, sample_tenant):
        """Test get_membership returns None for non-member."""
        other_user = User(
            email='other@different.com',
            name='Other User',
            sso_domain='different.com',
            auth_type='local'
        )
        session.add(other_user)
        session.commit()

        membership = other_user.get_membership(sample_tenant.id)
        assert membership is None

    def test_get_role(self, session, admin_user, sample_tenant):
        """Test User.get_role() returns correct role."""
        role = admin_user.get_role(sample_tenant.id)
        assert role == GlobalRole.ADMIN

    def test_is_admin_of(self, session, admin_user, sample_user, sample_tenant, sample_membership):
        """Test User.is_admin_of()."""
        assert admin_user.is_admin_of(sample_tenant.id) is True
        assert sample_user.is_admin_of(sample_tenant.id) is False

    def test_is_full_admin_of(self, session, admin_user, steward_user, sample_tenant):
        """Test User.is_full_admin_of()."""
        assert admin_user.is_full_admin_of(sample_tenant.id) is True
        assert steward_user.is_full_admin_of(sample_tenant.id) is False


class TestArchitectureDecisionTenant:
    """Test ArchitectureDecision tenant-related functionality."""

    def test_decision_with_tenant(self, session, sample_tenant, sample_user):
        """Test creating decision with tenant_id."""
        decision = ArchitectureDecision(
            title='Test Decision',
            context='Test context',
            decision='Test decision',
            consequences='Test consequences',
            domain='example.com',
            tenant_id=sample_tenant.id,
            created_by_id=sample_user.id
        )
        session.add(decision)
        session.commit()

        assert decision.tenant_id == sample_tenant.id
        assert decision.tenant == sample_tenant

    def test_decision_to_dict_includes_tenant_id(self, session, sample_tenant, sample_user):
        """Test that to_dict includes tenant_id."""
        decision = ArchitectureDecision(
            title='Test Decision',
            context='Test context',
            decision='Test decision',
            consequences='Test consequences',
            domain='example.com',
            tenant_id=sample_tenant.id,
            created_by_id=sample_user.id
        )
        session.add(decision)
        session.commit()

        data = decision.to_dict()
        assert 'tenant_id' in data
        assert data['tenant_id'] == sample_tenant.id

    def test_decision_to_dict_with_spaces(self, session, sample_tenant, sample_user, sample_space):
        """Test that to_dict can include spaces."""
        decision = ArchitectureDecision(
            title='Test Decision',
            context='Test context',
            decision='Test decision',
            consequences='Test consequences',
            domain='example.com',
            tenant_id=sample_tenant.id,
            created_by_id=sample_user.id
        )
        session.add(decision)
        session.flush()

        link = DecisionSpace(decision_id=decision.id, space_id=sample_space.id)
        session.add(link)
        session.commit()

        data = decision.to_dict(include_spaces=True)
        assert 'spaces' in data
        assert len(data['spaces']) == 1
        assert data['spaces'][0]['name'] == 'Default Space'

    def test_decision_tenant_backref(self, session, sample_tenant, sample_user):
        """Test that tenant.decisions relationship works."""
        for i in range(3):
            decision = ArchitectureDecision(
                title=f'Decision {i}',
                context='Test context',
                decision='Test decision',
                consequences='Test consequences',
                domain='example.com',
                tenant_id=sample_tenant.id,
                created_by_id=sample_user.id
            )
            session.add(decision)
        session.commit()

        assert sample_tenant.decisions.count() == 3
