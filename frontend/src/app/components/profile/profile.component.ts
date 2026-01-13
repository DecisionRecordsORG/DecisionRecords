import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDividerModule } from '@angular/material/divider';
import { MatListModule } from '@angular/material/list';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { Clipboard, ClipboardModule } from '@angular/cdk/clipboard';
import { AuthService } from '../../services/auth.service';
import { WebAuthnService } from '../../services/webauthn.service';
import { AdminService } from '../../services/admin.service';
import { Subscription, User, WebAuthnCredential, GlobalRole } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';
import { RoleRequestDialogComponent } from '../shared/role-request-dialog.component';

// API Key interface
interface AIApiKey {
  id: number;
  name: string;
  key_prefix: string;
  scopes: string[];
  created_at: string;
  expires_at?: string;
  last_used_at?: string;
  is_revoked: boolean;
  is_expired: boolean;
}

// Password policy constants
const PASSWORD_MIN_LENGTH = 8;
const PASSWORD_REQUIRES_UPPERCASE = true;
const PASSWORD_REQUIRES_LOWERCASE = true;
const PASSWORD_REQUIRES_NUMBER = true;

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    MatCardModule,
    MatSlideToggleModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDividerModule,
    MatListModule,
    MatChipsModule,
    MatDialogModule,
    MatTooltipModule,
    MatFormFieldModule,
    MatInputModule,
    MatCheckboxModule,
    ClipboardModule,
    RoleRequestDialogComponent,
    RouterLink
  ],
  template: `
    <div class="profile-container">
      @if (setupMode) {
        <div class="setup-banner">
          <mat-icon>key</mat-icon>
          <div>
            <h2>Complete Your Account Setup</h2>
            <p>Set up a passkey or password to secure your account</p>
          </div>
        </div>

        <!-- Credential Setup Card (only in setup mode) -->
        <mat-card class="setup-card">
          <mat-card-header>
            <mat-card-title>Choose Your Authentication Method</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            @if (checkingPasskeySupport) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
                <p>Checking device capabilities...</p>
              </div>
            } @else {
              <div class="auth-options">
                <!-- Passkey Option -->
                <div class="auth-option" [class.recommended]="passkeyAvailable">
                  <div class="option-header">
                    <mat-icon>fingerprint</mat-icon>
                    <div>
                      <h3>Passkey</h3>
                      @if (passkeyAvailable) {
                        <span class="recommended-badge">Recommended</span>
                      }
                    </div>
                  </div>
                  <p class="option-description">
                    Use Face ID, Touch ID, or Windows Hello for secure, passwordless login.
                    Passkeys are phishing-resistant and more secure than passwords.
                  </p>
                  @if (passkeyAvailable) {
                    <button mat-raised-button color="primary" (click)="setupPasskey()"
                            [disabled]="isSettingUpCredential">
                      <mat-spinner diameter="20" *ngIf="isSettingUpCredential && setupMethod === 'passkey'"></mat-spinner>
                      <mat-icon *ngIf="!(isSettingUpCredential && setupMethod === 'passkey')">fingerprint</mat-icon>
                      <span *ngIf="!(isSettingUpCredential && setupMethod === 'passkey')">Set up Passkey</span>
                    </button>
                  } @else {
                    <p class="not-available">
                      <mat-icon>info</mat-icon>
                      Passkeys are not available on this device. Please use a password instead.
                    </p>
                  }
                  @if (passkeyError) {
                    <p class="error-message">{{ passkeyError }}</p>
                  }
                </div>

                <mat-divider></mat-divider>

                <!-- Password Option -->
                <div class="auth-option">
                  <div class="option-header">
                    <mat-icon>lock</mat-icon>
                    <h3>Password</h3>
                  </div>
                  <p class="option-description">
                    Create a strong password. You can add a passkey later for easier login.
                  </p>
                  <form [formGroup]="passwordForm" (ngSubmit)="setupPassword()">
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Password</mat-label>
                      <input matInput type="password" formControlName="password">
                      @if (passwordForm.get('password')?.hasError('required') && passwordForm.get('password')?.touched) {
                        <mat-error>Password is required</mat-error>
                      }
                      @if (passwordForm.get('password')?.hasError('minlength')) {
                        <mat-error>Password must be at least 8 characters</mat-error>
                      }
                      @if (passwordForm.get('password')?.hasError('pattern')) {
                        <mat-error>Password must contain uppercase, lowercase, and a number</mat-error>
                      }
                    </mat-form-field>
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Confirm Password</mat-label>
                      <input matInput type="password" formControlName="confirmPassword">
                      @if (passwordForm.get('confirmPassword')?.hasError('passwordMismatch')) {
                        <mat-error>Passwords do not match</mat-error>
                      }
                    </mat-form-field>
                    <p class="password-requirements">
                      <strong>Password requirements:</strong> At least 8 characters, including uppercase, lowercase, and a number.
                    </p>
                    <button mat-raised-button color="accent" type="submit"
                            [disabled]="passwordForm.invalid || isSettingUpCredential">
                      <mat-spinner diameter="20" *ngIf="isSettingUpCredential && setupMethod === 'password'"></mat-spinner>
                      <mat-icon *ngIf="!(isSettingUpCredential && setupMethod === 'password')">lock</mat-icon>
                      <span *ngIf="!(isSettingUpCredential && setupMethod === 'password')">Set Password</span>
                    </button>
                  </form>
                  @if (passwordError) {
                    <p class="error-message">{{ passwordError }}</p>
                  }
                </div>
              </div>
            }
          </mat-card-content>
        </mat-card>
      } @else {
        <h1>
          <mat-icon>person</mat-icon>
          Profile & Notifications
        </h1>
      }

      @if (authService.currentUser) {
        <mat-card class="profile-card">
          <mat-card-header>
            <mat-card-title>Account Information</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <div class="info-grid">
              <div class="info-item">
                <span class="label">Name</span>
                <span class="value">{{ user?.name || 'Not set' }}</span>
              </div>
              <div class="info-item">
                <span class="label">Email</span>
                <span class="value">{{ user?.email }}</span>
              </div>
              <div class="info-item">
                <span class="label">Domain</span>
                <span class="value">{{ user?.sso_domain }}</span>
              </div>
              <div class="info-item">
                <span class="label">Authentication</span>
                <span class="value">
                  @if (user?.auth_type === 'webauthn') {
                    <mat-icon class="auth-icon">fingerprint</mat-icon> Passkey
                  } @else if (user?.auth_type === 'local') {
                    <mat-icon class="auth-icon">password</mat-icon> Password
                  } @else if (user?.auth_type === 'oidc') {
                    <mat-icon class="auth-icon">login</mat-icon> SSO
                  } @else {
                    <mat-icon class="auth-icon">verified_user</mat-icon> {{ user?.auth_type || 'Not set' }}
                  }
                </span>
              </div>
              <div class="info-item">
                <span class="label">Last Login</span>
                <span class="value">{{ user?.last_login ? (user?.last_login | date:'medium') : 'Never' }}</span>
              </div>
              <div class="info-item">
                <span class="label">Role</span>
                <span class="value">
                  @if (user?.global_role === 'admin') {
                    <mat-chip class="role-chip admin-chip">Administrator</mat-chip>
                  } @else if (user?.global_role === 'steward') {
                    <mat-chip class="role-chip steward-chip">Steward</mat-chip>
                  } @else if (user?.global_role === 'provisional_admin') {
                    <mat-chip class="role-chip provisional-chip">Provisional Admin</mat-chip>
                  } @else {
                    <mat-chip class="role-chip user-chip">User</mat-chip>
                  }
                </span>
              </div>
            </div>

            <!-- Role Request Section (only for regular users or users without assigned role) -->
            @if (!setupMode && canRequestRole) {
              <div class="role-request-section">
                <div class="role-request-explainer">
                  <mat-icon class="explainer-icon">info_outline</mat-icon>
                  <div class="explainer-text">
                    <p>
                      <strong>Want to help manage this organization?</strong>
                      Request an elevated role to gain additional permissions like approving access requests,
                      inviting users, or managing tenant settings.
                    </p>
                  </div>
                </div>

                <button mat-raised-button color="accent" (click)="requestRole()"
                        [disabled]="isRequestingRole">
                  <mat-spinner diameter="20" *ngIf="isRequestingRole"></mat-spinner>
                  <mat-icon *ngIf="!isRequestingRole">admin_panel_settings</mat-icon>
                  <span *ngIf="!isRequestingRole">Request Elevated Role</span>
                </button>

                <!-- Tenant Admins List -->
                @if (tenantAdmins.length > 0) {
                  <div class="tenant-admins-list">
                    <p class="admins-header">
                      <mat-icon>group</mat-icon>
                      Current administrators who can review your request:
                    </p>
                    <div class="admins-chips">
                      @for (admin of tenantAdmins; track admin.name) {
                        <mat-chip class="admin-chip" [class.admin-role]="admin.role === 'admin'" [class.steward-role]="admin.role === 'steward'">
                          <mat-icon matChipAvatar>{{ admin.role === 'admin' ? 'admin_panel_settings' : 'shield' }}</mat-icon>
                          {{ admin.name }}
                        </mat-chip>
                      }
                    </div>
                  </div>
                }
              </div>
            }
          </mat-card-content>
        </mat-card>

        <!-- Passkeys Section (only for WebAuthn users, hidden during initial setup) -->
        @if (user?.auth_type === 'webauthn' && !setupMode) {
          <mat-card class="passkeys-card">
            <mat-card-header>
              <mat-card-title>
                <mat-icon>key</mat-icon>
                Passkeys
              </mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <p class="section-description">
                Passkeys are secure credentials stored on your devices. You can add multiple passkeys for backup access.
              </p>

              @if (isLoadingCredentials) {
                <div class="loading">
                  <mat-spinner diameter="40"></mat-spinner>
                </div>
              } @else {
                <mat-list class="credentials-list">
                  @for (credential of credentials; track credential.id) {
                    <mat-list-item>
                      <mat-icon matListItemIcon>fingerprint</mat-icon>
                      <div matListItemTitle>{{ credential.device_name }}</div>
                      <div matListItemLine>
                        Created: {{ credential.created_at | date:'mediumDate' }}
                        @if (credential.last_used_at) {
                          &middot; Last used: {{ credential.last_used_at | date:'mediumDate' }}
                        }
                      </div>
                      <button mat-icon-button matListItemMeta
                              [disabled]="credentials.length <= 1"
                              (click)="deleteCredential(credential)"
                              [matTooltip]="credentials.length <= 1 ? 'Cannot delete your only passkey' : 'Delete passkey'">
                        <mat-icon>delete</mat-icon>
                      </button>
                    </mat-list-item>
                  }
                </mat-list>

                @if (credentials.length === 0) {
                  <p class="no-credentials">No passkeys registered. This shouldn't happen - please contact support.</p>
                }

                <button mat-raised-button color="primary" class="add-passkey-button"
                        (click)="addPasskey()" [disabled]="isAddingPasskey">
                  <mat-spinner diameter="20" *ngIf="isAddingPasskey"></mat-spinner>
                  <mat-icon *ngIf="!isAddingPasskey">add</mat-icon>
                  <span *ngIf="!isAddingPasskey">Add new passkey</span>
                </button>
              }
            </mat-card-content>
          </mat-card>
        }

        <!-- Subscription card (hidden during setup mode) -->
        @if (!setupMode) {
        <mat-card class="subscription-card">
          <mat-card-header>
            <mat-card-title>
              <mat-icon>notifications</mat-icon>
              Notification Preferences
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            @if (isLoading) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else {
              <div class="notification-options">
                <div class="notification-option">
                  <div class="option-info">
                    <h3>New Decisions</h3>
                    <p>Get notified when new decision records are created</p>
                  </div>
                  <mat-slide-toggle [(ngModel)]="subscription.notify_on_create"
                                    (change)="saveSubscription()">
                  </mat-slide-toggle>
                </div>

                <mat-divider></mat-divider>

                <div class="notification-option">
                  <div class="option-info">
                    <h3>Decision Updates</h3>
                    <p>Get notified when existing decisions are modified</p>
                  </div>
                  <mat-slide-toggle [(ngModel)]="subscription.notify_on_update"
                                    (change)="saveSubscription()">
                  </mat-slide-toggle>
                </div>

                <mat-divider></mat-divider>

                <div class="notification-option">
                  <div class="option-info">
                    <h3>Status Changes</h3>
                    <p>Get notified when a decision's status changes (e.g., proposed to accepted)</p>
                  </div>
                  <mat-slide-toggle [(ngModel)]="subscription.notify_on_status_change"
                                    (change)="saveSubscription()">
                  </mat-slide-toggle>
                </div>
              </div>

              @if (isSaving) {
                <div class="saving-indicator">
                  <mat-spinner diameter="20"></mat-spinner>
                  <span>Saving...</span>
                </div>
              }
            }
          </mat-card-content>
        </mat-card>
        }

        <!-- API Keys Section (hidden during setup mode) -->
        @if (!setupMode) {
          <mat-card class="api-keys-card">
            <mat-card-header>
              <mat-card-title>
                <mat-icon>vpn_key</mat-icon>
                API Keys
              </mat-card-title>
            </mat-card-header>
            <mat-card-content>
              @if (!aiExternalAccessEnabled) {
                <!-- Show message when AI features are not enabled -->
                <div class="ai-not-enabled-notice">
                  <div class="notice-icon">
                    <mat-icon>info</mat-icon>
                  </div>
                  <div class="notice-content">
                    <h4>API Access Not Enabled</h4>
                    <p>
                      API keys allow you to integrate with AI tools like ChatGPT Custom GPTs, Claude MCP servers,
                      and other external applications. To use this feature:
                    </p>
                    <ul>
                      <li>A <strong>Tenant Administrator</strong> must enable "External AI Access" in the
                          <a [routerLink]="'/' + user?.tenant_info?.domain + '/admin'" class="admin-link">Admin Settings</a> → AI Features section</li>
                      <li>If you're not an admin, ask your organization's administrator to enable this feature</li>
                    </ul>
                    <p class="notice-hint">
                      <mat-icon>lightbulb</mat-icon>
                      Once enabled, you'll be able to create API keys here to connect your decision records
                      with AI-powered tools.
                    </p>
                  </div>
                </div>
              } @else {
              <p class="section-description">
                API keys allow external applications to access decision records on your behalf.
                Keep your keys secure and revoke any that are no longer needed.
              </p>

              @if (isLoadingApiKeys) {
                <div class="loading">
                  <mat-spinner diameter="40"></mat-spinner>
                </div>
              } @else {
                <!-- New key display (shown immediately after creation) -->
                @if (newlyCreatedKey) {
                  <div class="new-key-banner">
                    <div class="new-key-header">
                      <mat-icon>check_circle</mat-icon>
                      <span>API Key Created Successfully</span>
                    </div>
                    <p class="new-key-warning">
                      <strong>Save this key now!</strong> It will not be shown again.
                    </p>
                    <div class="new-key-display">
                      <code>{{ newlyCreatedKey }}</code>
                      <button mat-icon-button (click)="copyApiKey(newlyCreatedKey)" matTooltip="Copy to clipboard">
                        <mat-icon>content_copy</mat-icon>
                      </button>
                    </div>
                    <button mat-button color="primary" (click)="dismissNewKey()">
                      I've saved my key
                    </button>
                  </div>
                }

                <!-- API Keys list -->
                @if (apiKeys.length > 0) {
                  <mat-list class="api-keys-list">
                    @for (key of apiKeys; track key.id) {
                      <mat-list-item [class.revoked]="key.is_revoked" [class.expired]="key.is_expired">
                        <mat-icon matListItemIcon>vpn_key</mat-icon>
                        <div matListItemTitle>
                          {{ key.name }}
                          @if (key.is_revoked) {
                            <mat-chip class="status-chip revoked-chip">Revoked</mat-chip>
                          } @else if (key.is_expired) {
                            <mat-chip class="status-chip expired-chip">Expired</mat-chip>
                          }
                        </div>
                        <div matListItemLine>
                          <span class="key-prefix">{{ key.key_prefix }}...</span>
                          &middot; Scopes:
                          @for (scope of key.scopes; track scope) {
                            <span class="scope-badge" [class.scope-read]="scope === 'read'" [class.scope-search]="scope === 'search'" [class.scope-write]="scope === 'write'">{{ scope }}</span>
                          }
                          &middot; Created: {{ key.created_at | date:'mediumDate' }}
                          @if (key.last_used_at) {
                            &middot; Last used: {{ key.last_used_at | date:'mediumDate' }}
                          }
                        </div>
                        @if (!key.is_revoked) {
                          <button mat-icon-button matListItemMeta
                                  (click)="revokeApiKey(key)"
                                  matTooltip="Revoke this key">
                            <mat-icon>delete</mat-icon>
                          </button>
                        }
                      </mat-list-item>
                    }
                  </mat-list>
                } @else if (!newlyCreatedKey) {
                  <p class="no-keys">No API keys yet. Create one to integrate with external tools.</p>
                }

                <!-- Create new key section -->
                @if (!isCreatingKey) {
                  <div class="create-key-section">
                    <div class="key-form">
                      <mat-form-field appearance="outline" class="key-name-field">
                        <mat-label>Key Name</mat-label>
                        <input matInput [(ngModel)]="newKeyName" placeholder="e.g., My MCP Server">
                      </mat-form-field>
                      <div class="scope-selection">
                        <span class="scope-label">Permissions:</span>
                        <div class="scope-checkboxes">
                          <mat-checkbox [(ngModel)]="newKeyScopes.read" [disabled]="true" matTooltip="Read is always enabled">
                            Read
                          </mat-checkbox>
                          <mat-checkbox [(ngModel)]="newKeyScopes.search">
                            Search
                          </mat-checkbox>
                          <mat-checkbox [(ngModel)]="newKeyScopes.write">
                            Write (create decisions)
                          </mat-checkbox>
                        </div>
                      </div>
                    </div>
                    <button mat-raised-button color="primary" (click)="createApiKey()"
                            [disabled]="!newKeyName.trim() || apiKeys.length >= 5">
                      <mat-icon>add</mat-icon>
                      Create API Key
                    </button>
                  </div>
                  @if (apiKeys.length >= 5) {
                    <p class="max-keys-warning">
                      <mat-icon>warning</mat-icon>
                      Maximum of 5 API keys reached. Revoke an existing key to create a new one.
                    </p>
                  }
                } @else {
                  <div class="loading">
                    <mat-spinner diameter="24"></mat-spinner>
                    <span>Creating key...</span>
                  </div>
                }
              }
              }
            </mat-card-content>
          </mat-card>
        }
      }
    </div>
  `,
  styles: [`
    .profile-container {
      padding: 24px;
      max-width: 800px;
      margin: 0 auto;
    }

    h1 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 24px;
    }

    .setup-banner {
      display: flex;
      align-items: center;
      gap: 16px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 24px;
      border-radius: 8px;
      margin-bottom: 24px;
    }

    .setup-banner mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
    }

    .setup-banner h2 {
      margin: 0 0 4px 0;
      font-size: 20px;
    }

    .setup-banner p {
      margin: 0;
      opacity: 0.9;
    }

    .profile-card, .subscription-card, .passkeys-card, .setup-card {
      margin-bottom: 24px;
    }

    .setup-card {
      border: 2px solid #667eea;
    }

    .auth-options {
      padding: 16px 0;
    }

    .auth-option {
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 16px;
    }

    .auth-option.recommended {
      background: #f0f4ff;
      border: 1px solid #667eea;
    }

    .option-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }

    .option-header mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      color: #667eea;
    }

    .option-header h3 {
      margin: 0;
      font-size: 18px;
    }

    .recommended-badge {
      display: inline-block;
      background: #667eea;
      color: white;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 12px;
      margin-left: 8px;
    }

    .option-description {
      color: #666;
      font-size: 14px;
      margin-bottom: 16px;
    }

    .not-available {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #999;
      font-size: 14px;
      background: #f5f5f5;
      padding: 12px;
      border-radius: 4px;
    }

    .not-available mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .password-requirements {
      font-size: 12px;
      color: #666;
      margin-bottom: 16px;
    }

    .error-message {
      color: #c62828;
      font-size: 14px;
      margin-top: 12px;
      padding: 8px 12px;
      background: #ffebee;
      border-radius: 4px;
    }

    .full-width {
      width: 100%;
    }

    .info-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      padding-top: 16px;
    }

    .info-item .label {
      display: block;
      font-size: 12px;
      color: #888;
      text-transform: uppercase;
      margin-bottom: 4px;
    }

    .info-item .value {
      font-size: 16px;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .auth-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .role-chip {
      font-size: 12px;
    }

    .admin-chip {
      background-color: #e3f2fd !important;
      color: #1565c0 !important;
    }

    .steward-chip {
      background-color: #f3e5f5 !important;
      color: #7b1fa2 !important;
    }

    .provisional-chip {
      background-color: #fff3e0 !important;
      color: #e65100 !important;
    }

    .user-chip {
      background-color: #f5f5f5 !important;
      color: #616161 !important;
    }

    .role-request-section {
      margin-top: 24px;
      padding-top: 24px;
      border-top: 1px solid #e0e0e0;
    }

    .role-request-explainer {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 16px;
      background: linear-gradient(135deg, #f5f7ff 0%, #e8eaf6 100%);
      border-radius: 8px;
      margin-bottom: 20px;
      border-left: 4px solid #3f51b5;
    }

    .role-request-explainer .explainer-icon {
      color: #3f51b5;
      flex-shrink: 0;
    }

    .role-request-explainer .explainer-text p {
      margin: 0;
      font-size: 13px;
      line-height: 1.5;
      color: #333;
    }

    .role-request-explainer .explainer-text strong {
      color: #1a237e;
    }

    .role-request-section button {
      display: block;
      margin: 0 auto;
      max-width: 280px;
    }

    .tenant-admins-list {
      margin-top: 20px;
      padding: 16px;
      background: #fafafa;
      border-radius: 8px;
    }

    .tenant-admins-list .admins-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 12px 0;
      font-size: 13px;
      color: #666;
    }

    .tenant-admins-list .admins-header mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #999;
    }

    .admins-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .admin-chip {
      font-size: 12px;
    }

    .admin-chip.admin-role {
      background-color: #e3f2fd !important;
      color: #1565c0 !important;
    }

    .admin-chip.steward-role {
      background-color: #f3e5f5 !important;
      color: #7b1fa2 !important;
    }

    .subscription-card mat-card-title,
    .passkeys-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .section-description {
      color: #666;
      font-size: 14px;
      margin-bottom: 16px;
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 24px;
    }

    .credentials-list {
      margin-bottom: 16px;
    }

    .no-credentials {
      text-align: center;
      color: #999;
      padding: 24px;
    }

    .add-passkey-button {
      width: 100%;
    }

    .notification-options {
      padding-top: 16px;
    }

    .notification-option {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 0;
    }

    .option-info h3 {
      margin: 0 0 4px 0;
      font-size: 16px;
      font-weight: 500;
    }

    .option-info p {
      margin: 0;
      font-size: 14px;
      color: #666;
    }

    .saving-indicator {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #888;
      margin-top: 16px;
    }

    mat-divider {
      margin: 0;
    }

    /* API Keys Section */
    .api-keys-card {
      margin-bottom: 24px;
    }

    .api-keys-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .new-key-banner {
      background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
      border: 1px solid #4caf50;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }

    .new-key-header {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #2e7d32;
      font-weight: 500;
      margin-bottom: 8px;
    }

    .new-key-warning {
      color: #333;
      font-size: 14px;
      margin-bottom: 12px;
    }

    .new-key-display {
      display: flex;
      align-items: center;
      gap: 8px;
      background: white;
      padding: 12px;
      border-radius: 4px;
      margin-bottom: 12px;
      overflow-x: auto;
    }

    .new-key-display code {
      font-family: monospace;
      font-size: 14px;
      word-break: break-all;
      flex: 1;
    }

    .api-keys-list {
      margin-bottom: 16px;
    }

    .api-keys-list mat-list-item.revoked,
    .api-keys-list mat-list-item.expired {
      opacity: 0.6;
    }

    .key-prefix {
      font-family: monospace;
      background: #f5f5f5;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 12px;
    }

    .status-chip {
      font-size: 10px;
      height: 18px;
      margin-left: 8px;
    }

    .revoked-chip {
      background-color: #ffebee !important;
      color: #c62828 !important;
    }

    .expired-chip {
      background-color: #fff3e0 !important;
      color: #e65100 !important;
    }

    .no-keys {
      text-align: center;
      color: #999;
      padding: 24px;
      background: #fafafa;
      border-radius: 8px;
      margin-bottom: 16px;
    }

    .max-keys-warning {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #e65100;
      font-size: 13px;
      margin-top: 8px;
      padding: 8px 12px;
      background: #fff3e0;
      border-radius: 4px;
    }

    .max-keys-warning mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    /* Scope badges */
    .scope-badge {
      display: inline-block;
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      margin-left: 4px;
      font-weight: 500;
      text-transform: uppercase;
    }

    .scope-read {
      background: #e3f2fd;
      color: #1565c0;
    }

    .scope-search {
      background: #f3e5f5;
      color: #7b1fa2;
    }

    .scope-write {
      background: #fff3e0;
      color: #e65100;
    }

    /* Scope selection UI */
    .key-form {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .scope-selection {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .scope-label {
      font-size: 12px;
      color: #666;
      font-weight: 500;
    }

    .scope-checkboxes {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }

    .scope-checkboxes mat-checkbox {
      font-size: 14px;
    }

    .create-key-section {
      display: flex;
      gap: 12px;
      align-items: flex-end;
      margin-top: 16px;
    }

    .key-name-field {
      flex: 1;
    }

    /* AI Not Enabled Notice */
    .ai-not-enabled-notice {
      display: flex;
      gap: 16px;
      padding: 20px;
      background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
      border: 1px solid #ffc107;
      border-radius: 8px;
      border-left: 4px solid #ff9800;
    }

    .ai-not-enabled-notice .notice-icon {
      flex-shrink: 0;
    }

    .ai-not-enabled-notice .notice-icon mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      color: #f57c00;
    }

    .ai-not-enabled-notice .notice-content h4 {
      margin: 0 0 12px 0;
      font-size: 16px;
      font-weight: 600;
      color: #e65100;
    }

    .ai-not-enabled-notice .notice-content p {
      margin: 0 0 12px 0;
      font-size: 14px;
      color: #333;
      line-height: 1.5;
    }

    .ai-not-enabled-notice .notice-content ul {
      margin: 0 0 16px 0;
      padding-left: 20px;
    }

    .ai-not-enabled-notice .notice-content ul li {
      font-size: 14px;
      color: #333;
      line-height: 1.6;
      margin-bottom: 8px;
    }

    .ai-not-enabled-notice .admin-link {
      color: #1565c0;
      text-decoration: none;
      font-weight: 500;
    }

    .ai-not-enabled-notice .admin-link:hover {
      text-decoration: underline;
    }

    .ai-not-enabled-notice .notice-hint {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      background: rgba(255, 255, 255, 0.7);
      padding: 12px;
      border-radius: 6px;
      margin-top: 8px;
      font-size: 13px;
      color: #666;
    }

    .ai-not-enabled-notice .notice-hint mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #ff9800;
      flex-shrink: 0;
      margin-top: 2px;
    }
  `]
})
export class ProfileComponent implements OnInit {
  subscription: Subscription = {
    notify_on_create: false,
    notify_on_update: false,
    notify_on_status_change: false
  };
  credentials: WebAuthnCredential[] = [];
  isLoading = true;
  isLoadingCredentials = true;
  isSaving = false;
  isAddingPasskey = false;
  isRequestingRole = false;
  user: User | null = null;
  setupMode = false;
  pendingDomain = false;
  tenantAdmins: { name: string; role: string }[] = [];

