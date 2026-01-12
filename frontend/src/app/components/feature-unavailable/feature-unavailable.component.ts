import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';

/**
 * Feature Unavailable Component
 *
 * Displayed in Community Edition when a user tries to access
 * an Enterprise Edition feature (Slack, Teams, AI, etc.)
 */
@Component({
  selector: 'app-feature-unavailable',
  standalone: true,
  imports: [CommonModule, RouterModule, MatButtonModule, MatIconModule, MatCardModule],
  template: `
    <div class="feature-unavailable-container">
      <mat-card class="feature-card">
        <mat-card-content>
          <mat-icon class="feature-icon">business</mat-icon>
          <h1>Enterprise Feature</h1>
          <p>
            This feature is only available in the Enterprise Edition of Decision Records.
          </p>
          <p class="subtext">
            Enterprise Edition includes advanced integrations like Slack, Microsoft Teams,
            AI-powered features, and more.
          </p>
          <div class="actions">
            <a mat-raised-button color="primary" routerLink="/">
              <mat-icon>home</mat-icon>
              Go to Home
            </a>
            <a mat-stroked-button href="https://decisionrecords.org/pricing" target="_blank">
              <mat-icon>open_in_new</mat-icon>
              Learn More
            </a>
          </div>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .feature-unavailable-container {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 80vh;
      padding: 20px;
    }

    .feature-card {
      max-width: 500px;
      text-align: center;
      padding: 40px;
    }

    .feature-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #1976d2;
      margin-bottom: 20px;
    }

    h1 {
      margin: 0 0 16px 0;
      color: #333;
    }

    p {
      color: #666;
      margin: 0 0 12px 0;
      line-height: 1.6;
    }

    .subtext {
      font-size: 14px;
      color: #888;
    }

    .actions {
      display: flex;
      gap: 12px;
      justify-content: center;
      margin-top: 24px;
      flex-wrap: wrap;
    }

    .actions a {
      display: flex;
      align-items: center;
      gap: 8px;
    }
  `]
})
export class FeatureUnavailableComponent {}
