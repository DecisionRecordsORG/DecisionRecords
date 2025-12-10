# Database Schema Documentation

This document describes the complete database schema for Architecture Decisions v1.5+.

## Overview

The application uses PostgreSQL in production and SQLite for testing. The schema supports:
- Multi-tenant architecture (domain-based tenancy)
- v1.5 Governance Model with Tenants and Memberships
- WebAuthn/Passkey authentication
- SSO (OpenID Connect) authentication
- Local password authentication
- Architecture Decision Records (ADRs)

## Schema Diagram

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  master_accounts│     │      users       │     │     tenants     │
└─────────────────┘     └────────┬─────────┘     └────────┬────────┘
                                 │                        │
                                 │                        │
                        ┌────────┴────────┐      ┌────────┴────────┐
                        │                 │      │                 │
                        ▼                 ▼      ▼                 ▼
              ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
              │webauthn_creds   │  │tenant_memberships│  │ tenant_settings │
              └─────────────────┘  └─────────────────┘  └─────────────────┘
                                                               │
                                          ┌────────────────────┤
                                          ▼                    ▼
                               ┌─────────────────┐   ┌─────────────────┐
                               │     spaces      │   │   audit_logs    │
                               └────────┬────────┘   └─────────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │ decision_spaces │◄──────┐
                               └─────────────────┘       │
                                                         │
                               ┌─────────────────┐       │
                               │arch_decisions   │───────┘
                               └────────┬────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │decision_history │
                               └─────────────────┘
