import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../services/auth.service';
import { FeatureFlagsService } from '../../services/feature-flags.service';

interface SystemStatus {
  has_tenants: boolean;
  tenant_count: number;
  has_super_admin: boolean;
  license_accepted: boolean;
  edition: string;
  is_community: boolean;
}

interface TenantInfo {
  id: number;
  sso_domain: string;
  company_name: string;
}

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    MatProgressSpinnerModule
  ],
  template: `
    <div class="landing-container">
      <div class="hero-section">
        <div class="hero-content">
          <h1>Decision Records</h1>
          <p class="tagline">Helping teams remember why decisions were made</p>
          <p class="description">
            An open source platform for capturing and preserving the reasoning behind
            important architecture decisions using the ADR format.
          </p>

          <!-- Loading State -->
          <div class="cta-section" *ngIf="loading">
            <mat-spinner diameter="40"></mat-spinner>
          </div>

          <!-- Community Edition: Fresh Install (No Tenants) -->
          <div class="cta-section" *ngIf="!loading && isCommunity && !hasTenants && !isLoggedIn">
            <div class="setup-cta">
              <button mat-raised-button class="primary-button large-button" (click)="goToSetup()">
                <mat-icon>rocket_launch</mat-icon>
                Set Up Your Instance
              </button>
              <p class="cta-hint">First time? Configure your organization in just a few steps.</p>
            </div>
          </div>

          <!-- Community Edition: Configured (Has Tenant) -->
          <div class="cta-section" *ngIf="!loading && isCommunity && hasTenants && !isLoggedIn">
            <div class="signin-cta">
              <button mat-raised-button class="primary-button large-button" (click)="goToSignIn()">
                <mat-icon>login</mat-icon>
                Sign In
              </button>
              <p class="cta-hint" *ngIf="tenantName">Sign in to {{ tenantName }}</p>
            </div>
          </div>

          <!-- Enterprise Edition: Domain Input -->
          <div class="cta-section" *ngIf="!loading && !isCommunity && !isLoggedIn">
            <div class="domain-input">
              <mat-form-field appearance="outline">
                <mat-label>Your company domain</mat-label>
                <input matInput [(ngModel)]="domain" placeholder="example.com"
                       (keyup.enter)="goToTenant()">
                <mat-hint>Enter your company domain to get started</mat-hint>
              </mat-form-field>
              <button mat-raised-button class="primary-button" (click)="goToTenant()" [disabled]="!domain">
                Get Started
              </button>
            </div>
            <p class="sign-in-link">
              Already have an account? Enter your domain above and click Get Started.
            </p>
          </div>

          <!-- Logged In State -->
          <div class="cta-section" *ngIf="!loading && isLoggedIn">
            <button mat-raised-button class="primary-button large-button" (click)="goToDashboard()">
              <mat-icon>dashboard</mat-icon>
              Go to Dashboard
            </button>
          </div>
        </div>
      </div>

      <div class="features-section">
        <h2>Core Features</h2>
        <div class="features-grid">
          <mat-card class="feature-card">
            <mat-icon>description</mat-icon>
            <h3>Decision Records</h3>
            <p>Capture decisions using a structured format with context, decision, and consequences.</p>
          </mat-card>

          <mat-card class="feature-card">
            <mat-icon>business</mat-icon>
            <h3>Multi-Tenant</h3>
            <p>Each organization gets their own isolated workspace based on email domain.</p>
          </mat-card>

          <mat-card class="feature-card">
            <mat-icon>fingerprint</mat-icon>
            <h3>Passkey Authentication</h3>
            <p>Secure passwordless login with WebAuthn/Passkeys and SSO support.</p>
          </mat-card>

          <mat-card class="feature-card">
            <mat-icon>security</mat-icon>
            <h3>Role-Based Access</h3>
            <p>Admins, stewards, and users with appropriate permissions for each role.</p>
          </mat-card>

          <mat-card class="feature-card">
            <mat-icon>history</mat-icon>
            <h3>Audit Logging</h3>
            <p>Complete history of all changes with who made them and when.</p>
          </mat-card>

          <mat-card class="feature-card">
            <mat-icon>folder</mat-icon>
            <h3>Spaces & Organization</h3>
            <p>Organize decisions into spaces for different teams or projects.</p>
          </mat-card>
        </div>
      </div>

      <div class="admin-section">
        <a routerLink="/superadmin" class="admin-link">
          <mat-icon>admin_panel_settings</mat-icon>
          Super Admin Login
        </a>
      </div>

      <footer class="landing-footer">
        <p>
          <a href="https://github.com/DecisionRecordsORG/DecisionRecords" target="_blank">
            <mat-icon>code</mat-icon> View on GitHub
          </a>
          &nbsp;|&nbsp;
          Licensed under BSL 1.1
        </p>
      </footer>
    </div>
  `,
  styles: [`
    .landing-container {
      min-height: 100vh;
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #1e40af 100%);
    }

    .hero-section {
      padding: 80px 20px;
      text-align: center;
      color: white;
    }

    .hero-content {
      max-width: 800px;
      margin: 0 auto;
    }

    h1 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 3.5rem;
      margin-bottom: 16px;
      font-weight: 700;
    }

    .tagline {
      font-family: 'Inter', sans-serif;
      font-size: 1.5rem;
      opacity: 0.9;
      margin-bottom: 24px;
    }

    .description {
      font-family: 'Inter', sans-serif;
      font-size: 1.1rem;
      opacity: 0.8;
      max-width: 600px;
      margin: 0 auto 40px;
      line-height: 1.6;
    }

    .cta-section {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
    }

    .setup-cta,
    .signin-cta {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
    }

    .cta-hint {
      font-size: 0.95rem;
      opacity: 0.85;
      margin: 0;
    }

    .primary-button {
      background: #3b82f6 !important;
      color: white !important;
      border-radius: 8px !important;
      font-weight: 500 !important;
      text-transform: none !important;
      letter-spacing: 0 !important;
    }

    .primary-button:hover {
      background: #2563eb !important;
    }

    .primary-button:disabled {
      background: rgba(255, 255, 255, 0.3) !important;
      color: rgba(255, 255, 255, 0.6) !important;
    }

    .large-button {
      padding: 12px 32px !important;
      font-size: 1.1rem !important;
      height: auto !important;
    }

    .large-button mat-icon {
      margin-right: 8px;
    }

    .domain-input {
      display: flex;
      gap: 16px;
      align-items: flex-start;
    }

    .domain-input mat-form-field {
      width: 300px;
    }

    .domain-input ::ng-deep .mat-mdc-text-field-wrapper {
      background: rgba(255, 255, 255, 0.95);
      border-radius: 8px;
    }

    .domain-input ::ng-deep .mat-mdc-form-field-subscript-wrapper {
      color: rgba(255, 255, 255, 0.8);
    }

    .features-section {
      padding: 60px 20px;
      background: #f8fafc;
    }

    .features-section h2 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      text-align: center;
      margin-bottom: 40px;
      color: #1e293b;
      font-size: 2rem;
    }

    .features-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 24px;
      max-width: 1200px;
      margin: 0 auto;
    }

    .feature-card {
      padding: 24px;
      text-align: center;
      border-radius: 12px !important;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
      transition: box-shadow 0.2s ease, transform 0.2s ease;
    }

    .feature-card:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
      transform: translateY(-2px);
    }

    .feature-card mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #3b82f6;
      margin-bottom: 16px;
    }

    .feature-card h3 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      margin-bottom: 12px;
      color: #1e293b;
      font-weight: 600;
    }

    .feature-card p {
      font-family: 'Inter', sans-serif;
      color: #64748b;
      line-height: 1.5;
    }

    .admin-section {
      padding: 40px 20px;
      text-align: center;
      background: #e2e8f0;
    }

    .admin-link {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #64748b;
      text-decoration: none;
      font-size: 0.9rem;
      font-family: 'Inter', sans-serif;
      transition: color 0.2s ease;
    }

    .admin-link:hover {
      color: #3b82f6;
    }

    .admin-link mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .landing-footer {
      padding: 24px 20px;
      text-align: center;
      background: #1e3a8a;
      color: white;
    }

    .landing-footer a {
      color: white;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-family: 'Inter', sans-serif;
    }

    .landing-footer a:hover {
      text-decoration: underline;
    }

    .landing-footer mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .sign-in-link {
      margin-top: 16px;
      font-size: 0.9rem;
      opacity: 0.8;
    }

    mat-spinner {
      margin: 20px auto;
    }

    ::ng-deep mat-spinner circle {
      stroke: white !important;
    }

    @media (max-width: 600px) {
      h1 {
        font-size: 2.5rem;
      }

      .tagline {
        font-size: 1.2rem;
      }

      .domain-input {
        flex-direction: column;
        width: 100%;
      }

      .domain-input mat-form-field {
        width: 100%;
      }

      .large-button {
        width: 100%;
        max-width: 300px;
      }
    }
  `]
})
export class LandingComponent implements OnInit {
  private authService = inject(AuthService);
  private router = inject(Router);
  private http = inject(HttpClient);
  private featureFlags = inject(FeatureFlagsService);

