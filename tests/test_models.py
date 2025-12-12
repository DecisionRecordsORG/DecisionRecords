"""
Tests for database models.
"""
import pytest
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, Space, DecisionSpace,
    ArchitectureDecision, AuditLog, GlobalRole, VisibilityPolicy,
    MaturityState, SystemConfig
)


class TestTenantMembershipModel:
    """Test TenantMembership model and properties."""

    def test_is_admin_property_for_admin(self, session, sample_tenant, admin_user):
        """is_admin property returns True for admin roles."""
        membership = admin_user.get_membership(sample_tenant.id)
        assert membership.is_admin is True

    def test_is_admin_property_for_steward(self, session, sample_tenant, steward_user):
        """is_admin property returns True for steward (admin-level)."""
        membership = steward_user.get_membership(sample_tenant.id)
        assert membership.is_admin is True

    def test_is_admin_property_for_provisional(self, session, sample_tenant):
        """is_admin property returns True for provisional admin."""
        user = User(email='prov@example.com', name='Prov', sso_domain='example.com', auth_type='local')
        session.add(user)
        session.flush()
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=sample_tenant.id,
            global_role=GlobalRole.PROVISIONAL_ADMIN
        )
        session.add(membership)
        session.commit()

        assert membership.is_admin is True

    def test_is_admin_property_for_user(self, session, sample_user, sample_tenant, sample_membership):
        """is_admin property returns False for regular user."""
        assert sample_membership.is_admin is False

    def test_is_full_admin_property(self, session, sample_tenant, admin_user, steward_user):
        """is_full_admin property only True for full admin."""
        admin_mem = admin_user.get_membership(sample_tenant.id)
        steward_mem = steward_user.get_membership(sample_tenant.id)

        assert admin_mem.is_full_admin is True
        assert steward_mem.is_full_admin is False

    def test_can_change_tenant_settings_property(self, session, sample_tenant, admin_user, steward_user):
        """can_change_tenant_settings only True for full admin."""
        admin_mem = admin_user.get_membership(sample_tenant.id)
        steward_mem = steward_user.get_membership(sample_tenant.id)

        assert admin_mem.can_change_tenant_settings is True
        assert steward_mem.can_change_tenant_settings is False

    def test_can_approve_requests_property(self, session, sample_tenant, admin_user, steward_user, sample_user, sample_membership):
        """can_approve_requests True for admin-level roles."""
        admin_mem = admin_user.get_membership(sample_tenant.id)
        steward_mem = steward_user.get_membership(sample_tenant.id)

        assert admin_mem.can_approve_requests is True
        assert steward_mem.can_approve_requests is True
        assert sample_membership.can_approve_requests is False

    def test_deletion_rate_limiting_fields_exist(self, sample_membership):
        """Membership has deletion rate limiting fields."""
        assert hasattr(sample_membership, 'deletion_rate_limited_at')
        assert hasattr(sample_membership, 'deletion_count_window_start')
        assert hasattr(sample_membership, 'deletion_count')

    def test_to_dict_includes_role_flags(self, session, sample_tenant, admin_user):
        """to_dict includes role flag properties."""
        membership = admin_user.get_membership(sample_tenant.id)
        data = membership.to_dict()

        assert 'is_admin' in data
        assert 'is_full_admin' in data
        assert data['is_admin'] is True
        assert data['is_full_admin'] is True


class TestSpaceModel:
    """Test Space model."""

    def test_space_creation(self, session, sample_tenant, sample_user):
        """Can create a space."""
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

        assert space.id is not None
        assert space.name == 'Test Space'

    def test_space_to_dict(self, sample_space):
        """Space.to_dict includes all fields."""
        data = sample_space.to_dict()

        assert 'id' in data
        assert 'tenant_id' in data
        assert 'name' in data
        assert 'description' in data
        assert 'is_default' in data
        assert 'visibility_policy' in data
        assert 'created_by_id' in data
        assert 'created_at' in data

    def test_space_tenant_relationship(self, sample_space, sample_tenant):
        """Space has relationship to tenant."""
        assert sample_space.tenant_id == sample_tenant.id
        assert sample_space.tenant == sample_tenant


