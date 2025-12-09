# Implementation Plan: Multi-tenant Auth Enhancements & UI Improvements (v1.4)

## Overview

This plan addresses 7 key feature areas based on user feedback. All changes follow the API integration guidelines in CLAUDE.md.

---

## Feature 1: Tenant Admin Auto-Approval Toggle

### Problem
All signups require tenant admin approval by default. Tenant admins need a toggle to allow users from their domain to sign up without manual approval.

### Current State
- `AuthConfig.require_approval` exists (Boolean, default: True)
- Frontend settings component has this toggle but needs clearer UX

### Solution
**Backend Changes (app.py):**
- Verify `/api/auth/send-verification` respects `require_approval` setting
- When `require_approval=False`, auto-approve users from same domain during signup
- Skip access_request creation when auto-approval is enabled

**Frontend Changes (settings.component.ts):**
- Ensure "Require Admin Approval" toggle is clearly visible in Authentication tab
- Add helper text: "When disabled, users with emails matching your domain can sign up without admin approval"
- Show confirmation dialog when toggling off (security implication)

### Files to Modify
- `app.py` - Verify signup flow logic (~lines 1612-1720)
- `frontend/src/app/components/settings/settings.component.ts` - Enhance toggle UX

---

## Feature 2: Decisions UI Improvements

### Problem
The decisions UI (screenshot) shows:
- Buttons not styled correctly (blue pill button needs Material styling)
- Status chips could use better styling
- Empty state could be more polished
- Overall layout needs Material Design consistency

### Solution
**Style Improvements:**
1. Replace custom button styles with `mat-raised-button` or `mat-flat-button`
2. Use `mat-chip-listbox` for status filters with proper colors
3. Add elevation and proper card styling
4. Improve empty state with centered layout and subtle icon
5. Ensure consistent spacing and typography

**Specific Changes:**
- "Create Decision" button: Use `mat-raised-button color="primary"`
- Status filter chips: Use `mat-chip` with `selected` state binding
- Card hover effects: Use Material elevation classes
- Empty state: Center content, use `mat-icon` with larger size

### Files to Modify
- `frontend/src/app/components/decision-list/decision-list.component.ts` - Template & styles
- `frontend/src/app/components/decision-detail/decision-detail.component.ts` - If needed

---

## Feature 3: Decision IDs with Tenant Prefix

### Problem
Decisions need visible IDs. Each tenant must have a unique 3-letter prefix (consonants only, no vowels) appended to a sequential number, e.g., "GYH-034", "JHB-002".

### Solution

**Database Changes (models.py):**
1. Add `tenant_prefix` field to a new `Tenant` model or to `AuthConfig`:
   ```python
   tenant_prefix = db.Column(db.String(3), unique=True, nullable=True)
   ```

2. Add `decision_number` field to `Decision` model:
   ```python
   decision_number = db.Column(db.Integer, nullable=False, default=1)
   ```

3. Add computed property for display ID:
   ```python
   @property
   def display_id(self):
       return f"{self.tenant_prefix}-{self.decision_number:03d}"
   ```

**Backend Changes (app.py):**
1. Auto-generate unique 3-letter prefix when tenant is created:
   - Use consonants only: B, C, D, F, G, H, J, K, L, M, N, P, Q, R, S, T, V, W, X, Y, Z
   - Check uniqueness before assigning
   - Generate on first decision or tenant creation

2. Auto-increment `decision_number` per tenant when creating decisions

3. Add endpoint to fetch/display decision by ID

**Frontend Changes:**
- Display ID prominently in decision cards and detail view
- Format: "GYH-034" (prefix-number with leading zeros)
- Add ID to decision list columns

### Files to Modify
- `models.py` - Add tenant_prefix to AuthConfig, decision_number to Decision
- `app.py` - Prefix generation, decision numbering logic
- `frontend/src/app/components/decision-list/decision-list.component.ts`
- `frontend/src/app/components/decision-detail/decision-detail.component.ts`
- `frontend/src/app/models/decision.model.ts` - Add display_id field

---

## Feature 4: Authentication Settings Clarification

### Problem
Authentication tab lists Passkey and SSO. Need to clarify:
- If nothing selected: offer both passkey and local password
- If Passkey selected: can enforce passkey-only
- If SSO selected: must be configured and verified
- Local password-only cannot be enforced (encourage passkey adoption)

### Current State
- `AuthConfig` has: `auth_method`, `allow_password`, `allow_passkey`
- These need clearer UI representation

### Solution

**Simplified Auth Options:**
1. **Default (Both)**: Users can choose passkey OR password
2. **Passkey Enforced**: Users must use passkey (no password option)
3. **SSO**: Users must use configured SSO provider

**Backend Validation:**
- Prevent selecting SSO unless SSO is configured and verified
- Prevent selecting "Password Only" (not an option)
- When "Passkey Enforced": set `allow_password=False`, `allow_passkey=True`

