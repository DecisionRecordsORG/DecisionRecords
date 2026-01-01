# Microsoft Teams Integration Plan

## Executive Summary

This document provides a detailed implementation plan for adding Microsoft Teams integration to the Decision Records application, mirroring the existing Slack integration architecture.

**Key 2025 Considerations:**
- Multi-tenant bot creation deprecated after July 31, 2025 - use Single-Tenant or User-Assigned Managed Identity
- Bot Framework SDK support ends December 31, 2025 - plan migration to Microsoft 365 Agents SDK
- Office 365 Connectors retirement extended to March 31, 2026 - use Bot-based notifications

---

## 1. Architecture Overview

### Slack vs Teams Architecture Mapping

| Slack Concept | Teams Equivalent | Technical Implementation |
|--------------|------------------|--------------------------|
| Slack App | Teams App | App manifest JSON + Azure Bot |
| Bot Token (xoxb-) | Azure AD Access Token | Single-tenant app registration |
| Slash Commands (/decision) | Bot Commands (@DecisionRecords) | Message activity handler |
| Block Kit | Adaptive Cards | JSON-based card format |
| Modals | Task Modules / Dialogs | Adaptive Cards with Action.Submit |
| Message Shortcuts | Message Extensions (Action) | composeExtensions in manifest |
| Global Shortcuts | Message Extensions (Action) | compose/commandBox context |
| App Home Tab | Personal Tab / Bot Welcome | Static tab + proactive messaging |
| OAuth State (Fernet) | Azure AD OAuth + encrypted state | Same pattern with MSAL |
| HMAC-SHA256 verification | JWT Bearer token validation | Bot Framework authentication |
| Incoming Webhooks | Bot proactive messages | Conversation references stored |

### High-Level Architecture

```
                    Microsoft Teams
                          |
                          v
                 Azure Bot Service (Single-Tenant)
                          |
                          v
    +---------------------|-------------------+
    |                     |                   |
    v                     v                   v
Bot Endpoint      OAuth Callback      Tab Content
/api/teams/       /api/teams/         /teams/
webhook           oauth/callback      tab/*
    |                     |
    +----------+----------+
               |
               v
        teams_service.py
               |
    +----------+----------+
    |          |          |
    v          v          v
teams_       models.py   Decision
security.py  (Teams      Records
             Models)     API
```

---

## 2. File Structure

### New Files to Create

```
/architecture-decisions/
├── teams_service.py          # Main Teams service class (~1500 lines)
├── teams_security.py         # Token validation, encryption (~300 lines)
├── teams_cards.py            # Adaptive Card builders (~400 lines)
├── teams-app-manifest.json   # Teams app manifest
├── teams-app-manifest-dev.json # Dev environment manifest
│
├── frontend/src/app/components/
│   ├── teams-integration/    # Marketing/landing page
│   │   ├── teams-integration.component.ts
│   │   ├── teams-integration.component.html
│   │   └── teams-integration.component.scss
│   ├── teams-installed/      # Post-installation success page
│   │   └── teams-installed.component.ts
│   └── teams-link-account/   # Account linking flow
│       └── teams-link-account.component.ts
│
├── e2e/tests/
│   ├── teams-settings.spec.ts
│   └── teams-oidc.spec.ts
│
├── tests/
│   ├── test_teams.py
│   └── test_teams_security.py
│
└── docs/
    └── teams-integration.md
```

### Modifications to Existing Files

| File | Changes Required |
|------|------------------|
| `models.py` | Add TeamsWorkspace, TeamsUserMapping, TeamsConversationReference models |
| `app.py` | Add Teams API endpoints (~400 lines of routes) |
| `keyvault_client.py` | Add methods for Teams secrets |
| `frontend/src/app/app.routes.ts` | Add Teams routes |
| `requirements.txt` | Add `botbuilder-core`, `msal`, `botbuilder-integration-aiohttp` |

---

## 3. Database Models

### TeamsWorkspace Model

