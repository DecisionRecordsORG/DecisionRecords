# Open Core Architecture

This document describes the modular architecture that separates Community Edition (CE) from Enterprise Edition (EE) features.

## Overview

Decision Records follows an **Open Core** model:
- **Community Edition**: Core ADR functionality under BSL 1.1 license
- **Enterprise Edition**: Commercial features under proprietary license

The key principle is **physical separation**: EE code doesn't exist in Community builds, not just hidden by UI flags.

## Directory Structure

```
architecture-decisions/
├── app.py                    # Core Flask app (CE routes only)
├── models.py                 # Shared models
├── feature_flags.py          # Edition detection
├── frontend/
│   └── src/app/
│       ├── components/       # CE components
│       └── ee/               # Symlink to ee/frontend (EE builds only)
├── ee/                       # Enterprise Edition (separate git repo/submodule)
│   ├── LICENSE               # Proprietary license
│   ├── requirements.txt      # EE Python dependencies
│   ├── backend/
│   │   ├── __init__.py       # EE module registration
│   │   ├── slack/            # Slack integration
│   │   │   ├── __init__.py
│   │   │   ├── routes.py     # Flask Blueprint
│   │   │   ├── slack_service.py
│   │   │   └── slack_security.py
│   │   ├── teams/            # Teams integration
│   │   ├── ai/               # AI features
│   │   ├── analytics/        # PostHog
│   │   ├── azure/            # Key Vault
│   │   ├── cloudflare/       # Cloudflare security
│   │   └── oauth_providers/  # Google OAuth
│   └── frontend/
│       ├── components/       # EE Angular components
│       └── pages/            # EE marketing pages
└── Dockerfile.community      # Excludes ee/
```

## Backend Architecture

### Module Registration Pattern

Each EE module is a Flask Blueprint that self-registers:

```python
# ee/backend/slack/routes.py
from flask import Blueprint

slack_bp = Blueprint('slack', __name__)

@slack_bp.route('/install')
def slack_install():
    ...

@slack_bp.route('/oauth/callback')
def slack_callback():
    ...
```

The main app conditionally registers these blueprints:

```python
# app.py
from feature_flags import is_enterprise

def register_ee_modules(app):
    """Register EE modules if available."""
    if not is_enterprise():
        return

    try:
        from ee.backend import register_all_blueprints
        register_all_blueprints(app)
    except ImportError:
        logger.info("EE modules not available")

# In create_app or at module level
register_ee_modules(app)
```

### EE Module Structure

Each EE backend module follows this pattern:

```
ee/backend/{module}/
├── __init__.py       # Exports public interface
├── routes.py         # Flask Blueprint with route handlers
├── service.py        # Business logic
└── security.py       # Security utilities (optional)
```

The `__init__.py` exports the blueprint and any shared services:

```python
# ee/backend/slack/__init__.py
from .routes import slack_bp
from .slack_service import SlackService

__all__ = ['slack_bp', 'SlackService']
```

### Central EE Registration

```python
# ee/backend/__init__.py
def register_all_blueprints(app):
    """Register all EE blueprints with the Flask app."""
    from .slack.routes import slack_bp
    from .teams.routes import teams_bp
    from .ai.routes import ai_bp
    from .analytics.routes import analytics_bp

    app.register_blueprint(slack_bp, url_prefix='/api/slack')
    app.register_blueprint(teams_bp, url_prefix='/api/teams')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
```

## Frontend Architecture

### Path Mapping

In `tsconfig.json`, EE components are mapped with a path alias:

```json
{
  "compilerOptions": {
    "paths": {
      "@ee/*": ["ee/frontend/*"]
    }
  }
}
```

### Conditional Routes

Routes are conditionally included based on edition:

```typescript
// app.routes.ts
import { environment } from '../environments/environment';

const eeRoutes: Routes = environment.edition === 'enterprise' ? [
  {
    path: ':tenant/admin/slack',
    loadComponent: () => import('@ee/components/slack/slack-integration.component')
  },
  // ... other EE routes
] : [];

export const routes: Routes = [
  // Core routes (always included)
  { path: '', component: LandingComponent },
  { path: ':tenant', component: DecisionListComponent },

  // EE routes (only in Enterprise builds)
  ...eeRoutes
];
```

### Build Configurations

`angular.json` has separate configurations:

```json
{
  "configurations": {
    "community": {
      "fileReplacements": [{
        "replace": "src/environments/environment.ts",
        "with": "src/environments/environment.community.ts"
      }]
    },
    "enterprise": {
      "fileReplacements": [{
        "replace": "src/environments/environment.ts",
        "with": "src/environments/environment.enterprise.ts"
      }]
    }
  }
}
```

Environment files:

```typescript
// environment.community.ts
export const environment = {
  production: true,
  edition: 'community'
};

// environment.enterprise.ts
export const environment = {
  production: true,
  edition: 'enterprise'
};
```

## Build Process

### Community Edition

