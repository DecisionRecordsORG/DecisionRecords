import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-teams-integration',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="teams-page">
      <!-- Hero Section -->
      <header class="teams-hero">
        <div class="container">
          <div class="hero-content">
            <div class="hero-badge">
              <img src="/assets/teams-logo.svg" alt="Teams" class="teams-icon" />
              <span>+</span>
              <img src="/assets/decision-records-logo-white.svg" alt="Decision Records" class="dr-icon" />
            </div>
            <h1>Decision Records for Microsoft Teams</h1>
            <p class="hero-tagline">
              Capture architecture decisions where your team already collaborates
            </p>
            <div class="hero-cta">
              <a routerLink="/admin" fragment="teams"
                 class="teams-install-button">
                <img src="/assets/teams-logo.svg" alt="" class="btn-icon" />
                <span>Connect Teams</span>
              </a>
              <p class="install-hint">Free for your organisation</p>
            </div>
          </div>
        </div>
      </header>

      <!-- Features Section -->
      <section class="features-section">
        <div class="container">
          <h2>What you can do with Decision Records in Teams</h2>

          <div class="features-grid">
            <div class="feature-card">
              <div class="feature-icon">
                <mat-icon>add_circle</mat-icon>
              </div>
              <h3>Create Decisions from Messages</h3>
              <p>
                Turn any Teams message into a decision record with message extensions. Capture the context while it's still fresh.
              </p>
            </div>

            <div class="feature-card">
              <div class="feature-icon">
                <mat-icon>search</mat-icon>
              </div>
              <h3>Search Past Decisions</h3>
              <p>
                Use &#64;DecisionRecords commands to quickly find and share past decisions without leaving Teams. No more digging through channels.
              </p>
            </div>

            <div class="feature-card">
              <div class="feature-icon">
                <mat-icon>notifications</mat-icon>
              </div>
              <h3>Stay Updated</h3>
              <p>
                Get notified when decisions are created, updated, or superseded. Keep your team aligned on the latest choices.
              </p>
            </div>

            <div class="feature-card">
              <div class="feature-icon">
                <mat-icon>link</mat-icon>
              </div>
              <h3>Link Your Account</h3>
              <p>
                Connect your Microsoft identity to Decision Records for seamless single sign-on and attribution.
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- How It Works -->
      <section class="how-it-works">
        <div class="container">
          <h2>How It Works</h2>

          <div class="steps">
            <div class="step">
              <div class="step-number">1</div>
              <div class="step-content">
                <h3>Install the App</h3>
                <p>Add Decision Records to your Teams workspace. Admins can control which teams and channels have access.</p>
              </div>
            </div>

            <div class="step">
              <div class="step-number">2</div>
              <div class="step-content">
                <h3>Connect Your Organisation</h3>
                <p>Link your Microsoft 365 tenant to your Decision Records organisation. This enables seamless user mapping.</p>
              </div>
            </div>

            <div class="step">
              <div class="step-number">3</div>
              <div class="step-content">
                <h3>Start Capturing Decisions</h3>
                <p>Use <code>&#64;DecisionRecords</code> commands or message extensions to create and find decisions directly in Teams.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Commands Section -->
      <section class="commands-section">
        <div class="container">
          <h2>Teams Commands</h2>

          <div class="commands-grid">
            <div class="command-card">
              <code>&#64;DecisionRecords create</code>
              <p>Create a new decision record</p>
            </div>
            <div class="command-card">
              <code>&#64;DecisionRecords search [query]</code>
              <p>Search for existing decisions</p>
            </div>
            <div class="command-card">
              <code>&#64;DecisionRecords list</code>
              <p>Show recent decisions in your space</p>
            </div>
            <div class="command-card">
              <code>&#64;DecisionRecords help</code>
              <p>Get help with available commands</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Security Section -->
      <section class="security-section">
        <div class="container">
          <div class="security-content">
            <mat-icon>security</mat-icon>
            <div>
              <h2>Enterprise-Ready Security</h2>
              <p>
                Decision Records for Teams is built with enterprise security in mind. We use Azure AD single sign-on, and all data is encrypted in transit and at rest.
              </p>
              <ul>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>Azure AD Single Sign-On</span>
                </li>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>Data encrypted at rest and in transit</span>
                </li>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>Minimal permission scopes requested</span>
                </li>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>Admin controls for tenant access</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- CTA Section -->
      <section class="cta-section">
        <div class="container">
          <h2>Ready to capture decisions in Teams?</h2>
          <p>Install the app and start preserving your team's decision context</p>
          <a routerLink="/admin" fragment="teams"
             class="teams-install-button">
            <img src="/assets/teams-logo.svg" alt="" class="btn-icon" />
            <span>Connect Teams</span>
          </a>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .teams-page {
      min-height: 100vh;
      background: #f8fafc;
    }

    .container {
      max-width: 1000px;
      margin: 0 auto;
      padding: 0 24px;
    }

    /* Hero */
    .teams-hero {
      background: linear-gradient(135deg, #5558AF 0%, #6264A7 50%, #5558AF 100%);
      color: white;
      padding: 100px 0 80px;
    }

    .back-link {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: rgba(255, 255, 255, 0.8);
      text-decoration: none;
      font-size: 0.9rem;
      margin-bottom: 40px;
      transition: color 0.2s;
    }

    .back-link:hover {
      color: white;
    }

    .back-link mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .hero-content {
      text-align: center;
      max-width: 600px;
      margin: 0 auto;
    }

    .hero-badge {
      display: inline-flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 24px;
      padding: 12px 24px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 100px;
    }

    .hero-badge span {
      font-size: 1.5rem;
      color: rgba(255, 255, 255, 0.6);
    }

    .teams-icon {
      width: 40px;
      height: 40px;
    }

    .dr-icon {
      height: 32px;
      width: auto;
    }

    .teams-hero h1 {
      font-size: 2.75rem;
      font-weight: 700;
      margin: 0 0 16px;
      letter-spacing: -0.02em;
    }

    .hero-tagline {
      font-size: 1.25rem;
      color: rgba(255, 255, 255, 0.85);
      margin: 0 0 32px;
      line-height: 1.5;
    }

    .hero-cta {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
    }

    .teams-install-button {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      padding: 14px 32px;
      background: white;
      color: #1D1C1D;
      font-size: 1.1rem;
      font-weight: 600;
      border-radius: 8px;
      text-decoration: none;
      transition: all 0.2s;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }

    .teams-install-button:hover {
      background: #f8f8f8;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    .teams-install-button .btn-icon {
      width: 24px;
      height: 24px;
    }

    .install-hint {
      font-size: 0.9rem;
      color: rgba(255, 255, 255, 0.7);
      margin: 0;
    }

    /* Features */
    .features-section {
      padding: 80px 0;
    }

    .features-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .features-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
    }

    .feature-card {
      background: white;
      padding: 28px;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
    }

    .feature-icon {
      width: 48px;
      height: 48px;
      background: linear-gradient(135deg, #5558AF 0%, #6264A7 100%);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
    }

    .feature-icon mat-icon {
      color: white;
      font-size: 24px;
      width: 24px;
      height: 24px;
    }

    .feature-card h3 {
      font-size: 1.15rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
    }

    .feature-card p {
      font-size: 0.95rem;
      color: #64748b;
      line-height: 1.6;
      margin: 0;
    }

    /* How It Works */
    .how-it-works {
      padding: 80px 0;
      background: #f1f5f9;
    }

    .how-it-works h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .steps {
      max-width: 600px;
      margin: 0 auto;
    }

    .step {
      display: flex;
      gap: 24px;
      margin-bottom: 32px;
    }

    .step:last-child {
      margin-bottom: 0;
    }

    .step-number {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, #5558AF 0%, #6264A7 100%);
      color: white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 1.1rem;
      flex-shrink: 0;
    }

    .step-content h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
    }

    .step-content p {
      font-size: 0.95rem;
      color: #64748b;
      line-height: 1.6;
      margin: 0;
    }

    .step-content code {
      background: #e2e8f0;
      padding: 2px 8px;
      border-radius: 4px;
      font-family: 'Fira Code', monospace;
      font-size: 0.9em;
    }

    /* Commands */
    .commands-section {
      padding: 80px 0;
    }

    .commands-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .commands-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
    }

    .command-card {
      background: #1e293b;
      padding: 20px 24px;
      border-radius: 12px;
    }

    .command-card code {
      display: block;
      font-family: 'Fira Code', monospace;
      font-size: 1rem;
      color: #22d3ee;
      margin-bottom: 8px;
    }

    .command-card p {
      font-size: 0.9rem;
      color: #94a3b8;
      margin: 0;
    }

    /* Security */
    .security-section {
      padding: 80px 0;
      background: #f1f5f9;
    }

    .security-content {
      display: flex;
      gap: 32px;
      align-items: flex-start;
      max-width: 700px;
      margin: 0 auto;
    }

    .security-content > mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #5558AF;
      flex-shrink: 0;
    }

    .security-content h2 {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 12px;
    }

    .security-content > div > p {
      font-size: 1rem;
      color: #64748b;
      line-height: 1.6;
      margin: 0 0 20px;
    }

    .security-content ul {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .security-content li {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 0.95rem;
      color: #334155;
      margin-bottom: 12px;
    }

    .security-content li mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
      color: #22c55e;
    }

    /* CTA */
    .cta-section {
      padding: 80px 0;
      text-align: center;
    }

    .cta-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 12px;
    }

    .cta-section p {
      font-size: 1.1rem;
      color: #64748b;
      margin: 0 0 32px;
    }

    /* Footer */
    .teams-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 24px;
      text-align: center;
    }

    .teams-footer p {
      margin: 0;
      font-size: 0.9rem;
    }

    @media (max-width: 768px) {
      .teams-hero {
        padding: 32px 0 60px;
      }

      .teams-hero h1 {
        font-size: 2rem;
      }

      .hero-tagline {
        font-size: 1.1rem;
      }

      .features-section,
      .how-it-works,
      .commands-section,
      .security-section,
      .cta-section {
        padding: 60px 0;
      }

      .features-grid,
      .commands-grid {
        grid-template-columns: 1fr;
      }

      .security-content {
        flex-direction: column;
        text-align: center;
      }

      .security-content > mat-icon {
        margin: 0 auto;
      }

      .security-content li {
        justify-content: center;
      }
    }
  `]
})
export class TeamsIntegrationComponent {}
