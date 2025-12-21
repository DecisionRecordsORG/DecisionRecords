import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatTabsModule } from '@angular/material/tabs';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatChipsModule } from '@angular/material/chips';
import { AdminService, CreateSSOConfigRequest, EmailConfigRequest, AuthConfigRequest, SlackSettings, SlackChannel } from '../../services/admin.service';
import { ActivatedRoute } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { SpaceService } from '../../services/space.service';
import { SSOConfig, EmailConfig, User, AuthConfig, AccessRequest, GlobalRole, Space, RoleRequest } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';
import { SetupLinkDialogComponent } from '../shared/setup-link-dialog.component';
import { MatSelectModule } from '@angular/material/select';
import { MatRadioModule } from '@angular/material/radio';
import { MatTooltipModule } from '@angular/material/tooltip';
import { getRoleBadge, RoleBadge } from '../../services/role.helper';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule,
    MatCardModule,
    MatDividerModule,
    MatTabsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatTableModule,
    MatSlideToggleModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDialogModule,
    MatChipsModule,
    MatSelectModule,
    MatRadioModule,
    MatTooltipModule,
    ConfirmDialogComponent,
    SetupLinkDialogComponent
  ],
  template: `
    <div class="settings-container">
      <h1>
        <mat-icon>settings</mat-icon>
        {{ authService.isMasterAccount ? 'System Settings' : 'Organization Settings' }}
      </h1>

      <!-- Provisional Admin Banner -->
      @if (isProvisionalAdmin) {
        <div class="provisional-admin-banner" data-testid="provisional-admin-banner">
          <mat-icon>info</mat-icon>
          <div class="banner-content">
            <strong>You are currently a provisional administrator.</strong>
            <p>Some settings will unlock once others from your organisation join.</p>
          </div>
        </div>
      }

      <mat-tab-group [(selectedIndex)]="selectedTabIndex">
        <!-- SSO Configuration Tab -->
        <mat-tab label="SSO Providers">
          <div class="tab-content">
            <mat-card class="info-card">
              <mat-card-header>
                <mat-card-title>
                  <mat-icon>info</mat-icon>
                  About Single Sign-On (SSO)
                </mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <p><strong>What is SSO?</strong> Single Sign-On allows your team to authenticate using your organisation's identity provider.</p>
                <h4>Security Benefits</h4>
                <ul>
                  <li>Centralised access control</li>
                  <li>Automatic deprovisioning when users leave</li>
                  <li>Enforced security policies from your IdP</li>
                </ul>
                <h4>Privacy Benefits</h4>
                <ul>
                  <li>No passwords stored in this application</li>
                  <li>Authentication handled by your trusted provider</li>
                </ul>
                <h4>Supported Providers</h4>
                <p>Google Workspace, Microsoft Entra ID (Azure AD), Okta, and any OIDC-compliant provider</p>
              </mat-card-content>
            </mat-card>

            <mat-card class="form-card">
              <mat-card-header>
                <mat-card-title>
                  {{ editingSSOId ? 'Edit SSO Provider' : 'Add SSO Provider' }}
                </mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <form [formGroup]="ssoForm" (ngSubmit)="saveSSOConfig()">
                  <div class="form-row">
                    <mat-form-field appearance="outline">
                      <mat-label>Domain</mat-label>
                      <input matInput formControlName="domain" placeholder="example.com"
                             [readonly]="editingSSOId !== null || !authService.isMasterAccount">
                      @if (!authService.isMasterAccount) {
                        <mat-hint>Domain is set to your organization</mat-hint>
                      }
                    </mat-form-field>

                    <mat-form-field appearance="outline">
                      <mat-label>Provider Name</mat-label>
                      <input matInput formControlName="provider_name" placeholder="Google, Okta, Azure AD...">
                    </mat-form-field>
                  </div>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Client ID</mat-label>
                    <input matInput formControlName="client_id">
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Client Secret</mat-label>
                    <input matInput formControlName="client_secret" type="password"
                           [placeholder]="editingSSOId ? 'Leave blank to keep existing' : ''">
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Discovery URL (OIDC)</mat-label>
                    <input matInput formControlName="discovery_url"
                           placeholder="https://accounts.google.com/.well-known/openid-configuration">
                  </mat-form-field>

                  <mat-slide-toggle formControlName="enabled">Enabled</mat-slide-toggle>

                  <div class="form-actions">
                    <button mat-flat-button color="primary" type="submit"
                            [disabled]="ssoForm.invalid || savingSSOConfig">
                      <mat-spinner diameter="20" *ngIf="savingSSOConfig"></mat-spinner>
                      <mat-icon *ngIf="!savingSSOConfig">save</mat-icon>
                      <span *ngIf="!savingSSOConfig">{{ editingSSOId ? 'Update' : 'Add Provider' }}</span>
                    </button>
                    @if (editingSSOId) {
                      <button mat-stroked-button type="button" (click)="cancelSSOEdit()">Cancel</button>
                    }
                  </div>
                </form>
              </mat-card-content>
            </mat-card>

            <mat-card class="list-card">
              <mat-card-header>
                <mat-card-title>SSO Providers</mat-card-title>
              </mat-card-header>
              <mat-card-content>
                @if (ssoConfigs.length === 0) {
                  <p class="empty-message">No SSO providers configured</p>
                } @else {
                  <table mat-table [dataSource]="ssoConfigs" class="full-width">
                    <ng-container matColumnDef="domain">
                      <th mat-header-cell *matHeaderCellDef>Domain</th>
                      <td mat-cell *matCellDef="let config">{{ config.domain }}</td>
                    </ng-container>

                    <ng-container matColumnDef="provider_name">
                      <th mat-header-cell *matHeaderCellDef>Provider</th>
                      <td mat-cell *matCellDef="let config">{{ config.provider_name }}</td>
                    </ng-container>

                    <ng-container matColumnDef="enabled">
                      <th mat-header-cell *matHeaderCellDef>Status</th>
                      <td mat-cell *matCellDef="let config">
                        <mat-chip [class.enabled]="config.enabled" [class.disabled]="!config.enabled">
                          {{ config.enabled ? 'Enabled' : 'Disabled' }}
                        </mat-chip>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="actions">
                      <th mat-header-cell *matHeaderCellDef>Actions</th>
                      <td mat-cell *matCellDef="let config">
                        <button mat-icon-button (click)="editSSOConfig(config)">
                          <mat-icon>edit</mat-icon>
                        </button>
                        <button mat-icon-button color="warn" (click)="deleteSSOConfig(config)">
                          <mat-icon>delete</mat-icon>
                        </button>
                      </td>
                    </ng-container>

                    <tr mat-header-row *matHeaderRowDef="ssoColumns"></tr>
                    <tr mat-row *matRowDef="let row; columns: ssoColumns;"></tr>
                  </table>
                }
              </mat-card-content>
            </mat-card>
          </div>
        </mat-tab>

        <!-- Email Configuration Tab -->
        <mat-tab label="Email Settings">
          <div class="tab-content">
            <mat-card class="info-card">
              <mat-card-header>
                <mat-card-title>
                  <mat-icon>info</mat-icon>
                  About Email Settings
                </mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <p><strong>What is this for?</strong> Configure email delivery for notifications about your organisation's architecture decisions.</p>
                <h4>Use Cases</h4>
                <ul>
                  <li>Decision status changes</li>
                  <li>Comment notifications</li>
                  <li>Weekly digests</li>
                </ul>
                <h4>Benefits</h4>
                <ul>
                  <li><strong>Privacy:</strong> Notifications stay on your organisation's mail infrastructure</li>
                  <li><strong>Branding:</strong> Send from your own domain for better deliverability</li>
                </ul>
                <p class="option-hint"><strong>Note:</strong> If not configured, the system will use the platform's default email service</p>
              </mat-card-content>
            </mat-card>

            <mat-card class="form-card">
              <mat-card-header>
                <mat-card-title>SMTP Configuration</mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <form [formGroup]="emailForm" (ngSubmit)="saveEmailConfig()">
                  <div class="form-row">
                    <mat-form-field appearance="outline">
                      <mat-label>SMTP Server</mat-label>
                      <input matInput formControlName="smtp_server" placeholder="smtp.gmail.com">
                    </mat-form-field>

                    <mat-form-field appearance="outline" class="small">
                      <mat-label>Port</mat-label>
                      <input matInput formControlName="smtp_port" type="number" placeholder="587">
                    </mat-form-field>
                  </div>

                  <div class="form-row">
                    <mat-form-field appearance="outline">
                      <mat-label>SMTP Username</mat-label>
                      <input matInput formControlName="smtp_username">
                    </mat-form-field>

                    <mat-form-field appearance="outline">
                      <mat-label>SMTP Password</mat-label>
                      <input matInput formControlName="smtp_password" type="password"
                             [placeholder]="hasExistingEmailConfig ? 'Leave blank to keep existing' : ''">
                    </mat-form-field>
                  </div>

                  <div class="form-row">
                    <mat-form-field appearance="outline">
                      <mat-label>From Email</mat-label>
                      <input matInput formControlName="from_email" placeholder="noreply@example.com">
                    </mat-form-field>

                    <mat-form-field appearance="outline">
                      <mat-label>From Name</mat-label>
                      <input matInput formControlName="from_name" placeholder="Architecture Decisions">
                    </mat-form-field>
                  </div>

                  <div class="toggle-row">
                    <mat-slide-toggle formControlName="use_tls">Use TLS</mat-slide-toggle>
                    <mat-slide-toggle formControlName="enabled">Enabled</mat-slide-toggle>
                  </div>

                  <div class="form-actions">
                    <button mat-flat-button color="primary" type="submit"
                            [disabled]="emailForm.invalid || savingEmailConfig">
                      <mat-spinner diameter="20" *ngIf="savingEmailConfig"></mat-spinner>
                      <mat-icon *ngIf="!savingEmailConfig">save</mat-icon>
                      <span *ngIf="!savingEmailConfig">Save Configuration</span>
                    </button>
                    <button mat-stroked-button type="button" (click)="testEmail()"
                            [disabled]="!hasExistingEmailConfig || testingEmail">
                      <mat-spinner diameter="20" *ngIf="testingEmail"></mat-spinner>
                      <mat-icon *ngIf="!testingEmail">send</mat-icon>
                      <span *ngIf="!testingEmail">Send Test Email</span>
                    </button>
                  </div>
                </form>
              </mat-card-content>
            </mat-card>
          </div>
        </mat-tab>

        <!-- User Management Tab -->
        <mat-tab label="Users">
          <div class="tab-content">
            <mat-card class="list-card">
              <mat-card-header>
                <mat-card-title>User Management</mat-card-title>
              </mat-card-header>
              <mat-card-content>
                @if (users.length === 0) {
                  <p class="empty-message">No users found</p>
                } @else {
                  <table mat-table [dataSource]="users" class="full-width" data-testid="user-list">
                    <ng-container matColumnDef="name">
                      <th mat-header-cell *matHeaderCellDef>Name</th>
                      <td mat-cell *matCellDef="let user">{{ user.name || 'No name' }}</td>
                    </ng-container>

                    <ng-container matColumnDef="email">
                      <th mat-header-cell *matHeaderCellDef>Email</th>
                      <td mat-cell *matCellDef="let user">{{ user.email }}</td>
                    </ng-container>

                    <ng-container matColumnDef="domain">
                      <th mat-header-cell *matHeaderCellDef>Domain</th>
                      <td mat-cell *matCellDef="let user">{{ user.sso_domain }}</td>
                    </ng-container>

                    <ng-container matColumnDef="auth_type">
                      <th mat-header-cell *matHeaderCellDef>Auth Type</th>
                      <td mat-cell *matCellDef="let user">
                        @if (user.auth_type === 'webauthn') {
                          <mat-icon class="auth-type-icon">fingerprint</mat-icon> Passkey
                        } @else {
                          <mat-icon class="auth-type-icon">login</mat-icon> SSO
                        }
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="role">
                      <th mat-header-cell *matHeaderCellDef>Role</th>
                      <td mat-cell *matCellDef="let user">
                        <mat-chip [class]="getUserRoleBadge(user.global_role).cssClass"
                                  [matTooltip]="getUserRoleBadge(user.global_role).tooltip"
                                  [attr.data-testid]="'role-badge-' + user.global_role">
                          {{ getUserRoleBadge(user.global_role).label }}
                        </mat-chip>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="last_login">
                      <th mat-header-cell *matHeaderCellDef>Last Login</th>
                      <td mat-cell *matCellDef="let user">
                        {{ user.last_login ? (user.last_login | date:'short') : 'Never' }}
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="actions">
                      <th mat-header-cell *matHeaderCellDef>Actions</th>
                      <td mat-cell *matCellDef="let user">
                        @if (!user.has_passkey && !user.has_password) {
                          <button mat-icon-button color="primary"
                                  (click)="generateSetupLink(user)"
                                  matTooltip="Generate Setup Link">
                            <mat-icon>link</mat-icon>
                          </button>
                        } @else {
                          <mat-chip class="credentials-chip">
                            @if (user.has_passkey) {
                              <mat-icon>fingerprint</mat-icon>
                            }
                            @if (user.has_password) {
                              <mat-icon>password</mat-icon>
                            }
                          </mat-chip>
                        }
                      </td>
                    </ng-container>

                    <tr mat-header-row *matHeaderRowDef="userColumns"></tr>
                    <tr mat-row *matRowDef="let row; columns: userColumns;"></tr>
                  </table>
                }
              </mat-card-content>
            </mat-card>
          </div>
        </mat-tab>

        <!-- Authentication Configuration Tab -->
        <mat-tab label="Authentication">
          <div class="tab-content">
            <mat-card class="form-card">
              <mat-card-header>
                <mat-card-title>
                  <mat-icon>security</mat-icon>
                  Authentication Method
                </mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <p class="section-description">
                  Configure how users in your organization authenticate. Choose the method that best fits your security needs.
                </p>

                <form [formGroup]="authConfigForm" (ngSubmit)="saveAuthConfig()">
                  <!-- Provisional Admin Auth Method Restriction Notice -->
                  @if (isProvisionalAdmin) {
                    <div class="provisional-auth-notice">
                      <mat-icon>lock</mat-icon>
                      <span>Authentication method settings are locked until shared administration is established.</span>
                    </div>
                  }

                  <div class="auth-method-options" [class.disabled-section]="isProvisionalAdmin">
                    <mat-radio-group formControlName="auth_method" class="auth-method-group">
                      <mat-radio-button value="both" class="auth-method-option" [disabled]="isProvisionalAdmin">
                        <div class="option-content">
                          <div class="option-icons">
                            <mat-icon>fingerprint</mat-icon>
                            <span class="icon-plus">+</span>
                            <mat-icon>password</mat-icon>
                          </div>
                          <div class="option-text">
                            <strong>Passkey + Password</strong>
                            <span class="recommended-badge">Recommended</span>
                            <span class="option-desc">Users can choose their preferred authentication method</span>
                          </div>
                        </div>
                      </mat-radio-button>

                      <mat-radio-button value="webauthn" class="auth-method-option" [disabled]="isProvisionalAdmin">
                        <div class="option-content">
                          <div class="option-icons">
                            <mat-icon>fingerprint</mat-icon>
                          </div>
                          <div class="option-text">
                            <strong>Passkey Only</strong>
                            <span class="option-desc">Enforce passwordless authentication for all users</span>
                          </div>
                        </div>
                      </mat-radio-button>

                      <mat-radio-button value="sso" class="auth-method-option"
                                        [disabled]="!hasSSOConfigForDomain || isProvisionalAdmin">
                        <div class="option-content">
                          <div class="option-icons">
                            <mat-icon>login</mat-icon>
                          </div>
                          <div class="option-text">
                            <strong>Single Sign-On (SSO)</strong>
                            @if (hasSSOConfigForDomain) {
                              <span class="option-desc">Use your organization's identity provider</span>
                            } @else {
                              <span class="option-desc disabled-hint">Configure SSO in the SSO Providers tab first</span>
                            }
                          </div>
                        </div>
                      </mat-radio-button>

                      <mat-radio-button value="slack_oidc" class="auth-method-option"
                                        [disabled]="!slackOidcGloballyEnabled || isProvisionalAdmin">
                        <div class="option-content">
                          <div class="option-icons">
                            <img src="/assets/slack-logo.svg" alt="Slack" class="slack-icon-auth">
                          </div>
                          <div class="option-text">
                            <strong>Slack Only</strong>
                            @if (slackOidcGloballyEnabled) {
                              <span class="option-desc">Only allow sign-in via Slack (SSO alternative)</span>
                            } @else {
                              <span class="option-desc disabled-hint">Slack integration not available</span>
                            }
                          </div>
                        </div>
                      </mat-radio-button>
                    </mat-radio-group>
                  </div>

                  <!-- Slack Sign-in Toggle (when not in slack_oidc mode) -->
                  @if (slackOidcGloballyEnabled && authConfigForm.value.auth_method !== 'slack_oidc' && authConfigForm.value.auth_method !== 'sso') {
                    <div class="slack-oidc-toggle-section">
                      <h4 class="options-header">Slack Sign-in</h4>
                      <mat-slide-toggle formControlName="allow_slack_oidc">
                        Allow "Sign in with Slack" option
                      </mat-slide-toggle>
                      <p class="option-hint">
                        When enabled, users can sign in using their Slack account in addition to other methods.
                      </p>
                    </div>
                  }

                  <!-- Google Sign-in Toggle (when not in SSO mode) -->
                  @if (googleOauthGloballyEnabled && authConfigForm.value.auth_method !== 'sso') {
                    <div class="google-oauth-toggle-section">
                      <h4 class="options-header">Google Sign-in</h4>
                      <mat-slide-toggle formControlName="allow_google_oauth">
                        Allow "Sign in with Google" option
                      </mat-slide-toggle>
                      <p class="option-hint">
                        When enabled, users with Google Workspace accounts from your domain can sign in using Google.
                        Personal Gmail accounts are not allowed.
                      </p>
                    </div>
                  }

                  <div class="registration-options" *ngIf="authConfigForm.value.auth_method !== 'sso'">
                      <h4 class="options-header">User Registration</h4>

                      @if (isProvisionalAdmin) {
                        <div class="provisional-admin-notice">
                          <mat-icon>info</mat-icon>
                          <span>These settings will become available once shared administration is established (add another admin or steward).</span>
                        </div>
                      }

                      <div class="toggle-with-tooltip">
                        <mat-slide-toggle formControlName="allow_registration"
                                          [disabled]="isProvisionalAdmin || (isRegistrationToggleRestricted && !authConfigForm.value.allow_registration)"
                                          data-testid="allow-registration-toggle">
                          Allow new user registration
                        </mat-slide-toggle>
                        @if (isRegistrationToggleRestricted && !isProvisionalAdmin) {
                          <mat-icon class="restricted-icon"
                                    matTooltip="This setting affects everyone in your organisation. It will become available once shared administration is established."
                                    data-testid="registration-lock-icon">
                            lock
                          </mat-icon>
                        }
                      </div>
                      <p class="option-hint">
                        When enabled, new users can create accounts. When disabled, only existing users can sign in.
                      </p>

                      <div class="approval-toggle-section" *ngIf="authConfigForm.value.allow_registration">
                          <div class="toggle-with-tooltip">
                            <mat-slide-toggle formControlName="auto_approve_users"
                                              [disabled]="isProvisionalAdmin || (isApprovalToggleRestricted && authConfigForm.value.auto_approve_users)"
                                              data-testid="auto-approve-toggle">
                              Auto-approve new users from your domain
                            </mat-slide-toggle>
                            @if (isApprovalToggleRestricted && !isProvisionalAdmin) {
                              <mat-icon class="restricted-icon"
                                        matTooltip="This setting affects everyone in your organisation. It will become available once shared administration is established."
                                        data-testid="approval-lock-icon">
                                lock
                              </mat-icon>
                            }
                          </div>
                          <p class="option-hint">
                            When enabled, users with verified {{ '@' + getCurrentDomain() }} emails are automatically approved.
                            When disabled, an admin must approve each new user.
                          </p>
                          <div class="auto-approve-warning" *ngIf="authConfigForm.value.auto_approve_users">
                              <mat-icon>info</mat-icon>
                              <span>Anyone with a verified {{ '@' + getCurrentDomain() }} email can automatically join your organization.</span>
                          </div>
                      </div>

                      <div class="app-name-section">
                        <mat-form-field appearance="outline" class="full-width">
                          <mat-label>Application Name</mat-label>
                          <input matInput formControlName="rp_name" placeholder="Architecture Decisions"
                                 [readonly]="isProvisionalAdmin">
                          <mat-hint>Shown to users during passkey setup</mat-hint>
                        </mat-form-field>
                      </div>
                  </div>

                  <div class="form-actions">
                    <button mat-flat-button color="primary" type="submit"
                            [disabled]="authConfigForm.invalid || savingAuthConfig">
                      <mat-spinner diameter="20" *ngIf="savingAuthConfig"></mat-spinner>
                      <mat-icon *ngIf="!savingAuthConfig">save</mat-icon>
                      <span *ngIf="!savingAuthConfig">Save Configuration</span>
                    </button>
                  </div>
                </form>
              </mat-card-content>
            </mat-card>

            <mat-card class="info-card">
              <mat-card-header>
                <mat-card-title>
                  <mat-icon>info</mat-icon>
                  About Authentication Methods
                </mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <div class="auth-info-grid">
                  <div class="auth-info-item">
                    <h4><mat-icon>fingerprint</mat-icon> Passkeys</h4>
                    <ul>
                      <li>No passwords to remember</li>
                      <li>Uses device biometrics (fingerprint, face)</li>
                      <li>Resistant to phishing</li>
                      <li>Can register multiple devices</li>
                    </ul>
                  </div>
                  <div class="auth-info-item">
                    <h4><mat-icon>password</mat-icon> Passwords</h4>
                    <ul>
                      <li>Traditional authentication</li>
                      <li>Works on any device</li>
                      <li>Good fallback option</li>
                      <li>Requires password management</li>
                    </ul>
                  </div>
                  <div class="auth-info-item">
                    <h4><mat-icon>login</mat-icon> SSO</h4>
                    <ul>
                      <li>Centralized authentication</li>
                      <li>Google, Microsoft, Okta support</li>
                      <li>One login for all apps</li>
                      <li>Managed by IT</li>
                    </ul>
                  </div>
                </div>
              </mat-card-content>
            </mat-card>
          </div>
        </mat-tab>

        <!-- Spaces Tab (for non-master admins only) -->
        <mat-tab label="Spaces" *ngIf="!authService.isMasterAccount">
          <div class="tab-content">
            <mat-card class="form-card">
              <mat-card-header>
                <mat-card-title>
                  <mat-icon>folder</mat-icon>
                  {{ editingSpaceId ? 'Edit Space' : 'Create New Space' }}
                </mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <form [formGroup]="spaceForm" (ngSubmit)="saveSpace()">
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Space Name</mat-label>
                    <input matInput formControlName="name" placeholder="e.g., Backend, Frontend, Infrastructure">
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Description (optional)</mat-label>
                    <textarea matInput formControlName="description" rows="3"
                              placeholder="Describe this space..."></textarea>
                  </mat-form-field>

                  <mat-slide-toggle formControlName="is_default" [disabled]="isEditingDefaultSpace()">
                    Set as default space
                  </mat-slide-toggle>
                  <p class="option-hint">New decisions will automatically be assigned to the default space.</p>

                  <div class="form-actions">
                    <button mat-flat-button color="primary" type="submit"
                            [disabled]="spaceForm.invalid || savingSpace">
                      <mat-spinner diameter="20" *ngIf="savingSpace"></mat-spinner>
                      <mat-icon *ngIf="!savingSpace">save</mat-icon>
                      <span *ngIf="!savingSpace">{{ editingSpaceId ? 'Update' : 'Create Space' }}</span>
                    </button>
                    @if (editingSpaceId) {
                      <button mat-stroked-button type="button" (click)="cancelSpaceEdit()">Cancel</button>
                    }
                  </div>
                </form>
              </mat-card-content>
            </mat-card>

            <mat-card class="list-card">
              <mat-card-header>
                <mat-card-title>Spaces</mat-card-title>
              </mat-card-header>
              <mat-card-content>
                @if (loadingSpaces) {
                  <div class="loading-container">
                    <mat-spinner diameter="40"></mat-spinner>
                  </div>
                } @else if (spaces.length === 0) {
                  <p class="empty-message">No spaces configured</p>
                } @else {
                  <table mat-table [dataSource]="spaces" class="full-width">
                    <ng-container matColumnDef="name">
                      <th mat-header-cell *matHeaderCellDef>Name</th>
                      <td mat-cell *matCellDef="let space">
                        {{ space.name }}
                        @if (space.is_default) {
                          <mat-chip class="default-chip">Default</mat-chip>
                        }
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="description">
                      <th mat-header-cell *matHeaderCellDef>Description</th>
                      <td mat-cell *matCellDef="let space">{{ space.description || '-' }}</td>
                    </ng-container>

                    <ng-container matColumnDef="decision_count">
                      <th mat-header-cell *matHeaderCellDef>Decisions</th>
                      <td mat-cell *matCellDef="let space">{{ space.decision_count || 0 }}</td>
                    </ng-container>

                    <ng-container matColumnDef="actions">
                      <th mat-header-cell *matHeaderCellDef>Actions</th>
                      <td mat-cell *matCellDef="let space">
                        <button mat-icon-button (click)="editSpace(space)" matTooltip="Edit">
                          <mat-icon>edit</mat-icon>
                        </button>
                        <button mat-icon-button color="warn" (click)="deleteSpace(space)"
                                [disabled]="space.is_default" matTooltip="{{ space.is_default ? 'Cannot delete default space' : 'Delete' }}">
                          <mat-icon>delete</mat-icon>
                        </button>
                      </td>
                    </ng-container>

                    <tr mat-header-row *matHeaderRowDef="spaceColumns"></tr>
                    <tr mat-row *matRowDef="let row; columns: spaceColumns;"></tr>
                  </table>
                }
              </mat-card-content>
            </mat-card>

            <mat-card class="info-card">
              <mat-card-header>
                <mat-card-title>
                  <mat-icon>info</mat-icon>
                  About Spaces
                </mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <p>Spaces help organize your architecture decisions into logical groups.</p>
                <ul>
                  <li><strong>Default Space:</strong> New decisions are automatically assigned to this space</li>
                  <li><strong>Multiple Spaces:</strong> Decisions can belong to multiple spaces</li>
                  <li><strong>Filtering:</strong> Users can filter decisions by space in the decision list</li>
                </ul>
              </mat-card-content>
            </mat-card>
          </div>
        </mat-tab>

        <!-- Access Requests Tab (for non-master admins only) -->
        <mat-tab *ngIf="!authService.isMasterAccount">
          <ng-template mat-tab-label>
            Access Requests
            <span class="tab-badge" *ngIf="pendingRequestsCount > 0">{{ pendingRequestsCount }}</span>
          </ng-template>
            <div class="tab-content">
              <mat-card class="list-card">
                <mat-card-header>
                  <mat-card-title>
                    <mat-icon>person_add</mat-icon>
                    Pending Access Requests
                  </mat-card-title>
                </mat-card-header>
                <mat-card-content>
                  <div class="loading-container" *ngIf="loadingRequests">
                      <mat-spinner diameter="40"></mat-spinner>
                  </div>
                  <p class="empty-message" *ngIf="!loadingRequests && accessRequests.length === 0">No pending access requests</p>
                  <table mat-table [dataSource]="accessRequests" class="full-width" *ngIf="!loadingRequests && accessRequests.length > 0">
                      <ng-container matColumnDef="name">
                        <th mat-header-cell *matHeaderCellDef>Name</th>
                        <td mat-cell *matCellDef="let request">{{ request.name }}</td>
                      </ng-container>

                      <ng-container matColumnDef="email">
                        <th mat-header-cell *matHeaderCellDef>Email</th>
                        <td mat-cell *matCellDef="let request">{{ request.email }}</td>
                      </ng-container>

                      <ng-container matColumnDef="reason">
                        <th mat-header-cell *matHeaderCellDef>Reason</th>
                        <td mat-cell *matCellDef="let request">
                          {{ request.reason || 'No reason provided' }}
                        </td>
                      </ng-container>

                      <ng-container matColumnDef="created_at">
                        <th mat-header-cell *matHeaderCellDef>Requested</th>
                        <td mat-cell *matCellDef="let request">
                          {{ request.created_at | date:'short' }}
                        </td>
                      </ng-container>

                      <ng-container matColumnDef="status">
                        <th mat-header-cell *matHeaderCellDef>Status</th>
                        <td mat-cell *matCellDef="let request">
                          <mat-chip [class]="'status-' + request.status">
                            {{ request.status | titlecase }}
                          </mat-chip>
                        </td>
                      </ng-container>

                      <ng-container matColumnDef="actions">
                        <th mat-header-cell *matHeaderCellDef>Actions</th>
                        <td mat-cell *matCellDef="let request">
                          <ng-container *ngIf="request.status === 'pending'">
                            <button mat-icon-button color="primary"
                                    (click)="approveRequest(request)"
                                    [disabled]="processingRequest === request.id"
                                    matTooltip="Approve">
                              <mat-spinner diameter="20" *ngIf="processingRequest === request.id"></mat-spinner>
                              <mat-icon *ngIf="processingRequest !== request.id">check_circle</mat-icon>
                            </button>
                            <button mat-icon-button color="warn"
                                    (click)="rejectRequest(request)"
                                    [disabled]="processingRequest === request.id"
                                    matTooltip="Reject">
                              <mat-icon>cancel</mat-icon>
                            </button>
                          </ng-container>
                          <span class="status-text approved" *ngIf="request.status === 'approved'">
                              <mat-icon>check</mat-icon> Approved
                          </span>
                          <span class="status-text rejected" *ngIf="request.status === 'rejected'">
                              <mat-icon>close</mat-icon> Rejected
                          </span>
                        </td>
                      </ng-container>

                      <tr mat-header-row *matHeaderRowDef="accessRequestColumns"></tr>
                      <tr mat-row *matRowDef="let row; columns: accessRequestColumns;"></tr>
                    </table>
                </mat-card-content>
              </mat-card>

              <mat-card class="info-card">
                <mat-card-header>
                  <mat-card-title>
                    <mat-icon>info</mat-icon>
                    About Access Requests
                  </mat-card-title>
                </mat-card-header>
                <mat-card-content>
                  <p>When users try to sign up with an email domain that already has an existing tenant,
                  they can request access instead of creating a new account.</p>
                  <ul>
                    <li><strong>Approve:</strong> Creates a new user account with the requested email</li>
                    <li><strong>Reject:</strong> Denies access (you can provide a reason)</li>
                  </ul>
                  <p>Approved users will be able to sign in using the authentication method configured for your domain.</p>
                </mat-card-content>
              </mat-card>
            </div>
          </mat-tab>

        <!-- Role Requests Tab (for non-master admins only) -->
        <mat-tab *ngIf="!authService.isMasterAccount">
          <ng-template mat-tab-label>
            Role Requests
            <span class="tab-badge" *ngIf="pendingRoleRequestsCount > 0">{{ pendingRoleRequestsCount }}</span>
          </ng-template>
          <div class="tab-content">
            <mat-card class="list-card">
              <mat-card-header>
                <mat-card-title>
                  <mat-icon>admin_panel_settings</mat-icon>
                  Role Elevation Requests
                </mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <div class="loading-container" *ngIf="loadingRoleRequests">
                  <mat-spinner diameter="40"></mat-spinner>
                </div>
                <p class="empty-message" *ngIf="!loadingRoleRequests && roleRequests.length === 0">No role requests</p>
                <table mat-table [dataSource]="roleRequests" class="full-width" *ngIf="!loadingRoleRequests && roleRequests.length > 0">
                  <ng-container matColumnDef="user">
                    <th mat-header-cell *matHeaderCellDef>User</th>
                    <td mat-cell *matCellDef="let request">
                      <div class="user-info">
                        <strong>{{ request.user?.name || 'Unknown' }}</strong>
                        <span class="email-text">{{ request.user?.email }}</span>
                      </div>
                    </td>
                  </ng-container>

                  <ng-container matColumnDef="requested_role">
                    <th mat-header-cell *matHeaderCellDef>Requested Role</th>
                    <td mat-cell *matCellDef="let request">
                      <mat-chip [class]="getRoleChipClass(request.requested_role)">
                        {{ request.requested_role === 'admin' ? 'Administrator' : 'Steward' }}
                      </mat-chip>
                    </td>
                  </ng-container>

                  <ng-container matColumnDef="reason">
                    <th mat-header-cell *matHeaderCellDef>Reason</th>
                    <td mat-cell *matCellDef="let request">
                      <div class="reason-cell">
                        {{ request.reason || 'No reason provided' }}
                      </div>
                    </td>
                  </ng-container>

                  <ng-container matColumnDef="created_at">
                    <th mat-header-cell *matHeaderCellDef>Requested</th>
                    <td mat-cell *matCellDef="let request">
                      {{ request.created_at | date:'short' }}
                    </td>
                  </ng-container>

                  <ng-container matColumnDef="status">
                    <th mat-header-cell *matHeaderCellDef>Status</th>
                    <td mat-cell *matCellDef="let request">
                      <mat-chip [class]="'status-' + request.status">
                        {{ request.status | titlecase }}
                      </mat-chip>
                    </td>
                  </ng-container>

                  <ng-container matColumnDef="actions">
                    <th mat-header-cell *matHeaderCellDef>Actions</th>
                    <td mat-cell *matCellDef="let request">
                      <ng-container *ngIf="request.status === 'pending'">
                        <button mat-icon-button color="primary"
                                (click)="approveRoleRequest(request)"
                                [disabled]="processingRoleRequest === request.id"
                                matTooltip="Approve">
                          <mat-spinner diameter="20" *ngIf="processingRoleRequest === request.id"></mat-spinner>
                          <mat-icon *ngIf="processingRoleRequest !== request.id">check_circle</mat-icon>
                        </button>
                        <button mat-icon-button color="warn"
                                (click)="rejectRoleRequest(request)"
                                [disabled]="processingRoleRequest === request.id"
                                matTooltip="Reject">
                          <mat-icon>cancel</mat-icon>
                        </button>
                      </ng-container>
                      <span class="status-text approved" *ngIf="request.status === 'approved'">
                        <mat-icon>check</mat-icon> Approved
                      </span>
                      <span class="status-text rejected" *ngIf="request.status === 'rejected'">
                        <mat-icon>close</mat-icon> Rejected
                      </span>
                    </td>
                  </ng-container>

                  <tr mat-header-row *matHeaderRowDef="roleRequestColumns"></tr>
                  <tr mat-row *matRowDef="let row; columns: roleRequestColumns;"></tr>
                </table>
              </mat-card-content>
            </mat-card>

            <mat-card class="info-card">
              <mat-card-header>
                <mat-card-title>
                  <mat-icon>info</mat-icon>
                  About Role Requests
                </mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <p>Users can request elevated privileges to help manage the organization.</p>
                <ul>
                  <li><strong>Steward:</strong> Can approve access requests, invite users, and help with basic governance</li>
                  <li><strong>Admin:</strong> Full administrative access to all settings and configurations</li>
                  <li><strong>Transparency:</strong> All role requests are logged and visible to current admins and stewards</li>
                </ul>
                <p>Review each request carefully and consider the user's role and needs before approving.</p>
              </mat-card-content>
            </mat-card>
          </div>
        </mat-tab>

        <!-- Slack Integration Tab (only for tenant admins and when feature enabled) -->
        @if (!authService.isMasterAccount && slackFeatureEnabled) {
        <mat-tab label="Slack">
          <div class="tab-content">
            <mat-card class="info-card">
              <mat-card-header>
                <mat-card-title>
                  <mat-icon>info</mat-icon>
                  About Slack Integration
                </mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <p>Connect Slack to enable your team to:</p>
                <ul>
                  <li><strong>Slash Commands:</strong> Use <code>/decision</code>, <code>/decision list</code>, <code>/decision view</code> directly in Slack</li>
                  <li><strong>Notifications:</strong> Get notified when decisions are created or updated</li>
                  <li><strong>Quick Access:</strong> View and manage decisions without leaving Slack</li>
                </ul>
              </mat-card-content>
            </mat-card>

            @if (loadingSlackSettings) {
              <div class="loading-spinner">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else if (!slackSettings?.installed) {
              <!-- Not Connected -->
              <mat-card class="form-card">
                <mat-card-header>
                  <mat-card-title>
                    <mat-icon>link_off</mat-icon>
                    Slack Not Connected
                  </mat-card-title>
                </mat-card-header>
                <mat-card-content>
                  <p>Connect your Slack workspace to enable slash commands and notifications.</p>

                  <div class="slack-connect-options">
                    <div class="connect-option">
                      <h4>Option A: Install Fresh</h4>
                      <p>Install Decision Records to your Slack workspace. You need Slack admin permissions for this option.</p>

                      <div class="slack-install-guidance">
                        <h5>What happens when you click "Add to Slack":</h5>
                        <ol>
                          <li>You'll be redirected to Slack to authorize the app</li>
                          <li>Select which workspace to install it to</li>
                          <li>After installation, you'll be redirected back here</li>
                          <li>The integration will be automatically connected</li>
                        </ol>
                      </div>

                      <a mat-flat-button color="primary" href="/api/slack/install" target="_blank" rel="noopener noreferrer" data-testid="slack-install-button">
                        <mat-icon>add</mat-icon>
                        Add to Slack
                      </a>

                      <p class="slack-install-note">
                        <mat-icon>info</mat-icon>
                        <span>After installing, return to this page and refresh to see the connection status.</span>
                      </p>
                    </div>

                    <mat-divider></mat-divider>

                    <div class="connect-option">
                      <h4>Option B: Claim Existing Installation</h4>
                      <p>If your IT team already installed the app from the Slack App Directory, enter your Workspace ID to claim it:</p>
                      <div class="claim-form">
                        <mat-form-field appearance="outline">
                          <mat-label>Slack Workspace ID</mat-label>
                          <input matInput [(ngModel)]="slackClaimWorkspaceId" placeholder="e.g., T0A36UYCYLX" data-testid="slack-workspace-id-input">
                          <mat-hint>Workspace IDs start with T</mat-hint>
                        </mat-form-field>
                        <button mat-stroked-button color="primary" (click)="claimSlackWorkspace()" [disabled]="claimingSlackWorkspace || !slackClaimWorkspaceId" data-testid="slack-claim-button">
                          <mat-spinner diameter="20" *ngIf="claimingSlackWorkspace"></mat-spinner>
                          <mat-icon *ngIf="!claimingSlackWorkspace">verified</mat-icon>
                          <span>{{ claimingSlackWorkspace ? 'Claiming...' : 'Claim Workspace' }}</span>
                        </button>
                      </div>
                      <p class="note"><mat-icon>info</mat-icon> Note: You need Slack admin permissions to install apps. If you're not a Slack admin, ask your IT team to install "Decision Records" and share the Workspace ID with you.</p>
                    </div>
                  </div>
                </mat-card-content>
              </mat-card>
            } @else if (slackSettings) {
              <!-- Connected -->
              <mat-card class="form-card slack-connected-card">
                <mat-card-header>
                  <mat-card-title class="slack-connected-title">
                    <mat-icon class="slack-connected-icon">check_circle</mat-icon>
                    Connected to {{ slackSettings.workspace_name || 'Slack' }}
                  </mat-card-title>
                </mat-card-header>
                <mat-card-content>
                  <div class="slack-status">
                    <p><strong>Workspace:</strong> {{ slackSettings.workspace_name || 'Unknown' }}</p>
                    <p><strong>Installed:</strong> {{ slackSettings.installed_at ? (slackSettings.installed_at | date:'medium') : 'Unknown' }}</p>
                    @if (slackSettings.last_activity_at) {
                      <p><strong>Last activity:</strong> {{ slackSettings.last_activity_at | date:'medium' }}</p>
                    }
                  </div>

                  <h4>Notification Settings</h4>
                  <form [formGroup]="slackForm" class="slack-form">
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Notification Channel</mat-label>
                      <mat-select formControlName="default_channel_id" data-testid="slack-channel-select">
                        <mat-option value="">-- Select a channel --</mat-option>
                        @for (channel of slackChannels; track channel.id) {
                          <mat-option [value]="channel.id">
                            {{ channel.is_private ? '🔒 ' : '#' }}{{ channel.name }}
                          </mat-option>
                        }
                      </mat-select>
                    </mat-form-field>

                    <div class="toggle-group">
                      <mat-slide-toggle formControlName="notifications_enabled" data-testid="slack-notifications-toggle">
                        Enable notifications
                      </mat-slide-toggle>
                    </div>

                    <div class="toggle-group nested" [class.disabled]="!slackForm.get('notifications_enabled')?.value">
                      <mat-slide-toggle formControlName="notify_on_create" [disabled]="!slackForm.get('notifications_enabled')?.value" data-testid="slack-notify-create-toggle">
                        Notify when decisions are created
                      </mat-slide-toggle>
                    </div>

                    <div class="toggle-group nested" [class.disabled]="!slackForm.get('notifications_enabled')?.value">
                      <mat-slide-toggle formControlName="notify_on_status_change" [disabled]="!slackForm.get('notifications_enabled')?.value" data-testid="slack-notify-status-toggle">
                        Notify when decision status changes
                      </mat-slide-toggle>
                    </div>
                  </form>
                </mat-card-content>
                <mat-card-actions>
                  <button mat-flat-button color="primary" (click)="saveSlackSettings()" [disabled]="savingSlackSettings" data-testid="slack-save-button">
                    <mat-spinner diameter="20" *ngIf="savingSlackSettings"></mat-spinner>
                    <mat-icon *ngIf="!savingSlackSettings">save</mat-icon>
                    <span *ngIf="!savingSlackSettings">Save Settings</span>
                  </button>
                  <button mat-stroked-button (click)="testSlackNotification()" [disabled]="testingSlack || !slackSettings.default_channel_id" data-testid="slack-test-button">
                    <mat-spinner diameter="20" *ngIf="testingSlack"></mat-spinner>
                    <mat-icon *ngIf="!testingSlack">send</mat-icon>
                    <span *ngIf="!testingSlack">Send Test</span>
                  </button>
                  <button mat-stroked-button color="warn" (click)="disconnectSlack()" data-testid="slack-disconnect-button">
                    <mat-icon>link_off</mat-icon>
                    Disconnect
                  </button>
                </mat-card-actions>
              </mat-card>
            }
          </div>
        </mat-tab>
        }
      </mat-tab-group>
    </div>
  `,
  styles: [`
    .settings-container {
      padding: 24px;
      max-width: 1200px;
      margin: 0 auto;
    }

    h1 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 24px;
    }

    /* Provisional Admin Banner */
    .provisional-admin-banner {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 16px 20px;
      margin-bottom: 24px;
      background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
      border-radius: 12px;
      border-left: 4px solid #ff9800;
    }

    .provisional-admin-banner mat-icon {
      color: #f57c00;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .provisional-admin-banner .banner-content {
      flex: 1;
    }

    .provisional-admin-banner strong {
      display: block;
      color: #e65100;
      margin-bottom: 4px;
      font-size: 15px;
    }

    .provisional-admin-banner p {
      margin: 0;
      font-size: 13px;
      color: #5d4037;
      line-height: 1.5;
    }

    /* Toggle with tooltip */
    .toggle-with-tooltip {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .restricted-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #ff9800;
      cursor: help;
    }

    .provisional-admin-notice {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 12px;
      background-color: #fff3e0;
      border-radius: 8px;
      margin-bottom: 16px;
      color: #e65100;
      font-size: 13px;
    }

    .provisional-admin-notice mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
      flex-shrink: 0;
    }

    /* Role badge styles */
    .role-admin {
      background-color: #e3f2fd !important;
      color: #1565c0 !important;
    }

    .role-provisional {
      background-color: #fff3e0 !important;
      color: #e65100 !important;
    }

    .role-steward {
      background-color: #f3e5f5 !important;
      color: #7b1fa2 !important;
    }

    .role-user {
      background-color: #f5f5f5 !important;
      color: #616161 !important;
    }

    /* Tab Styling */
    ::ng-deep .mat-mdc-tab-group {
      margin-top: 16px;
      background: #f8fafc;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }

    ::ng-deep .mat-mdc-tab-header {
      background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
      border-bottom: none;
      border-radius: 12px 12px 0 0;
      padding: 0 8px;
    }

    ::ng-deep .mat-mdc-tab-labels {
      gap: 4px;
    }

    ::ng-deep .mat-mdc-tab {
      min-width: 100px;
      padding: 0 20px;
      opacity: 1;
      height: 52px;
      border-radius: 8px 8px 0 0;
      margin-top: 4px;
    }

    ::ng-deep .mat-mdc-tab:hover {
      background: rgba(255, 255, 255, 0.05);
    }

    ::ng-deep .mat-mdc-tab .mdc-tab__text-label {
      color: rgba(255, 255, 255, 0.7) !important;
      font-weight: 500 !important;
      font-size: 13px !important;
      letter-spacing: 0.3px;
    }

    ::ng-deep .mat-mdc-tab:hover .mdc-tab__text-label {
      color: rgba(255, 255, 255, 0.95) !important;
    }

    ::ng-deep .mat-mdc-tab.mdc-tab--active {
      background: rgba(96, 165, 250, 0.15);
    }

    ::ng-deep .mat-mdc-tab.mdc-tab--active .mdc-tab__text-label {
      color: white !important;
      font-weight: 600 !important;
    }

    ::ng-deep .mat-mdc-tab-body-wrapper {
      background: #f8fafc;
      min-height: 400px;
    }

    ::ng-deep .mat-mdc-tab-body-content {
      padding: 24px;
      overflow: hidden !important;
    }

    ::ng-deep .mat-mdc-tab-body.mat-mdc-tab-body-active {
      overflow-y: hidden !important;
    }

    ::ng-deep .mdc-tab-indicator__content--underline {
      border-color: #60a5fa !important;
      border-width: 3px !important;
    }

    .tab-content {
      padding: 0;
    }

    /* Info Card Styling */
    .info-card {
      background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
      border: 1px solid #bfdbfe;
      border-radius: 12px;
      margin-bottom: 24px;
      box-shadow: none;
    }

    .info-card mat-card-header {
      padding: 16px 20px 0;
    }

    .info-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 16px;
      font-weight: 600;
      color: #1e40af;
    }

    .info-card mat-card-title mat-icon {
      color: #3b82f6;
      font-size: 22px;
      width: 22px;
      height: 22px;
    }

    .info-card mat-card-content {
      padding: 16px 20px 20px;
      color: #1e3a5f;
      font-size: 14px;
      line-height: 1.6;
    }

    .info-card h4 {
      font-size: 14px;
      font-weight: 600;
      color: #1e40af;
      margin: 16px 0 8px;
    }

    .info-card ul {
      margin: 0;
      padding-left: 20px;
    }

    .info-card li {
      margin-bottom: 4px;
    }

    /* Form Card Styling */
    .form-card, .list-card {
      background: white;
      border-radius: 12px;
      border: 1px solid #e2e8f0;
      margin-bottom: 24px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }

    .form-card mat-card-header,
    .list-card mat-card-header {
      padding: 20px 24px 0;
      border-bottom: 1px solid #f1f5f9;
      margin-bottom: 0;
    }

    .form-card mat-card-title,
    .list-card mat-card-title {
      font-size: 18px;
      font-weight: 600;
      color: #1e293b;
      padding-bottom: 16px;
    }

    .form-card mat-card-content,
    .list-card mat-card-content {
      padding: 24px;
    }

    .form-row {
      display: flex;
      gap: 16px;
    }

    .form-row mat-form-field {
      flex: 1;
    }

    .form-row mat-form-field.small {
      flex: 0 0 120px;
    }

    .full-width {
      width: 100%;
    }

    mat-form-field {
      margin-bottom: 8px;
    }

    .toggle-row {
      display: flex;
      gap: 24px;
      margin: 16px 0;
    }

    .form-actions {
      display: flex;
      gap: 12px;
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid #f1f5f9;
    }

    /* Primary button styling - consistent across all tabs */
    .form-actions button[mat-flat-button][color="primary"],
    mat-card-actions button[mat-flat-button][color="primary"],
    mat-card-actions a[mat-flat-button][color="primary"] {
      background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
      border-radius: 8px;
      padding: 0 24px;
      height: 40px;
      font-weight: 500;
    }

    /* Secondary button styling - consistent across all tabs */
    .form-actions button[mat-stroked-button],
    mat-card-actions button[mat-stroked-button] {
      border-radius: 8px;
      padding: 0 20px;
      height: 40px;
      border-color: #cbd5e1;
      color: #475569;
      font-weight: 500;
    }

    .form-actions button[mat-stroked-button]:hover,
    mat-card-actions button[mat-stroked-button]:hover {
      background: #f1f5f9;
      border-color: #94a3b8;
    }

    /* Warn button styling */
    mat-card-actions button[mat-stroked-button][color="warn"] {
      border-color: #fca5a5;
      color: #dc2626;
    }

    mat-card-actions button[mat-stroked-button][color="warn"]:hover {
      background: #fef2f2;
      border-color: #f87171;
    }

    .empty-message {
      text-align: center;
      color: #888;
      padding: 24px;
    }

    table {
      width: 100%;
    }

    mat-chip.enabled {
      background-color: #e8f5e9 !important;
      color: #2e7d32 !important;
    }

    mat-chip.disabled {
      background-color: #ffebee !important;
      color: #c62828 !important;
    }

    .auth-type-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      vertical-align: middle;
      margin-right: 4px;
    }

    .section-description {
      color: #666;
      margin-bottom: 24px;
    }

    .auth-method-group {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .auth-method-option {
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 16px;
      margin: 0;
    }

    .auth-method-option.mat-mdc-radio-checked {
      border-color: #3f51b5;
      background-color: #f5f7ff;
    }

    .option-content {
      display: flex;
      align-items: flex-start;
      gap: 12px;
    }

    .option-content mat-icon {
      color: #3f51b5;
      margin-top: 2px;
    }

    .option-text {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .option-text strong {
      font-size: 16px;
    }

    .option-text span {
      font-size: 14px;
      color: #666;
    }

    .webauthn-options {
      margin-top: 24px;
      padding: 16px;
      background: #f5f5f5;
      border-radius: 8px;
    }

    .option-hint {
      font-size: 13px;
      color: #666;
      margin: 8px 0 16px 0;
    }

    .info-card {
      background: #fafafa;
    }

    .info-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px !important;
    }

    .info-card mat-card-content {
      font-size: 12px;
      color: #666;
    }

    .info-card mat-card-content p {
      font-size: 12px;
      margin: 8px 0;
    }

    .info-card h4 {
      margin: 12px 0 6px 0;
      color: #333;
      font-size: 13px;
    }

    .info-card ul {
      margin: 0;
      padding-left: 16px;
      color: #666;
      font-size: 12px;
    }

    .info-card li {
      margin-bottom: 3px;
      line-height: 1.4;
    }

    .tab-badge {
      background: #ff4081;
      color: white;
      border-radius: 50%;
      padding: 2px 6px;
      font-size: 11px;
      margin-left: 8px;
    }

    .loading-container {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .status-pending {
      background-color: #fff3e0 !important;
      color: #e65100 !important;
    }

    .status-approved {
      background-color: #e8f5e9 !important;
      color: #2e7d32 !important;
    }

    .status-rejected {
      background-color: #ffebee !important;
      color: #c62828 !important;
    }

    .status-text {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 13px;
    }

    .status-text.approved {
      color: #2e7d32;
    }

    .status-text.rejected {
      color: #c62828;
    }

    .status-text mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    .credentials-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: #e8f5e9 !important;
      color: #2e7d32 !important;
    }

    .credentials-chip mat-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
    }

    .approval-toggle-section {
      margin-bottom: 16px;
    }

    .auto-approve-warning {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 12px;
      margin-top: 12px;
      background: #fff3e0;
      border-radius: 8px;
      border-left: 4px solid #ff9800;
    }

    .auto-approve-warning mat-icon {
      color: #f57c00;
      flex-shrink: 0;
    }

    .auto-approve-warning span {
      font-size: 13px;
      color: #5d4037;
      line-height: 1.4;
    }

    /* Provisional Admin Auth Method Restriction */
    .provisional-auth-notice {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 16px;
      margin-bottom: 16px;
      background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
      border-radius: 8px;
      border-left: 4px solid #ff9800;
    }

    .provisional-auth-notice mat-icon {
      color: #f57c00;
      flex-shrink: 0;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .provisional-auth-notice span {
      font-size: 13px;
      color: #5d4037;
      line-height: 1.4;
    }

    .disabled-section {
      opacity: 0.6;
      pointer-events: none;
      position: relative;
    }

    .disabled-section::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(255, 255, 255, 0.3);
      border-radius: 8px;
      cursor: not-allowed;
    }

    /* Authentication method options styling */
    .auth-method-options {
      margin-bottom: 24px;
    }

    .option-icons {
      display: flex;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
    }

    .option-icons mat-icon {
      font-size: 28px;
      width: 28px;
      height: 28px;
    }

    .option-icons .slack-icon-auth {
      width: 24px;
      height: 24px;
    }

    .slack-oidc-toggle-section {
      margin-top: 24px;
      padding-top: 24px;
      border-top: 1px solid #e0e0e0;
    }

    .slack-oidc-toggle-section .options-header {
      margin-bottom: 12px;
    }

    .google-oauth-toggle-section {
      margin-top: 24px;
      padding-top: 24px;
      border-top: 1px solid #e0e0e0;
    }

    .google-oauth-toggle-section .options-header {
      margin-bottom: 12px;
    }

    .icon-plus {
      font-size: 16px;
      color: #666;
      font-weight: 500;
    }

    .recommended-badge {
      display: inline-block;
      background: linear-gradient(135deg, #4caf50, #2e7d32);
      color: white;
      font-size: 10px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-left: 8px;
    }

    .option-desc {
      display: block;
      margin-top: 4px;
    }

    .disabled-hint {
      color: #999 !important;
      font-style: italic;
    }

    .registration-options {
      background: #f8f9fa;
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
    }

    .options-header {
      margin: 0 0 16px 0;
      font-size: 15px;
      font-weight: 500;
      color: #333;
    }

    .app-name-section {
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid #e0e0e0;
    }

    /* Auth info grid for the info card */
    .auth-info-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 24px;
    }

    .auth-info-item {
      padding: 16px;
      background: #f8f9fa;
      border-radius: 8px;
    }

    .auth-info-item h4 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 12px 0;
      font-size: 15px;
      font-weight: 600;
      color: #333;
    }

    .auth-info-item h4 mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
      color: #3f51b5;
    }

    .auth-info-item ul {
      margin: 0;
      padding-left: 20px;
    }

    .auth-info-item li {
      font-size: 13px;
      color: #666;
      margin-bottom: 6px;
      line-height: 1.4;
    }

    /* Default space chip */
    .default-chip {
      background-color: #e3f2fd !important;
      color: #1565c0 !important;
      font-size: 11px;
      height: 20px;
      line-height: 20px;
      margin-left: 8px;
    }

    /* Role request styles */
    .user-info {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .user-info strong {
      font-size: 14px;
      color: #333;
    }

    .email-text {
      font-size: 12px;
      color: #666;
    }

    .reason-cell {
      max-width: 300px;
      white-space: normal;
      line-height: 1.4;
      font-size: 13px;
      color: #555;
    }

    /* Slack Integration Styles */
    .loading-spinner {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    /* Slack connected state styling */
    .slack-connected-card {
      border: 2px solid #4caf50 !important;
    }

    .slack-connected-title {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #2e7d32 !important;
    }

    .slack-connected-icon {
      color: #4caf50 !important;
      font-size: 28px;
      height: 28px;
      width: 28px;
    }

    .slack-status {
      margin-bottom: 24px;
      padding: 16px;
      background: #e8f5e9;
      border-radius: 8px;
      border-left: 4px solid #4caf50;
    }

    .slack-status p {
      margin: 8px 0;
      font-size: 14px;
    }

    .slack-form {
      margin-top: 16px;
    }

    .slack-form .toggle-group {
      margin: 16px 0;
    }

    .slack-form .toggle-group.nested {
      margin-left: 24px;
    }

    .slack-form .toggle-group.disabled {
      opacity: 0.5;
    }

    .slack-connect-options {
      margin-top: 24px;
    }

    .slack-connect-options .connect-option {
      padding: 16px 0;
    }

    .slack-connect-options .connect-option h4 {
      margin: 0 0 8px 0;
      font-size: 16px;
      font-weight: 500;
    }

    .slack-connect-options .connect-option p {
      margin: 0 0 12px 0;
      color: #666;
    }

    .slack-connect-options mat-divider {
      margin: 16px 0;
    }

    .slack-install-guidance {
      background: #f5f5f5;
      border-radius: 8px;
      padding: 16px;
      margin: 16px 0;
    }

    .slack-install-guidance h5 {
      margin: 0 0 12px 0;
      font-size: 14px;
      font-weight: 500;
      color: #333;
    }

    .slack-install-guidance ol {
      margin: 0;
      padding-left: 20px;
    }

    .slack-install-guidance li {
      margin: 6px 0;
      font-size: 13px;
      color: #666;
    }

    .slack-install-note {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 12px;
      font-size: 13px;
      color: #666;
    }

    .slack-install-note mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #ff9800;
    }

    .claim-form {
      display: flex;
      gap: 12px;
      align-items: flex-start;
      flex-wrap: wrap;
    }

    .claim-form mat-form-field {
      flex: 1;
      min-width: 200px;
    }

    .claim-form button {
      margin-top: 6px;
    }

    .note {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      margin-top: 16px;
      padding: 12px;
      background: #e3f2fd;
      border-radius: 8px;
      font-size: 13px;
      color: #1565c0;
    }

    .note mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    mat-card-actions {
      display: flex;
      gap: 12px;
      padding: 16px !important;
    }

    code {
      background: #e8e8e8;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 13px;
    }

    /* Responsive adjustments */
    @media (max-width: 768px) {
      .auth-info-grid {
        grid-template-columns: 1fr;
      }

      .form-row {
        flex-direction: column;
      }

      .form-row mat-form-field.small {
        flex: 1;
      }

      .option-content {
        flex-direction: column;
      }

      .option-icons {
        margin-bottom: 8px;
      }

      mat-card-actions {
        flex-wrap: wrap;
      }
    }
  `]
})
export class SettingsComponent implements OnInit {
  ssoForm: FormGroup;
  emailForm: FormGroup;
  authConfigForm: FormGroup;
  ssoConfigs: SSOConfig[] = [];
  users: User[] = [];
  authConfig: AuthConfig | null = null;
  accessRequests: AccessRequest[] = [];
  roleRequests: RoleRequest[] = [];
  ssoColumns = ['domain', 'provider_name', 'enabled', 'actions'];
  userColumns = ['name', 'email', 'domain', 'auth_type', 'role', 'last_login', 'actions'];
  accessRequestColumns = ['name', 'email', 'reason', 'created_at', 'status', 'actions'];
  roleRequestColumns = ['user', 'requested_role', 'reason', 'created_at', 'status', 'actions'];
  spaceColumns = ['name', 'description', 'decision_count', 'actions'];

