# v2.0 Licensing & Business Model Plan

## Executive Summary

This document outlines the technical changes required to support the dual-licensing model:
- **Self-hosted (Apache 2.0)**: Free, unlimited, community-supported
- **Cloud-hosted**: Tiered pricing with enterprise features

---

## 1. Pricing Tiers Analysis

### Tier Breakdown

| Feature | Self-Hosted | Cloud Free | Team ($49/mo) | Enterprise | Regulated Add-On |
|---------|-------------|------------|---------------|------------|------------------|
| Users | Unlimited | 5 | 50 | Unlimited | - |
| Tenants | Unlimited | 3 | Unlimited | Unlimited | - |
| Storage | Unlimited | 2 GB | TBD | Unlimited | - |
| Audit Log Retention | Unlimited | 30 days | 1 year | 10 years | Immutable |
| SSO (SAML/OIDC) | Yes | No | Yes | Yes | - |
| SCIM Provisioning | No | No | No | Yes | - |
| IP Allowlists | No | No | No | Yes | - |
| Data Residency | No | No | No | Yes | - |
| CMEK | No | No | No | No | Yes |
| Priority Support | No | No | Yes | SLA-based | Yes |
| API Rate Limits | None | Basic | Increased | Custom | Custom |

---

## 2. Schema Changes

### 2.1 New Models

#### `Plan` - Defines available subscription plans

```python
class Plan(db.Model):
    """Subscription plans available in the system."""
    __tablename__ = 'plans'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # 'free', 'team', 'enterprise', 'regulated'
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price_monthly_cents = db.Column(db.Integer, default=0)  # Price in cents (4900 = €49)
    price_annual_cents = db.Column(db.Integer, default=0)   # Annual price (discount)
    is_active = db.Column(db.Boolean, default=True)
    is_addon = db.Column(db.Boolean, default=False)  # True for "Regulated Industries Add-On"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Limits (null = unlimited)
    max_users = db.Column(db.Integer, nullable=True)          # null = unlimited
    max_tenants = db.Column(db.Integer, nullable=True)        # null = unlimited
    max_storage_bytes = db.Column(db.BigInteger, nullable=True)  # null = unlimited
    audit_retention_days = db.Column(db.Integer, nullable=True)  # null = unlimited

    # Feature flags
    sso_enabled = db.Column(db.Boolean, default=False)
    scim_enabled = db.Column(db.Boolean, default=False)
    ip_allowlist_enabled = db.Column(db.Boolean, default=False)
    data_residency_enabled = db.Column(db.Boolean, default=False)
    cmek_enabled = db.Column(db.Boolean, default=False)
    priority_support = db.Column(db.Boolean, default=False)

    # API rate limits (requests per minute)
    api_rate_limit = db.Column(db.Integer, default=60)
    api_burst_limit = db.Column(db.Integer, default=100)
```

#### `AccountSubscription` - Links accounts to plans

```python
class AccountSubscription(db.Model):
    """Account subscription to a plan."""
    __tablename__ = 'account_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    status = db.Column(db.String(20), default='active')  # 'active', 'cancelled', 'past_due', 'trialing'
    billing_cycle = db.Column(db.String(20), default='monthly')  # 'monthly', 'annual'

    # Billing
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    # External billing (Stripe, etc.)
    external_subscription_id = db.Column(db.String(255), nullable=True)  # Stripe subscription ID
    external_customer_id = db.Column(db.String(255), nullable=True)      # Stripe customer ID

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### `Account` - Top-level billing entity (owns tenants)

```python
class Account(db.Model):
    """Billing account that owns one or more tenants."""
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    billing_email = db.Column(db.String(255), nullable=False)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Usage tracking
    storage_used_bytes = db.Column(db.BigInteger, default=0)

    # Data residency
    data_region = db.Column(db.String(20), default='eu')  # 'eu', 'us', 'apac'

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenants = db.relationship('Tenant', backref='account', lazy='dynamic')
    subscriptions = db.relationship('AccountSubscription', backref='account', lazy='dynamic')
