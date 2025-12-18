// v1.5 Role types
export type GlobalRole = 'user' | 'provisional_admin' | 'steward' | 'admin';

export interface TenantMembership {
  id: number;
  user_id: number;
  tenant_id: number;
  global_role: GlobalRole;
  joined_at: string;
}

// v1.5 Tenant info (included in /api/user/me response)
export type MaturityState = 'bootstrap' | 'mature';

export interface TenantInfo {
  id: number;
  domain: string;
  name: string | null;
  maturity_state: MaturityState;
  admin_count: number;
  steward_count: number;
}

export interface User {
  id: number;
  email: string;
  name: string;
  sso_domain: string;
  auth_type: 'sso' | 'webauthn' | 'local' | 'oidc';
  is_admin: boolean;  // Legacy field - use membership.global_role for v1.5
  has_passkey: boolean;
  has_password: boolean;
  email_verified: boolean;
  has_seen_admin_onboarding: boolean;
  created_at: string;
  last_login: string;
  // v1.5 additions
  membership?: TenantMembership;
  global_role?: GlobalRole;  // Convenience field populated by backend
  tenant_info?: TenantInfo;  // Tenant status info for governance UI
}

export interface MasterAccount {
  id: number;
  username: string;
  name: string;
  created_at: string;
  last_login: string;
}

export interface ITInfrastructure {
  id: number;
  name: string;
  type: InfrastructureType;
  description: string | null;
  domain: string;
  created_at: string;
  updated_at: string;
  created_by: User | null;
}

export type InfrastructureType = 'application' | 'network' | 'database' | 'server' | 'service' | 'api' | 'storage' | 'cloud' | 'container' | 'other';

// v1.5 Space types
export type VisibilityPolicy = 'tenant_visible' | 'space_focused';

export interface Space {
  id: number;
  tenant_id: number;
  name: string;
  description: string | null;
  is_default: boolean;
  visibility_policy: VisibilityPolicy;
  created_by_id: number | null;
  created_at: string;
  decision_count?: number;  // Optional, included in GET /api/spaces/:id
}

export interface DecisionSpace {
  id: number;
  decision_id: number;
  space_id: number;
  added_at: string;
  added_by_id: number | null;
}

export interface Decision {
  id: number;
  display_id?: string;  // e.g., "GYH-034"
  decision_number?: number;
  title: string;
  context: string;
  decision: string;
  status: DecisionStatus;
  consequences: string;
  created_at: string;
  updated_at: string;
  domain?: string;
  created_by?: User;
  updated_by?: User;
  deleted_at?: string;
  deleted_by?: User;
  history?: DecisionHistory[];
  infrastructure?: ITInfrastructure[];
  // v1.5 additions
  tenant_id?: number;
  spaces?: Space[];
}

export interface DecisionHistory {
  id: number;
  decision_id: number;
  title: string;
  context: string;
  decision: string;
  status: DecisionStatus;
  consequences: string;
  changed_at: string;
  changed_by?: User;
  change_reason?: string;
}

export type DecisionStatus = 'proposed' | 'accepted' | 'deprecated' | 'superseded';

export interface SSOConfig {
  id: number;
  domain: string;
  provider_name: string;
  client_id: string;
  discovery_url: string;
  enabled: boolean;
  created_at: string;
}

export interface EmailConfig {
  id: number;
  domain: string;
  smtp_server: string;
  smtp_port: number;
  smtp_username: string;
  from_email: string;
  from_name: string;
  use_tls: boolean;
  enabled: boolean;
}

export interface Subscription {
  notify_on_create: boolean;
  notify_on_update: boolean;
  notify_on_status_change: boolean;
}

export interface ApiError {
  error: string;
}

export interface AuthConfig {
  domain: string;
  auth_method: 'sso' | 'webauthn' | 'slack_oidc' | string;
  allow_registration: boolean;
  require_approval: boolean;
  rp_name: string;
  tenant_prefix?: string;  // 3-letter prefix for decision IDs
  allow_password?: boolean;
  allow_passkey?: boolean;
  allow_slack_oidc?: boolean;  // Allow "Sign in with Slack" option
  allow_google_oauth?: boolean;  // Allow "Sign in with Google" option
  id?: number;
  created_at?: string;
  updated_at?: string;
}

export interface WebAuthnCredential {
  id: number;
  credential_id: string;
  device_name: string;
  created_at: string;
  last_used_at: string | null;
}

export interface WebAuthnRegistrationOptions {
  rp: {
    name: string;
    id: string;
  };
  user: {
    id: string;
    name: string;
    displayName: string;
  };
  challenge: string;
  pubKeyCredParams: Array<{
    type: string;
    alg: number;
  }>;
  timeout?: number;
  excludeCredentials?: Array<{
    type: string;
    id: string;
    transports?: string[];
  }>;
  authenticatorSelection?: {
    residentKey?: string;
    userVerification?: string;
    authenticatorAttachment?: string;
  };
  attestation?: string;
}

export interface WebAuthnAuthenticationOptions {
  challenge: string;
  timeout?: number;
  rpId: string;
  allowCredentials?: Array<{
    type: string;
    id: string;
    transports?: string[];
  }>;
  userVerification?: string;
}

export interface AccessRequest {
  id: number;
  email: string;
  name: string;
  domain: string;
  reason: string | null;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  updated_at: string;
  processed_by: User | null;
  processed_at: string | null;
  rejection_reason: string | null;
}

export interface TenantStatus {
  domain: string;
  has_users: boolean;
  user_count: number;
  auth_method: 'sso' | 'webauthn';
  allow_registration: boolean;
  require_approval: boolean;
  has_sso: boolean;
  sso_provider: string | null;
  sso_id: number | null;
  email_verification_required: boolean;
}

export interface EmailVerificationResponse {
  message: string;
  email: string;
  purpose: 'signup' | 'access_request' | 'login';
  token?: string;  // Only in debug mode
}

export interface VerificationStatus {
  valid: boolean;
  email?: string;
  domain?: string;
  purpose?: 'signup' | 'access_request' | 'login';
  expired?: boolean;
  verified?: boolean;
  error?: string;
}

export interface RoleRequest {
  id: number;
  user_id: number;
  tenant_id: number;
  requested_role: GlobalRole;
  reason: string | null;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  reviewed_at: string | null;
  reviewed_by?: User;
  user?: User;
}
