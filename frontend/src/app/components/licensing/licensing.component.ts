import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-licensing',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="licensing-page">
      <!-- Header -->
      <header class="licensing-header">
        <div class="container">
          <a routerLink="/" class="back-link">
            <mat-icon>arrow_back</mat-icon>
            <span>Back to Home</span>
          </a>
          <h1>License Model</h1>
          <p class="subtitle">Open, transparent, and sustainable — today and in the future</p>
        </div>
      </header>

      <!-- Content -->
      <main class="licensing-content">
        <div class="container">
          <article class="prose">
            <p class="lead">
              This project is built on the belief that architecture decisions should be open, portable, and preserved for the long term. To stay true to this mission, we operate with a simple and transparent licensing approach.
            </p>

            <section class="license-section">
              <h2><span class="section-number">1</span> The core platform will always be free and open</h2>
              <p>
                The foundational capabilities of the platform — the ability to create, store, browse, and share architecture decisions — will remain available at no cost.
              </p>
              <p>Our intention is that:</p>
              <ul>
                <li>Anyone can use the platform without paying</li>
                <li>The open-source version will remain free to self-host</li>
                <li>No one will lose access to their existing decisions or data</li>
              </ul>
            </section>

            <section class="license-section">
              <h2><span class="section-number">2</span> A self-hosted version will always be available</h2>
              <p>
                We believe organisations should never be locked into a single hosting provider.
              </p>
              <p>
                We will release and maintain an open-source, self-hosted edition that includes the essential features needed to run the platform privately.
              </p>
              <p>This ensures:</p>
              <ul>
                <li>Full control over your own data</li>
                <li>No dependency on us for hosting</li>
                <li>The ability to operate the platform independently, forever</li>
              </ul>
            </section>

            <section class="license-section">
              <h2><span class="section-number">3</span> The hosted cloud service may introduce paid plans</h2>
              <p>
                To sustain the project and fund infrastructure, the cloud-hosted version may introduce:
              </p>
              <ul>
                <li>A free tier for individuals, students, and small teams</li>
                <li>Usage-based paid plans for larger teams and enterprises</li>
                <li>Optional upgrades (e.g., SSO, advanced audit logs, increased storage)</li>
              </ul>
              <p>
                This allows us to grow sustainably without taking anything away from existing users.
              </p>
            </section>

            <section class="license-section">
              <h2><span class="section-number">4</span> Free tiers will remain free</h2>
              <p>If you sign up under a free tier, you will:</p>
              <ul>
                <li>Keep access to your data</li>
                <li>Keep access to the platform</li>
                <li>Never be forced into a paid plan to avoid losing your work</li>
              </ul>
              <p>Any future changes will be:</p>
              <ul>
                <li>Transparent</li>
                <li>Well-communicated</li>
                <li>Respectful of the commitments we make today</li>
              </ul>
            </section>

            <section class="license-section">
              <h2><span class="section-number">5</span> Your data always belongs to you</h2>
              <p>Regardless of hosting model or pricing:</p>
              <ul>
                <li>You always own your data</li>
                <li>Your data will never be sold</li>
                <li>You can export your data at any time</li>
                <li>You can migrate to a self-hosted edition without penalty</li>
              </ul>
              <p class="emphasis">This is central to the purpose of the platform.</p>
            </section>

            <section class="license-section">
              <h2><span class="section-number">6</span> No retroactive restrictions — ever</h2>
              <p>Any future licensing or pricing changes:</p>
              <ul>
                <li>Will not retroactively restrict existing free users</li>
                <li>Will not remove features you already rely on</li>
                <li>Will not lock or hide your data behind new paywalls</li>
              </ul>
              <p class="emphasis">We are committed to fairness and continuity.</p>
            </section>

            <section class="license-section">
              <h2><span class="section-number">7</span> We will communicate openly before any major change</h2>
              <p>If we introduce a paid service or licensing update:</p>
              <ul>
                <li>You will be informed in advance</li>
                <li>Changes will be documented openly</li>
                <li>We will provide clear migration options, including self-hosting</li>
              </ul>
              <p class="emphasis">Transparency is part of our trust model.</p>
            </section>

            <section class="why-section">
              <h2>Why are we sharing this now?</h2>
              <p class="lead">Because trust is foundational.</p>
              <p>
                We are building a platform that organisations may rely on for years. Being open about our future intentions — even before the business model is fully defined — ensures that:
              </p>
              <ul>
                <li>Users are not surprised later</li>
                <li>Contributions are made with full awareness</li>
                <li>Organisations can adopt the platform confidently</li>
                <li>We stay aligned with our mission of openness</li>
              </ul>
            </section>
          </article>

          <div class="cta-section">
            <button mat-raised-button class="cta-button" routerLink="/">
              <mat-icon>home</mat-icon>
              <span>Get Started</span>
            </button>
          </div>
        </div>
      </main>

      <!-- Footer -->
      <footer class="licensing-footer">
        <div class="container">
          <p>&copy; {{ currentYear }} Architecture-Decisions.org</p>
        </div>
      </footer>
    </div>
  `,
  styles: [`
    .licensing-page {
      min-height: 100vh;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
    }

    .licensing-header {
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #1e40af 100%);
      color: white;
      padding: 40px 24px 60px;
    }

    .container {
      max-width: 800px;
      margin: 0 auto;
    }

    .back-link {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: rgba(255, 255, 255, 0.8);
      text-decoration: none;
      font-size: 0.9rem;
      margin-bottom: 24px;
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

    .licensing-header h1 {
      font-size: 2.5rem;
      font-weight: 700;
      margin: 0 0 12px;
      letter-spacing: -0.02em;
    }

    .subtitle {
      font-size: 1.1rem;
      color: #e0f2fe;
      margin: 0;
      font-weight: 400;
    }

    .licensing-content {
      flex: 1;
      padding: 60px 24px;
    }

    .prose {
      color: #334155;
      font-size: 1.05rem;
      line-height: 1.8;
    }

    .prose .lead {
      font-size: 1.2rem;
      color: #475569;
      line-height: 1.7;
      margin-bottom: 40px;
    }

    .license-section {
      margin-bottom: 48px;
      padding-bottom: 32px;
      border-bottom: 1px solid #e2e8f0;
    }

    .license-section:last-of-type {
      border-bottom: none;
    }

    .license-section h2 {
      font-size: 1.35rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 16px;
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .section-number {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
      color: white;
      border-radius: 50%;
      font-size: 0.9rem;
      font-weight: 600;
      flex-shrink: 0;
    }

    .license-section p {
      margin: 0 0 16px;
    }

    .license-section ul {
      margin: 0 0 16px;
      padding-left: 24px;
    }

    .license-section li {
      margin-bottom: 8px;
      color: #475569;
    }

    .emphasis {
      font-weight: 500;
      color: #1e40af;
    }

    .why-section {
      margin-top: 48px;
      padding: 32px;
      background: #f1f5f9;
      border-radius: 12px;
    }

    .why-section h2 {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 16px;
    }

    .why-section .lead {
      font-size: 1.15rem;
      font-weight: 500;
      color: #1e40af;
      margin-bottom: 16px;
    }

    .cta-section {
      margin-top: 48px;
      text-align: center;
    }

    .cta-button {
      padding: 14px 32px !important;
      font-size: 16px !important;
      font-weight: 500 !important;
      border-radius: 100px !important;
      background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%) !important;
      color: white !important;
    }

    .cta-button mat-icon {
      margin-right: 8px;
    }

    .licensing-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 24px;
      text-align: center;
    }

    .licensing-footer p {
      margin: 0;
      font-size: 0.9rem;
    }

    @media (max-width: 600px) {
      .licensing-header {
        padding: 32px 16px 48px;
      }

      .licensing-header h1 {
        font-size: 1.75rem;
      }

      .subtitle {
        font-size: 1rem;
      }

      .licensing-content {
        padding: 40px 16px;
      }

      .prose {
        font-size: 1rem;
      }

      .prose .lead {
        font-size: 1.1rem;
      }

      .license-section h2 {
        font-size: 1.15rem;
      }

      .section-number {
        width: 28px;
        height: 28px;
        font-size: 0.85rem;
      }

      .why-section {
        padding: 24px 20px;
      }
    }
  `]
})
export class LicensingComponent {
  currentYear = new Date().getFullYear();
}