**Frontend Changes:**
- Radio group with 3 options:
  - "Passkey + Password (Default)" - Users choose their preference
  - "Passkey Only" - Enforce passkey authentication
  - "SSO" - Disabled if SSO not configured, shows "Configure SSO first"
- Remove confusing individual toggles
- Add info cards explaining each option

### Files to Modify
- `app.py` - Auth config validation
- `frontend/src/app/components/settings/settings.component.ts` - Simplified radio UI

---

## Feature 5: Account Recovery Flow (Self-Service)

### Problem
Users who lose access to their passkey/password have no recovery option. Users need a self-service way to recover their accounts.

### Current State
- `SetupToken` model exists with 48-hour validity
- Admin can generate setup links for incomplete accounts (separate feature)
- Need to add self-service account recovery for existing tenant members

### Solution

**Self-Service Recovery Flow:**
```
┌─────────────────────────────────────────────────────────────────┐
│                 SELF-SERVICE ACCOUNT RECOVERY                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User clicks "Forgot credentials?" on login page             │
│              │                                                  │
│              ▼                                                  │
│  2. User enters their email address                             │
│              │                                                  │
│              ▼                                                  │
│  3. Backend checks:                                             │
│     - Email exists as a user?                                   │
│     - User is member of a tenant?                               │
│     - Rate limit (2 min between requests)?                      │
│              │                                                  │
│      ┌───────┴───────┐                                          │
│      │               │                                          │
│      ▼               ▼                                          │
│   Valid: Send    Invalid: Show                                  │
│   recovery       generic "check                                 │
│   email          your email" (no leak)                          │
│      │                                                          │
│      ▼                                                          │
│  4. User clicks email link (valid 2 hours)                      │
│              │                                                  │
│              ▼                                                  │
│  5. Token validated → redirect to /recover/:token               │
│              │                                                  │
│              ▼                                                  │
│  6. User sets up new passkey OR password                        │
│              │                                                  │
│              ▼                                                  │
│  7. Credentials updated → logged in                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Extend SetupToken:**
1. Add `purpose` field: 'initial_setup' | 'account_recovery' | 'admin_invite'
2. Recovery tokens should:
   - Be user-initiated (self-service)
   - Allow user to set up new passkey or password
   - Be valid for 2 hours
   - Only work for users who are members of a tenant

**New Backend Endpoints:**
```python
# Self-service: User requests their own recovery link
POST /api/auth/request-recovery
Body: { "email": "user@example.com" }
Response: { "message": "If an account exists, a recovery link has been sent" }

# Admin: Send setup link for incomplete accounts (existing feature, clarified)
POST /api/admin/users/<user_id>/send-setup-email
Response: { "message": "Setup link sent to user" }
```

**Frontend - Login Page:**
- Add "Forgot your credentials?" link
- Opens recovery request dialog
- User enters email
- Shows success message (always same message for security)

**Frontend - Recovery Flow:**
- New component: `account-recovery.component.ts`
- Route: `/recover/:token`
- Shows: "Reset your account credentials"
- Options: Set up new passkey OR create password
- Error handling for expired/invalid tokens

### Files to Modify
- `models.py` - Extend SetupToken with purpose, shorter expiry for recovery
- `app.py` - Add self-service recovery endpoint
- `frontend/src/app/components/login/login.component.ts` - Add recovery link
- `frontend/src/app/components/account-recovery/` - New component
- `frontend/src/app/app.routes.ts` - Add recovery route

---

## Feature 6: Email Verification Flow

### Problem
When super admin enables email verification:
1. All signups must verify email first
2. User receives link to complete account setup
3. Link valid for 2 hours
4. Need flow to request new verification link

### Current State
- `EmailVerification` model exists
- `SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED` exists
- Basic flow in place but needs testing and refinement

### Solution

**Complete Email Verification Flow:**

```
┌─────────────────────────────────────────────────────────────────┐
│                      SIGNUP FLOW                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User enters email on signup page                            │
│              │                                                  │
│              ▼                                                  │
│  2. Backend checks: email_verification_required?                │
│              │                                                  │
│      ┌───────┴───────┐                                          │
│      │               │                                          │
│      ▼               ▼                                          │
│   YES: Send      NO: Direct                                     │
│   verification   signup                                         │
│   email          (existing flow)                                │
│      │                                                          │
│      ▼                                                          │
│  3. User clicks email link                                      │
│     (valid 2 hours)                                             │
│              │                                                  │
│              ▼                                                  │
│  4. Token validated → redirect to /setup/:token                 │
│              │                                                  │
│              ▼                                                  │
│  5. User sets up passkey or password                            │
│              │                                                  │
│              ▼                                                  │
│  6. Account created → logged in                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 RESEND VERIFICATION FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User on login page clicks "Resend verification email"       │
│              │                                                  │
│              ▼                                                  │
│  2. User enters email                                           │
│              │                                                  │
│              ▼                                                  │
│  3. Backend checks:                                             │
│     - Email exists in EmailVerification?                        │
│     - Not already verified?                                     │
│     - Rate limit (2 min between requests)?                      │
│              │                                                  │
│              ▼                                                  │
│  4. Generate new token, invalidate old one                      │
│              │                                                  │
│              ▼                                                  │
│  5. Send new verification email                                 │
│              │                                                  │
│              ▼                                                  │
│  6. Show success: "Check your email"                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Backend Changes:**
1. Change `EmailVerification` default expiry from 24h to 2h
2. Add `/api/auth/resend-verification` endpoint
3. Ensure signup flow checks `email_verification_required` setting
4. Add clear error messages for expired/invalid tokens

