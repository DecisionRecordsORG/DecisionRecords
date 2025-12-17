import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-terms-of-service',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="terms-page">
      <!-- Header -->
      <header class="terms-header">
        <div class="container">
          <a routerLink="/" class="back-link">
            <mat-icon>arrow_back</mat-icon>
            <span>Back to Home</span>
          </a>
          <h1>Terms of Service</h1>
          <p class="subtitle">Clear terms for the hosted cloud service</p>
        </div>
      </header>

      <!-- Content -->
      <main class="terms-content">
        <div class="container">
          <article class="prose">
            <p class="meta">Last updated: December 2024</p>

            <p class="lead">
              These Terms of Service govern your access to and use of the Architecture Decisions platform, including the hosted cloud service, related websites, and documentation. By creating an account or using the service, you agree to these terms.
            </p>

            <hr class="divider">

            <section class="terms-section">
              <h2>1. Purpose of the service</h2>
              <p>
                Architecture Decisions provides a platform for capturing, preserving, and collaborating on architecture decisions and the context behind them. The project exists to help organisations retain institutional knowledge and reduce the long-term cost of lost decision rationale.
              </p>
              <p>
                The project is operated as an independent, open source initiative and is offered both as self-hosted software and as a hosted cloud service. While related, these offerings are distinct and are governed by different terms.
              </p>
            </section>

            <section class="terms-section">
              <h2>2. Software license (self-hosted edition)</h2>
              <p>
                The source code for the self-hosted edition of the platform is made available under the Business Source License (BSL).
              </p>
              <p>
                Under this license, you may view, modify, and run the software on your own infrastructure for internal use. You may not offer the software as a competing hosted or managed service, or resell it as such.
              </p>
              <p>
                The full license text is available in the project repository and governs all self-hosted usage. These Terms of Service do not replace or modify the BSL.
              </p>
            </section>

            <section class="terms-section">
              <h2>3. Hosted cloud service</h2>
              <p>
                The hosted cloud service is a separate offering operated by the project maintainers. It includes managed infrastructure, backups, monitoring, security controls, and ongoing maintenance.
              </p>
              <p>
                Use of the hosted service is governed by these Terms of Service, along with any additional service-specific terms that may apply as the platform evolves.
              </p>
            </section>

            <section class="terms-section">
              <h2>4. Limited Preview</h2>
              <p>
                The hosted service is currently offered as a Limited Preview. This allows early users to explore the platform while we stabilise features, validate usage patterns, and refine the long-term hosting model.
              </p>
              <p>
                During this preview period, each tenant is limited to a maximum of five users. The service is provided without formal uptime guarantees or support service levels. Limits and features may change as the platform matures.
              </p>
              <p>
                If your organisation would like to explore broader usage, higher limits, or specific requirements, you are encouraged to contact us. We are actively learning from early adopters.
              </p>
            </section>

            <section class="terms-section">
              <h2>5. Accounts and organisational access</h2>
              <p>
                You are responsible for maintaining the security of your account and ensuring that access is used appropriately within your organisation.
              </p>
              <p>
                Tenant spaces are shared organisational environments. No single user owns a tenant by default. Administrative privileges are intended to be exercised as stewardship on behalf of the organisation, rather than as exclusive control.
              </p>
              <p>
                Safeguards are in place to prevent accidental or unilateral actions that would block other legitimate users from accessing a shared tenant.
              </p>
            </section>

            <section class="terms-section">
              <h2>6. Your data</h2>
              <p>
                You retain full ownership of all data and content you create or upload to the platform.
              </p>
              <p>
                We do not sell user data, use it for advertising, or process it for purposes unrelated to operating and securing the service. Access to content is limited to what is necessary to provide the platform and to respond to support or security issues where appropriate.
              </p>
              <p>
                You may export your data at any time. Further details about data handling are described in our Privacy Policy and Data Processing Agreement.
              </p>
            </section>

            <section class="terms-section">
              <h2>7. Acceptable use</h2>
              <p>
                You agree to use the service in a lawful and responsible manner. This includes refraining from actions that would disrupt the service, interfere with other users, violate applicable laws, or attempt to bypass platform safeguards and limits.
              </p>
              <p>
                We reserve the right to restrict or suspend access where use of the service poses legal, security, or operational risks, or where these terms are materially violated.
              </p>
            </section>

            <section class="terms-section">
              <h2>8. Availability and support</h2>
              <p>
                During the Limited Preview phase, the service is provided on an "as-is" basis without guarantees of availability or formal support commitments.
              </p>
              <p>
                For future paid plans, availability targets and support commitments will be described in a separate Service Level Agreement.
              </p>
            </section>

            <section class="terms-section">
              <h2>9. Changes to the service and terms</h2>
              <p>
                We may update the service and these terms over time as the platform evolves.
              </p>
              <p>
                We are committed to transparency and will not retroactively restrict access to existing data, remove features you already rely on without notice, or introduce pricing changes that force payment to retain access to your work.
              </p>
              <p>
                Material changes will be communicated in advance whenever reasonably possible.
              </p>
            </section>

            <section class="terms-section">
              <h2>10. Termination</h2>
              <p>
                You may stop using the service at any time.
              </p>
              <p>
                We may suspend or terminate access where required by law, where use creates significant risk, or where these terms are materially violated. In such cases, you will be given an opportunity to export your data where reasonably practicable.
              </p>
              <p>
                After termination, data will be retained for a limited period before being deleted or anonymised.
              </p>
            </section>

            <section class="terms-section">
              <h2>11. Disclaimer</h2>
              <p>
                The service is provided without warranties of any kind, to the extent permitted by law. In particular, we do not guarantee uninterrupted availability or error-free operation, especially during the Limited Preview phase.
              </p>
            </section>

            <section class="terms-section">
              <h2>12. Limitation of liability</h2>
              <p>
                To the extent permitted by law, we are not liable for indirect, incidental, or consequential damages. Our total liability in connection with the service is limited to the amount paid for the service in the twelve months preceding the claim, or zero where the service is used free of charge.
              </p>
            </section>

            <section class="terms-section">
              <h2>13. Governing law</h2>
              <p>
                These Terms of Service are governed by the laws of the Republic of South Africa, without regard to conflict-of-law principles.
              </p>
            </section>

            <section class="terms-section">
              <h2>14. Contact</h2>
              <p>
                If you have questions about these terms, licensing, or the direction of the project, you can contact us at:
              </p>
              <p class="contact-email">
                <a href="mailto:contact&#64;decisionrecords.org">contact&#64;decisionrecords.org</a>
              </p>
            </section>

            <div class="summary-box">
              <h3>Plain-language summary</h3>
              <p>
                We're building a platform intended to last. These terms exist to protect users, the integrity of shared organisational knowledge, and the long-term sustainability of the project — without surprises.
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
      <footer class="terms-footer">
        <div class="container">
          <p>&copy; {{ currentYear }} DecisionRecords.org</p>
        </div>
      </footer>
    </div>
  `,
  styles: [`
    .terms-page {
      min-height: 100vh;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
    }

    .terms-header {
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

    .terms-header h1 {
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

    .terms-content {
      flex: 1;
      padding: 60px 24px;
    }

    .prose {
      color: #334155;
      font-size: 1.05rem;
      line-height: 1.8;
    }

    .meta {
      font-size: 0.95rem;
      color: #64748b;
      font-style: italic;
      margin-bottom: 24px;
    }

    .prose .lead {
      font-size: 1.15rem;
      color: #475569;
      line-height: 1.7;
      margin-bottom: 32px;
    }

    .divider {
      border: none;
      border-top: 2px solid #e2e8f0;
      margin: 48px 0;
    }

    .terms-section {
      margin-bottom: 40px;
    }

    .terms-section h2 {
      font-size: 1.35rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 16px;
    }

    .terms-section p {
      margin: 0 0 16px;
      color: #475569;
    }

    .terms-section p:last-child {
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

    .summary-box {
      margin-top: 48px;
      padding: 32px;
      background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
      border-radius: 12px;
      border-left: 4px solid #2563eb;
    }

    .summary-box h3 {
      font-size: 1.25rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 12px;
    }

    .summary-box p {
      margin: 0;
      color: #475569;
      font-size: 1.05rem;
      line-height: 1.7;
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

    .terms-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 24px;
      text-align: center;
    }

    .terms-footer p {
      margin: 0;
      font-size: 0.9rem;
    }

    @media (max-width: 600px) {
      .terms-header {
        padding: 32px 16px 48px;
      }

      .terms-header h1 {
        font-size: 1.75rem;
      }

      .subtitle {
        font-size: 1rem;
      }

      .terms-content {
        padding: 40px 16px;
      }

      .prose {
        font-size: 1rem;
      }

      .prose .lead {
        font-size: 1.1rem;
      }

      .terms-section h2 {
        font-size: 1.15rem;
      }

      .summary-box {
        padding: 24px 20px;
      }
    }
  `]
})
export class TermsOfServiceComponent {
  currentYear = new Date().getFullYear();
}
