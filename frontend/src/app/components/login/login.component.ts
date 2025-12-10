import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDividerModule } from '@angular/material/divider';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTabsModule } from '@angular/material/tabs';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../../services/auth.service';
import { WebAuthnService } from '../../services/webauthn.service';
import { SSOConfig, AuthConfig } from '../../models/decision.model';

type LoginView = 'initial' | 'webauthn' | 'password' | 'register' | 'recovery';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatDividerModule,
    MatProgressSpinnerModule,
    MatTabsModule
  ],
  template: `
    <div class="login-container">
      <mat-card class="login-card">
        <mat-card-header>
          <mat-card-title>
            <mat-icon>architecture</mat-icon>
            Architecture Decisions
          </mat-card-title>
          <mat-card-subtitle>
            @if (currentView === 'initial') {
              Sign in to continue
            } @else if (currentView === 'webauthn') {
              Sign in with passkey
            } @else if (currentView === 'register') {
              Create your account
            } @else {
              Reset your credentials
            }
          </mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          @if (error) {
            <div class="error-message">{{ error }}</div>
          }

          @if (success) {
            <div class="success-message">{{ success }}</div>
          }

          <!-- Initial View: Email Entry / SSO Options -->
          @if (currentView === 'initial') {
            <!-- WebAuthn Check Not Supported Notice -->
            @if (!webAuthnSupported) {
              <div class="warning-message">
                <mat-icon>warning</mat-icon>
                Passkey login is not supported in this browser.
              </div>
            }

            <!-- SSO Login Options -->
            @if (ssoConfigs.length > 0) {
              <div class="sso-section">
                <p class="section-title">Sign in with SSO</p>
                @for (config of ssoConfigs; track config.id) {
                  <a [href]="'/auth/sso/' + config.id" mat-raised-button color="primary" class="sso-button">
                    <mat-icon>login</mat-icon>
                    {{ config.provider_name }}
                  </a>
                }
              </div>
              <mat-divider></mat-divider>
            }

            <!-- Email Entry for WebAuthn -->
            @if (webAuthnSupported) {
              <div class="webauthn-section">
                <p class="section-title">
                  <mat-icon>fingerprint</mat-icon>
                  Sign in with Passkey
                </p>

                <form [formGroup]="emailForm" (ngSubmit)="checkEmail()" data-testid="email-form">
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Email</mat-label>
                    <input matInput formControlName="email" type="email" placeholder="you@example.com" data-testid="email-input">
                    <mat-icon matPrefix>email</mat-icon>
                  </mat-form-field>

                  <button mat-raised-button color="primary" type="submit"
                          [disabled]="emailForm.invalid || isLoading" class="full-width" data-testid="continue-button">
                    @if (isLoading) {
                      <mat-spinner diameter="20"></mat-spinner>
                    } @else {
                      Continue
                      <mat-icon>arrow_forward</mat-icon>
                    }
                  </button>
                </form>

                <!-- Quick Passkey Login (for discoverable credentials) -->
                <button mat-stroked-button class="full-width passkey-quick-login" (click)="quickPasskeyLogin()"
                        [disabled]="isLoading">
                  <mat-icon>key</mat-icon>
                  Sign in with saved passkey
                </button>
              </div>
              <mat-divider></mat-divider>
            }

            <!-- Local Admin Login -->
            <div class="admin-section">
              <p class="section-title">
                <mat-icon>admin_panel_settings</mat-icon>
                Administrator Login
              </p>
              <form [formGroup]="adminForm" (ngSubmit)="adminLogin()">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Username</mat-label>
                  <input matInput formControlName="username" placeholder="admin">
                  <mat-icon matPrefix>person</mat-icon>
                </mat-form-field>

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Password</mat-label>
                  <input matInput [type]="hidePassword ? 'password' : 'text'" formControlName="password">
                  <mat-icon matPrefix>lock</mat-icon>
                  <button mat-icon-button matSuffix type="button" (click)="hidePassword = !hidePassword">
                    <mat-icon>{{ hidePassword ? 'visibility_off' : 'visibility' }}</mat-icon>
                  </button>
                </mat-form-field>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="adminForm.invalid || isLoading" class="full-width">
                  @if (isLoading) {
                    <mat-spinner diameter="20"></mat-spinner>
                  } @else {
                    <mat-icon>login</mat-icon>
                    Sign In
                  }
                </button>
              </form>

              @if (ssoConfigs.length === 0) {
                <p class="hint-text">
                  Default credentials: admin / changeme
                </p>
              }
            </div>
          }

          <!-- WebAuthn Sign In View -->
          @if (currentView === 'webauthn') {
            <div class="webauthn-auth-section" data-testid="webauthn-view">
              <p class="user-email" data-testid="current-email">{{ currentEmail }}</p>

              <button mat-raised-button color="primary" class="full-width passkey-button"
                      (click)="signInWithPasskey()" [disabled]="isLoading" data-testid="passkey-signin-button">
                @if (isLoading) {
                  <mat-spinner diameter="20"></mat-spinner>
                } @else {
                  <mat-icon>fingerprint</mat-icon>
                  Use passkey to sign in
                }
              </button>

              <p class="alt-action">
                <button mat-button color="primary" (click)="showPasswordLogin()" data-testid="use-password-link">
                  <mat-icon>password</mat-icon>
                  Sign in with password instead
                </button>
              </p>

              @if (authConfig?.allow_registration) {
                <p class="alt-action">
                  Don't have a passkey?
                  <button mat-button color="primary" (click)="showRegister()">Create account</button>
                </p>
              }

              <p class="recovery-link">
                <button mat-button (click)="showRecovery()">
                  <mat-icon>lock_reset</mat-icon>
                  Forgot your credentials?
                </button>
              </p>

              <button mat-button class="back-button" (click)="goBack()" data-testid="back-button">
                <mat-icon>arrow_back</mat-icon>
                Back
              </button>
            </div>
          }

          <!-- Password Sign In View -->
          @if (currentView === 'password') {
            <div class="password-auth-section" data-testid="password-view">
              <p class="user-email" data-testid="current-email">{{ currentEmail }}</p>

              <form [formGroup]="passwordForm" (ngSubmit)="passwordLogin()" data-testid="password-form">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Password</mat-label>
                  <input matInput [type]="hidePassword ? 'password' : 'text'" formControlName="password" data-testid="password-input">
                  <mat-icon matPrefix>lock</mat-icon>
                  <button mat-icon-button matSuffix type="button" (click)="hidePassword = !hidePassword">
                    <mat-icon>{{ hidePassword ? 'visibility_off' : 'visibility' }}</mat-icon>
                  </button>
                </mat-form-field>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="passwordForm.invalid || isLoading" class="full-width" data-testid="login-button">
                  @if (isLoading) {
                    <mat-spinner diameter="20"></mat-spinner>
                  } @else {
                    <mat-icon>login</mat-icon>
                    Sign In
                  }
                </button>
              </form>

              <p class="alt-action">
                <button mat-button color="primary" (click)="showWebAuthn()" data-testid="use-passkey-link">
                  <mat-icon>fingerprint</mat-icon>
                  Sign in with passkey instead
                </button>
              </p>

              <p class="recovery-link">
                <button mat-button (click)="showRecovery()">
                  <mat-icon>lock_reset</mat-icon>
                  Forgot your password?
                </button>
              </p>

              <button mat-button class="back-button" (click)="goBack()" data-testid="back-button">
                <mat-icon>arrow_back</mat-icon>
                Back
              </button>
            </div>
          }

          <!-- Registration View -->
          @if (currentView === 'register') {
            <div class="register-section">
              <form [formGroup]="registerForm" (ngSubmit)="registerWithPasskey()">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Email</mat-label>
                  <input matInput formControlName="email" type="email" readonly>
                  <mat-icon matPrefix>email</mat-icon>
                </mat-form-field>

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Full Name</mat-label>
                  <input matInput formControlName="name" placeholder="Your name">
                  <mat-icon matPrefix>person</mat-icon>
                </mat-form-field>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="registerForm.invalid || isLoading" class="full-width">
                  @if (isLoading) {
                    <mat-spinner diameter="20"></mat-spinner>
                  } @else {
                    <mat-icon>fingerprint</mat-icon>
                    Create account with passkey
                  }
                </button>
              </form>

              <p class="alt-action">
                Already have an account?
                <button mat-button color="primary" (click)="showWebAuthn()">Sign in</button>
              </p>

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Back
              </button>
            </div>
          }

          <!-- Account Recovery View -->
          @if (currentView === 'recovery') {
            <div class="recovery-section">
              <div class="recovery-icon">
                <mat-icon>lock_reset</mat-icon>
              </div>
              <p class="recovery-description">
                Enter your email address and we'll send you a link to reset your credentials.
              </p>

              <form [formGroup]="recoveryForm" (ngSubmit)="requestRecovery()">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Email</mat-label>
                  <input matInput formControlName="email" type="email" placeholder="you@example.com">
                  <mat-icon matPrefix>email</mat-icon>
                </mat-form-field>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="recoveryForm.invalid || isLoading" class="full-width">
                  @if (isLoading) {
                    <mat-spinner diameter="20"></mat-spinner>
                  } @else {
                    <mat-icon>send</mat-icon>
                    Send Recovery Link
                  }
                </button>
              </form>

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Back to login
              </button>
            </div>
          }
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .login-container {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      padding: 20px;
    }

    .login-card {
      width: 100%;
      max-width: 400px;
      padding: 20px;
    }

    mat-card-header {
      margin-bottom: 20px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 24px;
    }

    .error-message {
      background-color: #ffebee;
      color: #c62828;
      padding: 12px;
      border-radius: 4px;
      margin-bottom: 16px;
    }

    .success-message {
      background-color: #e8f5e9;
      color: #2e7d32;
      padding: 12px;
      border-radius: 4px;
      margin-bottom: 16px;
    }

    .warning-message {
      display: flex;
      align-items: center;
      gap: 8px;
      background-color: #fff3e0;
      color: #e65100;
      padding: 12px;
      border-radius: 4px;
      margin-bottom: 16px;
      font-size: 14px;
    }

    .section-title {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #666;
      font-size: 14px;
      margin-bottom: 16px;
    }

    .sso-section {
      margin-bottom: 20px;
    }

    .sso-button {
      width: 100%;
      margin-bottom: 8px;
    }

    .webauthn-section {
      margin-bottom: 20px;
    }

    .admin-section {
      margin-top: 20px;
    }

    .full-width {
      width: 100%;
    }

    mat-form-field {
      margin-bottom: 8px;
    }

    .hint-text {
      font-size: 12px;
      color: #888;
      text-align: center;
      margin-top: 16px;
    }

    mat-divider {
      margin: 20px 0;
    }

    .passkey-quick-login {
      margin-top: 12px;
    }

    .webauthn-auth-section, .register-section, .password-auth-section {
      text-align: center;
    }

    .user-email {
      font-size: 16px;
      color: #333;
      margin-bottom: 24px;
      padding: 12px;
      background: #f5f5f5;
      border-radius: 4px;
    }

    .passkey-button {
      padding: 12px 24px;
      font-size: 16px;
    }

    .alt-action {
      margin-top: 24px;
      color: #666;
      font-size: 14px;
    }

    .back-button {
      margin-top: 16px;
    }

    .recovery-link {
      margin-top: 16px;
      text-align: center;
    }

    .recovery-link button {
      color: #666;
      font-size: 13px;
    }

    .recovery-section {
      text-align: center;
    }

    .recovery-icon {
      margin-bottom: 16px;
    }

    .recovery-icon mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #3f51b5;
    }

    .recovery-description {
      color: #666;
      margin-bottom: 24px;
      font-size: 14px;
      line-height: 1.5;
    }
  `]
})
export class LoginComponent implements OnInit {
  emailForm: FormGroup;
  adminForm: FormGroup;
  registerForm: FormGroup;
  recoveryForm: FormGroup;
  passwordForm: FormGroup;