  // Spaces
  spaceForm: FormGroup;
  spaces: Space[] = [];
  editingSpaceId: number | null = null;
  savingSpace = false;
  loadingSpaces = false;

  editingSSOId: number | null = null;
  hasExistingEmailConfig = false;
  hasSSOConfigForDomain = false;
  savingSSOConfig = false;
  savingEmailConfig = false;
  savingAuthConfig = false;
  testingEmail = false;
  loadingRequests = false;
  loadingRoleRequests = false;
  processingRequest: number | null = null;
  processingRoleRequest: number | null = null;
  pendingRequestsCount = 0;
  pendingRoleRequestsCount = 0;

  // Slack Integration
  slackForm: FormGroup;
  slackSettings: SlackSettings | null = null;
  slackChannels: SlackChannel[] = [];
  loadingSlackSettings = false;
  savingSlackSettings = false;
  testingSlack = false;
  slackClaimWorkspaceId = '';
  claimingSlackWorkspace = false;

  // Feature flags
  slackFeatureEnabled = false;
  slackOidcGloballyEnabled = false;  // Global Slack OIDC sign-in availability
  googleOauthGloballyEnabled = false;  // Global Google OAuth sign-in availability

  // Tab index for navigation
  selectedTabIndex = 0;
  // Tab map matches actual tab order in template:
  // 0: SSO, 1: Email, 2: Users, 3: Auth, 4: Spaces*, 5: Access Requests*, 6: Role Requests*, 7: Slack*
  // (*) = conditional tabs for non-master accounts
  private tabMap: { [key: string]: number } = {
    'sso': 0,
    'email': 1,
    'users': 2,
    'auth': 3,
    'spaces': 4,
    'access-requests': 5,
    'role-requests': 6,
    'slack': 7
  };

