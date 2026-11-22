# Decision Records

> Open source decision records for teams

[![License](https://img.shields.io/badge/license-BSL%201.1-blue)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](docker-compose.yml)

Decision Records helps teams remember why decisions were made. It gives any team one shared place to record a decision, the situation that led to it, and what follows from it: a pricing change, a supplier choice, a hiring policy, or a software design.

Each record has the same three parts: Context, Decision, and Consequences. Records can be linked to each other, grouped into spaces, and replaced by later decisions without losing the history. Software teams will recognise the structure as the [Architecture Decision Record (ADR)](https://adr.github.io/) format; see [Decision record format](#decision-record-format).

## Quick Start

```bash
# Clone and run with Docker
git clone https://github.com/DecisionRecordsORG/DecisionRecords.git
cd DecisionRecords
cp .env.example .env
# Set SECRET_KEY and MASTER_PASSWORD in .env first
docker-compose up -d

# Open http://localhost:3000
```

On first run, the **Setup Wizard** will guide you through:
1. Creating your organization
2. Setting up your admin account

Super Admin access (for managing multiple tenants) uses `MASTER_USERNAME` / `MASTER_PASSWORD`.
The default bootstrap username is `admin`; you must set a strong `MASTER_PASSWORD` before first start.

## Features

### Community Edition (Free & Open Source)

- **Decision Records** - Record decisions in one proven format: Context, Decision, Consequences
- **Decision Relationships** - Link decisions that supersede, amend, or depend on each other, with relationship packs for software, data, security, operations, people, finance, and product teams
- **Multi-Tenant** - Each organization gets isolated workspace based on email domain
- **Passkey Authentication** - Secure passwordless login with WebAuthn/FIDO2
- **SSO/OIDC Integration** - Connect with Okta, Azure AD, Auth0, or any OIDC provider
- **Role-Based Access Control** - Admins, Stewards, and Users with appropriate permissions
- **Audit Logging** - Complete history of all changes with attribution
- **IT Infrastructure Mapping** - Link decisions to applications, servers, databases
- **Spaces & Organization** - Organize decisions into projects or team spaces
- **Email Notifications** - Subscribe to decision updates
- **Self-Hosted** - Run on your own infrastructure with SQLite or PostgreSQL
- **Public Releases** - Versioned Docker images published to GitHub Container Registry

### Enterprise Edition

The Enterprise Edition adds:

- Slack integration with slash commands and notifications
- Microsoft Teams bot and notifications
- Google OAuth authentication
- AI-powered decision assistance
- PostHog analytics integration
- Priority support

[Contact us](mailto:enterprise@decisionrecords.org) for Enterprise licensing.

## Releases

Community Edition release artifacts are published from this repository as:

- GitHub Releases: [DecisionRecordsORG/DecisionRecords releases](https://github.com/DecisionRecordsORG/DecisionRecords/releases)
- Container images: `ghcr.io/decisionrecordsorg/decisionrecords`

Example:

```bash
docker pull ghcr.io/decisionrecordsorg/decisionrecords:latest
```

For a pinned install, prefer a version tag such as `v2.2.0` once that release is published.

## Installation

### Docker (Recommended)

```bash
# Quick start with SQLite
docker-compose up -d

# With PostgreSQL
docker-compose --profile postgres up -d
```

### Manual Installation

```bash
# Install Python dependencies (every package is pinned, including the gunicorn production server)
pip install -r requirements.txt

# Install and build the Community frontend
# (the default build configuration needs the private ee/ modules and fails without them)
cd frontend && npm ci && npm run build -- --configuration=community && cd ..

# Set environment variables
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export MASTER_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
export DATABASE_URL=sqlite:///instance/decisions.db

# Run
gunicorn --bind 0.0.0.0:5000 app:app
```

See [docs/self-hosting.md](docs/self-hosting.md) for detailed deployment instructions.

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | Required |
| `MASTER_PASSWORD` | Bootstrap super admin password | Required for self-hosted setup |
| `DATABASE_URL` | Database connection string | `sqlite:///decisions.db` |
| `DECISION_RECORDS_EDITION` | `community` or `enterprise` | `community` |

## Decision Record Format

Every decision record has the same fields:

- **Title** - Short name for the decision
- **Status** - `proposed`, `accepted`, `archived`, or `superseded`
- **Context** - What prompted the decision: the situation, the problem, and what limits the options
- **Decision** - What was decided, stated plainly ("We will...")
- **Consequences** - What follows from the decision: benefits, costs, and accepted risks

Each tenant gets a short prefix, so decisions have IDs such as `XYZ-001` that people can quote.

### For software teams: ADRs and arc42

The format is the Architecture Decision Record (ADR) format described by Michael Nygard: Title, Status, Context, Decision, Consequences. A decision record in this tool is an ADR, and the statuses cover the usual ADR lifecycle (`archived` takes the place of "deprecated").

[arc42](https://arc42.org/) reserves section 9, "Architecture Decisions", for exactly these records. Teams that document with arc42 can keep their decisions here and refer to them from section 9 by ID.

The Software Delivery, Data & Analytics, Security & Risk, and Operations & Service relationship packs add relationship classes such as "implements", "blocks", and "mitigates" for technical decisions.

## Authentication

### Passkeys (WebAuthn)

Passwordless authentication using device biometrics or security keys:
- Face ID, Touch ID, Windows Hello, or hardware keys
- Phishing-resistant
- No passwords to manage

### Single Sign-On (OIDC)

Enterprise authentication with any OIDC provider:
- Google Workspace
- Microsoft Azure AD
- Okta
- Auth0
- Any OIDC-compliant provider

## Project Structure

```
decision-records/
├── app.py                 # Flask application
├── models.py              # Database models
├── auth.py                # Authentication
├── feature_flags.py       # Edition feature flags
├── requirements.txt       # Core Python dependencies
├── Dockerfile.community   # Community Edition build
├── docker-compose.yml     # Self-hosting configuration
├── frontend/              # Angular frontend
│   └── src/app/
│       ├── components/    # UI components
│       └── services/      # API services
├── ee/                    # Private Enterprise submodule (optional checkout)
└── docs/                  # Documentation
```

## Troubleshooting

### Reset Database (Fresh Start)

To completely reset the application to a fresh state:

```bash
# Stop container and remove data volume
docker-compose down -v

# Remove cached images (optional, for clean rebuild)
docker system prune -f

# Rebuild and start fresh
docker-compose build --no-cache app
docker-compose up -d
```

### Clear Browser Cache

If you see stale UI after an update:
1. Hard refresh: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows/Linux)
2. Or clear browser cache and reload

### Port Already in Use

```bash
# Find and kill process using port 3000
lsof -i :3000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Then restart
docker-compose up -d
```

### Check Container Logs

```bash
docker-compose logs -f app
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the [Business Source License 1.1](LICENSE).

**Key terms:**
- Free for internal/self-hosted use
- Cannot offer as a competing hosted service
- Converts to Apache 2.0 after 4 years

The `ee/` directory is a private Enterprise repository/submodule and is not part of the public Community Edition distribution.

## Support

- [GitHub Issues](https://github.com/DecisionRecordsORG/DecisionRecords/issues) - Bug reports and feature requests
- [Documentation](docs/) - Guides and references
- [Enterprise Support](mailto:enterprise@decisionrecords.org) - Priority support for Enterprise customers

## Acknowledgments

- [Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) - ADR format creator
- [arc42](https://arc42.org/) - Architecture documentation template
- The open source community

---

Made with care by the Decision Records team
