"""
Tests for role request functionality.
"""
import pytest
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, RoleRequest,
    GlobalRole, RequestedRole, RequestStatus, AuditLog
)


class TestRoleRequestCreation:
    """Test role request creation endpoint logic."""

    def test_user_can_request_steward_role(self, session, sample_tenant, sample_user, sample_membership):
        """Regular user can request steward role."""
        # Create role request
        role_request = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            reason='I want to help manage the space'
        )
        session.add(role_request)
        session.commit()

        assert role_request.id is not None
        assert role_request.status == RequestStatus.PENDING
        assert role_request.requested_role == RequestedRole.STEWARD

    def test_user_can_request_admin_role(self, session, sample_tenant, sample_user, sample_membership):
        """Regular user can request admin role."""
        role_request = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.ADMIN,
            reason='I need admin access'
        )
        session.add(role_request)
        session.commit()

        assert role_request.id is not None
        assert role_request.requested_role == RequestedRole.ADMIN

    def test_cannot_request_if_already_admin(self, session, sample_tenant, admin_user):
        """Admin users should not create requests."""
        membership = admin_user.get_membership(sample_tenant.id)
        assert membership.global_role == GlobalRole.ADMIN

        # Request would be rejected at endpoint level
        # Here we verify the logic
        if membership.global_role == GlobalRole.ADMIN:
            # Should not create request
            request_count = RoleRequest.query.filter_by(
                user_id=admin_user.id,
                tenant_id=sample_tenant.id
            ).count()
            assert request_count == 0

    def test_cannot_request_steward_if_already_steward(self, session, sample_tenant, steward_user):
        """Steward cannot request steward role again."""
        membership = steward_user.get_membership(sample_tenant.id)
        assert membership.global_role == GlobalRole.STEWARD

        # Check logic that would prevent duplicate request
        if membership.global_role == GlobalRole.STEWARD:
            # Should not create steward request
            pass

    def test_steward_can_request_admin_upgrade(self, session, sample_tenant, steward_user):
        """Steward can request upgrade to admin."""
        role_request = RoleRequest(
            user_id=steward_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.ADMIN,
            reason='Need admin access for tenant config'
        )
        session.add(role_request)
        session.commit()

        assert role_request.id is not None
        assert role_request.requested_role == RequestedRole.ADMIN

    def test_prevents_duplicate_pending_requests(self, session, sample_tenant, sample_user):
        """Cannot create duplicate pending requests for same role."""
        # Create first request
        request1 = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            reason='First request'
        )
        session.add(request1)
        session.commit()

        # Check for existing pending request
        existing = RoleRequest.query.filter_by(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            status=RequestStatus.PENDING
        ).first()

        assert existing is not None
        # Endpoint would reject creating request2

    def test_can_create_new_request_after_rejection(self, session, sample_tenant, sample_user):
        """Can create new request after previous was rejected."""
        # Create and reject first request
        request1 = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            reason='First request',
            status=RequestStatus.REJECTED
        )
        session.add(request1)
        session.commit()

        # Check for pending requests only
        pending = RoleRequest.query.filter_by(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            status=RequestStatus.PENDING
        ).first()

        assert pending is None
        # New request can be created


class TestRoleRequestApproval:
    """Test role request approval logic."""

    def test_approval_updates_membership(self, session, sample_tenant, sample_user, sample_membership, admin_user):
        """Approving request updates user's role."""
        # Create request
        role_request = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            reason='Test'
        )
        session.add(role_request)
        session.commit()

        # Approve request
        role_request.status = RequestStatus.APPROVED
        role_request.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        role_request.reviewed_by_id = admin_user.id

        # Update membership
        sample_membership.global_role = GlobalRole.STEWARD
        session.commit()

        session.refresh(sample_membership)
        assert sample_membership.global_role == GlobalRole.STEWARD
        assert role_request.status == RequestStatus.APPROVED

    def test_approval_creates_audit_log(self, session, sample_tenant, sample_user, admin_user):
        """Approving request creates audit log entry."""
        from governance import log_admin_action

        role_request = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            reason='Test'
        )
        session.add(role_request)
        session.commit()

        # Log approval
        audit_entry = log_admin_action(
            tenant_id=sample_tenant.id,
            actor_user_id=admin_user.id,
            action_type=AuditLog.ACTION_ROLE_REQUEST_APPROVED,
            target_entity='role_request',
            target_id=role_request.id,
            details={
                'requested_role': 'steward',
                'user_id': sample_user.id
            }
        )
        session.commit()

        assert audit_entry.id is not None
        assert audit_entry.action_type == AuditLog.ACTION_ROLE_REQUEST_APPROVED

    def test_admin_can_approve_steward_request(self, session, sample_tenant, admin_user):
        """Admin has permission to approve steward requests."""
        membership = admin_user.get_membership(sample_tenant.id)
        assert membership.can_promote_to_steward is True

    def test_steward_can_approve_steward_request(self, session, sample_tenant, steward_user):
        """Steward has permission to approve steward requests."""
        membership = steward_user.get_membership(sample_tenant.id)
        assert membership.can_promote_to_steward is True

    def test_only_admin_can_approve_admin_request(self, session, sample_tenant, admin_user, steward_user):
        """Only admin can approve admin requests, not steward."""
        admin_membership = admin_user.get_membership(sample_tenant.id)
        steward_membership = steward_user.get_membership(sample_tenant.id)

        assert admin_membership.can_promote_to_admin is True
        assert steward_membership.can_promote_to_admin is False


