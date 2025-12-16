import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { AuthService } from '../../services/auth.service';

interface LinkTokenData {
  valid: boolean;
  workspace_name: string;
  workspace_id: string;
  slack_user_id: string;
  slack_email: string | null;
  is_logged_in: boolean;
  user_email?: string;
  user_name?: string;
  tenant_domain?: string;
  error?: string;
}

@Component({
  selector: 'app-slack-link-account',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule
  ],
  template: `
    <div class="link-container">
      <mat-card class="link-card">
        @if (loading) {
          <div class="loading-state">
            <mat-spinner diameter="40"></mat-spinner>
            <p>Verifying your link...</p>
          </div>
        } @else if (error) {
          <div class="error-state">
            <mat-icon class="error-icon">error_outline</mat-icon>
            <h2>{{ errorTitle }}</h2>
            <p>{{ error }}</p>
            <button mat-flat-button color="primary" routerLink="/">
              Go to Homepage
            </button>
          </div>
        } @else if (linkComplete) {
          <div class="success-state">
            <mat-icon class="success-icon">check_circle</mat-icon>
            <h2>Account Linked!</h2>
            <p>Your Slack account has been successfully linked to your Decision Records account.</p>
            <p class="hint">You can now use /adr commands in Slack to create and view decisions.</p>
            <div class="next-steps">
              <h4>Try these commands in Slack:</h4>
              <ul>
                <li><code>/adr create</code> - Create a new decision</li>
                <li><code>/adr list</code> - List recent decisions</li>
                <li><code>/adr search [query]</code> - Search decisions</li>
                <li><code>/adr help</code> - See all commands</li>
              </ul>
            </div>
            <button mat-flat-button color="primary" (click)="closeWindow()">
              Close this window
            </button>
          </div>
        } @else if (tokenData) {
          <mat-card-header>
            <mat-card-title>
              <mat-icon>link</mat-icon>
              Link Your Slack Account
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <div class="workspace-info">
              <mat-icon>chat</mat-icon>
              <div>
                <p class="workspace-name">{{ tokenData.workspace_name }}</p>
                <p class="workspace-detail">Slack Workspace</p>
              </div>
            </div>

            @if (tokenData.is_logged_in) {
              <!-- User is already logged in -->
              <div class="logged-in-flow">
                <div class="user-info">
                  <mat-icon>person</mat-icon>
                  <div>
                    <p class="user-name">{{ tokenData.user_name }}</p>
                    <p class="user-email">{{ tokenData.user_email }}</p>
                  </div>
                </div>

                <p class="instruction">
                  Click below to link your Slack account to your Decision Records account.
                  This will allow you to use /adr commands in Slack.
                </p>

                @if (tokenData.slack_email && tokenData.slack_email !== tokenData.user_email) {
                  <div class="email-mismatch-notice">
                    <mat-icon>info</mat-icon>
                    <p>
                      Your Slack email ({{ tokenData.slack_email }}) is different from your
                      Decision Records email ({{ tokenData.user_email }}). This is fine - we'll
                      link based on your login, not email.
                    </p>
                  </div>
                }

                <button mat-flat-button color="primary" (click)="completeLink()" [disabled]="linking">
                  @if (linking) {
                    <mat-spinner diameter="20"></mat-spinner>
                    Linking...
                  } @else {
                    Link Account
                  }
                </button>

                <p class="switch-account">
                  Not you? <a (click)="switchAccount()">Sign in with a different account</a>
                </p>
              </div>
            } @else {
              <!-- User needs to log in -->
              <div class="login-flow">
                <p class="instruction">
                  To link your Slack account, please sign in to Decision Records first.
                </p>

                @if (tokenData.slack_email) {
                  <div class="email-hint">
                    <mat-icon>mail</mat-icon>
                    <p>Your Slack email: <strong>{{ tokenData.slack_email }}</strong></p>
                  </div>
                }

                <!-- Slack Sign-in Option -->
                @if (slackOidcEnabled) {
                  <button mat-flat-button class="slack-signin-btn" (click)="signInWithSlack()">
                    <img src="/assets/slack-logo.svg" alt="Slack" class="slack-logo">
                    <span>Sign in with Slack</span>
                  </button>
                  <div class="social-divider">
                    <span>or</span>
                  </div>
                }

                <div class="action-buttons">
                  <button mat-flat-button color="primary" (click)="goToLogin()">
                    Sign In
                  </button>
                  <button mat-stroked-button color="primary" (click)="goToSignup()">
                    Create Account
                  </button>
                </div>

                <p class="help-text">
                  Don't have a Decision Records account? You'll need to either:
                </p>
                <ul class="help-list">
                  <li>Sign up and create a new organization</li>
                  <li>Ask your organization admin to invite you</li>
                </ul>
              </div>
            }
          </mat-card-content>
        }
      </mat-card>
    </div>
  `,
  styles: [`
    .link-container {
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 24px;
      background: linear-gradient(135deg, #4a154b 0%, #611f69 100%);
    }

    .link-card {
      max-width: 480px;
      width: 100%;
      padding: 32px;
    }

    mat-card-header {
      margin-bottom: 24px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 22px;
    }

    mat-card-title mat-icon {
      color: #4a154b;
    }

    .loading-state,
    .error-state,
    .success-state {
      text-align: center;
      padding: 24px;
    }

    .loading-state p {
      margin-top: 16px;
      color: #666;
    }

    .error-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #f44336;
    }

    .success-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #4caf50;
    }

    .error-state h2,
    .success-state h2 {
      margin: 16px 0 8px;
      color: #333;
    }

    .error-state p,
    .success-state p {
      color: #666;
      margin-bottom: 24px;
    }

    .success-state .hint {
      color: #4caf50;
      font-weight: 500;
    }

    .next-steps {
      text-align: left;
      background: #f5f5f5;
      padding: 16px;
      border-radius: 8px;
      margin: 24px 0;
    }

    .next-steps h4 {
      margin: 0 0 12px;
      font-size: 14px;
      color: #333;
    }

    .next-steps ul {
      margin: 0;
      padding-left: 20px;
    }

    .next-steps li {
      margin: 8px 0;
      color: #666;
    }

    .next-steps code {
      background: #e0e0e0;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 13px;
    }

    .workspace-info {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
      background: #4a154b;
      border-radius: 8px;
      margin-bottom: 24px;
      color: white;
    }

    .workspace-info mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
    }

    .workspace-name {
      margin: 0;
      font-size: 18px;
      font-weight: 500;
    }

    .workspace-detail {
      margin: 4px 0 0;
      opacity: 0.8;
      font-size: 14px;
    }

    .user-info {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
      background: #e8f5e9;
      border-radius: 8px;
      margin-bottom: 16px;
    }

    .user-info mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      color: #4caf50;
    }

    .user-name {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
    }

    .user-email {
      margin: 4px 0 0;
      color: #666;
      font-size: 14px;
    }

    .instruction {
      color: #666;
      margin-bottom: 20px;
      line-height: 1.5;
    }

    .email-mismatch-notice {
      display: flex;
      gap: 12px;
      padding: 12px;
      background: #fff3e0;
      border-radius: 8px;
      margin-bottom: 20px;
    }

    .email-mismatch-notice mat-icon {
      color: #ff9800;
      flex-shrink: 0;
    }

    .email-mismatch-notice p {
      margin: 0;
      font-size: 13px;
      color: #666;
    }

    .logged-in-flow button,
    .login-flow button {
      width: 100%;
      padding: 12px;
      font-size: 16px;
    }

    .switch-account {
      margin-top: 16px;
      font-size: 14px;
      color: #666;
      text-align: center;
    }

    .switch-account a {
      color: #3f51b5;
      cursor: pointer;
      text-decoration: underline;
    }

    .email-hint {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px;
      background: #e3f2fd;
      border-radius: 8px;
      margin-bottom: 20px;
    }

    .email-hint mat-icon {
      color: #1976d2;
    }

    .email-hint p {
      margin: 0;
      font-size: 14px;
      color: #333;
    }

    /* Slack Sign-in Button Styles */
    .slack-signin-btn {
      display: flex !important;
      width: 100%;
      align-items: center;
      justify-content: center;
      gap: 12px;
      padding: 14px 24px !important;
      border: none !important;
      border-radius: 8px !important;
      background: #4a154b !important;
      color: white !important;
      font-weight: 500 !important;
      font-size: 15px !important;
      transition: all 0.2s ease !important;
      height: auto !important;
      min-height: 48px;
      margin-bottom: 16px;
    }

    .slack-signin-btn:hover {
      background: #611f69 !important;
      box-shadow: 0 4px 12px rgba(74, 21, 75, 0.3);
    }

    .slack-signin-btn .slack-logo {
      width: 22px;
      height: 22px;
    }

    .social-divider {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 16px;
      color: #94a3b8;
      font-size: 13px;
      text-transform: lowercase;
    }

    .social-divider::before,
    .social-divider::after {
      content: '';
      flex: 1;
      height: 1px;
      background: #e2e8f0;
    }

    .action-buttons {
      display: flex;
      gap: 12px;
      margin-bottom: 24px;
    }

    .action-buttons button {
      flex: 1;
      padding: 12px;
    }

    .help-text {
      color: #666;
      font-size: 14px;
      margin-bottom: 8px;
    }

    .help-list {
      margin: 0;
      padding-left: 20px;
      color: #666;
      font-size: 14px;
    }

    .help-list li {
      margin: 4px 0;
    }
  `]
})
export class SlackLinkAccountComponent implements OnInit {
  loading = true;
  error: string | null = null;
  errorTitle = 'Link Error';
  tokenData: LinkTokenData | null = null;
  token: string | null = null;
  linking = false;
  linkComplete = false;
  slackOidcEnabled = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient,
    private authService: AuthService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token');
    if (!this.token) {
      this.error = 'No link token provided. Please click the "Link Account" button in Slack again.';
      this.errorTitle = 'Missing Token';
      this.loading = false;
      return;
    }