```python
class TeamsWorkspace(db.Model):
    """Microsoft Teams workspace (tenant) installation for a Decision Records tenant."""

    __tablename__ = 'teams_workspaces'

    STATUS_PENDING_CONSENT = 'pending_consent'
    STATUS_ACTIVE = 'active'
    STATUS_DISCONNECTED = 'disconnected'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, unique=True, index=True)

    # Azure AD / Microsoft 365 tenant info
    ms_tenant_id = db.Column(db.String(50), nullable=False, unique=True, index=True)
    ms_tenant_name = db.Column(db.String(255), nullable=True)

    # Service URL for proactive messaging
    service_url = db.Column(db.String(500), nullable=True)

    # Bot installation info
    bot_id = db.Column(db.String(100), nullable=True)

    # Status tracking
    status = db.Column(db.String(20), default=STATUS_PENDING_CONSENT)
    consent_granted_at = db.Column(db.DateTime, nullable=True)
    consent_granted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Notification settings
    default_channel_id = db.Column(db.String(100), nullable=True)
    default_channel_name = db.Column(db.String(255), nullable=True)
    default_team_id = db.Column(db.String(100), nullable=True)
    default_team_name = db.Column(db.String(255), nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True)
    notify_on_create = db.Column(db.Boolean, default=True)
    notify_on_status_change = db.Column(db.Boolean, default=True)

    # State
    is_active = db.Column(db.Boolean, default=True)
    installed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity_at = db.Column(db.DateTime, nullable=True)

    # App version tracking
    app_version = db.Column(db.String(20), nullable=True)
```

### TeamsUserMapping Model

```python
class TeamsUserMapping(db.Model):
    """Maps Teams users to Decision Records platform users."""

    __tablename__ = 'teams_user_mappings'

    id = db.Column(db.Integer, primary_key=True)
    teams_workspace_id = db.Column(db.Integer, db.ForeignKey('teams_workspaces.id'), nullable=False, index=True)

    # Azure AD user identifiers
    aad_object_id = db.Column(db.String(50), nullable=False, index=True)
    aad_user_principal_name = db.Column(db.String(320), nullable=True)
    aad_email = db.Column(db.String(320), nullable=True)
    aad_display_name = db.Column(db.String(255), nullable=True)

    # Linked Decision Records user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # How the user was linked
    link_method = db.Column(db.String(20), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    linked_at = db.Column(db.DateTime, nullable=True)
```

### TeamsConversationReference Model

```python
class TeamsConversationReference(db.Model):
    """Stores conversation references for proactive messaging."""

    __tablename__ = 'teams_conversation_references'

    id = db.Column(db.Integer, primary_key=True)
    teams_workspace_id = db.Column(db.Integer, db.ForeignKey('teams_workspaces.id'), nullable=False, index=True)

    conversation_id = db.Column(db.String(500), nullable=False)
    channel_id = db.Column(db.String(100), nullable=True)
    team_id = db.Column(db.String(100), nullable=True)
    reference_json = db.Column(db.Text, nullable=False)
    context_type = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
```

---

