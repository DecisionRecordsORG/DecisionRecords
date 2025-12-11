# Backend Unit Tests

Comprehensive Python unit tests for the Architecture Decisions Flask backend application.

## Test Structure

```
tests/
├── __init__.py                 # Package marker
├── conftest.py                 # Pytest fixtures (test database, users, tenants)
├── README.md                   # This file
├── test_auth.py                # Authentication and auth decorator tests
├── test_decisions.py           # Decision CRUD and deletion tests
├── test_governance.py          # Governance model tests (existing)
├── test_models.py              # Database model unit tests
├── test_role_requests.py       # Role request functionality tests
├── test_security.py            # Security and sanitization tests
├── test_spaces.py              # Space management tests (existing)
├── test_tenants.py             # Tenant maturity and management tests
└── test_v15_governance_models.py  # v1.5 governance integration tests (existing)
```

## Running Tests

### Run All Tests

```bash
# From project root
pytest tests/

# With verbose output
pytest tests/ -v

# With coverage report
pytest tests/ --cov=. --cov-report=html
```

### Run Specific Test Files

```bash
# Run only auth tests
pytest tests/test_auth.py -v

# Run only decision tests
pytest tests/test_decisions.py -v

# Run only governance tests
pytest tests/test_governance.py -v
```

### Run Specific Test Classes or Functions

```bash
# Run a specific test class
pytest tests/test_auth.py::TestGetCurrentUser -v

# Run a specific test function
pytest tests/test_decisions.py::TestDecisionDeletion::test_admin_can_delete_decision -v
```

## Test Coverage

### Key Areas Tested

#### Authentication (`test_auth.py`)
- User authentication and session management
- Master account authentication
- Password hashing and validation
- User model methods (get_membership, is_admin_of, etc.)
- Email domain extraction

#### Decisions (`test_decisions.py`)
- Decision deletion with role checks
- Soft delete with 30-day retention
- Rate limiting (3 deletions in 5 minutes)
- Rate limit window expiration
- Decision history tracking
- Display ID generation with tenant prefix

#### Governance (`test_governance.py`)
- High-impact settings guards
- Provisional admin restrictions
- Automatic role upgrades on maturity
- Role promotion permissions
- Role demotion checks
- Audit logging

#### Models (`test_models.py`)
- TenantMembership properties and permissions
- Space creation and relationships
- DecisionSpace linking (many-to-many)
- AuditLog creation and JSON storage
- SystemConfig get/set operations
- Enum types validation

#### Role Requests (`test_role_requests.py`)
- Role request creation
- Duplicate request prevention
- Request approval logic
- Request rejection logic
- Permission checks (who can approve what)
- Audit log creation for approvals

#### Security (`test_security.py`)
- HTML sanitization (XSS prevention)
- String sanitization with max length
- Title/name sanitization (no HTML)
- Email validation and sanitization
- Domain validation
- Request data schema validation
- CSRF token generation and validation

#### Tenants (`test_tenants.py`)
- Maturity state computation
- Threshold handling (None values)
- Two admin maturity trigger
- Admin + steward maturity trigger
- User count threshold
- Age threshold
- Maturity state updates
- Helper methods (get_admin_count, etc.)
- Soft delete fields

## Test Fixtures

Common fixtures available in `conftest.py`:

- `app` - Flask test application with in-memory SQLite
- `session` - Database session
- `client` - Test HTTP client
- `authenticated_client` - Client with user session
- `admin_client` - Client with admin session
- `sample_user` - Regular user
- `admin_user` - Admin user with membership
- `steward_user` - Steward user with membership
- `sample_tenant` - Tenant in BOOTSTRAP state
- `sample_tenant_with_settings` - Tenant with TenantSettings
- `sample_membership` - User membership (regular user role)
- `sample_space` - Default space
- `sample_decision` - Sample decision record

## Test Requirements

