# Claude Code Instructions

This file contains instructions and context for Claude Code when working on this project.

## Project Overview

Architecture Decisions is a multi-tenant web application for managing Architecture Decision Records (ADRs) based on the arc42 format.

- **Backend**: Python/Flask with SQLAlchemy
- **Frontend**: Angular 18 with Material UI
- **Auth**: WebAuthn/Passkeys, OIDC SSO, local auth
- **Deployment**: Docker → Azure Container Instances

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
| App Gateway | - | Load balancer + WAF |

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

## Testing

Before deploying, consider testing:

1. **Frontend build**: `cd frontend && npm run build`
2. **Python imports**: `python -c "import app"`
3. **Local Docker**: `docker build -t test . && docker run -p 8000:8000 test`

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