```dockerfile
# Dockerfile.community
FROM node:20 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/ .
# NOTE: ee/ is NOT copied - @ee/* imports will fail at build time if used
RUN npm ci && npm run build -- --configuration=community

FROM python:3.11-slim
COPY --from=frontend-builder /app/frontend/dist /app/static
COPY app.py models.py feature_flags.py requirements.txt /app/
# NOTE: ee/ is NOT copied
ENV DECISION_RECORDS_EDITION=community
```

### Enterprise Edition

```dockerfile
# Dockerfile.production
FROM node:20 AS frontend-builder
WORKDIR /app
COPY frontend/ frontend/
COPY ee/frontend/ ee/frontend/
# Create symlink so @ee/* imports work
RUN ln -s /app/ee/frontend /app/frontend/src/app/ee
RUN cd frontend && npm ci && npm run build -- --configuration=enterprise

FROM python:3.11-slim
COPY --from=frontend-builder /app/frontend/dist /app/static
COPY app.py models.py feature_flags.py requirements.txt /app/
COPY ee/ /app/ee/
RUN pip install -r /app/ee/requirements.txt
ENV DECISION_RECORDS_EDITION=enterprise
```

## Security Model

### Why Physical Separation Matters

1. **No code = no vulnerability surface**: EE code doesn't exist in CE builds
2. **No unlock hacks**: Users can't enable EE features by changing flags
3. **License compliance**: Clear separation of proprietary code
4. **Smaller images**: CE images don't include unused EE code

### Can Self-Hosters Override Controls?

| Attack Vector | Can Override? | Why? |
|---------------|---------------|------|
| Set `DECISION_RECORDS_EDITION=enterprise` | ❌ No effect | EE code doesn't exist in `Dockerfile.community` builds |
| Modify frontend JS to show hidden UI | ⚠️ UI only | Backend APIs return 503 - EE Python code doesn't exist |
| Call EE API endpoints directly | ❌ Fails | `from ee.backend.slack import ...` throws ImportError |
| Build from source with enterprise flag | ❌ Fails | `ee/` directory not in public repo (private submodule) |

**What happens if someone sets `DECISION_RECORDS_EDITION=enterprise` on Community Edition:**

```python
# In app.py during startup:
from feature_flags import is_enterprise

if is_enterprise():  # Returns True (env var says enterprise)
    try:
        from ee.backend import register_all_blueprints
        register_all_blueprints(app)
    except ImportError:
        # This happens! ee/ doesn't exist in Community images
        logger.info("EE modules not available")

# Result: App starts in "enterprise mode" but no EE routes registered
# /api/slack/install → 404 Not Found
```

**Frontend security:**
- Even if someone modifies JS to show EE UI sections
- Clicking buttons triggers API calls that fail (404/503)
- No data exposure because backend code doesn't exist

### Runtime Checks Are Defense-in-Depth

Even in EE builds, runtime checks exist as defense-in-depth:

```python
@slack_bp.route('/install')
def slack_install():
    if not is_slack_enabled():
        return jsonify({'error': 'Slack integration not enabled'}), 503
    # ... proceed with installation
```

This handles cases where:
- EE code is present but feature is disabled by config
- License has expired
- Feature is in maintenance mode

## Adding New EE Features

See [Adding EE Features Guide](adding-ee-features.md) for step-by-step instructions.

## Migration from Inline Code

When moving existing inline EE code to modules:

1. Identify all routes/functions belonging to the feature
2. Create the module structure in `ee/backend/{module}/`
3. Move route handlers to `routes.py` as a Blueprint
4. Move business logic to `service.py`
5. Update app.py to remove inline code
6. Update imports in `ee/backend/__init__.py`
7. Test both CE and EE builds

## Testing

### Testing CE Build

```bash
# Build without ee/
docker build -f Dockerfile.community -t dr:ce .

# Run and verify EE routes return 404
docker run -p 8000:8000 dr:ce
curl http://localhost:8000/api/slack/install  # Should 404
```

### Testing EE Build

```bash
# Build with ee/
docker build -f deployment/Dockerfile.production -t dr:ee .

# Run and verify EE routes work
docker run -p 8000:8000 -e DECISION_RECORDS_EDITION=enterprise dr:ee
curl http://localhost:8000/api/slack/install  # Should work (or require auth)
```

## Implementation Status

This section tracks the migration progress from inline code to the modular architecture.

### Backend Modules

| Module | Blueprint Ready | Registered | Routes in app.py | Status |
|--------|-----------------|------------|------------------|--------|
| Slack | ✅ `ee/backend/slack/routes.py` | ⏳ Pending | ✅ Still inline | Migration pending |
| Teams | ✅ `ee/backend/teams/routes.py` | ⏳ Pending | ✅ Still inline | Migration pending |
| AI | ✅ `ee/backend/ai/api.py` | ✅ Yes | ❌ | Complete |
| Analytics | ⏳ | ⏳ | ✅ Some inline | Partial |
| OAuth | ⏳ | ⏳ | ✅ Inline | Migration pending |
| Cloudflare | ✅ | ✅ | ❌ | Complete |
| Azure KV | ✅ | ✅ | ❌ | Complete |