  domain = '';
  isLoggedIn = false;
  loading = true;
  isCommunity = false;
  hasTenants = false;
  tenantDomain = '';
  tenantName = '';

  ngOnInit() {
    // Check system status to determine what to show
    this.http.get<SystemStatus>('/api/system/status').subscribe({
      next: (status) => {
        this.isCommunity = status.is_community;
        this.hasTenants = status.has_tenants;

        // For Community Edition, check license first
        if (status.is_community && !status.license_accepted) {
          this.router.navigate(['/license']);
          return;
        }

        // If Community Edition has a single tenant, get its info for the Sign In button
        if (status.is_community && status.has_tenants) {
          this.loadTenantInfo();
        }

        this.loading = false;
      },
      error: () => {
        // Fallback to feature flags service if status endpoint fails
        this.isCommunity = this.featureFlags.isCommunity;
        this.loading = false;

        // Check license for Community Edition
        if (this.isCommunity) {
          this.http.get<{ accepted: boolean }>('/api/system/license').subscribe({
            next: (response) => {
              if (!response.accepted) {
                this.router.navigate(['/license']);
              }
            },
            error: () => {
              this.router.navigate(['/license']);
            }
          });
        }
      }
    });

    // Check auth state
    this.authService.currentUser$.subscribe(currentUser => {
      this.isLoggedIn = !!currentUser?.user;
      if (currentUser?.user && 'sso_domain' in currentUser.user) {
        this.domain = (currentUser.user as any).sso_domain || '';
      }
    });
  }

