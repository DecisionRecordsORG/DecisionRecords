import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-data-processing-agreement',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatIconModule
  ],
  template: `
    <div class="dpa-page">
      <header class="dpa-header">
        <div class="container">
          <a routerLink="/" class="back-link">
            <mat-icon>arrow_back</mat-icon>
            <span>Back to Home</span>
          </a>
          <h1>Data Processing Addendum</h1>
          <p class="subtitle">How hosted service data processing is handled</p>
        </div>
      </header>

      <main class="dpa-content">
        <div class="container">
          <article class="prose">
            <p class="meta">Last updated: July 2026</p>
            <p class="lead">
              This page summarizes the data processing position for the Decision Records hosted service. A signed Data Processing Addendum can be provided for paid hosted customers when commercial plans are introduced.
            </p>

            <hr class="divider">

            <section class="dpa-section">
              <h2>Processing Roles</h2>
              <p>
                Customer organisations control the decision records, user accounts, and related organisational content they add to the service. Decision Records processes that data to provide the hosted platform, maintain security, support users, and operate the service.
              </p>
            </section>

            <section class="dpa-section">
              <h2>Categories of Data</h2>
              <p>
                The service may process account information, authentication metadata, decision records, audit events, tenant configuration, and support communications. The service is not intended for special-category personal data.
              </p>
            </section>

            <section class="dpa-section">
              <h2>Security Measures</h2>
              <p>
                Data is protected through tenant isolation, role-based access controls, encrypted transport, audit logging, least-privilege operational access, dependency monitoring, and repeatable deployment processes.
              </p>
            </section>

            <section class="dpa-section">
              <h2>Subprocessors</h2>
              <p>
                Hosted service infrastructure may rely on cloud, email, monitoring, and security providers. A subprocessor list will be published before paid hosted plans create contractual processing commitments.
              </p>
            </section>

            <section class="dpa-section">
              <h2>Data Return and Deletion</h2>
              <p>
                Customer organisations should be able to export their organisational records and request deletion or anonymisation of personal data according to the applicable hosted service terms.
              </p>
            </section>

            <section class="dpa-section">
              <h2>Contact</h2>
              <p>
                For data protection questions or a hosted service DPA request, contact <a href="mailto:lawrence@decisionrecords.org">lawrence&#64;decisionrecords.org</a>.
              </p>
            </section>
          </article>
        </div>
      </main>
    </div>
  `,
  styles: [`
    .dpa-page {
      min-height: 100vh;
      background: #f8fafc;
      color: #1e293b;
    }

    .dpa-header {
      background: linear-gradient(135deg, #0f172a 0%, #1e40af 100%);
      color: white;
      padding: 48px 24px 56px;
    }

    .container {
      max-width: 920px;
      margin: 0 auto;
    }

    .back-link {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: rgba(255, 255, 255, 0.86);
      text-decoration: none;
      margin-bottom: 28px;
      font-weight: 500;
    }

    .back-link:hover {
      color: white;
    }

    h1 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 2.75rem;
      margin: 0 0 12px;
      letter-spacing: 0;
    }

    .subtitle {
      margin: 0;
      color: rgba(255, 255, 255, 0.82);
      font-size: 1.1rem;
    }

    .dpa-content {
      padding: 48px 24px 72px;
    }

    .prose {
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 40px;
      box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
    }

    .meta {
      color: #64748b;
      font-size: 0.9rem;
      margin: 0 0 20px;
    }

    .lead {
      color: #334155;
      font-size: 1.08rem;
      line-height: 1.7;
      margin: 0;
    }

    .divider {
      border: 0;
      border-top: 1px solid #e2e8f0;
      margin: 32px 0;
    }

    .dpa-section {
      margin-bottom: 28px;
    }

    .dpa-section:last-child {
      margin-bottom: 0;
    }

    h2 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 1.28rem;
      margin: 0 0 10px;
      color: #0f172a;
      letter-spacing: 0;
    }

    p {
      color: #475569;
      line-height: 1.7;
      margin: 0;
    }

    a {
      color: #1d4ed8;
      font-weight: 600;
    }

    @media (max-width: 640px) {
      .dpa-header {
        padding: 36px 20px 44px;
      }

      h1 {
        font-size: 2rem;
      }

      .dpa-content {
        padding: 32px 16px 48px;
      }

      .prose {
        padding: 24px;
      }
    }
  `]
})
export class DataProcessingAgreementComponent {}
