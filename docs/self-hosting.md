# Self-Hosting Guide

This guide covers deploying Decision Records on your own infrastructure.

## Quick Start (Docker)

The fastest way to get started:

```bash
# Clone the repository
git clone https://github.com/DecisionRecordsORG/DecisionRecords.git
cd DecisionRecords

# Start with docker-compose
docker-compose up -d

# Access at http://localhost:3000
```

## Docker Deployment

### Using docker-compose (Recommended)

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    image: ghcr.io/decisionrecordsorg/decision-records:latest
    ports:
      - "3000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=sqlite:////data/decisions.db
    volumes:
      - decision-records-data:/data
    restart: unless-stopped

volumes:
  decision-records-data:
```

### With PostgreSQL

```yaml
version: '3.8'

services:
  app:
    image: ghcr.io/decisionrecordsorg/decision-records:latest
    ports:
      - "3000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/decisions
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=decisions
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

### Single Container

```bash
# With SQLite (persistent volume)
docker run -d \
  --name decision-records \
  -p 3000:8000 \
  -v decision-records-data:/data \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  ghcr.io/decisionrecordsorg/decision-records:latest

# With PostgreSQL
docker run -d \
  --name decision-records \
  -p 3000:8000 \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e DATABASE_URL="postgresql://user:pass@host:5432/decisions" \
  ghcr.io/decisionrecordsorg/decision-records:latest
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret (min 32 chars) | `openssl rand -hex 32` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `sqlite:////data/decisions.db` |
| `DECISION_RECORDS_EDITION` | `community` or `enterprise` | `community` |
| `ENVIRONMENT` | `development` or `production` | `production` |
| `SKIP_CLOUDFLARE_CHECK` | Skip Cloudflare validation | `true` |

### Email Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SMTP_USERNAME` | SMTP authentication username | - |
| `SMTP_PASSWORD` | SMTP authentication password | - |

Email can also be configured through the admin UI after setup.

### Database URLs

```bash
# SQLite (default, good for small deployments)
DATABASE_URL=sqlite:////data/decisions.db

# PostgreSQL (recommended for production)
DATABASE_URL=postgresql://user:password@host:5432/database

# PostgreSQL with SSL
DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require
```

## Reverse Proxy Setup

### Nginx

```nginx
server {
    listen 80;
    server_name decisions.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name decisions.example.com;

    ssl_certificate /etc/letsencrypt/live/decisions.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/decisions.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Caddy

```caddyfile
decisions.example.com {
    reverse_proxy localhost:3000
}
```

### Traefik

```yaml
# docker-compose.yml with Traefik labels
services:
  app:
    image: ghcr.io/decisionrecordsorg/decision-records:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.decisions.rule=Host(`decisions.example.com`)"
      - "traefik.http.routers.decisions.entrypoints=websecure"
      - "traefik.http.routers.decisions.tls.certresolver=letsencrypt"
```

## First-Time Setup

1. **Access the application** at your configured URL
2. **Setup Wizard** will guide you through:
   - Creating your organization
   - Setting up your admin account
   - Configuring authentication

3. **Super Admin access** (for managing multiple tenants):
   - Username: `admin`
   - Password: `changeme`
   - **Important**: Change this password immediately!

## Backups

### SQLite

```bash
# Backup
docker cp decision-records:/data/decisions.db ./backup-$(date +%Y%m%d).db

# Restore
docker cp ./backup.db decision-records:/data/decisions.db
docker restart decision-records
```

### PostgreSQL

```bash
# Backup
docker exec postgres pg_dump -U postgres decisions > backup-$(date +%Y%m%d).sql

# Restore
docker exec -i postgres psql -U postgres decisions < backup.sql
```

## Upgrading

```bash
# Pull latest image
docker-compose pull

# Restart with new image
docker-compose up -d

# Check logs for migration status
docker-compose logs -f app
```

Database migrations run automatically on startup.

## Health Check

The application exposes a health endpoint:

```bash
curl http://localhost:3000/api/health
# {"status":"ok","server":"running","timestamp":"..."}
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs app

# Common issues:
# - Missing SECRET_KEY
# - Invalid DATABASE_URL
# - Port already in use
```

### Database connection failed

```bash
# Verify PostgreSQL is accessible
docker exec -it postgres psql -U postgres -c "SELECT 1"

# Check DATABASE_URL format
# postgresql://user:password@host:5432/database
```

### Reset to fresh state

```bash
# WARNING: This deletes all data!
docker-compose down -v
docker-compose up -d
```

## Security Recommendations

1. **Use HTTPS** - Always run behind a reverse proxy with TLS
2. **Strong SECRET_KEY** - Use at least 32 random characters
3. **Database security** - Use strong passwords, enable SSL
4. **Regular backups** - Automate daily backups
5. **Keep updated** - Pull new images regularly

## GDPR Compliance

Decision Records includes built-in GDPR features: account deletion with anonymisation, personal data export, and consent management. These work out of the box for user-initiated actions.

### Automated GDPR Tasks

To enforce data retention policies automatically (purging expired soft-deleted records, cleaning up login history, completing account anonymisation after the grace period), you need to set up a cron job that calls the GDPR task execution endpoint.

#### 1. Set the cron secret

Add a shared secret to your environment:

```bash
# In your docker-compose.yml or .env file
GDPR_CRON_SECRET=your-secure-random-secret-here
```

Generate a strong secret:

```bash
openssl rand -hex 32
```

#### 2. Configure the cron job

Set up a cron job to call the endpoint (hourly recommended):

```bash
# Add to your server's crontab (crontab -e)
0 * * * * curl -s -X POST http://localhost:3000/api/admin/execute-gdpr-tasks \
  -H "Content-Type: application/json" \
  -H "X-Cron-Secret: your-secure-random-secret-here" \
  > /var/log/gdpr-tasks.log 2>&1
```

Or using docker-compose:

```bash
0 * * * * docker exec decision-records curl -s -X POST http://localhost:8000/api/admin/execute-gdpr-tasks \
  -H "Content-Type: application/json" \
  -H "X-Cron-Secret: your-secure-random-secret-here" \
  >> /var/log/gdpr-tasks.log 2>&1
```

#### 3. What the automated tasks do

| Task | Frequency | Description |
|------|-----------|-------------|
| Account anonymisation | Hourly | Completes deletion for accounts past the 7-day grace period |
| History cleanup | Hourly | Removes login history entries older than 90 days |
| Record purge | Hourly | Permanently deletes soft-deleted decisions/tenants older than 30 days |

#### 4. Existing installations

If upgrading from a version before v2.28.0, run the migration script to add the consent tables:

```bash
DATABASE_URL="postgresql://..." python ee/scripts/migrate_to_v228.py --verbose
```

## Support

- [GitHub Issues](https://github.com/DecisionRecordsORG/DecisionRecords/issues)
- [Documentation](https://github.com/DecisionRecordsORG/DecisionRecords/tree/main/docs)
