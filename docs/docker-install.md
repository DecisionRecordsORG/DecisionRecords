# Docker Installation Guide

Deploy Decision Records on your own infrastructure in minutes using Docker.

## Quick Start

### One-Line Install (SQLite)

```bash
docker run -d --name decision-records \
  -p 3000:8000 \
  -v decision-records-data:/data \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  ghcr.io/decisionrecordsorg/decisionrecords:latest
```

Open http://localhost:3000 and create your first tenant.

### Using Docker Compose (Recommended)

```bash
# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/DecisionRecordsORG/DecisionRecords/main/docker-compose.yml

# Create environment file
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env

# Start the application
docker-compose up -d

# View logs
docker-compose logs -f
```

Open http://localhost:3000

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **Yes** | - | Secret key for session encryption. Generate with `openssl rand -hex 32` |
| `DATABASE_URL` | No | SQLite | Database connection string |
| `SKIP_CLOUDFLARE_CHECK` | No | `true` | Set to `true` for self-hosted deployments |
| `DECISION_RECORDS_EDITION` | No | `community` | Edition (`community` or `enterprise`) |

### Database Options

#### SQLite (Default - Simple Setup)

Best for small teams (< 50 users) or evaluation.

```bash
docker run -d --name decision-records \
  -p 3000:8000 \
  -v decision-records-data:/data \
  -e SECRET_KEY=your-secret-key \
  ghcr.io/decisionrecordsorg/decisionrecords:latest
```

Data is stored in `/data/architecture_decisions.db` inside the container.

#### PostgreSQL (Recommended for Production)

Best for larger teams, high availability, and data durability.

```bash
# Using docker-compose with PostgreSQL profile
docker-compose --profile postgres up -d
```

Or manually:

```bash
# Start PostgreSQL
docker run -d --name postgres \
  -e POSTGRES_USER=decisions \
  -e POSTGRES_PASSWORD=your-db-password \
  -e POSTGRES_DB=decisions \
  -v postgres-data:/var/lib/postgresql/data \
  postgres:15-alpine

# Start Decision Records
docker run -d --name decision-records \
  -p 3000:8000 \
  -e SECRET_KEY=your-secret-key \
  -e DATABASE_URL=postgresql://decisions:your-db-password@postgres:5432/decisions \
  --link postgres \
  ghcr.io/decisionrecordsorg/decisionrecords:latest
```

## First-Time Setup

1. Open http://localhost:3000 in your browser
2. You'll see the login page - click "Create Tenant" or access `/superadmin`
3. Create your first tenant with a name and URL slug
4. Create your admin account
5. Start creating architecture decisions!

### Default Super Admin

For initial setup, access the super admin panel at `/superadmin`:
- Username: `admin`
- Password: `changeme`

**Important**: Change this password immediately after first login.

## Updating

### Manual Update

```bash
# Pull latest image
docker pull ghcr.io/decisionrecordsorg/decisionrecords:latest

# Stop and remove old container
docker stop decision-records
docker rm decision-records

# Start with new image (same command as before)
docker run -d --name decision-records \
  -p 3000:8000 \
  -v decision-records-data:/data \
  -e SECRET_KEY=your-secret-key \
  ghcr.io/decisionrecordsorg/decisionrecords:latest
```

### Automatic Updates with Watchtower

Enable automatic updates by adding the `auto-update` profile:

```bash
docker-compose --profile auto-update up -d
```

Watchtower will check daily for new images and automatically update.

### Check for Updates

You can check if updates are available via the API:

```bash
curl http://localhost:3000/api/version/check
```

Response:
```json
{
  "current_version": "1.15.0",
  "latest_version": "1.16.0",
  "update_available": true,
  "release_url": "https://github.com/DecisionRecordsORG/DecisionRecords/releases/tag/v1.16.0",
  "release_notes": "..."
}
```

## Data Persistence

### Volume Locations

| Volume | Purpose |
|--------|---------|
| `/data` | SQLite database (if not using PostgreSQL) |
| PostgreSQL volume | Database files (if using PostgreSQL profile) |

### Backup

#### SQLite

