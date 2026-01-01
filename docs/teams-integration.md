# Microsoft Teams Integration Guide

Decision Records integrates with Microsoft Teams to help your team manage architecture decisions directly from where they communicate.

## Features

- **Bot Commands**: Mention `@DecisionRecords` to open an interactive menu or use commands like `@DecisionRecords create`
- **Message Extensions**: Create decisions from the compose box or from any message using the "..." menu
- **Adaptive Cards**: Rich, interactive cards for viewing and creating decisions
- **Notifications**: Get notified in Teams channels when decisions are created or status changes
- **Auto-linking**: Team members are automatically linked by UPN or email
- **Dedicated Link Page**: Clean account linking flow for users coming from Teams

## Prerequisites

1. You must be a **tenant admin** to install the Teams integration
2. Commercial features must be enabled (`COMMERCIAL_FEATURES_ENABLED=true`)
3. Azure resources must be configured:
   - Azure Bot (Single-Tenant)
   - Azure AD App Registration
4. Teams credentials must be configured in Azure Key Vault:
   - `teams-bot-app-id`
   - `teams-bot-app-secret`
   - `teams-bot-tenant-id`

## Installation

### Option A: Connect from Decision Records (Recommended)

1. Go to **Settings** in Decision Records (or navigate to `/{your-domain}/admin`)
2. Click the **Teams** tab
3. Read the guidance on what happens when you click "Connect with Microsoft Teams"
4. Click **Connect with Microsoft Teams**
5. Sign in with your Microsoft 365 admin account
6. Grant the required permissions (admin consent)
7. You'll be redirected back to Settings with the Teams tab selected and a success message
8. Refresh the page if the connection status doesn't update immediately

### Option B: Install from Teams App Store

If your IT team installed the app from the Teams App Store or Admin Center:

1. The app is installed in Teams but not yet linked to Decision Records
2. Go to **Settings** → **Teams** tab in Decision Records
3. Click **Connect with Microsoft Teams** to complete the OAuth consent flow
4. The integration will be linked to your organization

### Step 2: Configure Notifications

After installation:

1. Select a **default notification channel** from the dropdown
   - Shows channels from Teams where the bot is installed
2. Enable/disable notification types:
   - **New decisions**: Notify when a decision is created
   - **Status changes**: Notify when a decision status changes
3. Click **Save Settings**

### Step 3: Test the Integration

1. Click **Send Test Notification**
2. Check your selected Teams channel for the test message

## Using the Interactive Menu

The easiest way to use Decision Records in Teams is the interactive menu:

1. Mention `@DecisionRecords` in any channel or chat (no command needed)
2. An interactive Adaptive Card appears with buttons:
   - **Create Decision** - Opens the create decision task module
   - **List Decisions** - Shows recent decisions from your organization
   - **My Decisions** - Shows decisions you own or created
3. Click any button to perform that action

This is perfect for users who prefer clicking over typing commands.

## Using Bot Commands

For power users, mention the bot followed by a command:

| Command | Description | Example |
|---------|-------------|---------|
| `@DecisionRecords` | Open interactive menu with buttons | `@DecisionRecords` |
| `@DecisionRecords help` | Show available commands | `@DecisionRecords help` |
| `@DecisionRecords create` | Open task module to create a decision | `@DecisionRecords create` |
| `@DecisionRecords list` | List recent decisions | `@DecisionRecords list` |
| `@DecisionRecords list [status]` | List decisions by status | `@DecisionRecords list accepted` |
| `@DecisionRecords view <id>` | View a specific decision | `@DecisionRecords view 42` |
| `@DecisionRecords search <query>` | Search decisions | `@DecisionRecords search authentication` |

### Valid Statuses
- `proposed`
- `accepted`
- `archived`
- `superseded`

## Using Message Extensions

### Create Decision from Compose Box

1. Click the **...** (More actions) button in the message compose area
2. Select **Decision Records** → **Create Decision**
3. A task module opens with the decision form
4. Fill in the details and click **Create**

### Create Decision from Message

1. Click the **...** (More actions) on any message
2. Select **Create Decision** under Decision Records
3. The message content is used as context for the decision
4. Complete the form and click **Create**

### Search Decisions

1. Click the **...** (More actions) button in the message compose area
2. Select **Decision Records** → **Search Decisions**
3. Type your search query
4. Select a decision to insert a card into the conversation

## Creating Decisions from Teams

### Using the Create Command

1. Mention `@DecisionRecords create` in any channel
2. A task module opens with the following fields:
   - **Title** (required): What is this decision about?
   - **Context**: The background and forces at play
   - **Decision**: The decision that was made
   - **Consequences**: What follows from this decision
   - **Status**: Proposed, Accepted, Archived, or Superseded
   - **Decision Owner**: Select a team member to own this decision
3. Click **Create**

### Decision Creation Feedback