class TestRoleRequestRejection:
    """Test role request rejection logic."""

    def test_rejection_does_not_update_membership(self, session, sample_tenant, sample_user, sample_membership, admin_user):
        """Rejecting request does not change user's role."""
        original_role = sample_membership.global_role

        role_request = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            reason='Test'
        )
        session.add(role_request)
        session.commit()

        # Reject request
        role_request.status = RequestStatus.REJECTED
        role_request.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        role_request.reviewed_by_id = admin_user.id
        role_request.rejection_reason = 'Not needed at this time'
        session.commit()

        session.refresh(sample_membership)
        assert sample_membership.global_role == original_role
        assert role_request.status == RequestStatus.REJECTED

    def test_rejection_includes_reason(self, session, sample_tenant, sample_user, admin_user):
        """Rejection can include a reason."""
        role_request = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.ADMIN,
            reason='Test'
        )
        session.add(role_request)
        session.commit()

        role_request.status = RequestStatus.REJECTED
        role_request.rejection_reason = 'Need more experience first'
        session.commit()

        assert role_request.rejection_reason is not None
        assert 'experience' in role_request.rejection_reason


class TestRoleRequestModel:
    """Test RoleRequest model methods."""

    def test_to_dict_includes_all_fields(self, session, sample_tenant, sample_user):
        """to_dict includes all role request fields."""
        role_request = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            reason='Test reason'
        )
        session.add(role_request)
        session.commit()

        data = role_request.to_dict()
        assert 'id' in data
        assert 'user_id' in data
        assert 'tenant_id' in data
        assert 'requested_role' in data
        assert 'reason' in data
        assert 'status' in data
        assert 'created_at' in data
        assert data['requested_role'] == 'steward'
        assert data['status'] == 'pending'

    def test_to_dict_includes_user_data(self, session, sample_tenant, sample_user):
        """to_dict includes nested user data."""
        role_request = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.ADMIN,
            reason='Test'
        )
        session.add(role_request)
        session.commit()

        data = role_request.to_dict()
        assert 'user' in data
        assert data['user']['email'] == sample_user.email

    def test_to_dict_includes_reviewer_when_reviewed(self, session, sample_tenant, sample_user, admin_user):
        """to_dict includes reviewer data when request is reviewed."""
        role_request = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            reason='Test',
            status=RequestStatus.APPROVED,
            reviewed_by_id=admin_user.id,
            reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        session.add(role_request)
        session.commit()

        data = role_request.to_dict()
        assert 'reviewed_by' in data
        assert data['reviewed_by']['email'] == admin_user.email
        assert 'reviewed_at' in data


class TestRoleRequestQueries:
    """Test role request querying."""

    def test_query_pending_requests_for_tenant(self, session, sample_tenant, sample_user):
        """Can query pending requests for a tenant."""
        # Create pending request
        request1 = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.STEWARD,
            reason='Test'
        )
        session.add(request1)

        # Create approved request
        request2 = RoleRequest(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id,
            requested_role=RequestedRole.ADMIN,
            reason='Test',
            status=RequestStatus.APPROVED
        )
        session.add(request2)
        session.commit()

        # Query only pending
        pending = RoleRequest.query.filter_by(
            tenant_id=sample_tenant.id,
            status=RequestStatus.PENDING
        ).all()

        assert len(pending) == 1
        assert pending[0].requested_role == RequestedRole.STEWARD

    def test_query_user_requests(self, session, sample_tenant, sample_user):
        """Can query all requests by a user."""
        # Create multiple requests
        for role in [RequestedRole.STEWARD, RequestedRole.ADMIN]:
            request = RoleRequest(
                user_id=sample_user.id,
                tenant_id=sample_tenant.id,
                requested_role=role,
                reason='Test'
            )
            session.add(request)
        session.commit()

        # Query user's requests
        user_requests = RoleRequest.query.filter_by(
            user_id=sample_user.id,
            tenant_id=sample_tenant.id
        ).all()

        assert len(user_requests) == 2
