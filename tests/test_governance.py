"""
Tests for v1.5 Governance Module.

Tests permission guards, role restrictions, and automatic upgrades.
"""
import pytest
from datetime import datetime, timedelta, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, TenantSettings, AuditLog,
    MaturityState, GlobalRole
)
from governance import (
    can_modify_high_impact_setting,
    is_restricted_for_provisional_admin,
    get_provisional_admin_restrictions,
    check_and_upgrade_provisional_admins,
    can_promote_to_role,
    can_demote_user,
    log_admin_action,
    log_setting_change,
    HIGH_IMPACT_SETTINGS
)


class TestHighImpactSettingsGuard:
    """Test high-impact settings permission checks."""

    def test_mature_tenant_can_modify(self, session, sample_user, admin_user, sample_tenant):
        """Mature tenant can modify any high-impact setting."""
        sample_tenant.maturity_state = MaturityState.MATURE
        session.commit()

        admin_membership = admin_user.get_membership(sample_tenant.id)
        allowed, error = can_modify_high_impact_setting(
            sample_tenant, admin_membership,
            'allow_registration', False
        )
        assert allowed is True
        assert error is None

    def test_bootstrap_with_single_admin_cannot_modify(self, session, sample_tenant):
        """Bootstrap tenant with single admin cannot modify high-impact settings."""
        # Create single admin
        user = User(email='single@example.com', name='Single Admin', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.ADMIN
        )
        session.add(membership)
        session.commit()

        allowed, error = can_modify_high_impact_setting(
            sample_tenant, membership,
            'allow_registration', False
        )
        assert allowed is False
        assert error['error'] == 'Cannot modify restrictive settings yet'
        assert 'admin_count' in error['current_state']
        assert error['current_state']['admin_count'] == 1

    def test_two_admins_can_modify(self, session, sample_tenant):
        """Bootstrap tenant with 2+ admins can modify high-impact settings."""
        # Create two admins
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

        admin_membership = TenantMembership.query.filter_by(
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.ADMIN
        ).first()

        allowed, error = can_modify_high_impact_setting(
            sample_tenant, admin_membership,
            'require_approval', True
        )
        assert allowed is True
        assert error is None

    def test_admin_plus_steward_can_modify(self, session, sample_tenant):
        """Bootstrap tenant with 1 admin + 1 steward can modify high-impact settings."""
        # Create admin
        admin = User(email='admin@example.com', name='Admin', sso_domain='example.com', auth_type='local')
        session.add(admin)
        session.flush()
        admin_mem = TenantMembership(user_id=admin.id, tenant_id=sample_tenant.id, global_role=GlobalRole.ADMIN)
        session.add(admin_mem)

        # Create steward
        steward = User(email='steward@example.com', name='Steward', sso_domain='example.com', auth_type='local')
        session.add(steward)
        session.flush()
        steward_mem = TenantMembership(user_id=steward.id, tenant_id=sample_tenant.id, global_role=GlobalRole.STEWARD)
        session.add(steward_mem)
        session.commit()

        allowed, error = can_modify_high_impact_setting(
            sample_tenant, admin_mem,
            'allow_registration', False
        )
        assert allowed is True
        assert error is None

    def test_non_high_impact_setting_always_allowed(self, session, sample_tenant):
        """Non-high-impact settings can always be modified by admin."""
        user = User(email='admin@example.com', name='Admin', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.ADMIN
        )
        session.add(membership)
        session.commit()

        # rp_name is not a high-impact setting
        allowed, error = can_modify_high_impact_setting(
            sample_tenant, membership,
            'rp_name', 'New Name'
        )
        assert allowed is True
        assert error is None

    def test_non_admin_cannot_modify_any_setting(self, session, sample_tenant, sample_user, sample_membership):
        """Non-admin users cannot modify settings even if governance requirements met."""
        # Make tenant mature
        sample_tenant.maturity_state = MaturityState.MATURE
        session.commit()

        allowed, error = can_modify_high_impact_setting(
            sample_tenant, sample_membership,
            'rp_name', 'New Name'
        )
        assert allowed is False
        assert error['error'] == 'Permission denied'