**Frontend Changes:**
1. Update signup component to show "Check your email" after submission
2. Add "Resend verification email" link on login page
3. Add resend dialog/form component
4. Handle expired token gracefully with resend option

### Files to Modify
- `models.py` - Update EmailVerification expiry default
- `app.py` - Add resend endpoint, verify flow logic
- `frontend/src/app/components/signup/signup.component.ts`
- `frontend/src/app/components/login/login.component.ts` - Add resend link
- `frontend/src/app/components/verify-email/` - Handle token validation

---

## Feature 7: Unified Setup Link System

### Problem
Setup links are used for:
1. Initial account setup (after email verification)
2. Account recovery (admin-generated)
3. Completing incomplete accounts

Need a unified, secure system.

### Solution

**Unified Setup Token:**
```python
class SetupToken:
    purpose: 'email_verification' | 'account_recovery' | 'admin_invite'
    expires_at: DateTime  # 2 hours for verification/recovery, 48h for invite
    user_id: Optional[int]  # Set after email verified
    email: Optional[str]  # For verification before user created
```

**Setup Page Flow:**
```
/setup/:token
    │
    ├── Validate token
    │       │
    │       ├── Invalid/Expired → Show error + "Request new link"
    │       │
    │       └── Valid → Continue
    │
    ├── Check purpose
    │       │
    │       ├── email_verification → Create user if needed
    │       ├── account_recovery → Show recovery options
    │       └── admin_invite → Show setup options
    │
    └── Show credential setup form
            │
            ├── Option 1: Set up Passkey
            └── Option 2: Create Password
```

### Files to Modify
- `models.py` - Unify SetupToken purposes
- `app.py` - Unified setup endpoints
- `frontend/src/app/components/account-setup/account-setup.component.ts`

---

## Implementation Order

### Phase 1: Foundation (Backend)
1. Database migrations for new fields (tenant_prefix, decision_number, setup token purpose)
2. Decision ID generation logic
3. Update email verification expiry to 2 hours
4. Add resend verification endpoint
5. Add recovery link endpoints

### Phase 2: Auth Flow Improvements
1. Verify auto-approval toggle works correctly
2. Simplify authentication settings UI
3. Test email verification flow end-to-end
4. Implement resend verification flow

### Phase 3: UI Improvements
1. Decision list Material styling improvements
2. Decision ID display
3. Settings component auth section cleanup
4. Account recovery component

### Phase 4: Testing & Polish
1. Test all flows locally
2. Test email sending
3. Edge cases (expired tokens, rate limiting)
4. Deploy and verify in production

---

## Database Migration Required

```python
# Add to models.py

# 1. Tenant prefix on AuthConfig
AuthConfig.tenant_prefix = db.Column(db.String(3), unique=True, nullable=True)

# 2. Decision number on Decision
Decision.decision_number = db.Column(db.Integer, nullable=False, default=1)

# 3. Setup token purpose
SetupToken.purpose = db.Column(db.String(20), default='initial_setup')
SetupToken.email = db.Column(db.String(320), nullable=True)  # For pre-user tokens
```

---

## API Endpoints Summary

### New Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/resend-verification` | Resend verification email |
| POST | `/api/auth/request-recovery` | Self-service: User requests recovery link |
| POST | `/api/admin/users/<id>/send-setup-email` | Admin: Send setup link for incomplete accounts |

### Modified Endpoints
| Method | Path | Change |
|--------|------|--------|
| POST | `/api/auth/send-verification` | Respect auto-approval setting |
| POST | `/api/decisions` | Auto-assign decision number |
| GET | `/api/decisions` | Include display_id in response |

---

## Testing Checklist

- [ ] Email verification flow (super admin enabled)
- [ ] Resend verification email
- [ ] Auto-approval toggle
- [ ] Passkey-only enforcement
- [ ] Account recovery flow
- [ ] Decision ID generation (unique per tenant)
- [ ] Decision ID display in UI
- [ ] Material styling on decisions page
- [ ] All flows work in production with HTTPS

---

## Notes

- All setup/verification links are 2 hours validity (changed from 24h)
- Rate limit on resend: 2 minutes between requests
- Tenant prefix uses consonants only (21 letters), 3 chars = 9,261 unique combinations
- Decision numbers are sequential per tenant, formatted with leading zeros (001, 002, etc.)