  // API Key Management
  apiKeys: AIApiKey[] = [];
  isLoadingApiKeys = true;
  isCreatingKey = false;
  newKeyName = '';
  newKeyScopes = { read: true, search: true, write: false };
  newlyCreatedKey: string | null = null;
  aiExternalAccessEnabled = false;

  /**
   * Check if user can request a role elevation
   * Shows button for 'user' role or when role is undefined (legacy users)
   */
  get canRequestRole(): boolean {
    if (!this.user) return false;
    const role = this.user.global_role;
    // Show for 'user' role or when role is not set (undefined/null)
    return !role || role === 'user';
  }

  // Credential setup properties
  checkingPasskeySupport = true;
  passkeyAvailable = false;
  isSettingUpCredential = false;
  setupMethod: 'passkey' | 'password' | null = null;
  passkeyError: string | null = null;
  passwordError: string | null = null;
  passwordForm: FormGroup;

  constructor(
    public authService: AuthService,
    private webAuthnService: WebAuthnService,
    private adminService: AdminService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog,
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private http: HttpClient,
    private clipboard: Clipboard
  ) {
    // Password form with validation
    // Pattern: at least one uppercase, one lowercase, one number
    const passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$/;
    this.passwordForm = this.fb.group({
      password: ['', [
        Validators.required,
        Validators.minLength(PASSWORD_MIN_LENGTH),
        Validators.pattern(passwordPattern)
      ]],
      confirmPassword: ['', Validators.required]
    }, { validators: this.passwordMatchValidator });
  }

