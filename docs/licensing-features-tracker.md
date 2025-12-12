# Licensing Features Tracker

This document tracks the implementation status of licensing and pricing tier features for the Architecture Decisions platform.

## Overview

The platform supports tiered pricing with the following tiers:
- **Self-Hosted (Free)**: Unlimited users, tenants, storage
- **Cloud Free Tier**: Up to 5 users, 3 tenants, 2 GB storage
- **Team**: Up to 50 users, unlimited tenants, SSO, priority support
- **Enterprise**: Unlimited users, advanced features, dedicated support

## Feature Implementation Status

### Phase 1: User Limits (Current)

| Feature | Status | Backend | Frontend | Unit Tests | Integration Tests | E2E Tests |
|---------|--------|---------|----------|------------|-------------------|-----------|
| Max users per tenant (global setting) | Complete | Done | Done | Done | Done | Done |
| Super admin configuration UI | Complete | N/A | Done | N/A | N/A | Done |
| Enforce limit on access requests | Complete | Done | N/A | Done | Done | Pending |
| Enforce limit on auto-approval | Complete | Done | N/A | Done | Done | Pending |
| User count display in tenant list | Existing | Done | Done | - | - | - |

### Phase 2: Tenant Limits (Future)

| Feature | Status | Backend | Frontend | Unit Tests | Integration Tests | E2E Tests |
|---------|--------|---------|----------|------------|-------------------|-----------|
| Max tenants per account | Not Started | - | - | - | - | - |
| Account model | Not Started | - | - | - | - | - |
| Account-tenant association | Not Started | - | - | - | - | - |

### Phase 3: Storage Limits (Future)

| Feature | Status | Backend | Frontend | Unit Tests | Integration Tests | E2E Tests |
|---------|--------|---------|----------|------------|-------------------|-----------|
| Storage tracking per tenant | Not Started | - | - | - | - | - |
| Storage quota enforcement | Not Started | - | - | - | - | - |
| Storage usage display | Not Started | - | - | - | - | - |

### Phase 4: Audit Log Retention (Future)

| Feature | Status | Backend | Frontend | Unit Tests | Integration Tests | E2E Tests |
|---------|--------|---------|----------|------------|-------------------|-----------|
| Configurable retention period | Not Started | - | - | - | - | - |
| Auto-cleanup job | Not Started | - | - | - | - | - |
| Retention by tier | Not Started | - | - | - | - | - |

### Phase 5: SSO Features (Future)

| Feature | Status | Backend | Frontend | Unit Tests | Integration Tests | E2E Tests |
|---------|--------|---------|----------|------------|-------------------|-----------|
| SAML SSO | Not Started | - | - | - | - | - |
| OIDC SSO | Partial | Exists | Exists | - | - | - |
| SCIM provisioning | Not Started | - | - | - | - | - |

## Configuration Keys

System configuration keys used for licensing features:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_users_per_tenant` | Integer | 5 | Maximum users allowed per tenant (0 = unlimited) |
| `max_tenants_per_account` | Integer | 3 | Maximum tenants per account (future) |
| `max_storage_gb_per_tenant` | Integer | 2 | Maximum storage in GB per tenant (future) |
| `audit_log_retention_days` | Integer | 30 | Days to retain audit logs (future) |

## API Endpoints

### Licensing Settings (Super Admin)

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `GET /api/admin/settings/licensing` | GET | Get all licensing settings | Complete |
| `POST /api/admin/settings/licensing` | POST | Update licensing settings | Complete |
| `GET /api/tenants/<domain>/limits` | GET | Get tenant limit status | Complete |

## Implementation Notes

### User Limit Enforcement Points

The user limit must be enforced at these points:
1. **Access Request Approval** (`POST /api/admin/access-requests/<id>/approve`)
2. **Access Request Auto-Approval** (`POST /api/auth/access-request` when auto-approve enabled)
3. **User Invitation** (if direct invitation is implemented)
4. **SSO First Login** (when user is auto-created via SSO)

### Edge Cases to Handle

1. Existing tenants exceeding limits when setting is lowered
2. Admin users vs regular users counting
3. Pending access requests when limit is reached
4. SSO users who are auto-created

## Changelog

### 2025-12-12
- Created licensing features tracker
- Implemented max users per tenant feature (Phase 1)
  - Added `KEY_MAX_USERS_PER_TENANT` constant to SystemConfig
  - Added `DEFAULT_MAX_USERS_PER_TENANT = 5` (free tier limit)
  - Created `GET/POST /api/admin/settings/licensing` endpoints
  - Created `GET /api/tenants/<domain>/limits` endpoint
  - Added `can_tenant_accept_users()` helper function
  - Enforced limit in access request approval and auto-approval flows
  - Added Licensing & Limits section to super admin settings UI
  - Created unit tests (`tests/test_licensing.py`)
  - Created E2E tests (`e2e/tests/licensing-settings.spec.ts`)
