import { GlobalRole } from '../models/decision.model';

export interface RoleBadge {
  label: string;
  color: 'primary' | 'accent' | 'warn' | 'basic';
  cssClass: string;
  tooltip: string;
}

/**
 * Get display information for a user role
 */
export function getRoleBadge(role: GlobalRole | undefined): RoleBadge {
  switch (role) {
    case 'admin':
      return {
        label: 'Admin',
        color: 'primary',
        cssClass: 'role-admin',
        tooltip: 'Full administrator with all permissions'
      };
    case 'provisional_admin':
      return {
        label: 'Admin',
        color: 'warn',
        cssClass: 'role-provisional',
        tooltip: 'Provisional admin - some settings are restricted until another admin or steward is assigned'
      };
    case 'steward':
      return {
        label: 'Steward',
        color: 'accent',
        cssClass: 'role-steward',
        tooltip: 'Shared governance role - can approve requests and promote stewards'
      };
    case 'user':
    default:
      return {
        label: 'User',
        color: 'basic',
        cssClass: 'role-user',
        tooltip: 'Regular user'
      };
  }
}

/**
 * Check if a role has admin-level permissions
 */
export function isAdminRole(role: GlobalRole | undefined): boolean {
  return role === 'admin' || role === 'provisional_admin' || role === 'steward';
}

/**
 * Check if a role is a full admin (not provisional)
 */
export function isFullAdmin(role: GlobalRole | undefined): boolean {
  return role === 'admin';
}

/**
 * Check if a role can manage spaces
 */
export function canManageSpaces(role: GlobalRole | undefined): boolean {
  return role === 'admin' || role === 'steward' || role === 'provisional_admin';
}

/**
 * Check if a role can delete spaces
 */
export function canDeleteSpaces(role: GlobalRole | undefined): boolean {
  return role === 'admin';
}

/**
 * Get role priority for sorting (higher is more privileged)
 */
export function getRolePriority(role: GlobalRole | undefined): number {
  switch (role) {
    case 'admin': return 4;
    case 'provisional_admin': return 3;
    case 'steward': return 2;
    case 'user': return 1;
    default: return 0;
  }
}

/**
 * Get human-readable role name
 */
export function getRoleDisplayName(role: GlobalRole | undefined): string {
  switch (role) {
    case 'admin': return 'Administrator';
    case 'provisional_admin': return 'Provisional Administrator';
    case 'steward': return 'Steward';
    case 'user': return 'User';
    default: return 'Unknown';
  }
}
