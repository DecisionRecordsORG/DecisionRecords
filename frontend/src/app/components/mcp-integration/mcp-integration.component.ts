import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-mcp-integration',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="mcp-page">
      <!-- Hero Section -->
      <header class="mcp-hero">
        <div class="container">
          <div class="hero-content">
            <div class="hero-badge">
              <mat-icon class="mcp-icon">terminal</mat-icon>
              <span>+</span>
              <img src="/assets/decision-records-logo-white.svg" alt="Decision Records" class="dr-icon" />
            </div>
            <h1>MCP Server Integration</h1>
            <p class="hero-tagline">
              Access decision records directly from your development tools
            </p>
            <p class="hero-description">
              Connect Claude Code, Cursor, VS Code, and other MCP-compatible tools to search, read, and create architecture decisions without leaving your IDE.
            </p>
          </div>
        </div>
      </header>

      <!-- Supported Tools Section -->
      <section class="tools-section">
        <div class="container">
          <h2>Supported Development Tools</h2>

          <div class="tools-grid">
            <div class="tool-card">
              <div class="tool-icon claude">
                <mat-icon>smart_toy</mat-icon>
              </div>
              <h3>Claude Code</h3>
              <p>Anthropic's AI coding assistant with native MCP support</p>
            </div>

            <div class="tool-card">
              <div class="tool-icon cursor">
                <mat-icon>edit_note</mat-icon>
              </div>
              <h3>Cursor</h3>
              <p>AI-first code editor with MCP server configuration</p>
            </div>

            <div class="tool-card">
              <div class="tool-icon vscode">
                <mat-icon>code</mat-icon>
              </div>
              <h3>VS Code</h3>
              <p>Via MCP extension for Visual Studio Code</p>
            </div>

            <div class="tool-card">
              <div class="tool-icon other">
                <mat-icon>extension</mat-icon>
              </div>
              <h3>Other MCP Tools</h3>
              <p>Any tool supporting the Model Context Protocol</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Features Section -->
      <section class="features-section">
        <div class="container">
          <h2>What You Can Do</h2>

          <div class="features-grid">
            <div class="feature-card">
              <div class="feature-icon">
                <mat-icon>search</mat-icon>
              </div>
              <h3>Search Decisions</h3>
              <p>
                Find relevant decisions using natural language queries. Filter by status, search across all fields.
              </p>
            </div>

            <div class="feature-card">
              <div class="feature-icon">
                <mat-icon>visibility</mat-icon>
              </div>
              <h3>Read Full Context</h3>
              <p>
                Access complete decision records including context, rationale, and consequences.
              </p>
            </div>

            <div class="feature-card">
              <div class="feature-icon">
                <mat-icon>add_circle</mat-icon>
              </div>
              <h3>Create Decisions</h3>
              <p>
                Draft new decisions directly from your IDE when you make architectural choices in code.
              </p>
            </div>

            <div class="feature-card">
              <div class="feature-icon">
                <mat-icon>history</mat-icon>
              </div>
              <h3>View Change History</h3>
              <p>
                Track how decisions evolved over time with full audit history.
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- Available Tools Section -->
      <section class="mcp-tools-section">
        <div class="container">
          <h2>Available MCP Tools</h2>

          <div class="tools-list">
            <div class="tool-item">
              <code>search_decisions</code>
              <p>Search decisions using keywords and optional status filter</p>
            </div>
            <div class="tool-item">
              <code>get_decision</code>
              <p>Get full details of a specific decision by ID (e.g., ADR-42)</p>
            </div>
            <div class="tool-item">
              <code>list_decisions</code>
              <p>List decisions with pagination and sorting options</p>
            </div>
            <div class="tool-item">
              <code>create_decision</code>
              <p>Create a new decision record (requires write scope)</p>
            </div>
            <div class="tool-item">
              <code>get_decision_history</code>
              <p>View the change history of a decision</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Setup Section -->
      <section class="setup-section">
        <div class="container">
          <h2>Quick Setup</h2>

          <div class="setup-steps">
            <div class="step">
              <div class="step-number">1</div>
              <div class="step-content">
                <h3>Generate an API Key</h3>
                <p>Go to your account settings in Decision Records and create a new API key with the scopes you need (read, search, write).</p>
              </div>
            </div>

            <div class="step">
              <div class="step-number">2</div>
              <div class="step-content">
                <h3>Configure Your Tool</h3>
                <p>Add the MCP server configuration to your development tool. The server URL and authentication details are provided below.</p>
              </div>
            </div>

            <div class="step">
              <div class="step-number">3</div>
              <div class="step-content">
                <h3>Start Using</h3>
                <p>Your AI assistant can now search, read, and create decision records directly in your workflow.</p>
              </div>
            </div>
          </div>

          <!-- Configuration Examples -->
          <div class="config-examples">
            <h3>Configuration Examples</h3>

            <div class="config-card">
              <div class="config-header">
                <span class="config-title">Claude Code / Cursor</span>
              </div>
              <div class="code-block">
                <pre><code>{{ '{' }}
  "mcpServers": {{ '{' }}
    "decision-records": {{ '{' }}
      "url": "https://decisionrecords.org/api/mcp",
      "headers": {{ '{' }}
        "Authorization": "Bearer adr_your_api_key_here"
      {{ '}' }}
    {{ '}' }}
  {{ '}' }}
{{ '}' }}</code></pre>
              </div>
            </div>

            <div class="config-card">
              <div class="config-header">
                <span class="config-title">API Endpoint</span>
              </div>
              <div class="code-block">
                <pre><code>POST https://decisionrecords.org/api/mcp
