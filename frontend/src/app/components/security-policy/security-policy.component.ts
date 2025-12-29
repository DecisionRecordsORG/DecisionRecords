import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-security-policy',
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
          <a routerLink="/" class="back-link">
            <mat-icon>arrow_back</mat-icon>
            <span>Back to Home</span>
          </a>
          <h1>Security Overview</h1>
          <p class="subtitle">Built for long-term preservation of organisational knowledge</p>
        </div>
      </header>

      <!-- Content -->
      <main class="security-content">
        <div class="container">
          <article class="prose">
            <p class="lead">
              Decision Records is designed to support long-lived organisational knowledge. Because the platform is intended to preserve context over time, security and integrity are treated as foundational concerns rather than optional features.
            </p>

            <p>
              This overview describes how we approach security for the hosted cloud service, and the principles that guide our design.
            </p>

            <hr class="divider">

            <section class="security-section">
              <div class="section-header">
                <mat-icon class="section-icon">cloud</mat-icon>
                <h2>Hosting and Infrastructure</h2>
              </div>
              <p>
                The hosted service runs on established cloud infrastructure with dedicated production environments. Systems are deployed using repeatable, automated processes to reduce configuration drift and operational risk. Backups are performed regularly and stored securely, with recovery procedures tested as part of normal operations.
              </p>
              <p>
                We operate separate environments for development, testing, and production to limit the blast radius of changes and ensure stability.
              </p>
            </section>

            <section class="security-section">
              <div class="section-header">
                <mat-icon class="section-icon">lock</mat-icon>
                <h2>Access Control and Isolation</h2>
              </div>
              <p>
                Access to the platform is governed by tenant-level isolation and role-based access control. Users are assigned roles that determine what actions they can perform, and sensitive operations require elevated privileges.
              </p>
              <p>
                Administrative actions are explicitly scoped and logged. No single user implicitly owns an organisational space, and safeguards are in place to prevent accidental or unilateral lock-out of other users.
              </p>
            </section>

            <section class="security-section">
              <div class="section-header">
                <mat-icon class="section-icon">shield</mat-icon>
                <h2>Data Protection</h2>
              </div>
              <p>
                All communication with the service is encrypted in transit. Data stored by the platform is logically isolated per tenant and protected using industry-standard encryption mechanisms provided by the underlying infrastructure.
              </p>
              <p>
                We design the system so that organisational data remains intact even when individual user accounts are removed. Personal data can be deleted or anonymised without compromising the integrity of shared decision records.
              </p>
            </section>

            <section class="security-section">
              <div class="section-header">
                <mat-icon class="section-icon">history</mat-icon>
                <h2>Auditability and Traceability</h2>
              </div>
              <p>
                The platform maintains detailed audit logs for administrative and security-relevant actions. These logs are designed to be append-only and tamper-resistant, providing a reliable history of changes over time.
              </p>
              <p>
                Audit retention periods vary by plan, allowing organisations with regulatory or compliance obligations to retain records for longer periods where necessary.
              </p>
            </section>

            <section class="security-section">
              <div class="section-header">
                <mat-icon class="section-icon">code</mat-icon>
                <h2>Secure Development Practices</h2>
              </div>
              <p>
                Security is built into the development process. Code changes are reviewed before deployment, dependencies are monitored for known vulnerabilities, and updates are applied regularly.
              </p>
              <p>
                We follow the principle of least privilege across infrastructure and application components, reducing the impact of potential misconfigurations or compromised credentials.
              </p>
            </section>

            <section class="security-section">
              <div class="section-header">
                <mat-icon class="section-icon">warning</mat-icon>
                <h2>Incident Response</h2>
              </div>
              <p>
                We monitor the platform for availability and security events and maintain documented procedures for responding to incidents. When issues occur, our focus is on containment, recovery, and clear communication.
              </p>
              <p>
                For significant incidents affecting availability or data integrity, we provide updates and post-incident summaries to affected customers where appropriate.
              </p>
            </section>

            <section class="security-section">
              <div class="section-header">
                <mat-icon class="section-icon">verified</mat-icon>
                <h2>Compliance Posture</h2>
              </div>
              <p>
                At this stage, the platform is not formally certified against specific security standards such as ISO 27001 or SOC 2. However, it is designed with these frameworks in mind, and many of the underlying controls align with common enterprise security expectations.
              </p>
              <p>
                Formal certifications may be pursued as the project and its operational footprint mature.
              </p>
            </section>

            <section class="security-section">
              <div class="section-header">
                <mat-icon class="section-icon">handshake</mat-icon>
                <h2>Shared Responsibility</h2>
              </div>
              <p>
                Security is a shared responsibility. While we take care of the hosted infrastructure, platform security, and operational controls, customers remain responsible for managing access within their organisations and for the content they choose to store.
              </p>
            </section>

            <div class="contact-box">
              <h3>Questions about security?</h3>
              <p>
                If you have specific security questions or would like to report a vulnerability, please contact us at:
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
      <footer class="security-footer">
        <div class="container">
          <p>&copy; {{ currentYear }} DecisionRecords.org</p>
        </div>
      </footer>
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

    .security-header h1 {
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

    .security-content {
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

    .divider {
      border: none;
      border-top: 2px solid #e2e8f0;
      margin: 48px 0;
    }

    .security-section {
      margin-bottom: 48px;
    }

    .section-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }

    .section-icon {
      color: #2563eb;
      font-size: 28px;
      width: 28px;
      height: 28px;
    }

    .security-section h2 {
      font-size: 1.35rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0;
    }

    .security-section p {
      margin: 0 0 16px;
      color: #475569;
    }

    .security-section p:last-child {
      margin-bottom: 0;
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

    .security-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 24px;
      text-align: center;
    }

    .security-footer p {
      margin: 0;
      font-size: 0.9rem;
    }

    @media (max-width: 600px) {
      .security-header {
        padding: 32px 16px 48px;
      }

      .security-header h1 {
        font-size: 1.75rem;
      }

      .subtitle {
        font-size: 1rem;
      }

      .security-content {
        padding: 40px 16px;
      }

      .prose {
        font-size: 1rem;
      }

      .prose .lead {
        font-size: 1.1rem;
      }

      .security-section h2 {
        font-size: 1.15rem;
      }

      .section-icon {
        font-size: 24px;
        width: 24px;
        height: 24px;
      }

      .contact-box {
        padding: 24px 20px;
      }
    }
  `]
})
export class SecurityPolicyComponent {
  currentYear = new Date().getFullYear();
}
