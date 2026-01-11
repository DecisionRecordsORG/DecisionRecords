# Adding Enterprise Edition Features

This guide explains how to add new features to the Enterprise Edition while maintaining clean separation from Community Edition.

## Prerequisites

- Understanding of the [Open Core Model](open-core-model.md)
- Access to the `ee/` repository
- Flask Blueprint knowledge for backend
- Angular lazy loading for frontend

## Backend: Adding a New EE Module

### Step 1: Create Module Structure

```bash
mkdir -p ee/backend/myfeature
touch ee/backend/myfeature/__init__.py
touch ee/backend/myfeature/routes.py
touch ee/backend/myfeature/service.py
```

### Step 2: Define the Blueprint

```python
# ee/backend/myfeature/routes.py
from flask import Blueprint, jsonify, request
from functools import wraps

myfeature_bp = Blueprint('myfeature', __name__)

def require_myfeature_enabled(f):
    """Decorator to check if feature is enabled."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        from feature_flags import is_feature_enabled
        if not is_feature_enabled('myfeature'):
            return jsonify({'error': 'Feature not enabled'}), 503
        return f(*args, **kwargs)
    return wrapper

@myfeature_bp.route('/status')
@require_myfeature_enabled
def get_status():
    """Get feature status."""
    return jsonify({'status': 'active'})

@myfeature_bp.route('/action', methods=['POST'])
@require_myfeature_enabled
def perform_action():
    """Perform some action."""
    data = request.get_json() or {}
    # ... implementation
    return jsonify({'result': 'success'})
```

### Step 3: Create Service Layer

```python
# ee/backend/myfeature/service.py
class MyFeatureService:
    """Business logic for MyFeature."""

    def __init__(self, config=None):
        self.config = config or {}

    def do_something(self, input_data):
        """Core business logic."""
        # Implementation here
        return {'processed': input_data}
```

### Step 4: Export Public Interface

```python
# ee/backend/myfeature/__init__.py
from .routes import myfeature_bp
from .service import MyFeatureService

__all__ = ['myfeature_bp', 'MyFeatureService']
```

### Step 5: Register in Central Module

```python
# ee/backend/__init__.py
def register_all_blueprints(app):
    """Register all EE blueprints."""
    # ... existing blueprints ...

    from .myfeature.routes import myfeature_bp
    app.register_blueprint(myfeature_bp, url_prefix='/api/myfeature')
```

### Step 6: Add Feature Flag

```python
# feature_flags.py
FEATURES = {
    # ... existing features ...
    'myfeature': EDITION == Edition.ENTERPRISE,
}
```

### Step 7: Add Dependencies (if needed)

```
# ee/requirements.txt
myfeature-sdk>=1.0.0
```

## Frontend: Adding a New EE Component

### Step 1: Create Component

```typescript
// ee/frontend/components/myfeature/myfeature.component.ts
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-myfeature',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="myfeature-container">
      <h1>My Feature</h1>
      <!-- Component content -->
    </div>
  `
})
export class MyFeatureComponent implements OnInit {
  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.http.get('/api/myfeature/status').subscribe(/* ... */);
  }
}
```

### Step 2: Add Route (EE routes file)

Create or update `ee/frontend/routes/ee-routes.ts`:

```typescript
// ee/frontend/routes/ee-routes.ts
import { Routes } from '@angular/router';

export const EE_ROUTES: Routes = [
  {
    path: ':tenant/myfeature',
    loadComponent: () =>
      import('../components/myfeature/myfeature.component')
        .then(m => m.MyFeatureComponent)
  }
];
```

### Step 3: Integrate with Main Routes

The main `app.routes.ts` conditionally includes EE routes:

```typescript
// frontend/src/app/app.routes.ts
import { environment } from '../environments/environment';

// Dynamic import of EE routes (only works in EE builds)
const loadEERoutes = async (): Promise<Routes> => {
  if (environment.edition !== 'enterprise') {
    return [];
  }
  try {
    const { EE_ROUTES } = await import('@ee/routes/ee-routes');
    return EE_ROUTES;
  } catch {
    return [];
  }
};