  ssoConfigs: SSOConfig[] = [];
  authConfig: AuthConfig | null = null;
  currentEmail = '';
  currentView: LoginView = 'initial';

  hidePassword = true;
  isLoading = false;
  error = '';
  success = '';

  webAuthnSupported = false;

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private router: Router,
    private authService: AuthService,
    private webAuthnService: WebAuthnService
  ) {
    this.emailForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]]
    });

    this.adminForm = this.fb.group({
      username: ['', Validators.required],
      password: ['', Validators.required]
    });

    this.registerForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      name: ['', Validators.required]
    });

    this.recoveryForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]]
    });

    this.passwordForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required]
    });
  }

  ngOnInit(): void {
    this.webAuthnSupported = this.webAuthnService.isWebAuthnSupported();
    this.loadSSOConfigs();
  }

  loadSSOConfigs(): void {
    this.http.get<SSOConfig[]>('/api/auth/sso-configs').subscribe({
      next: (configs) => this.ssoConfigs = configs,
      error: () => this.ssoConfigs = []
    });
  }

  checkEmail(): void {
    if (this.emailForm.invalid) return;

    this.isLoading = true;
    this.error = '';
    this.currentEmail = this.emailForm.value.email;

    // Extract domain from email
    const domain = this.currentEmail.split('@')[1];
    if (!domain) {
      this.error = 'Invalid email address';
      this.isLoading = false;
      return;
    }

    // Check auth config for this domain
    this.webAuthnService.getAuthConfig(domain).subscribe({
      next: (config) => {
        this.authConfig = config;
        this.isLoading = false;

        if (config.auth_method === 'sso') {
          // Check if there's an SSO config for this domain
          const ssoConfig = this.ssoConfigs.find(c => c.domain === domain);
          if (ssoConfig) {
            // Redirect to SSO
            window.location.href = `/auth/sso/${ssoConfig.id}`;
          } else {
            this.error = 'SSO is configured for this domain but no provider is set up. Contact your administrator.';
          }
        } else {
          // WebAuthn - show sign in view
          this.currentView = 'webauthn';
          this.registerForm.patchValue({ email: this.currentEmail });
        }
      },
      error: () => {
        this.isLoading = false;
        // Default to WebAuthn if can't get config
        this.authConfig = {
          domain,
          auth_method: 'webauthn',
          allow_registration: true,
          rp_name: 'Architecture Decisions'
        };
        this.currentView = 'webauthn';
        this.registerForm.patchValue({ email: this.currentEmail });
      }
    });
  }

  signInWithPasskey(): void {
    this.isLoading = true;
    this.error = '';

    this.webAuthnService.authenticate(this.currentEmail).subscribe({
      next: () => {
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.isLoading = false;
        if (err.error?.error === 'No passkeys registered for this account') {
          this.error = 'No passkey found for this account. Would you like to create one?';
          if (this.authConfig?.allow_registration) {
            this.showRegister();
          }
        } else if (err.error?.error === 'User not found') {
          this.error = 'No account found with this email.';
          if (this.authConfig?.allow_registration) {
            this.showRegister();
          }
        } else {
          this.error = err.error?.error || 'Authentication failed. Please try again.';
        }
      }
    });
  }

  quickPasskeyLogin(): void {
    this.isLoading = true;
    this.error = '';

    this.webAuthnService.authenticate().subscribe({
      next: () => {
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Authentication failed. Please try again.';
      }
    });
  }

  registerWithPasskey(): void {
    if (this.registerForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { email, name } = this.registerForm.value;

    this.webAuthnService.register(email, name).subscribe({
      next: () => {
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Registration failed. Please try again.';
      }
    });
  }

  adminLogin(): void {
    if (this.adminForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { username, password } = this.adminForm.value;

    this.http.post('/auth/local', { username, password }, { responseType: 'text' }).subscribe({
      next: () => {
        this.authService.loadCurrentUser();
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Invalid username or password';
      }
    });
  }

  showRegister(): void {
    this.currentView = 'register';
    this.error = '';
  }

  showWebAuthn(): void {
    this.currentView = 'webauthn';
    this.error = '';
  }

  showPasswordLogin(): void {
    this.currentView = 'password';
    this.error = '';
    this.passwordForm.patchValue({ email: this.currentEmail });
  }

  passwordLogin(): void {
    if (this.passwordForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const password = this.passwordForm.value.password;

    this.http.post<{ message: string; user?: any; redirect?: string }>('/api/auth/login', {
      email: this.currentEmail,
      password
    }).subscribe({
      next: (response) => {
        this.authService.loadCurrentUser();
        const domain = this.currentEmail.split('@')[1];
        this.router.navigate(['/' + domain + '/decisions']);
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Invalid email or password';
      }
    });
  }

  showRecovery(): void {
    this.currentView = 'recovery';
    this.error = '';
    this.success = '';
    // Pre-fill email if we have it
    if (this.currentEmail) {
      this.recoveryForm.patchValue({ email: this.currentEmail });
    }
  }

  requestRecovery(): void {
    if (this.recoveryForm.invalid) return;

    this.isLoading = true;
    this.error = '';
    this.success = '';

    const email = this.recoveryForm.value.email;

    this.http.post<{ message: string }>('/api/auth/request-recovery', { email }).subscribe({
      next: (response) => {
        this.isLoading = false;
        this.success = response.message;
      },
      error: (err) => {
        this.isLoading = false;
        // For security, we still show a success-like message
        this.success = err.error?.message || 'If an account exists with this email, a recovery link has been sent.';
      }
    });
  }

  goBack(): void {
    this.currentView = 'initial';
    this.error = '';
    this.success = '';
    this.authConfig = null;
    this.currentEmail = '';
  }
}
