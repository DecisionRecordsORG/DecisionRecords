# Slack Integration Guide

Decision Records integrates with Slack to help your team manage architecture decisions directly from where they communicate.

## Features

- **Slash Commands**: Create, list, view, and search decisions with `/adr`
- **Notifications**: Get notified in Slack when decisions are created or status changes
- **Message Shortcuts**: Right-click any message and save it as a decision
- **Auto-linking**: Team members are automatically linked by email

## Prerequisites

1. You must be a **tenant admin** to install the Slack integration
2. Commercial features must be enabled (`COMMERCIAL_FEATURES_ENABLED=true`)
3. Slack credentials must be configured in Azure Key Vault:
   - `slack-client-id`
   - `slack-client-secret`
   - `slack-signing-secret`

## Installation

### Step 1: Install the App

1. Go to **Settings** in Decision Records
2. Click the **Integrations** tab
3. Click **Add to Slack**
4. Select your Slack workspace and authorize the app
5. You'll be redirected back to Settings with a success message

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

## Using Slack Commands

All commands use `/adr`:

| Command | Description | Example |
|---------|-------------|---------|
| `/adr help` | Show available commands | `/adr help` |
| `/adr create` | Open modal to create a decision | `/adr create` |
| `/adr list` | List recent decisions | `/adr list` |
| `/adr list [status]` | List decisions by status | `/adr list accepted` |
| `/adr view <id>` | View a specific decision | `/adr view 42` |
| `/adr search <query>` | Search decisions | `/adr search authentication` |

### Valid Statuses
- `proposed`
- `accepted`
- `deprecated`
- `superseded`

## User Account Linking

When a team member uses `/adr` for the first time:

### Automatic Linking (Preferred)
If their Slack email matches their Decision Records email, they're automatically linked.

### Manual Linking (Fallback)
If emails don't match:
1. Slack shows a "Link Account" button
2. Click to open Decision Records in browser
3. Log in (or create an account)
4. Account is linked automatically

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
- `channels:read` - List public channels
- `groups:read` - List private channels (if added)

### Webhook URLs
Configure these in your Slack app settings:

| Setting | URL |
|---------|-----|
| Slash Commands | `https://decisionrecords.org/api/slack/webhook/commands` |
| Interactivity | `https://decisionrecords.org/api/slack/webhook/interactions` |
| OAuth Redirect | `https://decisionrecords.org/api/slack/oauth/callback` |
