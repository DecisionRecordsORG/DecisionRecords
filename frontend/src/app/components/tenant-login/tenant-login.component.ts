import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, ActivatedRoute, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDividerModule } from '@angular/material/divider';
import { MatTabsModule } from '@angular/material/tabs';
import { WebAuthnService } from '../../services/webauthn.service';
import { AuthService } from '../../services/auth.service';

interface TenantAuthConfig {
  domain: string;
  auth_method: string;
  allow_password: boolean;
  allow_passkey: boolean;
  allow_registration: boolean;
  has_sso: boolean;
  sso_provider: string | null;
  sso_id: number | null;
}

interface UserStatus {
  exists: boolean;
  has_passkey: boolean;
  has_password: boolean;
}

type LoginView = 'initial' | 'login' | 'request-access' | 'request-sent';

@Component({
  selector: 'app-tenant-login',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatDividerModule,
    MatTabsModule
  ],
  template: `
    <div class="login-container">
      <mat-card class="login-card">
        <mat-card-header>
          <mat-card-title>
            <mat-icon>business</mat-icon>
            {{ tenant }}
          </mat-card-title>
          <mat-card-subtitle>
            @if (currentView === 'initial') {
              Sign in to your organization
            } @else if (currentView === 'login') {
              Welcome back, {{ currentEmail }}
            } @else if (currentView === 'request-access') {
              Request access to join
            } @else {
              Request submitted
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

          <!-- Initial View: Email Entry -->
          @if (currentView === 'initial') {
            @if (authConfig?.has_sso && authConfig?.sso_id) {
              <div class="sso-section">
                <a [href]="'/auth/sso/' + authConfig!.sso_id" mat-raised-button color="primary" class="full-width">
                  <mat-icon>login</mat-icon>
                  Sign in with {{ authConfig!.sso_provider }}
                </a>
                <mat-divider></mat-divider>
                <p class="or-text">or continue with email</p>
              </div>
            }

            <form [formGroup]="emailForm" (ngSubmit)="checkUser()">
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Email</mat-label>
                <input matInput formControlName="email" type="email" [placeholder]="'you@' + tenant">
                <mat-icon matPrefix>email</mat-icon>
              </mat-form-field>

              <button mat-raised-button color="primary" type="submit"
                      [disabled]="emailForm.invalid || isLoading" class="full-width sign-in-button">
                <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                <mat-icon *ngIf="!isLoading">login</mat-icon>
                <span *ngIf="!isLoading">Sign In</span>
              </button>
            </form>
          }

          <!-- Login View: Passkey first (default), Password as alternative -->
          @if (currentView === 'login') {
            <div class="login-section">
              <p class="user-email">{{ currentEmail }}</p>

              <!-- Passkey Login (Primary) -->
              @if (authConfig?.allow_passkey && userStatus?.has_passkey && !showPasswordLogin) {
                <button mat-raised-button color="primary" class="full-width passkey-button"
                        (click)="signInWithPasskey()" [disabled]="isLoading">
                  <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                  <mat-icon *ngIf="!isLoading">fingerprint</mat-icon>
                  <span *ngIf="!isLoading">Sign in with passkey</span>
                </button>

                @if (authConfig?.allow_password && userStatus?.has_password) {
                  <button mat-button class="alt-login-button" (click)="showPasswordLogin = true">
                    <mat-icon>password</mat-icon>
                    Use password instead
                  </button>
                }
              }

              <!-- Password Login (Secondary) -->
              @if (showPasswordLogin || (!userStatus?.has_passkey && userStatus?.has_password)) {
                @if (authConfig?.allow_password && userStatus?.has_password) {
                  <form [formGroup]="loginForm" (ngSubmit)="loginWithPassword()">
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Password</mat-label>
                      <input matInput formControlName="password" type="password">
                      <mat-icon matPrefix>lock</mat-icon>
                    </mat-form-field>

                    <button mat-raised-button color="primary" type="submit"
                            [disabled]="loginForm.invalid || isLoading" class="full-width">
                      <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                      <mat-icon *ngIf="!isLoading">login</mat-icon>
                      <span *ngIf="!isLoading">Sign In</span>
                    </button>
                  </form>

                  @if (authConfig?.allow_passkey && userStatus?.has_passkey) {
                    <button mat-button class="alt-login-button" (click)="showPasswordLogin = false">
                      <mat-icon>fingerprint</mat-icon>
                      Use passkey instead (recommended)
                    </button>
                  }
                }
              }

              <!-- No credentials set up -->
              @if (!userStatus?.has_password && !userStatus?.has_passkey) {
                <div class="info-text warning">
                  <mat-icon>warning</mat-icon>
                  <span>
                    Your account doesn't have any login credentials set up yet.
                    Please contact your administrator.
                  </span>
                </div>
              }

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Use different email
              </button>
            </div>
          }

          <!-- Request Access View -->
          @if (currentView === 'request-access') {
            <div class="request-section">
              <p class="info-text">
                <mat-icon>info</mat-icon>
                You don't have an account with <strong>{{ tenant }}</strong> yet.
                Request access from your organization's administrator.
              </p>

              <form [formGroup]="requestForm" (ngSubmit)="submitAccessRequest()">
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

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Reason for Access (Optional)</mat-label>
                  <textarea matInput formControlName="reason" rows="3"
                            placeholder="Brief description of why you need access"></textarea>
                  <mat-icon matPrefix>message</mat-icon>
                </mat-form-field>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="requestForm.invalid || isLoading" class="full-width">
                  <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                  <mat-icon *ngIf="!isLoading">send</mat-icon>
                  <span *ngIf="!isLoading">Submit Request</span>
                </button>
              </form>

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Back
              </button>
            </div>
          }

          <!-- Request Sent View -->
          @if (currentView === 'request-sent') {
            <div class="request-sent-section">
              <mat-icon class="success-icon">check_circle</mat-icon>
              <h3>Request Submitted</h3>
              <p>
                Your access request has been sent to the administrator of <strong>{{ tenant }}</strong>.
                You'll receive an email once your request is approved.
              </p>
              <button mat-raised-button color="primary" routerLink="/">
                <mat-icon>home</mat-icon>
                Back to Home
              </button>
            </div>
          }
        </mat-card-content>

        @if (currentView === 'initial') {
          <mat-card-actions>
            <a mat-button routerLink="/">
              <mat-icon>arrow_back</mat-icon>
              Different Organization
            </a>
          </mat-card-actions>
        }
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
      max-width: 420px;
      padding: 24px;
    }

    mat-card-header {
      margin-bottom: 20px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 22px;
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

    .full-width {
      width: 100%;
    }

    mat-form-field {
      margin-bottom: 8px;
    }

    .sso-section {
      margin-bottom: 20px;
    }

    .or-text {
      text-align: center;
      color: #888;
      margin: 16px 0;
      font-size: 14px;
    }

    .login-buttons {
      display: flex;
      flex-direction: column;
    }

    .or-divider {
      display: flex;
      align-items: center;
      margin: 16px 0;
      color: #888;
      font-size: 14px;
    }

    .or-divider::before,
    .or-divider::after {
      content: '';
      flex: 1;
      border-bottom: 1px solid #ddd;
    }

    .or-divider span {
      padding: 0 12px;
    }

    .passkey-quick-login {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }

    .login-section, .request-section, .request-sent-section {
      text-align: center;
    }

    .login-section form {
      text-align: left;
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

    .login-divider {
      margin: 16px 0;
    }

    .back-button {
      margin-top: 16px;
    }

    .alt-login-button {
      margin-top: 12px;
      color: #666;
    }

    .info-text {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      font-size: 14px;
      color: #666;
      margin-bottom: 20px;
      padding: 12px;
      background: #e3f2fd;
      border-radius: 4px;
      text-align: left;
    }

    .info-text.warning {
      background: #fff3e0;
    }

    .info-text.warning mat-icon {
      color: #f57c00;
    }

    .info-text mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
      color: #1976d2;
    }

    .request-sent-section {
      padding: 24px 0;
    }

    .success-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #4caf50;
      margin-bottom: 16px;
    }

    .request-sent-section h3 {
      margin: 0 0 12px 0;
      color: #333;
    }

    .request-sent-section p {
      color: #666;
      margin-bottom: 24px;
    }

    mat-card-actions {
      display: flex;
      justify-content: center;
      padding: 16px;
    }

    .sign-in-button {
      padding: 12px 24px;
      font-size: 16px;
      margin-top: 8px;
    }
  `]
})
export class TenantLoginComponent implements OnInit {
  emailForm: FormGroup;
  loginForm: FormGroup;
  requestForm: FormGroup;

