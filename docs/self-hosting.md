# Self-Hosting Guide

This guide will help you deploy Decision Records on your own infrastructure.

## Quick Start (Docker)

The fastest way to get started is with Docker:

```bash
# Clone the repository
git clone https://github.com/decisionrecords/decision-records.git
cd decision-records

# Start with Docker Compose (uses SQLite)
docker-compose up -d

# Open http://localhost:3000
```

## Requirements

### Hardware
- **Minimum**: 1 CPU, 1GB RAM
- **Recommended**: 2 CPU, 2GB RAM
- **Storage**: 1GB + space for your decision records

### Software
- Docker 20.10+ and Docker Compose 2.0+
- OR Python 3.11+ and Node.js 18+

## Deployment Options

### Option 1: Docker with SQLite (Simplest)

Best for small teams (< 50 users) or evaluation.

```bash
docker-compose up -d
```

### Option 2: Docker with PostgreSQL (Recommended)

Best for production use with multiple users.

```bash
# Set your PostgreSQL password
export POSTGRES_PASSWORD=secure-password-here

# Start with PostgreSQL profile
docker-compose --profile postgres up -d

# Update DATABASE_URL in your environment
export DATABASE_URL=postgresql://decisions:${POSTGRES_PASSWORD}@db:5432/decisions
```

### Option 3: Manual Installation

For custom deployments or development.

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install and build frontend
cd frontend
npm ci
npm run build
cd ..

# Set environment variables
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export DATABASE_URL=sqlite:///instance/decisions.db
export DECISION_RECORDS_EDITION=community

# Run with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for session signing | `your-secret-key-here` |
| `DATABASE_URL` | Database connection string | `sqlite:///decisions.db` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `DECISION_RECORDS_EDITION` | `community` or `enterprise` | `community` |
| `SKIP_CLOUDFLARE_CHECK` | Disable Cloudflare validation | `false` |
| `USE_HTTPS` | Enable secure cookies | `false` |

## Database Configuration

### SQLite (Default)

No additional setup required. The database is created automatically.

```bash
DATABASE_URL=sqlite:////data/architecture_decisions.db
```

### PostgreSQL (Recommended for Production)

```bash
DATABASE_URL=postgresql://username:password@host:5432/database
```

Create the database:
```sql
CREATE DATABASE decisions;
CREATE USER decisions WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE decisions TO decisions;
```

## Authentication

### Default Admin Account

On first run, a default master admin account is created:

- **Username**: `admin`
- **Password**: `changeme`

**Important**: Change this password immediately after first login at `/superadmin`.

### SSO Configuration

Decision Records supports:
- Generic OIDC (Okta, Auth0, Azure AD, etc.)
- WebAuthn/Passkeys

Configure SSO through the admin panel after initial setup.

## Reverse Proxy

### Nginx Example

```nginx
server {
    listen 80;
    server_name decisions.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name decisions.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Caddy Example

```caddyfile
decisions.example.com {
    reverse_proxy localhost:3000
}
```

## Backup and Restore

### SQLite

```bash
# Backup
docker cp decision-records-app-1:/data/architecture_decisions.db ./backup.db

# Restore
docker cp ./backup.db decision-records-app-1:/data/architecture_decisions.db
docker-compose restart app
```

### PostgreSQL

```bash
# Backup
docker exec decision-records-db-1 pg_dump -U decisions decisions > backup.sql

# Restore
docker exec -i decision-records-db-1 psql -U decisions decisions < backup.sql
```

## Upgrading

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose build
docker-compose up -d
```

## Troubleshooting

### Container won't start

Check logs:
```bash
docker-compose logs app
```

### Database connection errors

Verify DATABASE_URL is correct and the database is accessible.

### Login issues

Clear browser cookies and cache, or try incognito mode.

## Community vs Enterprise

The Community Edition includes:
- Architecture Decision Records (ADR) management
- Multi-tenant support
- WebAuthn/Passkey authentication
- Generic OIDC SSO
- Role-based access control
- Audit logging
- IT Infrastructure mapping
- Email notifications
- Spaces/Tags organization

Enterprise Edition adds:
- Slack integration
- Microsoft Teams integration
- Google OAuth
- AI-powered features
- PostHog analytics
- Priority support

For Enterprise licensing, contact enterprise@decisionrecords.org.

## Getting Help

- [GitHub Issues](https://github.com/decisionrecords/decision-records/issues)
- [Documentation](https://docs.decisionrecords.org)