```

#### `UsageRecord` - Track usage for billing

```python
class UsageRecord(db.Model):
    """Track usage metrics for billing and limits."""
    __tablename__ = 'usage_records'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    metric = db.Column(db.String(50), nullable=False)  # 'api_calls', 'storage', 'users', 'tenants'
    value = db.Column(db.BigInteger, nullable=False)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

#### `IPAllowlist` - IP restrictions for Enterprise

```python
class IPAllowlist(db.Model):
    """IP allowlist for Enterprise accounts."""
    __tablename__ = 'ip_allowlists'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    ip_range = db.Column(db.String(50), nullable=False)  # CIDR notation: "192.168.1.0/24"
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### 2.2 Modified Models

#### `Tenant` - Add account relationship

```python
# Add to Tenant model:
account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)  # Nullable for migration
```

#### `AuditLog` - Add immutability flag and retention

```python
# Add to AuditLog model:
is_immutable = db.Column(db.Boolean, default=False)  # For regulated industries
retention_expires_at = db.Column(db.DateTime, nullable=True)  # When log can be purged
```

---

## 3. Deployment Mode Separation

### 3.1 Environment Configuration

```python
# config.py
class DeploymentMode(enum.Enum):
    SELF_HOSTED = 'self_hosted'   # Apache 2.0, no limits
    CLOUD = 'cloud'               # SaaS with tiers

# Environment variable
DEPLOYMENT_MODE = os.environ.get('DEPLOYMENT_MODE', 'self_hosted')
```

### 3.2 Feature Toggle System

```python
class FeatureFlags:
    """Feature flags based on deployment mode and subscription."""

    @staticmethod
    def is_cloud_mode():
        return os.environ.get('DEPLOYMENT_MODE') == 'cloud'

    @staticmethod
    def enforce_limits():
        """Only enforce limits in cloud mode."""
        return FeatureFlags.is_cloud_mode()

    @staticmethod
    def get_effective_limits(account_or_tenant):
        """Get limits for an account/tenant based on subscription."""
        if not FeatureFlags.enforce_limits():
            return {
                'max_users': None,  # Unlimited
                'max_tenants': None,
                'max_storage_bytes': None,
                'audit_retention_days': None,
            }
        # Get from subscription plan
        subscription = account_or_tenant.get_active_subscription()
        if subscription:
            plan = subscription.plan
            return {
                'max_users': plan.max_users,
                'max_tenants': plan.max_tenants,
                'max_storage_bytes': plan.max_storage_bytes,
                'audit_retention_days': plan.audit_retention_days,
            }
        # Default to free tier
        return FREE_TIER_LIMITS
```

### 3.3 Code Segregation Strategy

```
├── core/                    # Shared between self-hosted & cloud (Apache 2.0)
│   ├── models/
│   ├── api/
│   └── services/
├── cloud/                   # Cloud-only features (proprietary license)
│   ├── billing/
│   ├── limits/
│   ├── scim/
│   └── compliance/
├── app.py                   # Main app, conditionally imports cloud modules
└── LICENSE                  # Apache 2.0 for core
```

---

## 4. API Changes

### 4.1 New Endpoints

#### Subscription Management
```
GET  /api/account/subscription          # Get current subscription
POST /api/account/subscription/upgrade  # Upgrade plan
POST /api/account/subscription/cancel   # Cancel subscription
GET  /api/account/usage                 # Get usage metrics
GET  /api/account/invoices              # Get invoice history
```

#### Account Management
```
GET  /api/account                       # Get account details
PUT  /api/account                       # Update account
GET  /api/account/limits                # Get effective limits
```

#### IP Allowlist (Enterprise)
```
GET    /api/account/ip-allowlist        # List allowed IPs
POST   /api/account/ip-allowlist        # Add IP range
DELETE /api/account/ip-allowlist/:id    # Remove IP range
```

#### SCIM (Enterprise)
```
POST   /scim/v2/Users                   # Provision user
GET    /scim/v2/Users/:id               # Get user
PUT    /scim/v2/Users/:id               # Update user
DELETE /scim/v2/Users/:id               # Deprovision user
GET    /scim/v2/Groups                  # List groups
```

### 4.2 Modified Endpoints

All existing endpoints need middleware to:
1. Check plan limits before allowing operations
2. Track API usage for rate limiting
3. Enforce IP allowlist (if enabled)

```python
@app.before_request
def check_plan_limits():
    if not FeatureFlags.enforce_limits():
        return  # Self-hosted, no limits

    # Check user count limit
    # Check tenant count limit
    # Check storage limit
    # Check API rate limit
