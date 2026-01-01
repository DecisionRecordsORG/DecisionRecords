import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-ai-api-integration',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="ai-api-page">
      <!-- Hero Section -->
      <header class="ai-api-hero">
        <div class="container">
          <div class="hero-content">
            <div class="hero-badge">
              <mat-icon class="ai-icon">auto_awesome</mat-icon>
              <span>+</span>
              <img src="/assets/decision-records-logo-white.svg" alt="Decision Records" class="dr-icon" />
            </div>
            <h1>AI API for Custom GPTs</h1>
            <p class="hero-tagline">
              Build AI assistants that understand your architecture decisions
            </p>
            <p class="hero-description">
              Use our REST API to create Custom GPTs, AI agents, and integrations that can search, read, and create decision records.
            </p>
          </div>
        </div>
      </header>

      <!-- Use Cases Section -->
      <section class="use-cases-section">
        <div class="container">
          <h2>What You Can Build</h2>

          <div class="use-cases-grid">
            <div class="use-case-card">
              <div class="use-case-icon gpt">
                <mat-icon>chat</mat-icon>
              </div>
              <h3>Custom GPTs</h3>
              <p>Create ChatGPT assistants that can access your organization's decision records and help with architecture questions.</p>
            </div>

            <div class="use-case-card">
              <div class="use-case-icon agent">
                <mat-icon>smart_toy</mat-icon>
              </div>
              <h3>AI Agents</h3>
              <p>Build autonomous agents that reference decisions when making recommendations or answering questions.</p>
            </div>

            <div class="use-case-card">
              <div class="use-case-icon workflow">
                <mat-icon>account_tree</mat-icon>
              </div>
              <h3>Workflow Automation</h3>
              <p>Integrate decision records into your CI/CD pipelines, PR reviews, or documentation workflows.</p>
            </div>

            <div class="use-case-card">
              <div class="use-case-icon custom">
                <mat-icon>build</mat-icon>
              </div>
              <h3>Custom Integrations</h3>
              <p>Connect Decision Records to any tool or platform using our comprehensive REST API.</p>
            </div>
          </div>
        </div>
      </section>

      <!-- API Endpoints Section -->
      <section class="endpoints-section">
        <div class="container">
          <h2>API Endpoints</h2>

          <div class="endpoints-list">
            <div class="endpoint-card">
              <div class="endpoint-method post">POST</div>
              <div class="endpoint-details">
                <code>/api/ai/search</code>
                <p>Search decisions using keywords and optional filters</p>
              </div>
            </div>

            <div class="endpoint-card">
              <div class="endpoint-method get">GET</div>
              <div class="endpoint-details">
                <code>/api/ai/decisions</code>
                <p>List decisions with pagination, filtering, and sorting</p>
              </div>
            </div>

            <div class="endpoint-card">
              <div class="endpoint-method get">GET</div>
              <div class="endpoint-details">
                <code>/api/ai/decisions/:id</code>
                <p>Get full details of a specific decision</p>
              </div>
            </div>

            <div class="endpoint-card">
              <div class="endpoint-method post">POST</div>
              <div class="endpoint-details">
                <code>/api/ai/decisions</code>
                <p>Create a new decision record (requires write scope)</p>
              </div>
            </div>

            <div class="endpoint-card">
              <div class="endpoint-method get">GET</div>
              <div class="endpoint-details">
                <code>/api/ai/decisions/:id/history</code>
                <p>View the change history of a decision</p>
              </div>
            </div>

            <div class="endpoint-card schema">
              <div class="endpoint-method schema">SCHEMA</div>
              <div class="endpoint-details">
                <code>/api/ai/openapi.json</code>
                <p>OpenAPI 3.1 schema for Custom GPT configuration</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Custom GPT Setup -->
      <section class="gpt-setup-section">
        <div class="container">
          <h2>Create a Custom GPT</h2>

          <div class="setup-steps">
            <div class="step">
              <div class="step-number">1</div>
              <div class="step-content">
                <h3>Generate an API Key</h3>
                <p>Create an API key in Decision Records with the scopes you need. For read-only access, select "read" and "search" scopes.</p>
              </div>
            </div>

            <div class="step">
              <div class="step-number">2</div>
              <div class="step-content">
                <h3>Create Your GPT</h3>
                <p>In ChatGPT, go to "Create a GPT" and configure it with a name, description, and instructions for how it should use decisions.</p>
              </div>
            </div>

            <div class="step">
              <div class="step-number">3</div>
              <div class="step-content">
                <h3>Add the Action</h3>
                <p>In the GPT configuration, add an action using our OpenAPI schema URL. This tells the GPT what API calls it can make.</p>
              </div>
            </div>

            <div class="step">
              <div class="step-number">4</div>
              <div class="step-content">
                <h3>Configure Authentication</h3>
                <p>Set authentication to "API Key" with type "Bearer", then paste your Decision Records API key.</p>
              </div>
            </div>
          </div>

          <!-- OpenAPI Schema -->
          <div class="schema-card">
            <div class="schema-header">
              <mat-icon>description</mat-icon>
              <div>
                <h3>OpenAPI Schema URL</h3>
                <p>Use this URL when configuring your Custom GPT action</p>
              </div>
            </div>
            <div class="schema-url">
              <code>https://decisionrecords.org/api/ai/openapi.json</code>
            </div>
          </div>
        </div>
      </section>

      <!-- Example Request/Response -->
      <section class="examples-section">
        <div class="container">
          <h2>Example Usage</h2>

          <div class="example-grid">
            <div class="example-card">
              <h3>Search Decisions</h3>
              <div class="code-block">
                <div class="code-header">
                  <span>Request</span>
                </div>
                <pre><code>curl -X POST https://decisionrecords.org/api/ai/search \\
  -H "Authorization: Bearer adr_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{{ '{' }}"query": "authentication"{{ '}' }}'</code></pre>
              </div>
              <div class="code-block">
                <div class="code-header">
                  <span>Response</span>
                </div>
                <pre><code>{{ '{' }}
  "query": "authentication",
  "count": 2,
  "decisions": [
    {{ '{' }}
      "id": 42,
      "display_id": "ADR-42",
      "title": "Use OAuth2 for API auth",
      "status": "accepted"
    {{ '}' }}
  ]
{{ '}' }}</code></pre>
              </div>
            </div>

            <div class="example-card">
              <h3>Get Decision</h3>
              <div class="code-block">
                <div class="code-header">
                  <span>Request</span>
                </div>
                <pre><code>curl https://decisionrecords.org/api/ai/decisions/ADR-42 \\
  -H "Authorization: Bearer adr_your_key"</code></pre>
              </div>
              <div class="code-block">
                <div class="code-header">
                  <span>Response</span>
                </div>
                <pre><code>{{ '{' }}
  "id": 42,
  "display_id": "ADR-42",
  "title": "Use OAuth2 for API auth",
  "status": "accepted",
  "context": "We need secure...",
  "decision": "We will use...",
  "consequences": "Positive:..."
{{ '}' }}</code></pre>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Security Section -->
      <section class="security-section">
        <div class="container">
          <div class="security-content">
            <mat-icon>security</mat-icon>
            <div>
              <h2>Secure API Access</h2>
              <p>
                All API access is authenticated and logged, with fine-grained permission controls.
              </p>
              <ul>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>Bearer token authentication</span>
                </li>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>Scoped permissions (read, search, write)</span>
                </li>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>Optional key expiration</span>
                </li>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>Full audit logging of all API calls</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- CTA Section -->
      <section class="cta-section">
        <div class="container">
          <h2>Ready to build your AI integration?</h2>
          <p>Generate an API key and start building with decision records</p>
          <div class="cta-buttons">
            <a routerLink="/dashboard" class="cta-button primary">
              <mat-icon>vpn_key</mat-icon>
              <span>Generate API Key</span>
            </a>
            <a href="/api/ai/openapi.json" target="_blank" class="cta-button secondary">
              <mat-icon>description</mat-icon>
              <span>View OpenAPI Schema</span>
            </a>
          </div>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .ai-api-page {
      min-height: 100vh;
      background: #f8fafc;
    }

    .container {
      max-width: 1000px;
      margin: 0 auto;
      padding: 0 24px;
    }

    /* Hero */
    .ai-api-hero {
      background: linear-gradient(135deg, #059669 0%, #10b981 50%, #34d399 100%);
      color: white;
      padding: 100px 0 80px;
    }

    .hero-content {
      text-align: center;
      max-width: 700px;
      margin: 0 auto;
    }

    .hero-badge {
      display: inline-flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 24px;
      padding: 12px 24px;
      background: rgba(255, 255, 255, 0.15);
      border-radius: 100px;
    }

    .hero-badge span {
      font-size: 1.5rem;
      color: rgba(255, 255, 255, 0.6);
    }

    .ai-icon {
      font-size: 40px;
      width: 40px;
      height: 40px;
      color: white;
    }

    .dr-icon {
      height: 32px;
      width: auto;
    }

    .ai-api-hero h1 {
      font-size: 2.75rem;
      font-weight: 700;
      margin: 0 0 16px;
      letter-spacing: -0.02em;
    }

    .hero-tagline {
      font-size: 1.35rem;
      color: rgba(255, 255, 255, 0.95);
      margin: 0 0 16px;
      line-height: 1.5;
    }

    .hero-description {
      font-size: 1.1rem;
      color: rgba(255, 255, 255, 0.8);
      margin: 0;
      line-height: 1.6;
    }

    /* Use Cases */
    .use-cases-section {
      padding: 80px 0;
    }

    .use-cases-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .use-cases-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
    }

    .use-case-card {
      background: white;
      padding: 28px;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
    }

    .use-case-icon {
      width: 56px;
      height: 56px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
    }

    .use-case-icon.gpt {
      background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
    }

    .use-case-icon.agent {
      background: linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%);
    }

    .use-case-icon.workflow {
      background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
    }

    .use-case-icon.custom {
      background: linear-gradient(135deg, #3b82f6 0%, #60a5fa 100%);
    }

    .use-case-icon mat-icon {
      color: white;
      font-size: 28px;
      width: 28px;
      height: 28px;
    }

    .use-case-card h3 {
      font-size: 1.15rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
    }

    .use-case-card p {
      font-size: 0.95rem;
      color: #64748b;
      line-height: 1.6;
      margin: 0;
    }

    /* Endpoints */
    .endpoints-section {
      padding: 80px 0;
      background: #f1f5f9;
    }

    .endpoints-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .endpoints-list {
      max-width: 700px;
      margin: 0 auto;
    }

    .endpoint-card {
      background: white;
      padding: 16px 20px;
      border-radius: 12px;
      border: 1px solid #e2e8f0;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .endpoint-card.schema {
      background: #fef3c7;
      border-color: #fbbf24;
    }

    .endpoint-method {
      font-size: 0.75rem;
      font-weight: 700;
      padding: 6px 12px;
      border-radius: 6px;
      flex-shrink: 0;
    }

    .endpoint-method.get {
      background: #dbeafe;
      color: #1d4ed8;
    }

    .endpoint-method.post {
      background: #dcfce7;
      color: #166534;
    }

    .endpoint-method.schema {
      background: #fef3c7;
      color: #92400e;
    }

    .endpoint-details code {
      display: block;
      font-family: 'Fira Code', monospace;
      font-size: 0.95rem;
      color: #0f172a;
      margin-bottom: 4px;
    }

    .endpoint-details p {
      font-size: 0.85rem;
      color: #64748b;
      margin: 0;
    }

    /* GPT Setup */
    .gpt-setup-section {
      padding: 80px 0;
    }

    .gpt-setup-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .setup-steps {
      max-width: 600px;
      margin: 0 auto 48px;
    }

    .step {
      display: flex;
      gap: 24px;
      margin-bottom: 32px;
    }

    .step:last-child {
      margin-bottom: 0;
    }

    .step-number {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, #059669 0%, #10b981 100%);
      color: white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 1.1rem;
      flex-shrink: 0;
    }

    .step-content h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
    }

    .step-content p {
      font-size: 0.95rem;
      color: #64748b;
      line-height: 1.6;
      margin: 0;
    }

    .schema-card {
      max-width: 600px;
      margin: 0 auto;
      background: white;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
      overflow: hidden;
    }

    .schema-header {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px 24px;
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
    }

    .schema-header mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      color: #059669;
    }

    .schema-header h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 4px;
    }

    .schema-header p {
      font-size: 0.9rem;
      color: #64748b;
      margin: 0;
    }

    .schema-url {
      padding: 20px 24px;
      background: #1e293b;
    }

    .schema-url code {
      font-family: 'Fira Code', monospace;
      font-size: 0.95rem;
      color: #22d3ee;
    }

    /* Examples */
    .examples-section {
      padding: 80px 0;
      background: #f1f5f9;
    }

    .examples-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .example-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
    }

    .example-card {
      background: white;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
      overflow: hidden;
    }

    .example-card h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #0f172a;
      padding: 20px 24px;
      margin: 0;
      border-bottom: 1px solid #e2e8f0;
    }

    .code-block {
      background: #1e293b;
    }

    .code-header {
      padding: 8px 16px;
      background: #0f172a;
      border-bottom: 1px solid #334155;
    }

    .code-header span {
      font-size: 0.8rem;
      font-weight: 500;
      color: #94a3b8;
    }

    .code-block pre {
      margin: 0;
      padding: 16px;
      overflow-x: auto;
    }

    .code-block code {
      font-family: 'Fira Code', monospace;
      font-size: 0.8rem;
      color: #e2e8f0;
      line-height: 1.5;
    }

    /* Security */
    .security-section {
      padding: 80px 0;
    }

    .security-content {
      display: flex;
      gap: 32px;
      align-items: flex-start;
      max-width: 700px;
      margin: 0 auto;
    }

    .security-content > mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #059669;
      flex-shrink: 0;
    }

    .security-content h2 {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 12px;
    }

    .security-content > div > p {
      font-size: 1rem;
      color: #64748b;
      line-height: 1.6;
      margin: 0 0 20px;
    }

    .security-content ul {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .security-content li {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 0.95rem;
      color: #334155;
      margin-bottom: 12px;
    }

    .security-content li mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
      color: #22c55e;
    }

    /* CTA */
    .cta-section {
      padding: 80px 0;
      background: #f1f5f9;
      text-align: center;
    }

    .cta-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 12px;
    }

    .cta-section p {
      font-size: 1.1rem;
      color: #64748b;
      margin: 0 0 32px;
    }

    .cta-buttons {
      display: flex;
      gap: 16px;
      justify-content: center;
    }

    .cta-button {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 14px 28px;
      font-size: 1rem;
      font-weight: 600;
      border-radius: 8px;
      text-decoration: none;
      transition: all 0.2s;
    }

    .cta-button.primary {
      background: linear-gradient(135deg, #059669 0%, #10b981 100%);
      color: white;
      box-shadow: 0 2px 8px rgba(5, 150, 105, 0.3);
    }

    .cta-button.primary:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(5, 150, 105, 0.4);
    }

    .cta-button.secondary {
      background: white;
      color: #059669;
      border: 2px solid #059669;
    }

    .cta-button.secondary:hover {
      background: #ecfdf5;
    }

    .cta-button mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    @media (max-width: 768px) {
      .ai-api-hero {
        padding: 32px 0 60px;
      }

      .ai-api-hero h1 {
        font-size: 2rem;
      }

      .hero-tagline {
        font-size: 1.1rem;
      }

      .use-cases-section,
      .endpoints-section,
      .gpt-setup-section,
      .examples-section,
      .security-section,
      .cta-section {
        padding: 60px 0;
      }

      .use-cases-grid,
      .example-grid {
        grid-template-columns: 1fr;
      }

      .security-content {
        flex-direction: column;
        text-align: center;
      }

      .security-content > mat-icon {
        margin: 0 auto;
      }

      .security-content li {
        justify-content: center;
      }

      .cta-buttons {
        flex-direction: column;
        align-items: center;
      }
    }
  `]
})
export class AiApiIntegrationComponent {}