  /**
   * Check if current user is a provisional admin
   */
  get isProvisionalAdmin(): boolean {
    const user = this.authService.currentUser?.user as User | undefined;
    return user?.global_role === 'provisional_admin';
  }

  /**
   * Check if registration toggle is restricted (provisional admin trying to disable registration)
   */
  get isRegistrationToggleRestricted(): boolean {
    return this.isProvisionalAdmin;
  }

  /**
   * Check if approval toggle is restricted (provisional admin trying to require approval)
   */
  get isApprovalToggleRestricted(): boolean {
    return this.isProvisionalAdmin;
  }

  /**
   * Get role badge for a user
   */
  getUserRoleBadge(role: GlobalRole | undefined): RoleBadge {
    return getRoleBadge(role);
  }

  /**
   * Get role chip CSS class for role requests
   */
  getRoleChipClass(role: string): string {
    if (role === 'admin') {
      return 'role-admin';
    } else if (role === 'steward') {
      return 'role-steward';
    }
    return '';
  }

  constructor(
    private fb: FormBuilder,
    private adminService: AdminService,
    public authService: AuthService,
    private spaceService: SpaceService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog,
    private http: HttpClient,
    private route: ActivatedRoute
  ) {
    this.spaceForm = this.fb.group({
      name: ['', Validators.required],
      description: [''],
      is_default: [false]
    });

    this.ssoForm = this.fb.group({
      domain: ['', Validators.required],
      provider_name: ['', Validators.required],
      client_id: ['', Validators.required],
      client_secret: [''],
      discovery_url: ['', Validators.required],
      enabled: [true]
    });

    this.emailForm = this.fb.group({
      smtp_server: ['', Validators.required],
      smtp_port: [587, Validators.required],
      smtp_username: ['', Validators.required],
      smtp_password: [''],
      from_email: ['', [Validators.required, Validators.email]],
      from_name: ['Architecture Decisions'],
      use_tls: [true],
      enabled: [true]
    });

    this.authConfigForm = this.fb.group({
      auth_method: ['both', Validators.required],  // 'both', 'webauthn', 'sso', or 'slack_oidc'
      allow_registration: [true],
      auto_approve_users: [false],  // Inverted from require_approval for better UX
      allow_slack_oidc: [true],     // Allow Slack OIDC sign-in for tenant
      allow_google_oauth: [true],   // Allow Google OAuth sign-in for tenant
      rp_name: ['Architecture Decisions']
    });

    this.slackForm = this.fb.group({
      default_channel_id: [''],
      notifications_enabled: [true],
      notify_on_create: [true],
      notify_on_status_change: [true]
    });
  }