class TestDecisionSpaceModel:
    """Test DecisionSpace linking model."""

    def test_decision_space_creation(self, session, sample_decision, sample_space, sample_user):
        """Can create decision-space link."""
        link = DecisionSpace(
            decision_id=sample_decision.id,
            space_id=sample_space.id,
            added_by_id=sample_user.id
        )
        session.add(link)
        session.commit()

        assert link.id is not None
        assert link.decision_id == sample_decision.id
        assert link.space_id == sample_space.id

    def test_decision_space_unique_constraint(self, session, sample_decision, sample_space, sample_user):
        """Cannot create duplicate decision-space links."""
        link1 = DecisionSpace(
            decision_id=sample_decision.id,
            space_id=sample_space.id,
            added_by_id=sample_user.id
        )
        session.add(link1)
        session.commit()

        # Try to create duplicate
        link2 = DecisionSpace(
            decision_id=sample_decision.id,
            space_id=sample_space.id,
            added_by_id=sample_user.id
        )
        session.add(link2)

        with pytest.raises(Exception):  # IntegrityError
            session.commit()

    def test_decision_spaces_property(self, session, sample_decision, sample_user):
        """Decision.spaces property returns linked spaces."""
        # Create spaces and link them
        space1 = Space(
            tenant_id=sample_decision.tenant_id,
            name='Space 1',
            is_default=False,
            visibility_policy=VisibilityPolicy.TENANT_VISIBLE,
            created_by_id=sample_user.id
        )
        space2 = Space(
            tenant_id=sample_decision.tenant_id,
            name='Space 2',
            is_default=False,
            visibility_policy=VisibilityPolicy.TENANT_VISIBLE,
            created_by_id=sample_user.id
        )
        session.add_all([space1, space2])
        session.flush()

        link1 = DecisionSpace(decision_id=sample_decision.id, space_id=space1.id, added_by_id=sample_user.id)
        link2 = DecisionSpace(decision_id=sample_decision.id, space_id=space2.id, added_by_id=sample_user.id)
        session.add_all([link1, link2])
        session.commit()

        spaces = sample_decision.spaces
        assert len(spaces) == 2
        assert space1 in spaces
        assert space2 in spaces


class TestAuditLogModel:
    """Test AuditLog model."""

    def test_audit_log_creation(self, session, sample_tenant, admin_user):
        """Can create audit log entry."""
        audit = AuditLog(
            tenant_id=sample_tenant.id,
            actor_user_id=admin_user.id,
            action_type=AuditLog.ACTION_CREATE_SPACE,
            target_entity='space',
            target_id=1,
            details={'name': 'New Space'}
        )
        session.add(audit)
        session.commit()

        assert audit.id is not None
        assert audit.action_type == AuditLog.ACTION_CREATE_SPACE

    def test_audit_log_has_action_constants(self):
        """AuditLog has action type constants."""
        assert hasattr(AuditLog, 'ACTION_PROMOTE_USER')
        assert hasattr(AuditLog, 'ACTION_DEMOTE_USER')
        assert hasattr(AuditLog, 'ACTION_CHANGE_SETTING')
        assert hasattr(AuditLog, 'ACTION_APPROVE_REQUEST')
        assert hasattr(AuditLog, 'ACTION_REJECT_REQUEST')
        assert hasattr(AuditLog, 'ACTION_CREATE_SPACE')
        assert hasattr(AuditLog, 'ACTION_DELETE_SPACE')
        assert hasattr(AuditLog, 'ACTION_DELETE')
        assert hasattr(AuditLog, 'ACTION_ROLE_REQUESTED')
        assert hasattr(AuditLog, 'ACTION_MATURITY_CHANGE')

    def test_audit_log_to_dict(self, session, sample_tenant, admin_user):
        """AuditLog.to_dict includes all fields."""
        audit = AuditLog(
            tenant_id=sample_tenant.id,
            actor_user_id=admin_user.id,
            action_type=AuditLog.ACTION_PROMOTE_USER,
            target_entity='user',
            target_id=1,
            details={'old_role': 'user', 'new_role': 'steward'}
        )
        session.add(audit)
        session.commit()

        data = audit.to_dict()
        assert 'id' in data
        assert 'tenant_id' in data
        assert 'actor_user_id' in data
        assert 'action_type' in data
        assert 'target_entity' in data
        assert 'target_id' in data
        assert 'details' in data
        assert 'created_at' in data

    def test_audit_log_stores_json_details(self, session, sample_tenant, admin_user):
        """AuditLog can store complex JSON in details."""
        complex_details = {
            'setting': 'allow_registration',
            'old_value': True,
            'new_value': False,
            'metadata': {
                'reason': 'security',
                'approved_by': 'admin'
            }
        }

        audit = AuditLog(
            tenant_id=sample_tenant.id,
            actor_user_id=admin_user.id,
            action_type=AuditLog.ACTION_CHANGE_SETTING,
            details=complex_details
        )
        session.add(audit)
        session.commit()

        session.refresh(audit)
        assert audit.details['setting'] == 'allow_registration'
        assert audit.details['metadata']['reason'] == 'security'


