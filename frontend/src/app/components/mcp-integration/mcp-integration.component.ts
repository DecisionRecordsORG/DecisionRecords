import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { Clipboard, ClipboardModule } from '@angular/cdk/clipboard';

@Component({
  selector: 'app-mcp-integration',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    ClipboardModule
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
              Your architecture decisions, right where you code
            </p>
            <p class="hero-description">
              Connect Claude Code, Cursor, or any MCP-compatible tool and let your AI assistant access your team's architecture decisions. Ask questions in natural language—no context switching required.
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
              <div class="tool-icon-wrapper claude">
                <img src="/assets/claude-code-icon.svg" alt="Claude Code" class="tool-svg-icon" />
              </div>
              <h3>Claude Code</h3>
              <p>Anthropic's AI coding assistant with native MCP support</p>
            </div>

            <div class="tool-card">
              <div class="tool-icon-wrapper cursor">
                <img src="/assets/cursor-icon.svg" alt="Cursor" class="tool-svg-icon" />
              </div>
              <h3>Cursor</h3>
              <p>AI-first code editor with MCP server configuration</p>
            </div>

            <div class="tool-card">
              <div class="tool-icon-wrapper vscode">
                <img src="/assets/vscode-svgrepo-com.svg" alt="VS Code" class="tool-svg-icon" />
              </div>
              <h3>VS Code</h3>
              <p>Via MCP extension for Visual Studio Code</p>
            </div>

            <div class="tool-card">
              <div class="tool-icon-wrapper other">
                <mat-icon>extension</mat-icon>
              </div>
              <h3>Other MCP Tools</h3>
              <p>Any tool supporting the Model Context Protocol</p>
            </div>
          </div>
        </div>
      </section>

      <!-- What You Can Say Section -->
      <section class="conversation-section">
        <div class="container">
          <h2>Just Ask Your AI Assistant</h2>
          <p class="section-intro">
            Once connected, your AI assistant can search, read, and create decisions using natural language. Here are some things you can say:
          </p>

          <div class="conversation-grid">
            <div class="conversation-card">
              <div class="conversation-icon search">
                <mat-icon>search</mat-icon>
              </div>
              <div class="conversation-content">
                <h3>Search & Discover</h3>
                <ul class="conversation-examples">
                  <li>"Search for decisions about authentication"</li>
                  <li>"Find all accepted decisions about our API"</li>
                  <li>"What decisions have we made about caching?"</li>
                  <li>"Show me recent architecture decisions"</li>
                </ul>
              </div>
            </div>

            <div class="conversation-card">
              <div class="conversation-icon read">
                <mat-icon>description</mat-icon>
              </div>
              <div class="conversation-content">
                <h3>Get Full Context</h3>
                <ul class="conversation-examples">
                  <li>"Get the details of ADR-42"</li>
                  <li>"What was the rationale for using PostgreSQL?"</li>
                  <li>"Show me the consequences of our event-driven decision"</li>
                  <li>"What's the history of changes to ADR-15?"</li>
                </ul>
              </div>
            </div>

            <div class="conversation-card">
              <div class="conversation-icon create">
                <mat-icon>add_circle</mat-icon>
              </div>
              <div class="conversation-content">
                <h3>Create New Decisions</h3>
                <ul class="conversation-examples">
                  <li>"Create a decision about using Redis for session storage"</li>
                  <li>"Document our choice to adopt GraphQL for the new API"</li>
                  <li>"I just decided to use TypeScript—create an ADR for it"</li>
                  <li>"Record our decision to migrate to microservices"</li>
                </ul>
              </div>
            </div>

            <div class="conversation-card">
              <div class="conversation-icon context">
                <mat-icon>psychology</mat-icon>
              </div>
              <div class="conversation-content">
                <h3>Contextual Assistance</h3>
                <ul class="conversation-examples">
                  <li>"Before I implement this, are there any relevant decisions?"</li>
                  <li>"Does this approach conflict with our architecture decisions?"</li>
                  <li>"What patterns have we decided on for error handling?"</li>
                  <li>"List all proposed decisions that need review"</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Features Section - Side by Side Layout -->
      <section class="features-section">
        <div class="container">
          <div class="features-layout">
            <div class="features-content">
              <span class="features-badge">Seamless Integration</span>
              <h2>Your decisions, right in your IDE</h2>
              <p class="features-intro">
                No more switching tabs or digging through docs. Your AI assistant fetches decisions instantly.
              </p>
              <div class="features-list">
                <div class="feature-item">
                  <mat-icon class="feature-check">check_circle</mat-icon>
                  <div class="feature-text">
                    <strong>Search with natural language</strong>
                    <span>"What did we decide about caching?"</span>
                  </div>
                </div>
                <div class="feature-item">
                  <mat-icon class="feature-check">check_circle</mat-icon>
                  <div class="feature-text">
                    <strong>Full context inline</strong>
                    <span>See rationale, consequences, and status</span>
                  </div>
                </div>
                <div class="feature-item">
                  <mat-icon class="feature-check">check_circle</mat-icon>
                  <div class="feature-text">
                    <strong>Create while you code</strong>
                    <span>Capture decisions the moment you make them</span>
                  </div>
                </div>
                <div class="feature-item">
                  <mat-icon class="feature-check">check_circle</mat-icon>
                  <div class="feature-text">
                    <strong>Track decision history</strong>
                    <span>See how decisions evolved over time</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="features-visual">
              <img src="/assets/mcp-ide-mockup.svg" alt="MCP integration in IDE showing AI assistant searching and creating decisions" />
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

      <!-- Setup Section - ngrok inspired -->
      <section class="setup-section">
        <div class="container">
          <!-- Step 1: Generate API Key -->
          <div class="setup-step">
            <div class="step-header">
              <span class="step-badge">1</span>
              <div class="step-title">
                <h2>Generate an API Key</h2>
                <p>Create an API key with the permissions you need</p>
              </div>
            </div>
            <div class="step-body">
              <div class="key-generation-card">
                <div class="key-info">
                  <mat-icon>vpn_key</mat-icon>
                  <div>
                    <h3>API Key Scopes</h3>
                    <p>Select the permissions for your key when creating it in your profile settings</p>
                  </div>
                </div>
                <div class="scope-options">
                  <div class="scope-item">
                    <mat-icon class="scope-icon read">visibility</mat-icon>
                    <div>
                      <strong>Read</strong>
                      <span>View decision details</span>
                    </div>
                  </div>
                  <div class="scope-item">
                    <mat-icon class="scope-icon search">search</mat-icon>
                    <div>
                      <strong>Search</strong>
                      <span>Find decisions by keywords</span>
                    </div>
                  </div>
                  <div class="scope-item">
                    <mat-icon class="scope-icon write">edit</mat-icon>
                    <div>
                      <strong>Write</strong>
                      <span>Create new decisions</span>
                    </div>
                  </div>
                </div>
                <a routerLink="/dashboard" class="generate-key-btn">
                  <mat-icon>add</mat-icon>
                  Generate API Key
                </a>
              </div>
            </div>
          </div>

          <!-- Step 2: Connect -->
          <div class="setup-step">
            <div class="step-header">
              <span class="step-badge">2</span>
              <div class="step-title">
                <h2>Connect</h2>
                <p>Add the MCP server to your development tool</p>
              </div>
            </div>
            <div class="step-body">
              <!-- Tool Tabs -->
              <mat-tab-group class="tool-tabs" animationDuration="200ms">
                <mat-tab>
                  <ng-template mat-tab-label>
                    <div class="tab-label">
                      <mat-icon>terminal</mat-icon>
                      <span>Claude Code</span>
                      <span class="tab-badge">Recommended</span>
                    </div>
                  </ng-template>
                  <div class="tab-content">
                    <p class="tab-description">Run this command in your terminal:</p>
                    <div class="code-block-modern">
                      <pre><code>{{ claudeCodeCommand }}</code></pre>
                      <button class="copy-btn" (click)="copyToClipboard(claudeCodeCommand)">
                        <mat-icon>content_copy</mat-icon>
                      </button>
                    </div>
                    <p class="tab-note">Then verify the connection:</p>
                    <div class="code-block-modern">
                      <pre><code>{{ claudeListCommand }}</code></pre>
                      <button class="copy-btn" (click)="copyToClipboard(claudeListCommand)">
                        <mat-icon>content_copy</mat-icon>
                      </button>
                    </div>
                  </div>
                </mat-tab>
                <mat-tab>
                  <ng-template mat-tab-label>
                    <div class="tab-label">
                      <mat-icon>edit_note</mat-icon>
                      <span>Cursor</span>
                    </div>
                  </ng-template>
                  <div class="tab-content">
                    <p class="tab-description">Add to <code>~/.cursor/mcp.json</code>:</p>
                    <div class="code-block-modern">
                      <pre><code>{{ '{' }}
  "mcpServers": {{ '{' }}
    "decision-records": {{ '{' }}
      "url": "https://decisionrecords.org/api/mcp",
      "headers": {{ '{' }}
        "Authorization": "Bearer YOUR_API_KEY"
      {{ '}' }}
    {{ '}' }}
  {{ '}' }}
{{ '}' }}</code></pre>
                      <button class="copy-btn" (click)="copyToClipboard(cursorConfig)">
                        <mat-icon>content_copy</mat-icon>
                      </button>
                    </div>
                  </div>
                </mat-tab>
                <mat-tab>
                  <ng-template mat-tab-label>
                    <div class="tab-label">
                      <mat-icon>extension</mat-icon>
                      <span>Continue.dev</span>
                    </div>
                  </ng-template>
                  <div class="tab-content">
                    <p class="tab-description">Add to <code>~/.continue/config.json</code>:</p>
                    <div class="code-block-modern">
                      <pre><code>{{ '{' }}
  "mcpServers": [
    {{ '{' }}
      "name": "decision-records",
      "transport": {{ '{' }}
        "type": "http",
        "url": "https://decisionrecords.org/api/mcp",
        "headers": {{ '{' }}
          "Authorization": "Bearer YOUR_API_KEY"
        {{ '}' }}
      {{ '}' }}
    {{ '}' }}
  ]
{{ '}' }}</code></pre>
                      <button class="copy-btn" (click)="copyToClipboard(continueConfig)">
                        <mat-icon>content_copy</mat-icon>
                      </button>
                    </div>
                  </div>
                </mat-tab>
                <mat-tab>
                  <ng-template mat-tab-label>
                    <div class="tab-label">
                      <mat-icon>code</mat-icon>
                      <span>cURL</span>
                    </div>
                  </ng-template>
                  <div class="tab-content">
                    <p class="tab-description">Test the connection:</p>
                    <div class="code-block-modern">
                      <pre><code>curl -X POST https://decisionrecords.org/api/mcp \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{ '{' }}"jsonrpc": "2.0", "id": 1, "method": "tools/list"{{ '}' }}'</code></pre>
                      <button class="copy-btn" (click)="copyToClipboard(curlCommand)">
                        <mat-icon>content_copy</mat-icon>
                      </button>
                    </div>
                  </div>
                </mat-tab>
              </mat-tab-group>
            </div>
          </div>

          <!-- Step 3: Start Using -->
          <div class="setup-step">
            <div class="step-header">
              <span class="step-badge">3</span>
              <div class="step-title">
                <h2>Start Using</h2>
                <p>Ask your AI assistant about your architecture decisions</p>
              </div>
            </div>
            <div class="step-body">
              <div class="ready-card">
                <mat-icon class="ready-icon">check_circle</mat-icon>
                <div class="ready-content">
                  <h3>You're all set!</h3>
                  <p>Try asking your AI assistant:</p>
                  <div class="example-prompts">
                    <span class="prompt">"Search for decisions about authentication"</span>
                    <span class="prompt">"What did we decide about caching?"</span>
                    <span class="prompt">"Create a decision about using Redis"</span>
                  </div>
                </div>
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

    .tool-icon-wrapper {
      width: 64px;
      height: 64px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 16px;
      overflow: hidden;
    }

    .tool-icon-wrapper.claude {
      background: transparent;
    }

    .tool-icon-wrapper.cursor {
      background: #f8fafc;
      padding: 10px;
    }

    .tool-icon-wrapper.vscode {
      background: transparent;
    }

    .tool-icon-wrapper.other {
      background: linear-gradient(135deg, #475569 0%, #64748b 100%);
    }

    .tool-svg-icon {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }

    .tool-icon-wrapper mat-icon {
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

    /* Conversation Section */
    .conversation-section {
      padding: 80px 0;
      background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
    }

    .conversation-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 12px;
    }

    .section-intro {
      font-size: 1.1rem;
      color: #64748b;
      text-align: center;
      max-width: 600px;
      margin: 0 auto 48px;
      line-height: 1.6;
    }

    .conversation-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
    }

    .conversation-card {
      background: white;
      padding: 28px;
      border-radius: 16px;
      border: 1px solid #e9d5ff;
      display: flex;
      gap: 20px;
    }

    .conversation-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .conversation-icon.search {
      background: linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%);
    }

    .conversation-icon.read {
      background: linear-gradient(135deg, #3b82f6 0%, #60a5fa 100%);
    }

    .conversation-icon.create {
      background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
    }

    .conversation-icon.context {
      background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
    }

    .conversation-icon mat-icon {
      color: white;
      font-size: 24px;
      width: 24px;
      height: 24px;
    }

    .conversation-content h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 12px;
    }

    .conversation-examples {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .conversation-examples li {
      font-size: 0.9rem;
      color: #475569;
      padding: 8px 12px;
      background: #f8fafc;
      border-radius: 8px;
      margin-bottom: 8px;
      border-left: 3px solid #8b5cf6;
      font-style: italic;
    }

    .conversation-examples li:last-child {
      margin-bottom: 0;
    }

    /* Features - Side by Side Layout */
    .features-section {
      padding: 80px 0;
      background: #f1f5f9;
    }

    .features-layout {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 64px;
      align-items: center;
    }

    .features-badge {
      display: inline-block;
      padding: 8px 16px;
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
      color: white;
      font-size: 0.8rem;
      font-weight: 600;
      border-radius: 100px;
      margin-bottom: 16px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .features-content h2 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 2rem;
      font-weight: 700;
      color: #0f172a;
      margin: 0 0 16px;
      letter-spacing: -0.02em;
      line-height: 1.2;
    }

    .features-intro {
      font-size: 1.1rem;
      color: #64748b;
      line-height: 1.6;
      margin: 0 0 32px;
    }

    .features-list {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .feature-item {
      display: flex;
      gap: 16px;
      align-items: flex-start;
    }

    .feature-check {
      color: #22c55e;
      font-size: 24px;
      width: 24px;
      height: 24px;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .feature-text {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .feature-text strong {
      font-size: 1rem;
      font-weight: 600;
      color: #0f172a;
    }

    .feature-text span {
      font-size: 0.9rem;
      color: #64748b;
    }

    .features-visual {
      display: flex;
      justify-content: center;
    }

    .features-visual img {
      max-width: 100%;
      height: auto;
      filter: drop-shadow(0 20px 40px rgba(0, 0, 0, 0.15));
      border-radius: 12px;
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

    /* Setup - ngrok inspired */
    .setup-section {
      padding: 80px 0;
      background: #0f172a;
    }

    .setup-step {
      max-width: 800px;
      margin: 0 auto 48px;
    }

    .setup-step:last-child {
      margin-bottom: 0;
    }

    .step-header {
      display: flex;
      align-items: flex-start;
      gap: 20px;
      margin-bottom: 24px;
    }

    .step-badge {
      width: 48px;
      height: 48px;
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
      color: white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 1.25rem;
      flex-shrink: 0;
    }

    .step-title h2 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 1.5rem;
      font-weight: 600;
      color: white;
      margin: 0 0 4px;
    }

    .step-title p {
      font-size: 0.95rem;
      color: #94a3b8;
      margin: 0;
    }

    .step-body {
      margin-left: 68px;
    }

    /* Key Generation Card */
    .key-generation-card {
      background: #1e293b;
      border-radius: 12px;
      padding: 24px;
      border: 1px solid #334155;
    }

    .key-info {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 24px;
    }

    .key-info > mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      color: #60a5fa;
    }

    .key-info h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: white;
      margin: 0 0 4px;
    }

    .key-info p {
      font-size: 0.9rem;
      color: #94a3b8;
      margin: 0;
    }

    .scope-options {
      display: flex;
      gap: 16px;
      margin-bottom: 24px;
    }

    .scope-item {
      flex: 1;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
      background: #0f172a;
      border-radius: 8px;
      border: 1px solid #334155;
    }

    .scope-icon {
      font-size: 24px;
      width: 24px;
      height: 24px;
    }

    .scope-icon.read { color: #60a5fa; }
    .scope-icon.search { color: #a78bfa; }
    .scope-icon.write { color: #34d399; }

    .scope-item strong {
      display: block;
      font-size: 0.9rem;
      font-weight: 600;
      color: white;
      margin-bottom: 2px;
    }

    .scope-item span {
      font-size: 0.8rem;
      color: #94a3b8;
    }

    .generate-key-btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 12px 24px;
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
      color: white;
      font-weight: 600;
      border-radius: 8px;
      text-decoration: none;
      transition: all 0.2s;
    }

    .generate-key-btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }

    /* Tool Tabs */
    .tool-tabs {
      background: #1e293b;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid #334155;
    }

    .tool-tabs ::ng-deep .mat-mdc-tab-header {
      background: #0f172a;
      border-bottom: 1px solid #334155;
    }

    .tool-tabs ::ng-deep .mat-mdc-tab {
      min-width: 140px;
    }

    .tool-tabs ::ng-deep .mat-mdc-tab:not(.mat-mdc-tab-disabled) .mdc-tab__text-label {
      color: #94a3b8;
    }

    .tool-tabs ::ng-deep .mat-mdc-tab.mat-mdc-tab-active .mdc-tab__text-label {
      color: white;
    }

    .tool-tabs ::ng-deep .mdc-tab-indicator__content--underline {
      border-color: #3b82f6;
    }

    .tab-label {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .tab-label mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .tab-badge {
      font-size: 0.65rem;
      font-weight: 600;
      padding: 2px 8px;
      background: #22c55e;
      color: white;
      border-radius: 100px;
      text-transform: uppercase;
    }

    .tab-content {
      padding: 24px;
    }

    .tab-description {
      font-size: 0.95rem;
      color: #94a3b8;
      margin: 0 0 16px;
    }

    .tab-description code {
      background: #0f172a;
      padding: 2px 8px;
      border-radius: 4px;
      color: #60a5fa;
      font-family: 'Fira Code', monospace;
    }

    .tab-note {
      font-size: 0.9rem;
      color: #64748b;
      margin: 16px 0 12px;
    }

    .code-block-modern {
      position: relative;
      background: #0f172a;
      border-radius: 8px;
      border: 1px solid #334155;
      overflow: hidden;
    }

    .code-block-modern pre {
      margin: 0;
      padding: 16px;
      padding-right: 56px;
      overflow-x: auto;
    }

    .code-block-modern code {
      font-family: 'Fira Code', 'Consolas', monospace;
      font-size: 0.85rem;
      color: #e2e8f0;
      line-height: 1.6;
    }

    .copy-btn {
      position: absolute;
      top: 8px;
      right: 8px;
      width: 36px;
      height: 36px;
      background: #334155;
      border: none;
      border-radius: 6px;
      color: #94a3b8;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
    }

    .copy-btn:hover {
      background: #475569;
      color: white;
    }

    .copy-btn mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    /* Ready Card */
    .ready-card {
      display: flex;
      align-items: flex-start;
      gap: 20px;
      padding: 24px;
      background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%);
      border: 1px solid rgba(34, 197, 94, 0.3);
      border-radius: 12px;
    }

    .ready-icon {
      font-size: 40px;
      width: 40px;
      height: 40px;
      color: #22c55e;
    }

    .ready-content h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: white;
      margin: 0 0 8px;
    }

    .ready-content > p {
      font-size: 0.95rem;
      color: #94a3b8;
      margin: 0 0 16px;
    }

    .example-prompts {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .prompt {
      padding: 8px 14px;
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 100px;
      font-size: 0.85rem;
      color: #e2e8f0;
      font-style: italic;
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
      .conversation-section,
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

      .conversation-grid {
        grid-template-columns: 1fr;
      }

      .conversation-card {
        flex-direction: column;
      }

      .features-layout {
        grid-template-columns: 1fr;
        gap: 48px;
      }

      .features-visual {
        order: -1;
      }

      .features-visual img {
        max-width: 400px;
      }

      .features-content h2 {
        font-size: 1.75rem;
      }

      .step-body {
        margin-left: 0;
        margin-top: 16px;
      }

      .scope-options {
        flex-direction: column;
      }

      .tab-label span:not(.tab-badge) {
        display: none;
      }

      .ready-card {
        flex-direction: column;
        text-align: center;
      }

      .example-prompts {
        justify-content: center;
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
export class McpIntegrationComponent {
  constructor(private clipboard: Clipboard) {}

  // Config templates for copy functionality
  claudeCodeCommand = 'claude mcp add decision-records https://decisionrecords.org/api/mcp -t http -H "Authorization: Bearer YOUR_API_KEY"';
  claudeListCommand = 'claude mcp list';

  cursorConfig = `{
  "mcpServers": {
    "decision-records": {
      "url": "https://decisionrecords.org/api/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}`;

  continueConfig = `{
  "mcpServers": [
    {
      "name": "decision-records",
      "transport": {
        "type": "http",
        "url": "https://decisionrecords.org/api/mcp",
        "headers": {
          "Authorization": "Bearer YOUR_API_KEY"
        }
      }
    }
  ]
}`;

  curlCommand = `curl -X POST https://decisionrecords.org/api/mcp \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'`;

  copyToClipboard(text: string): void {
    this.clipboard.copy(text);
  }
}
