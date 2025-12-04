import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDividerModule } from '@angular/material/divider';
import { WebAuthnService } from '../../services/webauthn.service';

interface TenantStatus {
  domain: string;
  has_users: boolean;
  user_count: number;
  auth_method: 'sso' | 'webauthn';
  allow_registration: boolean;
  has_sso: boolean;
  sso_provider: string | null;
  sso_id: number | null;
}

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
    MatProgressSpinnerModule,
    MatDividerModule
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
          <mat-card-title>Get Started</mat-card-title>
          <mat-card-subtitle>
            @if (currentView === 'email') {
              Enter your work email to sign up or sign in
            } @else if (currentView === 'signup') {
              Create your account
            } @else {
              Complete your registration
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

            <form [formGroup]="signupForm" (ngSubmit)="signup()">
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
                You'll be the first user and administrator for <strong>{{ tenantDomain }}</strong>.
                Use a passkey (fingerprint, face, or security key) to secure your account.
              </p>

              <button mat-raised-button color="primary" type="submit"
                      [disabled]="signupForm.invalid || isLoading" class="full-width">
                @if (isLoading) {
                  <mat-spinner diameter="20"></mat-spinner>
                } @else {
                  <mat-icon>fingerprint</mat-icon>
                  Create Account with Passkey
                }
              </button>
            </form>

            <button mat-button class="back-button" (click)="goBack()">
              <mat-icon>arrow_back</mat-icon>
              Back
            </button>
          }
        </mat-card-content>

        <mat-divider></mat-divider>

        <mat-card-actions>
          <a mat-button routerLink="/superadmin" class="admin-link">
            <mat-icon>admin_panel_settings</mat-icon>
            Super Admin Login
          </a>
        </mat-card-actions>
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

    .info-text mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #1976d2;
    }

    .back-button {
      margin-top: 16px;
    }

    mat-card-actions {
      display: flex;
      justify-content: center;
      padding: 16px;
    }

    .admin-link {
      color: #666;
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
export class LandingComponent {
  emailForm: FormGroup;
  signupForm: FormGroup;

  currentView: 'email' | 'signup' = 'email';
  tenantDomain = '';
  tenantStatus: TenantStatus | null = null;

  isLoading = false;
  error = '';
  success = '';

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private router: Router,
    private webAuthnService: WebAuthnService
  ) {
    this.emailForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]]
    });

    this.signupForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      name: ['', Validators.required]
    });
  }

  checkEmail(): void {
    if (this.emailForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const email = this.emailForm.value.email;
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

        if (status.has_users) {
          // Tenant has users, redirect to tenant login
          this.router.navigate([`/${domain}/login`], {
            queryParams: { email }
          });
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

  signup(): void {
    if (this.signupForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { email, name } = this.signupForm.value;

    this.webAuthnService.register(email, name).subscribe({
      next: () => {
        // Registration successful, redirect to tenant dashboard
        this.router.navigate([`/${this.tenantDomain}`]);
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Registration failed. Please try again.';
      }
    });
  }

  goBack(): void {
    this.currentView = 'email';
    this.error = '';
    this.tenantStatus = null;
  }
}
