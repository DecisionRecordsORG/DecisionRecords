# Plan 1.5: Governance & Data Model Redesign

This document tracks the implementation of tiered admin permissions, Spaces, and the underlying data model changes required to support them safely.

**Author**: Lead Engineer
**Last Updated**: December 11, 2025
**Status**: Feature Complete (Pending Migration)

---

## Implementation Status (December 11, 2025)

### ✅ Phase 0: Data Model Foundation - COMPLETE
| Item | Status | Notes |
|------|--------|-------|
| 0.1 Create Tenant Table | ✅ Done | `models.py` - Tenant with maturity_state |
| 0.2 Create TenantMembership | ✅ Done | `models.py` - GlobalRole enum (USER, PROVISIONAL_ADMIN, STEWARD, ADMIN) |
| 0.3 Modify User Table | ✅ Done | Added `memberships` relationship, kept `sso_domain`/`is_admin` for compatibility |
| 0.4 Create TenantSettings | ⏸️ Deferred | Using AuthConfig directly for now |
| 0.5 Create Space & DecisionSpace | ✅ Done | `models.py` - Space, DecisionSpace with VisibilityPolicy |
| 0.6 Modify ArchitectureDecision | ⏸️ Partial | Added `tenant_id` FK, kept `domain` for compatibility |
| 0.7 Create AuditLog | ✅ Done | `models.py` - Full audit logging |
| 0.8 Migration Script | ❌ Not Done | Need to run for existing data |
| 0.9 RoleRequest Model | ✅ Done | `models.py` - Role elevation requests with audit |

### ✅ Phase 1: Permission Enforcement - COMPLETE
| Item | Status | Notes |
|------|--------|-------|
| 1.1 High-impact settings guard | ✅ Done | `governance.py` - `can_modify_high_impact_setting()` |
| 1.2 Provisional admin restrictions | ✅ Done | `governance.py` - HIGH_IMPACT_SETTINGS dict |
| 1.3 Automatic role upgrade | ✅ Done | `governance.py` - `check_and_upgrade_provisional_admin()` |
| Unit tests | ✅ Done | `tests/test_governance.py` - 23 tests passing |

### ✅ Phase 2: Space Implementation - COMPLETE
| Item | Status | Notes |
|------|--------|-------|
| 2.1 Space invariants | ✅ Done | Model constraints in `models.py` |
| 2.2 Space API endpoints | ✅ Done | `app.py` - 8 endpoints (CRUD + decision linking) |
| Unit tests | ✅ Done | `tests/test_spaces.py` - 15 tests passing |

### ✅ Phase 3: Frontend Changes - COMPLETE
| Item | Status | Notes |
|------|--------|-------|
| Role badges in user list | ✅ Done | `settings.component.ts` - replaces admin toggle |
| Provisional admin banner | ✅ Done | Updated to exact microcopy from requirements |
| Restricted setting tooltips | ✅ Done | Updated to exact microcopy from requirements |
| Space filter in decision list | ✅ Done | `decision-list.component.ts` - dropdown when multiple spaces |
| Space selector in decision form | ✅ Done | `decision-detail.component.ts` - multi-select for spaces |
| Spaces management in settings | ✅ Done | `settings.component.ts` - full CRUD for spaces |
| Space service | ✅ Done | `space.service.ts` |
| Role helper | ✅ Done | `role.helper.ts` |
| SSO tab explainer | ✅ Done | Security & privacy benefits info card |
| Email tab explainer | ✅ Done | Use cases & privacy benefits info card |

### ✅ Phase 4: Role Request Feature - COMPLETE
| Item | Status | Notes |
|------|--------|-------|
| Role request API | ✅ Done | `app.py` - POST/GET/approve/reject endpoints |
| Role request dialog | ✅ Done | `role-request-dialog.component.ts` - steward/admin selection |
| Request from profile | ✅ Done | `profile.component.ts` - users can request elevated role |
| Admin review in settings | ✅ Done | `settings.component.ts` - Role Requests tab |
| Audit logging | ✅ Done | All role requests/approvals logged |

