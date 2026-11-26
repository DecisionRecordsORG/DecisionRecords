# Configuration Reference

Configuration guide for self-hosting Decision Records Community Edition.

> **Note**: This documentation is for Community Edition self-hosters. Enterprise Edition users should refer to internal documentation.

## Environment Variables

### Core Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **Yes** | - | Flask secret key for session signing. Must be at least 32 characters. Generate with: `openssl rand -hex 32` |
| `MASTER_PASSWORD` | **Yes** | - | Bootstrap super admin password for `/superadmin`. If omitted, no bootstrap super admin account is created. |
| `MASTER_USERNAME` | No | `admin` | Bootstrap super admin username |
| `DATABASE_URL` | No | `sqlite:////data/decisions.db` | Database connection string |
| `DECISION_RECORDS_EDITION` | No | `community` | Edition: `community` or `enterprise` |
| `ENVIRONMENT` | No | `production` | Runtime environment: `development` or `production` |
| `SUPPORT_URL` | No | - | Address of your own support page for the "Can't sign in? Get help" link on the sign-in pages. Must start with `http://` or `https://`. Set it to `none` to hide the link. See [Help link](#help-link) |

### Help link

The sign-in, setup and recovery pages can show a "Can't sign in? Get help" link for people who are stuck before they are signed in. A self-hosted installation shows no link unless you give it an address.

| `SUPPORT_URL` | What the app does |
|---------------|-------------------|
| not set or empty | The default: no link on a self-hosted installation |
| an `http://` or `https://` address | The link leads to that address. The app adds `topic`, and when they are known `email` and `org` (the organisation's email domain), as query parameters |
| `none` | The link is hidden |
| anything else | The link is hidden and a warning is written to the log. Addresses with a user name or password in them, with spaces or with markup characters are not accepted |

A super admin can set the same value under Super Admin > Settings > Help link. A saved setting wins over `SUPPORT_URL`; clearing the setting goes back to `SUPPORT_URL`. The value is stored in system settings under the key `support_url` and is reported to the app as `support_url` by `/api/features`.

```yaml
environment:
  - SUPPORT_URL=https://intranet.example.org/decision-records-help
```

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
| `SMTP_ENCRYPTION_KEY` | Fernet key used to encrypt the secrets saved in the Admin UI: SMTP passwords and SSO client secrets. Without it they are stored unencrypted. Secrets saved before the key was set are encrypted at the next start. Keep the key stable: with a different key the saved secrets cannot be read. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

Additional email settings (server, port, from address) are configured in the Admin UI under Settings > Email.

### Security Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIP_CLOUDFLARE_CHECK` | `false` | Set to `true` for self-hosted deployments not behind Cloudflare |
| `TRUSTED_PROXIES` | - | Addresses or networks of your reverse proxies, comma-separated (`172.17.0.1, 10.0.0.0/8`). Empty by default: no forwarding header is believed. Set it when the application runs behind a reverse proxy. See [Behind a reverse proxy](#behind-a-reverse-proxy) |
| `RETENTION_AUTO_RUN` | `true` | Set to `false` to turn off the daily automatic data retention run for this installation. It wins over the super admin setting. With it off, expired data is erased only when a super admin or a cron job starts a run |
| `GDPR_CRON_SECRET` | - | Optional. Shared secret for an operator's own cron job that calls `/api/admin/execute-gdpr-tasks`. Not needed for the automatic run. Generate with: `openssl rand -hex 32` |

### Behind a reverse proxy

The application needs each visitor's address for two things: the rate limiter counts requests per address (200 a minute for each endpoint by default, fewer on sign-in and the public forms), and the login history and audit log record it.

The only address the application can be sure of is the one that opened the connection. Behind a reverse proxy that is the proxy, for every visitor. The proxy passes the visitor's address on in the `X-Forwarded-For` header, but anyone can send that header, so the application believes it only when the connection comes from a proxy you have named:

```bash
# The address (or network) your proxy connects from, as the application sees it
TRUSTED_PROXIES=172.17.0.1
```

| `TRUSTED_PROXIES` | Address used |
|-------------------|--------------|
| not set (default) | The address that opened the connection. No header is read. Right when visitors reach the application directly. Behind a proxy, all visitors count as one: they share one rate-limit allowance and the login history shows the proxy |
| your proxy | The last address in `X-Forwarded-For` that is not one of your proxies. Entries further left were sent by the visitor and are ignored |

With more than one proxy in a row (a load balancer or CDN in front of nginx), list all of them. The header is read from the right and stops at the first address that is not in the list.

Rules:

- List only proxies you run or trust. Whoever can connect from a listed address can choose the address the application records.
- The proxy must append the address that connected to it to `X-Forwarded-For`. nginx does with `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`; Caddy and Traefik do by default.
- Make sure visitors cannot reach the application around the proxy. With Docker, publish the port on the loopback address only (`127.0.0.1:3000:8000`).
- An entry that is not an address or network is ignored and reported in the log at start-up. `X-Real-IP`, `Forwarded` and provider-specific headers are never read.
- An IPv6 visitor is counted by `/64` block for rate limiting.

To check: sign in, then open the login history in the super admin pages. It should show your own address, not the proxy's.

**Rate limit counts and worker processes.** Each limit is counted per visitor and per endpoint, and each worker process keeps its own counts in memory. With the image's two workers a visitor can make up to twice the stated number of requests before being refused, and counts start again when the application restarts. That is acceptable for a single installation. The application can read a shared store from `REDIS_URL`, but the published image does not include a Redis client, so this needs an image of your own with the `redis` package added.

### Edition

Community Edition is the default and only option for self-hosted deployments:

```bash
DECISION_RECORDS_EDITION=community  # Default, can be omitted
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

## Runtime Configuration

Many settings can be configured at runtime through the Admin UI:

### Super Admin Settings

Access via `/superadmin` with master credentials.

| Setting | Location | Description |
|---------|----------|-------------|
| Email verification | System Config | Require email verification for new users |
| Default email config | Email Settings | SMTP configuration for all tenants |
| Data retention | Data retention | Turn the daily automatic run on or off, set its limits, see what is waiting and the last runs, and run a held back category |
| Help link | Settings | Address of your own support page for the "Can't sign in? Get help" link, or `none` to hide it. Wins over `SUPPORT_URL` |

### Tenant Admin Settings

Access via `/:tenant/admin/settings`.

| Setting | Location | Description |
|---------|----------|-------------|
| Authentication | Auth Settings | Enable/disable auth methods |
| SSO/OIDC | Auth Settings | Configure identity provider |
| Tenant email | Email Settings | Override system email config |
| Governance | Tenant Settings | Maturity state and policies |

### GDPR / Privacy

The platform enforces the following data retention and privacy settings:

| Setting | Value | Description |
|---------|-------|-------------|
| Account deletion grace period | 7 days | Time before a deletion request becomes permanent. Users can cancel during this period. |
| Soft-delete retention | 30 days | Soft-deleted decisions and tenants are erased after this period. |
| Login history retention | 90 days | Authentication log entries are deleted after this period. |
| Stored message retention | 24 months | Messages from the contact, "Get in touch" and feedback forms are deleted after this period. |
| Request log retention | 90 days | Log entries of API, MCP and AI requests are deleted after this period. |
| Confirmation and set-up records | 30 days after expiry | Email confirmation records and account set-up or recovery links are deleted 30 days after they expired. |
| Access request retention | 90 days after the answer | Requests to join an organisation are deleted 90 days after they were approved or rejected. Pending requests stay. |
| API key retention | 90 days after revocation or expiry | Revoked and expired API keys are deleted after this period. Working keys stay. |
| Anonymisation behaviour | "Former Member" | Deleted users' contributions are preserved with attribution changed to "Former Member". |

The application enforces these periods itself, once a day, without a cron job (see [Data retention](self-hosting.md#data-retention)). Erasure cannot be undone; a database backup is the only way back.

**Automatic run settings** (Super Admin > Data retention, stored in system settings):

| Setting | Key | Default | Description |
|---------|-----|---------|-------------|
| Run automatically | `retention_auto_run_enabled` | `true` | Turns the daily run on or off. `RETENTION_AUTO_RUN=false` in the environment turns it off regardless |
| Account limit | `retention_limit_accounts` | 10 | Most accounts one automatic run anonymises. With more waiting, the run leaves accounts alone until a super admin runs them |
| Decision limit | `retention_limit_decisions` | 50 | Most soft-deleted decisions one automatic run erases |
| Tenant limit | `retention_limit_tenants` | 1 | Most soft-deleted tenants one automatic run erases |
| Days overdue | `retention_backlog_days` | 7 | A category whose oldest item is more than this many days overdue is left alone until a super admin runs it. 0 turns the check off |

A limit of 0 means the automatic run never does that category by itself. Everything that is deleted by age alone (login history, stored messages, the request log, expired confirmation and set-up records, answered access requests, revoked and expired API keys) has no limit.

**Privacy preferences** each person sets on their profile page:

| Switch | Default | What it does |
|--------|---------|--------------|
| Analytics (Enterprise Edition; not shown in the Community Edition, which has no analytics) | Off | On: the person's browser may send page views and clicks to the analytics service once the notice is accepted in that browser, and the server's usage events and error reports carry a code derived from the account. Off: the browser sends nothing, and the server's events are still counted but carry no code for the person or their organisation |
| AI processing (Enterprise Edition) | Off | Whether AI features may process the person's decision content |
| Email notifications | On | Off: the person gets no emails about decisions (neither the notifications they subscribed to, nor the message sent when they are made the owner of a decision). Emails about the account itself (verification, set-up and recovery links) are always sent |

A change takes effect at once. For each switch the application stores the choice, when it was made and the IP address it was made from; the address is removed when the account is anonymised.

A person can also correct their own name on the profile page. The email address cannot be changed there: it is the account's identity and decides which organisation the account belongs to.

The retention periods and the switches are fixed and not configurable.

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
  "version": "2.3.1",
  "build_date": "2026-11-22",
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

When a support page address was chosen (see [Help link](#help-link)), the answer also has `"support_url"`: the address, or `"none"` when the link is hidden. Without a choice the key is absent.

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
