import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
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
import { AdminService, CreateSSOConfigRequest, EmailConfigRequest, AuthConfigRequest } from '../../services/admin.service';
import { AuthService } from '../../services/auth.service';
import { SSOConfig, EmailConfig, User, AuthConfig, AccessRequest } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';
import { SetupLinkDialogComponent } from '../shared/setup-link-dialog.component';
import { MatSelectModule } from '@angular/material/select';
import { MatRadioModule } from '@angular/material/radio';
import { MatTooltipModule } from '@angular/material/tooltip';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
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

      <mat-tab-group>
        <!-- SSO Configuration Tab -->
        <mat-tab label="SSO Providers">
          <div class="tab-content">
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
                    <button mat-raised-button color="primary" type="submit"
                            [disabled]="ssoForm.invalid || savingSSOConfig">
                      <mat-spinner diameter="20" *ngIf="savingSSOConfig"></mat-spinner>
                      <mat-icon *ngIf="!savingSSOConfig">save</mat-icon>
                      <span *ngIf="!savingSSOConfig">{{ editingSSOId ? 'Update' : 'Add Provider' }}</span>
                    </button>
                    @if (editingSSOId) {
                      <button mat-button type="button" (click)="cancelSSOEdit()">Cancel</button>
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
                    <button mat-raised-button color="primary" type="submit"
                            [disabled]="emailForm.invalid || savingEmailConfig">
                      <mat-spinner diameter="20" *ngIf="savingEmailConfig"></mat-spinner>
                      <mat-icon *ngIf="!savingEmailConfig">save</mat-icon>
                      <span *ngIf="!savingEmailConfig">Save Configuration</span>
                    </button>
                    <button mat-button type="button" (click)="testEmail()"
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
                  <table mat-table [dataSource]="users" class="full-width">
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

                    <ng-container matColumnDef="is_admin">
                      <th mat-header-cell *matHeaderCellDef>Admin</th>
                      <td mat-cell *matCellDef="let user">
                        <mat-slide-toggle [checked]="user.is_admin"
                                          (change)="toggleAdmin(user, $event.checked)">
                        </mat-slide-toggle>
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
                  <div class="auth-method-options">
                    <mat-radio-group formControlName="auth_method" class="auth-method-group">
                      <mat-radio-button value="both" class="auth-method-option">
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

                      <mat-radio-button value="webauthn" class="auth-method-option">
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
                                        [disabled]="!hasSSOConfigForDomain">
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
                    </mat-radio-group>
                  </div>

                  <div class="registration-options" *ngIf="authConfigForm.value.auth_method !== 'sso'">
                      <h4 class="options-header">User Registration</h4>

                      <mat-slide-toggle formControlName="allow_registration">
                        Allow new user registration
                      </mat-slide-toggle>
                      <p class="option-hint">
                        When enabled, new users can create accounts. When disabled, only existing users can sign in.
                      </p>

                      <div class="approval-toggle-section" *ngIf="authConfigForm.value.allow_registration">
                          <mat-slide-toggle formControlName="auto_approve_users">
                            Auto-approve new users from your domain
                          </mat-slide-toggle>
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
                          <input matInput formControlName="rp_name" placeholder="Architecture Decisions">
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

    .tab-content {
      padding: 24px 0;
    }

    .form-card, .list-card {
      margin-bottom: 24px;
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
      gap: 16px;
      margin-top: 24px;
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

    .info-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .info-card h4 {
      margin: 16px 0 8px 0;
      color: #333;
    }

    .info-card ul {
      margin: 0;
      padding-left: 20px;
      color: #666;
    }

    .info-card li {
      margin-bottom: 4px;
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
  ssoColumns = ['domain', 'provider_name', 'enabled', 'actions'];
  userColumns = ['name', 'email', 'domain', 'auth_type', 'is_admin', 'last_login', 'actions'];
  accessRequestColumns = ['name', 'email', 'reason', 'created_at', 'status', 'actions'];

  editingSSOId: number | null = null;
  hasExistingEmailConfig = false;
  hasSSOConfigForDomain = false;
  savingSSOConfig = false;
  savingEmailConfig = false;
  savingAuthConfig = false;
  testingEmail = false;
  loadingRequests = false;
  processingRequest: number | null = null;
  pendingRequestsCount = 0;

  constructor(
    private fb: FormBuilder,
    private adminService: AdminService,
    public authService: AuthService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {
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
      auth_method: ['both', Validators.required],  // 'both', 'webauthn', or 'sso'
      allow_registration: [true],
      auto_approve_users: [false],  // Inverted from require_approval for better UX
      rp_name: ['Architecture Decisions']
    });
  }

  ngOnInit(): void {
    this.loadSSOConfigs();
    this.loadEmailConfig();
    this.loadUsers();
    this.loadAuthConfig();
    if (!this.authService.isMasterAccount) {
      this.loadAccessRequests();
      // Pre-fill domain for tenant admins
      if (this.authService.currentUser?.user) {
        const user = this.authService.currentUser.user as User;
        if (user.sso_domain) {
          this.ssoForm.patchValue({ domain: user.sso_domain });
        }
      }
    }
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
          if (this.authConfig.auth_method === 'sso') {
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
    let backendAuthMethod: 'sso' | 'webauthn' = 'webauthn';
    let allowPassword = true;
    let allowPasskey = true;

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
        break;
    }

    const config: AuthConfigRequest = {
      auth_method: backendAuthMethod,
      allow_registration: formValue.allow_registration,
      require_approval: !formValue.auto_approve_users,  // Invert for API
      rp_name: formValue.rp_name,
      allow_password: allowPassword,
      allow_passkey: allowPasskey
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
}