### ✅ Phase 5: Super Admin Features - COMPLETE
| Item | Status | Notes |
|------|--------|-------|
| Tenant maturity threshold config | ✅ Done | `app.py` - PUT /api/tenants/<domain>/maturity |
| Tenant status overview | ✅ Done | Tenant list shows maturity_state, steward_count, age_days |
| Force maturity upgrade | ✅ Done | `app.py` - POST /api/tenants/<domain>/maturity/force-upgrade |
| Tenant deletion | ✅ Done | `app.py` - DELETE /api/tenants/<domain> with confirmation |
| Tenant details dialog | ✅ Done | `superadmin-tenants.component.ts` - full stats and actions |
| Delete confirmation dialog | ✅ Done | Requires typing domain name to confirm |
| E2E tests | ✅ Done | `e2e/tests/superadmin.spec.ts` - comprehensive test suite |

### Outstanding Work Summary
1. **Migration script** - Run to populate existing data into new tables
2. **Production deployment** - Deploy v1.5.0+ to production

---

## Executive Summary

The current data model has fundamental limitations:
1. **No explicit Tenant entity** - `domain` strings everywhere with no referential integrity
2. **Role tied to User** - Can't support multi-tenant users or proper role hierarchy
3. **No organizational structure** - Decisions are flat within a tenant
4. **Boolean admin** - No nuance between provisional/steward/admin roles

The new model introduces:
- **Tenant** as a first-class entity
- **TenantMembership** with role (decoupled from User)
- **Space** for organizational views (not containers)
- **Maturity states** that control permissions

---

## Current vs Target Data Model

### Current Model (Problems Highlighted)

```
User
├── sso_domain: String ← No FK, just a string
├── is_admin: Boolean  ← Binary, no role hierarchy
└── Can only belong to one "tenant" (by convention)

AuthConfig
├── domain: String (unique) ← Acts as tenant, but isn't
├── allow_registration, require_approval
└── No relationship to User table

ArchitectureDecision
├── domain: String ← No FK, no integrity
└── No organizational structure within tenant
```

**Issues:**
- `domain` appears in 5+ tables as a string with no FK constraints
- If someone changes AuthConfig.domain, all decisions become orphaned
- `is_admin` is boolean - first user gets it, but has full power
- No way to track tenant age or maturity
- No audit trail for admin actions

### Target Model

```
┌─────────────────────────────────────────────────────────────────┐
│                          TENANT                                  │
│  id | domain (unique) | name | maturity_state | created_at      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ TenantMembership│   │     Space       │   │    Decision     │
│ user_id (FK)    │   │ tenant_id (FK)  │   │ tenant_id (FK)  │
│ tenant_id (FK)  │   │ is_default      │   │ number, title   │
│ global_role     │   │ name            │   │ created_by      │
│ joined_at       │   └────────┬────────┘   └────────┬────────┘
└─────────────────┘            │                     │
         │                     │                     │
         ▼                     └──────────┬──────────┘
┌─────────────────┐                       ▼
│      User       │              ┌─────────────────┐
│ id | email      │              │  DecisionSpace  │
│ name | domain   │              │ decision_id     │
│ (from email)    │              │ space_id        │
└─────────────────┘              └─────────────────┘
```

---

## Phase 0: Data Model Foundation (MUST DO FIRST)

This phase restructures the database. Everything else depends on it.

### 0.1 Create Tenant Table

