import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterModule, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { TenantStatus, EmailVerificationResponse } from '../../models/decision.model';

type ViewState = 'email' | 'signup' | 'verification_sent' | 'access_request';

@Component({
  selector: 'app-landing',
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
    MatProgressSpinnerModule
  ],
  template: `
    <div class="landing-container">
      <div class="hero-section">
        <div class="hero-content">
          <mat-icon class="hero-icon">architecture</mat-icon>
          <h1>Architecture Decisions</h1>
          <p class="hero-subtitle">
            Document and track your architecture decisions using the arc42 format.
            Collaborate with your team and maintain a clear record of technical choices.
          </p>
        </div>
      </div>

      <mat-card class="signup-card">
        <mat-card-header>
          <mat-card-title>
            @if (currentView === 'verification_sent') {
              Check Your Email
            } @else if (currentView === 'access_request') {
              Request Access
            } @else {
              Get Started
            }
          </mat-card-title>
          <mat-card-subtitle>
            @if (currentView === 'email') {
              Enter your work email to sign up or sign in
            } @else if (currentView === 'signup') {
              Create your account
            } @else if (currentView === 'verification_sent') {
              We've sent you a verification link
            } @else if (currentView === 'access_request') {
              Request access to join your organization
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

          <!-- Email Entry View -->
          @if (currentView === 'email') {
            <form [formGroup]="emailForm" (ngSubmit)="checkEmail()">
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Work Email</mat-label>
                <input matInput formControlName="email" type="email" placeholder="you@company.com">
                <mat-icon matPrefix>email</mat-icon>
                <mat-hint>We'll use your email domain to set up your organization</mat-hint>
              </mat-form-field>

              <button mat-raised-button color="primary" type="submit"
                      [disabled]="emailForm.invalid || isLoading" class="full-width">
                @if (isLoading) {
                  <mat-spinner diameter="20"></mat-spinner>
                } @else {
                  Continue
                  <mat-icon>arrow_forward</mat-icon>
                }
              </button>
            </form>
          }

          <!-- Signup View (first user for domain) -->
          @if (currentView === 'signup') {
            <div class="tenant-info">
              <mat-icon>domain</mat-icon>
              <span>Setting up <strong>{{ tenantDomain }}</strong></span>
            </div>

            <form [formGroup]="signupForm" (ngSubmit)="sendVerification()">
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

              <p class="info-text">
                <mat-icon>info</mat-icon>
                <span>
                  You'll be the first user and administrator for <strong>{{ tenantDomain }}</strong>.
                  We'll send a verification email to confirm your identity.
                </span>
              </p>

              <button mat-raised-button color="primary" type="submit"
                      [disabled]="signupForm.invalid || isLoading" class="full-width">
                @if (isLoading) {
                  <mat-spinner diameter="20"></mat-spinner>
                } @else {
                  <mat-icon>mail</mat-icon>
                  Send Verification Email
                }
              </button>
            </form>

            <button mat-button class="back-button" (click)="goBack()">
              <mat-icon>arrow_back</mat-icon>
              Back
            </button>
          }

          <!-- Verification Email Sent View -->
          @if (currentView === 'verification_sent') {
            <div class="verification-sent">
              <div class="verification-icon">
                <mat-icon>mark_email_read</mat-icon>
              </div>
              <p>
                We've sent a verification link to <strong>{{ verificationEmail }}</strong>
              </p>
              <p class="small-text">
                Click the link in your email to verify your identity and complete registration.
                The link expires in 24 hours.
              </p>

              <div class="verification-actions">
                <button mat-stroked-button (click)="resendVerification()" [disabled]="isLoading || resendCooldown > 0">
                  @if (resendCooldown > 0) {
                    Resend in {{ resendCooldown }}s
                  } @else if (isLoading) {
                    <mat-spinner diameter="16"></mat-spinner>
                  } @else {
                    <mat-icon>refresh</mat-icon>
                    Resend Email
                  }
                </button>
              </div>

              <p class="help-text">
                <mat-icon>help</mat-icon>
                <span>Didn't receive the email? Check your spam folder or try a different email address.</span>
              </p>
            </div>

            <button mat-button class="back-button" (click)="goBack()">
              <mat-icon>arrow_back</mat-icon>
              Try Different Email
            </button>
          }

          <!-- Access Request View (for existing tenants requiring approval) -->
          @if (currentView === 'access_request') {
            <div class="tenant-info">
              <mat-icon>business</mat-icon>
              <span><strong>{{ tenantDomain }}</strong> already has users</span>
            </div>

            <form [formGroup]="accessRequestForm" (ngSubmit)="sendAccessRequestVerification()">
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
                <textarea matInput formControlName="reason" placeholder="Why do you need access?"
                          rows="3"></textarea>
                <mat-icon matPrefix>note</mat-icon>
              </mat-form-field>

              <p class="info-text warning">
                <mat-icon>security</mat-icon>
                <span>
                  For security, your organization admin must approve your access request.
                  We'll send you a verification email first to confirm your identity.
                </span>
              </p>

              <button mat-raised-button color="primary" type="submit"
                      [disabled]="accessRequestForm.invalid || isLoading" class="full-width">
                @if (isLoading) {
                  <mat-spinner diameter="20"></mat-spinner>
                } @else {
                  <mat-icon>mail</mat-icon>
                  Verify Email & Request Access
                }
              </button>
            </form>

            <button mat-button class="back-button" (click)="goBack()">
              <mat-icon>arrow_back</mat-icon>
              Back
            </button>
          }
        </mat-card-content>
      </mat-card>

      <div class="features-section">
        <div class="feature">
          <mat-icon>description</mat-icon>
          <h3>Document Decisions</h3>
          <p>Record architectural decisions with context, rationale, and consequences</p>
        </div>
        <div class="feature">
          <mat-icon>people</mat-icon>
          <h3>Team Collaboration</h3>
          <p>Share decisions with your team and track who made changes</p>
        </div>
        <div class="feature">
          <mat-icon>history</mat-icon>
          <h3>Version History</h3>
          <p>Keep track of how decisions evolved over time</p>
        </div>
        <div class="feature">
          <mat-icon>notifications</mat-icon>
          <h3>Stay Informed</h3>
          <p>Get notified when decisions are created or updated</p>
        </div>
      </div>

      <footer class="landing-footer">
        <small>
          Architecture Decision Records - Based on
          <a href="https://docs.arc42.org/section-9/" target="_blank" rel="noopener">arc42 Section 9</a>
          <span class="separator">|</span>
          Created by Lawrance Nyakiso
        </small>
      </footer>
    </div>
  `,
  styles: [`
    .landing-container {
      min-height: 100vh;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }

    .hero-section {
      padding: 60px 20px 40px;
      text-align: center;
      color: white;
    }

    .hero-content {
      max-width: 600px;
      margin: 0 auto;
    }

    .hero-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      margin-bottom: 16px;
    }

    .hero-section h1 {
      font-size: 36px;
      font-weight: 300;
      margin: 0 0 16px 0;
    }

    .hero-subtitle {
      font-size: 16px;
      opacity: 0.9;
      line-height: 1.6;
    }

    .signup-card {
      max-width: 440px;
      margin: 0 auto 40px;
      padding: 24px;
    }

    mat-card-header {
      margin-bottom: 16px;
    }

    mat-card-title {
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

    .full-width {
      width: 100%;
    }

    mat-form-field {
      margin-bottom: 8px;
    }

    .tenant-info {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px;
      background: #f5f5f5;
      border-radius: 4px;
      margin-bottom: 16px;
      color: #666;
    }

    .info-text {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      font-size: 13px;
      color: #666;
      margin: 16px 0;
      padding: 12px;
      background: #e3f2fd;
      border-radius: 4px;
    }

    .info-text.warning {
      background: #fff3e0;
    }

    .info-text.warning mat-icon {
      color: #e65100;
    }

    .info-text mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #1976d2;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .back-button {
      margin-top: 16px;
    }

    .verification-sent {
      text-align: center;
      padding: 16px 0;
    }

    .verification-icon {
      margin-bottom: 16px;
    }

    .verification-icon mat-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #4caf50;
    }

    .verification-sent p {
      margin: 0 0 16px 0;
      font-size: 16px;
    }

    .small-text {
      font-size: 14px !important;
      color: #666;
    }

    .verification-actions {
      margin: 24px 0;
    }

    .help-text {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-size: 12px;
      color: #888;
      margin-top: 24px;
    }

    .help-text mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    .features-section {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 24px;
      max-width: 900px;
      margin: 0 auto;
      padding: 40px 20px;
    }

    .feature {
      text-align: center;
      color: white;
    }

    .feature mat-icon {
      font-size: 40px;
      width: 40px;
      height: 40px;
      margin-bottom: 12px;
      opacity: 0.9;
    }

    .feature h3 {
      margin: 0 0 8px 0;
      font-weight: 500;
    }

    .feature p {
      margin: 0;
      font-size: 14px;
      opacity: 0.8;
    }

    .landing-footer {
      text-align: center;
      padding: 24px;
      color: rgba(255, 255, 255, 0.8);
    }

    .landing-footer a {
      color: white;
    }

    .separator {
      margin: 0 8px;
    }
  `]
})
export class LandingComponent implements OnInit {
  emailForm: FormGroup;
  signupForm: FormGroup;
  accessRequestForm: FormGroup;

