import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { SiteNavComponent } from '../shared/site-nav/site-nav.component';

@Component({
  selector: 'app-solutions',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    SiteNavComponent
  ],
  template: `
    <div class="solutions-page">
      <!-- Sticky Site Navigation -->
      <app-site-nav></app-site-nav>

      <!-- Header -->
      <header class="solutions-header">
        <div class="container">
          <h1>Decision Records</h1>
          <p class="header-subtitle">Preserving Organisational Decision Memory</p>
        </div>
      </header>

      <!-- Content -->
      <main class="solutions-content">
        <div class="container">
          <article class="prose">
            <!-- Opening Definition -->
            <p class="lead">
              Decision records are a lightweight way for organisations to capture important decisions along with their context and reasoning. They help teams preserve shared understanding over time, especially as people, priorities, and structures change.
            </p>

            <!-- Problem Section -->
            <section class="content-section">
              <h2>The Problem</h2>
              <p>
                Most organisations make decisions constantly, but rarely store them in a way that others can easily find or understand later. Decisions are discussed in meetings, chats, and documents, but the reasoning behind them is often lost. This leads to repeated discussions, misunderstandings between teams, and unnecessary friction as organisations grow.
              </p>
            </section>

            <!-- What Decision Records Capture -->
            <section class="content-section">
              <h2>What Decision Records Capture</h2>
              <p>Decision records provide a shared mental model for preserving important choices. They typically capture:</p>
              <ul class="feature-list">
                <li>
                  <mat-icon>check_circle</mat-icon>
                  <span><strong>The decision itself</strong> — what was decided and when</span>
                </li>
                <li>
                  <mat-icon>check_circle</mat-icon>
                  <span><strong>The context at the time</strong> — circumstances that shaped the choice</span>
                </li>
                <li>
                  <mat-icon>check_circle</mat-icon>
                  <span><strong>The reasoning and trade-offs</strong> — why this option was chosen</span>
                </li>
                <li>
                  <mat-icon>check_circle</mat-icon>
                  <span><strong>Alternatives considered</strong> — what else was evaluated and rejected</span>
                </li>
              </ul>
            </section>

            <!-- Who Decision Records Are For -->
            <section class="content-section">
              <h2>Who Decision Records Are For</h2>
              <p>
                Decision records are useful for any team that makes decisions others need to understand later. This includes product teams, founders, marketing teams, operations, retail organisations, and service businesses. They are not limited to technical or regulated environments.
              </p>
              <div class="audience-grid">
                <div class="audience-card">
                  <mat-icon>rocket_launch</mat-icon>
                  <h3>Startups</h3>
                  <p>Preserve early decisions that shape company direction as you scale</p>
                </div>
                <div class="audience-card">
                  <mat-icon>groups</mat-icon>
                  <h3>Growing Teams</h3>
                  <p>Maintain context when onboarding new team members</p>
                </div>
                <div class="audience-card">
                  <mat-icon>business</mat-icon>
                  <h3>Enterprises</h3>
                  <p>Coordinate decisions across departments and regions</p>
                </div>
                <div class="audience-card">
                  <mat-icon>storefront</mat-icon>
                  <h3>Operations</h3>
                  <p>Document operational choices that affect daily work</p>
                </div>
              </div>
            </section>

            <!-- Decision Records as Organisational Memory -->
            <section class="content-section">
              <h2>Organisational Memory</h2>
              <p>
                Over time, decision records form a durable memory of how an organisation thinks and operates. They explain not just what exists today, but how it came to be. This makes communication easier, onboarding faster, and collaboration more effective across teams.
              </p>
              <blockquote>
                Decision records create institutional memory that survives role changes, team reorganisations, and the passage of time.
              </blockquote>
            </section>

            <!-- Platform Introduction -->
            <section class="content-section platform-section">
              <h2>The Platform</h2>
              <p>
                DecisionRecords.org is a platform built specifically to support decision records at scale. It provides a shared, searchable place for organisations to capture decisions and preserve context over the long term.
              </p>
            </section>
          </article>

          <div class="cta-section">
            <h3>Start preserving your decisions today</h3>
            <p>Free during our limited preview period</p>
            <button mat-raised-button class="cta-button" routerLink="/">
              <mat-icon>rocket_launch</mat-icon>
              <span>Get Started Free</span>
            </button>
          </div>
        </div>
      </main>

      <!-- Footer -->
      <footer class="solutions-footer">
        <div class="container">
          <p>&copy; {{ currentYear }} DecisionRecords.org</p>
        </div>
      </footer>
    </div>
  `,
  styles: [`
    .solutions-page {
      min-height: 100vh;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
    }

    .solutions-header {
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #1e40af 100%);
      color: white;
      padding: 100px 24px 60px;
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

    .solutions-header h1 {
      font-size: 2.5rem;
      font-weight: 700;
      margin: 0 0 12px;
      letter-spacing: -0.02em;
    }

    .header-subtitle {
      font-size: 1.15rem;
      color: rgba(255, 255, 255, 0.85);
      margin: 0;
    }

    .solutions-content {
      flex: 1;
      padding: 60px 24px;
    }

    .prose {
      color: #334155;
      font-size: 1.1rem;
      line-height: 1.8;
    }

    .prose .lead {
      font-size: 1.25rem;
      color: #475569;
      line-height: 1.7;
      margin-bottom: 48px;
      padding-bottom: 32px;
      border-bottom: 1px solid #e2e8f0;
    }

    .content-section {
      margin-bottom: 48px;
    }

    .content-section h2 {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 20px;
      letter-spacing: -0.01em;
    }

    .content-section p {
      margin: 0 0 20px;
    }

    .feature-list {
      list-style: none;
      padding: 0;
      margin: 24px 0;
    }

    .feature-list li {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 16px;
      font-size: 1.05rem;
    }

    .feature-list mat-icon {
      color: #2563eb;
      font-size: 22px;
      width: 22px;
      height: 22px;
      margin-top: 2px;
      flex-shrink: 0;
    }

    .audience-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 20px;
      margin-top: 32px;
    }

    .audience-card {
      background: white;
      padding: 24px;
      border-radius: 12px;
      border: 1px solid #e2e8f0;
    }

    .audience-card mat-icon {
      color: #2563eb;
      font-size: 32px;
      width: 32px;
      height: 32px;
      margin-bottom: 12px;
    }

    .audience-card h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
    }

    .audience-card p {
      font-size: 0.95rem;
      color: #64748b;
      margin: 0;
      line-height: 1.5;
    }

    blockquote {
      font-size: 1.15rem;
      font-style: italic;
      color: #475569;
      margin: 32px 0;
      padding: 24px 32px;
      border-left: 4px solid #2563eb;
      background: #f1f5f9;
      border-radius: 0 8px 8px 0;
    }

    .platform-section {
      background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
      padding: 32px;
      border-radius: 12px;
      border: 1px solid #bae6fd;
    }

    .platform-section h2 {
      color: #0c4a6e;
    }

    .platform-section p {
      margin: 0;
      color: #0369a1;
    }

    .cta-section {
      margin-top: 64px;
      text-align: center;
      padding: 48px;
      background: white;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
    }

    .cta-section h3 {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
    }

    .cta-section p {
      font-size: 1.05rem;
      color: #64748b;
      margin: 0 0 24px;
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

    .solutions-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 24px;
      text-align: center;
    }

    .solutions-footer p {
      margin: 0;
      font-size: 0.9rem;
    }

    @media (max-width: 600px) {
      .solutions-header {
        padding: 32px 16px 48px;
      }

      .solutions-header h1 {
        font-size: 1.75rem;
      }

      .header-subtitle {
        font-size: 1rem;
      }

      .solutions-content {
        padding: 40px 16px;
      }

      .prose {
        font-size: 1rem;
      }

      .prose .lead {
        font-size: 1.1rem;
      }

      .content-section h2 {
        font-size: 1.25rem;
      }

      .audience-grid {
        grid-template-columns: 1fr;
      }

      blockquote {
        padding: 20px 24px;
        font-size: 1rem;
      }

      .platform-section {
        padding: 24px;
      }

      .cta-section {
        padding: 32px 24px;
      }
    }
  `]
})
export class SolutionsComponent {
  currentYear = new Date().getFullYear();
}
