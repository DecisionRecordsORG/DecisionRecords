import { Component, TemplateRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatDividerModule } from '@angular/material/divider';
import { MatBadgeModule } from '@angular/material/badge';
import { MatDialogModule, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../services/auth.service';
import { AdminService } from '../../services/admin.service';
import { User, MasterAccount } from '../../models/decision.model';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    ReactiveFormsModule,
    MatToolbarModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatDividerModule,
    MatBadgeModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatCheckboxModule,
    MatProgressSpinnerModule
  ],
  template: `
    <mat-toolbar color="primary" class="navbar">
      <a [routerLink]="homeLink" class="brand">
        <mat-icon>article</mat-icon>
        <span class="brand-text">Decision Records</span>
        @if (!authService.isMasterAccount && userDomain) {
          <span class="tenant-badge">{{ userDomain }}</span>
        }
      </a>

      <span class="spacer"></span>

      @if (authService.isAuthenticated) {
        <nav class="nav-links">
          <a mat-button [routerLink]="decisionsLink" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}">
            <mat-icon>list</mat-icon>
            Decisions
          </a>
          @if (!authService.isMasterAccount) {
            <a mat-button [routerLink]="newDecisionLink" routerLinkActive="active">
              <mat-icon>add</mat-icon>
              New
            </a>
          }
        </nav>

        @if (!authService.isMasterAccount) {
          <button mat-button class="feedback-btn" (click)="openFeedbackDialog()">
            <mat-icon>feedback</mat-icon>
            <span>Feedback</span>
          </button>
        }

        <button mat-button [matMenuTriggerFor]="userMenu" class="user-button">
          @if (authService.isMasterAccount) {
            <mat-icon>admin_panel_settings</mat-icon>
          } @else {
            <mat-icon>person</mat-icon>
          }
          <span class="user-name">{{ displayName }}</span>
          @if (pendingRequestsCount > 0 && authService.isAdmin) {
            <span class="badge">{{ pendingRequestsCount }}</span>
          }
          <mat-icon>arrow_drop_down</mat-icon>
        </button>

        <mat-menu #userMenu="matMenu">
          <div class="menu-header">
            @if (authService.isMasterAccount) {
              <mat-icon>shield</mat-icon>
              <span>Super Admin</span>
            } @else {
              <mat-icon>business</mat-icon>
              <span>{{ userDomain }}</span>
            }
          </div>
          <mat-divider></mat-divider>

          @if (authService.isMasterAccount) {
            <a mat-menu-item routerLink="/superadmin/dashboard">
              <mat-icon>dashboard</mat-icon>
              Dashboard
            </a>
            <a mat-menu-item routerLink="/superadmin/settings">
              <mat-icon>settings</mat-icon>
              System Settings
            </a>
          } @else {
            <a mat-menu-item [routerLink]="profileLink">
              <mat-icon>person</mat-icon>
              Profile
            </a>
            <a mat-menu-item [routerLink]="profileLink">
              <mat-icon>notifications</mat-icon>
              Notifications
            </a>
            @if (authService.isAdmin) {
              <a mat-menu-item [routerLink]="adminLink">
                <mat-icon>settings</mat-icon>
                Admin Settings
                @if (pendingRequestsCount > 0) {
                  <span class="menu-badge">{{ pendingRequestsCount }}</span>
                }
              </a>
            }
          }

          <mat-divider></mat-divider>
          <button mat-menu-item (click)="logout()">
            <mat-icon>logout</mat-icon>
            Logout
          </button>
        </mat-menu>
      }
    </mat-toolbar>

    <!-- Feedback Dialog Template -->
    <ng-template #feedbackDialog>
      <div class="feedback-dialog-container">
        <button mat-icon-button class="dialog-close" (click)="closeFeedbackDialog()">
          <mat-icon>close</mat-icon>
        </button>

        <div class="dialog-header">
          <mat-icon class="dialog-icon">feedback</mat-icon>
          <h2>Send Feedback</h2>
        </div>

        <p class="dialog-intro">
          Share your thoughts, suggestions, or report issues. Your email is used to create a support ticket and may be used to follow up with you.
        </p>

        @if (feedbackSuccess) {
          <div class="success-message">
            <mat-icon>check_circle</mat-icon>
            <p>{{ feedbackSuccess }}</p>
          </div>
        } @else {
          <form [formGroup]="feedbackForm" (ngSubmit)="submitFeedback()">
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Your Email</mat-label>
              <input matInput formControlName="email" type="email" readonly>
              <mat-icon matPrefix>email</mat-icon>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Your Name</mat-label>
              <input matInput formControlName="name" placeholder="Your name">
              <mat-icon matPrefix>person</mat-icon>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Your Feedback</mat-label>
              <textarea matInput formControlName="feedback" rows="4"
                        placeholder="Share your thoughts, suggestions, or report issues..."></textarea>
            </mat-form-field>

            <mat-checkbox formControlName="contactConsent" class="consent-checkbox">
              It's okay to reach out to me about this feedback
            </mat-checkbox>

            @if (feedbackError) {
              <p class="error-message">{{ feedbackError }}</p>
            }

            <button mat-raised-button color="primary" type="submit"
                    [disabled]="feedbackForm.invalid || feedbackLoading" class="full-width submit-btn">
              <mat-spinner diameter="20" *ngIf="feedbackLoading"></mat-spinner>
              <ng-container *ngIf="!feedbackLoading">
                <mat-icon>send</mat-icon>
                <span>Send Feedback</span>
              </ng-container>
            </button>
          </form>
        }
      </div>
    </ng-template>
  `,
  styles: [`
    .navbar {
      position: sticky;
      top: 0;
      z-index: 1000;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
      color: white;
      text-decoration: none;
      font-size: 18px;
      font-weight: 500;
    }

    .tenant-badge {
      font-size: 12px;
      background: rgba(255, 255, 255, 0.2);
      padding: 2px 8px;
      border-radius: 4px;
      margin-left: 8px;
    }

    .spacer {
      flex: 1;
    }

    .nav-links {
      display: flex;
      gap: 8px;
      margin-right: 16px;
    }

    .nav-links a {
      color: rgba(255, 255, 255, 0.9);
    }

    .nav-links a.active {
      background: rgba(255, 255, 255, 0.1);
    }

    .user-button {
      color: white;
    }

    .user-name {
      margin: 0 4px;
      max-width: 150px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .badge {
      background: #ff4081;
      color: white;
      border-radius: 50%;
      padding: 2px 6px;
      font-size: 11px;
      margin-left: 4px;
    }

    .menu-badge {
      background: #ff4081;
      color: white;
      border-radius: 4px;
      padding: 2px 6px;
      font-size: 11px;
      margin-left: 8px;
    }

    .menu-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      color: #666;
      font-size: 13px;
    }

    .menu-header mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    @media (max-width: 600px) {
      .nav-links {
        display: none;
      }

      .user-name {
        display: none;
      }

      .brand-text {
        display: none;
      }

      .tenant-badge {
        margin-left: 0;
      }
    }

    /* Feedback button */
    .feedback-btn {
      color: rgba(255, 255, 255, 0.85);
      margin-right: 8px;
    }

    .feedback-btn mat-icon {
      margin-right: 4px;
    }

    .feedback-btn:hover {
      color: white;
      background: rgba(255, 255, 255, 0.1);
    }

    /* Feedback dialog styles */
    .feedback-dialog-container {
      padding: 24px;
      min-width: 380px;
      max-width: 420px;
      position: relative;
    }

    .dialog-close {
      position: absolute;
      top: 8px;
      right: 8px;
      color: #94a3b8;
    }

    .dialog-close:hover {
      color: #64748b;
      background: #f1f5f9;
    }

    .dialog-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
      padding-right: 32px;
    }

    .dialog-header h2 {
      font-size: 1.25rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0;
    }

    .dialog-icon {
      color: #2563eb;
      font-size: 28px;
      width: 28px;
      height: 28px;
    }

    .dialog-intro {
      color: #64748b;
      font-size: 0.9rem;
      line-height: 1.5;
      margin: 0 0 20px;
    }

    .full-width {
      width: 100%;
    }

    mat-form-field {
      margin-bottom: 4px;
    }

    .consent-checkbox {
      display: block;
      margin: 8px 0 16px;
      color: #475569;
      font-size: 0.9rem;
    }

    ::ng-deep .consent-checkbox .mdc-form-field {
      color: #475569;
    }

    .submit-btn {
      margin-top: 8px;
      padding: 10px 24px;
      font-size: 14px;
      font-weight: 500;
      border-radius: 100px;
      background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%) !important;
    }

    .submit-btn span,
    .submit-btn mat-icon {
      color: #ffffff !important;
    }

    ::ng-deep .submit-btn .mdc-button__label {
      display: inline-flex !important;
      align-items: center !important;
      gap: 8px !important;
    }

    .error-message {
      background-color: #fef2f2;
      color: #dc2626;
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 16px;
      font-size: 14px;
    }

    .success-message {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      padding: 24px 0;
    }

    .success-message mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #16a34a;
      margin-bottom: 12px;
    }

    .success-message p {
      color: #16a34a;
      font-size: 1rem;
      margin: 0;
    }
  `]
})
export class NavbarComponent {
  @ViewChild('feedbackDialog') feedbackDialogTemplate!: TemplateRef<any>;
  feedbackDialogRef: MatDialogRef<any> | null = null;
  feedbackForm: FormGroup;
  feedbackLoading = false;
  feedbackError = '';
  feedbackSuccess = '';
  pendingRequestsCount = 0;

