export interface User {
  id: number;
  email: string;
  name: string;
  sso_domain: string;
  auth_type: 'sso' | 'webauthn';
  is_admin: boolean;
  has_passkey: boolean;
  email_verified: boolean;
  created_at: string;
  last_login: string;
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

export interface Decision {
  id: number;
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
  auth_method: 'sso' | 'webauthn';
  allow_registration: boolean;
  require_approval: boolean;
  rp_name: string;
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
