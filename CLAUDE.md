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
# Correct workflow
git add .
git commit -m "Description of changes"
./scripts/version-bump.sh patch  # Optional: if releasing new version
docker build --platform linux/amd64 -t adrregistry2024eu.azurecr.io/architecture-decisions:latest -f deployment/Dockerfile.production .
az acr login --name adrregistry2024eu
docker push adrregistry2024eu.azurecr.io/architecture-decisions:latest
az container restart --name adr-app-eu --resource-group adr-resources-eu
./scripts/update-gateway-backend.sh  # Update Application Gateway if container IP changed
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
