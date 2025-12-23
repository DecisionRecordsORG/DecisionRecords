# Authentication Flows

This document defines the authentication flows for the Architecture Decisions application. These are the **requirements** that the implementation must satisfy.

## Table of Contents
- [Design Principles](#design-principles)
- [Authentication Types](#authentication-types)
- [User States](#user-states)
- [Flow 1: New User Signup (First user for domain)](#flow-1-new-user-signup-first-user-for-domain)
- [Flow 2: New User Signup (Existing domain)](#flow-2-new-user-signup-existing-domain)
- [Flow 3: Login with Passkey](#flow-3-login-with-passkey)
- [Flow 4: Login with Password](#flow-4-login-with-password)
- [Flow 5: Account Recovery](#flow-5-account-recovery)
- [Flow 6: Add Backup Authentication](#flow-6-add-backup-authentication)
- [Flow 7: Sign in with Google](#flow-7-sign-in-with-google)
- [Flow 8: Sign in with Slack](#flow-8-sign-in-with-slack)
- [Admin-Enforced Authentication](#admin-enforced-authentication)
- [Security Requirements](#security-requirements)
- [Success Criteria](#success-criteria)

---

## Design Principles

1. **Passkeys are preferred** - Encourage users to use passkeys (more secure, phishing-resistant)
2. **No access without credentials** - Users MUST have at least one authentication method before accessing the app
3. **Recovery is essential** - Users must have a way to recover their account if they lose their device
4. **Progressive security** - Allow password as fallback, but encourage passkey adoption
5. **Email verification as security layer** - When enabled, ensures email ownership before account creation
6. **OAuth simplifies onboarding** - OAuth providers (Google, Slack) verify identity, so OAuth users skip email verification

---

## Authentication Types

The `auth_type` field tracks the user's authentication method:

| auth_type | Description | Requires Credential Setup |
|-----------|-------------|---------------------------|
| `webauthn` | Passkey authentication (FIDO2/WebAuthn) | No - passkey is the credential |
| `local` | Password-based authentication | No - password is the credential |
| `sso` | OAuth/SSO authentication (Google, Slack, Enterprise SAML) | No - OAuth is the credential |

### How auth_type is Set

1. **Initial Signup with Passkey**: `auth_type = 'webauthn'`
2. **Initial Signup with Password**: `auth_type = 'local'`
3. **Sign in with Google**: `auth_type = 'sso'` (only if user had no auth_type or was 'local')
4. **Sign in with Slack**: `auth_type = 'sso'` (only if user had no auth_type or was 'local')
5. **Enterprise SAML SSO**: `auth_type = 'sso'`

### Auth Type Preservation

When a user signs in with a different method than their original setup, the behavior is:

| Original auth_type | Signs in with | Resulting auth_type | Notes |
|--------------------|---------------|---------------------|-------|
| `webauthn` | Google OAuth | `webauthn` | Preserved - user has existing passkey |
| `webauthn` | Slack OIDC | `webauthn` | Preserved - user has existing passkey |
| `local` | Google OAuth | `sso` | Updated - OAuth becomes primary method |
| `local` | Slack OIDC | `sso` | Updated - OAuth becomes primary method |
| (none) | Google OAuth | `sso` | Set - OAuth is first auth method |
| (none) | Slack OIDC | `sso` | Set - OAuth is first auth method |

**Rationale**: If a user already has passkey authentication set up, we preserve it because passkeys are considered more secure and the user may want to continue using them. OAuth just becomes an alternative login method. However, if a user only had password ('local'), switching to OAuth upgrades their security posture.

---

## System Settings (Super Admin)

These settings affect authentication behavior for all tenants:

| Setting | Default | Description |
|---------|---------|-------------|
| Email Verification | ON | Require email verification before account creation |
| Admin Session Timeout | 1 hour | How long super admin stays logged in |
| User Session Timeout | 8 hours | How long regular users stay logged in |

### Email Configuration

The system uses **AWS SES** for sending emails:
- Verification emails for signup
- Account recovery emails
- Notification emails (decision updates, etc.)

Email settings are configured in the Super Admin portal under "Email Configuration".

---

## User States

A user can be in one of these states:

| State | has_passkey | has_password | Can Access App |
|-------|-------------|--------------|----------------|
| `incomplete` | false | false | NO - must complete setup |
| `passkey_only` | true | false | YES |
| `password_only` | false | true | YES |
| `full` | true | true | YES |

**Critical Rule**: A user in `incomplete` state MUST be redirected to credential setup and CANNOT access any other part of the application.

---

## Flow 1: New User Signup (First user for domain)

This user becomes the tenant admin.

### Prerequisites
- Super admin email verification setting determines which sub-flow is used
- Email is sent via AWS SES (configured in super admin portal)

### Steps

```
1. User enters email on landing page
2. System checks domain:
   - If public domain (gmail, yahoo, etc.) → REJECT with message
   - If disposable domain → REJECT with message
   - If corporate domain → CONTINUE
3. System checks if domain has existing users:
   - No users → This is a new tenant, user will be admin
4. System checks EMAIL VERIFICATION setting:
   - If ON → Email Verification Flow (Flow 1A)
   - If OFF → Direct Signup Flow (Flow 1B)
```

### Flow 1A: Email Verification ON (Default, More Secure)

```
1. User enters name
2. System sends verification email via AWS SES
3. User receives email with verification link
4. User clicks link → lands on verification page
5. System verifies token, creates user account
6. User selects auth method:
   - Passkey (recommended) → passkey registration
   - Password → password entry
7. User completes credential setup
8. User is logged in and redirected to dashboard
```

### Flow 1B: Email Verification OFF (Direct Signup)

```
1. User enters name
2. User selects auth preference on signup form:
   - "Use Passkey (recommended)" → passkey flow
   - "Use Password" → password flow

### Passkey Sub-flow:
   2a.1. System creates user account (incomplete state, email auto-verified)
   2a.2. System logs user in (session created)
   2a.3. System redirects to /[domain]/profile?setup=passkey
   2a.4. Setup page prompts WebAuthn registration
   2a.5. User completes passkey creation
   2a.6. System updates user state (has_passkey = true)
   2a.7. System redirects to /[domain] (dashboard)

### Password Sub-flow:
   2b.1. User enters password (min 8 chars)
   2b.2. System creates user account with password (email auto-verified)
   2b.3. System logs user in
   2b.4. System redirects to /[domain] (dashboard)
   2b.5. Dashboard shows prompt to add passkey for better security
```

### Success Criteria
- [ ] User cannot access /[domain] until they have passkey OR password
- [ ] First user for domain is automatically admin
- [ ] Domain approval record is created (auto-approved for corporate domains)
- [ ] User session is created after credential setup complete
- [ ] Email verification setting is respected (ON = verify first, OFF = direct signup)
- [ ] When email verification ON, verification email is sent via AWS SES

---

## Flow 2: New User Signup (Existing domain)

User joins an existing tenant.

### Approval Settings

Two independent concepts control user approval:

| Setting | Description | Who Controls |
|---------|-------------|--------------|
| `require_approval` | Whether new users must be approved | Tenant admin (in Settings) |
| `can_process_access_requests` | Whether tenant has admins who CAN approve | System (based on tenant maturity) |

**Effective Approval Requirement:**
```
effective_require_approval = require_approval AND can_process_access_requests
```

**Edge Case - Bootstrap Tenant:**
When a tenant is in BOOTSTRAP state (only has provisional admin), `can_process_access_requests=false` because provisional admins cannot approve access requests. In this case, even if `require_approval=true`, users are auto-approved to avoid a deadlock where no one can approve them.

### Steps

```
1. User enters email on landing page
2. System checks domain exists with users → YES
3. System computes effective_require_approval:
   - require_approval setting from AuthConfig
   - can_process_access_requests (has full admin or steward?)
   - effective = require_approval AND can_process_access_requests
4. Based on effective_require_approval:
   - If true → Access request flow (approval will be required)
   - If false → Direct signup flow (auto-approved)

### Direct Signup Flow:
   Same as Flow 1, steps 4-5, but user is NOT admin

### Access Request Flow:
   3a.1. User enters name and optional reason
   3a.2. System sends verification email
   3a.3. User clicks verification link
   3a.4. System creates access request (pending)
   3a.5. User sees "Pending Approval" page
   3a.6. Tenant admin approves request
   3a.7. User receives approval email
   3a.8. User clicks link → credential setup flow
   3a.9. After credential setup → dashboard
```

### API Response Fields

The `/api/auth/tenant/{domain}` endpoint returns:

| Field | Type | Description |
|-------|------|-------------|
| `require_approval` | boolean | Tenant's configured setting (admin's choice) |
| `can_process_access_requests` | boolean | Whether tenant has admins who can approve |
| `effective_require_approval` | boolean | Actual behavior (require_approval AND can_process_access_requests) |

### Success Criteria
- [ ] New users cannot access tenant data until approved (if effective approval required)
- [ ] New users cannot access app until credential setup complete
- [ ] Tenant admin is notified of access requests (if effective approval required)
- [ ] Bootstrap tenants auto-approve users (no deadlock)

---

## Flow 3: Login with Passkey

### Steps

```
1. User navigates to /[domain]/login
2. User clicks "Sign in with Passkey"
3. System initiates WebAuthn authentication
4. Browser prompts for passkey (biometric/PIN)
5. User authenticates with device
6. System verifies credential
7. System creates session
8. System redirects to /[domain] (dashboard)
```

### Success Criteria
- [ ] Login completes in < 5 seconds
- [ ] Failed attempts are rate-limited
- [ ] Session timeout respects system settings

---

## Flow 4: Login with Password

### Steps

```
1. User navigates to /[domain]/login
2. User enters email and password
3. System verifies credentials
4. System creates session
5. System redirects to /[domain] (dashboard)
```

### Success Criteria
- [ ] Failed attempts are rate-limited (5 per minute)
- [ ] Account lockout after 10 failed attempts
- [ ] Password is never logged

---

## Flow 5: Account Recovery

For users who lose access to their passkey device.

### Scenario A: User has password backup

```
1. User clicks "Trouble signing in?"
2. User selects "Sign in with password instead"
3. Normal password login flow
4. After login, prompt to register new passkey
```

### Scenario B: User has passkey only (no password)

```
1. User clicks "Trouble signing in?"
2. User selects "I lost access to my passkey"
3. System sends recovery email to user's address
4. User clicks recovery link (valid 1 hour)
5. System prompts to set a password OR register new passkey
6. User completes credential setup
7. System invalidates old passkeys (optional, configurable)
8. User is logged in
```

### Success Criteria
- [ ] Recovery email is sent within 30 seconds
- [ ] Recovery link expires after 1 hour
- [ ] Recovery link is single-use
- [ ] User can choose new auth method during recovery

---

## Flow 6: Add Backup Authentication

Users should be encouraged to have multiple auth methods.

### Add Passkey (for password-only users)

```
1. User goes to Profile page
2. User clicks "Add Passkey"
3. WebAuthn registration flow
4. Passkey added to account
```

### Add Password (for passkey-only users)

```
1. User goes to Profile page
2. User clicks "Add Password Backup"
3. User enters new password (with confirmation)
4. Password added to account
5. User now has recovery option
```

### Success Criteria
- [ ] Users with only one auth method see a warning/prompt
- [ ] Adding backup auth is easy and discoverable

---

## Flow 7: Sign in with Google

Google OAuth 2.0 provides a convenient sign-in option for organizations using Google Workspace.

### Prerequisites
- Google OAuth must be enabled (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET configured)
- User's email domain must match their Google account domain

### New User Flow (First-time Google Sign-in)

```
1. User clicks "Sign in with Google" on landing page
2. User is redirected to Google's consent screen
3. User selects their Google account
4. Google verifies identity and returns to callback
5. System extracts email from Google's response
6. System checks if user exists:
   - No → Create new user with:
     - email_verified = true (Google verified the email)
     - auth_type = 'sso'
     - setup_mode = false (no credential setup needed)
     - has_passkey = false, has_password = false
   - Yes → Sign in existing user
7. System checks/creates tenant for user's email domain
8. System creates session
9. System redirects to /{domain} (tenant dashboard)
```

### Existing User Flow (User has account, signs in with Google)

```
1. User clicks "Sign in with Google"
2. Google OAuth flow completes
3. System finds existing user by email
4. System updates auth_type:
   - If auth_type is null or 'local' → set to 'sso'
   - If auth_type is 'webauthn' → preserve (passkey remains primary)
5. System creates session
6. System redirects to /{domain} (tenant dashboard)
```

### Why OAuth Users Skip Credential Setup

OAuth users do NOT need to set up a passkey or password because:
1. **Identity is verified** - Google has already verified the user's email ownership
2. **OAuth IS the credential** - The user authenticates via Google each time
3. **Reduced friction** - Requiring additional credentials defeats the purpose of OAuth

The system recognizes OAuth users by checking `auth_type === 'sso'` and skips the credential setup flow.

### Success Criteria
- [ ] Google sign-in completes successfully
- [ ] New OAuth users skip email verification (Google verified them)
- [ ] New OAuth users skip credential setup (OAuth is their auth method)
- [ ] Existing passkey users can use Google as alternative login
- [ ] auth_type is set correctly based on user state

---

## Flow 8: Sign in with Slack

Slack OIDC provides sign-in for organizations using Slack Connect.

### Prerequisites
- Slack OIDC must be enabled (SLACK_CLIENT_ID and SLACK_CLIENT_SECRET configured)
- User's email domain must match their Slack workspace domain

### Flow

```
1. User clicks "Sign in with Slack" on landing page
2. User is redirected to Slack's authorization page
3. User authorizes the application
4. Slack verifies identity and returns to callback
5. System extracts email from Slack's response
6. Same user creation/lookup logic as Google OAuth
7. System creates session
8. System redirects to /{domain}?slack_welcome=1
```

### Slack Welcome Modal

New Slack users see a welcome modal explaining:
- How Decision Records integrates with Slack
- How to use the Slack app for decision tracking
- Quick start tips

---

## Admin-Enforced Authentication

Mature tenants can enforce specific authentication methods.

### Tenant Maturity Levels

| Level | Description | Can Enforce Auth |
|-------|-------------|------------------|
| BOOTSTRAP | Only provisional admin, no policies | No |
| GROWING | Has full admin, basic policies | Yes |
| MATURE | Full governance, compliance features | Yes |

### Enforceable Auth Methods

Tenant admins in GROWING or MATURE tenants can enforce:

| Method | Description | Effect |
|--------|-------------|--------|
| Passkey Only | Require WebAuthn passkeys | Users must have passkey to access |
| Password + Passkey | Require both methods | Users must have both credentials |
| Google SSO | Require Google Workspace login | Users must sign in via Google |
| Slack SSO | Require Slack login | Users must sign in via Slack |
| Any SSO | Allow any OAuth provider | Users can use Google or Slack |

### When Admin Enforces Google Auth

If a tenant admin enforces Google authentication:

1. **New users** must sign in with Google (other methods hidden)
2. **Existing passkey users** can continue using passkeys OR switch to Google
3. **Existing password users** must use Google (password login disabled)

**Note**: When a passkey user signs in with Google, their `auth_type` remains 'webauthn' but Google login is now available as an alternative. The enforcement applies to the LOGIN method, not the stored auth_type.

### Implementation Details

The `auth_type` field represents the user's **original/primary** auth setup, not necessarily how they logged in most recently. This allows:
- Users to have fallback auth methods
- Admins to enforce policies without breaking existing accounts
- Gradual migration to new auth methods

---

## Security Requirements

### Session Management
- Admin sessions: 1 hour timeout (configurable)
- User sessions: 8 hours timeout (configurable)
- Sessions invalidated on password change
- Sessions invalidated on passkey revocation

### Rate Limiting
- Login attempts: 5 per minute per IP
- Signup attempts: 3 per minute per IP
- Recovery requests: 3 per hour per email

### Credential Storage
- Passwords: bcrypt with cost factor 12
- Passkey public keys: stored as-is (not secret)
- Session tokens: secure random, httponly cookies

---

## Success Criteria Checklist

### Signup Flow
- [ ] User cannot access app without at least one credential
- [ ] Passkey registration works on desktop and mobile
- [ ] Password meets minimum requirements (8+ chars)
- [ ] First user becomes admin
- [ ] Corporate domains are auto-approved
- [ ] Public/disposable domains are rejected

### Login Flow
- [ ] Passkey login works
- [ ] Password login works
- [ ] Failed attempts are rate-limited
- [ ] Session respects timeout settings

### Recovery Flow
- [ ] Password users can login if passkey lost
- [ ] Passkey-only users can recover via email
- [ ] Recovery links expire appropriately

### Security
- [ ] No access to app data without valid credential
- [ ] Sessions expire correctly
- [ ] CSRF protection on all forms
- [ ] Rate limiting prevents brute force

---

## Current Issues (To Fix)

1. **CRITICAL**: Users can access app without any credential (incomplete state allows access)
2. **CRITICAL**: Frontend doesn't redirect to passkey setup after signup
3. **MISSING**: Account recovery flow for passkey-only users
4. **MISSING**: Prompt for backup auth method

---

*Last Updated: December 23, 2025 - Added Google OAuth and Slack OIDC flows, auth_type documentation*