After creating a decision, you receive:

1. **Confirmation Card**: A card is posted showing:
   - Decision ID (e.g., `DRS-042`)
   - Decision title and status
   - Owner (if assigned)
   - Link to view the decision in Decision Records

2. **Channel Notification**: If enabled, a notification is posted to your configured Teams channel

3. **Owner Notification**: If you assigned an owner (different from yourself), they receive a personal chat message with:
   - Notice they've been assigned as owner
   - Decision ID and title
   - Context preview
   - Link to view the full decision

### Decision Owner Field

When creating a decision via Teams, you can assign an owner:

- Select any Teams user from the dropdown
- The system automatically links the owner to their Decision Records account if:
  - They've already linked their Teams account, OR
  - Their Teams email/UPN matches a Decision Records user
- If the owner isn't in Decision Records, their email is stored for future linking
- Owners receive immediate Teams notification when assigned

## User Account Linking

### Automatic Linking

When users interact with Decision Records via Teams, the system attempts to auto-link by:

1. **UPN Match**: If the user's User Principal Name (UPN) matches a Decision Records email
2. **Email Match**: If the Teams email matches a Decision Records email

### Manual Linking

If auto-linking fails:

1. Click the **Link Account** button in the interactive menu
2. You're redirected to a secure linking page
3. Sign in to Decision Records (or create an account)
4. Click **Link Account** to complete the connection
5. Return to Teams - you're now linked!

### Link Status

- **Linked**: Full access to create and view decisions
- **Not Linked**: You can view public information but must link to create decisions

## Azure Configuration

### Azure Bot Setup (Single-Tenant)

1. Create an Azure Bot resource with "Single Tenant" type
2. Note the Bot ID (same as Azure AD App ID)
3. Enable the Microsoft Teams channel

### Azure AD App Registration

1. Create a new app registration (or use the one created with the bot)
2. Set supported account types to "Single tenant"
3. Add redirect URIs:
   - `https://your-domain.com/api/teams/oauth/callback`
   - `https://token.botframework.com/.auth/web/redirect`
4. Configure API permissions:
   - `User.Read` (delegated)
5. Expose an API: `api://your-domain.com/{app-id}`
6. Create a client secret

### Key Vault Secrets

Add the following secrets to Azure Key Vault:

| Secret Name | Value |
|-------------|-------|
| `teams-bot-app-id` | Azure AD Application (client) ID |
| `teams-bot-app-secret` | Azure AD client secret |
| `teams-bot-tenant-id` | Azure AD tenant ID |

## Troubleshooting

### Bot Not Responding

1. Verify the bot is installed in your Teams workspace
2. Check that the bot endpoint URL is correct
3. Verify Azure Bot service health

### OAuth Consent Failed

1. Ensure you're signing in with a Microsoft 365 admin account
2. Check that admin consent is granted for the required permissions
3. Verify the redirect URI matches exactly

### Notifications Not Working

1. Verify a default channel is selected in Settings
2. Ensure the bot is added to the target channel
3. Check that notifications are enabled

### Users Can't Link Accounts

1. Verify their Teams email matches their Decision Records email
2. Have them use the manual linking flow
3. Check the Teams workspace is connected to the correct Decision Records tenant

## Security

The Teams integration uses:

- **JWT Bearer Token Validation**: All bot requests are validated against Bot Framework
- **Azure AD OAuth 2.0**: Secure consent flow for workspace connection
- **Fernet Encryption**: State and link tokens are encrypted at rest
- **Minimal Permissions**: Only required Graph API permissions are requested

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/teams/webhook` | POST | Bot Framework activity handler |
| `/api/teams/oauth/start` | GET | Start Azure AD OAuth consent |
| `/api/teams/oauth/callback` | GET | Handle OAuth callback |
| `/api/teams/settings` | GET/PUT | Manage Teams settings |
| `/api/teams/disconnect` | POST | Disconnect Teams workspace |
| `/api/teams/channels` | GET | List available channels |
| `/api/teams/test` | POST | Send test notification |
| `/api/teams/link/initiate` | GET | Start user account linking |
| `/api/teams/link/validate` | POST | Validate link token |
| `/api/teams/link/complete` | POST | Complete account linking |

## Feature Comparison: Slack vs Teams

| Feature | Slack | Teams |
|---------|-------|-------|
| Interactive Menu | `/decision` | `@DecisionRecords` |
| Create Command | `/decision create` | `@DecisionRecords create` |
| Message Shortcuts | Yes (context menu) | Yes (message extensions) |
| Global Shortcuts | Yes (compose menu) | Yes (compose extensions) |
| Channel Notifications | Yes | Yes |
| Auto-link by Email | Yes | Yes (+ UPN) |
| OAuth Authentication | HMAC-SHA256 | JWT Bearer Token |
| Card Format | Block Kit | Adaptive Cards |
