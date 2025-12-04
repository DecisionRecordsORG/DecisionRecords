# Issue: Root route redirects to old /login template instead of serving Angular landing page

## Issue Description

After the multi-tenant architecture update, the root URL (`/`) incorrectly redirects to `/login` and serves the old HTML template instead of the new Angular landing page.

## Expected Behavior
- `/` should serve the Angular landing page for new tenant signup
- `/login` should also serve the Angular app with appropriate routing

## Actual Behavior
- `/` returns a 302 redirect to `/login`
- `/login` serves the old Bootstrap HTML template from `templates/login.html`

## Working Routes
- `/superadmin` ✅ Correctly serves Angular app
- `/index.html` ✅ Correctly serves Angular app
- `/{domain}/login` ❓ Needs testing with proper domain

## Root Cause
Flask authentication logic is intercepting the root route and redirecting to `/login`, and the `/login` route is serving the legacy HTML template instead of allowing Angular routing to handle it.

## Technical Analysis

### Request Flow
```
GET / → 302 Redirect → GET /login → templates/login.html (old template)
```

### Expected Flow
```
GET / → Angular index.html → Angular router handles landing page
```

### Flask Route Investigation Needed
1. Check if there's an `@login_required` decorator on root routes
2. Verify Angular serving configuration in `app.py`
3. Ensure legacy template routes are properly disabled

## Solution Needed
1. Update Flask routing to serve Angular app for root route
2. Ensure `/login` route serves Angular app instead of legacy template  
3. Remove or update authentication middleware that causes the redirect
4. Update route precedence so Angular routes take priority over legacy routes

## Code Areas to Investigate
- `app.py`: Authentication decorators and route definitions
- `app.py`: Angular frontend serving logic (lines around serve_angular function)
- `auth.py`: Login required middleware
- Legacy template routes that may be interfering

## Steps to Reproduce
1. Navigate to `http://localhost:5001/`
2. Observe 302 redirect to `/login`
3. See old Bootstrap template instead of Angular landing page
4. Compare with `http://localhost:5001/superadmin` which correctly serves Angular

## Environment
- Docker container with latest build (commit: latest)
- All Angular files correctly built and accessible at `frontend/dist/frontend/browser/`
- Flask backend running with new multi-tenant code
- Port 5001 (due to port 5000 conflict with macOS ControlCenter)

## Testing Checklist
- [ ] Root route `/` serves Angular landing page
- [ ] `/login` serves Angular app (not legacy template)
- [ ] `/superadmin` continues to work
- [ ] `/{domain}/login` routes work for tenant-specific login
- [ ] Authentication flows work correctly with Angular routing
- [ ] No broken legacy template references

## Priority
**High** - This affects the primary user onboarding flow for the new multi-tenant architecture.

## Labels
- bug
- routing
- high-priority
- multi-tenant
- angular
- flask

---
**Created**: 2025-12-04  
**Reporter**: Claude Code Assistant  
**Status**: Open  