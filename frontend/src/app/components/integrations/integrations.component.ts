import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';

interface Integration {
  name: string;
  icon: string;
  iconType: 'material' | 'svg';
  svgPath?: string;
  status: 'available' | 'coming-soon' | 'planned';
  description: string;
  features: string[];
  link?: string;
}

@Component({
  selector: 'app-integrations',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule
  ],
  template: `
    <div class="integrations-page">
      <!-- Header -->
      <header class="integrations-header">
        <div class="container">
          <h1>Integrations</h1>
          <p class="header-subtitle">
            Connect Decision Records with the tools your team already uses
          </p>
        </div>
      </header>

      <!-- Content -->
      <main class="integrations-content">
        <div class="container">
          <p class="intro">
            Decision Records integrates with your existing workflow tools, making it easy to capture and share decisions where your team already collaborates.
          </p>

          <!-- Integration Cards -->
          <div class="integrations-grid">
            @for (integration of integrations; track integration.name) {
              <div class="integration-card" [class.available]="integration.status === 'available'" [class.coming-soon]="integration.status === 'coming-soon'">
                <div class="card-header">
                  <div class="integration-icon">
                    @if (integration.iconType === 'svg') {
                      <img [src]="integration.svgPath" [alt]="integration.name" />
                    } @else {
                      <mat-icon>{{ integration.icon }}</mat-icon>
                    }
                  </div>
                  <div class="integration-title">
                    <h2>{{ integration.name }}</h2>
                    <span class="status-badge" [class]="integration.status">
                      @if (integration.status === 'available') {
                        Available
                      } @else if (integration.status === 'coming-soon') {
                        Coming Soon
                      } @else {
                        Planned
                      }
                    </span>
                  </div>
                </div>
                <p class="integration-description">{{ integration.description }}</p>
                <ul class="integration-features">
                  @for (feature of integration.features; track feature) {
                    <li>
                      <mat-icon>check</mat-icon>
                      <span>{{ feature }}</span>
                    </li>
                  }
                </ul>
                @if (integration.link && integration.status === 'available') {
                  <a [routerLink]="integration.link" class="learn-more">
                    Learn more
                    <mat-icon>arrow_forward</mat-icon>
                  </a>
                }
              </div>
            }
          </div>

          <!-- API Section -->
          <section class="api-section">
            <div class="api-content">
              <div class="api-text">
                <h2>REST API</h2>
                <p>
                  Build custom integrations with our comprehensive REST API. Create, read, update, and query decisions programmatically to fit your unique workflow.
                </p>
                <ul class="api-features">
                  <li>
                    <mat-icon>code</mat-icon>
                    <span>Full CRUD operations for decisions</span>
                  </li>
                  <li>
                    <mat-icon>search</mat-icon>
                    <span>Search and filter capabilities</span>
                  </li>
                  <li>
                    <mat-icon>webhook</mat-icon>
                    <span>Webhook notifications (coming soon)</span>
                  </li>
                  <li>
                    <mat-icon>security</mat-icon>
                    <span>Secure token-based authentication</span>
                  </li>
                </ul>
              </div>
              <div class="api-visual">
                <div class="code-block">
                  <div class="code-header">
                    <span class="code-dot"></span>
                    <span class="code-dot"></span>
                    <span class="code-dot"></span>
                  </div>
                  <pre><code>GET /api/decisions
Authorization: Bearer your-token

{{ '{' }}
  "decisions": [
    {{ '{' }}
      "id": "dr-001",
      "title": "Use PostgreSQL",
      "status": "accepted",
      "context": "..."
    {{ '}' }}
  ]
{{ '}' }}</code></pre>
                </div>
              </div>
            </div>
          </section>

          <!-- Request Integration -->
          <section class="request-section">
            <h2>Need a different integration?</h2>
            <p>We're always looking to expand our integration ecosystem. Let us know what tools you'd like us to support.</p>
            <button mat-stroked-button class="request-button" routerLink="/">
              <mat-icon>mail</mat-icon>
              <span>Contact Us</span>
            </button>
          </section>
        </div>
      </main>
    </div>
  `,
  styles: [`
    .integrations-page {
      min-height: 100vh;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
    }

    .integrations-header {
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #1e40af 100%);
      color: white;
      padding: 100px 24px 60px;
    }

    .container {
      max-width: 1000px;
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

    .integrations-header h1 {
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

    .integrations-content {
      flex: 1;
      padding: 60px 24px;
    }

    .intro {
      font-size: 1.15rem;
      color: #475569;
      line-height: 1.7;
      margin: 0 0 48px;
      max-width: 700px;
    }

    .integrations-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      margin-bottom: 64px;
    }

    .integration-card {
      background: white;
      border-radius: 16px;
      padding: 28px;
      border: 1px solid #e2e8f0;
      transition: all 0.2s;
    }

    .integration-card.available:hover {
      border-color: #2563eb;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
    }

    .integration-card.coming-soon {
      opacity: 0.85;
    }

    .card-header {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 16px;
    }

    .integration-icon {
      width: 48px;
      height: 48px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #f1f5f9;
      border-radius: 12px;
      flex-shrink: 0;
    }

    .integration-icon img {
      width: 32px;
      height: 32px;
    }

    .integration-icon mat-icon {
      font-size: 28px;
      width: 28px;
      height: 28px;
      color: #475569;
    }

    .integration-title {
      flex: 1;
    }

    .integration-title h2 {
      font-size: 1.25rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 6px;
    }

    .status-badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 100px;
      font-size: 0.75rem;
      font-weight: 500;
    }

    .status-badge.available {
      background: #dcfce7;
      color: #166534;
    }

    .status-badge.coming-soon {
      background: #fef3c7;
      color: #92400e;
    }

    .status-badge.planned {
      background: #f1f5f9;
      color: #475569;
    }

    .integration-description {
      font-size: 0.95rem;
      color: #64748b;
      line-height: 1.6;
      margin: 0 0 16px;
    }

    .integration-features {
      list-style: none;
      padding: 0;
      margin: 0 0 16px;
    }

    .integration-features li {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.9rem;
      color: #475569;
      margin-bottom: 8px;
    }

    .integration-features mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      color: #22c55e;
    }

    .learn-more {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #2563eb;
      text-decoration: none;
      font-size: 0.9rem;
      font-weight: 500;
      transition: gap 0.2s;
    }

    .learn-more:hover {
      gap: 10px;
    }

    .learn-more mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    /* API Section */
    .api-section {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      border-radius: 20px;
      padding: 48px;
      margin-bottom: 64px;
    }

    .api-content {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 48px;
      align-items: center;
    }

    .api-text h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: white;
      margin: 0 0 16px;
    }

    .api-text p {
      font-size: 1.05rem;
      color: #94a3b8;
      line-height: 1.7;
      margin: 0 0 24px;
    }

    .api-features {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .api-features li {
      display: flex;
      align-items: center;
      gap: 12px;
      color: #e2e8f0;
      font-size: 0.95rem;
      margin-bottom: 12px;
    }

    .api-features mat-icon {
      color: #60a5fa;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .code-block {
      background: #1e293b;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid #334155;
    }

    .code-header {
      display: flex;
      gap: 6px;
      padding: 12px 16px;
      background: #0f172a;
    }

    .code-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #475569;
    }

    .code-block pre {
      margin: 0;
      padding: 20px;
      overflow-x: auto;
    }

    .code-block code {
      font-family: 'Fira Code', 'Consolas', monospace;
      font-size: 0.85rem;
      color: #e2e8f0;
      line-height: 1.6;
    }

    /* Request Section */
    .request-section {
      text-align: center;
      padding: 48px;
      background: white;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
    }

    .request-section h2 {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 12px;
    }

    .request-section p {
      font-size: 1.05rem;
      color: #64748b;
      margin: 0 0 24px;
    }

    .request-button {
      padding: 12px 28px !important;
      font-size: 15px !important;
      border-radius: 100px !important;
      border-color: #2563eb !important;
      color: #2563eb !important;
    }

    .request-button mat-icon {
      margin-right: 8px;
    }

    .integrations-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 24px;
      text-align: center;
    }

    .integrations-footer p {
      margin: 0;
      font-size: 0.9rem;
    }

    @media (max-width: 768px) {
      .integrations-header {
        padding: 32px 16px 48px;
      }

      .integrations-header h1 {
        font-size: 1.75rem;
      }

      .integrations-content {
        padding: 40px 16px;
      }

      .integrations-grid {
        grid-template-columns: 1fr;
      }

      .api-section {
        padding: 32px 24px;
      }

      .api-content {
        grid-template-columns: 1fr;
        gap: 32px;
      }

      .api-visual {
        display: none;
      }

      .request-section {
        padding: 32px 24px;
      }
    }
  `]
})
export class IntegrationsComponent {
  integrations: Integration[] = [
    {
      name: 'Slack',
      icon: 'chat',
      iconType: 'svg',
      svgPath: '/assets/slack-logo.svg',
      status: 'available',
      description: 'Capture decisions directly from Slack conversations. Get notified when decisions are created or updated.',
      features: [
        'Create decisions from Slack messages',
        'Browse and search decisions in Slack',
        'Receive notifications for decision updates',
        'Link Slack accounts for seamless access'
      ],
      link: '/integrations/slack'
    },
    {
      name: 'MCP Server',
      icon: 'terminal',
      iconType: 'material',
      status: 'available',
      description: 'Connect Claude Code, Cursor, VS Code and other MCP-compatible tools to your decision records.',
      features: [
        'Search decisions from your IDE',
        'Read full decision context inline',
        'Create decisions while coding',
        'Works with any MCP-compatible tool'
      ],
      link: '/integrations/mcp'
    },
    {
      name: 'AI API / Custom GPTs',
      icon: 'auto_awesome',
      iconType: 'material',
      status: 'available',
      description: 'Build Custom GPTs and AI agents that can search, read, and create decision records.',
      features: [
        'REST API for AI integrations',
        'OpenAPI schema for Custom GPTs',
        'Create AI assistants with decision access',
        'Workflow automation support'
      ],
      link: '/integrations/ai-api'
    },
    {
      name: 'Microsoft Teams',
      icon: 'groups',
      iconType: 'material',
      status: 'coming-soon',
      description: 'Bring decision records to your Teams workspace. Create and manage decisions without leaving Teams.',
      features: [
        'Create decisions from Teams messages',
        'Teams bot for quick access',
        'Channel notifications for updates',
        'SSO with Microsoft accounts'
      ]
    },
    {
      name: 'Jira',
      icon: 'task_alt',
      iconType: 'material',
      status: 'planned',
      description: 'Link decisions to Jira issues and epics. Understand the decisions behind your tickets.',
      features: [
        'Link decisions to Jira issues',
        'View related decisions in Jira',
        'Create decisions from epic discussions',
        'Sync decision status with workflows'
      ]
    },
    {
      name: 'Confluence',
      icon: 'article',
      iconType: 'material',
      status: 'planned',
      description: 'Embed decision records in Confluence pages. Keep documentation and decisions in sync.',
      features: [
        'Embed decision cards in pages',
        'Create decisions from Confluence',
        'Auto-link related documentation',
        'Export decisions as Confluence pages'
      ]
    }
  ];
}
