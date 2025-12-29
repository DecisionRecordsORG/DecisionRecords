# Slack Integration Guide

Decision Records integrates with Slack to help your team manage architecture decisions directly from where they communicate.

## Features

- **Slash Commands**: Use `/decision` to open an interactive menu with buttons, or subcommands like `/decision create`
- **Global Shortcut**: Create decisions from anywhere using the "Create Decision Record" shortcut (accessible from Slack's "+" menu or lightning bolt)
- **Message Shortcuts**: Right-click any message and save it as a decision
- **Notifications**: Get notified in Slack when decisions are created or status changes
- **Auto-linking**: Team members are automatically linked by email
- **Dedicated Link Page**: Clean account linking flow for users coming from Slack

## Prerequisites

1. You must be a **tenant admin** to install the Slack integration
2. Commercial features must be enabled (`COMMERCIAL_FEATURES_ENABLED=true`)
3. Slack credentials must be configured in Azure Key Vault:
   - `slack-client-id`
   - `slack-client-secret`
   - `slack-signing-secret`

## Installation

There are two ways to install the Slack integration:

### Option A: Install from Decision Records (Recommended)

1. Go to **Settings** in Decision Records (or navigate to `/{your-domain}/admin`)
2. Click the **Slack** tab
3. Read the guidance on what happens when you click "Add to Slack"
4. Click **Add to Slack**
5. Select your Slack workspace and authorize the app
6. You'll be redirected back to Settings with the Slack tab selected and a success message
7. Refresh the page if the connection status doesn't update immediately

### Option B: Claim an Existing Installation

If your IT team installed the app from the Slack App Directory:

1. Go to **Settings** → **Slack** tab
2. Under "Claim Existing Installation", enter your Slack Workspace ID
3. Click **Claim Workspace**
4. The integration will be linked to your organization

### Step 2: Configure Notifications

After installation:

1. Select a **default notification channel** from the dropdown
2. Enable/disable notification types:
   - **New decisions**: Notify when a decision is created
   - **Status changes**: Notify when a decision status changes
3. Click **Save Settings**

### Step 3: Test the Integration

1. Click **Send Test Notification**
2. Check your selected Slack channel for the test message

## Using the Interactive Menu

The easiest way to use Decision Records in Slack is the interactive menu:

1. Type `/decision` in any channel (no subcommand needed)
2. An interactive menu appears with buttons:
   - **Create Decision** - Opens the create decision modal
   - **List Decisions** - Shows recent decisions from your organization
   - **My Decisions** - Shows decisions you own or created
3. Click any button to perform that action

This is perfect for users who prefer clicking over typing commands.

## Using the Global Shortcut

Create decisions from anywhere in Slack without typing a command:

1. Click the **+** button (plus menu) or **⚡** (lightning bolt) in any message composer
2. Select **Create Decision Record** from the shortcuts menu
3. The create decision modal opens immediately

You can also access shortcuts via:
- Keyboard: `Cmd+K` (Mac) or `Ctrl+K` (Windows), then type "Create Decision"
- Right-click in the message composer and select "Shortcuts"

## Using Slash Commands

For power users, all commands use `/decision`:

| Command | Description | Example |
|---------|-------------|---------|
| `/decision` | Open interactive menu with buttons | `/decision` |
| `/decision help` | Show available commands | `/decision help` |
| `/decision create` | Open modal to create a decision | `/decision create` |
| `/decision list` | List recent decisions | `/decision list` |
| `/decision list [status]` | List decisions by status | `/decision list accepted` |
| `/decision view <id>` | View a specific decision | `/decision view 42` |
| `/decision search <query>` | Search decisions | `/decision search authentication` |

### Valid Statuses
- `proposed`
- `accepted`
- `archived`
- `superseded`

## Creating Decisions from Slack

### Using `/decision create`

1. Type `/decision create` in any channel
2. A modal opens with the following fields:
   - **Title** (required): What is this decision about?
   - **Context**: The background and forces at play
   - **Decision**: The decision that was made
   - **Consequences**: What follows from this decision
   - **Status**: Proposed, Accepted, Archived, or Superseded
   - **Decision Owner**: Select a team member to own this decision
3. Click **Create**

### Decision Creation Feedback

After creating a decision, you receive:

1. **Confirmation DM**: You get a direct message with:
   - Decision ID (e.g., `DRS-042`)
   - Decision title and status
   - Owner (if assigned)
   - Link to view the decision in Decision Records

2. **Channel Notification**: If enabled, a notification is posted to your configured Slack channel

3. **Owner Notification**: If you assigned an owner (different from yourself), they receive a DM with:
   - Notice they've been assigned as owner
   - Decision ID and title
   - Context preview
   - Link to view the full decision

### Decision Owner Field

When creating a decision via Slack, you can assign an owner:

- Select any Slack user from the dropdown
- The system automatically links the owner to their Decision Records account if:
  - They've already linked their Slack account, OR
  - Their Slack email matches a Decision Records user
- If the owner isn't in Decision Records, their email is stored for future linking
- Owners receive immediate Slack notification when assigned

## User Account Linking

When a team member uses `/decision` for the first time, they need to link their Slack account to their Decision Records account.

### Automatic Linking (Preferred)
If their Slack email matches their Decision Records email, they're automatically linked. No action required!

### Manual Linking (Dedicated Link Page)
If emails don't match or auto-linking fails:

1. Slack shows a message with workspace context and step-by-step guidance
2. Click **"Link My Account"** button
3. You're taken to a dedicated account linking page (`/slack/link`)
4. The page shows:
   - Which Slack workspace you're linking from
   - Whether you're logged in to Decision Records
   - Clear instructions for next steps
5. If already logged in: Click **"Link Account"** to complete
6. If not logged in: Click **"Sign In"** or **"Create Account"**
7. After linking, you'll see a success page with available commands

### Email Mismatch Notice
If your Slack email differs from your Decision Records email, the link page will show a notice explaining that linking is based on your login, not email matching.

## Message Shortcuts

Save any Slack message as a decision:

1. Hover over a message
2. Click the **...** (more actions) menu
3. Select **Save as Decision**
4. Fill in the decision details in the modal
5. Click **Create**

The message content is pre-filled in the Context field.

## Notifications

When enabled, your team gets notified in Slack:

**New Decision Created**
```
:sparkles: New decision record created
DR-42: Choose API Authentication Method
Status: Proposed
By: John Smith
Context: We need to decide on the authentication method for our public API...
[View Decision]
```

**Status Changed**
```
:arrows_counterclockwise: Decision status changed
DR-42: Choose API Authentication Method
Status: Accepted
```

## Disconnecting

1. Go to **Settings** → **Integrations**
2. Click **Disconnect**
3. Confirm the disconnection

This removes the workspace connection but preserves all decisions.

## Troubleshooting

### "Slack integration not available"
- Ensure `COMMERCIAL_FEATURES_ENABLED=true` is set
- Check that Slack secrets are configured in Key Vault

### Commands return "Invalid signature"
- Verify `slack-signing-secret` is correct in Key Vault
- Check that the webhook URL matches your domain

### "Link your account" keeps appearing
- Your Slack email doesn't match your Decision Records email
- Click "Link Account" to manually link your accounts

### Notifications not sending
- Ensure a default channel is selected
- Verify the bot has permission to post in that channel
- Check that notifications are enabled in settings

### "Workspace not configured properly"
- The tenant doesn't have a Slack workspace connected
- Contact your tenant admin to install the integration

## Security

- Bot tokens are encrypted at rest using Fernet encryption
- All Slack requests are verified using HMAC-SHA256 signatures
- OAuth state tokens prevent CSRF attacks
- User linking requires authentication in Decision Records

## For Administrators

### Required Slack App Scopes
- `chat:write` - Post messages to channels
- `commands` - Handle slash commands
- `users:read` - Read user info for linking
- `users:read.email` - Read user emails for auto-linking
- `im:write` - Send DMs to users (confirmations, owner notifications)

### Webhook URLs
Configure these in your Slack app settings:

| Setting | URL |
|---------|-----|
| Slash Commands | `https://decisionrecords.org/api/slack/webhook/commands` |
| Interactivity | `https://decisionrecords.org/api/slack/webhook/interactions` |
| Events | `https://decisionrecords.org/api/slack/webhook/events` |
| OAuth Redirect | `https://decisionrecords.org/api/slack/oauth/callback` |

### Event Subscriptions
Subscribe to the following bot events:
- `app_home_opened` - Display App Home tab with upgrade prompts

## App Upgrades

Slack doesn't notify users when an app is updated. We must implement our own upgrade notification system.

Based on patterns from [Slack's bolt-js-upgrade-app](https://github.com/slack-samples/bolt-js-upgrade-app).

### Key Concepts

1. **Scopes can only be appended** - OAuth grants new scopes while keeping the existing token
2. **Users must re-authorize** - Clicking through OAuth grants the new permissions
3. **App Home is ideal for prompts** - Users see it when opening the app in Slack

### Where Upgrade Prompts Appear

1. **App Home Tab** - Banner at top with "Upgrade App" button showing:
   - Current vs latest version
   - List of missing features
   - One-click upgrade button
2. **Slash command responses** - Context message about new features (planned)

### How Upgrades Work

1. New app version is released with additional scopes in `slack_upgrade.py`
2. Manifest is updated with new scopes
3. Users see upgrade prompts when opening App Home
4. Clicking "Upgrade" takes them through OAuth flow
5. Slack appends new scopes to their existing bot token
6. New features become available immediately

### Version Tracking

The `SlackWorkspace` model tracks:
- `granted_scopes` - Comma-separated list of OAuth scopes granted
- `app_version` - Version string at time of last install/upgrade
- `scopes_updated_at` - Timestamp when scopes were last updated

This enables showing targeted upgrade prompts only to workspaces missing required scopes.

## For Developers: Releasing New Versions

### Adding a New Feature Requiring Scopes

1. **Update `slack_upgrade.py`**:
   ```python
   APP_VERSIONS["1.2.0"] = SlackAppVersion(
       version="1.2.0",
       release_date="2025-01-15",
       scopes=[
           "chat:write", "commands", "users:read",
           "users:read.email", "im:write",
           "new:scope"  # Add new scope
       ],
       features=[
           # Existing features...
           "New feature description"  # Add new feature
       ],
       changelog="Added new feature requiring new:scope"
   )

   # Update current version
   CURRENT_APP_VERSION = "1.2.0"
   ```

2. **Update `slack-app-manifest.yaml`**:
   ```yaml
   oauth_config:
     scopes:
       bot:
         - chat:write
         - commands
         - users:read
         - users:read.email
         - im:write
         - new:scope  # Add new scope
   ```

3. **Deploy the changes** - Users will see upgrade prompts

### Key Files

| File | Purpose |
|------|---------|
| `slack_upgrade.py` | Version definitions, scope comparison, App Home blocks |
| `slack_service.py` | Event handlers, App Home rendering |
| `slack-app-manifest.yaml` | Slack app configuration (scopes, events, URLs) |
| `models.py` | `SlackWorkspace` model with scope tracking fields |
| `app.py` | OAuth callback stores scopes, Events API endpoint |

### Scope Comparison Functions

```python
from slack_upgrade import (
    get_missing_scopes,    # Returns list of missing scopes
    needs_upgrade,         # Returns bool
    get_upgrade_info,      # Returns detailed upgrade dict
    get_workspace_scopes,  # Gets scopes from workspace model
    CURRENT_APP_VERSION,   # Current version string
    REQUIRED_SCOPES        # List of required scopes
)
```

### Testing Upgrades

1. Install app to a test workspace with old scopes
2. Update `CURRENT_APP_VERSION` and `REQUIRED_SCOPES`
3. Open App Home - should show upgrade banner
4. Click upgrade - should go through OAuth
5. Verify new scopes are stored in database

### OAuth Redirect URLs

Both URLs must be registered in your Slack app:
- `https://decisionrecords.org/api/slack/oauth/callback` - Workspace installation
- `https://decisionrecords.org/auth/slack/oidc/callback` - Sign in with Slack (OIDC)