**Migration Notes:**
- Slack and Teams blueprints are ready in `ee/backend/{module}/routes.py`
- Blueprints are NOT yet registered to avoid conflicts with inline routes in `app.py`
- Inline routes in `app.py` are protected by `@require_slack`/`@require_teams` decorators
- Full migration requires moving ~1700 lines of route handlers from `app.py` to blueprints

### Frontend Components

| Component | Location | Loading |
|-----------|----------|---------|
| Slack Integration | `ee/frontend/components/slack/` | Runtime feature flags |
| Teams Integration | `ee/frontend/components/teams/` | Runtime feature flags |
| AI API Config | `ee/frontend/components/ai-api/` | Runtime feature flags |
| MCP Config | `ee/frontend/components/mcp/` | Runtime feature flags |
| Marketing Pages | `ee/frontend/pages/` | Runtime feature flags |

**Frontend Notes:**
- Angular components use lazy loading via `loadComponent()`
- Feature visibility is controlled by `FeatureFlagsService`
- Build-time physical separation requires additional Angular configuration
- Current approach: Runtime visibility control + backend API enforcement

### UI Element Guards

The following UI elements are hidden in Community Edition using `@if (featureFlags.isEnterprise)`:

| Component | Section | Feature |
|-----------|---------|---------|
| **SuperAdmin Settings** | Licensing & Limits | EE license management |
| **SuperAdmin Settings** | Support Email | EE support configuration |
| **SuperAdmin Settings** | Product Analytics | PostHog integration |
| **SuperAdmin Settings** | Cloudflare Security | Cloudflare-specific settings |
| **SuperAdmin Settings** | AI & Integration Features | AI configuration |
| **SuperAdmin Tenants** | Login History tab | EE analytics feature |
| **SuperAdmin Tenants** | Slack Integrations tab | Slack workspace management |
| **Tenant Settings** | AI & API tab | MCP, API keys, AI settings |
| **Tenant Settings** | Slack tab | Slack notifications |
| **Tenant Settings** | Teams tab | Teams notifications |
| **Tenant Settings** | Slack OIDC option | In Authentication tab |
| **Tenant Settings** | Google OAuth option | In Authentication tab |

**Note**: The SSO Providers tab in Tenant Settings is visible in Community Edition because generic OIDC is a core feature (`generic_oidc: true`).

### FeatureFlagsService

The `FeatureFlagsService` manages feature visibility in the frontend:

```typescript
// services/feature-flags.service.ts
@Injectable({ providedIn: 'root' })
export class FeatureFlagsService {
  private flags: FeatureFlags = DEFAULT_FLAGS;

  get isEnterprise(): boolean {
    return this.flags.is_enterprise;
  }

  loadFlags(): Observable<FeatureFlags> {
    return this.http.get<FeatureFlags>('/api/features').pipe(
      tap(flags => this.flags = flags)
    );
  }
}
```

**Initialization**: Flags are loaded before the app bootstraps via `APP_INITIALIZER`:

```typescript
// app.config.ts
{
  provide: APP_INITIALIZER,
  useFactory: () => {
    const featureFlags = inject(FeatureFlagsService);
    return () => firstValueFrom(featureFlags.loadFlags());
  },
  multi: true
}
```

**Usage in templates**:

```typescript
@Component({
  template: `
    @if (featureFlags.isEnterprise) {
      <ee-only-section></ee-only-section>
    }
  `
})
export class MyComponent {
  constructor(public featureFlags: FeatureFlagsService) {}
}
```

### Why `@if` Is Safe for UX Gating

The `@if (featureFlags.isEnterprise)` pattern is used for **UX purposes**, not security:

1. **Backend enforces security**: EE API endpoints return 503/404 in Community Edition
2. **Frontend just hides UI**: Users don't see buttons for unavailable features
3. **Can't be hacked**: Modifying frontend JS doesn't grant access to EE features
4. **Flags come from backend**: Frontend can't override what `/api/features` returns

This is different from the "bad pattern" in the adding-ee-features.md guide, which refers to using `@if` to **hide EE code that exists in CE builds**. In our case, the EE backend code doesn't exist in CE Docker images.

### Security Enforcement

Even with inline routes, security is enforced at multiple levels:

1. **Decorator Level**: `@require_slack`, `@require_teams` return 503 in CE
2. **Import Level**: EE imports inside route handlers fail if ee/ doesn't exist
3. **Build Level**: Dockerfile.community excludes ee/ directory
4. **Runtime Level**: Feature flags service reports disabled features to frontend

### Next Steps

1. **Complete Blueprint Migration**: Move inline routes from app.py to blueprints
2. **Register Blueprints**: Update `ee/backend/__init__.py` to register all blueprints
3. **Angular Build Config**: Add community/enterprise build configurations
4. **Remove Inline Routes**: Delete migrated routes from app.py
