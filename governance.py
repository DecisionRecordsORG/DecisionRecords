"""
v1.5 Governance Module

Implements tiered admin permissions, high-impact settings guards,
and automatic role upgrades.
"""
from models import (
    db, Tenant, TenantMembership, TenantSettings, AuditLog,
    MaturityState, GlobalRole
)


# =============================================================================
# High-Impact Settings Guard (Phase 1.1)
# =============================================================================

HIGH_IMPACT_SETTINGS = {
    'allow_registration': {
        'restricted_value': False,
        'description': 'Disable open registration'
    },
    'require_approval': {
        'restricted_value': True,
        'description': 'Enable approval-only access'
    }
}


def can_modify_high_impact_setting(tenant, user_membership, setting_name=None, new_value=None):
    """
    Check if high-impact settings can be modified.

    High-impact settings:
    - Disable registration (allow_registration = false)
    - Enable approval-only (require_approval = true)

    Required conditions (any one):
    - Tenant is MATURE
    - 2+ ADMINs
    - 1 ADMIN + 1 STEWARD

    Args:
        tenant: Tenant object
        user_membership: TenantMembership of the acting user
        setting_name: Optional - specific setting being changed
        new_value: Optional - new value for the setting

    Returns:
        tuple: (allowed: bool, error_info: dict or None)
    """
    # Check if user has permission to change settings at all (must check this first)
    if not user_membership.can_change_tenant_settings:
        return False, {
            'error': 'Permission denied',
            'reason': 'Only full administrators can change tenant settings',
            'user_role': user_membership.global_role.value
        }

    # If this is not a high-impact setting, allow it (no governance check needed)
    if setting_name and setting_name not in HIGH_IMPACT_SETTINGS:
        return True, None

    # If setting_name is provided, check if the new_value is the restricted value
    if setting_name and setting_name in HIGH_IMPACT_SETTINGS:
        restricted_value = HIGH_IMPACT_SETTINGS[setting_name]['restricted_value']
        if new_value != restricted_value:
            # Setting is high-impact but not being set to the restricted value
            return True, None

    # Mature tenants can modify any setting
    if tenant.maturity_state == MaturityState.MATURE:
        return True, None

    # Count admins and stewards
    admin_count = TenantMembership.query.filter_by(
        tenant_id=tenant.id,
        global_role=GlobalRole.ADMIN
    ).count()

    steward_count = TenantMembership.query.filter_by(
        tenant_id=tenant.id,
        global_role=GlobalRole.STEWARD
    ).count()

    # Check governance requirements
    if admin_count >= 2:
        return True, None

    if admin_count >= 1 and steward_count >= 1:
        return True, None

    # Not allowed - return helpful message
    requirements = ['Wait for tenant to mature (age or user count)']
    if admin_count < 2:
        requirements.append(f'Add {2 - admin_count} more admin(s)')
    if admin_count >= 1 and steward_count == 0:
        requirements.append('Add a steward')

    return False, {
        'error': 'Cannot modify restrictive settings yet',
        'reason': 'Tenant governance requirements not met',
        'current_state': {
            'maturity': tenant.maturity_state.value,
            'admin_count': admin_count,
            'steward_count': steward_count,
        },
        'requirements': requirements,
        'help': 'High-impact settings require multiple admins or tenant maturity to prevent accidental lockout.'
    }


# =============================================================================
# Provisional Admin Restrictions (Phase 1.2)
# =============================================================================

PROVISIONAL_ADMIN_RESTRICTIONS = [
    ('allow_registration', False, 'Cannot disable open registration'),
    ('require_approval', True, 'Cannot enable approval-only access'),
]


def is_restricted_for_provisional_admin(setting_name, new_value, membership):
    """
    Check if a setting change is restricted for provisional admins.

    Args:
        setting_name: Name of the setting
        new_value: New value being set
        membership: TenantMembership of the acting user

    Returns:
        tuple: (is_restricted: bool, reason: str or None)
    """
    if membership.global_role != GlobalRole.PROVISIONAL_ADMIN:
        return False, None

    for (restricted_setting, restricted_value, reason) in PROVISIONAL_ADMIN_RESTRICTIONS:
        if setting_name == restricted_setting and new_value == restricted_value:
            return True, reason

    return False, None


def get_provisional_admin_restrictions(membership):
    """
    Get list of restrictions that apply to a provisional admin.

    Returns:
        list: List of restriction descriptions, or empty list if not provisional
    """
    if membership.global_role != GlobalRole.PROVISIONAL_ADMIN:
        return []

    return [reason for (_, _, reason) in PROVISIONAL_ADMIN_RESTRICTIONS]


# =============================================================================
# Automatic Role Upgrade (Phase 1.3)
# =============================================================================

