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
              Decision records deserve to be preserved for the long term. We operate with transparency so you can adopt the platform with confidence.
            </p>

            <section class="license-section">
              <h2><span class="section-number">1</span> Free to use, free to self-host</h2>
              <p>
                The core platform remains free. We will maintain an open-source, self-hosted edition so you're never locked in.
              </p>
            </section>

            <section class="license-section">
              <h2><span class="section-number">2</span> Paid plans may come, but free stays free</h2>
              <p>
                The cloud service may introduce paid tiers for larger teams. If you sign up under a free tier, you keep access — we won't force you into a paid plan.
              </p>
            </section>

            <section class="license-section">
              <h2><span class="section-number">3</span> Your data is yours</h2>
              <p>
                You own your data. It will never be sold. You can export or migrate to self-hosting at any time.
              </p>
            </section>

            <section class="license-section">
              <h2><span class="section-number">4</span> No retroactive restrictions</h2>
              <p>
                Future changes won't restrict existing users, remove features you rely on, or lock data behind paywalls.
              </p>
            </section>

            <section class="license-section">
              <h2><span class="section-number">5</span> Transparent communication</h2>
              <p>
                Any major changes will be communicated in advance with clear options, including self-hosting.
              </p>
            </section>

            <section class="why-section">
              <h2>Why share this now?</h2>
              <p>
                Organisations may rely on this platform for years. We believe in being upfront about our intentions so you can adopt it confidently.
              </p>
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
          <p>&copy; {{ currentYear }} DecisionRecords.org</p>
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