// For static route definition, use spread with condition
export const routes: Routes = [
  // Core routes
  { path: '', component: LandingComponent },
  // ... other core routes

  // EE routes are included at build time based on configuration
];
```

## Adding EE Sections to Existing Components

Sometimes you need to add EE-only sections to existing CE components (like admin settings).

### Pattern: Component Composition

Instead of `@if` flags, use component injection:

```typescript
// Core component (always exists)
// frontend/src/app/components/admin/admin.component.ts
@Component({
  template: `
    <div class="admin-container">
      <h1>Admin Settings</h1>

      <!-- Core settings -->
      <app-session-settings></app-session-settings>

      <!-- EE settings slot - filled by EE module if available -->
      <ng-container *ngComponentOutlet="eeSettingsComponent"></ng-container>
    </div>
  `
})
export class AdminComponent implements OnInit {
  eeSettingsComponent: Type<any> | null = null;

  constructor(private eeLoader: EELoaderService) {}

  ngOnInit() {
    // Dynamically load EE component if available
    this.eeLoader.loadComponent('admin-ee-settings')
      .then(component => this.eeSettingsComponent = component)
      .catch(() => { /* EE not available, that's fine */ });
  }
}
```

```typescript
// EE Loader Service
// frontend/src/app/services/ee-loader.service.ts
@Injectable({ providedIn: 'root' })
export class EELoaderService {
  private componentMap: Map<string, () => Promise<Type<any>>> = new Map();

  constructor() {
    // In EE builds, this gets populated
    if (environment.edition === 'enterprise') {
      this.registerEEComponents();
    }
  }

  private registerEEComponents() {
    this.componentMap.set('admin-ee-settings',
      () => import('@ee/components/admin/admin-ee-settings.component')
        .then(m => m.AdminEESettingsComponent)
    );
  }

  async loadComponent(name: string): Promise<Type<any> | null> {
    const loader = this.componentMap.get(name);
    if (!loader) return null;
    return loader();
  }
}
```

## Testing Your EE Feature

### Unit Tests

```python
# tests/test_myfeature.py
import pytest
from feature_flags import is_enterprise

# Skip if not EE
pytestmark = pytest.mark.skipif(
    not is_enterprise(),
    reason="Enterprise Edition required"
)

def test_myfeature_endpoint(client, auth_headers):
    response = client.get('/api/myfeature/status', headers=auth_headers)
    assert response.status_code == 200
```

### Integration Tests

```bash
# Test in CE build - should 404
curl http://localhost:8000/api/myfeature/status
# Expected: 404 Not Found

# Test in EE build - should work
curl http://localhost:8000/api/myfeature/status
# Expected: 200 {"status": "active"}
```

## Checklist for New EE Features

- [ ] Created module structure in `ee/backend/{feature}/`
- [ ] Defined Flask Blueprint with routes
- [ ] Added feature flag to `feature_flags.py`
- [ ] Registered blueprint in `ee/backend/__init__.py`
- [ ] Added any Python dependencies to `ee/requirements.txt`
- [ ] Created frontend component in `ee/frontend/components/{feature}/`
- [ ] Added route to `ee/frontend/routes/ee-routes.ts`
- [ ] Added tests with appropriate skip markers
- [ ] Tested CE build (feature should not exist)
- [ ] Tested EE build (feature should work)
- [ ] Updated documentation if user-facing

## Common Mistakes to Avoid

1. **Don't import EE modules at top of core files**
   ```python
   # BAD - breaks CE builds
   from ee.backend.myfeature import MyFeatureService

   # GOOD - import inside function or after check
   if is_enterprise():
       from ee.backend.myfeature import MyFeatureService
   ```

2. **Don't use `@if` for security**
   ```typescript
   // BAD - user can modify JS
   @if (isEnterprise) {
     <secret-ee-feature></secret-ee-feature>
   }

   // GOOD - component doesn't exist in CE build
   <ng-container *ngComponentOutlet="eeComponent"></ng-container>
   ```

3. **Don't hardcode EE URLs in CE code**
   ```typescript
   // BAD - exposes EE API structure
   this.http.get('/api/slack/status')

   // GOOD - EE component handles its own API calls
   ```

4. **Don't forget feature flags for runtime control**
   Even in EE builds, features should be toggleable via config.