```

---

## Core Tables

### `master_accounts`

Super admin accounts with full system access.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| username | VARCHAR(100) | NO | - | Unique username |
| password_hash | VARCHAR(255) | NO | - | Bcrypt hashed password |
| name | VARCHAR(255) | YES | 'System Administrator' | Display name |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| last_login | TIMESTAMP | YES | NULL | Last login timestamp |

**Indexes:** `username` (unique)

---

### `users`

Regular users authenticated via WebAuthn, SSO, or local password.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| email | VARCHAR(255) | NO | - | Unique email address |
| name | VARCHAR(255) | YES | NULL | Display name |
| password_hash | VARCHAR(255) | YES | NULL | Bcrypt hashed password (for local auth) |
| sso_subject | VARCHAR(255) | YES | NULL | SSO provider subject ID |
| sso_domain | VARCHAR(255) | NO | - | Domain for multi-tenancy |
| auth_type | VARCHAR(20) | NO | 'local' | Auth method: 'sso', 'webauthn', 'local' |
| is_admin | BOOLEAN | NO | FALSE | Legacy admin flag (use TenantMembership.global_role instead) |
| email_verified | BOOLEAN | NO | FALSE | Email verification status |
| has_seen_admin_onboarding | BOOLEAN | NO | FALSE | Admin onboarding modal shown |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| last_login | TIMESTAMP | YES | NULL | Last login timestamp |

**Indexes:** `email` (unique), `sso_domain`

---

### `webauthn_credentials`

WebAuthn/Passkey credentials for passwordless authentication.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| user_id | INTEGER | NO | - | FK to users.id |
| credential_id | BYTEA | NO | - | Raw credential ID bytes |
| public_key | BYTEA | NO | - | COSE public key |
| sign_count | INTEGER | NO | 0 | Signature counter |
| device_name | VARCHAR(255) | YES | NULL | User-friendly device name |
| transports | VARCHAR(255) | YES | NULL | JSON array of transports |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| last_used_at | TIMESTAMP | YES | NULL | Last authentication timestamp |

**Indexes:** `credential_id` (unique), `user_id`

---

## v1.5 Governance Tables

### `tenants`

Represents organizations/domains in the multi-tenant system.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| domain | VARCHAR(255) | NO | - | Unique domain identifier |
| name | VARCHAR(255) | YES | NULL | Display name |
| status | VARCHAR(20) | NO | 'active' | Status: 'active', 'suspended' |
| maturity_state | VARCHAR(20) | NO | 'bootstrap' | 'bootstrap' or 'mature' |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| maturity_age_days | INTEGER | NO | 14 | Days until auto-mature |
| maturity_user_threshold | INTEGER | NO | 5 | User count for auto-mature |

**Indexes:** `domain` (unique)

**Maturity Rules:**
- Tenant starts in `bootstrap` state
- Transitions to `mature` when ANY of:
  - 2+ full ADMINs
  - 1 ADMIN + 1 STEWARD
  - User count >= `maturity_user_threshold`
  - Age >= `maturity_age_days`

---

### `tenant_memberships`

Links users to tenants with their role.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| user_id | INTEGER | NO | - | FK to users.id |
| tenant_id | INTEGER | NO | - | FK to tenants.id |
| global_role | VARCHAR(30) | NO | 'user' | Role in tenant |
| joined_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Join timestamp |

**Indexes:** `user_id`, `tenant_id`
**Constraints:** `UNIQUE(user_id, tenant_id)`

**Global Roles:**
| Role | Description |
|------|-------------|
| `user` | Regular member |
| `provisional_admin` | First user, limited admin powers until mature |
| `steward` | Can approve requests, promote to steward |
| `admin` | Full admin powers |

---

### `tenant_settings`

Tenant-specific configuration (one-to-one with tenant).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| tenant_id | INTEGER | NO | - | FK to tenants.id (unique) |
| auth_method | VARCHAR(20) | NO | 'local' | Auth method: 'sso', 'webauthn', 'local' |
| allow_password | BOOLEAN | NO | TRUE | Allow password login |
| allow_passkey | BOOLEAN | NO | TRUE | Allow passkey login |
| rp_name | VARCHAR(255) | NO | 'Architecture Decisions' | WebAuthn RP name |
| allow_registration | BOOLEAN | NO | TRUE | Allow new user registration |
| require_approval | BOOLEAN | NO | FALSE | Require admin approval to join |
| tenant_prefix | VARCHAR(3) | YES | NULL | 3-letter prefix for decision IDs |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Last update timestamp |

**Indexes:** `tenant_id` (unique), `tenant_prefix` (unique)

---

### `spaces`

Organizational spaces within a tenant.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| tenant_id | INTEGER | NO | - | FK to tenants.id |
| name | VARCHAR(255) | NO | - | Space name |
| description | TEXT | YES | NULL | Space description |
| is_default | BOOLEAN | NO | FALSE | Is default space for tenant |
| visibility_policy | VARCHAR(30) | NO | 'tenant_visible' | Visibility policy |
| created_by_id | INTEGER | YES | NULL | FK to users.id |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |

**Indexes:** `tenant_id`

**Visibility Policies:**
| Policy | Description |
|--------|-------------|
| `tenant_visible` | All tenant members see decisions |
| `space_focused` | Default view scoped to space |

---

### `decision_spaces`

Links decisions to spaces (many-to-many).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| decision_id | INTEGER | NO | - | FK to architecture_decisions.id |
| space_id | INTEGER | NO | - | FK to spaces.id |
| added_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Link creation timestamp |
| added_by_id | INTEGER | YES | NULL | FK to users.id |

**Constraints:** `UNIQUE(decision_id, space_id)`

---

### `audit_logs`

Immutable audit log for admin/steward actions.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| tenant_id | INTEGER | NO | - | FK to tenants.id |
| actor_user_id | INTEGER | NO | - | FK to users.id (who performed action) |
| action_type | VARCHAR(50) | NO | - | Action type code |
| target_entity | VARCHAR(50) | YES | NULL | Target entity type |
| target_id | INTEGER | YES | NULL | Target entity ID |
| details | JSONB | YES | NULL | Additional action details |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Action timestamp |

**Indexes:** `tenant_id`, `created_at`

**Action Types:**
- `promote_user`, `demote_user`
- `change_setting`
- `approve_request`, `reject_request`
- `create_space`, `delete_space`
- `maturity_change`
- `user_joined`, `user_left`

---

## ADR Tables

### `architecture_decisions`

Main table for Architecture Decision Records.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| title | VARCHAR(255) | NO | - | Decision title |
| context | TEXT | NO | - | Context/background |
| decision | TEXT | NO | - | The decision made |
| status | VARCHAR(50) | NO | 'proposed' | Status code |
| consequences | TEXT | NO | - | Consequences of decision |
| decision_number | INTEGER | YES | NULL | Sequential number per tenant |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Last update timestamp |
| domain | VARCHAR(255) | NO | - | Domain (legacy, use tenant_id) |
| tenant_id | INTEGER | YES | NULL | FK to tenants.id |
| created_by_id | INTEGER | YES | NULL | FK to users.id |
| updated_by_id | INTEGER | YES | NULL | FK to users.id |
| deleted_at | TIMESTAMP | YES | NULL | Soft delete timestamp |
| deleted_by_id | INTEGER | YES | NULL | FK to users.id |

**Indexes:** `domain`, `tenant_id`

**Valid Statuses:** `proposed`, `accepted`, `deprecated`, `superseded`

**Display ID Format:** `{tenant_prefix}-{decision_number:03d}` (e.g., `GYH-034`)

---

### `decision_history`

Tracks update history of decisions.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| decision_id | INTEGER | NO | - | FK to architecture_decisions.id |
| title | VARCHAR(255) | NO | - | Title at time of change |
| context | TEXT | NO | - | Context at time of change |
| decision_text | TEXT | NO | - | Decision at time of change |
| status | VARCHAR(50) | NO | - | Status at time of change |
| consequences | TEXT | NO | - | Consequences at time of change |
| changed_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Change timestamp |
| change_reason | VARCHAR(500) | YES | NULL | Reason for change |
| changed_by_id | INTEGER | YES | NULL | FK to users.id |

---

### `decision_infrastructure`

Links decisions to infrastructure items (many-to-many).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| decision_id | INTEGER | NO | - | FK to architecture_decisions.id |
| infrastructure_id | INTEGER | NO | - | FK to it_infrastructure.id |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Link creation timestamp |

**Primary Key:** `(decision_id, infrastructure_id)`

---

### `it_infrastructure`

IT Infrastructure items that decisions can be mapped to.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| name | VARCHAR(255) | NO | - | Infrastructure name |
| type | VARCHAR(50) | NO | - | Infrastructure type |
| description | TEXT | YES | NULL | Description |
| domain | VARCHAR(255) | NO | - | Domain for multi-tenancy |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Last update timestamp |
| created_by_id | INTEGER | YES | NULL | FK to users.id |

**Valid Types:** `application`, `network`, `database`, `server`, `service`, `api`, `storage`, `cloud`, `container`, `other`

---

## Authentication Tables

### `sso_configs`

SSO configuration for OpenID Connect providers.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| domain | VARCHAR(255) | NO | - | Domain this config applies to |
| provider_name | VARCHAR(100) | NO | - | Provider name (Google, Okta, etc.) |
| client_id | VARCHAR(255) | NO | - | OAuth client ID |
| client_secret | VARCHAR(255) | NO | - | OAuth client secret (encrypted) |
| discovery_url | VARCHAR(500) | NO | - | OIDC discovery URL |
| enabled | BOOLEAN | NO | TRUE | Is config enabled |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Last update timestamp |

**Indexes:** `domain` (unique)

---

### `auth_configs`

Domain authentication configuration (legacy, migrated to tenant_settings).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| domain | VARCHAR(255) | NO | - | Domain |
| auth_method | VARCHAR(20) | NO | 'local' | Auth method |
| allow_password | BOOLEAN | NO | TRUE | Allow password |
| allow_passkey | BOOLEAN | NO | TRUE | Allow passkey |
| allow_registration | BOOLEAN | NO | TRUE | Allow registration |
| require_approval | BOOLEAN | NO | FALSE | Require approval |
| rp_name | VARCHAR(255) | NO | 'Architecture Decisions' | WebAuthn RP name |
| tenant_prefix | VARCHAR(3) | YES | NULL | 3-letter prefix |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Last update timestamp |

**Indexes:** `domain` (unique), `tenant_prefix` (unique)

---

### `setup_tokens`

Setup tokens for credential setup flows.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| user_id | INTEGER | YES | NULL | FK to users.id |
| email | VARCHAR(320) | YES | NULL | Email for pre-user tokens |
| token_hash | VARCHAR(255) | NO | - | SHA-256 hash of token |
| purpose | VARCHAR(20) | NO | 'initial_setup' | Token purpose |
| expires_at | TIMESTAMP | NO | - | Expiration timestamp |
| used_at | TIMESTAMP | YES | NULL | When token was used |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |

**Indexes:** `token_hash` (unique)

**Purposes:** `initial_setup`, `account_recovery`, `admin_invite`

---

### `email_verifications`

Email verification tokens.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| email | VARCHAR(255) | NO | - | Email to verify |
| name | VARCHAR(255) | YES | NULL | User name for signup |
| token | VARCHAR(255) | NO | - | Verification token |
| purpose | VARCHAR(50) | NO | 'signup' | Purpose code |
| domain | VARCHAR(255) | NO | - | Domain |
| expires_at | TIMESTAMP | NO | - | Expiration timestamp |
| verified_at | TIMESTAMP | YES | NULL | Verification timestamp |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| access_request_reason | TEXT | YES | NULL | Reason for access request |

**Indexes:** `email`, `token` (unique)

---

### `access_requests`

Access requests for users wanting to join a tenant.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| email | VARCHAR(255) | NO | - | Requester email |
| name | VARCHAR(255) | NO | - | Requester name |
| domain | VARCHAR(255) | NO | - | Domain requesting access to |
| reason | TEXT | YES | NULL | Reason for request |
| status | VARCHAR(20) | NO | 'pending' | Status |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Last update timestamp |
| processed_by_id | INTEGER | YES | NULL | FK to users.id |
| processed_at | TIMESTAMP | YES | NULL | Processing timestamp |
| rejection_reason | TEXT | YES | NULL | Rejection reason |

**Indexes:** `domain`

**Statuses:** `pending`, `approved`, `rejected`

---

### `domain_approvals`

Domain approval for preventing public email domains.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| domain | VARCHAR(255) | NO | - | Domain name |
| status | VARCHAR(20) | NO | 'pending' | Status |
| requested_by_email | VARCHAR(255) | YES | NULL | First requester email |
| requested_by_name | VARCHAR(255) | YES | NULL | First requester name |
| approved_by_id | INTEGER | YES | NULL | FK to master_accounts.id |
| rejection_reason | VARCHAR(500) | YES | NULL | Rejection reason |
| auto_approved | BOOLEAN | NO | FALSE | Was auto-approved |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| reviewed_at | TIMESTAMP | YES | NULL | Review timestamp |

**Indexes:** `domain` (unique)

**Statuses:** `pending`, `approved`, `rejected`

---

## System Tables

### `system_config`

Global system configuration.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| key | VARCHAR(100) | NO | - | Config key |
| value | VARCHAR(500) | YES | NULL | Config value |
| description | VARCHAR(500) | YES | NULL | Description |
| updated_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Last update timestamp |

**Indexes:** `key` (unique)

**Standard Keys:**
- `email_verification_required` - Require email verification
- `super_admin_notification_email` - Admin notification email
- `admin_session_timeout_hours` - Admin session timeout (default: 1)
- `user_session_timeout_hours` - User session timeout (default: 8)

---

### `email_configs`

Email/SMTP configuration for notifications.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| domain | VARCHAR(255) | NO | - | Associated domain |
| smtp_server | VARCHAR(255) | NO | - | SMTP server hostname |
| smtp_port | INTEGER | NO | 587 | SMTP port |
| smtp_username | VARCHAR(255) | NO | - | SMTP username |
| smtp_password | VARCHAR(255) | NO | - | SMTP password (encrypted) |
| from_email | VARCHAR(255) | NO | - | From email address |
| from_name | VARCHAR(255) | NO | 'Architecture Decisions' | From display name |
| use_tls | BOOLEAN | NO | TRUE | Use TLS |
| enabled | BOOLEAN | NO | TRUE | Is config enabled |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Last update timestamp |

**Indexes:** `domain` (unique)

---

### `subscriptions`

User notification subscriptions.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | auto | Primary key |
| user_id | INTEGER | NO | - | FK to users.id (unique) |
| notify_on_create | BOOLEAN | NO | TRUE | Notify on new decisions |
| notify_on_update | BOOLEAN | NO | FALSE | Notify on updates |
| notify_on_status_change | BOOLEAN | NO | TRUE | Notify on status changes |
| created_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NO | CURRENT_TIMESTAMP | Last update timestamp |

**Indexes:** `user_id` (unique)

---

## Migration Notes

### Auto-migrations on App Startup

The following columns are automatically added by `app.py` if they don't exist:

| Table | Column | Added By |
|-------|--------|----------|
| `domain_approvals` | `auto_approved` | Inline migration |
| `auth_configs` | `tenant_prefix` | Inline migration |
| `architecture_decisions` | `decision_number` | Inline migration |
| `setup_tokens` | `purpose` | Inline migration |
| `setup_tokens` | `email` | Inline migration |

### v1.5 Migration Script

The `scripts/migrate_to_v15.py` script handles:
1. Creating v1.5 tables (tenants, tenant_memberships, etc.)
2. Adding `tenant_id` column to `architecture_decisions`
3. Creating tenants from existing domains
4. Creating tenant memberships for existing users
5. Migrating auth_configs to tenant_settings
6. Linking decisions to tenants
7. Creating default spaces

Run with: `python scripts/migrate_to_v15.py [--dry-run] [--verbose]`
