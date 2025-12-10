1. Admin Permission Tiers

Tenant Roles

Regular User

Baseline role for all authenticated users.

Permissions
	•	Create and view architecture decisions
	•	Comment and collaborate on decisions
	•	View tenant members
	•	Request elevated roles (steward / admin)

Restrictions
	•	No access to tenant configuration
	•	No ability to manage users
	•	No ability to modify tenant-wide policies

⸻

Provisional Admin (Bootstrap Steward)

Automatically assigned to the first user from a new domain.

This role is intentionally limited and temporary.

Permissions
	•	Invite users from the same domain
	•	Promote users to Steward role
	•	View tenant configuration (read-only)
	•	Create, edit, and archive decision records
	•	See pending access requests

Restrictions
	•	❌ Cannot disable open registration
	•	❌ Cannot enable approval-only access
	•	❌ Cannot restrict visibility of content
	•	❌ Cannot delete tenant
	•	❌ Cannot demote/remove other admins
	•	❌ Cannot change domain ownership or tenant identity

Exit Conditions (automatic)
Provisional Admin status is lifted when any one of the following occurs:
	•	A second Admin or Steward is assigned
	•	Tenant age exceeds N days (e.g. 14 or 30)
	•	Tenant reaches N active users (e.g. 5)

At that point, role upgrades to Admin.

⸻

Steward

Shared governance role designed for continuity.

Permissions
	•	Invite users
	•	Approve or reject access requests (if approval mode is enabled)
	•	Promote users to Steward
	•	View tenant configuration
	•	See admin/steward audit logs
	•	Participate in admin decisions requiring multi-party approval

Restrictions
	•	❌ Cannot delete tenant
	•	❌ Cannot remove other Admins
	•	❌ Cannot unilaterally enable restrictive settings
	•	❌ Cannot transfer tenant ownership

Notes
	•	Steward is the recommended role for large or federated organisations.
	•	Multiple stewards are encouraged.

⸻

Admin

Full tenant administrator, with safeguards.

Permissions
	•	All Steward permissions
	•	Change tenant configuration
	•	Enable / disable registration modes
	•	Promote and demote users (except Super Admin)
	•	Assign additional Admins
	•	Configure tenant-wide defaults
	•	Manage integrations and exports

Restrictions
	•	❌ Cannot delete tenant without multi-admin approval
	•	❌ Cannot enable restrictive settings unless safeguards are met
	•	❌ Cannot bypass audit logging

⸻

Super Admin (Platform Operator)

Non-tenant role. Invisible by default.

Permissions
	•	Recover locked tenants
	•	Reassign admin roles in exceptional cases
	•	Resolve domain conflicts
	•	Enforce platform governance policies

Constraints
	•	No routine access to tenant content
	•	All actions logged and reviewable
	•	No ability to influence tenant decisions or content

⸻

High-Impact Settings Safeguards

The following actions require extra conditions:
	•	Disable open registration
	•	Enable approval-only access
	•	Restrict content visibility
	•	Delete tenant

Required conditions
	•	At least 2 Admins, OR
	•	1 Admin + 1 Steward approval, OR
	•	Tenant maturity thresholds met


Tenant Spaces
Entity Relationship Diagram (Text)
1. Core Entities

    User
    ----
    id (PK)
    email
    domain
    name
    status
    created_at
    last_login_at
    
    Tenant
    ------
    id (PK)
    domain (unique)
    name
    status
    created_at
    maturity_state

    TenantMembership
    ----------------
    id (PK)
    user_id (FK -> User.id)
    tenant_id (FK -> Tenant.id)
    global_role (USER | PROVISIONAL_ADMIN | STEWARD | ADMIN)
    joined_at
    
    Space
    -----
    id (PK)
    tenant_id (FK -> Tenant.id)
    name
    description
    is_default (boolean)
    visibility_policy (TENANT_VISIBLE | SPACE_FOCUSED)
    created_by_user_id (FK -> User.id)
    created_at
    
    Decision
    --------
    id (PK)
    tenant_id (FK -> Tenant.id)
    title
    status
    created_by_user_id (FK -> User.id)
    created_at
    updated_at
    
    DecisionSpace
    -------------
    id (PK)
    decision_id (FK -> Decision.id)
    space_id (FK -> Space.id)
    
    AuditLog
    --------
    id (PK)
    tenant_id (FK -> Tenant.id)
    actor_user_id (FK -> User.id)
    action_type
    target_entity
    target_id
    details
    created_at

2. Relationship Overview
User
 ├── belongs to ──< TenantMembership >── Tenant
 │                     │
 │                     └── defines global role
 │
 ├── belongs to ──< SpaceMembership >── Space
 │                     │
 │                     └── defines space role
 │
 └── creates ──< Decision
                      │
Tenant ───────────────┘
 │
 ├── contains ──< Space
 │
 └── contains ──< Decision >── linked to ──< DecisionSpace >── Space

3. Key Constraints & Invariants (Critical)

These are not optional. They encode your trust model.

These are not optional. They encode your trust model.

Tenant Constraints
	•	A Tenant is identified by a domain, not by a user.
	•	A Tenant always has at least one Space where is_default = true.
	•	No tenant is ever “owned” by a user.

⸻

Membership Constraints
	•	A User may belong to only one Tenant per domain.
	•	A User may belong to multiple Spaces within a Tenant.
	•	Space membership never overrides tenant membership.

⸻

Role Constraints
	•	PROVISIONAL_ADMIN is allowed only while Tenant.maturity_state = BOOTSTRAP.
	•	Restrictive tenant settings require:
	•	2 ADMINs, or
	•	1 ADMIN + 1 STEWARD, or
	•	Tenant.maturity_state = MATURE
	•	A STEWARD cannot demote an ADMIN.
	•	An ADMIN cannot demote another ADMIN unless multi-admin conditions are met.

⸻

Space Constraints
	•	A Space:
	•	cannot have independent registration rules
	•	cannot change tenant-wide settings
	•	cannot hide content from Admins or Stewards
	•	Space deletion:
	•	never deletes Decision
	•	removes only SpaceMembership and DecisionSpace links

⸻

Decision Constraints
	•	A Decision always belongs to exactly one Tenant.
	•	A Decision may belong to zero or more Spaces.
	•	Removing a Decision from a Space does not affect its existence or history.
	•	Visibility of a Decision:
	•	controlled by Tenant settings first
	•	optionally scoped by Space as a lens, not a container

⸻

Audit Constraints
	•	All admin and steward actions MUST generate AuditLog entries.
	•	AuditLog entries are immutable.
	•	Super-admin actions are logged but scoped to platform governance.

⸻

4. Maturity State (Derived Attribute)

Tenant.maturity_state can be derived from:
	•	tenant age
	•	number of members
	•	number of admins/stewards

Possible values:
BOOTSTRAP | ESTABLISHED | MATURE
Used for:
	•	unlocking admin powers
	•	enabling restrictive settings
	•	UI messaging

⸻

5. Why This ERD Is Trust-Safe
	•	No hidden ownership
	•	No silent isolation
	•	Spaces organise, they don’t divide
	•	All content belongs to the organisation
	•	Governance scales without central capture

This model will survive:
	•	staff turnover
	•	organisational politics
	•	institutional scrutiny
	•	future features