  currentView: ViewState = 'email';
  tenantDomain = '';
  tenantStatus: TenantStatus | null = null;
  verificationEmail = '';

  isLoading = false;
  error = '';
  success = '';
  resendCooldown = 0;

  private cooldownInterval: ReturnType<typeof setInterval> | null = null;

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private router: Router,
    private route: ActivatedRoute
  ) {
    this.emailForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]]
    });

    this.signupForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      name: ['', Validators.required]
    });

    this.accessRequestForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      name: ['', Validators.required],
      reason: ['']
    });
  }

  ngOnInit(): void {
    // Check for error query params
    this.route.queryParams.subscribe(params => {
      if (params['error'] === 'invalid_token') {
        this.error = 'Invalid verification link. Please try again.';
      } else if (params['error'] === 'expired_token') {
        this.error = 'Verification link has expired. Please request a new one.';
      }
    });
  }

  checkEmail(): void {
    if (this.emailForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const email = this.emailForm.value.email.toLowerCase();
    const domain = email.split('@')[1];

    if (!domain) {
      this.error = 'Invalid email address';
      this.isLoading = false;
      return;
    }

    this.tenantDomain = domain;

    // Check tenant status
    this.http.get<TenantStatus>(`/api/auth/tenant/${domain}`).subscribe({
      next: (status) => {
        this.tenantStatus = status;
        this.isLoading = false;

        // If email verification is disabled, redirect directly to tenant login
        if (!status.email_verification_required) {
          this.router.navigate([`/${domain}/login`], {
            queryParams: { email }
          });
          return;
        }

        if (status.has_users) {
          // Tenant exists - check if approval is required
          if (status.require_approval) {
            // Show access request form
            this.currentView = 'access_request';
            this.accessRequestForm.patchValue({ email });
          } else {
            // Auto-signup allowed, redirect to tenant login
            this.router.navigate([`/${domain}/login`], {
              queryParams: { email }
            });
          }
        } else {
          // New tenant, show signup form
          this.currentView = 'signup';
          this.signupForm.patchValue({ email });
        }
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Failed to check domain status';
      }
    });
  }

  sendVerification(): void {
    if (this.signupForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { email, name } = this.signupForm.value;

    this.http.post<EmailVerificationResponse>('/api/auth/send-verification', {
      email,
      name,
      purpose: 'signup'
    }).subscribe({
      next: (response) => {
        this.isLoading = false;
        this.verificationEmail = email;
        this.currentView = 'verification_sent';
        this.startCooldown();
      },
      error: (err) => {
        this.isLoading = false;
        if (err.error?.redirect) {
          // User already exists, redirect to login
          this.router.navigate([err.error.redirect]);
        } else {
          this.error = err.error?.error || 'Failed to send verification email';
        }
      }
    });
  }

  sendAccessRequestVerification(): void {
    if (this.accessRequestForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { email, name, reason } = this.accessRequestForm.value;

    this.http.post<EmailVerificationResponse>('/api/auth/send-verification', {
      email,
      name,
      purpose: 'access_request',
      reason
    }).subscribe({
      next: (response) => {
        this.isLoading = false;
        this.verificationEmail = email;
        this.currentView = 'verification_sent';
        this.startCooldown();
      },
      error: (err) => {
        this.isLoading = false;
        if (err.error?.redirect) {
          this.router.navigate([err.error.redirect]);
        } else {
          this.error = err.error?.error || 'Failed to send verification email';
        }
      }
    });
  }

  resendVerification(): void {
    if (this.resendCooldown > 0 || this.isLoading) return;

    this.isLoading = true;
    this.error = '';

    const formData = this.signupForm.value.email
      ? this.signupForm.value
      : this.accessRequestForm.value;

    this.http.post<EmailVerificationResponse>('/api/auth/send-verification', {
      email: formData.email,
      name: formData.name,
      purpose: this.tenantStatus?.has_users ? 'access_request' : 'signup',
      reason: this.accessRequestForm.value.reason
    }).subscribe({
      next: () => {
        this.isLoading = false;
        this.success = 'Verification email sent!';
        this.startCooldown();
        setTimeout(() => this.success = '', 3000);
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Failed to resend verification email';
      }
    });
  }

  private startCooldown(): void {
    this.resendCooldown = 60;
    if (this.cooldownInterval) {
      clearInterval(this.cooldownInterval);
    }
    this.cooldownInterval = setInterval(() => {
      this.resendCooldown--;
      if (this.resendCooldown <= 0 && this.cooldownInterval) {
        clearInterval(this.cooldownInterval);
        this.cooldownInterval = null;
      }
    }, 1000);
  }

  goBack(): void {
    this.currentView = 'email';
    this.error = '';
    this.success = '';
    this.tenantStatus = null;
    this.verificationEmail = '';
  }
}