```python
class MaturityState(enum.Enum):
    BOOTSTRAP = 'bootstrap'      # Single admin, limited powers
    MATURE = 'mature'            # Full admin capabilities (multi-admin or thresholds met)

class Tenant(db.Model):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False, unique=True, index=True)
    name = db.Column(db.String(255), nullable=True)  # Display name
    status = db.Column(db.String(20), default='active')  # active, suspended
    maturity_state = db.Column(db.Enum(MaturityState), default=MaturityState.BOOTSTRAP)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Maturity thresholds (can be overridden by super admin)
    maturity_age_days = db.Column(db.Integer, default=14)
    maturity_user_threshold = db.Column(db.Integer, default=5)
    maturity_admin_threshold = db.Column(db.Integer, default=2)

    # Relationships
    memberships = db.relationship('TenantMembership', back_populates='tenant', cascade='all, delete-orphan')
    spaces = db.relationship('Space', back_populates='tenant', cascade='all, delete-orphan')
    decisions = db.relationship('ArchitectureDecision', back_populates='tenant')
    settings = db.relationship('TenantSettings', back_populates='tenant', uselist=False)

    def compute_maturity_state(self):
        """Derive maturity state from current conditions."""
        admin_count = TenantMembership.query.filter_by(
            tenant_id=self.id,
            global_role=GlobalRole.ADMIN
        ).count()
        steward_count = TenantMembership.query.filter_by(
            tenant_id=self.id,
            global_role=GlobalRole.STEWARD
        ).count()
        total_members = TenantMembership.query.filter_by(tenant_id=self.id).count()

        # Exit conditions for MATURE state (any one triggers maturity)
        has_multi_admin = admin_count >= 2 or (admin_count >= 1 and steward_count >= 1)
        has_enough_users = total_members >= self.maturity_user_threshold
        is_old_enough = (datetime.utcnow() - self.created_at).days >= self.maturity_age_days

        if has_multi_admin or has_enough_users or is_old_enough:
            return MaturityState.MATURE
        else:
            return MaturityState.BOOTSTRAP

    def update_maturity(self):
        """Update maturity state if conditions have changed."""
        new_state = self.compute_maturity_state()
        if new_state != self.maturity_state:
            old_state = self.maturity_state
            self.maturity_state = new_state
            db.session.commit()
            # TODO: Log state transition
            return True
        return False
```

### 0.2 Create TenantMembership (Role on Membership)

```python
class GlobalRole(enum.Enum):
    USER = 'user'
    PROVISIONAL_ADMIN = 'provisional_admin'
    STEWARD = 'steward'
    ADMIN = 'admin'

class TenantMembership(db.Model):
    __tablename__ = 'tenant_memberships'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    global_role = db.Column(db.Enum(GlobalRole), default=GlobalRole.USER)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='memberships')
    tenant = db.relationship('Tenant', back_populates='memberships')

    # Constraints
    __table_args__ = (
        db.UniqueConstraint('user_id', 'tenant_id', name='unique_user_tenant'),
    )

    @property
    def is_admin(self):
        """Backward compatibility - any admin-level role."""
        return self.global_role in [
            GlobalRole.PROVISIONAL_ADMIN,
            GlobalRole.STEWARD,
            GlobalRole.ADMIN
        ]

    @property
    def is_full_admin(self):
        """Only full admin, not provisional."""
        return self.global_role == GlobalRole.ADMIN

    @property
    def can_change_tenant_settings(self):
        """Can modify tenant configuration."""
        return self.global_role == GlobalRole.ADMIN

    @property
    def can_approve_requests(self):
        """Can approve/reject access requests."""
        return self.global_role in [GlobalRole.PROVISIONAL_ADMIN, GlobalRole.STEWARD, GlobalRole.ADMIN]
```

### 0.3 Modify User Table

```python
class User(db.Model):
    # REMOVE: sso_domain (derived from email or membership)
    # REMOVE: is_admin (moved to TenantMembership)

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=True)
    # ... auth fields remain ...

    # Relationships
    memberships = db.relationship('TenantMembership', back_populates='user')

    @property
    def domain(self):
        """Extract domain from email."""
        return self.email.split('@')[1].lower() if '@' in self.email else None

    def get_membership(self, tenant_id=None, domain=None):
        """Get membership for a specific tenant."""
        if tenant_id:
            return TenantMembership.query.filter_by(
                user_id=self.id, tenant_id=tenant_id
            ).first()
        elif domain:
            tenant = Tenant.query.filter_by(domain=domain).first()
            if tenant:
                return TenantMembership.query.filter_by(
                    user_id=self.id, tenant_id=tenant.id
                ).first()
        return None

    def is_admin_of(self, tenant_id):
        """Check if user is admin of specific tenant."""
        membership = self.get_membership(tenant_id=tenant_id)
        return membership and membership.is_admin
```

### 0.4 Create TenantSettings (Replaces AuthConfig)

