# Claude Code Instructions
DO NOT add Claude code branding in commit messages.
Always ask approval before deploying to production.
Always run the redeploy script with required parameters.
When you add features, add UI tests for them too.
Make use of Claude code sub agents to write and run tests.

This file contains instructions and context for Claude Code when working on this project.

## Project Overview

Architecture Decisions is a multi-tenant web application for managing Architecture Decision Records (ADRs) based on the arc42 format.

- **Production URL**: https://decisionrecords.org
- **Backend**: Python/Flask with SQLAlchemy
- **Frontend**: Angular 18 with Material UI
- **Auth**: WebAuthn/Passkeys, OIDC SSO, local auth
- **Deployment**: Docker → Azure Container Instances
- **CDN/SSL**: Cloudflare (Free plan) with Origin Server certificates
- **Decision Repository**: This project uses its own platform via MCP integration

## Open Core Architecture

This project follows an **Open Core** model with a monorepo structure:
- **Community Edition** (BSL 1.1 License): Core ADR functionality, open source
- **Enterprise Edition** (Proprietary): Commercial features in `ee/` directory

### Edition Selection

The edition is controlled by the `DECISION_RECORDS_EDITION` environment variable:

```bash
# Community Edition (default for self-hosting)
DECISION_RECORDS_EDITION=community

# Enterprise Edition (production decisionrecords.org)
DECISION_RECORDS_EDITION=enterprise
```

### Feature Availability by Edition

| Feature | Community | Enterprise |
|---------|-----------|------------|
| Architecture Decisions (CRUD) | ✅ | ✅ |
| Multi-Tenancy | ✅ | ✅ |
| WebAuthn/Passkeys | ✅ | ✅ |
| Generic OIDC SSO | ✅ | ✅ |
| Spaces (Visibility Control) | ✅ | ✅ |
| Governance Model | ✅ | ✅ |
| Audit Logging | ✅ | ✅ |
| Slack Integration | ❌ | ✅ |
| Microsoft Teams | ❌ | ✅ |
| AI Features (MCP Server) | ❌ | ✅ |
| Google OAuth | ❌ | ✅ |
| PostHog Analytics | ❌ | ✅ |
| Azure Key Vault | ❌ | ✅ |

### Directory Structure

```
architecture-decisions/
├── app.py                    # Main Flask app (core routes)
├── models.py                 # SQLAlchemy models (shared)
├── feature_flags.py          # Edition-based feature detection
├── security.py               # Core security (CSRF, sanitization)
├── requirements.txt          # Core dependencies only
├── frontend/                 # Angular frontend (shared)
│   └── src/app/
│       ├── components/       # Core UI components
│       └── services/         # Core services
├── tests/                    # All tests (EE tests skip if unavailable)
├── ee/                       # Enterprise Edition (proprietary)
│   ├── LICENSE               # Proprietary license
│   ├── requirements.txt      # Additional EE dependencies
│   ├── backend/              # Python EE modules
│   │   ├── ai/               # AI/LLM integration
│   │   ├── slack/            # Slack integration
│   │   ├── teams/            # Teams integration
│   │   ├── analytics/        # PostHog integration
│   │   ├── azure/            # Azure Key Vault
│   │   ├── cloudflare/       # Cloudflare security
│   │   └── oauth_providers/  # Google OAuth
│   ├── frontend/             # Angular EE components
│   │   ├── components/       # EE-specific components
│   │   └── pages/            # EE-specific pages
│   └── infra/                # Azure ARM templates
├── deployment/
│   └── Dockerfile.production # Enterprise Edition build
├── Dockerfile.community      # Community Edition build
├── docker-compose.yml        # Self-hosting compose file
└── docs/
    └── self-hosting.md       # Self-hosting guide
```

### How Code is Loaded

**Backend (app.py)**:
```python
from feature_flags import is_enterprise

# EE modules are conditionally imported
if is_enterprise():
    from ee.backend.slack.slack_service import SlackService
    from ee.backend.teams.teams_service import TeamsService
    from ee.backend.ai import AIConfig
    # Register EE routes...
```

**Frontend**:
- Core components are in `frontend/src/app/components/`
- EE components are in `ee/frontend/components/` (loaded conditionally)
- Feature flags service fetches `/api/features` to determine edition

## Architecture Decision Records (ADRs)

