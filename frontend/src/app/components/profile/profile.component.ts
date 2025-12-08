import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
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
import { AuthService } from '../../services/auth.service';
import { WebAuthnService } from '../../services/webauthn.service';
import { Subscription, User, WebAuthnCredential } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';

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
    MatInputModule
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
                      @if (isSettingUpCredential && setupMethod === 'passkey') {
                        <mat-spinner diameter="20"></mat-spinner>
                      } @else {
                        <mat-icon>fingerprint</mat-icon>
                        Set up Passkey
                      }
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
                      @if (isSettingUpCredential && setupMethod === 'password') {
                        <mat-spinner diameter="20"></mat-spinner>
                      } @else {
                        <mat-icon>lock</mat-icon>
                        Set Password
                      }
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
                  } @else {
                    <mat-icon class="auth-icon">login</mat-icon> SSO
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
                  @if (user?.is_admin) {
                    <mat-chip class="admin-chip" highlighted>Administrator</mat-chip>
                  } @else {
                    User
                  }
                </span>
              </div>
            </div>
          </mat-card-content>
        </mat-card>

        <!-- Passkeys Section (only for WebAuthn users) -->
        @if (user?.auth_type === 'webauthn') {
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
                  @if (isAddingPasskey) {
                    <mat-spinner diameter="20"></mat-spinner>
                  } @else {
                    <mat-icon>add</mat-icon>
                    Add new passkey
                  }
                </button>
              }
            </mat-card-content>
          </mat-card>
        }

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
                    <p>Get notified when new architecture decisions are created</p>
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

    .admin-chip {
      font-size: 12px;
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
  user: User | null = null;
  setupMode = false;
  pendingDomain = false;

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
    private snackBar: MatSnackBar,
    private dialog: MatDialog,
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private http: HttpClient
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

      // Check for setup mode (new account passkey setup)
      this.route.queryParams.subscribe(async params => {
        if (params['setup'] === 'passkey') {
          this.setupMode = true;
          this.pendingDomain = params['pending'] === '1';

          // Check if passkey is available on this device
          // Per passkeys.dev best practices
          this.checkingPasskeySupport = true;
          this.passkeyAvailable = await this.webAuthnService.isPlatformAuthenticatorAvailable();
          this.checkingPasskeySupport = false;
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
        this.snackBar.open('Passkey created successfully! Redirecting...', 'Close', { duration: 2000 });

        // Refresh user to update has_passkey status
        this.authService.loadCurrentUser().subscribe(() => {
          setTimeout(() => this.redirectAfterSetup(), 1500);
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
      this.router.navigate([`/${this.user?.sso_domain}`]);
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
}