```python
class TenantSettings(db.Model):
    """Tenant-specific settings. One-to-one with Tenant."""
    __tablename__ = 'tenant_settings'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, unique=True)

    # Auth settings
    auth_method = db.Column(db.String(20), default='local')
    allow_password = db.Column(db.Boolean, default=True)
    allow_passkey = db.Column(db.Boolean, default=True)
    rp_name = db.Column(db.String(255), default='Architecture Decisions')

    # Registration settings
    allow_registration = db.Column(db.Boolean, default=True)
    require_approval = db.Column(db.Boolean, default=False)

    # Display settings
    tenant_prefix = db.Column(db.String(3), unique=True, nullable=True)

    # Relationships
    tenant = db.relationship('Tenant', back_populates='settings')

    # NOTE: No 'delete tenant' setting - that's Super Admin only
```

### 0.5 Create Space & DecisionSpace

```python
class VisibilityPolicy(enum.Enum):
    TENANT_VISIBLE = 'tenant_visible'  # All tenant members see decisions
    SPACE_FOCUSED = 'space_focused'    # Default view scoped to space

class Space(db.Model):
    __tablename__ = 'spaces'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_default = db.Column(db.Boolean, default=False)
    visibility_policy = db.Column(db.Enum(VisibilityPolicy), default=VisibilityPolicy.TENANT_VISIBLE)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', back_populates='spaces')
    created_by = db.relationship('User')
    decision_links = db.relationship('DecisionSpace', back_populates='space', cascade='all, delete-orphan')

    # Constraint: Only one default space per tenant
    __table_args__ = (
        db.Index('idx_tenant_default', 'tenant_id', 'is_default',
                 postgresql_where=db.text('is_default = true'),
                 unique=True),
    )

class DecisionSpace(db.Model):
    """Links decisions to spaces (many-to-many)."""
    __tablename__ = 'decision_spaces'

    id = db.Column(db.Integer, primary_key=True)
    decision_id = db.Column(db.Integer, db.ForeignKey('architecture_decisions.id'), nullable=False)
    space_id = db.Column(db.Integer, db.ForeignKey('spaces.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    added_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    decision = db.relationship('ArchitectureDecision', back_populates='space_links')
    space = db.relationship('Space', back_populates='decision_links')

    __table_args__ = (
        db.UniqueConstraint('decision_id', 'space_id', name='unique_decision_space'),
    )
```

### 0.6 Modify ArchitectureDecision

```python
class ArchitectureDecision(db.Model):
    # CHANGE: domain → tenant_id
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Keep domain temporarily for migration, then remove
    # domain = db.Column(db.String(255), nullable=True)  # DEPRECATED

    # Relationships
    tenant = db.relationship('Tenant', back_populates='decisions')
    space_links = db.relationship('DecisionSpace', back_populates='decision', cascade='all, delete-orphan')

    @property
    def spaces(self):
        """Get all spaces this decision belongs to."""
        return [link.space for link in self.space_links]
```

### 0.7 Create AuditLog

```python
class AuditLog(db.Model):
    """Immutable audit log for admin/steward actions."""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)  # e.g., 'promote_user', 'change_setting'
    target_entity = db.Column(db.String(50), nullable=True)  # e.g., 'user', 'tenant_settings'
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.JSON, nullable=True)  # Additional context
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships (read-only, no cascading deletes)
    tenant = db.relationship('Tenant')
    actor = db.relationship('User')

    # Action types
    ACTION_PROMOTE_USER = 'promote_user'
    ACTION_DEMOTE_USER = 'demote_user'
    ACTION_CHANGE_SETTING = 'change_setting'
    ACTION_APPROVE_REQUEST = 'approve_request'
    ACTION_REJECT_REQUEST = 'reject_request'
    ACTION_CREATE_SPACE = 'create_space'
    ACTION_DELETE_SPACE = 'delete_space'
    ACTION_MATURITY_CHANGE = 'maturity_change'
```

---

## Phase 0.8: Migration Script

**CRITICAL**: This migration must preserve all existing data.

