import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-service-level-agreement',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="sla-page">
      <!-- Header -->
      <header class="sla-header">
        <div class="container">
          <a routerLink="/" class="back-link">
            <mat-icon>arrow_back</mat-icon>
            <span>Back to Home</span>
          </a>
          <h1>Service Level Agreement</h1>
          <p class="subtitle">Availability and support commitments for paid plans</p>
        </div>
      </header>

      <!-- Content -->
      <main class="sla-content">
        <div class="container">
          <article class="prose">
            <p class="lead">
              This SLA describes the availability and support commitments for paid cloud plans.
            </p>

            <div class="notice-box">
              <mat-icon>info</mat-icon>
              <p>Free and Limited Preview usage is provided without SLA.</p>
            </div>

            <hr class="divider">

            <section class="sla-section">
              <div class="section-header">
                <mat-icon class="section-icon">schedule</mat-icon>
                <div>
                  <h2>Service Availability</h2>
                  <p class="section-subtitle">Uptime targets for paid plans</p>
                </div>
              </div>
              <div class="section-content">
                <p>For paid plans, we target:</p>
                <div class="metric-box">
                  <div class="metric-value">99.9%</div>
                  <div class="metric-label">Monthly Uptime</div>
                </div>
                <p>
                  Uptime is measured at the application layer and excludes:
                </p>
                <ul>
                  <li>Scheduled maintenance</li>
                  <li>Force majeure events</li>
                  <li>Issues caused by customer configuration or third-party services</li>
                </ul>
              </div>
            </section>

            <section class="sla-section">
              <div class="section-header">
                <mat-icon class="section-icon">build</mat-icon>
                <div>
                  <h2>Maintenance</h2>
                  <p class="section-subtitle">Planned updates and changes</p>
                </div>
              </div>
              <div class="section-content">
                <p>Planned maintenance:</p>
                <ul>
                  <li>Will be communicated in advance where possible</li>
                  <li>Is typically scheduled outside of business hours</li>
                  <li>Does not count against uptime targets</li>
                </ul>
              </div>
            </section>

            <section class="sla-section">
              <div class="section-header">
                <mat-icon class="section-icon">support_agent</mat-icon>
                <div>
                  <h2>Support Response Times</h2>
                  <p class="section-subtitle">For paid plans</p>
                </div>
              </div>
              <div class="section-content">
                <p>
                  Support response times and channels will be defined as paid plans are introduced. Details will be published before any such commitments apply.
                </p>
              </div>
            </section>

            <section class="sla-section">
              <div class="section-header">
                <mat-icon class="section-icon">announcement</mat-icon>
                <div>
                  <h2>Incident Communication</h2>
                  <p class="section-subtitle">Keeping you informed</p>
                </div>
              </div>
              <div class="section-content">
                <p>For major incidents:</p>
                <ul>
                  <li>We will provide status updates</li>
                  <li>A post-incident summary will be shared where appropriate</li>
                </ul>
              </div>
            </section>

            <section class="sla-section">
              <div class="section-header">
                <mat-icon class="section-icon">account_balance</mat-icon>
                <div>
                  <h2>SLA Credits</h2>
                  <p class="section-subtitle">Future consideration</p>
                </div>
              </div>
              <div class="section-content">
                <p>
                  Service credits may be introduced for Enterprise plans in the future. Details will be published before any such commitments apply.
                </p>
              </div>
            </section>

            <div class="info-box">
              <h3>Current Status</h3>
              <p>
                The platform is currently in Limited Preview. During this phase, the service is provided without formal SLA commitments. As we introduce paid plans, this page will be updated with specific availability and support targets.
              </p>
            </div>

            <div class="contact-box">
              <h3>Questions about service levels?</h3>
              <p>
                If you have questions about availability, support, or would like to discuss your organisation's requirements, please contact us at:
              </p>
              <p class="contact-email">
                <a href="mailto:contact&#64;decisionrecords.org">contact&#64;decisionrecords.org</a>
              </p>
            </div>
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
      <footer class="sla-footer">
        <div class="container">
          <p>&copy; {{ currentYear }} DecisionRecords.org</p>
        </div>
      </footer>
    </div>
  `,
  styles: [`
    .sla-page {
      min-height: 100vh;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
    }

    .sla-header {
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

    .sla-header h1 {
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

    .sla-content {
      flex: 1;
      padding: 60px 24px;
    }

    .prose {
      color: #334155;
      font-size: 1.05rem;
      line-height: 1.8;
    }

    .prose .lead {
      font-size: 1.15rem;
      color: #475569;
      line-height: 1.7;
      margin-bottom: 24px;
    }

    .notice-box {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px 24px;
      background: #fef3c7;
      border-left: 4px solid #f59e0b;
      border-radius: 0 8px 8px 0;
      margin-bottom: 32px;
    }

    .notice-box mat-icon {
      color: #f59e0b;
      font-size: 24px;
      width: 24px;
      height: 24px;
    }

    .notice-box p {
      margin: 0;
      color: #92400e;
      font-weight: 500;
    }

    .divider {
      border: none;
      border-top: 2px solid #e2e8f0;
      margin: 48px 0;
    }

    .sla-section {
      margin-bottom: 48px;
      padding-bottom: 32px;
      border-bottom: 1px solid #e2e8f0;
    }

    .sla-section:last-of-type {
      border-bottom: none;
    }

    .section-header {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 20px;
    }

    .section-icon {
      color: #2563eb;
      font-size: 32px;
      width: 32px;
      height: 32px;
      flex-shrink: 0;
    }

    .section-header h2 {
      font-size: 1.35rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 4px;
    }

    .section-subtitle {
      font-size: 0.95rem;
      color: #64748b;
      margin: 0;
    }

    .section-content p {
      margin: 0 0 16px;
      color: #475569;
    }

    .section-content p:last-child {
      margin-bottom: 0;
    }

    .section-content ul {
      margin: 0 0 16px;
      padding-left: 24px;
    }

    .section-content li {
      margin-bottom: 8px;
      color: #475569;
    }

    .metric-box {
      display: inline-flex;
      flex-direction: column;
      align-items: center;
      padding: 24px 40px;
      background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
      border-radius: 12px;
      margin: 16px 0;
    }

    .metric-value {
      font-size: 3rem;
      font-weight: 700;
      color: #2563eb;
      line-height: 1;
      margin-bottom: 8px;
    }

    .metric-label {
      font-size: 0.95rem;
      color: #475569;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .info-box {
      margin-top: 48px;
      padding: 32px;
      background: #f1f5f9;
      border-radius: 12px;
    }

    .info-box h3 {
      font-size: 1.25rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 12px;
    }

    .info-box p {
      margin: 0;
      color: #475569;
      font-size: 1.05rem;
      line-height: 1.7;
    }

    .contact-box {
      margin-top: 24px;
      padding: 32px;
      background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
      border-radius: 12px;
      border-left: 4px solid #2563eb;
    }

    .contact-box h3 {
      font-size: 1.25rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 12px;
    }

    .contact-box p {
      margin: 0 0 12px;
      color: #475569;
      font-size: 1.05rem;
      line-height: 1.7;
    }

    .contact-box p:last-child {
      margin-bottom: 0;
    }

    .contact-email {
      font-size: 1.1rem;
      font-weight: 500;
    }

    .contact-email a {
      color: #2563eb;
      text-decoration: none;
    }

    .contact-email a:hover {
      text-decoration: underline;
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

    .sla-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 24px;
      text-align: center;
    }

    .sla-footer p {
      margin: 0;
      font-size: 0.9rem;
    }

    @media (max-width: 600px) {
      .sla-header {
        padding: 32px 16px 48px;
      }

      .sla-header h1 {
        font-size: 1.75rem;
      }

      .subtitle {
        font-size: 1rem;
      }

      .sla-content {
        padding: 40px 16px;
      }

      .prose {
        font-size: 1rem;
      }

      .prose .lead {
        font-size: 1.1rem;
      }

      .section-header {
        gap: 12px;
      }

      .section-icon {
        font-size: 28px;
        width: 28px;
        height: 28px;
      }

      .section-header h2 {
        font-size: 1.15rem;
      }

      .metric-box {
        padding: 20px 32px;
      }

      .metric-value {
        font-size: 2.5rem;
      }

      .info-box,
      .contact-box {
        padding: 24px 20px;
      }

      .notice-box {
        padding: 12px 16px;
      }
    }
  `]
})
export class ServiceLevelAgreementComponent {
  currentYear = new Date().getFullYear();
}
