import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '../../services/auth.service';

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
    MatIconModule
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

          <div class="cta-section">
            <div class="domain-input" *ngIf="!isLoggedIn">
              <mat-form-field appearance="outline">
                <mat-label>Your company domain</mat-label>
                <input matInput [(ngModel)]="domain" placeholder="example.com"
                       (keyup.enter)="goToTenant()">
              </mat-form-field>
              <button mat-raised-button color="primary" (click)="goToTenant()">
                Get Started
              </button>
            </div>
            <div *ngIf="isLoggedIn">
              <button mat-raised-button color="primary" (click)="goToDashboard()">
                Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="features-section">
        <h2>Core Features</h2>
        <div class="features-grid">
          <mat-card class="feature-card">
            <mat-icon>description</mat-icon>
            <h3>Architecture Decision Records</h3>
            <p>Capture decisions using the proven ADR format with context, decision, and consequences.</p>
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
          <a href="https://github.com/decisionrecords/decision-records" target="_blank">
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
      background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
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
      font-size: 3.5rem;
      margin-bottom: 16px;
      font-weight: 700;
    }

    .tagline {
      font-size: 1.5rem;
      opacity: 0.9;
      margin-bottom: 24px;
    }

    .description {
      font-size: 1.1rem;
      opacity: 0.8;
      max-width: 600px;
      margin: 0 auto 40px;
      line-height: 1.6;
    }

    .cta-section {
      display: flex;
      justify-content: center;
      gap: 16px;
      flex-wrap: wrap;
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
      background: white;
      border-radius: 4px;
    }

    .features-section {
      padding: 60px 20px;
      background: #f5f5f5;
    }

    .features-section h2 {
      text-align: center;
      margin-bottom: 40px;
      color: #333;
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
    }

    .feature-card mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #1e3a5f;
      margin-bottom: 16px;
    }

    .feature-card h3 {
      margin-bottom: 12px;
      color: #333;
    }

    .feature-card p {
      color: #666;
      line-height: 1.5;
    }

    .admin-section {
      padding: 40px 20px;
      text-align: center;
      background: #e8e8e8;
    }

    .admin-link {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #666;
      text-decoration: none;
      font-size: 0.9rem;
    }

    .admin-link:hover {
      color: #1e3a5f;
    }

    .admin-link mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .landing-footer {
      padding: 24px 20px;
      text-align: center;
      background: #1e3a5f;
      color: white;
    }

    .landing-footer a {
      color: white;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }

    .landing-footer a:hover {
      text-decoration: underline;
    }

    .landing-footer mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
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
    }
  `]
})
export class LandingComponent implements OnInit {
  private authService = inject(AuthService);
  private router = inject(Router);

  domain = '';
  isLoggedIn = false;

  ngOnInit() {
    this.authService.currentUser$.subscribe(currentUser => {
      this.isLoggedIn = !!currentUser?.user;
      if (currentUser?.user && 'sso_domain' in currentUser.user) {
        this.domain = (currentUser.user as any).sso_domain || '';
      }
    });
  }

  goToTenant() {
    if (this.domain) {
      // Clean up domain - remove protocol, paths, etc.
      let cleanDomain = this.domain.toLowerCase().trim();
      cleanDomain = cleanDomain.replace(/^https?:\/\//, '');
      cleanDomain = cleanDomain.replace(/\/.*$/, '');
      cleanDomain = cleanDomain.replace(/^www\./, '');

      this.router.navigate(['/', cleanDomain]);
    }
  }

  goToDashboard() {
    if (this.domain) {
      this.router.navigate(['/', this.domain]);
    }
  }
}