The tests use an in-memory SQLite database for isolation and speed. Required packages:

```
pytest>=7.0.0
pytest-cov>=4.0.0
flask>=2.0.0
sqlalchemy>=1.4.0
werkzeug>=2.0.0
```

## Important Test Patterns

### Testing with Maturity State

```python
def test_mature_tenant(session, sample_tenant):
    # Set tenant to MATURE
    sample_tenant.maturity_state = MaturityState.MATURE
    session.commit()

    # Test logic that requires mature tenant
    assert sample_tenant.is_mature() is True
```

### Testing Role Permissions

```python
def test_admin_permission(session, sample_tenant, admin_user):
    membership = admin_user.get_membership(sample_tenant.id)
    assert membership.can_change_tenant_settings is True
```

### Testing Rate Limiting

```python
def test_rate_limit(session, sample_tenant, admin_user):
    membership = admin_user.get_membership(sample_tenant.id)

    # Set to rate limit threshold
    membership.deletion_count_window_start = datetime.utcnow()
    membership.deletion_count = 3
    session.commit()

    # Test rate limit behavior
    assert membership.deletion_count >= 3
```

### Testing Soft Delete

```python
def test_soft_delete(session, sample_decision, admin_user):
    sample_decision.deleted_at = datetime.utcnow()
    sample_decision.deleted_by_id = admin_user.id
    session.commit()

    # Verify not returned in normal queries
    decision = ArchitectureDecision.query.filter_by(
        id=sample_decision.id,
        deleted_at=None
    ).first()
    assert decision is None
```

## Key Test Scenarios

### Recently Added Tests for Bug Fixes

1. **Maturity Computation with None Thresholds** (`test_tenants.py`)
   - Tests handling of `None` values for `maturity_user_threshold`
   - Tests handling of `None` values for `maturity_age_days`
   - Tests handling of `None` for `created_at`

2. **Role Request Creation** (`test_role_requests.py`)
   - Tests POST `/api/admin/role-requests` endpoint logic
   - Tests duplicate request prevention
   - Tests role validation

3. **Decision Deletion Rate Limiting** (`test_decisions.py`)
   - Tests soft delete with retention window
   - Tests rate limiting after 3 deletions in 5 minutes
   - Tests role-based deletion permissions
   - Tests provisional admin in BOOTSTRAP vs MATURE

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```bash
# CI test command
FLASK_ENV=testing pytest tests/ --cov=. --cov-report=xml
```

The `FLASK_ENV=testing` environment variable ensures:
- SQLite in-memory database is used
- Rate limiting is disabled
- Test-specific configurations are applied

## Writing New Tests

When adding new tests, follow these guidelines:

1. **Use existing fixtures** from `conftest.py` when possible
2. **Test both success and error cases**
3. **Test edge cases** (None values, empty strings, max lengths)
4. **Test permissions** for role-based features
5. **Use descriptive test names** that explain what is being tested
6. **Group related tests** into classes for organization
7. **Add docstrings** to test functions explaining the scenario

Example:

```python
class TestNewFeature:
    """Test new feature functionality."""

    def test_feature_succeeds_for_admin(self, session, admin_user):
        """Admin users can use the new feature."""
        # Test logic here
        assert result is True

    def test_feature_fails_for_regular_user(self, session, sample_user):
        """Regular users cannot use the new feature."""
        # Test logic here
        assert result is False
```

## Debugging Tests

Run tests with debugging output:

```bash
# Print output
pytest tests/test_auth.py -v -s

# Stop on first failure
pytest tests/ -x

# Run last failed tests only
pytest tests/ --lf

# Drop into debugger on failure
pytest tests/ --pdb
```

## Test Database

Tests use an in-memory SQLite database that is:
- Created fresh for each test session
- Isolated from production database
- Fast and disposable
- Automatically cleaned up after tests

The database schema is created from the SQLAlchemy models, ensuring tests always run against the current schema.