  ngOnInit(): void {
    this.loadFeatureFlags();
    this.loadSSOConfigs();
    this.loadEmailConfig();
    this.loadUsers();
    this.loadAuthConfig();
    this.checkSlackOidcStatus();
    this.checkGoogleOauthStatus();
    if (!this.authService.isMasterAccount) {
      this.loadAccessRequests();
      this.loadRoleRequests();
      this.loadSpaces();
      this.loadSlackSettings();
      // Pre-fill domain for tenant admins
      if (this.authService.currentUser?.user) {
        const user = this.authService.currentUser.user as User;
        if (user.sso_domain) {
          this.ssoForm.patchValue({ domain: user.sso_domain });
        }
      }
    }

    // Handle query params for tab navigation and success messages
    this.route.queryParams.subscribe(params => {
      const tab = params['tab'];
      if (tab && this.tabMap[tab] !== undefined) {
        this.selectedTabIndex = this.tabMap[tab];
      }

      if (params['slack_success'] === 'true') {
        this.snackBar.open('Slack connected successfully!', 'Close', { duration: 5000 });
        // Reload Slack settings to show the connected state
        this.loadSlackSettings();
      }

      // Handle Slack error messages
      const slackError = params['slack_error'];
      if (slackError) {
        let errorMessage = 'Failed to connect Slack workspace.';

        if (slackError.startsWith('domain_mismatch')) {
          // Parse domain mismatch error
          const workspaceDomain = params['workspace_domain'];
          const tenantDomain = params['tenant_domain'];
          errorMessage = `Domain mismatch: The Slack workspace uses email domain "${workspaceDomain}" but your organization is "${tenantDomain}". You can only connect Slack workspaces where members use your organization's email domain.`;
        } else if (slackError === 'workspace_claimed_by_other') {
          errorMessage = 'This Slack workspace is already connected to another organization.';
        } else if (slackError === 'oauth_failed') {
          errorMessage = 'Slack authorization failed. Please try again.';
        } else if (slackError === 'invalid_state') {
          errorMessage = 'Authorization session expired. Please try again.';
        } else if (slackError === 'not_configured') {
          errorMessage = 'Slack integration is not configured. Please contact support.';
        } else if (slackError === 'missing_code') {
          errorMessage = 'Slack did not return an authorization code. Please try again.';
        }

        this.snackBar.open(errorMessage, 'Close', { duration: 10000, panelClass: ['error-snackbar'] });
      }
    });
  }