Authorization: Bearer adr_your_api_key_here
Content-Type: application/json

{{ '{' }}
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
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
              <h2>Secure by Design</h2>
              <p>
                The MCP server integration uses your personal API keys with scoped permissions, ensuring your team's data stays protected.
              </p>
              <ul>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>API keys are SHA256 hashed and never stored in plaintext</span>
                </li>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>Scoped permissions (read, search, write)</span>
                </li>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>All interactions are logged for audit</span>
                </li>
                <li>
                  <mat-icon>check</mat-icon>
                  <span>Tenant isolation ensures data privacy</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- CTA Section -->
      <section class="cta-section">
        <div class="container">
          <h2>Ready to integrate with your IDE?</h2>
          <p>Generate an API key and start accessing decisions from your development tools</p>
          <a routerLink="/dashboard" class="cta-button">
            <mat-icon>vpn_key</mat-icon>
            <span>Generate API Key</span>
          </a>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .mcp-page {
      min-height: 100vh;
      background: #f8fafc;
    }

    .container {
      max-width: 1000px;
      margin: 0 auto;
      padding: 0 24px;
    }

    /* Hero */
    .mcp-hero {
      background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #1e40af 100%);
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
      background: rgba(255, 255, 255, 0.1);
      border-radius: 100px;
    }

    .hero-badge span {
      font-size: 1.5rem;
      color: rgba(255, 255, 255, 0.6);
    }

    .mcp-icon {
      font-size: 40px;
      width: 40px;
      height: 40px;
      color: #60a5fa;
    }

    .dr-icon {
      height: 32px;
      width: auto;
    }

    .mcp-hero h1 {
      font-size: 2.75rem;
      font-weight: 700;
      margin: 0 0 16px;
      letter-spacing: -0.02em;
    }

    .hero-tagline {
      font-size: 1.35rem;
      color: rgba(255, 255, 255, 0.9);
      margin: 0 0 16px;
      line-height: 1.5;
    }

    .hero-description {
      font-size: 1.1rem;
      color: rgba(255, 255, 255, 0.7);
      margin: 0;
      line-height: 1.6;
    }

    /* Supported Tools */
    .tools-section {
      padding: 80px 0;
    }

    .tools-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .tools-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 24px;
    }

    .tool-card {
      background: white;
      padding: 28px 20px;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
      text-align: center;
    }

    .tool-icon {
      width: 56px;
      height: 56px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 16px;
    }

    .tool-icon.claude {
      background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
    }

    .tool-icon.cursor {
      background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%);
    }

    .tool-icon.vscode {
      background: linear-gradient(135deg, #0078d4 0%, #00bcf2 100%);
    }

    .tool-icon.other {
      background: linear-gradient(135deg, #475569 0%, #64748b 100%);
    }

    .tool-icon mat-icon {
      color: white;
      font-size: 28px;
      width: 28px;
      height: 28px;
    }

    .tool-card h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
    }

    .tool-card p {
      font-size: 0.9rem;
      color: #64748b;
      line-height: 1.5;
      margin: 0;
    }

    /* Features */
    .features-section {
      padding: 80px 0;
      background: #f1f5f9;
    }

    .features-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .features-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
    }

    .feature-card {
      background: white;
      padding: 28px;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
    }

    .feature-icon {
      width: 48px;
      height: 48px;
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
    }

    .feature-icon mat-icon {
      color: white;
      font-size: 24px;
      width: 24px;
      height: 24px;
    }

    .feature-card h3 {
      font-size: 1.15rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
    }

    .feature-card p {
      font-size: 0.95rem;
      color: #64748b;
      line-height: 1.6;
      margin: 0;
    }

    /* MCP Tools List */
    .mcp-tools-section {
      padding: 80px 0;
    }

    .mcp-tools-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .tools-list {
      max-width: 700px;
      margin: 0 auto;
    }

    .tool-item {
      background: #1e293b;
      padding: 20px 24px;
      border-radius: 12px;
      margin-bottom: 12px;
    }

    .tool-item:last-child {
      margin-bottom: 0;
    }

    .tool-item code {
      display: block;
      font-family: 'Fira Code', 'Consolas', monospace;
      font-size: 1rem;
      color: #22d3ee;
      margin-bottom: 8px;
    }

    .tool-item p {
      font-size: 0.9rem;
      color: #94a3b8;
      margin: 0;
    }

    /* Setup */
    .setup-section {
      padding: 80px 0;
      background: #f1f5f9;
    }

    .setup-section h2 {
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
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
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

    .config-examples {
      max-width: 700px;
      margin: 0 auto;
    }

    .config-examples h3 {
      font-size: 1.25rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 24px;
      text-align: center;
    }

    .config-card {
      background: #1e293b;
      border-radius: 12px;
      overflow: hidden;
      margin-bottom: 16px;
    }

    .config-header {
      padding: 12px 20px;
      background: #0f172a;
      border-bottom: 1px solid #334155;
    }

    .config-title {
      font-size: 0.9rem;
      font-weight: 500;
      color: #94a3b8;
    }

    .code-block {
      padding: 20px;
      overflow-x: auto;
    }

    .code-block pre {
      margin: 0;
    }

    .code-block code {
      font-family: 'Fira Code', 'Consolas', monospace;
      font-size: 0.85rem;
      color: #e2e8f0;
      line-height: 1.6;
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
      color: #1e3a8a;
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

    .cta-button {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      padding: 14px 32px;
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
      color: white;
      font-size: 1.1rem;
      font-weight: 600;
      border-radius: 8px;
      text-decoration: none;
      transition: all 0.2s;
      box-shadow: 0 2px 8px rgba(30, 58, 138, 0.3);
    }

    .cta-button:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(30, 58, 138, 0.4);
    }

    .cta-button mat-icon {
      font-size: 22px;
      width: 22px;
      height: 22px;
    }

    @media (max-width: 768px) {
      .mcp-hero {
        padding: 32px 0 60px;
      }

      .mcp-hero h1 {
        font-size: 2rem;
      }

      .hero-tagline {
        font-size: 1.1rem;
      }

      .tools-section,
      .features-section,
      .mcp-tools-section,
      .setup-section,
      .security-section,
      .cta-section {
        padding: 60px 0;
      }

      .tools-grid {
        grid-template-columns: repeat(2, 1fr);
      }

      .features-grid {
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
    }

    @media (max-width: 480px) {
      .tools-grid {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class McpIntegrationComponent {}
