"""
Tests for tenant management and maturity computation.
"""
import pytest
from datetime import datetime, timedelta, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, TenantSettings,
    GlobalRole, MaturityState
)


class TestTenantMaturityComputation:
    """Test tenant maturity state computation with various thresholds."""

    def test_bootstrap_tenant_with_single_admin(self, session, sample_tenant):
        """Single admin keeps tenant in BOOTSTRAP."""
        # Create single admin
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

        computed_state = sample_tenant.compute_maturity_state()
        assert computed_state == MaturityState.BOOTSTRAP

    def test_mature_with_two_admins(self, session, sample_tenant):
        """Two admins trigger MATURE state."""
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

        computed_state = sample_tenant.compute_maturity_state()
        assert computed_state == MaturityState.MATURE

    def test_mature_with_admin_and_steward(self, session, sample_tenant):
        """One admin + one steward trigger MATURE state."""
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

        computed_state = sample_tenant.compute_maturity_state()
        assert computed_state == MaturityState.MATURE

    def test_mature_with_user_threshold(self, session, sample_tenant):
        """Reaching user threshold triggers MATURE state."""
        # Set low user threshold
        sample_tenant.maturity_user_threshold = 3
        session.commit()

        # Create 3 users (including one admin)
        for i in range(3):
            user = User(
                email=f'user{i}@example.com',
                name=f'User {i}',
                sso_domain='example.com',
                auth_type='local'
            )
            session.add(user)
            session.flush()

            role = GlobalRole.ADMIN if i == 0 else GlobalRole.USER
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=sample_tenant.id,
                global_role=role
            )
            session.add(membership)
        session.commit()

        computed_state = sample_tenant.compute_maturity_state()
        assert computed_state == MaturityState.MATURE

    def test_mature_with_age_threshold(self, session, sample_tenant):
        """Reaching age threshold triggers MATURE state."""
        # Create single admin
        user = User(email='admin@example.com', name='Admin', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()
        membership = TenantMembership(user_id=user.id, tenant_id=sample_tenant.id, global_role=GlobalRole.ADMIN)
        session.add(membership)

        # Set age threshold to 1 day and backdate creation
        sample_tenant.maturity_age_days = 1
        sample_tenant.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
        session.commit()

        computed_state = sample_tenant.compute_maturity_state()
        assert computed_state == MaturityState.MATURE

    def test_handles_none_user_threshold(self, session, sample_tenant):
        """Handles None user threshold gracefully (uses default 5)."""
        # Create single admin
        user = User(email='admin@example.com', name='Admin', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()
        membership = TenantMembership(user_id=user.id, tenant_id=sample_tenant.id, global_role=GlobalRole.ADMIN)
        session.add(membership)

        # Set threshold to None
        sample_tenant.maturity_user_threshold = None
        sample_tenant.maturity_age_days = 90
        session.commit()

        # Should use default threshold of 5
        computed_state = sample_tenant.compute_maturity_state()
        # With 1 member, should be BOOTSTRAP (default threshold is 5)
        assert computed_state == MaturityState.BOOTSTRAP

    def test_handles_none_age_threshold(self, session, sample_tenant):
        """Handles None age threshold gracefully (uses default 90)."""
        # Create single admin
        user = User(email='admin@example.com', name='Admin', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()
        membership = TenantMembership(user_id=user.id, tenant_id=sample_tenant.id, global_role=GlobalRole.ADMIN)
        session.add(membership)

        # Set threshold to None
        sample_tenant.maturity_age_days = None
        sample_tenant.maturity_user_threshold = 10
        sample_tenant.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
        session.commit()

        # Should use default age of 90 days
        computed_state = sample_tenant.compute_maturity_state()
        # Tenant is only 2 days old, default is 90
        assert computed_state == MaturityState.BOOTSTRAP

    def test_handles_none_created_at(self, session, sample_tenant):
        """Handles None created_at gracefully."""
        # Create single admin
        user = User(email='admin@example.com', name='Admin', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()
        membership = TenantMembership(user_id=user.id, tenant_id=sample_tenant.id, global_role=GlobalRole.ADMIN)
        session.add(membership)

        # Set created_at to None
        sample_tenant.created_at = None
        sample_tenant.maturity_age_days = 1
        session.commit()

        # Should handle None gracefully and use current time
        computed_state = sample_tenant.compute_maturity_state()
        # Should be BOOTSTRAP since age is 0
        assert computed_state == MaturityState.BOOTSTRAP


class TestTenantMaturityUpdate:
    """Test update_maturity method."""

    def test_update_maturity_changes_state(self, session, sample_tenant):
        """update_maturity changes state when conditions met."""
        # Start in BOOTSTRAP
        assert sample_tenant.maturity_state == MaturityState.BOOTSTRAP

        # Create two admins to trigger maturity
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

        changed = sample_tenant.update_maturity()
        assert changed is True
        assert sample_tenant.maturity_state == MaturityState.MATURE

    def test_update_maturity_no_change_when_already_mature(self, session, sample_tenant):
        """update_maturity returns False when state unchanged."""
        # First, set up conditions that would compute to MATURE
        # Add two admins to meet multi-admin requirement
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

        # First update should change from PROVISIONAL to MATURE
        changed1 = sample_tenant.update_maturity()
        assert sample_tenant.maturity_state == MaturityState.MATURE

        # Second call should return False since it's already MATURE
        # and conditions still support MATURE
        changed2 = sample_tenant.update_maturity()
        assert changed2 is False
        assert sample_tenant.maturity_state == MaturityState.MATURE


class TestTenantHelperMethods:
    """Test tenant helper methods."""

    def test_get_admin_count(self, session, sample_tenant):
        """get_admin_count returns correct count."""
        # Create 2 admins
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

    def test_get_admin_count_excludes_provisional(self, session, sample_tenant):
        """get_admin_count excludes provisional admins."""
        # Create 1 admin and 1 provisional
        admin = User(email='admin@example.com', name='Admin', sso_domain='example.com', auth_type='local')
        session.add(admin)
        session.flush()
        admin_mem = TenantMembership(user_id=admin.id, tenant_id=sample_tenant.id, global_role=GlobalRole.ADMIN)
        session.add(admin_mem)

        prov = User(email='prov@example.com', name='Provisional', sso_domain='example.com', auth_type='local')
        session.add(prov)
        session.flush()
        prov_mem = TenantMembership(user_id=prov.id, tenant_id=sample_tenant.id, global_role=GlobalRole.PROVISIONAL_ADMIN)
        session.add(prov_mem)
        session.commit()

        assert sample_tenant.get_admin_count() == 1

    def test_get_steward_count(self, session, sample_tenant):
        """get_steward_count returns correct count."""
        # Create 2 stewards
        for i in range(2):
            user = User(
                email=f'steward{i}@example.com',
                name=f'Steward {i}',
                sso_domain='example.com',
                auth_type='local'
            )
            session.add(user)
            session.flush()
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=sample_tenant.id,
                global_role=GlobalRole.STEWARD
            )
            session.add(membership)
        session.commit()

        assert sample_tenant.get_steward_count() == 2

    def test_get_member_count(self, session, sample_tenant):
        """get_member_count returns total members."""
        # Create mixed roles
        roles = [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.USER, GlobalRole.USER]
        for i, role in enumerate(roles):
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
                global_role=role
            )
            session.add(membership)
        session.commit()

        assert sample_tenant.get_member_count() == 4

    def test_is_mature(self, session, sample_tenant):
        """is_mature returns correct boolean."""
        assert sample_tenant.is_mature() is False

        sample_tenant.maturity_state = MaturityState.MATURE
        assert sample_tenant.is_mature() is True


class TestTenantToDictMethod:
    """Test tenant to_dict serialization."""

    def test_to_dict_includes_essential_fields(self, session, sample_tenant):
        """to_dict includes all essential tenant fields."""
        data = sample_tenant.to_dict()

        assert 'id' in data
        assert 'domain' in data
        assert 'name' in data
        assert 'status' in data
        assert 'maturity_state' in data
        assert 'created_at' in data
        assert 'maturity_age_days' in data
        assert 'maturity_user_threshold' in data
        assert 'admin_count' in data
        assert 'steward_count' in data
        assert 'member_count' in data

    def test_to_dict_uses_domain_as_fallback_name(self, session):
        """to_dict uses domain as name when name is None."""
        tenant = Tenant(
            domain='test.com',
            name=None,
            status='active',
            maturity_state=MaturityState.BOOTSTRAP
        )
        session.add(tenant)
        session.commit()

        data = tenant.to_dict()
        assert data['name'] == 'test.com'


class TestTenantSoftDelete:
    """Test tenant soft delete functionality."""

    def test_tenant_has_soft_delete_fields(self, sample_tenant):
        """Tenant model has soft delete fields."""
        assert hasattr(sample_tenant, 'deleted_at')
        assert hasattr(sample_tenant, 'deleted_by_admin')
        assert hasattr(sample_tenant, 'deletion_expires_at')

    def test_soft_delete_sets_fields(self, session, sample_tenant):
        """Soft deleting tenant sets deletion fields."""
        deletion_time = datetime.now(timezone.utc).replace(tzinfo=None)
        sample_tenant.deleted_at = deletion_time
        sample_tenant.deleted_by_admin = 'superadmin'
        sample_tenant.deletion_expires_at = deletion_time + timedelta(days=30)
        session.commit()

        session.refresh(sample_tenant)
        assert sample_tenant.deleted_at is not None
        assert sample_tenant.deleted_by_admin == 'superadmin'
        assert sample_tenant.deletion_expires_at is not None


class TestTenantSettings:
    """Test TenantSettings model."""

    def test_tenant_settings_creation(self, session, sample_tenant):
        """Can create tenant settings."""
        settings = TenantSettings(
            tenant_id=sample_tenant.id,
            auth_method='local',
            allow_password=True,
            allow_passkey=True,
            allow_registration=True,
            require_approval=False,
            tenant_prefix='TST'
        )
        session.add(settings)
        session.commit()

        assert settings.id is not None
        assert settings.tenant_id == sample_tenant.id

    def test_tenant_settings_to_dict(self, session, sample_tenant):
        """TenantSettings.to_dict includes all fields."""
        settings = TenantSettings(
            tenant_id=sample_tenant.id,
            auth_method='sso',
            allow_password=False,
            allow_passkey=True
        )
        session.add(settings)
        session.commit()

        data = settings.to_dict()
        assert 'id' in data
        assert 'tenant_id' in data
        assert 'auth_method' in data
        assert 'allow_password' in data
        assert 'allow_passkey' in data
        assert 'allow_registration' in data
        assert 'require_approval' in data
        assert data['auth_method'] == 'sso'

    def test_tenant_settings_relationship(self, session, sample_tenant_with_settings):
        """Tenant has one-to-one relationship with settings."""
        tenant = sample_tenant_with_settings
        assert tenant.settings is not None
        assert tenant.settings.tenant_id == tenant.id