  loadFeatureFlags(): void {
    this.http.get<{ commercial: boolean; slack: boolean }>('/api/features').subscribe({
      next: (features) => {
        this.slackFeatureEnabled = features.slack;
      },
      error: () => {
        // Default to disabled if can't load features
        this.slackFeatureEnabled = false;
      }
    });
  }

  checkSlackOidcStatus(): void {
    this.http.get<{ enabled: boolean }>('/api/auth/slack-oidc-status').subscribe({
      next: (response) => {
        this.slackOidcGloballyEnabled = response.enabled;
      },
      error: () => {
        this.slackOidcGloballyEnabled = false;
      }
    });
  }

  checkGoogleOauthStatus(): void {
    this.http.get<{ enabled: boolean }>('/api/auth/google-status').subscribe({
      next: (response) => {
        this.googleOauthGloballyEnabled = response.enabled;
      },
      error: () => {
        this.googleOauthGloballyEnabled = false;
      }
    });
  }

  loadSSOConfigs(): void {
    this.adminService.getSSOConfigs().subscribe({
      next: (configs) => {
        this.ssoConfigs = configs;
        // Check if there's an SSO config for the current user's domain
        if (!this.authService.isMasterAccount && this.authService.currentUser) {
          const user = this.authService.currentUser.user as User;
          this.hasSSOConfigForDomain = configs.some(c => c.domain === user.sso_domain && c.enabled);
        }
      },
      error: () => this.snackBar.open('Failed to load SSO configs', 'Close', { duration: 3000 })
    });
  }

