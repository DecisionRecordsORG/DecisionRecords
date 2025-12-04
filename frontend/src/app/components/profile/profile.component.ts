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
import { MatListModule } from '@angular/material/list';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { AuthService } from '../../services/auth.service';
import { WebAuthnService } from '../../services/webauthn.service';
import { Subscription, User, WebAuthnCredential } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';

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
    MatDividerModule,
    MatListModule,
    MatChipsModule,
    MatDialogModule,
    MatTooltipModule
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
                <span class="label">Authentication</span>
                <span class="value">
                  @if (user?.auth_type === 'webauthn') {
                    <mat-icon class="auth-icon">fingerprint</mat-icon> Passkey
                  } @else {
                    <mat-icon class="auth-icon">login</mat-icon> SSO
                  }
                </span>
              </div>
              <div class="info-item">
                <span class="label">Last Login</span>
                <span class="value">{{ user?.last_login ? (user?.last_login | date:'medium') : 'Never' }}</span>
              </div>
              <div class="info-item">
                <span class="label">Role</span>
                <span class="value">
                  @if (user?.is_admin) {
                    <mat-chip class="admin-chip" highlighted>Administrator</mat-chip>
                  } @else {
                    User
                  }
                </span>
              </div>
            </div>
          </mat-card-content>
        </mat-card>

        <!-- Passkeys Section (only for WebAuthn users) -->
        @if (user?.auth_type === 'webauthn') {
          <mat-card class="passkeys-card">
            <mat-card-header>
              <mat-card-title>
                <mat-icon>key</mat-icon>
                Passkeys
              </mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <p class="section-description">
                Passkeys are secure credentials stored on your devices. You can add multiple passkeys for backup access.
              </p>

              @if (isLoadingCredentials) {
                <div class="loading">
                  <mat-spinner diameter="40"></mat-spinner>
                </div>
              } @else {
                <mat-list class="credentials-list">
                  @for (credential of credentials; track credential.id) {
                    <mat-list-item>
                      <mat-icon matListItemIcon>fingerprint</mat-icon>
                      <div matListItemTitle>{{ credential.device_name }}</div>
                      <div matListItemLine>
                        Created: {{ credential.created_at | date:'mediumDate' }}
                        @if (credential.last_used_at) {
                          &middot; Last used: {{ credential.last_used_at | date:'mediumDate' }}
                        }
                      </div>
                      <button mat-icon-button matListItemMeta
                              [disabled]="credentials.length <= 1"
                              (click)="deleteCredential(credential)"
                              [matTooltip]="credentials.length <= 1 ? 'Cannot delete your only passkey' : 'Delete passkey'">
                        <mat-icon>delete</mat-icon>
                      </button>
                    </mat-list-item>
                  }
                </mat-list>

                @if (credentials.length === 0) {
                  <p class="no-credentials">No passkeys registered. This shouldn't happen - please contact support.</p>
                }

                <button mat-raised-button color="primary" class="add-passkey-button"
                        (click)="addPasskey()" [disabled]="isAddingPasskey">
                  @if (isAddingPasskey) {
                    <mat-spinner diameter="20"></mat-spinner>
                  } @else {
                    <mat-icon>add</mat-icon>
                    Add new passkey
                  }
                </button>
              }
            </mat-card-content>
          </mat-card>
        }

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

    .profile-card, .subscription-card, .passkeys-card {
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
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .auth-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .admin-chip {
      font-size: 12px;
    }

    .subscription-card mat-card-title,
    .passkeys-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .section-description {
      color: #666;
      font-size: 14px;
      margin-bottom: 16px;
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 24px;
    }

    .credentials-list {
      margin-bottom: 16px;
    }

    .no-credentials {
      text-align: center;
      color: #999;
      padding: 24px;
    }

    .add-passkey-button {
      width: 100%;
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
  credentials: WebAuthnCredential[] = [];
  isLoading = true;
  isLoadingCredentials = true;
  isSaving = false;
  isAddingPasskey = false;
  user: User | null = null;

  constructor(
    public authService: AuthService,
    private webAuthnService: WebAuthnService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {}

  ngOnInit(): void {
    if (this.authService.currentUser && !this.authService.isMasterAccount) {
      this.user = this.authService.currentUser.user as User;
      this.loadSubscription();
      if (this.user.auth_type === 'webauthn') {
        this.loadCredentials();
      } else {
        this.isLoadingCredentials = false;
      }
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

  loadCredentials(): void {
    this.webAuthnService.getCredentials().subscribe({
      next: (credentials) => {
        this.credentials = credentials;
        this.isLoadingCredentials = false;
      },
      error: () => {
        this.isLoadingCredentials = false;
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

  addPasskey(): void {
    if (!this.user) return;

    this.isAddingPasskey = true;

    this.webAuthnService.register(this.user.email, this.user.name).subscribe({
      next: () => {
        this.isAddingPasskey = false;
        this.snackBar.open('Passkey added successfully', 'Close', { duration: 2000 });
        this.loadCredentials();
      },
      error: (err) => {
        this.isAddingPasskey = false;
        this.snackBar.open(err.error?.error || 'Failed to add passkey', 'Close', { duration: 3000 });
      }
    });
  }

  deleteCredential(credential: WebAuthnCredential): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete Passkey',
        message: `Are you sure you want to delete the passkey "${credential.device_name}"? You won't be able to use this device to sign in anymore.`,
        confirmText: 'Delete',
        cancelText: 'Cancel'
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.webAuthnService.deleteCredential(credential.credential_id).subscribe({
          next: () => {
            this.snackBar.open('Passkey deleted', 'Close', { duration: 2000 });
            this.loadCredentials();
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to delete passkey', 'Close', { duration: 3000 });
          }
        });
      }
    });
  }
}
