# Architecture Decisions

A self-hosted web application for managing Architecture Decision Records (ADRs) based on the [arc42 Section 9](https://docs.arc42.org/section-9/) format with enterprise features.

## Features

- **Modern Angular UI**: Built with Angular 18 and Angular Material for a responsive, professional interface
- **ADR Management**: Create, view, update, and delete architecture decisions
- **Complete History**: Track full update history for each decision with user attribution
- **SSO Authentication**: OpenID Connect (OIDC) integration for enterprise Single Sign-On
- **Multi-Tenancy**: Domain-based isolation ensures organizations only see their own decisions
- **User Tracking**: Know who created, modified, or deleted each decision
- **Email Notifications**: Subscribe to receive email alerts for new or updated decisions
- **Search & Filter**: Find decisions by keyword or status with real-time filtering
- **Master Account**: Local admin account for initial setup and system configuration
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

Default master account credentials:
- **Username**: `admin`
- **Password**: `changeme`

To stop the container:
```bash
docker compose down
```

### Option 2: Local Development

Requirements:
- Python 3.8+
- Node.js 18+ (for frontend development)
- npm

#### Backend Setup

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

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

#### Frontend Setup

4. Install Angular CLI and dependencies:
   ```bash
   cd frontend
   npm install
   ```

5. Build the Angular frontend:
   ```bash
   npm run build
   ```

6. Run the application:
   ```bash
   cd ..
   python app.py
   ```

7. Open your browser and navigate to `http://localhost:5000`

### Frontend Development Mode

For active frontend development with hot reload:

1. Start the Flask backend:
   ```bash
   python app.py
   ```

2. In a separate terminal, start the Angular dev server:
   ```bash
   cd frontend
   npm start
   ```

3. Access the Angular dev server at `http://localhost:4200`

Note: Configure a proxy in `frontend/proxy.conf.json` to forward API calls to the Flask backend.

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

## Master Account

The application includes a built-in master account for system administration:

- **Default Username**: `admin`
- **Default Password**: `changeme`

The master account can:
- Configure SSO providers for any domain
- Configure email settings for any domain
- View all decisions across all domains (read-only)
- Manage user admin privileges

**Important**: Change the default password immediately after first login!

## SSO Configuration

The application supports OpenID Connect (OIDC) for authentication. Configure SSO through the admin settings page (`/settings`).

### Setting Up SSO

1. Register your application with your identity provider (Google, Okta, Azure AD, etc.)
2. Set the callback URL to: `https://your-domain.com/auth/callback`
3. Log in with the master account
4. Navigate to Settings > SSO Providers
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
- Master account can view all domains but cannot create/modify decisions

## Email Notifications

Users can subscribe to receive email notifications for:

- **New Decisions**: When a new ADR is created
- **Status Changes**: When a decision's status changes
- **All Updates**: Any modification to a decision

Configure SMTP settings in the admin Settings page to enable email notifications.

## API Endpoints

All API endpoints require authentication via session cookie.

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/auth/sso-configs` | List available SSO providers |
| `POST` | `/auth/local` | Local master account login |
| `GET` | `/auth/sso/<id>` | Initiate SSO login flow |
| `GET` | `/logout` | Log out current session |

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

### Master Account

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/api/master/password` | Change master account password |
| `GET` | `/api/master/info` | Get master account info |

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
| `PUT` | `/api/admin/users/<id>/admin` | Toggle user admin status |

## Project Structure

```
architecture-decisions/
├── app.py                  # Flask application and API routes
├── models.py               # SQLAlchemy database models
├── auth.py                 # Authentication helpers and decorators
├── notifications.py        # Email notification service
├── requirements.txt        # Python dependencies
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Docker Compose configuration
├── README.md               # This file
├── templates/              # Legacy HTML templates (fallback)
├── static/                 # Legacy static assets (fallback)
└── frontend/               # Angular frontend application
    ├── src/
    │   ├── app/
    │   │   ├── components/     # Angular components
    │   │   │   ├── login/
    │   │   │   ├── decision-list/
    │   │   │   ├── decision-detail/
    │   │   │   ├── settings/
    │   │   │   ├── profile/
    │   │   │   ├── master-profile/
    │   │   │   └── shared/
    │   │   ├── services/       # API services
    │   │   │   ├── auth.service.ts
    │   │   │   ├── decision.service.ts
    │   │   │   └── admin.service.ts
    │   │   ├── guards/         # Route guards
    │   │   ├── models/         # TypeScript interfaces
    │   │   ├── app.routes.ts   # Application routing
    │   │   └── app.config.ts   # App configuration
    │   └── styles.scss         # Global styles
    ├── angular.json            # Angular CLI configuration
    ├── package.json            # Node.js dependencies
    └── tsconfig.json           # TypeScript configuration
```

## Running Tests

### Frontend Unit Tests

```bash
cd frontend
npm test
```

### Backend Tests

```bash
python -m pytest tests/
```

## Technology Stack

- **Backend**: Python 3.11, Flask, SQLAlchemy, Authlib
- **Frontend**: Angular 18, Angular Material, TypeScript
- **Database**: SQLite
- **Authentication**: OpenID Connect (OIDC)
- **Containerization**: Docker with multi-stage builds

## License

MIT License