  passwordMatchValidator(form: FormGroup) {
    const password = form.get('password');
    const confirmPassword = form.get('confirmPassword');
    if (password && confirmPassword && password.value !== confirmPassword.value) {
      confirmPassword.setErrors({ passwordMismatch: true });
    }
    return null;
  }

  ngOnInit(): void {
    if (this.authService.currentUser && !this.authService.isMasterAccount) {
      this.user = this.authService.currentUser.user as User;
      this.loadSubscription();
      if (this.user.auth_type === 'webauthn') {
        this.loadCredentials();
      } else {
        this.isLoadingCredentials = false;
      }

      // Load tenant admins for role request section
      if (this.canRequestRole) {
        this.loadTenantAdmins();
      }

      // Check AI external access and load API keys
      this.checkAiAccess();

      // Check for setup mode (new account passkey setup)
      this.route.queryParams.subscribe(async params => {
        if (params['setup'] === 'passkey') {
          this.setupMode = true;
          this.pendingDomain = params['pending'] === '1';

          // Check if passkey is available on this device
          // We check both platform authenticator AND general WebAuthn support
          // Even if platform auth isn't available, users might have security keys
          this.checkingPasskeySupport = true;

          // First check if WebAuthn is supported at all
          const webAuthnSupported = this.webAuthnService.isWebAuthnSupported();
          console.log('[Profile] WebAuthn supported:', webAuthnSupported);

          if (webAuthnSupported) {
            // Check for platform authenticator (Touch ID, Face ID, etc.)
            const platformAvailable = await this.webAuthnService.isPlatformAuthenticatorAvailable();
            console.log('[Profile] Platform authenticator available:', platformAvailable);

            // Allow passkey registration if WebAuthn is supported
            // (users can use security keys even without platform authenticator)
            this.passkeyAvailable = webAuthnSupported;
          } else {
            this.passkeyAvailable = false;
          }

          this.checkingPasskeySupport = false;
          console.log('[Profile] Final passkeyAvailable:', this.passkeyAvailable);
        }
      });
    }
  }