```

---

## 5. Database Migration Plan

### Phase 1: Add new tables (backward compatible)
```sql
-- Migration: Add plans table
CREATE TABLE plans (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    ...
);

-- Seed default plans
INSERT INTO plans (code, name, max_users, max_tenants, ...) VALUES
    ('free', 'Cloud Free', 5, 3, ...),
    ('team', 'Team', 50, NULL, ...),
    ('enterprise', 'Enterprise', NULL, NULL, ...),
    ('regulated', 'Regulated Add-On', NULL, NULL, ...);

-- Migration: Add accounts table
CREATE TABLE accounts (...);

-- Migration: Add account_subscriptions table
CREATE TABLE account_subscriptions (...);
```

### Phase 2: Link existing data
```sql
-- Create default account for each existing tenant
INSERT INTO accounts (name, billing_email, ...)
SELECT domain, (SELECT email FROM users WHERE sso_domain = t.domain LIMIT 1), ...
FROM tenants t;

-- Link tenants to accounts
UPDATE tenants SET account_id = ...;
```

### Phase 3: Add limit enforcement (cloud only)
```sql
-- Add account_id FK to tenants (with default)
ALTER TABLE tenants ADD COLUMN account_id INTEGER REFERENCES accounts(id);
```

---

## 6. Audit Log Retention Implementation

### 6.1 Retention Policy

```python
class AuditLogRetention:
    """Manage audit log retention based on plan."""

    @staticmethod
    def get_retention_days(account):
        """Get retention days for account's plan."""
        if not FeatureFlags.enforce_limits():
            return None  # Unlimited in self-hosted

        subscription = account.get_active_subscription()
        if subscription:
            return subscription.plan.audit_retention_days
        return 30  # Free tier default

    @staticmethod
    def schedule_retention(audit_log, account):
        """Set retention expiry when creating audit log."""
        retention_days = AuditLogRetention.get_retention_days(account)
        if retention_days:
            audit_log.retention_expires_at = datetime.utcnow() + timedelta(days=retention_days)

    @staticmethod
    def purge_expired_logs():
        """Background job to purge expired audit logs."""
        if not FeatureFlags.enforce_limits():
            return  # Never purge in self-hosted

        AuditLog.query.filter(
            AuditLog.retention_expires_at < datetime.utcnow(),
            AuditLog.is_immutable == False  # Never purge immutable logs
        ).delete()
```

### 6.2 Immutable Logs (Regulated Industries)

```python
def create_immutable_audit_log(tenant_id, actor_user_id, action_type, ...):
    """Create an immutable audit log for regulated industries."""
    log = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action_type=action_type,
        is_immutable=True,
        retention_expires_at=None,  # Never expires
        ...
    )
    db.session.add(log)
    return log
```

---

## 7. Testing Requirements

### 7.1 Unit Tests

```
tests/test_plans.py
├── test_plan_creation
├── test_plan_limits
├── test_plan_feature_flags
└── test_plan_pricing

tests/test_subscriptions.py
├── test_subscription_create
├── test_subscription_upgrade
├── test_subscription_downgrade
├── test_subscription_cancel
├── test_subscription_renewal
└── test_subscription_past_due

tests/test_limits.py
├── test_user_limit_enforcement
├── test_tenant_limit_enforcement
├── test_storage_limit_enforcement
├── test_api_rate_limiting
├── test_limits_self_hosted_disabled
└── test_limits_cloud_enabled

tests/test_audit_retention.py
├── test_retention_free_tier_30_days
├── test_retention_team_1_year
├── test_retention_enterprise_10_years
├── test_retention_immutable_never_purged
├── test_retention_self_hosted_unlimited
└── test_purge_expired_logs
```

### 7.2 Integration Tests

```
tests/integration/test_billing_flow.py
├── test_free_tier_signup
├── test_upgrade_to_team
├── test_upgrade_to_enterprise
├── test_downgrade_with_overages
├── test_cancel_subscription
└── test_reactivate_subscription

