# Architecture Decisions

A self-hosted web application for managing Architecture Decision Records (ADRs) based on the [arc42 Section 9](https://docs.arc42.org/section-9/) format with enterprise features.

## Features

- **ADR Management**: Create, view, update, and delete architecture decisions
- **Complete History**: Track full update history for each decision with user attribution
- **SSO Authentication**: OpenID Connect (OIDC) integration for enterprise Single Sign-On
- **Multi-Tenancy**: Domain-based isolation ensures organizations only see their own decisions
- **User Tracking**: Know who created, modified, or deleted each decision
- **Email Notifications**: Subscribe to receive email alerts for new or updated decisions
- **Search & Filter**: Find decisions by keyword or status
- **Self-Hosted**: SQLite database for easy deployment with no external dependencies

## ADR Format

Each Architecture Decision Record follows the Michael Nygard format:

- **Title**: Short noun phrase describing the decision
- **Status**: `proposed`, `accepted`, `deprecated`, or `superseded`
- **Context**: Describes the forces at play (technological, political, social, project local)
- **Decision**: The response to the forces, stated in active voice (e.g., "We will...")
- **Consequences**: Resulting context after applying the decision (positive, negative, neutral)

## Installation

### Option 1: Docker (Recommended)

The easiest way to run the application:

```bash
# Clone the repository
git clone <repository-url>
cd architecture-decisions

# Run with Docker Compose
docker compose up -d

# Or build and run with Docker directly
docker build -t architecture-decisions .
docker run -d -p 5000:5000 -v adr-data:/data architecture-decisions
```

Open your browser and navigate to `http://localhost:5000`

To stop the container:
```bash
docker compose down
```

### Option 2: Python

Requirements:
- Python 3.8+
- pip

Setup:

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd architecture-decisions
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Open your browser and navigate to `http://localhost:5000`

## Configuration

The application can be configured using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite database path | `sqlite:///architecture_decisions.db` |
| `SECRET_KEY` | Flask secret key | Auto-generated |

Example:
```bash
export DATABASE_URL="sqlite:///path/to/your/database.db"
export SECRET_KEY="your-secure-secret-key"
python app.py
```

## SSO Configuration

The application supports OpenID Connect (OIDC) for authentication. Configure SSO through the admin settings page (`/settings`).

### Setting Up SSO

1. Register your application with your identity provider (Google, Okta, Azure AD, etc.)
2. Set the callback URL to: `https://your-domain.com/auth/callback`
3. Log in as the first user (becomes admin automatically)
4. Navigate to Settings > SSO Configuration
5. Add your provider details:
   - **Domain**: Email domain for your organization (e.g., `company.com`)
   - **Provider Name**: Display name (e.g., "Google Workspace")
   - **Client ID**: From your identity provider
   - **Client Secret**: From your identity provider
   - **Discovery URL**: OIDC discovery endpoint

### Common Discovery URLs

| Provider | Discovery URL |
|----------|---------------|
| Google | `https://accounts.google.com/.well-known/openid-configuration` |
| Azure AD | `https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration` |
| Okta | `https://{domain}.okta.com/.well-known/openid-configuration` |

## Multi-Tenancy

The application provides domain-based multi-tenancy:

- Users can only see decisions from their own organization (SSO domain)
- Each organization has independent data isolation
- The first user from a domain becomes an administrator
- Administrators can manage SSO and email settings for their domain

## Email Notifications

Users can subscribe to receive email notifications for:

- **New Decisions**: When a new ADR is created
- **Status Changes**: When a decision's status changes
- **All Updates**: Any modification to a decision

Configure SMTP settings in the admin Settings page to enable email notifications.

## API Endpoints

All API endpoints require authentication via session cookie.

### Decisions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/decisions` | List all decisions (filtered by domain) |
| `POST` | `/api/decisions` | Create a new decision |
| `GET` | `/api/decisions/<id>` | Get a decision with history |
| `PUT` | `/api/decisions/<id>` | Update a decision |
| `DELETE` | `/api/decisions/<id>` | Soft-delete a decision |
| `GET` | `/api/decisions/<id>/history` | Get decision history |

### User

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/user/me` | Get current user info |
| `GET` | `/api/user/subscription` | Get notification preferences |
| `PUT` | `/api/user/subscription` | Update notification preferences |

### Admin (requires admin role)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/sso` | List SSO configurations |
| `POST` | `/api/admin/sso` | Create SSO configuration |
| `PUT` | `/api/admin/sso/<id>` | Update SSO configuration |
| `DELETE` | `/api/admin/sso/<id>` | Delete SSO configuration |
| `GET` | `/api/admin/email` | Get email configuration |
| `POST` | `/api/admin/email` | Create/update email configuration |
| `POST` | `/api/admin/email/test` | Send test email |
| `GET` | `/api/admin/users` | List users in domain |

## Project Structure

```
architecture-decisions/
├── app.py              # Flask application and routes
├── models.py           # SQLAlchemy database models
├── auth.py             # Authentication helpers
├── notifications.py    # Email notification service
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker image definition
├── docker-compose.yml  # Docker Compose configuration
├── README.md           # This file
├── templates/          # HTML templates
│   ├── base.html       # Base template with navigation
│   ├── login.html      # SSO login page
│   ├── index.html      # Decision list page
│   ├── decision.html   # Decision view/edit page
│   ├── settings.html   # Admin settings page
│   ├── profile.html    # User profile/subscriptions
│   └── error.html      # Error page
└── static/             # Static assets
    ├── css/
    │   └── style.css   # Custom styles
    └── js/
        └── app.js      # JavaScript utilities
```

## License

MIT License