class TestSystemConfigModel:
    """Test SystemConfig model."""

    def test_system_config_creation(self, session):
        """Can create system config entry."""
        config = SystemConfig(
            key='test_key',
            value='test_value',
            description='Test configuration'
        )
        session.add(config)
        session.commit()

        assert config.id is not None
        assert config.key == 'test_key'

    def test_get_config_value(self, session):
        """SystemConfig.get returns value for key."""
        config = SystemConfig(key='test_key', value='test_value')
        session.add(config)
        session.commit()

        value = SystemConfig.get('test_key')
        assert value == 'test_value'

    def test_get_config_default(self, session):
        """SystemConfig.get returns default for non-existent key."""
        value = SystemConfig.get('nonexistent', default='default_value')
        assert value == 'default_value'

    def test_get_bool_config(self, session):
        """SystemConfig.get_bool parses boolean values."""
        config = SystemConfig(key='bool_true', value='true')
        session.add(config)
        session.commit()

        assert SystemConfig.get_bool('bool_true') is True
        assert SystemConfig.get_bool('nonexistent', default=False) is False

    def test_get_int_config(self, session):
        """SystemConfig.get_int parses integer values."""
        config = SystemConfig(key='int_val', value='42')
        session.add(config)
        session.commit()

        assert SystemConfig.get_int('int_val') == 42
        assert SystemConfig.get_int('nonexistent', default=0) == 0

    def test_set_config_creates_new(self, session):
        """SystemConfig.set creates new entry if not exists."""
        SystemConfig.set('new_key', 'new_value', 'Description')
        session.commit()

        config = SystemConfig.query.filter_by(key='new_key').first()
        assert config is not None
        assert config.value == 'new_value'

    def test_set_config_updates_existing(self, session):
        """SystemConfig.set updates existing entry."""
        config = SystemConfig(key='update_key', value='old_value')
        session.add(config)
        session.commit()

        SystemConfig.set('update_key', 'new_value')
        session.commit()

        updated = SystemConfig.query.filter_by(key='update_key').first()
        assert updated.value == 'new_value'

    def test_to_dict_includes_all_fields(self, session):
        """SystemConfig.to_dict includes all fields."""
        config = SystemConfig(
            key='test',
            value='value',
            description='Description'
        )
        session.add(config)
        session.commit()

        data = config.to_dict()
        assert 'id' in data
        assert 'key' in data
        assert 'value' in data
        assert 'description' in data
        assert 'updated_at' in data


class TestEnumTypes:
    """Test enum types are properly defined."""

    def test_maturity_state_enum(self):
        """MaturityState enum has expected values."""
        assert MaturityState.BOOTSTRAP.value == 'bootstrap'
        assert MaturityState.MATURE.value == 'mature'

    def test_global_role_enum(self):
        """GlobalRole enum has expected values."""
        assert GlobalRole.USER.value == 'user'
        assert GlobalRole.PROVISIONAL_ADMIN.value == 'provisional_admin'
        assert GlobalRole.STEWARD.value == 'steward'
        assert GlobalRole.ADMIN.value == 'admin'

    def test_visibility_policy_enum(self):
        """VisibilityPolicy enum has expected values."""
        assert VisibilityPolicy.TENANT_VISIBLE.value == 'tenant_visible'
        assert VisibilityPolicy.SPACE_FOCUSED.value == 'space_focused'
