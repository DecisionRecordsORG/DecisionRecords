import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-license-acceptance',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatCheckboxModule,
    MatProgressSpinnerModule
  ],
  template: `
    <div class="license-container">
      <mat-card class="license-card">
        <mat-card-header>
          <mat-card-title>
            <mat-icon>gavel</mat-icon>
            License Agreement
          </mat-card-title>
          <mat-card-subtitle>
            Business Source License 1.1
          </mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          <div class="license-intro">
            <p>Welcome to <strong>Decision Records</strong>!</p>
            <p>Before you begin, please review and accept the license terms.</p>
          </div>

          <div class="license-summary">
            <h3>License Summary</h3>
            <p>Decision Records is licensed under the <strong>Business Source License 1.1 (BSL 1.1)</strong>.</p>

            <div class="license-points">
              <div class="point allowed">
                <mat-icon>check_circle</mat-icon>
                <span><strong>Allowed:</strong> Use for your own organization's internal purposes</span>
              </div>
              <div class="point allowed">
                <mat-icon>check_circle</mat-icon>
                <span><strong>Allowed:</strong> Modify and contribute improvements</span>
              </div>
              <div class="point allowed">
                <mat-icon>check_circle</mat-icon>
                <span><strong>Allowed:</strong> Self-host for your team or company</span>
              </div>
              <div class="point restricted">
                <mat-icon>block</mat-icon>
                <span><strong>Restricted:</strong> Offering as a commercial hosted service</span>
              </div>
            </div>

            <p class="conversion-note">
              <mat-icon>schedule</mat-icon>
              The license converts to Apache 2.0 (fully open source) on the Change Date specified in the LICENSE file.
            </p>
          </div>

          <div class="license-link">
            <a href="https://github.com/DecisionRecordsORG/DecisionRecords/blob/main/LICENSE"
               target="_blank"
               rel="noopener noreferrer">
              <mat-icon>open_in_new</mat-icon>
              Read the full license text on GitHub
            </a>
          </div>

          <div class="acceptance-section">
            <mat-checkbox [(ngModel)]="accepted" color="primary">
              I have read and accept the Business Source License 1.1 terms
            </mat-checkbox>
          </div>
        </mat-card-content>

        <mat-card-actions>
          <button mat-raised-button
                  color="primary"
                  (click)="acceptLicense()"
                  [disabled]="!accepted || submitting">
            @if (submitting) {
              <mat-spinner diameter="20"></mat-spinner>
            } @else {
              <mat-icon>check</mat-icon>
              Accept and Continue
            }
          </button>
        </mat-card-actions>
      </mat-card>
    </div>
  `,
  styles: [`
    .license-container {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
      padding: 24px;
    }

    .license-card {
      max-width: 700px;
      width: 100%;
    }

    mat-card-header {
      margin-bottom: 16px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 24px;
    }

    mat-card-title mat-icon {
      font-size: 28px;
      width: 28px;
      height: 28px;
      color: #1976d2;
    }

    .license-intro {
      margin-bottom: 24px;
      font-size: 16px;
      line-height: 1.6;
    }

    .license-summary {
      background: #f5f5f5;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 24px;
    }

    .license-summary h3 {
      margin: 0 0 12px 0;
      color: #333;
    }

    .license-points {
      margin: 16px 0;
    }

    .point {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin: 12px 0;
      font-size: 14px;
    }

    .point mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
      flex-shrink: 0;
    }

    .point.allowed mat-icon {
      color: #2e7d32;
    }

    .point.restricted mat-icon {
      color: #f57c00;
    }

    .conversion-note {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 16px;
      padding: 12px;
      background: #e3f2fd;
      border-radius: 4px;
      font-size: 14px;
    }

    .conversion-note mat-icon {
      color: #1976d2;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .license-link {
      margin-bottom: 24px;
    }

    .license-link a {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #1976d2;
      text-decoration: none;
      font-weight: 500;
    }

    .license-link a:hover {
      text-decoration: underline;
    }

    .license-link mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .acceptance-section {
      margin-bottom: 16px;
      padding: 16px;
      background: #fff3e0;
      border-radius: 4px;
    }

    mat-card-actions {
      padding: 16px;
      display: flex;
      justify-content: flex-end;
    }

    mat-card-actions button {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    mat-card-actions mat-spinner {
      margin-right: 8px;
    }

    @media (max-width: 600px) {
      .license-container {
        padding: 16px;
      }

      .license-card {
        margin: 0;
      }
    }
  `]
})
export class LicenseAcceptanceComponent implements OnInit {
  accepted = false;
  submitting = false;

  constructor(
    private http: HttpClient,
    private router: Router
  ) {}

  ngOnInit(): void {
    // Check if license is already accepted
    this.http.get<{ accepted: boolean }>('/api/system/license').subscribe({
      next: (response) => {
        if (response.accepted) {
          // Already accepted, redirect to main app
          this.router.navigate(['/']);
        }
      },
      error: () => {
        // API error, continue showing the form
      }
    });
  }

  acceptLicense(): void {
    if (!this.accepted) return;

    this.submitting = true;
    this.http.post('/api/system/license/accept', {
      accept: true,
      accepted_by: 'self-hosted-admin'
    }).subscribe({
      next: () => {
        this.submitting = false;
        // Redirect to main app
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.submitting = false;
        console.error('Failed to accept license:', err);
        // Still redirect - the license acceptance is best-effort
        this.router.navigate(['/']);
      }
    });
  }
}