tests/integration/test_limit_enforcement.py
├── test_exceed_user_limit_blocked
├── test_exceed_tenant_limit_blocked
├── test_exceed_storage_limit_blocked
├── test_api_rate_limit_429
└── test_ip_allowlist_enforcement
```

### 7.3 E2E Tests

```
e2e/tests/pricing.spec.ts
├── test_pricing_page_display
├── test_free_tier_registration
├── test_upgrade_flow
├── test_billing_portal_access
└── test_usage_dashboard
```

---

## 8. Frontend Changes

### 8.1 New Components

```
frontend/src/app/components/
├── pricing/
│   ├── pricing-page.component.ts       # Public pricing page
│   └── plan-card.component.ts          # Individual plan display
├── billing/
│   ├── billing-dashboard.component.ts  # Account billing overview
│   ├── subscription-card.component.ts  # Current subscription
│   ├── usage-chart.component.ts        # Usage visualization
│   └── invoice-list.component.ts       # Invoice history
└── limits/
    └── limit-warning.component.ts      # Warning when approaching limits
```

### 8.2 New Services

```
frontend/src/app/services/
├── billing.service.ts                  # Subscription management
├── usage.service.ts                    # Usage tracking
└── limits.service.ts                   # Limit checking
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Add `Plan` model with seeded plans
- [ ] Add `Account` model
- [ ] Add `AccountSubscription` model
- [ ] Add `DEPLOYMENT_MODE` environment variable
- [ ] Create feature flag system
- [ ] Write unit tests for new models

### Phase 2: Limit Enforcement (Week 3-4)
- [ ] Add limit checking middleware
- [ ] Implement user count limits
- [ ] Implement tenant count limits
- [ ] Implement storage tracking
- [ ] Implement API rate limiting
- [ ] Write limit enforcement tests

### Phase 3: Audit Retention (Week 5)
- [ ] Add retention fields to AuditLog
- [ ] Implement retention scheduling
- [ ] Create background purge job
- [ ] Implement immutable logs
- [ ] Write retention tests

### Phase 4: Billing Integration (Week 6-7)
- [ ] Integrate Stripe (or alternative)
- [ ] Implement subscription lifecycle
- [ ] Create billing webhooks
- [ ] Build billing dashboard
- [ ] Write billing integration tests

### Phase 5: Enterprise Features (Week 8-9)
- [ ] Implement IP allowlisting
- [ ] Implement SCIM provisioning (basic)
- [ ] Add data residency controls
- [ ] Write enterprise feature tests

### Phase 6: Frontend & Polish (Week 10-11)
- [ ] Build pricing page
- [ ] Build billing dashboard
- [ ] Add limit warnings
- [ ] Update admin UI
- [ ] E2E tests

### Phase 7: Documentation & Launch (Week 12)
- [ ] Update API documentation
- [ ] Write upgrade guides
- [ ] Prepare self-hosted release notes
- [ ] Deploy to production

---

## 10. Open Questions

1. **Billing Provider**: Stripe vs Paddle vs alternative?
2. **Free Tier Overages**: Grace period or hard block?
3. **Annual Billing Discount**: What percentage?
4. **Enterprise Custom Pricing**: How to handle?
5. **Regulated Add-On**: Separate plan or feature flag on Enterprise?
6. **Migration**: How to handle existing cloud users?
7. **Self-hosted Telemetry**: Optional usage reporting?

---

## 11. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing users | Medium | High | Careful migration, backward compatibility |
| Complex billing edge cases | High | Medium | Comprehensive testing, manual override capability |
| Feature creep | Medium | Medium | Strict phase gates, MVP focus |
| Self-hosted feature parity complaints | Medium | Low | Clear documentation of what's included |
| Rate limiting false positives | Medium | Medium | Generous defaults, monitoring, manual override |

---

## 12. Success Metrics

1. **Technical**:
   - Zero breaking changes for existing users
   - All tests passing (>95% coverage on new code)
   - API response time unchanged (<100ms p95)

2. **Business**:
   - Pricing page live
   - Billing integration working
   - First paid subscription processed