  tenant = '';
  authConfig: TenantAuthConfig | null = null;
  userStatus: UserStatus | null = null;
  currentEmail = '';
  currentView: LoginView = 'initial';

  isLoading = false;
  error = '';
  success = '';
  showPasswordLogin = false;  // Default to showing passkey

  webAuthnSupported = false;

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private router: Router,
    private route: ActivatedRoute,
    private webAuthnService: WebAuthnService,
    private authService: AuthService
  ) {
    this.emailForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]]
    });

    this.loginForm = this.fb.group({
      password: ['', Validators.required]
    });

    this.requestForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      name: ['', Validators.required],
      reason: ['']
    });
  }

  ngOnInit(): void {
    this.webAuthnSupported = this.webAuthnService.isWebAuthnSupported();
    this.tenant = this.route.snapshot.paramMap.get('tenant') || '';

    // Load tenant auth config
    this.loadAuthConfig();

    // Pre-fill email from query params
    const email = this.route.snapshot.queryParamMap.get('email');
    if (email) {
      this.emailForm.patchValue({ email });
    }

    // Check for verified param - show success message
    if (this.route.snapshot.queryParamMap.get('verified') === '1') {
      this.success = 'Email verified! You can now sign in.';
    }

    // Check for passkey setup success
    if (this.route.snapshot.queryParamMap.get('passkey_setup') === 'success') {
      this.success = 'Passkey created successfully! Sign in with your new passkey below.';
    }
  }

  loadAuthConfig(): void {
    this.http.get<TenantAuthConfig>(`/api/tenant/${this.tenant}/auth-config`).subscribe({
      next: (config) => {
        this.authConfig = config;
      },
      error: () => {
        // Use defaults
        this.authConfig = {
          domain: this.tenant,
          auth_method: 'local',
          allow_password: true,
          allow_passkey: true,
          allow_registration: true,
          has_sso: false,
          sso_provider: null,
          sso_id: null
        };
      }
    });
  }

  checkUser(): void {
    if (this.emailForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const email = this.emailForm.value.email.toLowerCase();
    const emailDomain = email.split('@')[1];

    // Validate email domain matches tenant
    if (emailDomain !== this.tenant) {
      this.error = `Please use an email address from ${this.tenant}`;
      this.isLoading = false;
      return;
    }

    this.currentEmail = email;

    // Check if user exists
    this.http.get<UserStatus>(`/api/auth/user-exists/${email}`).subscribe({
      next: (result) => {
        this.userStatus = result;
        if (result.exists) {
          // User exists - check if passkey-only, auto-trigger passkey auth
          if (result.has_passkey && !result.has_password && this.webAuthnSupported && this.authConfig?.allow_passkey) {
            // Passkey-only user: auto-trigger passkey auth immediately
            this.signInWithPasskey();
          } else if (result.has_passkey && this.webAuthnSupported && this.authConfig?.allow_passkey) {
            // User has both passkey and password - still auto-trigger passkey (preferred)
            this.signInWithPasskey();
          } else {
            // Password-only user or passkey not supported - show login view
            this.isLoading = false;
            this.currentView = 'login';
            this.showPasswordLogin = true;
          }
        } else {
          // User doesn't exist, show request access form
          this.isLoading = false;
          this.currentView = 'request-access';
          this.requestForm.patchValue({ email });
        }
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Failed to check user status';
      }
    });
  }

  loginWithPassword(): void {
    if (this.loginForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    this.http.post<{ message: string; user: any; redirect: string }>('/api/auth/login', {
      email: this.currentEmail,
      password: this.loginForm.value.password
    }).subscribe({
      next: (response) => {
        // Wait for user to be loaded before navigating
        this.authService.loadCurrentUser().subscribe({
          next: () => {
            this.router.navigate([response.redirect || `/${this.tenant}`]);
          },
          error: () => {
            // Still navigate even if loadCurrentUser fails - session is set
            this.router.navigate([response.redirect || `/${this.tenant}`]);
          }
        });
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Login failed. Please try again.';
      }
    });
  }

  signInWithPasskey(): void {
    this.isLoading = true;
    this.error = '';

    this.webAuthnService.authenticate(this.currentEmail).subscribe({
      next: () => {
        // Wait for user to be loaded before navigating
        this.authService.loadCurrentUser().subscribe({
          next: () => this.router.navigate([`/${this.tenant}`]),
          error: () => this.router.navigate([`/${this.tenant}`])
        });
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Authentication failed. Please try again.';
      }
    });
  }

  submitAccessRequest(): void {
    if (this.requestForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { email, name, reason } = this.requestForm.value;

    this.http.post('/api/auth/access-request', {
      email,
      name,
      reason,
      domain: this.tenant
    }).subscribe({
      next: () => {
        this.isLoading = false;
        this.currentView = 'request-sent';
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Failed to submit request. Please try again.';
      }
    });
  }

  goBack(): void {
    this.currentView = 'initial';
    this.error = '';
    this.userStatus = null;
    this.showPasswordLogin = false;
    this.loginForm.reset();
  }
}
