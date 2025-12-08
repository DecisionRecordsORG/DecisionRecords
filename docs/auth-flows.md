# Authentication Flows

This document defines the authentication flows for the Architecture Decisions application. These are the **requirements** that the implementation must satisfy.

## Table of Contents
- [Design Principles](#design-principles)
- [User States](#user-states)
- [Flow 1: New User Signup (First user for domain)](#flow-1-new-user-signup-first-user-for-domain)
- [Flow 2: New User Signup (Existing domain)](#flow-2-new-user-signup-existing-domain)
- [Flow 3: Login with Passkey](#flow-3-login-with-passkey)
- [Flow 4: Login with Password](#flow-4-login-with-password)
- [Flow 5: Account Recovery](#flow-5-account-recovery)
- [Flow 6: Add Backup Authentication](#flow-6-add-backup-authentication)
- [Security Requirements](#security-requirements)
- [Success Criteria](#success-criteria)

---

## Design Principles

1. **Passkeys are preferred** - Encourage users to use passkeys (more secure, phishing-resistant)
2. **No access without credentials** - Users MUST have at least one authentication method before accessing the app
3. **Recovery is essential** - Users must have a way to recover their account if they lose their device
4. **Progressive security** - Allow password as fallback, but encourage passkey adoption

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

### Steps

```
1. User enters email on landing page
2. System checks domain:
   - If public domain (gmail, yahoo, etc.) → REJECT with message
   - If disposable domain → REJECT with message
   - If corporate domain → CONTINUE
3. System checks if domain has existing users:
   - No users → This is a new tenant, user will be admin
4. User enters name
5. User selects auth preference:
   - "Use Passkey (recommended)" → passkey flow
   - "Use Password" → password flow

### Passkey Flow (5a):
   5a.1. System creates user account (incomplete state)
   5a.2. System logs user in (session created)
   5a.3. System redirects to /[domain]/setup/passkey
   5a.4. Setup page prompts WebAuthn registration
   5a.5. User completes passkey creation
   5a.6. System updates user state (has_passkey = true)
   5a.7. System redirects to /[domain] (dashboard)

### Password Flow (5b):
   5b.1. User enters password (min 8 chars)
   5b.2. System creates user account with password
   5b.3. System logs user in
   5b.4. System redirects to /[domain] (dashboard)
   5b.5. Dashboard shows prompt to add passkey for better security
```

### Success Criteria
- [ ] User cannot access /[domain] until they have passkey OR password
- [ ] First user for domain is automatically admin
- [ ] Domain approval record is created (auto-approved for corporate domains)
- [ ] User session is created after credential setup complete

---

## Flow 2: New User Signup (Existing domain)

User joins an existing tenant.

### Steps

```
1. User enters email on landing page
2. System checks domain exists with users → YES
3. System checks tenant settings:
   - If require_approval = true → Access request flow
   - If require_approval = false → Direct signup flow

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

### Success Criteria
- [ ] New users cannot access tenant data until approved (if approval required)
- [ ] New users cannot access app until credential setup complete
- [ ] Tenant admin is notified of access requests

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

*Last Updated: December 2025*
