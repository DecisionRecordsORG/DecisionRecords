import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatExpansionModule } from '@angular/material/expansion';
import { SiteNavComponent } from '../shared/site-nav/site-nav.component';

interface FaqItem {
  question: string;
  answer: string;
}

interface FaqSection {
  title: string;
  icon: string;
  items: FaqItem[];
}

@Component({
  selector: 'app-faq',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    MatExpansionModule,
    SiteNavComponent
  ],
  template: `
    <div class="faq-page">
      <!-- Sticky Site Navigation -->
      <app-site-nav></app-site-nav>

      <!-- Header -->
      <header class="faq-header">
        <div class="container">
          <h1>Frequently Asked Questions</h1>
          <p class="header-subtitle">
            Everything you need to know about Decision Records
          </p>
        </div>
      </header>

      <!-- Section Navigation -->
      <nav class="section-nav">
        <div class="container">
          <div class="nav-pills">
            @for (section of sections; track section.title) {
              <a [href]="'#' + getSectionId(section.title)" class="nav-pill">
                <mat-icon>{{ section.icon }}</mat-icon>
                <span>{{ section.title }}</span>
              </a>
            }
          </div>
        </div>
      </nav>

      <!-- Content -->
      <main class="faq-content">
        <div class="container">
          @for (section of sections; track section.title) {
            <section class="faq-section" [id]="getSectionId(section.title)">
              <div class="section-header">
                <mat-icon>{{ section.icon }}</mat-icon>
                <h2>{{ section.title }}</h2>
              </div>

              <mat-accordion class="faq-accordion" multi>
                @for (item of section.items; track item.question) {
                  <mat-expansion-panel>
                    <mat-expansion-panel-header>
                      <mat-panel-title>
                        {{ item.question }}
                      </mat-panel-title>
                    </mat-expansion-panel-header>
                    <p class="answer">{{ item.answer }}</p>
                  </mat-expansion-panel>
                }
              </mat-accordion>
            </section>
          }

          <div class="cta-section">
            <h3>Still have questions?</h3>
            <p>Contact us through the form on our homepage or get started with a free account.</p>
            <div class="cta-buttons">
              <button mat-raised-button class="cta-button" routerLink="/">
                <mat-icon>rocket_launch</mat-icon>
                <span>Get Started Free</span>
              </button>
              <button mat-stroked-button class="cta-button-secondary" routerLink="/">
                <mat-icon>mail</mat-icon>
                <span>Contact Us</span>
              </button>
            </div>
          </div>
        </div>
      </main>

      <!-- Footer -->
      <footer class="faq-footer">
        <div class="container">
          <p>&copy; {{ currentYear }} DecisionRecords.org</p>
        </div>
      </footer>
    </div>
  `,
  styles: [`
    .faq-page {
      min-height: 100vh;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
    }

    .faq-header {
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #1e40af 100%);
      color: white;
      padding: 100px 24px 60px;
    }

    .container {
      max-width: 900px;
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

    .faq-header h1 {
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

    /* Section Navigation */
    .section-nav {
      background: white;
      border-bottom: 1px solid #e2e8f0;
      padding: 16px 24px;
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .nav-pills {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      justify-content: center;
    }

    .nav-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 18px;
      background: #f1f5f9;
      color: #475569;
      text-decoration: none;
      border-radius: 100px;
      font-size: 0.9rem;
      font-weight: 500;
      transition: all 0.2s;
    }

    .nav-pill:hover {
      background: #e2e8f0;
      color: #1e40af;
    }

    .nav-pill mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    /* FAQ Content */
    .faq-content {
      flex: 1;
      padding: 48px 24px;
    }

    .faq-section {
      margin-bottom: 48px;
      scroll-margin-top: 80px;
    }

    .section-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
    }

    .section-header mat-icon {
      font-size: 28px;
      width: 28px;
      height: 28px;
      color: #2563eb;
    }

    .section-header h2 {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0;
    }

    .faq-accordion {
      display: block;
    }

    ::ng-deep .faq-accordion .mat-expansion-panel {
      margin-bottom: 12px;
      border-radius: 12px !important;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
      border: 1px solid #e2e8f0;
    }

    ::ng-deep .faq-accordion .mat-expansion-panel:not(.mat-expanded) {
      background: white;
    }

    ::ng-deep .faq-accordion .mat-expansion-panel.mat-expanded {
      background: #fafbfc;
    }

    ::ng-deep .faq-accordion .mat-expansion-panel-header {
      padding: 20px 24px;
      height: auto !important;
    }

    ::ng-deep .faq-accordion .mat-expansion-panel-header-title {
      font-size: 1.05rem;
      font-weight: 500;
      color: #1e293b;
      line-height: 1.5;
    }

    ::ng-deep .faq-accordion .mat-expansion-panel-body {
      padding: 0 24px 20px;
    }

    .answer {
      font-size: 1rem;
      line-height: 1.75;
      color: #475569;
      margin: 0;
    }

    /* CTA Section */
    .cta-section {
      margin-top: 64px;
      text-align: center;
      padding: 48px;
      background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
      border-radius: 16px;
      border: 1px solid #bae6fd;
    }

    .cta-section h3 {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 12px;
    }

    .cta-section p {
      font-size: 1.05rem;
      color: #475569;
      margin: 0 0 24px;
    }

    .cta-buttons {
      display: flex;
      gap: 16px;
      justify-content: center;
      flex-wrap: wrap;
    }

    .cta-button {
      padding: 14px 28px !important;
      font-size: 15px !important;
      font-weight: 500 !important;
      border-radius: 100px !important;
      background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%) !important;
      color: white !important;
    }

    .cta-button mat-icon {
      margin-right: 8px;
    }

    .cta-button-secondary {
      padding: 14px 28px !important;
      font-size: 15px !important;
      font-weight: 500 !important;
      border-radius: 100px !important;
      border-color: #2563eb !important;
      color: #2563eb !important;
    }

    .cta-button-secondary mat-icon {
      margin-right: 8px;
    }

    /* Footer */
    .faq-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 24px;
      text-align: center;
    }

    .faq-footer p {
      margin: 0;
      font-size: 0.9rem;
    }

    /* Mobile Responsive */
    @media (max-width: 600px) {
      .faq-header {
        padding: 32px 16px 48px;
      }

      .faq-header h1 {
        font-size: 1.75rem;
      }

      .header-subtitle {
        font-size: 1rem;
      }

      .section-nav {
        padding: 12px 16px;
      }

      .nav-pills {
        gap: 8px;
      }

      .nav-pill {
        padding: 8px 14px;
        font-size: 0.85rem;
      }

      .nav-pill mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }

      .faq-content {
        padding: 32px 16px;
      }

      .section-header h2 {
        font-size: 1.25rem;
      }

      ::ng-deep .faq-accordion .mat-expansion-panel-header {
        padding: 16px 18px;
      }

      ::ng-deep .faq-accordion .mat-expansion-panel-header-title {
        font-size: 0.95rem;
      }

      ::ng-deep .faq-accordion .mat-expansion-panel-body {
        padding: 0 18px 16px;
      }

      .answer {
        font-size: 0.95rem;
      }

      .cta-section {
        padding: 32px 24px;
      }

      .cta-section h3 {
        font-size: 1.25rem;
      }

      .cta-buttons {
        flex-direction: column;
      }
    }
  `]
})
export class FaqComponent {
  currentYear = new Date().getFullYear();

