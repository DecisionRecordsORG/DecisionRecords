import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../services/auth.service';
import { interval, Subscription } from 'rxjs';

interface DomainStatus {
  domain: string;
  status: 'pending' | 'approved' | 'rejected' | 'unknown';
  message: string;
  is_public_domain?: boolean;
  reason?: string;
}

@Component({
  selector: 'app-pending-approval',
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
    <div class="pending-container">
      <mat-card class="pending-card">
        <div class="pending-icon">
          @if (isChecking) {
            <mat-spinner diameter="80"></mat-spinner>
          } @else if (status === 'approved') {
            <mat-icon class="success">check_circle</mat-icon>
          } @else if (status === 'rejected') {
            <mat-icon class="error">cancel</mat-icon>
          } @else {
            <mat-icon class="pending">hourglass_empty</mat-icon>
          }
        </div>

        @if (status === 'pending') {
          <h1>Domain Approval Pending</h1>
          <p class="subtitle">
            Your organisation domain <strong>{{ domain }}</strong> is awaiting approval.
          </p>

          <div class="info-section">
            <h3>What happens next?</h3>
            <ol>
              <li>Your domain request will be reviewed</li>
              <li>You will receive an email notification when your domain is approved</li>
              <li>Once approved, you can access all features of the application</li>
            </ol>
          </div>

          <div class="status-check">
            <p>Last checked: {{ lastChecked | date:'medium' }}</p>
            <button mat-raised-button color="primary" (click)="checkStatus()" [disabled]="isChecking">
              <mat-spinner diameter="20" *ngIf="isChecking"></mat-spinner>
              <mat-icon *ngIf="!isChecking">refresh</mat-icon>
              <span *ngIf="!isChecking">Check Status</span>
            </button>
          </div>

          <p class="auto-check-note">
            Status is automatically checked every 30 seconds
          </p>
        } @else if (status === 'approved') {
          <h1>Domain Approved!</h1>
          <p class="subtitle">
            Your organization domain <strong>{{ domain }}</strong> has been approved.
          </p>
          <p>You can now access all features of the application.</p>

          <button mat-raised-button color="primary" (click)="goToDashboard()">
            <mat-icon>dashboard</mat-icon>
            Go to Dashboard
          </button>
        } @else if (status === 'rejected') {
          <h1>Domain Rejected</h1>
          <p class="subtitle error-text">
            Unfortunately, your organisation domain <strong>{{ domain }}</strong> has been rejected.
          </p>
          @if (rejectionReason) {
            <div class="rejection-reason">
              <strong>Reason:</strong> {{ rejectionReason }}
            </div>
          }
          <p>Please contact support for more information.</p>

          <button mat-raised-button (click)="logout()">
            <mat-icon>logout</mat-icon>
            Logout
          </button>
        }
      </mat-card>

      <div class="footer-links">
        <a (click)="logout()">Logout</a>
        @if (hasPasskey) {
          <span>|</span>
          <a [routerLink]="['/' + domain, 'profile']">Manage Passkeys</a>
        }
      </div>
    </div>
  `,
  styles: [`
    .pending-container {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }

    .pending-card {
      max-width: 500px;
      width: 100%;
      padding: 48px;
      text-align: center;
    }

    .pending-icon {
      margin-bottom: 24px;
    }

    .pending-icon mat-icon {
      font-size: 80px;
      width: 80px;
      height: 80px;
    }

    .pending-icon mat-icon.pending {
      color: #ff9800;
    }

    .pending-icon mat-icon.success {
      color: #4caf50;
    }

    .pending-icon mat-icon.error {
      color: #f44336;
    }

    h1 {
      margin: 0 0 16px 0;
      font-size: 28px;
      font-weight: 500;
    }

    .subtitle {
      font-size: 16px;
      color: #666;
      margin-bottom: 32px;
    }

    .subtitle strong {
      color: #333;
    }

    .error-text {
      color: #c62828;
    }

    .info-section {
      text-align: left;
      background: #f5f5f5;
      padding: 24px;
      border-radius: 8px;
      margin-bottom: 32px;
    }

    .info-section h3 {
      margin: 0 0 16px 0;
      font-size: 16px;
    }

    .info-section ol {
      margin: 0;
      padding-left: 20px;
    }

    .info-section li {
      margin-bottom: 8px;
      color: #555;
    }

    .status-check {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      margin-bottom: 16px;
    }

    .status-check p {
      margin: 0;
      color: #888;
      font-size: 14px;
    }

    .status-check button {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .auto-check-note {
      font-size: 12px;
      color: #999;
      margin: 0;
    }

    .rejection-reason {
      background: #ffebee;
      color: #c62828;
      padding: 16px;
      border-radius: 8px;
      margin-bottom: 24px;
      text-align: left;
    }

    .footer-links {
      margin-top: 24px;
      display: flex;
      gap: 16px;
      color: rgba(255, 255, 255, 0.8);
    }

    .footer-links a {
      color: white;
      text-decoration: none;
      cursor: pointer;
    }

    .footer-links a:hover {
      text-decoration: underline;
    }

    button mat-icon {
      margin-right: 8px;
    }
  `]
})
export class PendingApprovalComponent implements OnInit, OnDestroy {
  domain = '';
  status: 'pending' | 'approved' | 'rejected' | 'unknown' = 'pending';
  rejectionReason = '';
  isChecking = false;
  lastChecked = new Date();
  hasPasskey = false;

  private checkSubscription?: Subscription;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient,
    private authService: AuthService
  ) {}

  ngOnInit(): void {
    this.domain = this.route.snapshot.paramMap.get('tenant') || '';

    // Check if user has passkey
    if (this.authService.currentUser?.user) {
      const user = this.authService.currentUser.user as any;
      this.hasPasskey = user.webauthn_credentials?.length > 0;
    }

    // Initial check
    this.checkStatus();

    // Auto-check every 30 seconds
    this.checkSubscription = interval(30000).subscribe(() => {
      this.checkStatus();
    });
  }

  ngOnDestroy(): void {
    this.checkSubscription?.unsubscribe();
  }

  checkStatus(): void {
    this.isChecking = true;

    this.http.get<DomainStatus>(`/api/domains/check/${this.domain}`).subscribe({
      next: (response) => {
        this.isChecking = false;
        this.lastChecked = new Date();
        this.status = response.status;

        if (response.status === 'approved') {
          // Domain approved - redirect to dashboard after a short delay
          setTimeout(() => this.goToDashboard(), 2000);
        } else if (response.status === 'rejected') {
          this.rejectionReason = response.reason || '';
        }
      },
      error: () => {
        this.isChecking = false;
        this.lastChecked = new Date();
      }
    });
  }

  goToDashboard(): void {
    this.router.navigate([`/${this.domain}`]);
  }

  logout(): void {
    this.authService.logout().subscribe({
      next: (response: any) => {
        // Redirect to marketing domain where OAuth login options are available
        if (response?.redirect_url) {
          window.location.href = response.redirect_url;
        } else {
          this.router.navigate(['/']);
        }
      },
      error: () => this.router.navigate(['/'])
    });
  }
}
