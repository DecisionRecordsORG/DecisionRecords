# Self-Hosting Guide

This guide covers deploying Decision Records on your own infrastructure.

## Quick Start (Docker)

The fastest way to get started:

```bash
# Clone the repository
git clone https://github.com/DecisionRecordsORG/DecisionRecords.git
cd DecisionRecords

# Copy the example environment and set secrets
cp .env.example .env

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
    image: ghcr.io/decisionrecordsorg/decisionrecords:latest
    ports:
      - "3000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - MASTER_USERNAME=${MASTER_USERNAME:-admin}
      - MASTER_PASSWORD=${MASTER_PASSWORD}
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
    image: ghcr.io/decisionrecordsorg/decisionrecords:latest
    ports:
      - "3000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - MASTER_USERNAME=${MASTER_USERNAME:-admin}
      - MASTER_PASSWORD=${MASTER_PASSWORD}
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
  -e MASTER_USERNAME="admin" \
  -e MASTER_PASSWORD="$(openssl rand -hex 24)" \
  ghcr.io/decisionrecordsorg/decisionrecords:latest

# With PostgreSQL
docker run -d \
  --name decision-records \
  -p 3000:8000 \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e MASTER_USERNAME="admin" \
  -e MASTER_PASSWORD="$(openssl rand -hex 24)" \
  -e DATABASE_URL="postgresql://user:pass@host:5432/decisions" \
  ghcr.io/decisionrecordsorg/decisionrecords:latest
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret (min 32 chars) | `openssl rand -hex 32` |
| `MASTER_PASSWORD` | Bootstrap super admin password | `openssl rand -hex 24` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `sqlite:////data/decisions.db` |
| `MASTER_USERNAME` | Bootstrap super admin username | `admin` |
| `DECISION_RECORDS_EDITION` | `community` or `enterprise` | `community` |
| `ENVIRONMENT` | `development` or `production` | `production` |
| `SKIP_CLOUDFLARE_CHECK` | Skip Cloudflare validation | `true` |
| `SUPPORT_URL` | Address of your own support page for the "Can't sign in? Get help" link. `none` hides the link | no link |

### Email Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SMTP_USERNAME` | SMTP authentication username | - |
| `SMTP_PASSWORD` | SMTP authentication password | - |
| `SMTP_ENCRYPTION_KEY` | Fernet key that encrypts SMTP passwords saved in the admin UI. If unset, those passwords are stored unencrypted. Keep it stable: changing it makes saved passwords unreadable. | - |

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
    image: ghcr.io/decisionrecordsorg/decisionrecords:latest
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
   - Username: value of `MASTER_USERNAME` (defaults to `admin`)
   - Password: value of `MASTER_PASSWORD`
   - **Important**: Set a strong password before first start and store it securely.

## Backups