This project uses the Decision Records platform to document architecture decisions. Claude Code has access to the `decision-records` MCP server to search, read, and create decisions.

### When to Create an Architecture Decision

**CREATE a decision record when:**
- Choosing between multiple valid technical approaches
- Introducing new dependencies, frameworks, or external services
- Changing API contracts or database schemas (especially breaking changes)
- Establishing patterns that will be followed project-wide
- Making security or authentication design choices
- Defining integration approaches with external systems (Slack, Teams, MCP, etc.)
- Making infrastructure or deployment architecture decisions
- Deprecating or replacing existing architectural components

**DO NOT create a decision record for:**
- Bug fixes (unless they reveal a design flaw requiring architectural change)
- Simple feature additions that follow established patterns
- Code refactoring that doesn't change the architecture
- Documentation updates
- Configuration changes
- Minor dependency version updates

### How to Create Decisions

Use the MCP tools to interact with the decision repository:

```bash
# Search existing decisions before creating new ones
mcp__decision-records__search_decisions(query="authentication")

# List recent decisions
mcp__decision-records__list_decisions(limit=10)

# Get full details of a decision
mcp__decision-records__get_decision(id="ADR-003")

# Create a new decision
mcp__decision-records__create_decision(
  title="Short descriptive title",
  context="Why this decision is needed, what forces are at play",
  decision="What we decided and why",
  consequences="Positive, negative, and neutral impacts",
  status="proposed"  # or "accepted" if already implemented
)
```

### Decision Format (arc42)

Decisions follow the arc42 ADR format:

1. **Title**: Short, descriptive (e.g., "Use PostgreSQL for persistent storage")
2. **Context**: Background, problem statement, decision drivers
3. **Decision**: What was decided, implementation details, criteria
4. **Consequences**: Positive, negative, and neutral impacts
5. **Status**: `proposed`, `accepted`, `deprecated`, or `superseded`

### Before Making Architectural Changes

1. **Search existing decisions** to understand prior context
2. **Check if a similar decision exists** that should be updated or superseded
3. **Create a new decision** if making a significant architectural choice
4. **Reference the decision** in commit messages when implementing (e.g., "Implements ADR-003")

## Critical Deployment Rules

### ALWAYS Commit Before Deploying

**NEVER deploy directly to Azure without first committing changes to git.**

The deployment workflow is:

1. Make code changes
2. Test locally if possible
3. **Commit changes to git** (this updates the version build date via pre-commit hook)
4. Build Docker image
5. Push to Azure Container Registry
6. Restart container

```bash
# Correct workflow - use the redeploy script
git add .
git commit -m "Description of changes"
./scripts/version-bump.sh patch  # Optional: if releasing new version
./scripts/redeploy.sh  # Builds, pushes, and redeploys container
```

The `redeploy.sh` script handles the full deployment:
1. Checks for uncommitted changes (fails if any)
2. Builds Docker image for linux/amd64
3. Pushes to Azure Container Registry
4. Stops and starts the container (forces new image pull)
5. Waits for container to be ready
6. Updates Application Gateway backend if IP changed
7. Shows recent logs

**Manual steps (if needed)**:
```bash
docker build --platform linux/amd64 -t adrregistry2024eu.azurecr.io/architecture-decisions:latest -f deployment/Dockerfile.production .
az acr login --name adrregistry2024eu
docker push adrregistry2024eu.azurecr.io/architecture-decisions:latest
az container stop --name adr-app-eu --resource-group adr-resources-eu
az container start --name adr-app-eu --resource-group adr-resources-eu
./scripts/update-gateway-backend.sh
```

### Reasoning

1. **Version tracking**: The pre-commit hook updates `version.py` with the build date
2. **Audit trail**: Git commits provide history of what was deployed
3. **Rollback capability**: Can revert to previous commit if deployment fails
4. **CI/CD alignment**: Matches production CI/CD pipeline behavior

## Version Management

### Version File

The version is managed in `version.py`:
- `__version__`: Semantic version (MAJOR.MINOR.PATCH)
- `__build_date__`: Auto-updated by pre-commit hook

### Version Bumping

Use the version bump script for releases:

```bash
./scripts/version-bump.sh patch  # Bug fixes: 1.0.0 -> 1.0.1
./scripts/version-bump.sh minor  # New features: 1.0.0 -> 1.1.0
./scripts/version-bump.sh major  # Breaking changes: 1.0.0 -> 2.0.0
```