class TestProvisionalAdminRestrictions:
    """Test provisional admin restrictions."""

    def test_provisional_admin_cannot_disable_registration(self, session, sample_tenant):
        """Provisional admin cannot disable registration."""
        user = User(email='prov@example.com', name='Provisional', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)
        session.commit()

        is_restricted, reason = is_restricted_for_provisional_admin(
            'allow_registration', False, membership
        )
        assert is_restricted is True
        assert 'disable' in reason.lower()

    def test_provisional_admin_cannot_enable_approval(self, session, sample_tenant):
        """Provisional admin cannot enable require_approval."""
        user = User(email='prov@example.com', name='Provisional', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)
        session.commit()

        is_restricted, reason = is_restricted_for_provisional_admin(
            'require_approval', True, membership
        )
        assert is_restricted is True
        assert 'approval' in reason.lower()

    def test_provisional_admin_can_enable_registration(self, session, sample_tenant):
        """Provisional admin CAN enable registration (not restrictive)."""
        user = User(email='prov@example.com', name='Provisional', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)
        session.commit()

        is_restricted, reason = is_restricted_for_provisional_admin(
            'allow_registration', True, membership
        )
        assert is_restricted is False

    def test_full_admin_no_restrictions(self, session, sample_tenant, admin_user):
        """Full admin has no restrictions."""
        membership = admin_user.get_membership(sample_tenant.id)

        is_restricted, reason = is_restricted_for_provisional_admin(
            'allow_registration', False, membership
        )
        assert is_restricted is False

    def test_get_restrictions_for_provisional(self, session, sample_tenant):
        """Get list of restrictions for provisional admin."""
        user = User(email='prov@example.com', name='Provisional', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)
        session.commit()

        restrictions = get_provisional_admin_restrictions(membership)
        assert len(restrictions) == 2
        assert any('registration' in r.lower() for r in restrictions)
        assert any('approval' in r.lower() for r in restrictions)


class TestAutomaticRoleUpgrade:
    """Test automatic role upgrade when maturity conditions are met."""

    def test_upgrade_on_maturity(self, session, sample_tenant):
        """Provisional admin upgraded to admin when tenant becomes mature."""
        # Create provisional admin
        user = User(email='prov@example.com', name='Provisional', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)

        # Make tenant mature by age
        sample_tenant.maturity_age_days = 1
        sample_tenant.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
        session.commit()

        upgraded = check_and_upgrade_provisional_admins(sample_tenant, user.id)

        assert user.id in upgraded
        session.refresh(membership)
        assert membership.global_role == GlobalRole.ADMIN

    def test_no_upgrade_when_bootstrap(self, session, sample_tenant):
        """No upgrade happens when tenant is still in bootstrap."""
        # Create provisional admin
        user = User(email='prov@example.com', name='Provisional', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)

        # Keep tenant in bootstrap (young, few users)
        sample_tenant.maturity_age_days = 30
        sample_tenant.maturity_user_threshold = 10
        session.commit()

        upgraded = check_and_upgrade_provisional_admins(sample_tenant, user.id)

        assert len(upgraded) == 0
        session.refresh(membership)
        assert membership.global_role == GlobalRole.PROVISIONAL_ADMIN

    def test_upgrade_creates_audit_log(self, session, sample_tenant):
        """Role upgrade creates audit log entry."""
        user = User(email='prov@example.com', name='Provisional', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)

        # Make tenant mature by setting low age threshold and backdating
        sample_tenant.maturity_age_days = 1
        sample_tenant.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
        session.commit()

        check_and_upgrade_provisional_admins(sample_tenant, user.id)

        # Check audit log
        audit = AuditLog.query.filter_by(
            tenant_id=sample_tenant.id,
            target_id=user.id
        ).first()
        assert audit is not None
        assert audit.action_type == AuditLog.ACTION_PROMOTE_USER
        assert audit.details['old_role'] == 'provisional_admin'
        assert audit.details['new_role'] == 'admin'