Back up the database regularly. Data retention erases expired accounts, decisions and tenants for good (see [Data retention](#data-retention)); a backup is the only way to get them back.

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

If you pin explicit release tags instead of `latest`, pull the target version from GitHub Container Registry before restarting:

```bash
docker pull ghcr.io/decisionrecordsorg/decisionrecords:v2.2.0
```

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

### Data retention

Decision Records keeps these deletion timelines by itself. There is nothing to install or schedule.

| What | When | What happens |
|------|------|--------------|
| Accounts | 7 days after the owner asked for deletion | The account is anonymised. Its decisions, comments and changes stay. Comments and the change history show "Former Member"; a decision the person wrote or owned no longer shows an author or owner. The person's name, email address and IP address are removed everywhere else they were written: sign-in history (including failed attempts recorded by address), audit log details, the request for the organisation's domain, linked Slack and Teams accounts, stored Teams conversations, API key names and the text of AI queries. Their passkeys, notification settings, role requests, access requests and setup links are deleted |
| Soft-deleted decisions | 30 days after deletion | The decision, its history, comments and links are erased |
| Soft-deleted tenants | 30 days after deletion | The tenant, its decisions, spaces, settings, sign-in configuration, logs and the accounts of its members are erased |
| Login history | After 90 days | The entries are deleted |
| Messages from the contact, "Get in touch" and feedback forms | After 24 months | The messages are deleted |

**Erasure cannot be undone.** The application keeps no copy of what it erases. A database backup is the only way to get erased data back, so take backups (see [Backups](#backups)) and decide how long you keep them.

#### How the automatic run works

Once a day (UTC) the application runs retention in the background. It starts about a minute after the application has started and served its first request, and after that it does not need traffic. With several workers or containers on one database, only one of them does a day's run: each run is claimed in the database first. A run never happens inside a user's request.

If the application is stopped part way through a run, nothing is left half erased: every account, decision and tenant is handled in its own database transaction. The run is shown as "interrupted" and the next day's run carries on with what is left.

Dates are stored in UTC. If your PostgreSQL server uses another time zone, some stored dates are off by that zone's offset, so retention waits the size of the offset plus one hour past each due date before it acts. Nothing is erased early; on such a server it happens a few hours late. Setting the database time zone to UTC avoids this.

#### Limits: when the automatic run holds back

An automatic run is deliberately cautious with the three things that cannot be put back. It leaves a whole category alone, and carries on with the others, when:

- more items are waiting than the category's limit, or
- the oldest waiting item is more than 7 days overdue. That only happens when retention has not been running, for example on the first start after an upgrade from a version that needed a cron job, or after the automatic run was turned off for a while.

| Category | Default limit per run |
|----------|-----------------------|
| Accounts to anonymise | 10 |
| Deleted decisions to erase | 50 |
| Deleted tenants to erase | 1 |
| Login history and stored messages | No limit. They are deleted by age alone |

A limit of 0 means the automatic run never does that category by itself. Setting the "days overdue" check to 0 turns that check off. A super admin changes these under Super Admin > Data retention, or with `PUT /api/admin/settings/retention`.

#### What you see when a category is held back

- Super Admin > Data retention shows a notice naming the category, how many items are waiting and why, with the list of what would be erased. The dashboard link shows how many categories are held back.
- The run is listed with the status "held back", and the application log has a warning line: `Retention: tenants held back (over_limit): 3 waiting, limit 1. A super admin must run it.`
- Nothing in that category is erased until a super admin opens the page, checks the list and chooses "Run now". The confirmation states the number of items. If more items have become due since the page was loaded, the run is refused and the page shows the new number.
- The same check runs every day, so a held back category stays held back, and stays visible, until someone releases it.

A soft-deleted tenant whose status was changed by hand to something other than "deleted" is never erased, automatically or by a super admin. The page lists it under "needs review". Restore it properly or set its status back to "deleted".

#### Turning the automatic run off

- For one installation, without a restart: Super Admin > Data retention, turn off "Run automatically".
- From the environment, for example before the first start of an upgraded installation: set `RETENTION_AUTO_RUN=false`. This wins over the setting and the page says so.

With the automatic run off, nothing is erased until a super admin runs a category from the page or a cron job calls the endpoint below. Your deletion timelines are then not being kept.

#### The record of what was erased

Every run is stored (when, how it was started, how many items per category, what was held back, errors, how long it took) and shown on the Data retention page. For each erasure a record is written in the same database transaction: the kind of thing, its id, for a tenant its domain, and how many rows went from each table. It never holds names, email addresses or the content of a decision. These records are in the `retention_runs` and `retention_erasures` tables and are not deleted automatically.

#### Optional: your own cron job

Installations that already call the task endpoint from cron can keep doing so. It is no longer needed. The endpoint does the same work as the automatic run, under the same limits, and cannot release a held back category.

```bash
# In your docker-compose.yml or .env file. Generate with: openssl rand -hex 32
GDPR_CRON_SECRET=your-secure-random-secret-here
```

```bash
# Add to your server's crontab (crontab -e)
0 3 * * * curl -s -X POST http://localhost:3000/api/admin/execute-gdpr-tasks \
  -H "Content-Type: application/json" \
  -H "X-Cron-Secret: your-secure-random-secret-here" \
  >> /var/log/gdpr-tasks.log 2>&1
```

The response keeps the counts it always had under `results` and adds `run_id`, `status`, `held_back` (categories that were left alone, with the number waiting) and `errors`.

#### Upgrading an installation where retention never ran

If you never set up the cron job, expired data has been building up. On the first start of this version the automatic run will delete old login history and old stored messages, and it will hold back accounts, decisions and tenants that are more than 7 days overdue. Open Super Admin > Data retention, read what is waiting, take a database backup, then run each held back category. From then on the daily run keeps up by itself.

### Messages from the contact and feedback forms

Messages sent through `/api/contact`, `/api/sponsorship` and `/api/feedback` are stored in the database before the notification email is attempted, so they are kept when SMTP is not configured or a send fails. A super admin reads them under Super Admin > Inquiries, where messages that were never emailed are marked "Not emailed". The stored record holds what the sender typed (name, email address, organisation, message and the optional "What does your team make decisions about?" answer) and, for a signed-in sender, their account and tenant domain. No IP address or user agent is stored. Deleting an account removes the name, email address and message from that person's inquiries.

#### 4. Existing installations

If upgrading from a version before `v2.2.0`, start the new Community Edition image and let the built-in migrations complete before sending production traffic to it. No separate public `ee/` migration script is required for Community Edition upgrades.

## Pointing the help link at your own support page

The sign-in, setup and recovery pages can show a "Can't sign in? Get help" link. On a self-hosted installation the link is not shown, so your users are not sent to the hosted service's support. To show it, give the address of a page of your own:

```yaml
environment:
  - SUPPORT_URL=https://intranet.example.org/decision-records-help
```

The address must start with `http://` or `https://`. The app opens it in a new tab and adds `topic` and, when it knows them, `email` and `org` as query parameters; your page can ignore them. `SUPPORT_URL=none` hides the link. A super admin can also set or hide the link under Super Admin > Settings > Help link, and that setting wins over the environment variable. More detail is in [Configuration](configuration.md#help-link).

## Support

- [GitHub Issues](https://github.com/DecisionRecordsORG/DecisionRecords/issues)
- [Documentation](https://github.com/DecisionRecordsORG/DecisionRecords/tree/main/docs)
