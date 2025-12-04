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
import { SSOConfig, EmailConfig, User, AuthConfig } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';
import { MatSelectModule } from '@angular/material/select';
import { MatRadioModule } from '@angular/material/radio';

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
    ConfirmDialogComponent
  ],
  template: `
    <div class="settings-container">
      <h1>
        <mat-icon>settings</mat-icon>
        System Settings
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
                             [readonly]="editingSSOId !== null">
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
                      @if (savingSSOConfig) {
                        <mat-spinner diameter="20"></mat-spinner>
                      } @else {
                        <mat-icon>save</mat-icon>
                        {{ editingSSOId ? 'Update' : 'Add Provider' }}
                      }
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
                      @if (savingEmailConfig) {
                        <mat-spinner diameter="20"></mat-spinner>
                      } @else {
                        <mat-icon>save</mat-icon>
                        Save Configuration
                      }
                    </button>
                    <button mat-button type="button" (click)="testEmail()"
                            [disabled]="!hasExistingEmailConfig || testingEmail">
                      @if (testingEmail) {
                        <mat-spinner diameter="20"></mat-spinner>
                      } @else {
                        <mat-icon>send</mat-icon>
                        Send Test Email
                      }
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
                  Configure how users in your domain authenticate. You can choose between SSO (Single Sign-On)
                  or Passkeys (WebAuthn) for passwordless authentication.
                </p>

                <form [formGroup]="authConfigForm" (ngSubmit)="saveAuthConfig()">
                  <div class="auth-method-options">
                    <mat-radio-group formControlName="auth_method" class="auth-method-group">
                      <mat-radio-button value="webauthn" class="auth-method-option">
                        <div class="option-content">
                          <mat-icon>fingerprint</mat-icon>
                          <div class="option-text">
                            <strong>Passkeys (WebAuthn)</strong>
                            <span>Passwordless authentication using device biometrics or security keys</span>
                          </div>
                        </div>
                      </mat-radio-button>

                      <mat-radio-button value="sso" class="auth-method-option"
                                        [disabled]="!hasSSOConfigForDomain">
                        <div class="option-content">
                          <mat-icon>login</mat-icon>
                          <div class="option-text">
                            <strong>Single Sign-On (SSO)</strong>
                            <span>
                              @if (hasSSOConfigForDomain) {
                                Use your organization's identity provider
                              } @else {
                                Configure an SSO provider first to enable this option
                              }
                            </span>
                          </div>
                        </div>
                      </mat-radio-button>
                    </mat-radio-group>
                  </div>

                  @if (authConfigForm.value.auth_method === 'webauthn') {
                    <div class="webauthn-options">
                      <mat-slide-toggle formControlName="allow_registration">
                        Allow new user registration
                      </mat-slide-toggle>
                      <p class="option-hint">
                        When enabled, new users can create accounts with their email and a passkey.
                        When disabled, only existing users can sign in.
                      </p>

                      <mat-form-field appearance="outline" class="full-width">
                        <mat-label>Application Name (shown during passkey setup)</mat-label>
                        <input matInput formControlName="rp_name" placeholder="Architecture Decisions">
                      </mat-form-field>
                    </div>
                  }

                  <div class="form-actions">
                    <button mat-raised-button color="primary" type="submit"
                            [disabled]="authConfigForm.invalid || savingAuthConfig">
                      @if (savingAuthConfig) {
                        <mat-spinner diameter="20"></mat-spinner>
                      } @else {
                        <mat-icon>save</mat-icon>
                        Save Configuration
                      }
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
                <h4>Passkeys (WebAuthn)</h4>
                <ul>
                  <li>No passwords to remember or manage</li>
                  <li>Uses device biometrics (fingerprint, face) or security keys</li>
                  <li>Resistant to phishing attacks</li>
                  <li>Users can register multiple devices for backup access</li>
                </ul>

                <h4>Single Sign-On (SSO)</h4>
                <ul>
                  <li>Users authenticate with your organization's identity provider</li>
                  <li>Centralized user management</li>
                  <li>Supports Google, Microsoft, Okta, and other OIDC providers</li>
                  <li>Requires SSO provider configuration in the SSO Providers tab</li>
                </ul>
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
  `]
})
export class SettingsComponent implements OnInit {
  ssoForm: FormGroup;
  emailForm: FormGroup;
  authConfigForm: FormGroup;
  ssoConfigs: SSOConfig[] = [];
  users: User[] = [];
  authConfig: AuthConfig | null = null;
  ssoColumns = ['domain', 'provider_name', 'enabled', 'actions'];
  userColumns = ['name', 'email', 'domain', 'auth_type', 'is_admin', 'last_login'];

  editingSSOId: number | null = null;
  hasExistingEmailConfig = false;
  hasSSOConfigForDomain = false;
  savingSSOConfig = false;
  savingEmailConfig = false;
  savingAuthConfig = false;
  testingEmail = false;

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
      auth_method: ['webauthn', Validators.required],
      allow_registration: [true],
      rp_name: ['Architecture Decisions']
    });
  }

  ngOnInit(): void {
    this.loadSSOConfigs();
    this.loadEmailConfig();
    this.loadUsers();
    this.loadAuthConfig();
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
          this.authConfigForm.patchValue({
            auth_method: this.authConfig.auth_method,
            allow_registration: this.authConfig.allow_registration,
            rp_name: this.authConfig.rp_name
          });
        }
      },
      error: () => {
        // Use defaults if no config exists
        this.authConfigForm.patchValue({
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

    const config: AuthConfigRequest = {
      auth_method: formValue.auth_method,
      allow_registration: formValue.allow_registration,
      rp_name: formValue.rp_name
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
}
