import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

interface SecurityFeature {
  title: string;
  description: string;
  icon: string;
  benefits: string[];
}

@Component({
  selector: 'app-security',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="security-page">
      <!-- Header -->
      <header class="security-header">
        <div class="container">
          <div class="header-content">
            <div class="header-text">
              <h1>Security & Privacy</h1>
              <p class="header-subtitle">
                Simple by default. Configurable when you need it.
              </p>
            </div>
            <div class="header-visual">
              <!-- Shield SVG -->
              <svg viewBox="0 0 200 200" class="header-svg">
                <defs>
                  <linearGradient id="shieldGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#60a5fa;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#3b82f6;stop-opacity:1" />
                  </linearGradient>
                </defs>
                <path d="M100 20 L170 50 L170 100 C170 145 140 175 100 190 C60 175 30 145 30 100 L30 50 Z"
                      fill="url(#shieldGradient)" opacity="0.9"/>
                <path d="M100 35 L155 58 L155 100 C155 138 130 163 100 175 C70 163 45 138 45 100 L45 58 Z"
                      fill="none" stroke="white" stroke-width="2" opacity="0.5"/>
                <path d="M75 100 L90 115 L130 75" fill="none" stroke="white" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
        </div>
      </header>

      <!-- Content -->
      <main class="security-content">
        <div class="container">
          <p class="intro">
            Decision Records is built with organisations of all sizes in mind. Our approach to security prioritises simplicity and minimal user friction. For teams without dedicated IT departments, everything should feel intuitive and secure by default. For enterprises requiring greater control over authentication, we provide flexible configuration options. Privacy is woven into the foundation of the platform.
          </p>
          <p class="intro intro-secondary">
            We take a deliberately flat approach to decision visibility. Rather than layering bureaucratic access rules that work against the very purpose of shared knowledge, decisions are accessible across your organisation by design. Security should enable collaboration, not hinder it.
          </p>

          <!-- Feature Sections -->
          <section class="feature-section">
            <div class="feature-visual">
              <!-- Authentication Lock SVG -->
              <svg viewBox="0 0 240 180" class="feature-svg">
                <rect x="60" y="80" width="120" height="90" rx="8" fill="#e2e8f0"/>
                <rect x="70" y="90" width="100" height="70" rx="4" fill="#f8fafc"/>
                <circle cx="120" cy="60" r="40" fill="none" stroke="#3b82f6" stroke-width="12"/>
                <rect x="114" y="80" width="12" height="30" fill="#3b82f6"/>
                <circle cx="120" cy="125" r="8" fill="#3b82f6"/>
                <rect x="116" y="125" width="8" height="20" fill="#3b82f6"/>
              </svg>
            </div>
            <div class="feature-content">
              <h2>Flexible Authentication</h2>
              <p>
                Control exactly how your team members sign in. Enable or disable authentication methods based on your organization's security requirements and user preferences.
              </p>
              <ul class="feature-benefits">
                <li>
                  <mat-icon>fingerprint</mat-icon>
                  <span><strong>Passkeys (WebAuthn)</strong> — Phishing-resistant passwordless authentication</span>
                </li>
                <li>
                  <mat-icon>key</mat-icon>
                  <span><strong>Traditional Passwords</strong> — Optional password-based login with secure hashing</span>
                </li>
                <li>
                  <mat-icon>login</mat-icon>
                  <span><strong>Sign in with Google</strong> — Leverage your existing Google Workspace identity</span>
                </li>
                <li>
                  <mat-icon>chat</mat-icon>
                  <span><strong>Sign in with Slack</strong> — Seamless authentication for Slack-first teams</span>
                </li>
              </ul>
            </div>
          </section>

          <section class="feature-section reverse">
            <div class="feature-visual">
              <!-- Role hierarchy SVG -->
              <svg viewBox="0 0 240 180" class="feature-svg">
                <!-- Admin at top -->
                <circle cx="120" cy="30" r="20" fill="#3b82f6"/>
                <text x="120" y="35" text-anchor="middle" fill="white" font-size="12" font-weight="bold">A</text>

                <!-- Steward level -->
                <line x1="120" y1="50" x2="80" y2="75" stroke="#94a3b8" stroke-width="2"/>
                <line x1="120" y1="50" x2="160" y2="75" stroke="#94a3b8" stroke-width="2"/>
                <circle cx="80" cy="90" r="16" fill="#60a5fa"/>
                <text x="80" y="95" text-anchor="middle" fill="white" font-size="10" font-weight="bold">S</text>
                <circle cx="160" cy="90" r="16" fill="#60a5fa"/>
                <text x="160" y="95" text-anchor="middle" fill="white" font-size="10" font-weight="bold">S</text>

                <!-- Contributors -->
                <line x1="80" y1="106" x2="50" y2="125" stroke="#94a3b8" stroke-width="2"/>
                <line x1="80" y1="106" x2="110" y2="125" stroke="#94a3b8" stroke-width="2"/>
                <line x1="160" y1="106" x2="130" y2="125" stroke="#94a3b8" stroke-width="2"/>
                <line x1="160" y1="106" x2="190" y2="125" stroke="#94a3b8" stroke-width="2"/>

                <circle cx="50" cy="140" r="12" fill="#93c5fd"/>
                <text x="50" y="144" text-anchor="middle" fill="white" font-size="9">C</text>
                <circle cx="110" cy="140" r="12" fill="#93c5fd"/>
                <text x="110" y="144" text-anchor="middle" fill="white" font-size="9">C</text>
                <circle cx="130" cy="140" r="12" fill="#93c5fd"/>
                <text x="130" y="144" text-anchor="middle" fill="white" font-size="9">C</text>
                <circle cx="190" cy="140" r="12" fill="#93c5fd"/>
                <text x="190" y="144" text-anchor="middle" fill="white" font-size="9">C</text>

                <!-- Legend -->
                <text x="120" y="175" text-anchor="middle" fill="#64748b" font-size="10">Role Hierarchy</text>
              </svg>
            </div>
            <div class="feature-content">
              <h2>Role-Based Access Control</h2>
              <p>
                Define who can do what with a clear, hierarchical role system. Assign roles based on responsibility and ensure proper separation of duties.
              </p>
              <ul class="feature-benefits">
                <li>
                  <mat-icon>admin_panel_settings</mat-icon>
                  <span><strong>Administrators</strong> — Full tenant control including settings, users, and roles</span>
                </li>
                <li>
                  <mat-icon>supervisor_account</mat-icon>
                  <span><strong>Stewards</strong> — Manage decisions and promote contributors</span>
                </li>
                <li>
                  <mat-icon>edit_note</mat-icon>
                  <span><strong>Contributors</strong> — Create and edit decisions within their spaces</span>
                </li>
                <li>
                  <mat-icon>visibility</mat-icon>
                  <span><strong>Users</strong> — Read-only access to view decisions</span>
                </li>
              </ul>
            </div>
          </section>

          <section class="feature-section">
            <div class="feature-visual">
              <!-- Audit log SVG -->
              <svg viewBox="0 0 240 180" class="feature-svg">
                <rect x="40" y="20" width="160" height="140" rx="8" fill="#f1f5f9" stroke="#e2e8f0" stroke-width="2"/>

                <!-- Log entries -->
                <rect x="55" y="35" width="130" height="24" rx="4" fill="white" stroke="#e2e8f0"/>
                <circle cx="70" cy="47" r="6" fill="#22c55e"/>
                <rect x="82" y="42" width="80" height="4" rx="2" fill="#94a3b8"/>
                <rect x="82" y="50" width="50" height="3" rx="1" fill="#cbd5e1"/>

                <rect x="55" y="65" width="130" height="24" rx="4" fill="white" stroke="#e2e8f0"/>
                <circle cx="70" cy="77" r="6" fill="#3b82f6"/>
                <rect x="82" y="72" width="70" height="4" rx="2" fill="#94a3b8"/>
                <rect x="82" y="80" width="60" height="3" rx="1" fill="#cbd5e1"/>

                <rect x="55" y="95" width="130" height="24" rx="4" fill="white" stroke="#e2e8f0"/>
                <circle cx="70" cy="107" r="6" fill="#f59e0b"/>
                <rect x="82" y="102" width="90" height="4" rx="2" fill="#94a3b8"/>
                <rect x="82" y="110" width="45" height="3" rx="1" fill="#cbd5e1"/>

                <rect x="55" y="125" width="130" height="24" rx="4" fill="white" stroke="#e2e8f0"/>
                <circle cx="70" cy="137" r="6" fill="#22c55e"/>
                <rect x="82" y="132" width="75" height="4" rx="2" fill="#94a3b8"/>
                <rect x="82" y="140" width="55" height="3" rx="1" fill="#cbd5e1"/>
              </svg>
            </div>
            <div class="feature-content">
              <h2>Immutable Audit Logs</h2>
              <p>
                Every administrative action is recorded in a tamper-proof audit log. Track who did what and when, ensuring complete accountability and compliance readiness.
              </p>
              <ul class="feature-benefits">
                <li>
                  <mat-icon>history</mat-icon>
                  <span><strong>Complete History</strong> — Track user promotions, demotions, and role changes</span>
                </li>
                <li>
                  <mat-icon>settings</mat-icon>
                  <span><strong>Settings Changes</strong> — Record all configuration modifications</span>
                </li>
                <li>
                  <mat-icon>approval</mat-icon>
                  <span><strong>Request Actions</strong> — Log all approval and rejection decisions</span>
                </li>
                <li>
                  <mat-icon>lock</mat-icon>
                  <span><strong>Immutable Records</strong> — Audit entries cannot be modified or deleted</span>
                </li>
              </ul>
            </div>
          </section>

          <section class="feature-section reverse">
            <div class="feature-visual">
              <!-- Registration gate SVG -->
              <svg viewBox="0 0 240 180" class="feature-svg">
                <!-- Gate structure -->
                <rect x="80" y="40" width="80" height="120" rx="4" fill="#f1f5f9" stroke="#e2e8f0" stroke-width="2"/>

                <!-- Gate bars -->
                <rect x="95" y="60" width="4" height="80" fill="#94a3b8"/>
                <rect x="118" y="60" width="4" height="80" fill="#94a3b8"/>
                <rect x="141" y="60" width="4" height="80" fill="#94a3b8"/>

                <!-- Top bar -->
                <rect x="85" y="55" width="70" height="8" rx="2" fill="#64748b"/>

                <!-- Lock -->
                <circle cx="120" cy="45" r="12" fill="#3b82f6"/>
                <rect x="116" y="40" width="8" height="12" fill="#f1f5f9"/>

                <!-- User trying to enter -->
                <circle cx="50" cy="100" r="12" fill="#60a5fa"/>
                <ellipse cx="50" cy="130" rx="10" ry="14" fill="#60a5fa"/>

                <!-- Checkmark/approval -->
                <circle cx="190" cy="90" r="20" fill="#22c55e" opacity="0.2"/>
                <circle cx="190" cy="90" r="14" fill="#22c55e"/>
                <path d="M182 90 L187 96 L198 84" fill="none" stroke="white" stroke-width="3" stroke-linecap="round"/>
              </svg>
            </div>
            <div class="feature-content">
              <h2>Registration Controls</h2>
              <p>
                Decide who can join your tenant. Enable open registration, require admin approval for new users, or restrict access entirely to invitation-only.
              </p>
              <ul class="feature-benefits">
                <li>
                  <mat-icon>person_add</mat-icon>
                  <span><strong>Self-Registration</strong> — Allow users to sign up directly</span>
                </li>
                <li>
                  <mat-icon>pending_actions</mat-icon>
                  <span><strong>Approval Required</strong> — Review and approve each new user request</span>
                </li>
                <li>
                  <mat-icon>block</mat-icon>
                  <span><strong>Closed Registration</strong> — Disable new user signups entirely</span>
                </li>
                <li>
                  <mat-icon>email</mat-icon>
                  <span><strong>Role Requests</strong> — Let users request elevated permissions with justification</span>
                </li>
              </ul>
            </div>
          </section>

          <section class="feature-section">
            <div class="feature-visual">
              <!-- Tenant isolation SVG -->
              <svg viewBox="0 0 240 180" class="feature-svg">
                <!-- First tenant bubble -->
                <ellipse cx="80" cy="90" rx="55" ry="65" fill="#dbeafe" stroke="#3b82f6" stroke-width="2"/>
                <circle cx="65" cy="70" r="10" fill="#3b82f6"/>
                <circle cx="95" cy="75" r="8" fill="#60a5fa"/>
                <circle cx="75" cy="100" r="9" fill="#60a5fa"/>
                <circle cx="85" cy="125" r="7" fill="#93c5fd"/>
                <text x="80" y="155" text-anchor="middle" fill="#3b82f6" font-size="10" font-weight="bold">Tenant A</text>

                <!-- Second tenant bubble -->
                <ellipse cx="160" cy="90" rx="55" ry="65" fill="#fce7f3" stroke="#ec4899" stroke-width="2"/>
                <circle cx="145" cy="70" r="10" fill="#ec4899"/>
                <circle cx="175" cy="75" r="8" fill="#f472b6"/>
                <circle cx="155" cy="100" r="9" fill="#f472b6"/>
                <circle cx="165" cy="125" r="7" fill="#f9a8d4"/>
                <text x="160" y="155" text-anchor="middle" fill="#ec4899" font-size="10" font-weight="bold">Tenant B</text>

                <!-- Barrier line -->
                <line x1="120" y1="25" x2="120" y2="165" stroke="#e2e8f0" stroke-width="3" stroke-dasharray="8,4"/>
              </svg>
            </div>
            <div class="feature-content">
              <h2>Complete Tenant Isolation</h2>
              <p>
                Each organization operates in its own isolated tenant. Data, users, and configurations are completely separated, ensuring no cross-tenant data leakage.
              </p>
              <ul class="feature-benefits">
                <li>
                  <mat-icon>security</mat-icon>
                  <span><strong>Data Isolation</strong> — Decisions and users are completely separated per tenant</span>
                </li>
                <li>
                  <mat-icon>tune</mat-icon>
                  <span><strong>Independent Settings</strong> — Each tenant has its own authentication configuration</span>
                </li>
                <li>
                  <mat-icon>workspaces</mat-icon>
                  <span><strong>Spaces Organization</strong> — Further organize decisions within your tenant</span>
                </li>
                <li>
                  <mat-icon>domain</mat-icon>
                  <span><strong>Custom Domain Identity</strong> — Your tenant is identified by your organization domain</span>
                </li>
              </ul>
            </div>
          </section>

          <!-- Trust Section -->
          <section class="trust-section">
            <h2>Built on Trust</h2>
            <div class="trust-grid">
              <div class="trust-card">
                <mat-icon>https</mat-icon>
                <h3>HTTPS Everywhere</h3>
                <p>All data is encrypted in transit with TLS 1.3</p>
              </div>
              <div class="trust-card">
                <mat-icon>storage</mat-icon>
                <h3>Encrypted at Rest</h3>
                <p>Data is encrypted using industry-standard algorithms</p>
              </div>
              <div class="trust-card">
                <mat-icon>cloud</mat-icon>
                <h3>Azure Hosted</h3>
                <p>Deployed on Microsoft Azure's secure infrastructure</p>
              </div>
              <div class="trust-card">
                <mat-icon>gpp_good</mat-icon>
                <h3>Privacy First</h3>
                <p>GDPR-ready with minimal data collection</p>
              </div>
            </div>
          </section>

          <!-- CTA Section -->
          <div class="cta-section">
            <h3>Ready to start recording decisions?</h3>
            <p>Security and privacy included from day one</p>
            <button mat-raised-button class="cta-button" routerLink="/">
              <mat-icon>rocket_launch</mat-icon>
              <span>Get Started Free</span>
            </button>
          </div>
        </div>
      </main>
    </div>
  `,
  styles: [`
    .security-page {
      min-height: 100vh;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
    }

    .security-header {
      background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #1d4ed8 100%);
      color: white;
      padding: 100px 24px 60px;
    }

    .container {
      max-width: 1100px;
      margin: 0 auto;
    }

    .header-content {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 48px;
    }

    .header-text {
      flex: 1;
    }

    .security-header h1 {
      font-size: 2.5rem;
      font-weight: 700;
      margin: 0 0 16px;
      letter-spacing: -0.02em;
    }

    .header-subtitle {
      font-size: 1.25rem;
      color: rgba(255, 255, 255, 0.85);
      margin: 0;
      line-height: 1.5;
    }

    .header-visual {
      flex-shrink: 0;
    }

    .header-svg {
      width: 160px;
      height: 160px;
    }

    .security-content {
      flex: 1;
      padding: 60px 24px;
    }

    .intro {
      font-size: 1.2rem;
      color: #475569;
      line-height: 1.7;
      margin: 0 0 24px;
      max-width: 800px;
    }

    .intro.intro-secondary {
      margin-bottom: 64px;
      font-size: 1.1rem;
      color: #64748b;
    }

    /* Feature Sections */
    .feature-section {
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 48px;
      align-items: center;
      margin-bottom: 72px;
      padding: 40px;
      background: white;
      border-radius: 20px;
      border: 1px solid #e2e8f0;
    }

    .feature-section.reverse {
      grid-template-columns: 1fr 280px;
    }

    .feature-section.reverse .feature-visual {
      order: 2;
    }

    .feature-section.reverse .feature-content {
      order: 1;
    }

    .feature-visual {
      display: flex;
      align-items: center;
      justify-content: center;
      background: #f8fafc;
      border-radius: 16px;
      padding: 24px;
    }

    .feature-svg {
      width: 100%;
      max-width: 240px;
      height: auto;
    }

    .feature-content h2 {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 16px;
      letter-spacing: -0.01em;
    }

    .feature-content > p {
      font-size: 1.05rem;
      color: #64748b;
      line-height: 1.7;
      margin: 0 0 24px;
    }

    .feature-benefits {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .feature-benefits li {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 14px;
      font-size: 0.95rem;
      color: #475569;
      line-height: 1.5;
    }

    .feature-benefits mat-icon {
      color: #3b82f6;
      font-size: 20px;
      width: 20px;
      height: 20px;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .feature-benefits strong {
      color: #1e293b;
    }

    /* Trust Section */
    .trust-section {
      margin-bottom: 64px;
      text-align: center;
    }

    .trust-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 32px;
    }

    .trust-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 20px;
    }

    .trust-card {
      background: white;
      padding: 28px 20px;
      border-radius: 12px;
      border: 1px solid #e2e8f0;
      text-align: center;
    }

    .trust-card mat-icon {
      font-size: 36px;
      width: 36px;
      height: 36px;
      color: #3b82f6;
      margin-bottom: 12px;
    }

    .trust-card h3 {
      font-size: 1rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
    }

    .trust-card p {
      font-size: 0.9rem;
      color: #64748b;
      margin: 0;
      line-height: 1.5;
    }

    /* CTA Section */
    .cta-section {
      text-align: center;
      padding: 48px;
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #1e40af 100%);
      border-radius: 20px;
    }

    .cta-section h3 {
      font-size: 1.5rem;
      font-weight: 600;
      color: white;
      margin: 0 0 8px;
    }

    .cta-section p {
      font-size: 1.05rem;
      color: rgba(255, 255, 255, 0.85);
      margin: 0 0 24px;
    }

    .cta-button {
      padding: 14px 32px !important;
      font-size: 16px !important;
      font-weight: 500 !important;
      border-radius: 100px !important;
      background: white !important;
      color: #1e40af !important;
    }

    .cta-button mat-icon {
      margin-right: 8px;
    }

    /* Responsive */
    @media (max-width: 900px) {
      .header-content {
        flex-direction: column;
        text-align: center;
      }

      .header-svg {
        width: 120px;
        height: 120px;
      }

      .feature-section,
      .feature-section.reverse {
        grid-template-columns: 1fr;
        gap: 32px;
        padding: 32px;
      }

      .feature-section.reverse .feature-visual,
      .feature-section.reverse .feature-content {
        order: unset;
      }

      .feature-visual {
        max-width: 280px;
        margin: 0 auto;
      }

      .trust-grid {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    @media (max-width: 600px) {
      .security-header {
        padding: 32px 16px 48px;
      }

      .security-header h1 {
        font-size: 1.75rem;
      }

      .header-subtitle {
        font-size: 1rem;
      }

      .security-content {
        padding: 40px 16px;
      }

      .intro {
        font-size: 1.05rem;
        margin-bottom: 48px;
      }

      .feature-section {
        padding: 24px;
        margin-bottom: 48px;
      }

      .feature-content h2 {
        font-size: 1.25rem;
      }

      .trust-grid {
        grid-template-columns: 1fr;
      }

      .cta-section {
        padding: 32px 24px;
      }

      .cta-section h3 {
        font-size: 1.25rem;
      }
    }
  `]
})
export class SecurityComponent {}
