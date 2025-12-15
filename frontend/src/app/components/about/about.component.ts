import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-about',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="about-page">
      <!-- Header -->
      <header class="about-header">
        <div class="container">
          <a routerLink="/" class="back-link">
            <mat-icon>arrow_back</mat-icon>
            <span>Back to Home</span>
          </a>
          <h1>About This Project</h1>
        </div>
      </header>

      <!-- Content -->
      <main class="about-content">
        <div class="container">
          <article class="prose">
            <p class="lead">
              Every organisation makes decisions that influence how its systems, services, and operations function. Some decisions are small and short-lived. Others quietly define structure, boundaries, and opportunities for years to come.
            </p>

            <p>
              Most of the time, these long-term decisions are not formally recognised. They are made in meetings, under pressure, with incomplete information and real constraints. Once the decision is made and implemented, attention shifts elsewhere. What rarely survives is the reasoning: why this option was chosen, what was ruled out, which risks were accepted, and which assumptions were believed to be valid at the time.
            </p>

            <p>
              Over time, people change roles, teams reorganise, vendors disappear, and priorities shift. Documentation deteriorates or is discarded altogether. What remains is a system that behaves in a certain way, with little visible explanation. Anyone asked to maintain, secure, regulate, modernise, or integrate with that system must reconstruct decisions after the fact, often through inference, guesswork, or repeated failure.
            </p>

            <h2>What is a Decision Record?</h2>

            <p>
              The term <em>decision record</em> signifies this class of choices. It does not describe a job title or a methodology. It refers to any decision with a lasting structural impact: decisions that limit future change, influence how components interact, or define the boundaries within which systems and organisations operate. These decisions exist whether documented or not. Naming them simply makes them visible.
            </p>

            <p>
              Despite their importance, important decisions are seldom treated as first-class knowledge. They tend to reside in people's minds, in forgotten presentations, or in fragments scattered across tools not designed to preserve rationale. When documented, it is often as an afterthought, detached from the context that made the decision meaningful.
            </p>

            <h2>Why This Project Exists</h2>

            <p>
              This project exists because the loss of context is not unavoidable. Capturing the reasoning behind important decisions does not require extensive processes, specialised language, or elaborate governance. It requires a shared understanding that some decisions matter beyond the moment they are made, and a straightforward, durable way to record them while the context is still fresh.
            </p>

            <p>
              We created the Decision Records platform to make this practice accessible and sustainable. The aim is not to impose a framework or to formalise every choice, but to lower barriers to recording decisions that genuinely shape systems over time. The platform is designed to support collaboration, make decision context easy to revisit, and ensure that knowledge endures beyond individual roles and projects.
            </p>

            <h2>Beyond Software Engineering</h2>

            <p>
              Although the idea originated in software engineering, the issue it addresses is much broader. Large organisations make structural decisions across IT landscapes, cloud and infrastructure strategies, security and compliance frameworks, data and integration methods, and operational structures. In all these areas, future teams bear the consequences without necessarily inheriting explanations.
            </p>

            <h2>A Non-Profit Initiative</h2>

            <p>
              Decision Records is a non-profit initiative because impartiality matters. The platform is not intended to promote tools, vendors, or certifications. Its purpose is to provide a stable infrastructure for preserving decision context, regardless of organisational size, maturity, or technical approach.
            </p>

            <blockquote>
              At its core, this project is about respecting future work. Recording why things are the way they are is an act of care for the people who will one day be asked to change them.
            </blockquote>
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
      <footer class="about-footer">
        <div class="container">
          <p>&copy; {{ currentYear }} DecisionRecords.org</p>
        </div>
      </footer>
    </div>
  `,
  styles: [`
    .about-page {
      min-height: 100vh;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
    }

    .about-header {
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

    .about-header h1 {
      font-size: 2.5rem;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.02em;
    }

    .about-content {
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
      margin-bottom: 32px;
    }

    .prose p {
      margin: 0 0 24px;
    }

    .prose h2 {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 48px 0 20px;
      letter-spacing: -0.01em;
    }

    .prose em {
      font-style: italic;
      color: #1e40af;
    }

    .prose blockquote {
      font-size: 1.15rem;
      font-style: italic;
      color: #475569;
      margin: 40px 0;
      padding: 24px 32px;
      border-left: 4px solid #2563eb;
      background: #f1f5f9;
      border-radius: 0 8px 8px 0;
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

    .about-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 24px;
      text-align: center;
    }

    .about-footer p {
      margin: 0;
      font-size: 0.9rem;
    }

    @media (max-width: 600px) {
      .about-header {
        padding: 32px 16px 48px;
      }

      .about-header h1 {
        font-size: 1.75rem;
      }

      .about-content {
        padding: 40px 16px;
      }

      .prose {
        font-size: 1rem;
      }

      .prose .lead {
        font-size: 1.1rem;
      }

      .prose h2 {
        font-size: 1.25rem;
        margin: 36px 0 16px;
      }

      .prose blockquote {
        padding: 20px 24px;
        font-size: 1rem;
      }
    }
  `]
})
export class AboutComponent {
  currentYear = new Date().getFullYear();
}
