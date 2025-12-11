# Backend Unit Tests - Summary

This document summarizes the comprehensive unit tests created for the Architecture Decisions Flask backend.

## Files Created

### New Test Files (6 files)

1. **test_auth.py** - Authentication and user management tests
2. **test_decisions.py** - Decision CRUD and deletion tests
3. **test_models.py** - Database model unit tests
4. **test_role_requests.py** - Role request functionality tests
5. **test_security.py** - Security and input sanitization tests
6. **test_tenants.py** - Tenant maturity and management tests

### Updated Files

- **conftest.py** - Added `sample_decision`, `client`, `authenticated_client`, `admin_client` fixtures
- **README.md** - Comprehensive testing documentation

### Supporting Files

- **TEST_SUMMARY.md** - This file
- **run_tests.sh** - Test runner script

## Test Coverage Summary

### 1. Authentication Tests (`test_auth.py`)

**Classes:**
- `TestGetCurrentUser` - 4 tests
- `TestIsMasterAccount` - 3 tests
- `TestAuthenticateMaster` - 4 tests
- `TestExtractDomainFromEmail` - 5 tests
- `TestUserModel` - 14 tests
- `TestMasterAccountModel` - 5 tests

**Total:** 35 tests

**Key Scenarios Covered:**
- User session management
- Master account authentication
- Password hashing and validation
- User membership queries
- Role checking (is_admin_of, is_full_admin_of)
- Email domain extraction
- User serialization (to_dict)

### 2. Decision Tests (`test_decisions.py`)

**Classes:**
- `TestDecisionDeletion` - 10 tests
- `TestDecisionHistory` - 3 tests
- `TestDecisionModel` - 4 tests

**Total:** 17 tests

**Key Scenarios Covered:**
- Admin/steward can delete decisions
- Provisional admin can delete in BOOTSTRAP only
- Regular users cannot delete
- Deletion rate limiting (3 in 5 minutes)
- Rate limit expiration (1 hour)
- Rate limit window reset (5 minutes)
- Soft delete with 30-day retention
- Deleted decisions filtered from queries
- Decision history tracking
- Display ID generation

**Critical Bug Tests:**
- ✅ Role-based deletion permissions
- ✅ Rate limiting edge cases
- ✅ Soft delete retention window

### 3. Model Tests (`test_models.py`)

**Classes:**
- `TestTenantMembershipModel` - 9 tests
- `TestSpaceModel` - 3 tests
- `TestDecisionSpaceModel` - 3 tests
- `TestAuditLogModel` - 4 tests
- `TestSystemConfigModel` - 8 tests
- `TestEnumTypes` - 3 tests

**Total:** 30 tests

**Key Scenarios Covered:**
- Membership role properties (is_admin, is_full_admin)
- Permission properties (can_change_tenant_settings, can_approve_requests)
- Deletion rate limiting fields
- Space creation and relationships
- Decision-space many-to-many links
- Audit log JSON storage
- System configuration get/set operations
- Enum type validation

### 4. Role Request Tests (`test_role_requests.py`)

**Classes:**
- `TestRoleRequestCreation` - 7 tests
- `TestRoleRequestApproval` - 5 tests
- `TestRoleRequestRejection` - 2 tests
- `TestRoleRequestModel` - 3 tests
- `TestRoleRequestQueries` - 2 tests

**Total:** 19 tests

**Key Scenarios Covered:**
- User can request steward/admin role
- Admins cannot request roles
- Duplicate pending request prevention
- Can create new request after rejection
- Approval updates membership
- Approval creates audit log
- Only admin can approve admin requests
- Rejection includes reason
- Query pending requests

**Critical Bug Tests:**
- ✅ POST `/api/admin/role-requests` endpoint logic
- ✅ Role validation and duplicate prevention
- ✅ Permission checks for approvals

### 5. Security Tests (`test_security.py`)

**Classes:**
- `TestSanitizeHTML` - 5 tests
- `TestSanitizeString` - 5 tests
- `TestSanitizeTextField` - 3 tests
- `TestSanitizeTitle` - 3 tests
- `TestSanitizeName` - 2 tests
- `TestSanitizeEmail` - 5 tests
- `TestValidateEmail` - 4 tests
- `TestValidateDomain` - 4 tests
- `TestSanitizeRequestData` - 6 tests
- `TestCSRFProtection` - 6 tests
- `TestSecurityHeaders` - 2 tests
- `TestInputValidationEdgeCases` - 4 tests

**Total:** 49 tests

**Key Scenarios Covered:**
- HTML sanitization (XSS prevention)
- Script tag removal
- onclick handler removal
- String length enforcement
- HTML stripping for titles/names
- Email validation and sanitization
- Domain validation
- Request data schema validation
- CSRF token generation and validation
- Security headers
- Unicode and special character handling

### 6. Tenant Tests (`test_tenants.py`)

**Classes:**
- `TestTenantMaturityComputation` - 8 tests
- `TestTenantMaturityUpdate` - 2 tests
- `TestTenantHelperMethods` - 5 tests
- `TestTenantToDictMethod` - 2 tests
- `TestTenantSoftDelete` - 2 tests
- `TestTenantSettings` - 3 tests

**Total:** 22 tests

**Key Scenarios Covered:**
- Bootstrap tenant with single admin
- Mature with two admins
- Mature with admin + steward
- User threshold maturity trigger
- Age threshold maturity trigger
- Handling None thresholds (uses defaults)
- Handling None created_at
- Maturity state updates
- Helper methods (get_admin_count, etc.)
- Soft delete fields
- Tenant settings relationship

