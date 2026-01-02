# Local Testing Guide

This guide covers testing the application locally, including integration testing with external services like Microsoft Teams.

## Quick Start

### Basic Local Development

```bash
# Backend
python run_local.py

# Frontend (separate terminal)
cd frontend && npm run start

# Access at http://localhost:4200
```

### Running Tests

```bash
# Backend unit tests
.venv/bin/python -m pytest tests/ -v

# E2E tests (starts servers automatically)
cd e2e && npx playwright test
```

## Integration Testing with ngrok

When testing integrations that require external services to call back to your local server (Teams Bot Framework, Slack Events API, webhooks), you need a public URL. ngrok provides this.

### Prerequisites

1. **Install ngrok**:
   ```bash
   # macOS
   brew install ngrok

   # Linux
   snap install ngrok

   # Windows
   choco install ngrok
   ```

2. **Authenticate ngrok**:
   ```bash
   ngrok config add-authtoken YOUR_TOKEN
   ```
   Get your token at: https://dashboard.ngrok.com/get-started/your-authtoken

### Starting ngrok

**Option 1: Using helper script (recommended)**
```bash
# Start ngrok tunnel
./scripts/start-ngrok.sh

# Start in background and update Azure Bot endpoint
./scripts/start-ngrok.sh --background --update-bot
```

**Option 2: Manual**
```bash
ngrok http 5001
```

The ngrok dashboard at http://localhost:4040 shows all requests for debugging.

## Teams Integration Testing

### First-Time Setup

1. **Deploy Azure Bot infrastructure**:
   ```bash
   ./scripts/deploy-teams-bot.sh --local
   ```
   This creates:
   - Azure AD App Registration
   - Azure Bot Service with Teams channel
   - Key Vault secrets

2. **Copy credentials to run_local.py**:
   The script outputs environment variables. Add them to `run_local.py`:
   ```python
   os.environ['TEAMS_BOT_APP_ID'] = 'your-app-id'
   os.environ['TEAMS_BOT_APP_SECRET'] = 'your-app-secret'
   os.environ['TEAMS_BOT_TENANT_ID'] = 'your-tenant-id'
   ```

3. **Create Teams app package**:
   ```bash
   # Update manifest with your App ID
   # Then create ZIP
   zip teams-app.zip teams-app-manifest.json frontend/src/assets/icon-*.png
   ```

4. **Sideload in Teams**:
   - Go to Teams > Apps > Manage your apps > Upload an app
   - Select the ZIP file

### Daily Testing Workflow

ngrok URLs change each session, so you need to update the bot endpoint:

```bash
# 1. Start ngrok
./scripts/start-ngrok.sh --background

# 2. Update Azure Bot endpoint (use the ngrok URL shown)
az bot update --name adr-teams-bot --resource-group adr-resources-eu \
  --endpoint 'https://YOUR-NGROK-URL.ngrok.io/api/teams/webhook'

# Or use the helper script with --update-bot flag:
./scripts/start-ngrok.sh --background --update-bot

# 3. Start local server
python run_local.py

# 4. Test in Teams
```

### Testing Specific Features

**OAuth Connect Flow**:
1. Go to http://localhost:4200/settings (logged in as admin)
2. Navigate to Teams tab
3. Click "Connect with Microsoft Teams"
4. Complete OAuth flow in Microsoft

**Bot Commands**:
In Teams, message the bot:
- `help` - Show available commands
- `list` - List recent decisions
- `create` - Create a new decision
- `search <query>` - Search decisions

**Notifications**:
1. Configure a notification channel in settings
2. Create or update a decision
3. Check the Teams channel for notification

## Debugging

### ngrok Dashboard

http://localhost:4040 provides:
- Request/response inspection
- Replay failed requests
- Request timing

### Flask Logs

Run with debug logging:
```bash
FLASK_DEBUG=1 python run_local.py
```

### Teams Bot Debugging

Check Azure Bot health:
```bash
az bot show --name adr-teams-bot --resource-group adr-resources-eu
```

Test bot endpoint directly:
```bash
curl -X POST https://YOUR-NGROK-URL.ngrok.io/api/teams/webhook \
  -H "Content-Type: application/json" \
  -d '{"type": "message", "text": "test"}'
```

## Common Issues

### "Teams Integration Not Configured"

The Azure Bot credentials are not set. Either:
- Run `./scripts/deploy-teams-bot.sh --local` to create them
- Add the credentials to `run_local.py`

### Bot Not Responding

1. Check ngrok is running: http://localhost:4040
2. Verify bot endpoint is updated with current ngrok URL
3. Check Flask logs for incoming requests
4. Verify JWT token validation is passing

### OAuth Callback Fails

The callback URL must match what's registered in Azure AD:
- For local testing: Uses ngrok URL
- Update Azure AD App Registration redirect URIs if needed

### Session/Cookie Issues

When testing through ngrok:
- Use the Angular frontend (localhost:4200) which proxies to backend
- Or access directly via ngrok URL (but cookies may not persist)

## Environment Variables Reference

| Variable | Purpose | Required |
|----------|---------|----------|
| `TEAMS_BOT_APP_ID` | Azure AD App ID | For Teams |
| `TEAMS_BOT_APP_SECRET` | Azure AD App Secret | For Teams |
| `TEAMS_BOT_TENANT_ID` | Azure AD Tenant ID | For Teams |
| `COMMERCIAL_FEATURES_ENABLED` | Enable Teams/Slack | Yes |
| `SKIP_CLOUDFLARE_CHECK` | Disable origin check | For local |

## CI/CD Integration

For CI pipelines that need to test webhooks:

1. Use a fixed ngrok domain (requires paid ngrok plan)
2. Or use Bot Framework Emulator for unit testing
3. Or mock the external service calls

The existing E2E tests don't require ngrok as they test the UI flow, not the actual Teams integration.
