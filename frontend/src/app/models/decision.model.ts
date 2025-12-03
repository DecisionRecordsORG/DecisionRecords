export interface User {
  id: number;
  email: string;
  name: string;
  sso_domain: string;
  is_admin: boolean;
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