**Critical Bug Tests:**
- ✅ GET `/api/tenants/<domain>/maturity` with None thresholds
- ✅ Maturity computation edge cases
- ✅ Default value handling

## Total Test Count

**New Tests:** 172 tests across 6 new files

**Existing Tests:** ~40 tests in existing files
- test_governance.py
- test_spaces.py
- test_v15_governance_models.py

**Grand Total:** ~212 comprehensive unit tests

## Test Fixtures (conftest.py)

### Core Fixtures
- `app` - Flask test application with SQLite in-memory DB
- `session` - Database session
- `client` - HTTP test client

### User Fixtures
- `sample_user` - Regular user with USER role
- `admin_user` - User with ADMIN role
- `steward_user` - User with STEWARD role

### Tenant Fixtures
- `sample_tenant` - Tenant in BOOTSTRAP state
- `sample_tenant_with_settings` - Tenant with TenantSettings

### Membership Fixtures
- `sample_membership` - Regular user membership

### Decision Fixtures
- `sample_decision` - Sample decision record
- `sample_space` - Default space

### Client Fixtures
- `authenticated_client` - Client with user session
- `admin_client` - Client with admin session

## Running Tests

### Quick Start

```bash
# Make runner executable
chmod +x run_tests.sh

# Run all tests
./run_tests.sh

# Run with coverage
./run_tests.sh --coverage

# Run specific file
pytest tests/test_auth.py -v

# Run specific test
pytest tests/test_decisions.py::TestDecisionDeletion::test_admin_can_delete_decision -v
```

### Test Selection

```bash
# Run tests matching pattern
pytest tests/ -k 'maturity' -v

# Run only auth tests
pytest tests/test_auth.py -v

# Run only decision deletion tests
pytest tests/test_decisions.py::TestDecisionDeletion -v
```

## Critical Bug Coverage

### 1. Role Request Creation (POST /api/admin/role-requests)
- ✅ Tests validate requested role
- ✅ Tests prevent duplicate pending requests
- ✅ Tests check user already has role
- ✅ Tests audit logging with correct signature

**File:** `tests/test_role_requests.py`

### 2. Tenant Maturity Computation (GET /api/tenants/<domain>/maturity)
- ✅ Tests handle None user_threshold (uses default 5)
- ✅ Tests handle None age_days (uses default 90)
- ✅ Tests handle None created_at (uses current time)
- ✅ Tests all maturity trigger conditions

**File:** `tests/test_tenants.py`

### 3. Decision Deletion (DELETE /api/decisions/<id>)
- ✅ Tests role-based permissions (admin, steward, provisional)
- ✅ Tests provisional admin only in BOOTSTRAP
- ✅ Tests rate limiting (3 deletions in 5 minutes)
- ✅ Tests soft delete with 30-day retention
- ✅ Tests audit logging

**File:** `tests/test_decisions.py`

### 4. Governance log_admin_action Function
- ✅ Tests correct parameter signature (actor_user_id)
- ✅ Tests audit log creation
- ✅ Tests setting change logging

**Files:** `tests/test_governance.py`, `tests/test_models.py`

## Test Database

All tests use an **in-memory SQLite database** that is:
- Created fresh for each test session
- Isolated from production
- Fast and disposable
- Automatically cleaned up

The schema is created from SQLAlchemy models, ensuring tests run against the current schema.

## Code Quality

### Test Organization
- Tests grouped by functionality (auth, decisions, models, etc.)
- Related tests organized into classes
- Descriptive test names following pytest conventions
- Comprehensive docstrings

### Test Coverage
- Success cases ✓
- Error cases ✓
- Edge cases ✓
- Permission checks ✓
- Null/None handling ✓
- Maximum length validation ✓
- XSS prevention ✓

### Best Practices
- DRY principle with fixtures
- Isolated tests (no dependencies between tests)
- Clear assertions
- Minimal setup per test
- Fast execution (in-memory DB)

## Integration with CI/CD

Tests are designed for CI/CD integration:

```bash
# CI command
FLASK_ENV=testing pytest tests/ --cov=. --cov-report=xml --cov-report=term

# Ensures:
# - SQLite in-memory DB is used
# - Rate limiting is disabled
# - Test configurations applied
# - Coverage report generated
```

## Next Steps

### Recommended Additions

1. **API Integration Tests**
   - Full HTTP request/response tests
   - Authentication flow tests
   - Error response validation

2. **Performance Tests**
   - Query performance benchmarks
   - Rate limiting behavior under load

3. **Migration Tests**
   - Database migration validation
   - Rollback testing

4. **Fixture Factories**
   - Factory pattern for test data generation
   - Randomized test data for edge cases

### Maintenance

- Update tests when adding new features
- Add regression tests for bugs
- Keep test coverage above 80%
- Review and refactor slow tests

## Documentation

- **README.md** - Comprehensive testing guide
- **TEST_SUMMARY.md** - This summary document
- **run_tests.sh** - Automated test runner
- **Inline docstrings** - Each test has descriptive docstring

## Conclusion

The test suite provides comprehensive coverage of:
- ✅ Authentication and authorization
- ✅ Decision CRUD operations
- ✅ Governance model logic
- ✅ Role-based permissions
- ✅ Input sanitization and security
- ✅ Database models and relationships
- ✅ Tenant maturity computation
- ✅ Rate limiting
- ✅ Soft delete functionality

All critical bugs identified in recent development have corresponding tests to prevent regressions.
