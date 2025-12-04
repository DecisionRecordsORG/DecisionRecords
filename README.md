# Architecture Decisions

A self-hosted web application for managing Architecture Decision Records (ADRs) based on the [arc42 Section 9](https://docs.arc42.org/section-9/) format with enterprise features.

## Features

- **Modern Angular UI**: Built with Angular 18 and Angular Material for a responsive, professional interface
- **ADR Management**: Create, view, update, and delete architecture decisions
- **IT Infrastructure Mapping**: Link decisions to applications, servers, databases, networks, and other infrastructure
- **Complete History**: Track full update history for each decision with user attribution
- **Dual Authentication**: Support for both SSO (OpenID Connect) and WebAuthn (Passkeys)
- **Passwordless Login**: Secure passkey-based authentication using device biometrics or security keys
- **Multi-Tenancy**: Domain-based isolation with tenant-specific URLs (e.g., `/{domain}/`)
- **Access Requests**: Users can request access to existing tenants with admin approval workflow
- **User Tracking**: Know who created, modified, or deleted each decision
- **Email Notifications**: Subscribe to receive email alerts for new or updated decisions
- **Search & Filter**: Find decisions by keyword or status with real-time filtering
- **Super Admin Account**: System-wide admin for configuration and oversight
- **Self-Hosted**: SQLite database for easy deployment with no external dependencies

## IT Infrastructure Mapping

Architecture Decisions can be linked to IT infrastructure items to track which systems, applications, or components are affected by each decision. Supported infrastructure types include:

- **Application**: Software applications and systems
- **Network**: Network components and configurations
- **Database**: Databases and data stores
- **Server**: Physical or virtual servers
- **Service**: Backend services and microservices
- **API**: API endpoints and integrations
- **Storage**: File storage and object storage systems
- **Cloud**: Cloud resources and services
- **Container**: Container platforms and orchestration
- **Other**: Any other infrastructure type

When creating or editing a decision, users can:
- Search and select existing infrastructure items
- Create new infrastructure items on the fly
- Associate multiple infrastructure items with a single decision

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

## Super Admin Account

The application includes a built-in super admin account for system administration:

- **Default Username**: `admin`
- **Default Password**: `changeme`
- **Login URL**: `/superadmin`

The super admin can:
- Configure SSO providers for any domain
- Configure email settings for any domain
- Configure authentication methods for any domain
- View all decisions across all domains (read-only)
- Manage user admin privileges

**Important**: Change the default password immediately after first login!

## URL Structure

The application uses tenant-aware URLs for multi-tenant isolation:

| URL Pattern | Description |
|-------------|-------------|
| `/` | Main landing page (signup for new tenants) |
| `/superadmin` | Super admin login page |
| `/superadmin/dashboard` | Super admin dashboard |
| `/superadmin/settings` | System-wide settings |
| `/{domain}/login` | Tenant-specific login page |
| `/{domain}/` | Decision list for tenant |
| `/{domain}/decision/new` | Create new decision |
| `/{domain}/decision/{id}` | View/edit decision |
| `/{domain}/profile` | User profile and passkey management |
| `/{domain}/admin` | Tenant admin settings |

## Authentication

### Authentication Methods

The application supports two authentication methods per tenant:

#### 1. Passkeys (WebAuthn) - Default

Passwordless authentication using device biometrics or security keys:
- Uses device fingerprint, Face ID, Touch ID, or hardware security keys
- Resistant to phishing attacks
- No passwords to remember or manage
- Users can register multiple devices for backup

#### 2. Single Sign-On (SSO)

Enterprise authentication via OpenID Connect:
- Integration with Google, Microsoft, Okta, and other OIDC providers
- Centralized user management through your identity provider
- Requires SSO configuration (see SSO Configuration section)

### Authentication Flow

1. **New User (First from Domain)**:
   - Visit `/` (landing page)
   - Enter email address and name
   - Receive verification email with secure link
   - Click verification link to confirm email ownership
   - User account is created and user becomes tenant administrator
   - Redirect to `/{domain}/login` to register passkey

2. **Existing Tenant User**:
   - Visit `/{domain}/login`
   - Authenticate with passkey or SSO (depending on tenant configuration)

3. **New User Joining Existing Tenant**:
   - Visit `/` and enter email
   - If admin approval is required:
     - User fills in name and optional reason
     - Verification email is sent
     - After email verification, access request is submitted
     - Tenant admin reviews and approves/rejects request
     - Upon approval, user can login via `/{domain}/login`
   - If auto-signup is enabled (admin approval not required):
     - User is redirected to `/{domain}/login` to sign up directly

### Email Verification Security

All new user signups require email verification before access is granted:

- **24-hour expiration**: Verification links expire after 24 hours
- **Rate limiting**: Users must wait 2 minutes between verification email requests
- **Single-use tokens**: Each verification link can only be used once
- **Tenant URL protection**: Tenant login URLs are not revealed until email is verified

This ensures that:
- Only legitimate email owners can join a tenant
- Tenant URLs remain private from unauthorized users
- Spam and abuse are prevented through rate limiting

## Access Requests

When a user tries to sign up with an email domain that already has an existing tenant:

1. **Request Access**: User is prompted to request access from their tenant admin
2. **Provide Reason**: User can optionally explain why they need access
3. **Admin Notification**: Tenant admins see pending requests in their settings
4. **Approval/Rejection**: Admin can approve (creates user account) or reject the request
5. **User Login**: Approved users can sign in using the tenant's configured authentication method

### Managing Access Requests (Admins)

1. Navigate to `/{domain}/admin`
2. Go to the "Access Requests" tab
3. Review pending requests showing:
   - User name and email
   - Reason for requesting access
   - Request date
4. Click ✓ to approve or ✗ to reject each request

### Auto-Signup Configuration

Tenant admins can control whether new users need approval:

1. Navigate to `/{domain}/admin`
2. Go to the "Authentication" tab
3. Toggle "Require admin approval for new users":
   - **Enabled (default)**: New users must request access and wait for admin approval
   - **Disabled**: Users with verified emails from your domain can sign up automatically

This setting only affects users from the same email domain as the tenant.

## SSO Configuration

The application supports OpenID Connect (OIDC) for authentication. Configure SSO through the admin settings.

### Setting Up SSO

1. Register your application with your identity provider (Google, Okta, Azure AD, etc.)
2. Set the callback URL to: `https://your-domain.com/auth/callback`
3. Log in as super admin (`/superadmin`) or tenant admin (`/{domain}/admin`)
4. Navigate to SSO Providers tab
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
| `POST` | `/api/auth/send-verification` | Send email verification link |
| `GET/POST` | `/api/auth/verify-email/<token>` | Verify email token |
| `GET` | `/api/auth/verification-status/<token>` | Check verification status |

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
| `GET` | `/api/admin/auth-config` | Get authentication configuration |
| `POST` | `/api/admin/auth-config` | Create/update auth configuration |
| `GET` | `/api/admin/access-requests` | List all access requests |
| `GET` | `/api/admin/access-requests/pending` | List pending access requests |
| `POST` | `/api/admin/access-requests/<id>/approve` | Approve an access request |
| `POST` | `/api/admin/access-requests/<id>/reject` | Reject an access request |

### WebAuthn (Passkey Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/webauthn/register/begin` | Start passkey registration |
| `POST` | `/api/webauthn/register/complete` | Complete passkey registration |
| `POST` | `/api/webauthn/authenticate/begin` | Start passkey authentication |
| `POST` | `/api/webauthn/authenticate/complete` | Complete passkey authentication |
| `GET` | `/api/webauthn/credentials` | List user's registered passkeys |
| `DELETE` | `/api/webauthn/credentials/<id>` | Delete a passkey |

### IT Infrastructure

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/infrastructure` | List all infrastructure items (filtered by domain) |
| `POST` | `/api/infrastructure` | Create a new infrastructure item |
| `GET` | `/api/infrastructure/<id>` | Get a single infrastructure item |
| `PUT` | `/api/infrastructure/<id>` | Update an infrastructure item |
| `DELETE` | `/api/infrastructure/<id>` | Delete an infrastructure item |
| `GET` | `/api/infrastructure/types` | Get available infrastructure types |

### Tenant Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/auth/tenant/<domain>` | Get tenant status (has users, auth method) |
| `GET` | `/api/auth/user-exists/<email>` | Check if user exists |
| `POST` | `/api/auth/access-request` | Submit access request to join tenant |

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
    │   │   │   ├── landing/           # Main signup page
    │   │   │   ├── tenant-login/      # Tenant-specific login
    │   │   │   ├── superadmin-login/  # Super admin login
    │   │   │   ├── decision-list/
    │   │   │   ├── decision-detail/
    │   │   │   ├── settings/          # Admin settings with access requests
    │   │   │   ├── profile/
    │   │   │   ├── master-profile/
    │   │   │   └── shared/            # Navbar, dialogs, etc.
    │   │   ├── services/       # API services
    │   │   │   ├── auth.service.ts
    │   │   │   ├── decision.service.ts
    │   │   │   └── admin.service.ts
    │   │   ├── guards/         # Route guards (auth, admin, master, tenant)
    │   │   ├── models/         # TypeScript interfaces
    │   │   ├── app.routes.ts   # Tenant-aware routing
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
- **Authentication**: OpenID Connect (OIDC), WebAuthn/FIDO2 (Passkeys)
- **Containerization**: Docker with multi-stage builds

## Author

**Lawrance Nyakiso**

## License

MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2024 Lawrance Nyakiso