  constructor(
    public authService: AuthService,
    private adminService: AdminService,
    private router: Router,
    private fb: FormBuilder,
    private http: HttpClient,
    private dialog: MatDialog
  ) {
    // Initialize feedback form
    this.feedbackForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      name: ['', Validators.required],
      feedback: ['', [Validators.required, Validators.minLength(10)]],
      contactConsent: [true]
    });

    // Load pending requests count for admins
    if (this.authService.isAdmin) {
      this.loadPendingRequestsCount();
    }
  }

  loadPendingRequestsCount(): void {
    this.adminService.getPendingAccessRequests().subscribe({
      next: (requests) => this.pendingRequestsCount = requests.length,
      error: () => this.pendingRequestsCount = 0
    });
  }

  get displayName(): string {
    const user = this.authService.currentUser?.user;
    if (!user) return '';

    if (this.authService.isMasterAccount) {
      const master = user as MasterAccount;
      return master.name || master.username;
    } else {
      const regularUser = user as User;
      return regularUser.name || regularUser.email;
    }
  }

  get userDomain(): string {
    if (this.authService.isMasterAccount) return '';
    const user = this.authService.currentUser?.user as User;
    return user?.sso_domain || '';
  }

  get homeLink(): string {
    if (this.authService.isMasterAccount) {
      return '/superadmin/dashboard';
    }
    return `/${this.userDomain}`;
  }

  get decisionsLink(): string {
    if (this.authService.isMasterAccount) {
      return '/superadmin/dashboard';
    }
    return `/${this.userDomain}`;
  }

  get newDecisionLink(): string {
    return `/${this.userDomain}/decision/new`;
  }

  get profileLink(): string {
    return `/${this.userDomain}/profile`;
  }

  get adminLink(): string {
    return `/${this.userDomain}/admin`;
  }

  logout(): void {
    // Capture master status before logout clears user state
    const wasMaster = this.authService.isMasterAccount;
    this.authService.logout().subscribe({
      next: () => {
        if (wasMaster) {
          this.router.navigate(['/superadmin']);
        } else {
          this.router.navigate(['/']);
        }
      },
      error: () => this.router.navigate(['/'])
    });
  }

  // Feedback dialog methods
  openFeedbackDialog(): void {
    this.feedbackError = '';
    this.feedbackSuccess = '';

    // Pre-fill user email and name from current user
    const user = this.authService.currentUser?.user as User;
    if (user) {
      this.feedbackForm.patchValue({
        email: user.email || '',
        name: user.name || ''
      });
    }

    this.feedbackDialogRef = this.dialog.open(this.feedbackDialogTemplate, {
      width: '450px',
      panelClass: 'feedback-dialog-panel'
    });
  }

  closeFeedbackDialog(): void {
    if (this.feedbackDialogRef) {
      this.feedbackDialogRef.close();
      this.feedbackDialogRef = null;
    }
  }

  submitFeedback(): void {
    if (this.feedbackForm.invalid) return;

    this.feedbackLoading = true;
    this.feedbackError = '';

    const formData = {
      ...this.feedbackForm.value,
      contact_consent: this.feedbackForm.value.contactConsent
    };

    this.http.post<{ message?: string; error?: string }>('/api/feedback', formData).subscribe({
      next: (result) => {
        this.feedbackLoading = false;
        this.feedbackSuccess = result.message || 'Thank you for your feedback!';
      },
      error: (err) => {
        this.feedbackLoading = false;
        this.feedbackError = err.error?.error || 'Failed to submit feedback. Please try again.';
      }
    });
  }
}
