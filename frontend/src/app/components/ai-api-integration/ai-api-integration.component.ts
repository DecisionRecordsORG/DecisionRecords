import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { Clipboard, ClipboardModule } from '@angular/cdk/clipboard';

@Component({
  selector: 'app-ai-api-integration',
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
            <h1>AI API & Custom GPTs</h1>
            <p class="hero-tagline">
              Give your AI assistants the context they need
            </p>
            <p class="hero-description">
              Build Custom GPTs, AI agents, and automations that understand your team's decisions. Your AI can search, read, and even create decision records—all through a simple REST API.
            </p>
          </div>
        </div>
      </header>

      <!-- Supported Platforms Section -->
      <section class="platforms-section">
        <div class="container">
          <h2>Build For Any AI Platform</h2>

          <div class="platforms-grid">
            <div class="platform-card">
              <div class="platform-icon-wrapper openai">
                <img src="/assets/openai-svgrepo-com.svg" alt="OpenAI" class="platform-svg-icon" />
              </div>
              <h3>Custom GPTs</h3>
              <p>Create ChatGPT assistants with decision knowledge</p>
            </div>

            <div class="platform-card">
              <div class="platform-icon-wrapper claude">
                <img src="/assets/claude-code-icon.svg" alt="Claude" class="platform-svg-icon" />
              </div>
              <h3>Claude</h3>
              <p>Power Anthropic Claude with your decisions</p>
            </div>

            <div class="platform-card">
              <div class="platform-icon-wrapper langchain">
                <mat-icon>link</mat-icon>
              </div>
              <h3>LangChain</h3>
              <p>Integrate with LangChain agents and tools</p>
            </div>

            <div class="platform-card">
              <div class="platform-icon-wrapper other">
                <mat-icon>api</mat-icon>
              </div>
              <h3>Any REST Client</h3>
              <p>Standard REST API for any integration</p>
            </div>
          </div>
        </div>
      </section>

      <!-- What Your AI Can Do Section -->
      <section class="ai-examples-section">
        <div class="container">
          <h2>Imagine Asking Your Custom GPT...</h2>
          <p class="section-intro">
            With Decision Records connected, your Custom GPT or AI agent can answer questions about your team's decisions:
          </p>

          <div class="ai-conversation">
            <div class="ai-message user">
              <div class="message-avatar">You</div>
              <div class="message-content">"What authentication approach did we decide on for our API?"</div>
            </div>
            <div class="ai-message assistant">
              <div class="message-avatar">AI</div>
              <div class="message-content">
                Based on ADR-42 "Use OAuth2 for API Authentication" (accepted on Dec 15, 2024), your team decided to use OAuth2 with JWT tokens. The key reasons were:
                <ul>
                  <li>Industry standard with broad library support</li>
                  <li>Supports both user and service-to-service auth</li>
                  <li>Stateless verification reduces database load</li>
                </ul>
              </div>
            </div>
            <div class="ai-message user">
              <div class="message-avatar">You</div>
              <div class="message-content">"Are there any decisions about caching that I should know about before implementing Redis?"</div>
            </div>
            <div class="ai-message assistant">
              <div class="message-avatar">AI</div>
              <div class="message-content">
                Yes! I found 2 relevant decisions:<br><br>
                <strong>ADR-38: Use Redis for Session Storage</strong> (accepted) - This aligns with your plan.<br>
                <strong>ADR-51: Cache Invalidation Strategy</strong> (proposed) - Still under review. You may want to wait or provide input.
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
              <span class="features-badge">REST API</span>
              <h2>Power your AI with decision context</h2>
              <p class="features-intro">
                Simple REST endpoints that any AI platform can call. Your Custom GPT becomes a decision expert.
              </p>
              <div class="features-list">
                <div class="feature-item">
                  <mat-icon class="feature-check">check_circle</mat-icon>
                  <div class="feature-text">
                    <strong>OpenAPI 3.1 schema</strong>
                    <span>Drop-in configuration for Custom GPTs</span>
                  </div>
                </div>
                <div class="feature-item">
                  <mat-icon class="feature-check">check_circle</mat-icon>
                  <div class="feature-text">
                    <strong>Semantic search</strong>
                    <span>Find relevant decisions by meaning, not just keywords</span>
                  </div>
                </div>
                <div class="feature-item">
                  <mat-icon class="feature-check">check_circle</mat-icon>
                  <div class="feature-text">
                    <strong>Create decisions</strong>
                    <span>Let your AI capture decisions on the fly</span>
                  </div>
                </div>
                <div class="feature-item">
                  <mat-icon class="feature-check">check_circle</mat-icon>
                  <div class="feature-text">
                    <strong>Full decision history</strong>
                    <span>Trace how decisions evolved over time</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="features-visual">
              <img src="/assets/ai-api-mockup.svg" alt="Custom GPT using Decision Records API to answer questions" />
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
                    <p>Select permissions when creating your key</p>
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
                      <span>Find decisions</span>
                    </div>
                  </div>
                  <div class="scope-item">
                    <mat-icon class="scope-icon write">edit</mat-icon>
                    <div>
                      <strong>Write</strong>
                      <span>Create decisions</span>
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

          <!-- Step 2: Configure -->
          <div class="setup-step">
            <div class="step-header">
              <span class="step-badge">2</span>
              <div class="step-title">
                <h2>Configure Your AI</h2>
                <p>Set up your AI platform to use the Decision Records API</p>
              </div>
            </div>
            <div class="step-body">
              <!-- Platform Tabs -->
              <mat-tab-group class="platform-tabs" animationDuration="200ms">
                <mat-tab>
                  <ng-template mat-tab-label>
                    <div class="tab-label">
                      <img src="/assets/openai-svgrepo-com.svg" alt="OpenAI" class="tab-icon-svg" />
                      <span>Custom GPT</span>
                      <span class="tab-badge">Recommended</span>
                    </div>
                  </ng-template>
                  <div class="tab-content">
                    <p class="tab-description">In your GPT configuration, add an action with this schema URL:</p>
                    <div class="code-block-modern">
                      <pre><code>{{ openapiUrl }}</code></pre>
                      <button class="copy-btn" (click)="copyToClipboard(openapiUrl)">
                        <mat-icon>content_copy</mat-icon>
                      </button>
                    </div>
                    <p class="tab-note">Then set authentication to "API Key" with type "Bearer" and paste your key.</p>
                  </div>
                </mat-tab>
                <mat-tab>
                  <ng-template mat-tab-label>
                    <div class="tab-label">
                      <mat-icon>link</mat-icon>
                      <span>LangChain</span>
                    </div>
                  </ng-template>
                  <div class="tab-content">
                    <p class="tab-description">Create a custom tool in your LangChain agent:</p>
                    <div class="code-block-modern">
                      <pre><code>{{ langchainCode }}</code></pre>
                      <button class="copy-btn" (click)="copyToClipboard(langchainCode)">
                        <mat-icon>content_copy</mat-icon>
                      </button>
                    </div>
                  </div>
                </mat-tab>
                <mat-tab>
                  <ng-template mat-tab-label>
                    <div class="tab-label">
                      <mat-icon>code</mat-icon>
                      <span>Python</span>
                    </div>
                  </ng-template>
                  <div class="tab-content">
                    <p class="tab-description">Call the API directly from Python:</p>
                    <div class="code-block-modern">
                      <pre><code>{{ pythonCode }}</code></pre>
                      <button class="copy-btn" (click)="copyToClipboard(pythonCode)">
                        <mat-icon>content_copy</mat-icon>
                      </button>
                    </div>
                  </div>
                </mat-tab>
                <mat-tab>
                  <ng-template mat-tab-label>
                    <div class="tab-label">
                      <mat-icon>terminal</mat-icon>
                      <span>cURL</span>
                    </div>
                  </ng-template>
                  <div class="tab-content">
                    <p class="tab-description">Test the API from your terminal:</p>
                    <div class="code-block-modern">
                      <pre><code>{{ curlCommand }}</code></pre>
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
                <h2>Start Asking Questions</h2>
                <p>Your AI now has access to your team's decisions</p>
              </div>
            </div>
            <div class="step-body">
              <div class="ready-card">
                <mat-icon class="ready-icon">check_circle</mat-icon>
                <div class="ready-content">
                  <h3>You're all set!</h3>
                  <p>Try asking your AI:</p>
                  <div class="example-prompts">
                    <span class="prompt">"What did we decide about authentication?"</span>
                    <span class="prompt">"Find decisions about our API design"</span>
                    <span class="prompt">"Create a decision about using GraphQL"</span>
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

    /* Platforms Section */
    .platforms-section {
      padding: 80px 0;
    }

    .platforms-section h2 {
      font-size: 1.75rem;
      font-weight: 600;
      color: #0f172a;
      text-align: center;
      margin: 0 0 48px;
    }

    .platforms-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 24px;
    }

    .platform-card {
      background: white;
      padding: 28px 20px;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
      text-align: center;
    }

    .platform-icon-wrapper {
      width: 64px;
      height: 64px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 16px;
      overflow: hidden;
    }

    .platform-icon-wrapper.openai {
      background: transparent;
    }

    .platform-icon-wrapper.openai .platform-svg-icon {
      width: 48px;
      height: 48px;
    }

    .platform-icon-wrapper.claude {
      background: transparent;
    }

    .platform-icon-wrapper.langchain {
      background: linear-gradient(135deg, #1a5f2c 0%, #2e7d32 100%);
    }

    .platform-icon-wrapper.other {
      background: linear-gradient(135deg, #475569 0%, #64748b 100%);
    }

    .platform-svg-icon {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }

    .platform-icon-wrapper mat-icon {
      color: white;
      font-size: 28px;
      width: 28px;
      height: 28px;
    }

    .platform-card h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
    }

    .platform-card p {
      font-size: 0.9rem;
      color: #64748b;
      line-height: 1.5;
      margin: 0;
    }

    /* AI Examples Section */
    .ai-examples-section {
      padding: 80px 0;
      background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    }

    .ai-examples-section h2 {
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

    .ai-conversation {
      max-width: 700px;
      margin: 0 auto;
      background: white;
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
    }

    .ai-message {
      display: flex;
      gap: 16px;
      margin-bottom: 24px;
    }

    .ai-message:last-child {
      margin-bottom: 0;
    }

    .message-avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.75rem;
      font-weight: 600;
      flex-shrink: 0;
    }

    .ai-message.user .message-avatar {
      background: #e0e7ff;
      color: #4338ca;
    }

    .ai-message.assistant .message-avatar {
      background: linear-gradient(135deg, #059669 0%, #10b981 100%);
      color: white;
    }

    .message-content {
      flex: 1;
      padding: 16px 20px;
      border-radius: 12px;
      font-size: 0.95rem;
      line-height: 1.6;
    }

    .ai-message.user .message-content {
      background: #f1f5f9;
      color: #334155;
      font-style: italic;
    }

    .ai-message.assistant .message-content {
      background: #f0fdf4;
      color: #166534;
      border: 1px solid #bbf7d0;
    }

    .ai-message.assistant .message-content ul {
      margin: 12px 0 0 0;
      padding-left: 20px;
    }

    .ai-message.assistant .message-content li {
      margin-bottom: 4px;
    }

    /* Features - Side by Side Layout */
    .features-section {
      padding: 80px 0;
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
      background: linear-gradient(135deg, #059669 0%, #10b981 100%);
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
      background: linear-gradient(135deg, #059669 0%, #10b981 100%);
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
      color: #34d399;
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
      background: linear-gradient(135deg, #059669 0%, #10b981 100%);
      color: white;
      font-weight: 600;
      border-radius: 8px;
      text-decoration: none;
      transition: all 0.2s;
    }

    .generate-key-btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }

    /* Platform Tabs */
    .platform-tabs {
      background: #1e293b;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid #334155;
    }

    .platform-tabs ::ng-deep .mat-mdc-tab-header {
      background: #0f172a;
      border-bottom: 1px solid #334155;
    }

    .platform-tabs ::ng-deep .mat-mdc-tab {
      min-width: 140px;
    }

    .platform-tabs ::ng-deep .mat-mdc-tab:not(.mat-mdc-tab-disabled) .mdc-tab__text-label {
      color: #94a3b8;
    }

    .platform-tabs ::ng-deep .mat-mdc-tab.mat-mdc-tab-active .mdc-tab__text-label {
      color: white;
    }

    .platform-tabs ::ng-deep .mdc-tab-indicator__content--underline {
      border-color: #10b981;
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

    .tab-icon-svg {
      width: 20px;
      height: 20px;
      object-fit: contain;
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
      color: #34d399;
      font-family: 'Fira Code', monospace;
    }

    .tab-note {
      font-size: 0.9rem;
      color: #64748b;
      margin: 16px 0 0;
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

      .platforms-section,
      .ai-examples-section,
      .features-section,
      .endpoints-section,
      .setup-section,
      .security-section,
      .cta-section {
        padding: 60px 0;
      }

      .platforms-grid {
        grid-template-columns: repeat(2, 1fr);
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

      .ai-conversation {
        padding: 20px;
      }

      .ai-message {
        flex-direction: column;
        gap: 8px;
      }

      .message-avatar {
        width: 32px;
        height: 32px;
        font-size: 0.65rem;
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

      .cta-buttons {
        flex-direction: column;
        align-items: center;
      }
    }

    @media (max-width: 480px) {
      .platforms-grid {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class AiApiIntegrationComponent {
  constructor(private clipboard: Clipboard) {}

  // Config templates for copy functionality
  openapiUrl = 'https://decisionrecords.org/api/ai/openapi.json';

  langchainCode = `from langchain.tools import tool
import requests

@tool
def search_decisions(query: str) -> str:
    """Search decisions by keyword."""
    response = requests.post(
        "https://decisionrecords.org/api/ai/search",
        headers={"Authorization": "Bearer YOUR_API_KEY"},
        json={"query": query}
    )
    return response.json()`;

  pythonCode = `import requests

API_KEY = "adr_your_key"
BASE_URL = "https://decisionrecords.org/api/ai"

# Search for decisions
response = requests.post(
    f"{BASE_URL}/search",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={"query": "authentication"}
)
decisions = response.json()["decisions"]`;

  curlCommand = `curl -X POST https://decisionrecords.org/api/ai/search \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "authentication"}'`;

  copyToClipboard(text: string): void {
    this.clipboard.copy(text);
  }
}