```python
def migrate_to_v15():
    """
    Migration from v1.4 to v1.5 data model.

    Steps:
    1. Create new tables (Tenant, TenantMembership, Space, etc.)
    2. Populate Tenant from distinct User.sso_domain values
    3. Populate TenantMembership from User.sso_domain + is_admin
    4. Populate TenantSettings from AuthConfig
    5. Create default Space per tenant
    6. Update Decision.tenant_id from Decision.domain
    7. Link all decisions to default space
    8. Verify data integrity
    9. Drop deprecated columns (in separate migration after verification)
    """

    # Step 1: Create tables
    db.create_all()

    # Step 2: Create Tenants from distinct domains
    domains = db.session.query(User.sso_domain).distinct().all()
    for (domain,) in domains:
        if domain:
            tenant = Tenant(
                domain=domain,
                name=domain,  # Can be updated later
                maturity_state=MaturityState.BOOTSTRAP,
                created_at=datetime.utcnow()  # Or find earliest user
            )
            db.session.add(tenant)
    db.session.flush()

    # Step 3: Create TenantMemberships
    users = User.query.all()
    for user in users:
        tenant = Tenant.query.filter_by(domain=user.sso_domain).first()
        if tenant:
            role = GlobalRole.PROVISIONAL_ADMIN if user.is_admin else GlobalRole.USER
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=role,
                joined_at=user.created_at
            )
            db.session.add(membership)
    db.session.flush()

    # Step 4: Migrate AuthConfig to TenantSettings
    auth_configs = AuthConfig.query.all()
    for config in auth_configs:
        tenant = Tenant.query.filter_by(domain=config.domain).first()
        if tenant:
            settings = TenantSettings(
                tenant_id=tenant.id,
                auth_method=config.auth_method,
                allow_password=config.allow_password,
                allow_passkey=config.allow_passkey,
                allow_registration=config.allow_registration,
                require_approval=config.require_approval,
                rp_name=config.rp_name,
                tenant_prefix=config.tenant_prefix
            )
            db.session.add(settings)
    db.session.flush()

    # Step 5: Create default Space per tenant
    tenants = Tenant.query.all()
    for tenant in tenants:
        space = Space(
            tenant_id=tenant.id,
            name='General',
            description='Default space for all decisions',
            is_default=True
        )
        db.session.add(space)
    db.session.flush()

    # Step 6: Update Decision.tenant_id
    decisions = ArchitectureDecision.query.all()
    for decision in decisions:
        tenant = Tenant.query.filter_by(domain=decision.domain).first()
        if tenant:
            decision.tenant_id = tenant.id
    db.session.flush()

    # Step 7: Link decisions to default space
    for tenant in tenants:
        default_space = Space.query.filter_by(tenant_id=tenant.id, is_default=True).first()
        if default_space:
            decisions = ArchitectureDecision.query.filter_by(tenant_id=tenant.id).all()
            for decision in decisions:
                link = DecisionSpace(decision_id=decision.id, space_id=default_space.id)
                db.session.add(link)
    db.session.flush()

    # Step 8: Update tenant maturity based on actual data
    for tenant in tenants:
        tenant.update_maturity()

    db.session.commit()

    # Step 9: Verification
    verify_migration()

def verify_migration():
    """Verify all data migrated correctly."""
    # Check no orphaned decisions
    orphaned = ArchitectureDecision.query.filter_by(tenant_id=None).count()
    assert orphaned == 0, f"{orphaned} decisions have no tenant"

    # Check all tenants have default space
    tenants = Tenant.query.all()
    for tenant in tenants:
        default = Space.query.filter_by(tenant_id=tenant.id, is_default=True).first()
        assert default, f"Tenant {tenant.domain} has no default space"

    # Check all users have membership for their domain
    users = User.query.all()
    for user in users:
        if user.sso_domain:  # Old field, still accessible during migration
            membership = TenantMembership.query.filter_by(user_id=user.id).first()
            assert membership, f"User {user.email} has no membership"
```

---

## Phase 1: Permission Enforcement

After Phase 0, implement the actual permission checks.

### 1.1 High-Impact Settings Guard

