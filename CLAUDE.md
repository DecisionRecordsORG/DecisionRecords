# Claude Code Instructions
DO NOT add Claude code branding in commit messages.
Always ask approval before deploying to production.
Always run the redeploy script with required parameters.
When you add features, add UI tests for them too.
Make use of Claude code sub agents to write and run tests.

This file contains instructions and context for Claude Code when working on this project.

## Project Overview

Architecture Decisions is a multi-tenant web application for managing Architecture Decision Records (ADRs) based on the arc42 format.

- **Production URL**: https://architecture-decisions.org
- **Backend**: Python/Flask with SQLAlchemy
- **Frontend**: Angular 18 with Material UI
- **Auth**: WebAuthn/Passkeys, OIDC SSO, local auth
- **Deployment**: Docker → Azure Container Instances
- **CDN/SSL**: Cloudflare (Free plan) with Origin Server certificates

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

- **Domain**: architecture-decisions.org
- **DNS Provider**: Cloudflare (Free plan)
- **SSL Mode**: Full (strict) - Cloudflare validates Origin certificate
- **Origin Certificate**: Cloudflare Origin Server certificate installed on App Gateway
- **Certificate Files**: `~/.ssh/architecture-decisions.pem` (cert) and `~/.ssh/architecture-decisions.key` (private key)

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

## File Structure

Key files to understand:

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application with all API routes |
| `models.py` | SQLAlchemy database models |
| `version.py` | Version information |
| `keyvault_client.py` | Azure Key Vault integration |
| `security.py` | Security helpers (CSRF, sanitization) |
| `frontend/src/app/` | Angular components and services |
| `deployment/Dockerfile.production` | Production Docker build |
| `infra/azure-deploy-vnet.json` | Azure ARM template |

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
# Run all backend tests
.venv/bin/python -m pytest tests/ -v

# Run specific test file
.venv/bin/python -m pytest tests/test_auth.py -v

# Run E2E tests (requires frontend running)
cd frontend && npm run build && cd ..
npx playwright test

# Run specific E2E test
npx playwright test e2e/tests/decisions.spec.ts
```

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