## 4. API Endpoints

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/api/teams/webhook` | POST | Bot Framework activity handler | Bot auth (JWT) |
| `/api/teams/oauth/start` | GET | Start Azure AD OAuth consent flow | Login + Admin |
| `/api/teams/oauth/callback` | GET | Handle OAuth callback | None (state validated) |
| `/api/teams/settings` | GET | Get Teams settings for tenant | Login + Admin |
| `/api/teams/settings` | PUT | Update Teams notification settings | Login + Admin |
| `/api/teams/disconnect` | POST | Disconnect Teams workspace | Login + Admin |
| `/api/teams/channels` | GET | List available Teams/channels | Login + Admin |
| `/api/teams/test` | POST | Send test notification | Login + Admin |
| `/api/teams/link/initiate` | GET | Start user account linking | Link token |
| `/api/teams/link/complete` | POST | Complete account linking | Login |

---

## 5. Teams App Manifest

```json
{
    "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.24/MicrosoftTeams.schema.json",
    "manifestVersion": "1.24",
    "version": "1.0.0",
    "id": "{{BOT_APP_ID}}",
    "name": {
        "short": "Decision Records",
        "full": "Decision Records - Architecture Decision Management"
    },
    "bots": [
        {
            "botId": "{{BOT_APP_ID}}",
            "scopes": ["personal", "team", "groupChat"],
            "commandLists": [
                {
                    "commands": [
                        { "title": "create", "description": "Create a new decision" },
                        { "title": "list", "description": "List recent decisions" },
                        { "title": "search", "description": "Search decisions" },
                        { "title": "view", "description": "View a decision by ID" },
                        { "title": "help", "description": "Show available commands" }
                    ]
                }
            ]
        }
    ],
    "composeExtensions": [
        {
            "botId": "{{BOT_APP_ID}}",
            "commands": [
                {
                    "id": "createDecision",
                    "type": "action",
                    "title": "Create Decision",
                    "fetchTask": true,
                    "context": ["compose", "commandBox", "message"]
                },
                {
                    "id": "searchDecisions",
                    "type": "query",
                    "title": "Search Decisions"
                }
            ]
        }
    ]
}
```

---

## 6. Implementation Phases

### Phase 1: Foundation
1. Create database migration for Teams models
2. Create `teams_security.py` with JWT validation and encryption
3. Add Key Vault methods for Teams secrets
4. Create Azure Bot resource (Single-Tenant)
5. Configure Azure AD app registration
6. Add secrets to Key Vault

### Phase 2: Core Bot Functionality
7. Create `teams_cards.py` with basic Adaptive Card builders
8. Create `teams_service.py` skeleton with activity routing
9. Implement `/api/teams/webhook` endpoint
10. Implement help, list, view, search command handlers
11. Build corresponding Adaptive Cards for each command
12. Implement create decision task module (fetch + submit)

### Phase 3: Advanced Features
13. Implement user auto-linking by email/UPN
14. Create `teams-link-account` Angular component
15. Implement browser-based linking flow endpoints
16. Implement message extension for "Create Decision from message"
17. Store conversation references on bot installation
18. Implement proactive notification sending

### Phase 4: Admin UI & Polish
19. Add Teams tab to admin settings component
20. Implement settings GET/PUT endpoints
21. Implement channel selection endpoint
22. Create `teams-integration` marketing page
23. Create `teams-installed` success page
24. Write unit tests and E2E tests

### Phase 5: Documentation & Deployment
25. Create `docs/teams-integration.md` documentation
26. Update Teams app manifest for production
27. Deploy and test end-to-end

---

## 7. Feature Mapping Summary

| Slack Feature | Teams Equivalent | Phase |
|--------------|------------------|-------|
| `/decision` menu | Bot command with Adaptive Card | 2 |
| `/decision create` | Task module form | 2 |
| `/decision list` | Adaptive Card list | 2 |
| `/decision view <id>` | Adaptive Card detail | 2 |
| `/decision search` | Adaptive Card results | 2 |
| Message shortcut | Message extension action | 3 |
| Global shortcut | Compose extension action | 3 |
| App Home tab | Personal tab / Welcome message | 4 |
| Channel notifications | Proactive bot messages | 3 |
| Auto-link by email | Auto-link by UPN/email | 3 |
| Browser auth linking | Browser auth linking | 3 |
| OAuth installation | Azure AD consent flow | 1 |
| Settings UI | Admin panel Teams tab | 4 |

---

## 8. Teams OIDC (Sign in with Microsoft)

### Additional Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/teams-oidc-status` | GET | Check if Teams OIDC is enabled |
| `/auth/teams/oidc` | GET | Start Microsoft OIDC flow |
| `/auth/teams/oidc/callback` | GET | Handle OIDC callback |

### OIDC Flow

1. User clicks "Sign in with Microsoft"
2. Redirect to `/auth/teams/oidc`
3. Generate encrypted state, redirect to Microsoft login
4. User authenticates with Microsoft 365
5. Callback receives authorization code
6. Exchange code for ID token + access token
7. Extract user info (email, name, tenant)
8. Create/login user based on email domain
9. Set session cookie

---

## 9. Azure Resources Required

### New Azure Resources

| Resource | Purpose |
|----------|---------|
| Azure Bot (Single-Tenant) | Bot registration with Teams channel |
| Azure AD App Registration | Authentication for bot and OAuth |

### Key Vault Secrets to Add

| Secret Name | Purpose |
|-------------|---------|
| `teams-bot-app-id` | Azure AD application (client) ID |
| `teams-bot-app-secret` | Azure AD client secret |
| `teams-bot-tenant-id` | Azure AD tenant ID (single-tenant) |

---

## 10. User Preferences Applied

- **Teams OIDC**: Included - "Sign in with Microsoft" feature
- **Bot Type**: Single-Tenant Azure Bot (recommended for 2025+)
- **Scope**: Full feature parity with Slack (all phases)