```python
def can_modify_high_impact_setting(tenant, user_membership):
    """
    Check if high-impact settings can be modified.

    High-impact settings:
    - Disable registration (allow_registration = false)
    - Enable approval-only (require_approval = true)

    Required conditions (any one):
    - Tenant is MATURE
    - 2+ ADMINs
    - 1 ADMIN + 1 STEWARD
    """
    if tenant.maturity_state == MaturityState.MATURE:
        return True, None

    admin_count = TenantMembership.query.filter_by(
        tenant_id=tenant.id,
        global_role=GlobalRole.ADMIN
    ).count()

    steward_count = TenantMembership.query.filter_by(
        tenant_id=tenant.id,
        global_role=GlobalRole.STEWARD
    ).count()

    if admin_count >= 2:
        return True, None

    if admin_count >= 1 and steward_count >= 1:
        return True, None

    # Not allowed - return helpful message
    return False, {
        'error': 'Cannot modify restrictive settings yet',
        'reason': 'Tenant governance requirements not met',
        'current_state': {
            'maturity': tenant.maturity_state.value,
            'admin_count': admin_count,
            'steward_count': steward_count,
        },
        'requirements': {
            'option_1': 'Wait for tenant to mature (age or user count)',
            'option_2': f'Add {2 - admin_count} more admin(s)',
            'option_3': 'Add a steward' if admin_count >= 1 and steward_count == 0 else None,
        }
    }
```

### 1.2 Provisional Admin Restrictions

```python
class SettingRestriction:
    """Define what settings are restricted for provisional admins."""

    PROVISIONAL_ADMIN_CANNOT = [
        ('allow_registration', False),   # Cannot disable
        ('require_approval', True),      # Cannot enable
    ]

    @staticmethod
    def is_restricted_change(setting_name, new_value, membership):
        """Check if a setting change is restricted for this user."""
        if membership.global_role != GlobalRole.PROVISIONAL_ADMIN:
            return False

        for (restricted_setting, restricted_value) in SettingRestriction.PROVISIONAL_ADMIN_CANNOT:
            if setting_name == restricted_setting and new_value == restricted_value:
                return True
        return False
```

### 1.3 Automatic Role Upgrade

```python
def check_and_upgrade_provisional_admin(tenant):
    """
    Upgrade provisional admin to full admin when exit conditions are met.

    Exit conditions:
    1. A second Admin or Steward is assigned
    2. Tenant becomes MATURE (age, user count, or multi-admin)
    """
    # Update tenant maturity first
    tenant.update_maturity()

    if tenant.maturity_state == MaturityState.BOOTSTRAP:
        return  # Still in bootstrap, no upgrades

    # Find provisional admins and upgrade them
    provisional = TenantMembership.query.filter_by(
        tenant_id=tenant.id,
        global_role=GlobalRole.PROVISIONAL_ADMIN
    ).all()

    for membership in provisional:
        membership.global_role = GlobalRole.ADMIN
        # Log the upgrade
        audit_log(
            tenant_id=tenant.id,
            actor_user_id=membership.user_id,  # System action, but attributed to user
            action_type=AuditLog.ACTION_MATURITY_CHANGE,
            details={
                'old_role': 'provisional_admin',
                'new_role': 'admin',
                'trigger': tenant.maturity_state.value
            }
        )

    if provisional:
        db.session.commit()
```

---

## Phase 2: Space Implementation

### 2.1 Space Invariants (CRITICAL)

These rules MUST be enforced:

1. **Every tenant has exactly one default space**
   - Created automatically when tenant is created
   - Cannot be deleted
   - `is_default = True` is unique per tenant

2. **Spaces organize, they don't isolate**
   - Admins and Stewards can see ALL decisions regardless of space
   - Space membership doesn't override tenant membership
   - Deleting a space removes links, not decisions

3. **Decisions always belong to tenant, optionally to spaces**
   - `Decision.tenant_id` is NOT NULL
   - `DecisionSpace` is optional (many-to-many)
   - A decision can be in zero spaces (shows in "Uncategorized")

### 2.2 Space Operations

```python
@app.route('/api/spaces', methods=['POST'])
@login_required
@require_admin_or_steward
def create_space():
    """Create a new space in the tenant."""
    # ... validation ...
    space = Space(
        tenant_id=g.current_tenant.id,
        name=data['name'],
        description=data.get('description'),
        is_default=False,  # Never create default via API
        created_by_id=g.current_user.id
    )
    db.session.add(space)
    audit_log(...)
    db.session.commit()
    return jsonify(space.to_dict())

@app.route('/api/spaces/<int:space_id>', methods=['DELETE'])
@login_required
@require_admin
def delete_space(space_id):
    """Delete a space (but not its decisions)."""
    space = Space.query.get_or_404(space_id)

    if space.is_default:
        return jsonify({'error': 'Cannot delete default space'}), 400

    # Remove links, not decisions
    DecisionSpace.query.filter_by(space_id=space.id).delete()
    db.session.delete(space)
    audit_log(...)
    db.session.commit()
    return jsonify({'message': 'Space deleted'})
```