  loadSubscription(): void {
    this.authService.getSubscription().subscribe({
      next: (subscription) => {
        this.subscription = subscription;
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  loadCredentials(): void {
    this.webAuthnService.getCredentials().subscribe({
      next: (credentials) => {
        this.credentials = credentials;
        this.isLoadingCredentials = false;
      },
      error: () => {
        this.isLoadingCredentials = false;
      }
    });
  }

  saveSubscription(): void {
    this.isSaving = true;
    this.authService.updateSubscription(this.subscription).subscribe({
      next: (subscription) => {
        this.subscription = subscription;
        this.isSaving = false;
        this.snackBar.open('Preferences saved', 'Close', { duration: 2000 });
      },
      error: () => {
        this.isSaving = false;
        this.snackBar.open('Failed to save preferences', 'Close', { duration: 3000 });
      }
    });
  }

  addPasskey(): void {
    if (!this.user) return;

    this.isAddingPasskey = true;

    this.webAuthnService.register(this.user.email, this.user.name).subscribe({
      next: () => {
        this.isAddingPasskey = false;
        this.snackBar.open('Passkey added successfully', 'Close', { duration: 2000 });
        this.loadCredentials();
      },
      error: (err) => {
        this.isAddingPasskey = false;
        this.snackBar.open(err.error?.error || 'Failed to add passkey', 'Close', { duration: 3000 });
      }
    });
  }

  addPasskeyWithRedirect(): void {
    if (!this.user) return;

    this.isAddingPasskey = true;

    this.webAuthnService.register(this.user.email, this.user.name).subscribe({
      next: () => {
        this.isAddingPasskey = false;
        this.snackBar.open('Passkey added successfully! Redirecting...', 'Close', { duration: 2000 });
        this.loadCredentials();

        // Redirect based on domain status
        setTimeout(() => {
          if (this.pendingDomain) {
            this.router.navigate([`/${this.user?.sso_domain}/pending`]);
          } else {
            this.router.navigate([`/${this.user?.sso_domain}`]);
          }
        }, 1500);
      },
      error: (err) => {
        this.isAddingPasskey = false;
        this.snackBar.open(err.error?.error || 'Failed to add passkey. Please try again.', 'Close', { duration: 5000 });
        // In setup mode, show the button to try again
      }
    });
  }

  /**
   * Setup passkey for new account (setup mode)
   */
  setupPasskey(): void {
    if (!this.user) return;

    this.isSettingUpCredential = true;
    this.setupMethod = 'passkey';
    this.passkeyError = null;

    this.webAuthnService.register(this.user.email, this.user.name).subscribe({
      next: () => {
        this.isSettingUpCredential = false;
        this.setupMethod = null;

        // Show success message with longer duration
        this.snackBar.open('Passkey created successfully! You can now sign in with your passkey.', 'Close', { duration: 4000 });

        // Refresh user to update has_passkey status
        this.authService.loadCurrentUser().subscribe(() => {
          // Redirect to login page with success message so user can test their new passkey
          setTimeout(() => {
            this.router.navigate([`/${this.user?.sso_domain}/login`], {
              queryParams: { passkey_setup: 'success' }
            });
          }, 2000);
        });
      },
      error: (err) => {
        this.isSettingUpCredential = false;
        this.setupMethod = null;
        this.passkeyError = err.error?.error || 'Failed to create passkey. You can try again or use a password instead.';
      }
    });
  }

  /**
   * Setup password for new account (setup mode)
   */
  setupPassword(): void {
    if (!this.user || this.passwordForm.invalid) return;

    this.isSettingUpCredential = true;
    this.setupMethod = 'password';
    this.passwordError = null;

    const password = this.passwordForm.get('password')?.value;

    this.http.post<{ message: string }>('/api/auth/set-password', { password }).subscribe({
      next: () => {
        this.isSettingUpCredential = false;
        this.setupMethod = null;
        this.snackBar.open('Password set successfully! Redirecting...', 'Close', { duration: 2000 });

        // Refresh user to update has_password status
        this.authService.loadCurrentUser().subscribe(() => {
          setTimeout(() => this.redirectAfterSetup(), 1500);
        });
      },
      error: (err) => {
        this.isSettingUpCredential = false;
        this.setupMethod = null;
        this.passwordError = err.error?.error || 'Failed to set password. Please try again.';
      }
    });
  }

  /**
   * Redirect after successful credential setup
   */
  private redirectAfterSetup(): void {
    if (this.pendingDomain) {
      this.router.navigate([`/${this.user?.sso_domain}/pending`]);
    } else {
      // Redirect to tenant login page so user can test their new credentials
      this.router.navigate([`/${this.user?.sso_domain}/login`]);
    }
  }

  deleteCredential(credential: WebAuthnCredential): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete Passkey',
        message: `Are you sure you want to delete the passkey "${credential.device_name}"? You won't be able to use this device to sign in anymore.`,
        confirmText: 'Delete',
        cancelText: 'Cancel'
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.webAuthnService.deleteCredential(credential.credential_id).subscribe({
          next: () => {
            this.snackBar.open('Passkey deleted', 'Close', { duration: 2000 });
            this.loadCredentials();
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to delete passkey', 'Close', { duration: 3000 });
          }
        });
      }
    });
  }

