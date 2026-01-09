# Decision Records

> Open source platform for capturing and preserving architecture decisions

[![License](https://img.shields.io/badge/license-BSL%201.1-blue)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](docker-compose.yml)

Decision Records helps teams remember why decisions were made. Based on the [Architecture Decision Records (ADR)](https://adr.github.io/) format, it provides a collaborative platform for documenting technical decisions with their context, rationale, and consequences.

## Quick Start

```bash
# Clone and run with Docker
git clone https://github.com/decisionrecords/decision-records.git
cd decision-records
docker-compose up -d

# Open http://localhost:3000
```

Default admin: `admin` / `changeme` (change immediately!)

## Features

### Community Edition (Free & Open Source)

- **Architecture Decision Records** - Create and manage ADRs with the proven format: Context, Decision, Consequences
- **Multi-Tenant** - Each organization gets isolated workspace based on email domain
- **Passkey Authentication** - Secure passwordless login with WebAuthn/FIDO2
- **SSO/OIDC Integration** - Connect with Okta, Azure AD, Auth0, or any OIDC provider
- **Role-Based Access Control** - Admins, Stewards, and Users with appropriate permissions
- **Audit Logging** - Complete history of all changes with attribution
- **IT Infrastructure Mapping** - Link decisions to applications, servers, databases
- **Spaces & Organization** - Organize decisions into projects or team spaces
- **Email Notifications** - Subscribe to decision updates
- **Self-Hosted** - Run on your own infrastructure with SQLite or PostgreSQL

### Enterprise Edition

The Enterprise Edition adds:

- Slack integration with slash commands and notifications
- Microsoft Teams bot and notifications
- Google OAuth authentication
- AI-powered decision assistance
- PostHog analytics integration
- Priority support

[Contact us](mailto:enterprise@decisionrecords.org) for Enterprise licensing.

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
# Install Python dependencies
pip install -r requirements.txt

# Install and build frontend
cd frontend && npm ci && npm run build && cd ..

# Set environment variables
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export DATABASE_URL=sqlite:///instance/decisions.db

# Run
gunicorn --bind 0.0.0.0:5000 app:app
```

See [docs/self-hosting.md](docs/self-hosting.md) for detailed deployment instructions.

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | Required |
| `DATABASE_URL` | Database connection string | `sqlite:///decisions.db` |
| `DECISION_RECORDS_EDITION` | `community` or `enterprise` | `community` |

## ADR Format

Each decision follows the Michael Nygard format:

- **Title** - Short description of the decision
- **Status** - `proposed`, `accepted`, `deprecated`, or `superseded`
- **Context** - The forces at play (technical, political, social)
- **Decision** - What was decided, in active voice ("We will...")
- **Consequences** - Results of the decision (positive, negative, neutral)

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
├── ee/                    # Enterprise Edition (proprietary)
│   ├── backend/           # EE backend modules
│   └── frontend/          # EE frontend components
└── docs/                  # Documentation
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the [Business Source License 1.1](LICENSE).

**Key terms:**
- Free for internal/self-hosted use
- Cannot offer as a competing hosted service
- Converts to Apache 2.0 after 4 years

The `/ee` directory contains proprietary Enterprise Edition code under a [separate license](ee/LICENSE).

## Support

- [GitHub Issues](https://github.com/decisionrecords/decision-records/issues) - Bug reports and feature requests
- [Documentation](docs/) - Guides and references
- [Enterprise Support](mailto:enterprise@decisionrecords.org) - Priority support for Enterprise customers

## Acknowledgments

- [Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) - ADR format creator
- [arc42](https://arc42.org/) - Architecture documentation template
- The open source community

---

Made with care by the Decision Records team
