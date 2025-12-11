import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { SSOConfig, EmailConfig, User, AuthConfig, AccessRequest, RoleRequest } from '../models/decision.model';

export interface CreateSSOConfigRequest {
  domain: string;
  provider_name: string;
  client_id: string;
  client_secret: string;
  discovery_url: string;
  enabled?: boolean;
}

export interface UpdateSSOConfigRequest {
  provider_name?: string;
  client_id?: string;
  client_secret?: string;
  discovery_url?: string;
  enabled?: boolean;
}

export interface EmailConfigRequest {
  smtp_server: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password?: string;
  from_email: string;
  from_name?: string;
  use_tls?: boolean;
  enabled?: boolean;
}

export interface AuthConfigRequest {
  domain?: string;  // Only required for master account
  auth_method: 'sso' | 'webauthn';
  allow_registration?: boolean;
  require_approval?: boolean;
  rp_name?: string;
  allow_password?: boolean;
  allow_passkey?: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class AdminService {
  private apiUrl = '/api/admin';

  constructor(private http: HttpClient) {}

  // SSO Configuration
  getSSOConfigs(): Observable<SSOConfig[]> {
    return this.http.get<SSOConfig[]>(`${this.apiUrl}/sso`);
  }

  createSSOConfig(config: CreateSSOConfigRequest): Observable<SSOConfig> {
    return this.http.post<SSOConfig>(`${this.apiUrl}/sso`, config);
  }

  updateSSOConfig(id: number, config: UpdateSSOConfigRequest): Observable<SSOConfig> {
    return this.http.put<SSOConfig>(`${this.apiUrl}/sso/${id}`, config);
  }

  deleteSSOConfig(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/sso/${id}`);
  }

  // Email Configuration
  getEmailConfig(): Observable<EmailConfig | null> {
    return this.http.get<EmailConfig | null>(`${this.apiUrl}/email`);
  }

  getEmailConfigs(): Observable<EmailConfig[]> {
    return this.http.get<EmailConfig[]>(`${this.apiUrl}/email/domains`);
  }

  saveEmailConfig(config: EmailConfigRequest): Observable<EmailConfig> {
    return this.http.post<EmailConfig>(`${this.apiUrl}/email`, config);
  }

  testEmail(domain?: string, email?: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/email/test`, { domain, email });
  }

  // User Management
  getUsers(): Observable<User[]> {
    return this.http.get<User[]>(`${this.apiUrl}/users`);
  }

  toggleUserAdmin(userId: number, isAdmin: boolean): Observable<User> {
    return this.http.put<User>(`${this.apiUrl}/users/${userId}/admin`, { is_admin: isAdmin });
  }

  // Auth Configuration
  getAuthConfig(): Observable<AuthConfig | AuthConfig[]> {
    return this.http.get<AuthConfig | AuthConfig[]>(`${this.apiUrl}/auth-config`);
  }

  saveAuthConfig(config: AuthConfigRequest): Observable<AuthConfig> {
    return this.http.post<AuthConfig>(`${this.apiUrl}/auth-config`, config);
  }

  // Access Requests
  getAccessRequests(): Observable<AccessRequest[]> {
    return this.http.get<AccessRequest[]>(`${this.apiUrl}/access-requests`);
  }

  getPendingAccessRequests(): Observable<AccessRequest[]> {
    return this.http.get<AccessRequest[]>(`${this.apiUrl}/access-requests/pending`);
  }

  approveAccessRequest(requestId: number): Observable<{ message: string; user: User }> {
    return this.http.post<{ message: string; user: User }>(`${this.apiUrl}/access-requests/${requestId}/approve`, {});
  }

  rejectAccessRequest(requestId: number, reason?: string): Observable<{ message: string; request: AccessRequest }> {
    return this.http.post<{ message: string; request: AccessRequest }>(`${this.apiUrl}/access-requests/${requestId}/reject`, { reason });
  }

  // Setup Links
  generateSetupLink(userId: number): Observable<{ message: string; setup_url: string; token: string; expires_at: string; hours_valid: number }> {
    return this.http.post<{ message: string; setup_url: string; token: string; expires_at: string; hours_valid: number }>(`${this.apiUrl}/users/${userId}/setup-link`, {});
  }

  sendSetupEmail(userId: number): Observable<{ message: string; setup_url: string; expires_at: string; hours_valid: number }> {
    return this.http.post<{ message: string; setup_url: string; expires_at: string; hours_valid: number }>(`${this.apiUrl}/users/${userId}/send-setup-email`, {});
  }

  // Role Requests
  createRoleRequest(role: string, reason: string): Observable<RoleRequest> {
    return this.http.post<RoleRequest>(`${this.apiUrl}/role-requests`, { requested_role: role, reason });
  }

  getRoleRequests(): Observable<RoleRequest[]> {
    return this.http.get<RoleRequest[]>(`${this.apiUrl}/role-requests`);
  }

  approveRoleRequest(id: number): Observable<{ message: string; user: User }> {
    return this.http.post<{ message: string; user: User }>(`${this.apiUrl}/role-requests/${id}/approve`, {});
  }

  rejectRoleRequest(id: number, reason?: string): Observable<{ message: string; request: RoleRequest }> {
    return this.http.post<{ message: string; request: RoleRequest }>(`${this.apiUrl}/role-requests/${id}/reject`, { reason });
  }
}
