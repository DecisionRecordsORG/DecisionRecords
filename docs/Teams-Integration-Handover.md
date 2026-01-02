# Teams Integration Handover Document

**Date**: 2026-01-02
**Session**: Teams Integration Infrastructure & Local Testing Setup

---

## Summary

This session completed the Microsoft Teams integration infrastructure that was previously code-complete but missing Azure resources. The Teams integration is now fully deployable and testable locally.

---

## What Was Done

### 1. Infrastructure Templates Created

| File | Purpose |
|------|---------|
| `infra/teams-bot-template.json` | ARM template for Azure Bot Service (Single-Tenant) |
| `scripts/deploy-teams-bot.sh` | Deployment script with `--local` mode for testing |
| `scripts/start-ngrok.sh` | Helper script for ngrok tunnel management |

### 2. Documentation Created

| File | Purpose |
|------|---------|
| `docs/local-testing.md` | Comprehensive guide for local testing with ngrok |
| `docs/Teams-Integration-Handover.md` | This document |

### 3. Code Fixes Applied

| File | Changes |
|------|---------|
| `frontend/src/app/services/admin.service.ts` | Added `install_url` to `TeamsSettings` interface |
| `frontend/src/app/components/settings/settings.component.ts` | Fixed Teams connect flow: proper API mapping, "not configured" state, OAuth callback handling, removed `target="_blank"` |
| `app.py` | Added Teams table existence check in schema migrations (lines 824-837) |
| `run_local.py` | Added Teams credentials loading from `local_secrets.py` |
| `e2e/playwright.config.ts` | Added ngrok URL detection for integration tests |
| `infra/README.md` | Added Teams section with deployment instructions and Key Vault secrets |
| `.gitignore` | Added `local_secrets.py` |

### 4. Azure Resources Deployed

| Resource | Name/Value |
|----------|------------|
| Azure Bot Service | `adr-teams-bot` |
| Azure AD App ID | `a140ddfe-c8cc-4378-9d43-936d619e4423` |
| Azure AD Tenant ID | `f0dbdb4d-b89f-4b0e-8771-9ef576954083` |
| Messaging Endpoint | `https://unexudative-unconcurring-sherril.ngrok-free.dev/api/teams/webhook` |
| Key Vault Secrets | `teams-bot-app-id`, `teams-bot-app-secret`, `teams-bot-tenant-id` |

### 5. Local Testing Setup

| File | Purpose |
|------|---------|
| `local_secrets.py` | Contains Teams credentials (gitignored) |
| `/tmp/ngrok_url.txt` | Current ngrok URL (created by start-ngrok.sh) |

---

## Current State

### ngrok Status
- **Running**: Yes
- **URL**: `https://unexudative-unconcurring-sherril.ngrok-free.dev`
- **Dashboard**: http://localhost:4040

### What Works Now
1. ✅ Teams tab in settings shows "Connect with Microsoft Teams" button (not "Not Configured")
2. ✅ OAuth flow redirects to Microsoft for consent
3. ✅ Credentials are loaded from `local_secrets.py`
4. ✅ Key Vault has all Teams secrets for production

### What Still Needs Testing
1. Complete OAuth consent flow end-to-end
2. Bot messaging (requires Teams app sideloading)
3. Notifications to Teams channels
4. User account linking

---

## Files Modified (Uncommitted)

Run `git status` to see all changes. Key files:

```
modified:   .gitignore
modified:   app.py
modified:   frontend/src/app/components/settings/settings.component.ts
modified:   frontend/src/app/services/admin.service.ts
modified:   infra/README.md
modified:   run_local.py
modified:   e2e/playwright.config.ts
modified:   teams-app-manifest.json
new file:   infra/teams-bot-template.json
new file:   scripts/deploy-teams-bot.sh
new file:   scripts/start-ngrok.sh
new file:   docs/local-testing.md
new file:   docs/Teams-Integration-Handover.md
new file:   local_secrets.py (gitignored)
```

---

## How to Test Locally

### Prerequisites
- ngrok installed and authenticated
- Local server running (`python run_local.py`)
- Frontend running (`cd frontend && npm run start`)

### Quick Test
1. Go to http://localhost:4200/settings
2. Login as admin
3. Navigate to Teams tab
4. Verify "Connect with Microsoft Teams" button appears

### Full Integration Test
1. Click "Connect with Microsoft Teams"
2. Complete Microsoft OAuth consent
3. Verify redirect back to settings with success message
4. Configure notification channel
5. Test notification

---

## When ngrok Restarts

ngrok URLs change each session. Update the bot endpoint:

```bash
# Get new ngrok URL
./scripts/start-ngrok.sh --background

# Update Azure Bot
az bot update --name adr-teams-bot --resource-group adr-resources-eu \
  --endpoint 'https://NEW-URL.ngrok.io/api/teams/webhook'
```

Or use the combined command:
```bash
./scripts/start-ngrok.sh --background --update-bot
```

---

## Production Deployment

When ready to deploy to production:

1. **Commit all changes** (except `local_secrets.py` which is gitignored)

2. **Update bot endpoint to production**:
   ```bash
   az bot update --name adr-teams-bot --resource-group adr-resources-eu \
     --endpoint 'https://decisionrecords.org/api/teams/webhook'
   ```

3. **Deploy application**:
   ```bash
   ./scripts/redeploy.sh patch
   ```

4. **Create Teams app package**:
   ```bash
   zip teams-app.zip teams-app-manifest.json frontend/src/assets/icon-*.png
   ```

5. **Upload to Teams Admin Center** or sideload for testing

---

## Key Vault Secrets Reference

| Secret | Purpose |
|--------|---------|
| `teams-bot-app-id` | Azure AD Application (client) ID |
| `teams-bot-app-secret` | Azure AD client secret |
| `teams-bot-tenant-id` | Azure AD tenant ID (single-tenant) |

These are automatically used by the production app via `keyvault_client.py`.

---

## Troubleshooting

### "Teams Integration Not Configured"
- Check `TEAMS_BOT_APP_ID` is set (via `local_secrets.py` or Key Vault)
- Verify `COMMERCIAL_FEATURES_ENABLED=true`

### OAuth Callback Fails
- Verify ngrok is running and URL matches bot endpoint
- Check Azure AD App Registration has correct redirect URIs

### Bot Not Responding
- Check ngrok dashboard (http://localhost:4040) for incoming requests
- Verify JWT validation is passing in Flask logs

---

## Contact

For questions about this implementation, refer to:
- `docs/local-testing.md` - Local testing guide
- `infra/README.md` - Infrastructure documentation
- Plan file: `/Users/lawrencenyakiso/.claude/plans/bubbly-jumping-eich.md`