### Version Display

The version is displayed in:
- UI footer (fetched from `/api/version`)
- Container logs on startup
- Health check endpoint

## Database Migration Guidelines

### CRITICAL: When Adding New Database Columns or Tables

**When modifying SQLAlchemy models that affect existing database tables, you MUST:**

1. **Update the model** in `models.py` with the new column/table definition
2. **Create a migration script** in `scripts/migrate_to_vXXX.py` to add the column/table to existing databases
3. **Verify fresh initialization** works by testing with a new database (SQLAlchemy's `db.create_all()` handles this)
4. **Run the migration** on production before deploying new code that uses the column

### Why This Matters

- **Fresh databases**: `db.create_all()` in `app.py` creates all tables/columns from model definitions - no migration needed
- **Existing databases**: Production databases need explicit ALTER TABLE statements to add new columns
- **Deployment order**: If you deploy code that queries a column that doesn't exist, you get 500 errors

### Migration Script Pattern

Migration scripts should be:
- **Idempotent**: Can be run multiple times safely (check if column/table exists before adding)
- **Named by version**: `migrate_to_v113.py` for version 1.13.0
- **Support dry-run**: `--dry-run` flag to preview changes without making them

Example structure:
```python
def column_exists(cur, table_name, column_name):
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s AND column_name = %s
        )
    """, (table_name, column_name))
    return cur.fetchone()[0]

def add_new_column(cur, dry_run=False):
    if column_exists(cur, 'tenants', 'new_column'):
        print("  Column already exists")
        return 0
    if dry_run:
        print("  [DRY-RUN] Would add column")
        return 0
    cur.execute("ALTER TABLE tenants ADD COLUMN new_column BOOLEAN DEFAULT FALSE")
    return 1
```

### Running Migrations

```bash
# Preview changes (dry-run)
DATABASE_URL="postgresql://..." python scripts/migrate_to_v113.py --dry-run --verbose

# Apply changes
DATABASE_URL="postgresql://..." python scripts/migrate_to_v113.py --verbose
```

### Existing Migration Scripts

| Script | Purpose |
|--------|---------|
| `scripts/migrate_to_v15.py` | v1.5 Governance model (tenants, memberships) |
| `scripts/migrate_to_v113.py` | v1.13 AI, Slack, Teams, Blog features |

### Common New Column Scenarios

| Change Type | Model Update | Migration Needed |
|-------------|--------------|------------------|
| New column on existing table | Add to model class | Yes - ALTER TABLE |
| New table | Add new model class | Yes - CREATE TABLE |
| Column with default | Add with `default=` | Yes - with DEFAULT clause |
| Nullable column | Add with `nullable=True` | Yes - no NOT NULL |
| New enum type | Add enum to models | Yes - CREATE TYPE before table |

## Secrets Management

All secrets are stored in Azure Key Vault (`adr-keyvault-eu`):

| Secret | Purpose |
|--------|---------|
| `flask-secret-key` | Flask session signing |
| `smtp-username` | Email SMTP auth |
| `smtp-password` | Email SMTP auth |

The application uses a fallback chain:
1. Azure Key Vault (production)
2. Environment variables (container config)
3. Default values (development only)

### Adding New Secrets

```bash
az keyvault secret set \
  --vault-name adr-keyvault-eu \
  --name "secret-name" \
  --value "secret-value"
```

## Azure Resources

| Resource | Name | Purpose |
|----------|------|---------|
| Resource Group | `adr-resources-eu` | Contains all resources |
| Container Registry | `adrregistry2024eu` | Docker images |
| Container Instance | `adr-app-eu` | Running application |
| Key Vault | `adr-keyvault-eu` | Secrets management |
| PostgreSQL | `adr-postgres-eu` | Database |
| App Gateway | `adr-appgateway` | Load balancer + SSL termination |
| Private DNS | `adr.internal` | Internal DNS for container IP |

## Domain & SSL Configuration

- **Domain**: decisionrecords.org
- **DNS Provider**: Cloudflare (Free plan)
- **SSL Mode**: Full (strict) - Cloudflare validates Origin certificate
- **Origin Certificate**: Cloudflare Origin Server certificate installed on App Gateway
- **Certificate Files**: `~/.ssh/decisionrecords.pem` (cert) and `~/.ssh/decisionrecords.key` (private key)

## Common Tasks

### Check Container Status

```bash
az container show --name adr-app-eu --resource-group adr-resources-eu --query "instanceView.state" -o tsv
```

### View Container Logs

```bash
az container logs --name adr-app-eu --resource-group adr-resources-eu
```

### Check Database

```bash
python3 -c "
import psycopg2
conn = psycopg2.connect('postgresql://adruser:PASSWORD@adr-postgres-eu.postgres.database.azure.com:5432/postgres?sslmode=require')
cursor = conn.cursor()
cursor.execute('SELECT tablename FROM pg_tables WHERE schemaname = \"public\";')
print([row[0] for row in cursor.fetchall()])
"
```

## Local Development

### Running the Backend Locally

In production, the app runs behind Cloudflare which provides security controls. For local development, you need to disable these checks.

#### Option 1: Use run_local.py (Recommended)

```bash
source .venv/bin/activate

# Run Enterprise Edition (all features - default)
python run_local.py

# Run Community Edition (core features only)
python run_local.py --community
```

This script automatically sets all required environment variables including `DECISION_RECORDS_EDITION`.

#### Option 2: Manual with Environment Variables

```bash
source .venv/bin/activate && \
DATABASE_URL="sqlite:////$(pwd)/instance/architecture_decisions.db" \
SECRET_KEY="local-dev-secret-key-12345" \
SKIP_CLOUDFLARE_CHECK="true" \
ENVIRONMENT="development" \
DEBUG="true" \
FLASK_DEBUG=1 \
flask run --host=0.0.0.0 --port=5001
```

**Note**: The DATABASE_URL requires 4 slashes for absolute paths (`sqlite:////absolute/path`).

#### Required Environment Variables for Local Dev

| Variable | Value | Purpose |
|----------|-------|---------|
| `SKIP_CLOUDFLARE_CHECK` | `true` | Disables Cloudflare origin IP validation |
| `DATABASE_URL` | `sqlite:////absolute/path/to/instance/architecture_decisions.db` | Use local SQLite (4 slashes for absolute path) |
| `SECRET_KEY` | Any string | Flask session signing (use any value locally) |
| `ENVIRONMENT` | `development` | Enables development mode |
| `DEBUG` | `true` | Enables debug logging |

#### Default Master Account

- **Username**: `admin`
- **Password**: `changeme`

#### Common Error: "Direct access not allowed"

If you see "Direct access not allowed. Please use decisionrecords.org", it means `SKIP_CLOUDFLARE_CHECK` is not set to `true`. The Cloudflare security middleware blocks direct access in production mode.

### Running Frontend + Backend Together

**IMPORTANT**: For login/session cookies to work, you MUST access the app through the Angular dev server (port 4200), not directly on the backend (port 5001). The Angular proxy handles routing API calls while maintaining the same-origin policy for cookies.

1. **Terminal 1 - Backend** (port 5001):
   ```bash
   source .venv/bin/activate && \
   DATABASE_URL="sqlite:////$(pwd)/instance/architecture_decisions.db" \
   SECRET_KEY="local-dev-secret-key-12345" \
   SKIP_CLOUDFLARE_CHECK="true" \
   ENVIRONMENT="development" \
   flask run --host=0.0.0.0 --port=5001
   ```

2. **Terminal 2 - Frontend** (port 4200):
   ```bash
   cd frontend
   npm start
   ```

3. **Access the app at `http://localhost:4200`** (NOT port 5001!)
   - Superadmin login: `http://localhost:4200/superadmin`
   - Regular login: `http://localhost:4200/login`

The Angular dev server proxies `/api` and `/auth` calls to the Flask backend via `proxy.conf.json`. This makes everything appear same-origin to the browser, so session cookies work correctly.

## File Structure

### Core Files (Community Edition)

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application with all API routes |
| `models.py` | SQLAlchemy database models |
| `version.py` | Version information |
| `feature_flags.py` | Edition detection and feature flags |
| `security.py` | Security helpers (CSRF, sanitization) |
| `requirements.txt` | Core Python dependencies |
| `frontend/src/app/` | Angular components and services |
| `Dockerfile.community` | Community Edition Docker build |
| `docker-compose.yml` | Self-hosting compose file |

### Enterprise Edition Files (`ee/`)

| File | Purpose |
|------|---------|
| `ee/backend/ai/` | AI/LLM integration (MCP server) |
| `ee/backend/slack/` | Slack integration (OAuth, commands) |
| `ee/backend/teams/` | Microsoft Teams integration |
| `ee/backend/analytics/` | PostHog analytics |
| `ee/backend/azure/keyvault_client.py` | Azure Key Vault integration |
| `ee/backend/cloudflare/` | Cloudflare security middleware |
| `ee/backend/oauth_providers/` | Google OAuth provider |
| `ee/frontend/components/` | EE Angular components |
| `ee/infra/` | Azure ARM templates |
| `ee/requirements.txt` | EE Python dependencies |
| `deployment/Dockerfile.production` | Enterprise Edition Docker build |

## Testing Requirements

**MANDATORY: Always write tests when adding or modifying code.**

### Test Suite Overview

| Test Type | Location | Command | Count |
|-----------|----------|---------|-------|
| Backend Unit Tests | `tests/` | `.venv/bin/python -m pytest tests/` | 265+ |
| E2E Tests | `e2e/tests/` | `npx playwright test` | 40+ |
| Integration Tests | `tests/test_api_integration.py` | `.venv/bin/python -m pytest tests/test_api_integration.py` | 30 |

### When to Write Tests

**Backend Changes (app.py, models.py, auth.py, etc.):**
1. Add unit tests in `tests/test_*.py` for new functions/methods
2. Add integration tests in `tests/test_api_integration.py` for new API endpoints
3. Test both success AND error cases
4. Test edge cases (null values, empty strings, missing fields)

**Frontend Changes (Angular components):**
1. Add E2E tests in `e2e/tests/*.spec.ts` for new UI features
2. Test the user flow end-to-end through the browser
3. Use existing patterns from `e2e/fixtures/auth.ts`

**API Contract Changes:**
1. Update both backend unit tests AND frontend E2E tests
2. Verify request/response formats match on both sides

### Test File Mapping

| Code Area | Test File |
|-----------|-----------|
| Authentication | `tests/test_auth.py` |
| Tenant management | `tests/test_tenants.py` |
| Decisions CRUD | `tests/test_decisions.py` |
| Role requests | `tests/test_role_requests.py` |
| Security/sanitization | `tests/test_security.py` |
| API endpoints | `tests/test_api_integration.py` |
| Super admin UI | `e2e/tests/superadmin-tenants.spec.ts` |
| Decisions UI | `e2e/tests/decisions.spec.ts` |
| Spaces UI | `e2e/tests/spaces.spec.ts` |

### Running Tests

```bash
# Run all backend tests (Enterprise Edition - includes EE tests)
DECISION_RECORDS_EDITION=enterprise .venv/bin/python -m pytest tests/ -v

# Run only Community Edition tests (skips EE tests)
DECISION_RECORDS_EDITION=community .venv/bin/python -m pytest tests/ -v

# Run specific test file
.venv/bin/python -m pytest tests/test_auth.py -v

# Run E2E tests (requires frontend running)
cd frontend && npm run build && cd ..
npx playwright test

# Run specific E2E test
npx playwright test e2e/tests/decisions.spec.ts
```

### Test Organization

Tests are organized by feature area. Enterprise Edition tests automatically skip when EE modules are not available:

| Test File | Edition | Purpose |
|-----------|---------|---------|
| `tests/test_auth.py` | Core | Authentication tests |
| `tests/test_decisions.py` | Core | Decision CRUD tests |
| `tests/test_tenants.py` | Core | Multi-tenancy tests |
| `tests/test_slack.py` | **EE** | Slack integration tests |
| `tests/test_teams.py` | **EE** | Teams integration tests |
| `tests/test_ai.py` | **EE** | AI/MCP tests |
| `tests/test_google_oauth.py` | **EE** | Google OAuth tests |

**EE tests use `pytest.mark.skipif`** to automatically skip when `ee/` modules are unavailable.

### Test Patterns to Follow

**Backend Unit Tests:**
```python
class TestFeatureName:
    def test_success_case(self, app, session, sample_user):
        """Description of what it tests."""
        # Arrange
        # Act
        # Assert

    def test_error_case_returns_appropriate_error(self, app, session):
        """Tests error handling."""
        # Test with invalid input, expect specific error

    def test_handles_null_values(self, app, session):
        """Tests null/None handling."""
        # Test with None values to prevent 500 errors
```

**E2E Tests:**
```typescript
test.describe('Feature Name', () => {
  test('can-do-action: Description of what it tests', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/relevant-page');
    // Perform action
    // Assert result
  });
});
```

### Before Deploying

1. **Run backend tests**: `.venv/bin/python -m pytest tests/ -v`
2. **Build frontend**: `cd frontend && npm run build`
3. **Verify app imports**: `python -c "import app"`
4. **Run E2E tests** (optional but recommended): `npx playwright test`

## API Integration Guidelines

When creating new frontend components that call backend APIs, **always follow these rules** to avoid mismatches:

### Before Writing Frontend Code

1. **Read the backend route first** - Check `app.py` for the exact:
   - URL path (e.g., `/api/webauthn/register/verify` not `/complete`)
   - Expected request body structure (what `request.get_json()` parses)
   - Response format (what `jsonify()` returns)

2. **Check existing similar code** - Look for existing services/components that call similar endpoints:
   - `webauthn.service.ts` for WebAuthn patterns
   - `auth.service.ts` for authentication patterns
   - `admin.service.ts` for admin API patterns

### API Contract Checklist

Before implementing any API call, verify:

- [ ] **Endpoint URL** matches backend `@app.route()` exactly
- [ ] **HTTP method** matches (GET, POST, PUT, DELETE)
- [ ] **Request body structure** matches backend parsing:
  ```python
  # If backend does:
  credential = data.get('credential')
  # Frontend must send:
  { credential: {...}, other_field: ... }
  ```
- [ ] **Response handling** matches backend return:
  ```python
  # If backend returns:
  return jsonify({'message': 'Success', 'user': user_data})
  # Frontend must check:
  if (result.user || result.message === 'Success')
  # NOT: if (result.success)
  ```

### Standard Response Patterns

This project uses these response patterns:

| Endpoint Type | Success Response | Error Response |
|---------------|------------------|----------------|
| Create/Register | `{ message: '...', entity: {...} }` | `{ error: '...' }, 400` |
| Authenticate | `{ message: '...', user: {...} }` | `{ error: '...' }, 401` |
| List | `[{...}, {...}]` | `{ error: '...' }, 500` |
| Delete | `{ message: '...' }` | `{ error: '...' }, 404` |

### Common Mistakes to Avoid

1. **Don't assume `success: true`** - Backend may return `message` or entity directly
2. **Don't flatten nested structures** - If backend expects `{ credential: {...} }`, don't send flat
3. **Don't guess endpoint names** - Always verify against `app.py`
4. **Don't skip error response handling** - Backend errors use `{ error: '...' }` format

## Analytics & Error Capture Guidelines (Enterprise Edition)

Analytics and error tracking are **Enterprise Edition features**. These are only available when running with `DECISION_RECORDS_EDITION=enterprise`.

### Adding Analytics to New Endpoints

All API endpoints should be instrumented with analytics tracking:

```python
# Only in Enterprise Edition
from feature_flags import is_enterprise
if is_enterprise():
    from ee.backend.analytics.analytics import track_endpoint

@app.route('/api/my-endpoint', methods=['GET'])
@login_required
@track_endpoint('api_my_endpoint')  # Add after auth decorators (EE only)
def my_endpoint():
    ...
```

When adding new endpoints:
1. Add the `@track_endpoint('endpoint_name')` decorator after authentication decorators
2. Use a descriptive endpoint name following the pattern: `api_<resource>_<action>`
3. Register the endpoint in `ee/backend/analytics/analytics.py` in the appropriate category

### Handling Errors with Exception Capture

For operations that might fail unexpectedly, capture exceptions:

```python
from feature_flags import is_enterprise
if is_enterprise():
    from ee.backend.analytics.analytics import capture_exception

try:
    risky_external_call()
except Exception as e:
    logger.error(f"External call failed: {e}")
    if is_enterprise():
        capture_exception(e, endpoint_name='external_integration')
    return jsonify({'error': 'Service temporarily unavailable'}), 503
```

Guidelines for exception capture:
1. **Always log first**: Use `logger.error()` before calling `capture_exception()`
2. **Never expose internals**: Return generic error messages to users
3. **Include context**: Pass the `endpoint_name` to help identify where errors occur
4. **Don't capture expected errors**: Only capture unexpected/bug-type exceptions

### What NOT to Capture

Do not capture these as exceptions (they're expected behavior):
- 400 Bad Request (client validation errors)
- 401 Unauthorized (auth working correctly)
- 403 Forbidden (authorization working correctly)
- 404 Not Found (normal behavior)

### Flask Error Handling Best Practices

Global error handlers in `app.py` already capture unhandled exceptions automatically:

```python
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    capture_exception(e, endpoint_name='unhandled_exception')
    return jsonify({'error': 'An internal server error occurred'}), 500
```

For route-specific error handling:
1. Log the error with details
2. Capture to PostHog if it's unexpected
3. Return a user-friendly error message
4. Use appropriate HTTP status codes

## Python/Flask Coding Guidelines

Follow these patterns to avoid deprecation warnings and ensure forward compatibility.

### DateTime Handling (Python 3.12+)

**NEVER use `datetime.utcnow()`** - it's deprecated in Python 3.12+.

```python
# ❌ WRONG - deprecated
from datetime import datetime
created_at = datetime.utcnow()

# ✅ CORRECT - use timezone-aware datetime
from datetime import datetime, timezone
created_at = datetime.now(timezone.utc)
```

For SQLAlchemy model columns with datetime defaults, use lambda functions:

```python
# ❌ WRONG - deprecated
created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ✅ CORRECT - use lambda for timezone-aware default
created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
```

### SQLAlchemy 2.0 Patterns

**NEVER use `Model.query.get(id)`** - it's a legacy pattern deprecated in SQLAlchemy 2.0.

```python
# ❌ WRONG - legacy pattern
user = User.query.get(user_id)
decision = ArchitectureDecision.query.get(decision_id)

# ✅ CORRECT - use session.get()
user = db.session.get(User, user_id)
decision = db.session.get(ArchitectureDecision, decision_id)
```

### Import Patterns

Always import `timezone` when working with datetime:

```python
from datetime import datetime, timedelta, timezone
```

Always import `db` when using `db.session.get()`:

```python
from models import db, User, Tenant
```

## Troubleshooting

### Login Issues

- Check if SECRET_KEY is loaded from Key Vault
- Verify session cookies are being set (check browser dev tools)
- Look for auth errors in container logs

### Styling Issues

- Clear browser cache (hard refresh)
- Check for CSP errors in browser console
- Verify Angular build completed without errors

### Database Issues

- Check DATABASE_URL environment variable
- Verify PostgreSQL is accessible from container VNet
- Check for migration errors in logs

### 502 Gateway Errors

If you get 502 errors after container restart, the container's private IP may have changed:

```bash
# Check backend health
az network application-gateway show-backend-health \
  --name adr-appgateway \
  --resource-group adr-resources-eu \
  --query "backendAddressPools[0].backendHttpSettingsCollection[0].servers[0]"

# If unhealthy, run the update script
./scripts/update-gateway-backend.sh
```

The container IP can change on restart because Azure Container Instances in VNets don't support static private IPs.

## Developing New Features

### Where to Put Code

**Community Edition (Core) Features** - Goes in main directories:
- Backend: `app.py`, `models.py`, `security.py`
- Frontend: `frontend/src/app/components/`
- Tests: `tests/test_*.py`

**Enterprise Edition Features** - Goes in `ee/` directory:
- Backend: `ee/backend/<feature>/`
- Frontend: `ee/frontend/components/<feature>/`
- Tests: `tests/test_<feature>.py` (with EE skip marker)

### Decision Criteria: Core vs Enterprise

| Put in Core if... | Put in EE if... |
|-------------------|-----------------|
| Essential for ADR management | Adds integration with external service |
| Basic multi-tenancy | Requires paid external APIs |
| Standard auth (WebAuthn, OIDC) | Provider-specific OAuth (Google) |
| Security fundamentals | Advanced analytics/monitoring |
| Self-hosting requirements | Cloud-specific (Azure, AWS) |

### Adding an Enterprise Feature

1. **Create module directory**:
   ```bash
   mkdir -p ee/backend/my_feature
   touch ee/backend/my_feature/__init__.py
   ```

2. **Add conditional import in app.py**:
   ```python
   from feature_flags import is_enterprise

   if is_enterprise():
       from ee.backend.my_feature import MyFeatureService
       # Register routes...
   ```

3. **Add dependencies to ee/requirements.txt**:
   ```
   my-feature-sdk>=1.0.0
   ```

4. **Create tests with skip marker**:
   ```python
   # tests/test_my_feature.py
   import pytest

   try:
       from ee.backend.my_feature import MyFeatureService
       EE_AVAILABLE = True
   except ImportError:
       EE_AVAILABLE = False

   pytestmark = pytest.mark.skipif(
       not EE_AVAILABLE,
       reason="Enterprise Edition modules not available"
   )
   ```

5. **Add feature flag**:
   ```python
   # feature_flags.py
   def get_features():
       return {
           ...
           'my_feature': is_enterprise(),
       }
   ```

### Adding a Core Feature

1. **Add to appropriate core file** (`app.py`, `models.py`, etc.)
2. **Add tests in `tests/`** (no skip marker needed)
3. **Verify it works in Community Edition**:
   ```bash
   python run_local.py --community
   # Test the feature
   ```

## GitHub Repository Configuration

### Repository Structure

This project uses **Option A: Public Repo with Private Submodule** for open core:

| Rep<br/>ository | URL | Visibility | Contains |
|------------|-----|------------|----------|
| **DecisionRecords** | `github.com/DecisionRecordsORG/DecisionRecords` | Public | Core code, docs, tests |
| **ee** | `github.com/DecisionRecordsORG/ee` | Private | EE backend, frontend, infra |

```
DecisionRecordsORG/
├── DecisionRecords (PUBLIC)     # Core open source code
│   ├── app.py
│   ├── models.py
│   ├── frontend/
│   ├── ee/ → submodule         # Points to private repo
│   └── ...
│
└── ee (PRIVATE)                 # Enterprise code
    ├── backend/
    │   ├── ai/
    │   ├── slack/
    │   ├── teams/
    │   └── ...
    ├── frontend/
    └── requirements.txt
```

### Cloning the Repository

**Community Edition** (public users, no access to ee/):
```bash
git clone https://github.com/DecisionRecordsORG/DecisionRecords.git
cd DecisionRecords
# ee/ directory is empty - Community Edition only
```

**Enterprise Edition** (team members with ee/ access):
```bash
git clone --recurse-submodules https://github.com/DecisionRecordsORG/DecisionRecords.git
cd DecisionRecords
# ee/ contains enterprise code - Full Enterprise Edition
```

**If you already cloned without submodule:**
```bash
git submodule update --init --recursive
```

### Updating the Submodule

When the ee/ repository has new commits:
```bash
# Update to latest ee/ commit
git submodule update --remote ee

# Commit the submodule reference update
git add ee
git commit -m "Update ee submodule to latest"
git push
```

### Making Changes to Enterprise Code

```bash
# Navigate into the submodule
cd ee

# Make changes, commit, and push to ee repo
git add .
git commit -m "Your change description"
git push origin main

# Go back to main repo and update submodule reference
cd ..
git add ee
git commit -m "Update ee submodule"
git push
```

### GitHub Actions for Dual Repos

```yaml
# .github/workflows/build.yml
name: Build

on: [push, pull_request]

jobs:
  build-community:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # No submodule checkout = Community Edition

      - name: Build Community Edition
        run: |
          docker build -f Dockerfile.community -t app:community .

  build-enterprise:
    runs-on: ubuntu-latest
    # Only run if we have access to the private submodule
    if: github.repository == 'DecisionRecordsORG/DecisionRecords'
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
          token: ${{ secrets.EE_REPO_TOKEN }}

      - name: Build Enterprise Edition
        run: |
          docker build -f deployment/Dockerfile.production -t app:enterprise .
```

### Access Control

| User Type | DecisionRecords (Public) | ee (Private) |
|-----------|--------------------------|--------------|
| Community contributor | Read/Write (via PR) | No access |
| Maintainer | Write | Read |
| Core team | Admin | Admin |

### Setting Up CI/CD Access to Private Submodule

For GitHub Actions to access the private `ee` repo:

1. **Create a Personal Access Token (PAT)** with `repo` scope
2. **Add as repository secret**: Settings → Secrets → `EE_REPO_TOKEN`
3. **Use in checkout action**: `token: ${{ secrets.EE_REPO_TOKEN }}`

Alternatively, use a **GitHub App** or **Deploy Key** for more granular permissions.
