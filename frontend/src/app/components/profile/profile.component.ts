import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDividerModule } from '@angular/material/divider';
import { AuthService } from '../../services/auth.service';
import { Subscription, User } from '../../models/decision.model';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatSlideToggleModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDividerModule
  ],
  template: `
    <div class="profile-container">
      <h1>
        <mat-icon>person</mat-icon>
        Profile & Notifications
      </h1>

      @if (authService.currentUser) {
        <mat-card class="profile-card">
          <mat-card-header>
            <mat-card-title>Account Information</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <div class="info-grid">
              <div class="info-item">
                <span class="label">Name</span>
                <span class="value">{{ user?.name || 'Not set' }}</span>
              </div>
              <div class="info-item">
                <span class="label">Email</span>
                <span class="value">{{ user?.email }}</span>
              </div>
              <div class="info-item">
                <span class="label">Domain</span>
                <span class="value">{{ user?.sso_domain }}</span>
              </div>
              <div class="info-item">
                <span class="label">Last Login</span>
                <span class="value">{{ user?.last_login ? (user?.last_login | date:'medium') : 'Never' }}</span>
              </div>
            </div>
          </mat-card-content>
        </mat-card>

        <mat-card class="subscription-card">
          <mat-card-header>
            <mat-card-title>
              <mat-icon>notifications</mat-icon>
              Notification Preferences
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            @if (isLoading) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else {
              <div class="notification-options">
                <div class="notification-option">
                  <div class="option-info">
                    <h3>New Decisions</h3>
                    <p>Get notified when new architecture decisions are created</p>
                  </div>
                  <mat-slide-toggle [(ngModel)]="subscription.notify_on_create"
                                    (change)="saveSubscription()">
                  </mat-slide-toggle>
                </div>

                <mat-divider></mat-divider>

                <div class="notification-option">
                  <div class="option-info">
                    <h3>Decision Updates</h3>
                    <p>Get notified when existing decisions are modified</p>
                  </div>
                  <mat-slide-toggle [(ngModel)]="subscription.notify_on_update"
                                    (change)="saveSubscription()">
                  </mat-slide-toggle>
                </div>

                <mat-divider></mat-divider>

                <div class="notification-option">
                  <div class="option-info">
                    <h3>Status Changes</h3>
                    <p>Get notified when a decision's status changes (e.g., proposed to accepted)</p>
                  </div>
                  <mat-slide-toggle [(ngModel)]="subscription.notify_on_status_change"
                                    (change)="saveSubscription()">
                  </mat-slide-toggle>
                </div>
              </div>

              @if (isSaving) {
                <div class="saving-indicator">
                  <mat-spinner diameter="20"></mat-spinner>
                  <span>Saving...</span>
                </div>
              }
            }
          </mat-card-content>
        </mat-card>
      }
    </div>
  `,
  styles: [`
    .profile-container {
      padding: 24px;
      max-width: 800px;
      margin: 0 auto;
    }

    h1 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 24px;
    }

    .profile-card, .subscription-card {
      margin-bottom: 24px;
    }

    .info-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      padding-top: 16px;
    }

    .info-item .label {
      display: block;
      font-size: 12px;
      color: #888;
      text-transform: uppercase;
      margin-bottom: 4px;
    }

    .info-item .value {
      font-size: 16px;
      font-weight: 500;
    }

    .subscription-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 24px;
    }

    .notification-options {
      padding-top: 16px;
    }

    .notification-option {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 0;
    }

    .option-info h3 {
      margin: 0 0 4px 0;
      font-size: 16px;
      font-weight: 500;
    }

    .option-info p {
      margin: 0;
      font-size: 14px;
      color: #666;
    }

    .saving-indicator {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #888;
      margin-top: 16px;
    }

    mat-divider {
      margin: 0;
    }
  `]
})
export class ProfileComponent implements OnInit {
  subscription: Subscription = {
    notify_on_create: false,
    notify_on_update: false,
    notify_on_status_change: false
  };
  isLoading = true;
  isSaving = false;
  user: User | null = null;

  constructor(
    public authService: AuthService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    if (this.authService.currentUser && !this.authService.isMasterAccount) {
      this.user = this.authService.currentUser.user as User;
      this.loadSubscription();
    }
  }

  loadSubscription(): void {
    this.authService.getSubscription().subscribe({
      next: (subscription) => {
        this.subscription = subscription;
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  saveSubscription(): void {
    this.isSaving = true;
    this.authService.updateSubscription(this.subscription).subscribe({
      next: (subscription) => {
        this.subscription = subscription;
        this.isSaving = false;
        this.snackBar.open('Preferences saved', 'Close', { duration: 2000 });
      },
      error: () => {
        this.isSaving = false;
        this.snackBar.open('Failed to save preferences', 'Close', { duration: 3000 });
      }
    });
  }
}