```bash
# Stop the container first for consistency
docker stop decision-records

# Copy the database file
docker cp decision-records:/data/architecture_decisions.db ./backup-$(date +%Y%m%d).db

# Restart
docker start decision-records
```

#### PostgreSQL

```bash
docker exec postgres pg_dump -U decisions decisions > backup-$(date +%Y%m%d).sql
```

### Restore

#### SQLite

```bash
docker stop decision-records
docker cp ./backup.db decision-records:/data/architecture_decisions.db
docker start decision-records
```

#### PostgreSQL

```bash
docker exec -i postgres psql -U decisions decisions < backup.sql
```

## Advanced Configuration

### Custom Port

```bash
docker run -d --name decision-records \
  -p 8080:8000 \  # Change 8080 to your desired port
  -v decision-records-data:/data \
  -e SECRET_KEY=your-secret-key \
  ghcr.io/decisionrecordsorg/decisionrecords:latest
```

### Behind Reverse Proxy (nginx, Traefik)

```yaml
# docker-compose.yml with Traefik labels
services:
  app:
    image: ghcr.io/decisionrecordsorg/decisionrecords:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.decisions.rule=Host(`decisions.example.com`)"
      - "traefik.http.routers.decisions.tls=true"
      - "traefik.http.routers.decisions.tls.certresolver=letsencrypt"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - SKIP_CLOUDFLARE_CHECK=true
```

### Email Notifications (Optional)

```bash
docker run -d --name decision-records \
  -p 3000:8000 \
  -v decision-records-data:/data \
  -e SECRET_KEY=your-secret-key \
  -e SMTP_HOST=smtp.gmail.com \
  -e SMTP_PORT=587 \
  -e SMTP_USERNAME=your-email@gmail.com \
  -e SMTP_PASSWORD=your-app-password \
  -e MAIL_FROM=your-email@gmail.com \
  ghcr.io/decisionrecordsorg/decisionrecords:latest
```

## Health Checks

The application exposes health check endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Basic health check |
| `GET /api/version` | Version information |
| `GET /api/version/check` | Check for updates |

Example health check:

```bash
curl http://localhost:3000/api/health
# {"status": "ok", "server": "running", "timestamp": "..."}
```

## Troubleshooting

### Container Won't Start

Check logs:
```bash
docker logs decision-records
```

Common issues:
- Missing `SECRET_KEY` - Required for session encryption
- Port already in use - Change the port mapping
- Permission issues with volume - Check Docker socket permissions

### Database Connection Failed

For PostgreSQL:
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Test connection
docker exec postgres pg_isready -U decisions
```

### Application Errors

Check the container logs:
```bash
docker logs -f decision-records
```

### Reset Everything

```bash
# Stop and remove containers
docker-compose down

# Remove volumes (WARNING: deletes all data!)
docker volume rm decision-records_adr-data decision-records_postgres-data

# Start fresh
docker-compose up -d
```

## System Requirements

### Minimum

- Docker 20.10+
- 512 MB RAM
- 1 GB disk space

### Recommended

- Docker 24.0+
- 2 GB RAM
- 10 GB disk space
- PostgreSQL for production

## Security Recommendations

1. **Generate a strong SECRET_KEY**: Use `openssl rand -hex 32`
2. **Use PostgreSQL in production**: SQLite is fine for evaluation
3. **Enable HTTPS**: Use a reverse proxy with TLS termination
4. **Regular backups**: Set up automated database backups
5. **Keep updated**: Enable Watchtower or check for updates regularly
6. **Change default credentials**: Update the super admin password immediately

## Getting Help

- [GitHub Issues](https://github.com/DecisionRecordsORG/DecisionRecords/issues)
- [Documentation](https://github.com/DecisionRecordsORG/DecisionRecords/tree/main/docs)
- [Community Discussions](https://github.com/DecisionRecordsORG/DecisionRecords/discussions)

## Next Steps

After installation:
1. Create your first tenant
2. Set up authentication (WebAuthn, OIDC)
3. Create your first Architecture Decision Record
4. Invite team members
5. Configure spaces for organizing decisions
