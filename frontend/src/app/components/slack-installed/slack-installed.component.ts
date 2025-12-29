import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

interface WorkspaceInfo {
  workspace_id: string;
  workspace_name: string;
  is_claimed: boolean;
  status: string;
  installed_at: string | null;
}

@Component({
  selector: 'app-slack-installed',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule
  ],
  template: `
    <div class="slack-installed-container">
      <mat-card class="slack-installed-card">
        @if (loading) {
          <div class="loading">
            <mat-spinner diameter="40"></mat-spinner>
            <p>Loading workspace information...</p>
          </div>
        } @else if (error) {
          <mat-card-header>
            <mat-card-title>
              <mat-icon>error_outline</mat-icon>
              Error
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <p>{{ error }}</p>
          </mat-card-content>
          <mat-card-actions>
            <a mat-flat-button color="primary" routerLink="/">Go to Homepage</a>
          </mat-card-actions>
        } @else if (alreadyClaimed) {
          <mat-card-header>
            <mat-card-title>
              <mat-icon>check_circle</mat-icon>
              Already Connected
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <p>This Slack workspace <strong>{{ workspaceInfo?.workspace_name }}</strong> is already connected to a Decision Records organization.</p>
            <p>If you're an admin of that organization, you can manage the connection from your Settings page.</p>
          </mat-card-content>
          <mat-card-actions>
            <a mat-flat-button color="primary" routerLink="/">Go to Homepage</a>
          </mat-card-actions>
        } @else {
          <mat-card-header>
            <mat-card-title>
              <mat-icon>check_circle</mat-icon>
              Decision Records App Installed!
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <p>The Decision Records app has been successfully installed to <strong>{{ workspaceInfo?.workspace_name }}</strong>.</p>

            <div class="next-steps">
              <h3>Next Steps</h3>
              <p>To complete setup, a Decision Records admin needs to connect this workspace to your organization's account.</p>

              <div class="option-box">
                <h4>Already have an account?</h4>
                <p>Sign in to Decision Records, go to Settings, select the Slack tab, and click "Claim Existing Installation" with the Workspace ID below.</p>
                <a mat-flat-button color="primary" routerLink="/">Go to Decision Records</a>
              </div>

              <div class="option-box">
                <h4>Don't have an account?</h4>
                <p>Sign up for Decision Records to start documenting your team's architecture decisions.</p>
                <a mat-stroked-button color="primary" routerLink="/">Sign Up for Free</a>
              </div>
            </div>

            <div class="workspace-info">
              <mat-icon>info</mat-icon>
              <div>
                <p><strong>Workspace ID:</strong> <code>{{ workspaceInfo?.workspace_id }}</code></p>
                <p class="hint">Share this with your Decision Records admin if needed.</p>
              </div>
            </div>
          </mat-card-content>
        }
      </mat-card>
    </div>
  `,
  styles: [`
    .slack-installed-container {
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 24px;
      background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }

    .slack-installed-card {
      max-width: 600px;
      width: 100%;
    }

    mat-card-header {
      margin-bottom: 16px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 24px;
    }

    mat-card-title mat-icon {
      color: #4caf50;
      font-size: 32px;
      width: 32px;
      height: 32px;
    }

    mat-card-content p {
      margin: 12px 0;
      line-height: 1.6;
    }

    .loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      padding: 48px;
    }

    .next-steps {
      margin-top: 24px;
    }

    .next-steps h3 {
      margin: 0 0 16px 0;
      font-size: 18px;
      font-weight: 500;
    }

    .option-box {
      padding: 16px;
      margin: 16px 0;
      background: #f5f5f5;
      border-radius: 8px;
    }

    .option-box h4 {
      margin: 0 0 8px 0;
      font-size: 16px;
      font-weight: 500;
    }

    .option-box p {
      margin: 0 0 12px 0;
      color: #666;
    }

    .workspace-info {
      display: flex;
      gap: 12px;
      margin-top: 24px;
      padding: 16px;
      background: #e3f2fd;
      border-radius: 8px;
    }

    .workspace-info mat-icon {
      color: #1976d2;
      margin-top: 2px;
    }

    .workspace-info code {
      background: #bbdefb;
      padding: 4px 8px;
      border-radius: 4px;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 14px;
    }

    .workspace-info .hint {
      font-size: 13px;
      color: #666;
      margin-top: 4px;
    }

    mat-card-actions {
      padding: 16px !important;
      display: flex;
      gap: 12px;
    }
  `]
})
export class SlackInstalledComponent implements OnInit {
  loading = true;
  error: string | null = null;
  workspaceInfo: WorkspaceInfo | null = null;
  alreadyClaimed = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    const workspaceId = this.route.snapshot.queryParamMap.get('workspace');
    this.alreadyClaimed = this.route.snapshot.queryParamMap.get('already_claimed') === 'true';

    if (!workspaceId) {
      this.error = 'No workspace ID provided';
      this.loading = false;
      return;
    }

    this.loadWorkspaceInfo(workspaceId);
  }

  private loadWorkspaceInfo(workspaceId: string): void {
    this.http.get<WorkspaceInfo>(`/api/slack/workspace/${workspaceId}`).subscribe({
      next: (info) => {
        this.workspaceInfo = info;
        this.alreadyClaimed = info.is_claimed;
        this.loading = false;
      },
      error: (err) => {
        this.error = err.error?.error || 'Failed to load workspace information';
        this.loading = false;
      }
    });
  }
}