def check_and_upgrade_provisional_admins(tenant, trigger_user_id=None):
    """
    Upgrade provisional admins to full admins when exit conditions are met.

    Exit conditions:
    1. A second Admin or Steward is assigned
    2. Tenant becomes MATURE (age, user count, or multi-admin)

    Args:
        tenant: Tenant to check
        trigger_user_id: User ID that triggered this check (for audit logging)

    Returns:
        list: List of user IDs that were upgraded
    """
    # Update tenant maturity first
    maturity_changed = tenant.update_maturity()

    if tenant.maturity_state == MaturityState.BOOTSTRAP:
        return []  # Still in bootstrap, no upgrades

    # Find provisional admins and upgrade them
    provisional_memberships = TenantMembership.query.filter_by(
        tenant_id=tenant.id,
        global_role=GlobalRole.PROVISIONAL_ADMIN
    ).all()

    upgraded_users = []

    for membership in provisional_memberships:
        old_role = membership.global_role
        membership.global_role = GlobalRole.ADMIN
        upgraded_users.append(membership.user_id)

        # Log the upgrade
        audit_entry = AuditLog(
            tenant_id=tenant.id,
            actor_user_id=trigger_user_id or membership.user_id,
            action_type=AuditLog.ACTION_PROMOTE_USER,
            target_entity='user',
            target_id=membership.user_id,
            details={
                'old_role': old_role.value,
                'new_role': GlobalRole.ADMIN.value,
                'trigger': 'maturity_upgrade',
                'tenant_maturity': tenant.maturity_state.value
            }
        )
        db.session.add(audit_entry)

    if upgraded_users:
        db.session.commit()

    return upgraded_users


def should_trigger_maturity_check(action, **kwargs):
    """
    Determine if an action should trigger a maturity check.

    Actions that can trigger maturity:
    - User joins tenant (user count threshold)
    - User promoted to steward/admin (multi-admin condition)

    Args:
        action: String describing the action
        **kwargs: Additional context

    Returns:
        bool: True if maturity check should run
    """
    maturity_triggers = [
        'user_joined',
        'user_promoted',
        'steward_assigned',
        'admin_assigned',
    ]
    return action in maturity_triggers


# =============================================================================
# Role Management
# =============================================================================

def can_promote_to_role(promoter_membership, target_role):
    """
    Check if a user can promote others to a specific role.

    Rules:
    - Only Admin can promote to Admin
    - Admin, Steward, Provisional Admin can promote to Steward
    - Anyone with admin privileges can demote (with restrictions)

    Args:
        promoter_membership: TenantMembership of the user doing the promotion
        target_role: GlobalRole being promoted to

    Returns:
        tuple: (allowed: bool, reason: str or None)
    """
    promoter_role = promoter_membership.global_role

    if target_role == GlobalRole.ADMIN:
        if promoter_role == GlobalRole.ADMIN:
            return True, None
        return False, 'Only full administrators can promote to admin role'

    if target_role == GlobalRole.STEWARD:
        if promoter_role in [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN]:
            return True, None
        return False, 'Only administrators or stewards can promote to steward role'

    if target_role == GlobalRole.USER:
        # Demotion
        if promoter_membership.is_admin:
            return True, None
        return False, 'Only administrators can demote users'

    return False, 'Invalid target role'


def can_demote_user(demoter_membership, target_membership, tenant):
    """
    Check if a user can demote another user.

    Rules:
    - Steward cannot demote Admin
    - Admin cannot demote another Admin unless multi-admin conditions met
    - Cannot demote self if it would leave tenant without admin

    Args:
        demoter_membership: TenantMembership of the user doing the demotion
        target_membership: TenantMembership of the user being demoted
        tenant: Tenant object

    Returns:
        tuple: (allowed: bool, reason: str or None)
    """
    demoter_role = demoter_membership.global_role
    target_role = target_membership.global_role

    # Steward cannot demote admin
    if demoter_role == GlobalRole.STEWARD and target_role == GlobalRole.ADMIN:
        return False, 'Stewards cannot demote administrators'

    # Self-demotion check
    if demoter_membership.user_id == target_membership.user_id:
        # Check if this would leave tenant without admin
        admin_count = TenantMembership.query.filter(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.global_role.in_([GlobalRole.ADMIN, GlobalRole.PROVISIONAL_ADMIN])
        ).count()

        if admin_count <= 1:
            return False, 'Cannot demote yourself - tenant would have no administrator'

    # Admin demoting admin requires multi-admin
    if target_role == GlobalRole.ADMIN and demoter_role == GlobalRole.ADMIN:
        admin_count = TenantMembership.query.filter_by(
            tenant_id=tenant.id,
            global_role=GlobalRole.ADMIN
        ).count()

        if admin_count < 2:
            return False, 'Cannot demote another admin without multi-admin governance'

    return True, None


# =============================================================================
# Audit Logging Helpers
# =============================================================================

def log_admin_action(tenant_id, actor_user_id, action_type, target_entity=None,
                     target_id=None, details=None):
    """
    Create an audit log entry for an admin action.

    Args:
        tenant_id: ID of the tenant
        actor_user_id: ID of the user performing the action
        action_type: Type of action (use AuditLog.ACTION_* constants)
        target_entity: Type of entity affected (e.g., 'user', 'tenant_settings')
        target_id: ID of the affected entity
        details: Additional context as dict

    Returns:
        AuditLog: The created audit log entry
    """
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action_type=action_type,
        target_entity=target_entity,
        target_id=target_id,
        details=details
    )
    db.session.add(entry)
    return entry


def log_setting_change(tenant_id, actor_user_id, setting_name, old_value, new_value):
    """
    Log a tenant setting change.

    Args:
        tenant_id: ID of the tenant
        actor_user_id: ID of the user making the change
        setting_name: Name of the setting
        old_value: Previous value
        new_value: New value

    Returns:
        AuditLog: The created audit log entry
    """
    return log_admin_action(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action_type=AuditLog.ACTION_CHANGE_SETTING,
        target_entity='tenant_settings',
        target_id=tenant_id,
        details={
            'setting': setting_name,
            'old_value': old_value,
            'new_value': new_value
        }
    )