---

## Phase 3: Frontend Changes

### 3.1 User Interface Updates

| Component | Change |
|-----------|--------|
| User list | Show role badge (Provisional Admin, Steward, Admin) |
| Admin settings | Disable restricted settings with explanation tooltip |
| Decision list | Add space filter dropdown |
| Decision form | Add space selector (multi-select) |
| Navigation | Add "Spaces" section |

### 3.2 Role Display Logic

```typescript
interface Membership {
  tenant_id: number;
  global_role: 'user' | 'provisional_admin' | 'steward' | 'admin';
  joined_at: string;
}

function getRoleBadge(role: string): { label: string; color: string; tooltip: string } {
  switch (role) {
    case 'provisional_admin':
      return {
        label: 'Admin',
        color: 'orange',
        tooltip: 'Provisional admin - some settings are restricted until another admin or steward is assigned'
      };
    case 'steward':
      return {
        label: 'Steward',
        color: 'blue',
        tooltip: 'Shared governance role - can approve requests and promote stewards'
      };
    case 'admin':
      return {
        label: 'Admin',
        color: 'green',
        tooltip: 'Full administrator'
      };
    default:
      return { label: 'User', color: 'gray', tooltip: 'Regular user' };
  }
}
```

---

## Security Considerations

### What NOT to Do

1. **No tenant self-deletion** - Removed from all admin UIs. Only Super Admin can delete tenants.

2. **No backdoor escalation** - Password recovery doesn't change role. Account recovery restores auth, not permissions.

3. **No bypass via direct API** - All permission checks happen server-side, not just UI.

4. **No single point of failure** - Provisional admin restrictions exist precisely to prevent one person from locking everyone out.

### Fallback Safety

| Scenario | Risk | Mitigation |
|----------|------|------------|
| Only admin leaves org | Tenant locked | Super Admin can reassign admin |
| Provisional admin enables require_approval before others join | New users can't join | Prevented by restriction |
| Admin disables registration | No new users | Requires 2 admins or maturity |
| Space deleted | Decisions lost | Decisions belong to tenant, not space |

---

## Implementation Order

```
Phase 0.1-0.7: Database schema changes
     │
     ▼
Phase 0.8: Migration script + verification
     │
     ▼
Phase 1.1: High-impact settings guard
     │
     ▼
Phase 1.2: Provisional admin restrictions
     │
     ▼
Phase 1.3: Automatic role upgrade
     │
     ▼
Phase 2.1-2.2: Space implementation
     │
     ▼
Phase 3: Frontend updates
```

---

## Testing Checklist

### Data Migration
- [ ] All existing users have TenantMembership records
- [ ] All existing decisions have tenant_id (not null)
- [ ] All tenants have default space
- [ ] Existing admins are PROVISIONAL_ADMIN (can be upgraded)
- [ ] No orphaned records

### Provisional Admin
- [ ] First user signup → PROVISIONAL_ADMIN
- [ ] Cannot disable registration
- [ ] Cannot enable require_approval
- [ ] Can invite users, approve requests
- [ ] Can promote to STEWARD (which triggers upgrade)

### Role Upgrade
- [ ] Adding second admin → all provisional become ADMIN
- [ ] Adding steward → all provisional become ADMIN
- [ ] Tenant age > 14 days → provisional become ADMIN
- [ ] Tenant users >= 5 → provisional become ADMIN

### Spaces
- [ ] Default space exists for all tenants
- [ ] Cannot delete default space
- [ ] Deleting space removes links, not decisions
- [ ] Admins see all decisions regardless of space

### Security
- [ ] Password recovery doesn't change role
- [ ] No tenant self-deletion option
- [ ] All permission checks are server-side

---

## Design Decisions (Confirmed)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Maturity states | **Two only**: BOOTSTRAP → MATURE | Simpler, ESTABLISHED added no value |
| Multi-tenant users | **Deferred** | Data model supports it, but not implementing for v1.5 |
| Space roles | **No space-specific roles** | Spaces use tenant roles only - keeps it simple |

---

*Last Updated: December 2025*