  sections: FaqSection[] = [
    {
      title: 'General',
      icon: 'help_outline',
      items: [
        {
          question: 'What are decision records?',
          answer: 'Decision records are short documents that capture an important organisational decision, the context in which it was made, and the reasoning behind it. They focus on why a decision was taken, not just what was decided. Decision records help teams preserve context over time and avoid repeating the same discussions.'
        },
        {
          question: 'Why should organisations document decisions?',
          answer: 'Organisations document decisions to retain shared understanding as teams grow and change. When decisions are not recorded, context is lost and teams are forced to re-evaluate past choices. Documenting decisions improves communication, onboarding, and collaboration across teams.'
        },
        {
          question: 'What types of decisions are worth recording?',
          answer: 'Any decision that affects how a team works, builds, prices, operates, or communicates is worth recording. This includes product decisions, business strategy, hiring approaches, tooling choices, and operational trade-offs. The goal is not to record everything, but to record decisions that others will need to understand later.'
        },
        {
          question: 'How are decision records different from documentation or wikis?',
          answer: 'Documentation explains how things work today. Decision records explain why things were set up that way. Wikis often change over time, while decision records preserve historical context even when decisions are later revisited or reversed.'
        },
        {
          question: 'Who should use decision records?',
          answer: 'Decision records are useful for startups, growing teams, and established organisations across all functions. They are not limited to technical teams. Anyone involved in making or relying on decisions can benefit from shared decision memory.'
        },
        {
          question: 'What is DecisionRecords.org?',
          answer: 'DecisionRecords.org is a platform that helps organisations capture, store, and share important decisions with context. It provides long-term decision memory so teams can easily understand past choices and communicate them across the organisation.'
        },
        {
          question: 'Is DecisionRecords.org a documentation tool?',
          answer: 'No. DecisionRecords.org is focused specifically on decisions, not general documentation. It complements existing tools by providing a dedicated place for decision context and reasoning.'
        },
        {
          question: 'How much detail should a decision record include?',
          answer: 'A decision record should include enough context for someone unfamiliar with the situation to understand the reasoning. It should be concise, but complete. The aim is clarity, not exhaustive detail.'
        },
        {
          question: 'Can decision records change over time?',
          answer: 'Yes. Decisions can be revisited or superseded, but the original context should remain accessible. DecisionRecords.org preserves decision history so organisations can see how and why choices evolved.'
        }
      ]
    },
    {
      title: 'Features',
      icon: 'featured_play_list',
      items: [
        {
          question: 'How do I organise decisions in DecisionRecords.org?',
          answer: 'Decisions are organised into Spaces, which represent logical groupings such as projects, teams, or departments. Each Space can have its own set of decisions, making it easy to find and manage related records. You can create as many Spaces as your organisation needs.'
        },
        {
          question: 'What is included in a decision record?',
          answer: 'Each decision record includes a title, status, context, the decision itself, consequences, and optional metadata like tags and links. The structured format ensures consistency while remaining flexible enough to capture different types of decisions.'
        },
        {
          question: 'Can I search for past decisions?',
          answer: 'Yes. DecisionRecords.org provides full-text search across all your decisions. You can search by title, content, tags, or status to quickly find relevant records. Filters help narrow results by date, Space, or decision status.'
        },
        {
          question: 'Does DecisionRecords.org support collaboration?',
          answer: 'Yes. Team members can contribute to decisions, add comments, and track changes. Role-based access controls ensure that only authorised users can create, edit, or view decisions based on their permissions within the organisation.'
        },
        {
          question: 'Can I track the status of decisions?',
          answer: 'Decisions can have different statuses: Proposed, Accepted, Deprecated, or Superseded. This helps teams understand which decisions are current and which have been replaced or are no longer relevant.'
        },
        {
          question: 'Is there an API for integrating with other tools?',
          answer: 'DecisionRecords.org provides a REST API that allows you to create, read, update, and query decisions programmatically. This enables integration with existing workflows, CI/CD pipelines, or custom tooling.'
        },
        {
          question: 'Can I export my decisions?',
          answer: 'Yes. Decisions can be exported in Markdown format, making it easy to include them in documentation, version control systems, or external reports. The export preserves the full structure and metadata of each record.'
        }
      ]
    },
    {
      title: 'Governance',
      icon: 'admin_panel_settings',
      items: [
        {
          question: 'How does multi-tenancy work?',
          answer: 'Each organisation gets its own isolated tenant based on email domain. When you sign up with your work email, DecisionRecords.org automatically creates or joins your organisation\'s tenant. All decisions and data are completely isolated between tenants.'
        },
        {
          question: 'What roles are available in an organisation?',
          answer: 'Organisations have three roles: Admin, Contributor, and Viewer. Admins can manage users, Spaces, and settings. Contributors can create and edit decisions within their assigned Spaces. Viewers have read-only access to decisions they are permitted to see.'
        },
        {
          question: 'How do I control who can access our decisions?',
          answer: 'Access is controlled at multiple levels. Organisation admins manage who can join the tenant. Space-level permissions determine who can view or edit decisions within specific Spaces. This layered approach provides fine-grained control over sensitive information.'
        },
        {
          question: 'Can I require approval for new users?',
          answer: 'Yes. Admins can configure the organisation to require approval before new users gain access. When someone signs up with your domain, they are placed in a pending state until an admin approves their request.'
        },
        {
          question: 'How is authentication handled?',
          answer: 'DecisionRecords.org supports multiple authentication methods including passwordless login via email, passkeys (WebAuthn), and single sign-on (SSO) with your identity provider. Admins can configure which methods are available for their organisation.'
        },
        {
          question: 'Is there an audit trail for decisions?',
          answer: 'Yes. All changes to decisions are tracked with timestamps and user attribution. This provides a complete history of how decisions evolved, who made changes, and when modifications occurred.'
        },
        {
          question: 'Can I configure SSO for my organisation?',
          answer: 'Yes. Enterprise organisations can configure SAML or OIDC-based single sign-on to integrate with their existing identity provider. This allows employees to access DecisionRecords.org using their corporate credentials.'
        }
      ]
    },
    {
      title: 'Licensing',
      icon: 'verified',
      items: [
        {
          question: 'Is DecisionRecords.org free to use?',
          answer: 'DecisionRecords.org is currently in limited preview and is free for early users while we stabilise features and grow the community. We are committed to keeping a generous free tier available for small teams and startups.'
        },
        {
          question: 'What are the limits of the free tier?',
          answer: 'The free tier includes unlimited decisions and Spaces with a limit on the number of users per organisation. This is suitable for small teams getting started with decision records. The exact limits may be adjusted as the platform evolves.'
        },
        {
          question: 'Will there be paid plans in the future?',
          answer: 'Yes. We plan to introduce paid plans for larger organisations that need advanced features such as SSO integration, enhanced governance controls, priority support, and higher user limits. Free tier functionality will remain available.'
        },
        {
          question: 'Is DecisionRecords.org open source?',
          answer: 'Yes. The DecisionRecords.org platform is open source. You can self-host the platform if you prefer to run it on your own infrastructure. The source code is available on GitHub under an open source license.'
        },
        {
          question: 'Can I self-host DecisionRecords.org?',
          answer: 'Yes. Organisations that require complete control over their data can deploy DecisionRecords.org on their own infrastructure. Documentation is provided for Docker-based deployments. Self-hosted instances have access to the same features as the managed service.'
        },
        {
          question: 'What support is available?',
          answer: 'Community support is available through our GitHub repository for all users. Paid plans will include priority email support and dedicated assistance for enterprise deployments. Documentation and guides are freely available to help you get started.'
        },
        {
          question: 'How is my data protected?',
          answer: 'Data is encrypted at rest and in transit. The managed service runs on secure cloud infrastructure with regular backups. Each organisation\'s data is isolated and access is controlled through authentication and authorisation. We do not sell or share your data with third parties.'
        }
      ]
    }
  ];

  getSectionId(title: string): string {
    return title.toLowerCase().replace(/\s+/g, '-');
  }
}
