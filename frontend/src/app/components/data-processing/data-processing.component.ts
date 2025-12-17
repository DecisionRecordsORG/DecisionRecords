import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-data-processing',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="dpa-page">
      <!-- Header -->
      <header class="dpa-header">
        <div class="container">
          <a routerLink="/" class="back-link">
            <mat-icon>arrow_back</mat-icon>
            <span>Back to Home</span>
          </a>
          <h1>Data Processing Agreement</h1>
          <p class="subtitle">GDPR-compliant data handling without unnecessary complexity</p>
        </div>
      </header>

      <!-- Content -->
      <main class="dpa-content">
        <div class="container">
          <article class="prose">
            <p class="lead">
              This Data Processing Agreement ("DPA") explains how Architecture Decisions processes personal data when providing the hosted cloud service. It is designed to meet the requirements of the GDPR and similar data protection laws, without unnecessary complexity.
            </p>

            <hr class="divider">

            <section class="dpa-section">
              <div class="section-number">1</div>
              <div class="section-content">
                <h2>Roles and Scope</h2>
                <p>For the purposes of data protection law:</p>
                <ul>
                  <li>You (the customer) are the <strong>Data Controller</strong></li>
                  <li>We (Architecture Decisions) are the <strong>Data Processor</strong></li>
                </ul>
                <p>
                  We process personal data only on your documented instructions and solely to provide and operate the service.
                </p>
              </div>
            </section>

            <section class="dpa-section">
              <div class="section-number">2</div>
              <div class="section-content">
                <h2>Categories of Data Processed</h2>
                <p>The service may process the following personal data:</p>
                <ul>
                  <li>User identifiers (name, email address)</li>
                  <li>Authentication and access data</li>
                  <li>Audit and activity metadata (timestamps, actions)</li>
                  <li>Optional profile information</li>
                </ul>
                <p>
                  We do not process special categories of personal data unless you explicitly choose to include them in your content.
                </p>
              </div>
            </section>

            <section class="dpa-section">
              <div class="section-number">3</div>
              <div class="section-content">
                <h2>Purpose of Processing</h2>
                <p>Personal data is processed only for:</p>
                <ul>
                  <li>Providing access to the platform</li>
                  <li>Enabling collaboration between users</li>
                  <li>Securing the service and preventing abuse</li>
                  <li>Maintaining auditability and traceability</li>
                  <li>Providing customer support (where applicable)</li>
                </ul>
                <p>
                  We do not sell personal data, share it with advertisers, or use it for unrelated purposes.
                </p>
              </div>
            </section>

            <section class="dpa-section">
              <div class="section-number">4</div>
              <div class="section-content">
                <h2>Sub-processors</h2>
                <p>
                  We may use trusted infrastructure and service providers (e.g. cloud hosting, email delivery) as sub-processors.
                </p>
                <p>We ensure that all sub-processors:</p>
                <ul>
                  <li>Are bound by appropriate data protection obligations</li>
                  <li>Process data only for the purposes of providing the service</li>
                </ul>
                <p>
                  A current list of sub-processors is available on request.
                </p>
              </div>
            </section>

            <section class="dpa-section">
              <div class="section-number">5</div>
              <div class="section-content">
                <h2>Data Security</h2>
                <p>
                  We implement appropriate technical and organisational measures to protect personal data, including access controls, encryption, and monitoring. More details are available in our Security Overview.
                </p>
              </div>
            </section>

            <section class="dpa-section">
              <div class="section-number">6</div>
              <div class="section-content">
                <h2>Data Subject Rights</h2>
                <p>
                  We support your obligations to respond to data subject requests, including:
                </p>
                <ul>
                  <li>Access</li>
                  <li>Rectification</li>
                  <li>Erasure</li>
                  <li>Restriction</li>
                  <li>Data portability</li>
                </ul>
                <p>
                  Where possible, users can exercise these rights directly within the platform.
                </p>
              </div>
            </section>

            <section class="dpa-section">
              <div class="section-number">7</div>
              <div class="section-content">
                <h2>Data Retention and Deletion</h2>
                <p>
                  Personal data is retained only as long as necessary to provide the service or as required by law.
                </p>
                <p>On termination of the service:</p>
                <ul>
                  <li>You may export your data</li>
                  <li>Personal data will be deleted or anonymised within a reasonable timeframe</li>
                </ul>
              </div>
            </section>

            <section class="dpa-section">
              <div class="section-number">8</div>
              <div class="section-content">
                <h2>International Transfers</h2>
                <p>
                  Where data is processed outside the EU/EEA, we ensure appropriate safeguards are in place, such as Standard Contractual Clauses.
                </p>
              </div>
            </section>

            <section class="dpa-section">
              <div class="section-number">9</div>
              <div class="section-content">
                <h2>Audits</h2>
                <p>
                  Upon reasonable request, we will provide information necessary to demonstrate compliance with this DPA.
                </p>
              </div>
            </section>

            <div class="contact-box">
              <h3>Questions about data processing?</h3>
              <p>
                If you have questions about this DPA or need to exercise data subject rights, please contact us at:
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
      <footer class="dpa-footer">
        <div class="container">
          <p>&copy; {{ currentYear }} DecisionRecords.org</p>
        </div>
      </footer>
    </div>
  `,
  styles: [`
    .dpa-page {
      min-height: 100vh;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
    }

    .dpa-header {
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

    .dpa-header h1 {
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

    .dpa-content {
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
      margin-bottom: 32px;
    }

    .divider {
      border: none;
      border-top: 2px solid #e2e8f0;
      margin: 48px 0;
    }

    .dpa-section {
      display: flex;
      gap: 20px;
      margin-bottom: 48px;
      padding-bottom: 32px;
      border-bottom: 1px solid #e2e8f0;
    }

    .dpa-section:last-of-type {
      border-bottom: none;
    }

    .section-number {
      flex-shrink: 0;
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
      color: white;
      border-radius: 50%;
      font-size: 1.1rem;
      font-weight: 600;
    }

    .section-content {
      flex: 1;
    }

    .dpa-section h2 {
      font-size: 1.35rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 16px;
    }

    .dpa-section p {
      margin: 0 0 16px;
      color: #475569;
    }

    .dpa-section p:last-child {
      margin-bottom: 0;
    }

    .dpa-section ul {
      margin: 0 0 16px;
      padding-left: 24px;
    }

    .dpa-section li {
      margin-bottom: 8px;
      color: #475569;
    }

    .dpa-section strong {
      font-weight: 600;
      color: #1e40af;
    }

    .contact-box {
      margin-top: 48px;
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

    .dpa-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 24px;
      text-align: center;
    }

    .dpa-footer p {
      margin: 0;
      font-size: 0.9rem;
    }

    @media (max-width: 600px) {
      .dpa-header {
        padding: 32px 16px 48px;
      }

      .dpa-header h1 {
        font-size: 1.75rem;
      }

      .subtitle {
        font-size: 1rem;
      }

      .dpa-content {
        padding: 40px 16px;
      }

      .prose {
        font-size: 1rem;
      }

      .prose .lead {
        font-size: 1.1rem;
      }

      .dpa-section {
        flex-direction: column;
        gap: 12px;
      }

      .section-number {
        width: 36px;
        height: 36px;
        font-size: 1rem;
      }

      .dpa-section h2 {
        font-size: 1.15rem;
      }

      .contact-box {
        padding: 24px 20px;
      }
    }
  `]
})
export class DataProcessingComponent {
  currentYear = new Date().getFullYear();
}