class TestRolePromotion:
    """Test role promotion permissions."""

    def test_admin_can_promote_to_admin(self, session, sample_tenant, admin_user):
        """Full admin can promote others to admin."""
        membership = admin_user.get_membership(sample_tenant.id)
        allowed, reason = can_promote_to_role(membership, GlobalRole.ADMIN)
        assert allowed is True

    def test_steward_cannot_promote_to_admin(self, session, sample_tenant, steward_user):
        """Steward cannot promote to admin."""
        membership = steward_user.get_membership(sample_tenant.id)
        allowed, reason = can_promote_to_role(membership, GlobalRole.ADMIN)
        assert allowed is False
        assert 'full administrator' in reason.lower()

    def test_provisional_can_promote_to_steward(self, session, sample_tenant):
        """Provisional admin can promote to steward."""
        user = User(email='prov@example.com', name='Provisional', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)
        session.commit()

        allowed, reason = can_promote_to_role(membership, GlobalRole.STEWARD)
        assert allowed is True

    def test_user_cannot_promote(self, session, sample_tenant, sample_user, sample_membership):
        """Regular user cannot promote anyone."""
        allowed, reason = can_promote_to_role(sample_membership, GlobalRole.STEWARD)
        assert allowed is False


class TestRoleDemotion:
    """Test role demotion permissions."""

    def test_steward_cannot_demote_admin(self, session, sample_tenant, steward_user, admin_user):
        """Steward cannot demote an admin."""
        steward_mem = steward_user.get_membership(sample_tenant.id)
        admin_mem = admin_user.get_membership(sample_tenant.id)

        allowed, reason = can_demote_user(steward_mem, admin_mem, sample_tenant)
        assert allowed is False
        assert 'steward' in reason.lower()

    def test_single_admin_cannot_self_demote(self, session, sample_tenant, admin_user):
        """Single admin cannot demote themselves."""
        admin_mem = admin_user.get_membership(sample_tenant.id)

        allowed, reason = can_demote_user(admin_mem, admin_mem, sample_tenant)
        assert allowed is False
        assert 'no administrator' in reason.lower()

    def test_admin_can_demote_with_multiple_admins(self, session, sample_tenant):
        """Admin can demote when there are multiple admins."""
        # Create two admins
        admins = []
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
            admins.append(membership)
        session.commit()

        # First admin can demote second
        allowed, reason = can_demote_user(admins[0], admins[1], sample_tenant)
        assert allowed is True


class TestAuditLogging:
    """Test audit logging helpers."""

    def test_log_admin_action(self, session, sample_tenant, admin_user):
        """Test creating audit log entry."""
        entry = log_admin_action(
            tenant_id=sample_tenant.id,
            actor_user_id=admin_user.id,
            action_type=AuditLog.ACTION_CREATE_SPACE,
            target_entity='space',
            target_id=1,
            details={'name': 'New Space'}
        )
        session.commit()

        assert entry.id is not None
        assert entry.action_type == AuditLog.ACTION_CREATE_SPACE
        assert entry.details['name'] == 'New Space'

    def test_log_setting_change(self, session, sample_tenant, admin_user):
        """Test logging setting changes."""
        entry = log_setting_change(
            tenant_id=sample_tenant.id,
            actor_user_id=admin_user.id,
            setting_name='allow_registration',
            old_value=True,
            new_value=False
        )
        session.commit()

        assert entry.action_type == AuditLog.ACTION_CHANGE_SETTING
        assert entry.details['setting'] == 'allow_registration'
        assert entry.details['old_value'] is True
        assert entry.details['new_value'] is False
