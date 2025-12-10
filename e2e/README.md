# E2E Test Plan - v1.5 Governance

This document serves as the comprehensive test plan for Playwright E2E tests.
It can be referenced after context compaction to continue implementation.

## Test Infrastructure

### Setup
- **Framework**: Playwright with TypeScript
- **Location**: `/e2e/` directory at project root
- **Backend**: Flask app on `localhost:5001`
- **Frontend**: Angular app on `localhost:4200`

### Test Database
Tests use an isolated SQLite database to avoid affecting real data.
Each test suite resets the database via API calls.

### Test Users (Created via API)
| Email | Role | Purpose |
|-------|------|---------|
| `superadmin` (master account) | Super Admin | System-wide admin access |
| `admin@test-org.com` | Admin | Full admin of test-org |
| `provisional@new-org.com` | Provisional Admin | First/only admin of new-org |
| `steward@test-org.com` | Steward | Shared governance role |
| `user@test-org.com` | User | Regular user |

---

## Test Categories

### 1. Authentication Tests (`auth.spec.ts`)
| Test | Description | Priority |
|------|-------------|----------|
| `super-admin-login` | Master account can login with username/password | High |
| `tenant-user-passkey-login` | Tenant user can login with passkey | High |
| `tenant-user-password-login` | Tenant user can login with password | High |
| `logout` | User can logout and session is cleared | High |
| `unauthorized-redirect` | Unauthenticated users redirect to login | High |

### 2. Governance Tests (`governance.spec.ts`)
| Test | Description | Priority |
|------|-------------|----------|
| `provisional-admin-sees-banner` | Provisional admin sees "Some settings are restricted" banner | High |
| `provisional-admin-cannot-disable-registration` | Allow registration toggle disabled for provisional admin | High |
| `provisional-admin-cannot-require-approval` | Auto-approve toggle disabled for provisional admin | High |
| `full-admin-no-restrictions` | Full admin sees no banner, all controls enabled | High |
| `adding-steward-upgrades-provisional` | After adding steward, provisional becomes full admin | High |
| `adding-second-admin-upgrades-provisional` | After adding 2nd admin, provisional becomes full admin | High |
| `role-badges-display-correctly` | User list shows correct role badges (Admin, Steward, User) | Medium |

### 3. Super Admin Tests (`superadmin.spec.ts`)
| Test | Description | Priority |
|------|-------------|----------|
| `view-all-tenants` | Super admin can see list of all tenants | High |
| `view-tenant-maturity-state` | Tenant list shows BOOTSTRAP/MATURE state | High |
| `configure-maturity-thresholds` | Can adjust age_days, user_threshold, admin_threshold | Medium |
| `force-maturity-upgrade` | Can manually set tenant to MATURE | Medium |
| `view-tenant-users` | Can see users in any tenant | Medium |

### 4. Space Tests (`spaces.spec.ts`)
| Test | Description | Priority |
|------|-------------|----------|
| `default-space-exists` | Every tenant has a "General" default space | High |
| `cannot-delete-default-space` | Delete button disabled or error shown | High |
| `admin-can-create-space` | Admin can create a new space | High |
| `steward-can-create-space` | Steward can create a new space | Medium |
| `user-cannot-create-space` | Regular user sees no create button | Medium |
| `delete-space-preserves-decisions` | Deleting space doesn't delete decisions | High |

### 5. Decision Tests (`decisions.spec.ts`)
| Test | Description | Priority |
|------|-------------|----------|
| `create-decision` | User can create a new decision | High |
| `edit-decision` | User can edit their decision | High |
| `view-decision-history` | History shows previous versions | Medium |
| `decision-belongs-to-tenant` | Decisions scoped to user's tenant | High |

---

## Test Fixtures

### Database Reset Fixture
```typescript
// e2e/fixtures/database.ts
export async function resetTestDatabase(request: APIRequestContext) {
  await request.post('http://localhost:5001/api/test/reset-database');
}
```

### User Creation Fixture
```typescript
// e2e/fixtures/users.ts
export async function createTestUser(
  request: APIRequestContext,
  email: string,
  password: string,
  role: 'user' | 'admin' | 'steward' | 'provisional_admin'
) {
  return request.post('http://localhost:5001/api/test/create-user', {
    data: { email, password, role }
  });
}
```

