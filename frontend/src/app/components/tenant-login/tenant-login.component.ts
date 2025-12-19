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
  allow_slack_oidc: boolean;
  allow_google_oauth: boolean;
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

type LoginView = 'initial' | 'login' | 'request-access' | 'request-sent' | 'auto-approved' | 'recovery' | 'resend-verification' | 'access-pending';

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
            } @else if (currentView === 'recovery') {
              Reset your credentials
            } @else if (currentView === 'resend-verification') {
              Resend verification email
            } @else if (currentView === 'access-pending') {
              Awaiting approval
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

            <form [formGroup]="emailForm" (ngSubmit)="checkUser()" data-testid="email-form">
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Email</mat-label>
                <input matInput formControlName="email" type="email" [placeholder]="'you@' + tenant" data-testid="email-input">
                <mat-icon matPrefix>email</mat-icon>
              </mat-form-field>

              <button mat-raised-button color="primary" type="submit"
                      [disabled]="emailForm.invalid || isLoading" class="full-width sign-in-button" data-testid="continue-button">
                <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                <mat-icon *ngIf="!isLoading">login</mat-icon>
                <span *ngIf="!isLoading">Sign In</span>
              </button>
            </form>

            <!-- Social Sign-in Options -->
            @if ((slackOidcEnabled && authConfig?.allow_slack_oidc) || (googleOauthEnabled && authConfig?.allow_google_oauth)) {
              <div class="social-divider">
                <span>or</span>
              </div>

              @if (slackOidcEnabled && authConfig?.allow_slack_oidc) {
                <button mat-stroked-button class="slack-signin-btn full-width" (click)="signInWithSlack()">
                  <img src="/assets/slack-logo.svg" alt="Slack" class="slack-logo">
                  <span>Sign in with Slack</span>
                </button>
              }

              @if (googleOauthEnabled && authConfig?.allow_google_oauth) {
                <button mat-stroked-button class="google-signin-btn full-width" (click)="signInWithGoogle()">
                  <img src="/assets/google-logo.svg" alt="Google" class="google-logo">
                  <span>Sign in with Google</span>
                </button>
              }
            }

            <p class="resend-link">
              <button mat-button (click)="showResendVerification()">
                <mat-icon>mark_email_unread</mat-icon>
                Didn't receive verification email?
              </button>
            </p>
          }

          <!-- Login View: Passkey first (default), Password as alternative -->
          @if (currentView === 'login') {
            <div class="login-section" data-testid="login-view">
              <p class="user-email" data-testid="current-email">{{ currentEmail }}</p>

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
                  <form [formGroup]="loginForm" (ngSubmit)="loginWithPassword()" data-testid="password-form">
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Password</mat-label>
                      <input matInput formControlName="password" type="password" data-testid="password-input">
                      <mat-icon matPrefix>lock</mat-icon>
                    </mat-form-field>

                    <button mat-raised-button color="primary" type="submit"
                            [disabled]="loginForm.invalid || isLoading" class="full-width" data-testid="login-button">
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
                    Please check your email for a setup link.
                  </span>
                </div>
                <button mat-raised-button color="accent" class="full-width resend-setup-btn"
                        (click)="requestSetupLink()" [disabled]="isLoading">
                  <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                  <mat-icon *ngIf="!isLoading">send</mat-icon>
                  <span *ngIf="!isLoading">Resend Setup Link</span>
                </button>
              }

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Use different email
              </button>

              <p class="recovery-link">
                <button mat-button (click)="showRecovery()">
                  <mat-icon>lock_reset</mat-icon>
                  Forgot your credentials?
                </button>
              </p>
            </div>
          }

          <!-- Recovery View -->
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
                  <input matInput formControlName="email" type="email" [placeholder]="'you@' + tenant">
                  <mat-icon matPrefix>email</mat-icon>
                </mat-form-field>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="recoveryForm.invalid || isLoading" class="full-width">
                  <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                  <mat-icon *ngIf="!isLoading">send</mat-icon>
                  <span *ngIf="!isLoading">Send Recovery Link</span>
                </button>
              </form>

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Back to Sign In
              </button>
            </div>
          }

          <!-- Resend Verification View -->
          @if (currentView === 'resend-verification') {
            <div class="resend-section">
              <div class="resend-icon">
                <mat-icon>mark_email_unread</mat-icon>
              </div>
              <p class="resend-description">
                Enter your email address and we'll send a new verification link. Links expire after 2 hours.
              </p>

              <form [formGroup]="resendForm" (ngSubmit)="resendVerification()">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Email</mat-label>
                  <input matInput formControlName="email" type="email" [placeholder]="'you@' + tenant">
                  <mat-icon matPrefix>email</mat-icon>
                </mat-form-field>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="resendForm.invalid || isLoading" class="full-width">
                  <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                  <mat-icon *ngIf="!isLoading">send</mat-icon>
                  <span *ngIf="!isLoading">Resend Verification Link</span>
                </button>
              </form>

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Back to Sign In
              </button>
            </div>
          }

          <!-- Request Access View -->
          @if (currentView === 'request-access') {
            <div class="request-section">
              <p class="info-text">
                <mat-icon>info</mat-icon>
                <span>You don't have an account with <strong>{{ tenant }}</strong> yet. Request access to join your organisation.</span>
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
                Your access request has been submitted for <strong>{{ tenant }}</strong>.
                You'll receive an email once your request is approved.
              </p>
              <button mat-raised-button color="primary" routerLink="/">
                <mat-icon>home</mat-icon>
                Back to Home
              </button>
            </div>
          }

          @if (currentView === 'auto-approved') {
            <div class="request-sent-section">
              <mat-icon class="success-icon">email</mat-icon>
              <h3>Account Created!</h3>
              <p>
                Your account has been created for <strong>{{ tenant }}</strong>.
                Check your email for a link to set up your login credentials.
              </p>
              <button mat-raised-button color="primary" routerLink="/">
                <mat-icon>home</mat-icon>
                Back to Home
              </button>
            </div>
          }

          <!-- Access Pending View - shown after email verification when admin approval required -->
          @if (currentView === 'access-pending') {
            <div class="request-sent-section">
              <mat-icon class="pending-icon">hourglass_top</mat-icon>
              <h3>Email Verified!</h3>
              <p>
                Your email has been verified and your access request for <strong>{{ tenant }}</strong> has been submitted.
              </p>
              <p class="pending-note">
                An administrator will review your request. You'll receive an email once approved.
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
      flex-shrink: 0;
    }

    .info-text span {
      flex: 1;
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

    .pending-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #ff9800;
      margin-bottom: 16px;
    }

    .pending-note {
      font-size: 14px;
      color: #888;
      margin-top: 8px;
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

    /* Slack Sign-in Button Styles */
    .social-divider {
      display: flex;
      align-items: center;
      gap: 16px;
      margin: 20px 0;
      color: #94a3b8;
      font-size: 13px;
      text-transform: lowercase;
    }

    .social-divider::before,
    .social-divider::after {
      content: '';
      flex: 1;
      height: 1px;
      background: #e2e8f0;
    }

    .slack-signin-btn {
      display: flex !important;
      align-items: center;
      justify-content: center;
      gap: 12px;
      padding: 12px 24px !important;
      border: 1px solid #e2e8f0 !important;
      border-radius: 8px !important;
      background: #fff !important;
      color: #1e293b !important;
      font-weight: 500 !important;
      font-size: 14px !important;
      transition: all 0.2s ease !important;
      height: auto !important;
      min-height: 48px;
    }

    .slack-signin-btn:hover {
      background: #f8fafc !important;
      border-color: #cbd5e1 !important;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }

    .slack-signin-btn .slack-logo {
      width: 20px;
      height: 20px;
    }

    .slack-signin-btn span {
      display: inline-block;
    }

    /* Google Sign-in Button Styles - Following Google Brand Guidelines */
    .google-signin-btn {
      display: flex !important;
      align-items: center;
      justify-content: center;
      gap: 12px;
      padding: 12px 24px !important;
      border: 1px solid #dadce0 !important;
      border-radius: 4px !important;
      background: #fff !important;
      color: #3c4043 !important;
      font-weight: 500 !important;
      font-size: 14px !important;
      font-family: 'Google Sans', Roboto, Arial, sans-serif !important;
      transition: all 0.2s ease !important;
      height: auto !important;
      min-height: 48px;
      margin-top: 8px;
    }

    .google-signin-btn:hover {
      background: #f8f9fa !important;
      border-color: #dadce0 !important;
      box-shadow: 0 1px 3px rgba(60, 64, 67, 0.3);
    }

    .google-signin-btn .google-logo {
      width: 20px;
      height: 20px;
    }

    .google-signin-btn span {
      display: inline-block;
    }

    .recovery-link {
      margin-top: 24px;
      text-align: center;
    }

    .recovery-link button {
      color: #666;
      font-size: 14px;
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
    }

    .resend-section {
      text-align: center;
    }

    .resend-icon {
      margin-bottom: 16px;
    }

    .resend-icon mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #ff9800;
    }

    .resend-description {
      color: #666;
      margin-bottom: 24px;
    }

    .resend-link {
      margin-top: 16px;
      text-align: center;
    }

    .resend-link button {
      color: #666;
      font-size: 14px;
    }

    .resend-setup-btn {
      margin-top: 16px;
      padding: 12px 24px;
      font-size: 14px;
    }
  `]
})
export class TenantLoginComponent implements OnInit {
  emailForm: FormGroup;
  loginForm: FormGroup;
  requestForm: FormGroup;
  recoveryForm: FormGroup;
  resendForm: FormGroup;

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
  slackOidcEnabled = false;  // Global Slack OIDC availability
  googleOauthEnabled = false;  // Global Google OAuth availability

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

    this.recoveryForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]]
    });

    this.resendForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]]
    });
  }

  ngOnInit(): void {
    this.webAuthnSupported = this.webAuthnService.isWebAuthnSupported();
    this.tenant = this.route.snapshot.paramMap.get('tenant') || '';

    // Load tenant auth config
    this.loadAuthConfig();

    // Check global Slack OIDC availability
    this.checkSlackOidcStatus();

    // Check global Google OAuth availability
    this.checkGoogleOauthStatus();

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

    // Check for access_requested param - show access pending view
    if (this.route.snapshot.queryParamMap.get('access_requested') === '1') {
      this.currentView = 'access-pending';
    }

    // Check for OAuth auth errors
    const errorParam = this.route.snapshot.queryParamMap.get('error');
    if (errorParam === 'slack_auth_error') {
      this.error = 'Slack authentication failed. Please try again.';
    } else if (errorParam === 'google_auth_error') {
      this.error = 'Google authentication failed. Please try again.';
    } else if (errorParam === 'public_email') {
      this.error = this.route.snapshot.queryParamMap.get('message') || 'Please use your work email address.';
    }
  }

  private checkSlackOidcStatus(): void {
    this.http.get<{ enabled: boolean }>('/api/auth/slack-oidc-status').subscribe({
      next: (response) => {
        this.slackOidcEnabled = response.enabled;
      },
      error: () => {
        this.slackOidcEnabled = false;
      }
    });
  }

  signInWithSlack(): void {
    // Include return URL to redirect back to tenant after login
    const returnUrl = `/${this.tenant}/decisions`;
    window.location.href = `/auth/slack/oidc?return_url=${encodeURIComponent(returnUrl)}`;
  }

  private checkGoogleOauthStatus(): void {
    this.http.get<{ enabled: boolean }>('/api/auth/google-status').subscribe({
      next: (response) => {
        this.googleOauthEnabled = response.enabled;
      },
      error: () => {
        this.googleOauthEnabled = false;
      }
    });
  }

  signInWithGoogle(): void {
    // Include return URL to redirect back to tenant after login
    const returnUrl = `/${this.tenant}/decisions`;
    window.location.href = `/auth/google?return_url=${encodeURIComponent(returnUrl)}`;
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
          allow_slack_oidc: true,
          allow_google_oauth: true,
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
        // Show login view so user can see recovery options
        this.currentView = 'login';
        this.error = err.error?.error || 'Authentication failed. Please try again or use account recovery.';
      }
    });
  }

  submitAccessRequest(): void {
    if (this.requestForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { email, name, reason } = this.requestForm.value;

    this.http.post<{message: string; auto_approved?: boolean; email?: string; domain?: string}>('/api/auth/access-request', {
      email,
      name,
      reason,
      domain: this.tenant
    }).subscribe({
      next: (response) => {
        this.isLoading = false;
        // Check if auto-approved (account created immediately)
        if (response.auto_approved) {
          this.currentView = 'auto-approved';
        } else {
          this.currentView = 'request-sent';
        }
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
    this.success = '';
    this.userStatus = null;
    this.showPasswordLogin = false;
    this.loginForm.reset();
    this.recoveryForm.reset();
    this.resendForm.reset();
  }

  showRecovery(): void {
    this.currentView = 'recovery';
    this.error = '';
    this.success = '';
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
        // Always show success message to prevent email enumeration
        this.success = err.error?.message || 'If an account exists with this email, a recovery link has been sent.';
      }
    });
  }

  showResendVerification(): void {
    this.currentView = 'resend-verification';
    this.error = '';
    this.success = '';
    if (this.currentEmail) {
      this.resendForm.patchValue({ email: this.currentEmail });
    }
  }

  resendVerification(): void {
    if (this.resendForm.invalid) return;

    this.isLoading = true;
    this.error = '';
    this.success = '';

    const email = this.resendForm.value.email;

    this.http.post<{ message: string }>('/api/auth/resend-verification', { email }).subscribe({
      next: (response) => {
        this.isLoading = false;
        this.success = response.message;
      },
      error: (err) => {
        this.isLoading = false;
        // Always show success message to prevent email enumeration
        this.success = err.error?.message || 'If a pending verification exists for this email, a new link has been sent.';
      }
    });
  }

  requestSetupLink(): void {
    if (!this.currentEmail) return;

    this.isLoading = true;
    this.error = '';
    this.success = '';

    this.http.post<{ message: string }>('/api/auth/request-setup-link', { email: this.currentEmail }).subscribe({
      next: (response) => {
        this.isLoading = false;
        this.success = response.message || 'If your account exists, a setup link has been sent to your email.';
      },
      error: (err) => {
        this.isLoading = false;
        // Always show success message to prevent email enumeration
        this.success = err.error?.message || 'If your account exists, a setup link has been sent to your email.';
      }
    });
  }
}