  loadEmailConfig(): void {
    this.adminService.getEmailConfig().subscribe({
      next: (config) => {
        if (config) {
          this.hasExistingEmailConfig = true;
          this.emailForm.patchValue({
            smtp_server: config.smtp_server,
            smtp_port: config.smtp_port,
            smtp_username: config.smtp_username,
            from_email: config.from_email,
            from_name: config.from_name,
            use_tls: config.use_tls,
            enabled: config.enabled
          });
        }
      }
    });
  }

  loadUsers(): void {
    this.adminService.getUsers().subscribe({
      next: (users) => this.users = users,
      error: () => this.snackBar.open('Failed to load users', 'Close', { duration: 3000 })
    });
  }

  saveSSOConfig(): void {
    if (this.ssoForm.invalid) return;

    this.savingSSOConfig = true;
    const formValue = this.ssoForm.value;

    if (this.editingSSOId) {
      this.adminService.updateSSOConfig(this.editingSSOId, formValue).subscribe({
        next: () => {
          this.snackBar.open('SSO config updated', 'Close', { duration: 3000 });
          this.loadSSOConfigs();
          this.cancelSSOEdit();
          this.savingSSOConfig = false;
        },
        error: (err) => {
          this.snackBar.open(err.error?.error || 'Failed to update', 'Close', { duration: 3000 });
          this.savingSSOConfig = false;
        }
      });
    } else {
      const config: CreateSSOConfigRequest = {
        domain: formValue.domain,
        provider_name: formValue.provider_name,
        client_id: formValue.client_id,
        client_secret: formValue.client_secret,
        discovery_url: formValue.discovery_url,
        enabled: formValue.enabled
      };

      this.adminService.createSSOConfig(config).subscribe({
        next: () => {
          this.snackBar.open('SSO config created', 'Close', { duration: 3000 });
          this.loadSSOConfigs();
          this.ssoForm.reset({ enabled: true });
          this.savingSSOConfig = false;
        },
        error: (err) => {
          this.snackBar.open(err.error?.error || 'Failed to create', 'Close', { duration: 3000 });
          this.savingSSOConfig = false;
        }
      });
    }
  }