    // Check if Slack OIDC is enabled
    this.checkSlackOidcStatus();

    this.validateToken();
  }

  private checkSlackOidcStatus(): void {
    this.http.get<{ enabled: boolean }>('/api/auth/slack-oidc-status').subscribe({
      next: (response) => {
        this.slackOidcEnabled = response.enabled;
      },
      error: () => {
        this.slackOidcEnabled = false;
      }
    });
  }

  signInWithSlack(): void {
    // Store the token in session storage to restore after login
    if (this.token) {
      sessionStorage.setItem('slack_link_token', this.token);
    }
    // Redirect to Slack OIDC with return URL to this page
    const returnUrl = `/slack/link?token=${this.token}`;
    window.location.href = `/auth/slack/oidc?return_url=${encodeURIComponent(returnUrl)}`;
  }

  validateToken(): void {
    this.http.post<LinkTokenData>('/api/slack/link/validate', { token: this.token }).subscribe({
      next: (data) => {
        if (data.valid) {
          this.tokenData = data;
        } else {
          this.error = data.error || 'Invalid or expired link token. Please click the "Link Account" button in Slack again.';
          this.errorTitle = 'Invalid Link';
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = err.error?.error || 'Failed to validate link token. Please try again.';
        this.errorTitle = 'Validation Error';
        this.loading = false;
      }
    });
  }

  completeLink(): void {
    if (!this.token || this.linking) return;

    this.linking = true;

    this.http.post<any>('/api/slack/link/complete', { token: this.token }).subscribe({
      next: (response) => {
        this.linkComplete = true;
        this.linking = false;
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to link account', 'Close', { duration: 5000 });
        this.linking = false;
      }
    });
  }

  goToLogin(): void {
    // Store the token in session storage to restore after login
    if (this.token) {
      sessionStorage.setItem('slack_link_token', this.token);
    }
    // Redirect to homepage with login hint
    this.router.navigate(['/'], { queryParams: { slack_link: 'true' } });
  }

  goToSignup(): void {
    // Store the token in session storage to restore after signup
    if (this.token) {
      sessionStorage.setItem('slack_link_token', this.token);
    }
    // Redirect to homepage with signup hint
    this.router.navigate(['/'], { queryParams: { slack_link: 'true', signup: 'true' } });
  }

  switchAccount(): void {
    // Clear current session and redirect to login
    this.authService.logout().subscribe({
      next: () => {
        if (this.token) {
          sessionStorage.setItem('slack_link_token', this.token);
        }
        this.router.navigate(['/'], { queryParams: { slack_link: 'true' } });
      },
      error: () => {
        // Even if logout fails, try to redirect
        if (this.token) {
          sessionStorage.setItem('slack_link_token', this.token);
        }
        this.router.navigate(['/'], { queryParams: { slack_link: 'true' } });
      }
    });
  }

  closeWindow(): void {
    // Try to close the window (works if opened by Slack)
    window.close();
    // If window didn't close, show a message
    setTimeout(() => {
      this.snackBar.open('You can close this tab and return to Slack', 'OK', { duration: 5000 });
    }, 500);
  }
}