  loadTenantAdmins(): void {
    this.adminService.getTenantAdmins().subscribe({
      next: (response) => {
        this.tenantAdmins = response.admins;
      },
      error: () => {
        // Silently fail - admins list is not critical
        this.tenantAdmins = [];
      }
    });
  }

  requestRole(): void {
    const dialogRef = this.dialog.open(RoleRequestDialogComponent, {
      data: {
        currentRole: this.user?.global_role
      },
      width: '600px'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.isRequestingRole = true;
        this.adminService.createRoleRequest(result.role, result.reason).subscribe({
          next: () => {
            this.isRequestingRole = false;
            this.snackBar.open('Role request submitted successfully. Admins will review your request.', 'Close', { duration: 5000 });
          },
          error: (err) => {
            this.isRequestingRole = false;
            this.snackBar.open(err.error?.error || 'Failed to submit role request', 'Close', { duration: 3000 });
          }
        });
      }
    });
  }

  // ============ API Key Management Methods ============

  /**
   * Check if AI external access is enabled for the user
   */
  checkAiAccess(): void {
    // Check if external API access is available for user
    this.http.get<{ available: boolean }>('/api/user/ai/access').subscribe({
      next: (response) => {
        this.aiExternalAccessEnabled = response.available;
        if (this.aiExternalAccessEnabled) {
          this.loadApiKeys();
        } else {
          this.isLoadingApiKeys = false;
        }
      },
      error: () => {
        // If we can't check, assume disabled
        this.aiExternalAccessEnabled = false;
        this.isLoadingApiKeys = false;
      }
    });
  }

  /**
   * Load user's API keys
   */
  loadApiKeys(): void {
    this.isLoadingApiKeys = true;
    this.http.get<AIApiKey[]>('/api/user/ai/keys').subscribe({
      next: (keys) => {
        this.apiKeys = keys;
        this.isLoadingApiKeys = false;
      },
      error: () => {
        this.apiKeys = [];
        this.isLoadingApiKeys = false;
      }
    });
  }

  /**
   * Create a new API key
   */
  createApiKey(): void {
    if (!this.newKeyName.trim()) return;

    // Build scopes array from selections
    const scopes: string[] = [];
    if (this.newKeyScopes.read) scopes.push('read');
    if (this.newKeyScopes.search) scopes.push('search');
    if (this.newKeyScopes.write) scopes.push('write');

    this.isCreatingKey = true;
    this.http.post<{ key: string } & AIApiKey>('/api/user/ai/keys', {
      name: this.newKeyName.trim(),
      scopes: scopes
    }).subscribe({
      next: (response) => {
        this.newlyCreatedKey = response.key;
        this.newKeyName = '';
        // Reset scopes to defaults
        this.newKeyScopes = { read: true, search: true, write: false };
        this.isCreatingKey = false;
        this.loadApiKeys();  // Reload the list
        this.snackBar.open('API key created successfully!', 'Close', { duration: 3000 });
      },
      error: (err) => {
        this.isCreatingKey = false;
        this.snackBar.open(err.error?.error || 'Failed to create API key', 'Close', { duration: 3000 });
      }
    });
  }

  /**
   * Revoke an API key
   */
  revokeApiKey(key: AIApiKey): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Revoke API Key',
        message: `Are you sure you want to revoke the API key "${key.name}"? This action cannot be undone and any applications using this key will stop working.`,
        confirmText: 'Revoke',
        cancelText: 'Cancel'
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.http.delete(`/api/user/ai/keys/${key.id}`).subscribe({
          next: () => {
            this.snackBar.open('API key revoked', 'Close', { duration: 2000 });
            this.loadApiKeys();
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to revoke API key', 'Close', { duration: 3000 });
          }
        });
      }
    });
  }

  /**
   * Copy API key to clipboard
   */
  copyApiKey(key: string): void {
    this.clipboard.copy(key);
    this.snackBar.open('API key copied to clipboard', 'Close', { duration: 2000 });
  }

  /**
   * Dismiss the newly created key banner
   */
  dismissNewKey(): void {
    this.newlyCreatedKey = null;
  }
}
