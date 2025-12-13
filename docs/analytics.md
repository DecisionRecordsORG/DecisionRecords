# Product Analytics (PostHog Integration)

This document describes the PostHog analytics integration for tracking platform usage patterns with privacy-respecting user identification.

## Overview

The Architecture Decisions platform includes optional product analytics powered by PostHog. This feature allows administrators to understand how the platform is being used while respecting user privacy.

**Key Features:**
- Off by default (opt-in)
- Privacy-respecting user identification (hashed IDs)
- Super admin configurable
- Customizable event names
- Support for both cloud and self-hosted PostHog

## Privacy Design

### User Identification

User identities are never sent to PostHog in plain form. Instead, a deterministic hash is generated:

```
distinct_id = SHA256(user_id + tenant_domain + secret_salt)[:32]
```

**Properties:**
- **Deterministic**: Same user generates the same ID across sessions
- **Not reversible**: Cannot derive the original user ID from the hash
- **Tenant-scoped**: Same user in different tenants has different IDs
- **Master admin**: Tracked as single identity `master_admin`

### Person Profiling

Person profiling can be disabled to prevent PostHog from creating user profiles:

- When **OFF** (default): Events are tracked but no user profiles are created in PostHog
- When **ON**: PostHog will create and maintain user profiles

## Configuration

### Super Admin Settings

Navigate to **Super Admin > System Settings > Product Analytics** to configure:

| Setting | Description | Default |
|---------|-------------|---------|
| Enable Analytics | Turn analytics on/off | OFF |
| PostHog Host URL | PostHog server address | `https://eu.i.posthog.com` |
| API Key | PostHog project API key | - |
| Person Profiling | Create user profiles in PostHog | OFF |

### API Key Storage

The API key is stored securely using a fallback chain:

1. **Azure Key Vault** (`posthog-api-key`) - Production/Cloud
2. **Environment Variable** (`POSTHOG_API_KEY`) - Container config
3. **SystemConfig Database** - Self-hosted deployments

For production deployments, store the API key in Azure Key Vault:

```bash
az keyvault secret set \
  --vault-name adr-keyvault-eu \
  --name "posthog-api-key" \
  --value "phc_your_api_key_here"
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `POSTHOG_API_KEY` | PostHog project API key |
| `ANALYTICS_SALT` | Secret salt for hashing user IDs |

## Event Categories

Events are organized into 10 categories for easy management:

| Category | Icon | Description | Events |
|----------|------|-------------|--------|
| System | monitor_heart | Health checks, version | 3 |
| Authentication | login | Login, logout, SSO, verification | 19 |
| WebAuthn | fingerprint | Passkey registration and auth | 4 |
| User Profile | person | Profile views, credentials | 7 |
| Decisions | description | ADR CRUD operations | 8 |
| Infrastructure | dns | IT infrastructure management | 6 |
| Spaces | folder | Space management | 6 |
| Admin | admin_panel_settings | Tenant admin operations | 26 |
| Super Admin | security | System configuration | 31 |
| Public | public | Feedback, sponsorship | 2 |

## Event Mappings

Super admins can customize event names sent to PostHog. Default mappings include:

| Internal Name | Default Event Name |
|--------------|-------------------|
| `api_decisions_list` | `decisions_listed` |
| `api_decisions_create` | `decision_created` |
| `api_decisions_update` | `decision_updated` |
| `auth_local` | `auth_local_attempted` |
| `api_user_me` | `user_profile_viewed` |

Full list of 86 events available in the Super Admin settings UI.

## API Endpoints

### Get Analytics Settings
```
GET /api/admin/settings/analytics
```
Returns current analytics configuration (API key status, not the key itself).

### Save Analytics Settings
```
POST /api/admin/settings/analytics
Content-Type: application/json

{
  "enabled": true,
  "host": "https://eu.i.posthog.com",
  "person_profiling": false,
  "event_mappings": {
    "api_decisions_list": "custom_event_name"
  }
}
```

### Save API Key
```
PUT /api/admin/settings/analytics/api-key
Content-Type: application/json

{
  "api_key": "phc_your_api_key"
}
```

### Test Connection
```
POST /api/admin/settings/analytics/test
```
Sends a test event to PostHog and returns success/failure status.

### Reset Event Mappings
```
POST /api/admin/settings/analytics/reset-mappings
```
Resets all custom event names to defaults.

## Developer Guide

### Adding Tracking to New Endpoints

Import the decorator and apply it to routes:

```python
from analytics import track_endpoint

@app.route('/api/my-endpoint', methods=['GET'])
@login_required
@track_endpoint('api_my_endpoint')  # Add after auth decorators
def my_endpoint():
    ...
```

### Manual Event Tracking

For custom events not tied to routes:

```python
from analytics import track_event

track_event('custom_event', properties={
    'action': 'something_happened',
    'value': 42
})
```

### Event Properties

All tracked events automatically include:

| Property | Description |
|----------|-------------|
| `user_type` | `anonymous`, `authenticated`, or `master_admin` |
| `endpoint` | Internal endpoint name |
| `path` | Request path |
| `method` | HTTP method |
| `tenant_hash` | Hashed tenant domain (if authenticated) |
| `response_status` | HTTP status code (if available) |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Flask Application                        │
│  ┌─────────────────┐    ┌──────────────────────────────┐   │
│  │ @track_endpoint │───>│      analytics.py            │   │
│  │    decorator    │    │  - Config caching (5 min)    │   │
│  └─────────────────┘    │  - Lazy PostHog init         │   │
│                         │  - Hash-based distinct_id    │   │
│                         └────────────┬─────────────────┘   │
└──────────────────────────────────────┼─────────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │      PostHog Cloud      │
                          │   (eu.i.posthog.com)    │
                          │                         │
                          │  Events with:           │
                          │  - Hashed user IDs      │
                          │  - Hashed tenant info   │
                          │  - No PII               │
                          └─────────────────────────┘
```

## Troubleshooting

### Analytics Not Working

1. **Check if enabled**: Verify analytics is enabled in Super Admin settings
2. **Verify API key**: Use the "Test Connection" button
3. **Check logs**: Look for PostHog errors in container logs
4. **Cache delay**: Config changes may take up to 5 minutes to apply

### Events Not Appearing in PostHog

1. **Flush delay**: PostHog batches events; may take a few seconds
2. **Endpoint not instrumented**: Verify `@track_endpoint` decorator is present
3. **Event filtered**: Check PostHog project settings for filters

### API Key Issues

```bash
# Check if key is in Key Vault
az keyvault secret show \
  --vault-name adr-keyvault-eu \
  --name "posthog-api-key"

# Set key in Key Vault
az keyvault secret set \
  --vault-name adr-keyvault-eu \
  --name "posthog-api-key" \
  --value "phc_your_key"
```

## Security Considerations

1. **API key security**: Never expose the API key in frontend responses
2. **User privacy**: All user IDs are hashed before sending to PostHog
3. **Tenant isolation**: Tenant domains are hashed in event properties
4. **GDPR compliance**: Person profiling is off by default
5. **Data minimization**: Only necessary event data is collected

---

*Last Updated: December 2024*