### Login Helper
```typescript
// e2e/fixtures/auth.ts
export async function loginAsUser(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.fill('[data-testid="email-input"]', email);
  await page.fill('[data-testid="password-input"]', password);
  await page.click('[data-testid="login-button"]');
  await page.waitForURL('**/decisions');
}

export async function loginAsSuperAdmin(page: Page) {
  await page.goto('/superadmin/login');
  await page.fill('[data-testid="username-input"]', 'admin');
  await page.fill('[data-testid="password-input"]', process.env.MASTER_PASSWORD);
  await page.click('[data-testid="login-button"]');
  await page.waitForURL('**/superadmin/**');
}
```

---

## Implementation Order

### Phase 1: Infrastructure (Priority: CRITICAL)
1. Install Playwright: `npm init playwright@latest`
2. Create test database reset API endpoint
3. Create test user creation API endpoint
4. Set up fixtures and helpers
5. Add `data-testid` attributes to key UI elements

### Phase 2: Core Auth Tests
1. `auth.spec.ts` - All authentication flows

### Phase 3: Governance Tests (Priority: HIGH)
1. `governance.spec.ts` - Provisional admin restrictions
2. Add `data-testid` to settings component elements

### Phase 4: Super Admin Tests
1. `superadmin.spec.ts` - Tenant management

### Phase 5: Feature Tests
1. `spaces.spec.ts` - Space CRUD
2. `decisions.spec.ts` - Decision CRUD

---

## Required API Endpoints for Testing

These endpoints are ONLY available when `FLASK_ENV=testing`:

```python
# In app.py, add these test-only routes
@app.route('/api/test/reset-database', methods=['POST'])
def reset_test_database():
    """Reset database to clean state. TEST ONLY."""
    if os.environ.get('FLASK_ENV') != 'testing':
        return jsonify({'error': 'Not available'}), 403
    # Drop and recreate all tables
    # Create default super admin
    return jsonify({'message': 'Database reset'})

@app.route('/api/test/create-user', methods=['POST'])
def create_test_user():
    """Create a user with specified role. TEST ONLY."""
    if os.environ.get('FLASK_ENV') != 'testing':
        return jsonify({'error': 'Not available'}), 403
    data = request.get_json()
    # Create user, tenant, membership with specified role
    return jsonify({'user': user.to_dict()})

@app.route('/api/test/set-tenant-maturity', methods=['POST'])
def set_tenant_maturity():
    """Set tenant maturity state. TEST ONLY."""
    if os.environ.get('FLASK_ENV') != 'testing':
        return jsonify({'error': 'Not available'}), 403
    # Set tenant.maturity_state directly
    return jsonify({'tenant': tenant.to_dict()})
```

---

## Data-TestId Attributes Needed

### Login Pages
- `data-testid="email-input"`
- `data-testid="password-input"`
- `data-testid="login-button"`
- `data-testid="username-input"` (superadmin)

### Settings Page
- `data-testid="provisional-admin-banner"`
- `data-testid="allow-registration-toggle"`
- `data-testid="auto-approve-toggle"`
- `data-testid="registration-lock-icon"`
- `data-testid="approval-lock-icon"`
- `data-testid="user-row-{userId}"`
- `data-testid="role-badge-{role}"`

### Spaces
- `data-testid="create-space-button"`
- `data-testid="space-list"`
- `data-testid="space-item-{spaceId}"`
- `data-testid="delete-space-button-{spaceId}"`

---

## Running Tests

```bash
# Run all tests
npx playwright test

# Run specific file
npx playwright test e2e/governance.spec.ts

# Run with UI
npx playwright test --ui

# Run headed (see browser)
npx playwright test --headed

# Debug mode
npx playwright test --debug
```

---

## CI/CD Integration

```yaml
# .github/workflows/e2e.yml
name: E2E Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - name: Install dependencies
        run: npm ci
      - name: Install Playwright
        run: npx playwright install --with-deps
      - name: Start backend
        run: |
          cd .. && python -m venv .venv && source .venv/bin/activate
          pip install -r requirements.txt
          FLASK_ENV=testing python app.py &
      - name: Start frontend
        run: npm run start &
      - name: Run tests
        run: npx playwright test
```

---

*Last Updated: December 10, 2025*
