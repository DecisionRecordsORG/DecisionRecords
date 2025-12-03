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
import { AdminService, CreateSSOConfigRequest, EmailConfigRequest } from '../../services/admin.service';
import { AuthService } from '../../services/auth.service';
import { SSOConfig, EmailConfig, User } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';

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
  `]
})
export class SettingsComponent implements OnInit {
  ssoForm: FormGroup;
  emailForm: FormGroup;
  ssoConfigs: SSOConfig[] = [];
  users: User[] = [];
  ssoColumns = ['domain', 'provider_name', 'enabled', 'actions'];
  userColumns = ['name', 'email', 'domain', 'is_admin', 'last_login'];

  editingSSOId: number | null = null;
  hasExistingEmailConfig = false;
  savingSSOConfig = false;
  savingEmailConfig = false;
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
  }

  ngOnInit(): void {
    this.loadSSOConfigs();
    this.loadEmailConfig();
    this.loadUsers();
  }

  loadSSOConfigs(): void {
    this.adminService.getSSOConfigs().subscribe({
      next: (configs) => this.ssoConfigs = configs,
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
}