  editSSOConfig(config: SSOConfig): void {
    this.editingSSOId = config.id;
    this.ssoForm.patchValue({
      domain: config.domain,
      provider_name: config.provider_name,
      client_id: config.client_id,
      client_secret: '',
      discovery_url: config.discovery_url,
      enabled: config.enabled
    });
  }

  cancelSSOEdit(): void {
    this.editingSSOId = null;
    this.ssoForm.reset({ enabled: true });
  }

  deleteSSOConfig(config: SSOConfig): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete SSO Provider',
        message: `Are you sure you want to delete the SSO provider for ${config.domain}?`,
        confirmText: 'Delete',
        isDanger: true
      }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.adminService.deleteSSOConfig(config.id).subscribe({
          next: () => {
            this.snackBar.open('SSO config deleted', 'Close', { duration: 3000 });
            this.loadSSOConfigs();
          },
          error: () => this.snackBar.open('Failed to delete', 'Close', { duration: 3000 })
        });
      }
    });
  }

  saveEmailConfig(): void {
    if (this.emailForm.invalid) return;

    this.savingEmailConfig = true;
    const formValue = this.emailForm.value;

    const config: EmailConfigRequest = {
      smtp_server: formValue.smtp_server,
      smtp_port: formValue.smtp_port,
      smtp_username: formValue.smtp_username,
      from_email: formValue.from_email,
      from_name: formValue.from_name,
      use_tls: formValue.use_tls,
      enabled: formValue.enabled
    };

    if (formValue.smtp_password) {
      config.smtp_password = formValue.smtp_password;
    }

    this.adminService.saveEmailConfig(config).subscribe({
      next: () => {
        this.hasExistingEmailConfig = true;
        this.snackBar.open('Email config saved', 'Close', { duration: 3000 });
        this.savingEmailConfig = false;
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to save', 'Close', { duration: 3000 });
        this.savingEmailConfig = false;
      }
    });
  }

  testEmail(): void {
    this.testingEmail = true;
    this.adminService.testEmail().subscribe({
      next: () => {
        this.snackBar.open('Test email sent', 'Close', { duration: 3000 });
        this.testingEmail = false;
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to send test email', 'Close', { duration: 3000 });
        this.testingEmail = false;
      }
    });
  }

  toggleAdmin(user: User, isAdmin: boolean): void {
    this.adminService.toggleUserAdmin(user.id, isAdmin).subscribe({
      next: (updated) => {
        user.is_admin = updated.is_admin;
        this.snackBar.open(`${user.name || user.email} admin status updated`, 'Close', { duration: 3000 });
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to update', 'Close', { duration: 3000 });
      }
    });
  }

  loadAuthConfig(): void {
    this.adminService.getAuthConfig().subscribe({
      next: (config) => {
        // Master account gets array, regular admin gets single config
        if (Array.isArray(config)) {
          // For master account, just use first config or defaults
          if (config.length > 0) {
            this.authConfig = config[0];
          }
        } else {
          this.authConfig = config;
        }

        if (this.authConfig) {
          // Convert from backend model to simplified UI model
          let uiAuthMethod = 'both';  // default
          if (this.authConfig.auth_method === 'slack_oidc') {
            uiAuthMethod = 'slack_oidc';
          } else if (this.authConfig.auth_method === 'sso') {
            uiAuthMethod = 'sso';
          } else if (this.authConfig.allow_passkey && !this.authConfig.allow_password) {
            uiAuthMethod = 'webauthn';  // passkey only
          } else {
            uiAuthMethod = 'both';  // passkey + password
          }

          this.authConfigForm.patchValue({
            auth_method: uiAuthMethod,
            allow_registration: this.authConfig.allow_registration,
            auto_approve_users: !this.authConfig.require_approval,  // Invert for UI
            allow_slack_oidc: this.authConfig.allow_slack_oidc !== false,  // Default true if undefined
            allow_google_oauth: this.authConfig.allow_google_oauth !== false,  // Default true if undefined
            rp_name: this.authConfig.rp_name
          });
        }
      },
      error: () => {
        // Use defaults if no config exists
        this.authConfigForm.patchValue({
          auto_approve_users: false,  // Default to requiring approval
          auth_method: 'webauthn',
          allow_registration: true,
          allow_google_oauth: true,  // Default true
          rp_name: 'Architecture Decisions'
        });
      }
    });
  }

  saveAuthConfig(): void {
    if (this.authConfigForm.invalid) return;

    this.savingAuthConfig = true;
    const formValue = this.authConfigForm.value;

    // Convert from simplified UI model to backend model
    let backendAuthMethod: string = 'webauthn';
    let allowPassword = true;
    let allowPasskey = true;
    let allowSlackOidc = formValue.allow_slack_oidc;
    let allowGoogleOauth = formValue.allow_google_oauth;

    switch (formValue.auth_method) {
      case 'both':
        backendAuthMethod = 'webauthn';
        allowPassword = true;
        allowPasskey = true;
        break;
      case 'webauthn':
        backendAuthMethod = 'webauthn';
        allowPassword = false;
        allowPasskey = true;
        break;
      case 'sso':
        backendAuthMethod = 'sso';
        allowPassword = false;
        allowPasskey = false;
        allowSlackOidc = false;  // SSO mode disables Slack OIDC
        allowGoogleOauth = false;  // SSO mode disables Google OAuth
        break;
      case 'slack_oidc':
        backendAuthMethod = 'slack_oidc';
        allowPassword = false;
        allowPasskey = false;
        allowSlackOidc = true;  // Slack-only mode
        break;
    }

    const config: AuthConfigRequest = {
      auth_method: backendAuthMethod,
      allow_registration: formValue.allow_registration,
      require_approval: !formValue.auto_approve_users,  // Invert for API
      rp_name: formValue.rp_name,
      allow_password: allowPassword,
      allow_passkey: allowPasskey,
      allow_slack_oidc: allowSlackOidc,
      allow_google_oauth: allowGoogleOauth
    };

    this.adminService.saveAuthConfig(config).subscribe({
      next: (savedConfig) => {
        this.authConfig = savedConfig;
        this.savingAuthConfig = false;
        this.snackBar.open('Authentication configuration saved', 'Close', { duration: 3000 });
      },
      error: (err) => {
        this.savingAuthConfig = false;
        this.snackBar.open(err.error?.error || 'Failed to save configuration', 'Close', { duration: 3000 });
      }
    });
  }

  loadAccessRequests(): void {
    this.loadingRequests = true;
    this.adminService.getAccessRequests().subscribe({
      next: (requests) => {
        this.accessRequests = requests;
        this.pendingRequestsCount = requests.filter(r => r.status === 'pending').length;
        this.loadingRequests = false;
      },
      error: () => {
        this.snackBar.open('Failed to load access requests', 'Close', { duration: 3000 });
        this.loadingRequests = false;
      }
    });
  }

  approveRequest(request: AccessRequest): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Approve Access Request',
        message: `Are you sure you want to approve access for ${request.name} (${request.email})? This will create a new user account.`,
        confirmText: 'Approve'
      }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.processingRequest = request.id;
        this.adminService.approveAccessRequest(request.id).subscribe({
          next: (response: any) => {
            this.loadAccessRequests();
            this.loadUsers();
            this.processingRequest = null;

            // Show the setup link dialog if a setup URL was generated
            if (response.setup_url) {
              this.dialog.open(SetupLinkDialogComponent, {
                data: {
                  userId: response.user?.id,
                  userName: request.name,
                  userEmail: request.email,
                  setupUrl: response.setup_url,
                  expiresInHours: response.token_expires_in_hours || 48
                },
                width: '500px'
              });
            } else {
              this.snackBar.open(`Access approved for ${request.email}`, 'Close', { duration: 3000 });
            }
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to approve request', 'Close', { duration: 3000 });
            this.processingRequest = null;
          }
        });
      }
    });
  }

  generateSetupLink(user: User): void {
    this.adminService.generateSetupLink(user.id).subscribe({
      next: (response: any) => {
        this.dialog.open(SetupLinkDialogComponent, {
          data: {
            userId: user.id,
            userName: user.name || user.email,
            userEmail: user.email,
            setupUrl: response.setup_url,
            expiresInHours: response.hours_valid || 48
          },
          width: '500px'
        });
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to generate setup link', 'Close', { duration: 3000 });
      }
    });
  }

  getCurrentDomain(): string {
    if (this.authService.currentUser?.user) {
      const user = this.authService.currentUser.user as User;
      return user.sso_domain || '';
    }
    return '';
  }

  rejectRequest(request: AccessRequest): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Reject Access Request',
        message: `Are you sure you want to reject access for ${request.name} (${request.email})?`,
        confirmText: 'Reject',
        isDanger: true
      }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.processingRequest = request.id;
        this.adminService.rejectAccessRequest(request.id).subscribe({
          next: () => {
            this.snackBar.open(`Access request rejected`, 'Close', { duration: 3000 });
            this.loadAccessRequests();
            this.processingRequest = null;
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to reject request', 'Close', { duration: 3000 });
            this.processingRequest = null;
          }
        });
      }
    });
  }

  // Spaces Management
  loadSpaces(): void {
    this.loadingSpaces = true;
    this.spaceService.getSpaces().subscribe({
      next: (spaces) => {
        this.spaces = spaces;
        this.loadingSpaces = false;
      },
      error: () => {
        this.snackBar.open('Failed to load spaces', 'Close', { duration: 3000 });
        this.loadingSpaces = false;
      }
    });
  }

  saveSpace(): void {
    if (this.spaceForm.invalid) return;

    this.savingSpace = true;
    const formValue = this.spaceForm.value;

    if (this.editingSpaceId) {
      this.spaceService.updateSpace(this.editingSpaceId, formValue).subscribe({
        next: () => {
          this.snackBar.open('Space updated', 'Close', { duration: 3000 });
          this.loadSpaces();
          this.cancelSpaceEdit();
          this.savingSpace = false;
        },
        error: (err) => {
          this.snackBar.open(err.error?.error || 'Failed to update space', 'Close', { duration: 3000 });
          this.savingSpace = false;
        }
      });
    } else {
      this.spaceService.createSpace(formValue).subscribe({
        next: () => {
          this.snackBar.open('Space created', 'Close', { duration: 3000 });
          this.loadSpaces();
          this.spaceForm.reset({ is_default: false });
          this.savingSpace = false;
        },
        error: (err) => {
          this.snackBar.open(err.error?.error || 'Failed to create space', 'Close', { duration: 3000 });
          this.savingSpace = false;
        }
      });
    }
  }

  editSpace(space: Space): void {
    this.editingSpaceId = space.id;
    this.spaceForm.patchValue({
      name: space.name,
      description: space.description || '',
      is_default: space.is_default
    });
  }

  cancelSpaceEdit(): void {
    this.editingSpaceId = null;
    this.spaceForm.reset({ is_default: false });
  }

  isEditingDefaultSpace(): boolean {
    if (!this.editingSpaceId) return false;
    const space = this.spaces.find(s => s.id === this.editingSpaceId);
    return space?.is_default || false;
  }

  deleteSpace(space: Space): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete Space',
        message: `Are you sure you want to delete the space "${space.name}"? Decisions in this space will be unassigned from it.`,
        confirmText: 'Delete',
        isDanger: true
      }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.spaceService.deleteSpace(space.id).subscribe({
          next: () => {
            this.snackBar.open('Space deleted', 'Close', { duration: 3000 });
            this.loadSpaces();
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to delete space', 'Close', { duration: 3000 });
          }
        });
      }
    });
  }

  // Role Requests Management
  loadRoleRequests(): void {
    this.loadingRoleRequests = true;
    this.adminService.getRoleRequests().subscribe({
      next: (requests) => {
        this.roleRequests = requests;
        this.pendingRoleRequestsCount = requests.filter(r => r.status === 'pending').length;
        this.loadingRoleRequests = false;
      },
      error: () => {
        this.snackBar.open('Failed to load role requests', 'Close', { duration: 3000 });
        this.loadingRoleRequests = false;
      }
    });
  }

  approveRoleRequest(request: RoleRequest): void {
    const roleLabel = request.requested_role === 'admin' ? 'Administrator' : 'Steward';
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Approve Role Request',
        message: `Are you sure you want to grant ${roleLabel} privileges to ${request.user?.name || request.user?.email}?`,
        confirmText: 'Approve'
      }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.processingRoleRequest = request.id;
        this.adminService.approveRoleRequest(request.id).subscribe({
          next: () => {
            this.loadRoleRequests();
            this.loadUsers();
            this.processingRoleRequest = null;
            this.snackBar.open(`Role request approved for ${request.user?.name || request.user?.email}`, 'Close', { duration: 3000 });
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to approve request', 'Close', { duration: 3000 });
            this.processingRoleRequest = null;
          }
        });
      }
    });
  }

  rejectRoleRequest(request: RoleRequest): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Reject Role Request',
        message: `Are you sure you want to reject the role request from ${request.user?.name || request.user?.email}?`,
        confirmText: 'Reject',
        isDanger: true,
        showInput: true,
        inputLabel: 'Rejection Reason (optional)',
        inputPlaceholder: 'Explain why this request was rejected...'
      }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result && result.confirmed) {
        this.processingRoleRequest = request.id;
        this.adminService.rejectRoleRequest(request.id, result.inputValue).subscribe({
          next: () => {
            this.snackBar.open('Role request rejected', 'Close', { duration: 3000 });
            this.loadRoleRequests();
            this.processingRoleRequest = null;
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to reject request', 'Close', { duration: 3000 });
            this.processingRoleRequest = null;
          }
        });
      }
    });
  }

  // Slack Integration Methods
  loadSlackSettings(): void {
    this.loadingSlackSettings = true;
    this.adminService.getSlackSettings().subscribe({
      next: (settings) => {
        this.slackSettings = settings;
        if (settings.installed) {
          // Populate the form with existing settings
          this.slackForm.patchValue({
            default_channel_id: settings.default_channel_id || '',
            notifications_enabled: settings.notifications_enabled ?? true,
            notify_on_create: settings.notify_on_create ?? true,
            notify_on_status_change: settings.notify_on_status_change ?? true
          });
          // Load available channels
          this.loadSlackChannels();
        }
        this.loadingSlackSettings = false;
      },
      error: () => {
        this.snackBar.open('Failed to load Slack settings', 'Close', { duration: 3000 });
        this.loadingSlackSettings = false;
      }
    });
  }

  loadSlackChannels(): void {
    this.adminService.getSlackChannels().subscribe({
      next: (response) => {
        this.slackChannels = response.channels || [];
      },
      error: () => {
        // Silently fail - channels list is optional
        this.slackChannels = [];
      }
    });
  }

  saveSlackSettings(): void {
    this.savingSlackSettings = true;
    const formValue = this.slackForm.value;

    // Find the channel name if a channel is selected
    const selectedChannel = this.slackChannels.find(c => c.id === formValue.default_channel_id);

    const settings = {
      default_channel_id: formValue.default_channel_id || undefined,
      default_channel_name: selectedChannel?.name,
      notifications_enabled: formValue.notifications_enabled,
      notify_on_create: formValue.notify_on_create,
      notify_on_status_change: formValue.notify_on_status_change
    };

    this.adminService.updateSlackSettings(settings).subscribe({
      next: (response) => {
        this.slackSettings = response.settings;
        this.snackBar.open('Slack settings saved', 'Close', { duration: 3000 });
        this.savingSlackSettings = false;
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to save Slack settings', 'Close', { duration: 3000 });
        this.savingSlackSettings = false;
      }
    });
  }

  testSlackNotification(): void {
    this.testingSlack = true;
    this.adminService.testSlackNotification().subscribe({
      next: () => {
        this.snackBar.open('Test notification sent to Slack', 'Close', { duration: 3000 });
        this.testingSlack = false;
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to send test notification', 'Close', { duration: 3000 });
        this.testingSlack = false;
      }
    });
  }

  disconnectSlack(): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Disconnect Slack',
        message: `Are you sure you want to disconnect Slack from your organization? This will disable all Slack commands and notifications.`,
        confirmText: 'Disconnect',
        isDanger: true
      }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.adminService.disconnectSlack().subscribe({
          next: () => {
            this.slackSettings = { installed: false };
            this.slackChannels = [];
            this.slackForm.reset({
              default_channel_id: '',
              notifications_enabled: true,
              notify_on_create: true,
              notify_on_status_change: true
            });
            this.snackBar.open('Slack disconnected successfully', 'Close', { duration: 3000 });
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to disconnect Slack', 'Close', { duration: 3000 });
          }
        });
      }
    });
  }

  claimSlackWorkspace(): void {
    if (!this.slackClaimWorkspaceId?.trim()) {
      this.snackBar.open('Please enter a Workspace ID', 'Close', { duration: 3000 });
      return;
    }

    this.claimingSlackWorkspace = true;
    this.adminService.claimSlackWorkspace(this.slackClaimWorkspaceId.trim()).subscribe({
      next: (response) => {
        this.snackBar.open(response.message || 'Workspace claimed successfully', 'Close', { duration: 5000 });
        this.slackClaimWorkspaceId = '';
        this.claimingSlackWorkspace = false;
        // Reload slack settings to show the connected state
        this.loadSlackSettings();
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to claim workspace', 'Close', { duration: 5000 });
        this.claimingSlackWorkspace = false;
      }
    });
  }
}
