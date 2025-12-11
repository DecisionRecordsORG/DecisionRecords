# Testing Patterns & Examples

Quick reference guide for common testing patterns used in the Architecture Decisions backend tests.

## Table of Contents
1. [Basic Test Structure](#basic-test-structure)
2. [Using Fixtures](#using-fixtures)
3. [Testing Role Permissions](#testing-role-permissions)
4. [Testing Maturity States](#testing-maturity-states)
5. [Testing Rate Limiting](#testing-rate-limiting)
6. [Testing Soft Delete](#testing-soft-delete)
7. [Testing Input Sanitization](#testing-input-sanitization)
8. [Testing Audit Logging](#testing-audit-logging)
9. [Common Assertions](#common-assertions)
10. [Error Testing](#error-testing)

## Basic Test Structure

### Simple Test

```python
def test_feature_works(session, sample_user):
    """Feature description."""
    # Arrange - Set up test data
    user = sample_user

    # Act - Execute the code being tested
    result = user.to_dict()

    # Assert - Verify the outcome
    assert result['email'] == 'test@example.com'
```

### Class-Based Tests

```python
class TestFeature:
    """Test feature functionality."""

    def test_success_case(self, session, sample_user):
        """Feature succeeds in normal case."""
        assert sample_user.email is not None

    def test_error_case(self, session):
        """Feature fails when conditions not met."""
        # Test error scenario
        pass
```

## Using Fixtures

### Basic Fixture Usage

```python
def test_with_user(sample_user):
    """Use the sample_user fixture."""
    assert sample_user.sso_domain == 'example.com'

def test_with_tenant(sample_tenant):
    """Use the sample_tenant fixture."""
    assert sample_tenant.status == 'active'
```

### Multiple Fixtures

```python
def test_with_multiple_fixtures(session, sample_tenant, admin_user, sample_decision):
    """Use multiple fixtures together."""
    membership = admin_user.get_membership(sample_tenant.id)
    assert membership is not None
    assert sample_decision.tenant_id == sample_tenant.id
```

### Creating Custom Test Data

```python
def test_with_custom_data(session, sample_tenant):
    """Create custom test data."""
    from models import User, TenantMembership, GlobalRole

    # Create custom user
    user = User(
        email='custom@example.com',
        name='Custom User',
        sso_domain='example.com',
        auth_type='local'
    )
    session.add(user)
    session.flush()

    # Create membership
    membership = TenantMembership(
        user_id=user.id,
        tenant_id=sample_tenant.id,
        global_role=GlobalRole.STEWARD
    )
    session.add(membership)
    session.commit()

    # Test with custom data
    assert user.is_admin_of(sample_tenant.id) is True
```

## Testing Role Permissions

### Admin Role Check

```python
def test_admin_has_permission(session, sample_tenant, admin_user):
    """Admin users have admin permissions."""
    membership = admin_user.get_membership(sample_tenant.id)

    assert membership.is_admin is True
    assert membership.is_full_admin is True
    assert membership.can_change_tenant_settings is True
```

### Steward Role Check

```python
def test_steward_has_limited_permissions(session, sample_tenant, steward_user):
    """Steward users have limited admin permissions."""
    membership = steward_user.get_membership(sample_tenant.id)

    assert membership.is_admin is True  # Admin-level
    assert membership.is_full_admin is False  # Not full admin
    assert membership.can_change_tenant_settings is False  # Can't change settings
    assert membership.can_approve_requests is True  # Can approve requests
```

### Regular User Check

```python
def test_user_has_no_admin_permissions(session, sample_user, sample_tenant, sample_membership):
    """Regular users have no admin permissions."""
    assert sample_membership.is_admin is False
    assert sample_membership.can_change_tenant_settings is False
```

### Testing Allowed Roles

```python
def test_allowed_roles_for_action(session, sample_tenant):
    """Test which roles can perform an action."""
    from models import GlobalRole, MaturityState

    # Action: delete decision
    allowed_roles = [GlobalRole.ADMIN, GlobalRole.STEWARD]

    # In BOOTSTRAP, provisional admin also allowed
    if sample_tenant.maturity_state == MaturityState.BOOTSTRAP:
        allowed_roles.append(GlobalRole.PROVISIONAL_ADMIN)

    # Test each role
    test_role = GlobalRole.ADMIN
    assert test_role in allowed_roles
```

## Testing Maturity States

### Bootstrap Tenant

```python
def test_bootstrap_behavior(session, sample_tenant):
    """Test behavior in BOOTSTRAP state."""
    from models import MaturityState

    # Ensure tenant is in BOOTSTRAP
    assert sample_tenant.maturity_state == MaturityState.BOOTSTRAP

    # Test bootstrap-specific logic
    computed_state = sample_tenant.compute_maturity_state()
    assert computed_state == MaturityState.BOOTSTRAP
```

### Mature Tenant

```python
def test_mature_behavior(session, sample_tenant):
    """Test behavior in MATURE state."""
    from models import MaturityState

    # Set tenant to MATURE
    sample_tenant.maturity_state = MaturityState.MATURE
    session.commit()

    # Test mature-specific logic
    assert sample_tenant.is_mature() is True
```

### Maturity Transition

```python
def test_maturity_transition(session, sample_tenant):
    """Test transition from BOOTSTRAP to MATURE."""
    from models import User, TenantMembership, GlobalRole, MaturityState

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

    # Update maturity
    changed = sample_tenant.update_maturity()

    # Verify transition
    assert changed is True
    assert sample_tenant.maturity_state == MaturityState.MATURE
```

### Testing with None Thresholds

```python
def test_none_threshold_handling(session, sample_tenant):
    """Test handling of None maturity thresholds."""
    from models import User, TenantMembership, GlobalRole

    # Set thresholds to None
    sample_tenant.maturity_user_threshold = None
    sample_tenant.maturity_age_days = None
    session.commit()

    # Create single admin
    user = User(email='admin@example.com', name='Admin', sso_domain='example.com', auth_type='local')
    session.add(user)
    session.flush()
    membership = TenantMembership(user_id=user.id, tenant_id=sample_tenant.id, global_role=GlobalRole.ADMIN)
    session.add(membership)
    session.commit()

    # Should use defaults (5 users, 90 days)
    computed_state = sample_tenant.compute_maturity_state()

    # With 1 member and recent creation, should be BOOTSTRAP
    assert computed_state == MaturityState.BOOTSTRAP
```

## Testing Rate Limiting

### Basic Rate Limiting

```python
def test_rate_limiting_tracks_count(session, sample_tenant, admin_user):
    """Test that deletion count is tracked."""
    from datetime import datetime

    membership = admin_user.get_membership(sample_tenant.id)

    # Initial state
    assert membership.deletion_count in (None, 0)

    # Simulate deletion
    membership.deletion_count_window_start = datetime.utcnow()
    membership.deletion_count = 1
    session.commit()

    # Verify tracking
    session.refresh(membership)
    assert membership.deletion_count == 1
```

### Rate Limit Trigger

```python
def test_rate_limit_triggered(session, sample_tenant, admin_user):
    """Test rate limit triggered after threshold."""
    from datetime import datetime

    membership = admin_user.get_membership(sample_tenant.id)
    RATE_LIMIT_COUNT = 3

    # Set to threshold
    membership.deletion_count_window_start = datetime.utcnow()
    membership.deletion_count = RATE_LIMIT_COUNT
    session.commit()

    # Check if at limit
    assert membership.deletion_count >= RATE_LIMIT_COUNT

    # Simulate triggering rate limit
    membership.deletion_rate_limited_at = datetime.utcnow()
    session.commit()

    # Verify rate limited
    assert membership.deletion_rate_limited_at is not None
```

### Rate Limit Expiration

```python
def test_rate_limit_expiration(session, sample_tenant, admin_user):
    """Test rate limit expires after 1 hour."""
    from datetime import datetime, timedelta

    membership = admin_user.get_membership(sample_tenant.id)

    # Set rate limit to 2 hours ago
    two_hours_ago = datetime.utcnow() - timedelta(hours=2)
    membership.deletion_rate_limited_at = two_hours_ago
    session.commit()

    # Check if expired (rate limit lasts 1 hour)
    now = datetime.utcnow()
    is_expired = now >= membership.deletion_rate_limited_at + timedelta(hours=1)

    assert is_expired is True
```

## Testing Soft Delete

### Soft Delete Operation

```python
def test_soft_delete(session, sample_decision, admin_user):
    """Test soft delete sets retention window."""
    from datetime import datetime, timedelta

    deletion_time = datetime.utcnow()
    retention_days = 30

    # Soft delete
    sample_decision.deleted_at = deletion_time
    sample_decision.deleted_by_id = admin_user.id
    sample_decision.deletion_expires_at = deletion_time + timedelta(days=retention_days)
    session.commit()

    # Verify soft delete
    session.refresh(sample_decision)
    assert sample_decision.deleted_at is not None
    assert sample_decision.deleted_by_id == admin_user.id
    assert sample_decision.deletion_expires_at is not None
```

### Query Filtering

```python
def test_soft_deleted_not_returned(session, sample_decision, admin_user):
    """Test soft deleted records filtered from queries."""
    from datetime import datetime
    from models import ArchitectureDecision

    # Soft delete
    sample_decision.deleted_at = datetime.utcnow()
    session.commit()

    # Query for non-deleted
    decision = ArchitectureDecision.query.filter_by(
        id=sample_decision.id,
        deleted_at=None
    ).first()

    # Should not be found
    assert decision is None
```

## Testing Input Sanitization

### HTML Sanitization

```python
def test_sanitize_removes_script_tags():
    """Test that script tags are removed."""
    from security import sanitize_html

    input_html = '<p>Safe</p><script>alert("xss")</script>'
    result = sanitize_html(input_html)

    assert '<script>' not in result
    assert 'alert' not in result
    assert 'Safe' in result
```

### Length Validation

```python
def test_sanitize_enforces_max_length():
    """Test max length enforcement."""
    from security import sanitize_title

    long_title = 'a' * 300
    result = sanitize_title(long_title)

    assert len(result) <= 255
```

### Email Validation

```python
def test_email_validation():
    """Test email format validation."""
    from security import validate_email

    assert validate_email('user@example.com') is True
    assert validate_email('invalid') is False
    assert validate_email('') is False
    assert validate_email(None) is False
```

## Testing Audit Logging

### Creating Audit Logs

```python
def test_audit_log_creation(session, sample_tenant, admin_user):
    """Test audit log is created for action."""
    from governance import log_admin_action
    from models import AuditLog

    # Log action
    entry = log_admin_action(
        tenant_id=sample_tenant.id,
        actor_user_id=admin_user.id,
        action_type=AuditLog.ACTION_CREATE_SPACE,
        target_entity='space',
        target_id=1,
        details={'name': 'New Space'}
    )
    session.commit()

    # Verify log created
    assert entry.id is not None
    assert entry.action_type == AuditLog.ACTION_CREATE_SPACE
    assert entry.details['name'] == 'New Space'
```

### Querying Audit Logs

```python
def test_query_audit_logs(session, sample_tenant, admin_user):
    """Test querying audit logs."""
    from governance import log_admin_action
    from models import AuditLog

    # Create multiple log entries
    for i in range(3):
        log_admin_action(
            tenant_id=sample_tenant.id,
            actor_user_id=admin_user.id,
            action_type=AuditLog.ACTION_PROMOTE_USER,
            target_entity='user',
            target_id=i,
            details={'role': 'steward'}
        )
    session.commit()

    # Query logs for tenant
    logs = AuditLog.query.filter_by(tenant_id=sample_tenant.id).all()

    assert len(logs) == 3
```

## Common Assertions

### Existence Checks

```python
# Object exists
assert user is not None
assert user.id is not None

# Object doesn't exist
assert user is None
```

### Equality Checks

```python
# Values match
assert user.email == 'test@example.com'
assert membership.global_role == GlobalRole.ADMIN

# Values don't match
assert user.email != 'wrong@example.com'
```

### Boolean Checks

```python
# True/False
assert user.is_admin is True
assert user.email_verified is False

# Truthy/Falsy
assert user.email  # Truthy (not empty)
assert not user.password_hash  # Falsy (None or empty)
```

### Collection Checks

```python
# Length
assert len(users) == 3
assert len(user.memberships.all()) > 0

# Membership
assert user in users_list
assert 'key' in dictionary

# Empty/Not empty
assert users  # Not empty
assert not []  # Empty
```

### Comparison Checks

```python
# Greater than
assert count > 0
assert len(items) >= 1

# Less than
assert age < 100
assert count <= 10
```

## Error Testing

### Testing Exceptions

```python
def test_raises_exception(session):
    """Test that exception is raised."""
    from models import User
    import pytest

    # Create duplicate user should raise error
    user1 = User(email='test@example.com', name='Test', sso_domain='example.com')
    session.add(user1)
    session.commit()

    user2 = User(email='test@example.com', name='Test2', sso_domain='example.com')
    session.add(user2)

    with pytest.raises(Exception):  # IntegrityError
        session.commit()
```

### Testing Error Messages

```python
def test_error_message(session):
    """Test error message content."""
    from governance import can_promote_to_role
    from models import GlobalRole

    # Steward trying to promote to admin
    allowed, reason = can_promote_to_role(steward_membership, GlobalRole.ADMIN)

    assert allowed is False
    assert 'administrator' in reason.lower()
```

### Testing Validation

```python
def test_validation_error():
    """Test validation returns error."""
    from security import sanitize_request_data

    schema = {
        'email': {'type': 'email', 'required': True}
    }
    data = {'email': 'invalid'}

    sanitized, errors = sanitize_request_data(data, schema)

    assert len(errors) > 0
    assert any('email' in err for err in errors)
```

## Tips and Best Practices

1. **Use descriptive test names** that explain what is being tested
2. **One assertion per logical concept** (can have multiple related asserts)
3. **Arrange-Act-Assert pattern** for clarity
4. **Use fixtures** to reduce duplication
5. **Test edge cases** (None, empty, max length, etc.)
6. **Test both success and failure** paths
7. **Keep tests isolated** - no dependencies between tests
8. **Use session.refresh()** after commits to get updated data
9. **session.flush()** to get IDs without committing
10. **Clean up with session.commit()** at end of setup

## Quick Reference

```python
# Common imports
from models import (
    db, User, Tenant, TenantMembership, GlobalRole,
    MaturityState, ArchitectureDecision, AuditLog
)
from governance import log_admin_action, can_promote_to_role
from security import sanitize_html, validate_email
from datetime import datetime, timedelta

# Creating test users
user = User(email='test@example.com', name='Test', sso_domain='example.com', auth_type='local')
session.add(user)
session.commit()

# Creating memberships
membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.ADMIN)
session.add(membership)
session.commit()

# Getting membership
membership = user.get_membership(tenant.id)

# Checking roles
assert user.is_admin_of(tenant.id) is True
assert membership.is_full_admin is True

# Maturity checks
assert tenant.is_mature() is False
computed = tenant.compute_maturity_state()
changed = tenant.update_maturity()

# Soft delete
decision.deleted_at = datetime.utcnow()
decision.deletion_expires_at = datetime.utcnow() + timedelta(days=30)

# Audit logging
log_admin_action(tenant_id, actor_user_id, action_type, target_entity, target_id, details)
```