  private loadTenantInfo() {
    // Get tenant info for Community Edition (typically single tenant)
    this.http.get<TenantInfo[]>('/api/tenants/public').subscribe({
      next: (tenants) => {
        if (tenants && tenants.length > 0) {
          // Use the first (or only) tenant
          this.tenantDomain = tenants[0].sso_domain;
          this.tenantName = tenants[0].company_name || tenants[0].sso_domain;
        }
      },
      error: () => {
        // Silent fail - will just not show tenant name
      }
    });
  }

  goToSetup() {
    // Navigate to setup wizard for first-time Community Edition setup
    this.router.navigate(['/setup']);
  }

  goToSignIn() {
    if (this.tenantDomain) {
      // Navigate directly to the tenant's login page
      this.router.navigate(['/', this.tenantDomain, 'login']);
    } else {
      // Fallback to super admin if no tenant domain found
      this.router.navigate(['/superadmin']);
    }
  }

  goToTenant() {
    if (this.domain) {
      // Clean up domain - remove protocol, paths, etc.
      let cleanDomain = this.domain.toLowerCase().trim();
      cleanDomain = cleanDomain.replace(/^https?:\/\//, '');
      cleanDomain = cleanDomain.replace(/\/.*$/, '');
      cleanDomain = cleanDomain.replace(/^www\./, '');

      // Navigate to tenant login page (/:tenant/login)
      // The login page allows unauthenticated users (guestGuard)
      this.router.navigate(['/', cleanDomain, 'login']);
    }
  }

  goToDashboard() {
    if (this.domain) {
      this.router.navigate(['/', this.domain]);
    } else if (this.tenantDomain) {
      this.router.navigate(['/', this.tenantDomain]);
    }
  }
}
