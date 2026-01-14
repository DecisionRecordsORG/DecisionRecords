# Configuration Reference

This document describes all configuration options for Decision Records.

## Environment Variables

### Core Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **Yes** | - | Flask secret key for session signing. Must be at least 32 characters. Generate with: `openssl rand -hex 32` |
| `DATABASE_URL` | No | `sqlite:////data/decisions.db` | Database connection string |
| `DECISION_RECORDS_EDITION` | No | `community` | Edition: `community` or `enterprise` |
| `ENVIRONMENT` | No | `production` | Runtime environment: `development` or `production` |

### Database Configuration

#### SQLite (Default)

```bash
DATABASE_URL=sqlite:////data/decisions.db
```

SQLite is suitable for:
- Small teams (< 50 users)
- Development and testing
- Simple deployments

#### PostgreSQL (Recommended for Production)

```bash
# Basic connection
DATABASE_URL=postgresql://user:password@host:5432/database

# With SSL (recommended)
DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require

# Full options
DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=verify-full&sslrootcert=/path/to/ca.crt
```

PostgreSQL is recommended for:
- Production deployments
- Multiple concurrent users
- High availability requirements

### Email Configuration

Email can be configured via environment variables or through the Admin UI.

| Variable | Description |
|----------|-------------|
| `SMTP_USERNAME` | SMTP server username |
| `SMTP_PASSWORD` | SMTP server password |

Additional email settings (server, port, from address) are configured in the Admin UI under Settings > Email.

### Security Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIP_CLOUDFLARE_CHECK` | `false` | Set to `true` for self-hosted deployments not behind Cloudflare |

### Feature Flags

The `DECISION_RECORDS_EDITION` variable controls which features are available:

#### Community Edition (`community`)

```bash
DECISION_RECORDS_EDITION=community
```

Features included:
- Architecture Decision Records
- Multi-tenant workspaces
- WebAuthn/Passkey authentication
- OIDC/SSO integration
- Role-based access control
- Audit logging
- IT Infrastructure mapping
- Spaces and organization
- Email notifications

#### Enterprise Edition (`enterprise`)

```bash
DECISION_RECORDS_EDITION=enterprise
```

Additional features:
- Slack integration
- Microsoft Teams integration
- Google OAuth
- AI-powered features
- PostHog analytics
- Azure Key Vault integration

## Runtime Configuration

Many settings can be configured at runtime through the Admin UI:

### Super Admin Settings

Access via `/superadmin` with master credentials.

| Setting | Location | Description |
|---------|----------|-------------|
| Email verification | System Config | Require email verification for new users |
| Default email config | Email Settings | SMTP configuration for all tenants |

### Tenant Admin Settings

Access via `/:tenant/admin/settings`.

| Setting | Location | Description |
|---------|----------|-------------|
| Authentication | Auth Settings | Enable/disable auth methods |
| SSO/OIDC | Auth Settings | Configure identity provider |
| Tenant email | Email Settings | Override system email config |
| Governance | Tenant Settings | Maturity state and policies |

## Authentication Methods

### WebAuthn/Passkeys (Default)

No additional configuration required. Users can register passkeys during signup or from their profile.

### OIDC/SSO

Configure through Admin UI or API:

```json
{
  "provider_url": "https://login.microsoftonline.com/{tenant}/v2.0",
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "scopes": "openid profile email"
}
```

Supported providers:
- Microsoft Azure AD / Entra ID
- Google Workspace
- Okta
- Auth0
- Any OIDC-compliant provider

### Local Authentication

Username/password authentication. Configure password requirements in tenant settings.

## Logging

Application logs are sent to stdout and can be captured by your container runtime.

```bash
# View logs with Docker
docker logs -f decision-records

# With docker-compose
docker-compose logs -f app
```

Log levels:
- `INFO` - Normal operation
- `WARNING` - Non-critical issues
- `ERROR` - Errors requiring attention

## Health Monitoring

### Health Endpoint

```bash
GET /api/health
```

Response:
```json
{
  "status": "ok",
  "server": "running",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Version Endpoint

```bash
GET /api/version
```

Response:
```json
{
  "version": "1.14.2",
  "build_date": "2024-01-15",
  "git_commit": "abc1234",
  "environment": "production"
}
```

### Features Endpoint

```bash
GET /api/features
```

Returns enabled features based on edition:
```json
{
  "edition": "community",
  "is_enterprise": false,
  "decisions": true,
  "multi_tenancy": true,
  "webauthn": true,
  "slack_integration": false,
  "teams_integration": false,
  "ai_features": false
}
```

## Example Configurations

### Minimal Self-Hosted

```bash
SECRET_KEY="$(openssl rand -hex 32)"
DATABASE_URL="sqlite:////data/decisions.db"
SKIP_CLOUDFLARE_CHECK="true"
```

### Production with PostgreSQL

```bash
SECRET_KEY="your-secure-secret-key-at-least-32-chars"
DATABASE_URL="postgresql://user:pass@db.example.com:5432/decisions?sslmode=require"
ENVIRONMENT="production"
SKIP_CLOUDFLARE_CHECK="true"
```

### Development

```bash
SECRET_KEY="dev-secret-key-not-for-production"
DATABASE_URL="sqlite:///instance/decisions.db"
ENVIRONMENT="development"
SKIP_CLOUDFLARE_CHECK="true"
DEBUG="true"
```
