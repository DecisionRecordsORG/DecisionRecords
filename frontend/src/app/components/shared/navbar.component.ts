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
import { DecisionService } from '../../services/decision.service';
import { User, MasterAccount } from '../../models/decision.model';
import { DecisionModalComponent, DecisionModalResult } from '../decision-modal/decision-modal.component';

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
    MatProgressSpinnerModule,
    DecisionModalComponent
  ],
  template: `
    <mat-toolbar class="navbar">
      <a [routerLink]="homeLink" class="brand">
        <svg class="logo-icon" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
          <path d="M9.91,25.94v-2.65l-2.52-.81c-.3,.14-.55,.35-.75,.61l-1.38,1.89c-.36,.49-.37,1.15-.02,1.66l.66,.96c.31,.46,.95,.57,1.39,.24l2.61-1.9Z" fill="#93c5fd"/>
          <path d="M14.26,31.5l3.65-2.14-1.67-3.44-3.05-2.94c-.47-.45-1.09-.7-1.75-.7h-3.18c-.3,0-.6,.07-.87,.21l2.52,3.46,3.65,5.02c.18,.24,.42,.43,.69,.54h0Z" fill="#60a5fa"/>
          <path d="M55.68,33.44l-1.25,3.18,1.25,3.16,3.08-3.08c.37-.37,.31-.99-.12-1.28l-2.95-1.98Z" fill="#93c5fd"/>
          <path d="M55.68,33.44l-1.25,3.18,1.25,3.16,1.4-1.4v-4l-1.4-.94Z" fill="#3b82f6"/>
          <path d="M55.42,28.04l-8.87,4.84-4.21,7.07,4.66,7.98c.32,.54,.9,.88,1.53,.88h6.14c.56,0,1.01-.46,1.01-1.02V28.81c-.01-.28-.1-.55-.26-.78h0Z" fill="#60a5fa"/>
          <path d="M40.51,22.17l-14.62,9.61v16c0,.56,.45,1.02,1.01,1.02h4.69c.65,0,1.28-.24,1.77-.68l8.97-8.17,13.08-11.91c-.16-.27-.4-.47-.69-.59l-14.22-5.28Z" fill="#93c5fd" fill-opacity="0.6"/>
          <path d="M38.88,15.48l-10.22,5.95-4.47,8.72,1.74,1.62,4.27,3.96c.44,.41,1.09,.5,1.63,.24l9.47-4.65c.53-.26,.82-.84,.71-1.42l-1.5-7.73-1.15-5.97c-.07-.29-.24-.54-.48-.71h0Z" fill="#60a5fa"/>
          <path d="M21.06,15.2c-.61,0-1.15,.38-1.35,.96l-3.46,9.76-1.98,5.59c.28,.12,.6,.16,.9,.11l9.01-1.46h0l14.7-14.67c-.21-.17-.46-.27-.73-.28H21.06Z" fill="#93c5fd" fill-opacity="0.5"/>
          <path d="M7.4,22.48l1.21,4.41,1.31-.95-2.52-3.46Z" fill="#fbbf24"/>
          <path d="M14.26,31.5l1.98-5.59-1.6-1.54-.38,7.13Z" fill="#fbbf24"/>
          <path d="M55.42,28.04l-10.75,15.9-2.33-3.99,13.08-11.91Z" fill="#2563eb"/>
        </svg>
        <span class="brand-text">Decision Records</span>
      </a>

      <span class="spacer"></span>

      @if (authService.isAuthenticated) {
        <nav class="nav-links">
          <a mat-button [routerLink]="decisionsLink" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}">
            <mat-icon>list</mat-icon>
            Decisions
          </a>
          @if (!authService.isMasterAccount) {
            <button mat-button (click)="openCreateModal()">
              <mat-icon>add</mat-icon>
              New
            </button>
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
      background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      color: white;
      text-decoration: none;
      font-size: 18px;
      font-weight: 500;
      transition: opacity 0.2s ease;
    }

    .brand:hover {
      opacity: 0.9;
    }

    .logo-icon {
      width: 38px;
      height: 38px;
      transition: transform 0.2s ease;
      filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
    }

    .brand:hover .logo-icon {
      transform: scale(1.05);
    }

    .brand-text {
      font-weight: 600;
      letter-spacing: -0.3px;
      color: white;
    }

    .spacer {
      flex: 1;
    }

    .nav-links {
      display: flex;
      gap: 4px;
      margin-right: 16px;
    }

    .nav-links a,
    .nav-links button {
      color: rgba(255, 255, 255, 0.8);
      border-radius: 8px;
      transition: all 0.2s ease;
    }

    .nav-links a:hover,
    .nav-links button:hover {
      color: white;
      background: rgba(255, 255, 255, 0.1);
    }

    .nav-links a.active {
      color: white;
      background: rgba(96, 165, 250, 0.2);
    }

    .user-button {
      color: rgba(255, 255, 255, 0.85) !important;
      border-radius: 8px;
    }

    .user-button:hover {
      color: white !important;
      background: rgba(255, 255, 255, 0.1);
    }

    .user-button mat-icon {
      color: rgba(255, 255, 255, 0.85) !important;
    }

    .user-name {
      margin: 0 4px;
      max-width: 150px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .badge {
      background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
      color: #1e293b;
      border-radius: 10px;
      padding: 2px 7px;
      font-size: 11px;
      margin-left: 4px;
      font-weight: 600;
    }

    .menu-badge {
      background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
      color: #1e293b;
      border-radius: 4px;
      padding: 2px 6px;
      font-size: 11px;
      margin-left: 8px;
      font-weight: 600;
    }

    .menu-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      color: #64748b;
      font-size: 13px;
    }

    .menu-header mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #3b82f6;
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

      .logo-icon {
        width: 32px;
        height: 32px;
      }
    }

    /* Feedback button */
    .feedback-btn {
      color: rgba(255, 255, 255, 0.75) !important;
      margin-right: 8px;
      border-radius: 8px;
      transition: all 0.2s ease;
    }

    .feedback-btn mat-icon {
      margin-right: 4px;
      color: rgba(255, 255, 255, 0.75) !important;
    }

    .feedback-btn:hover {
      color: #fbbf24 !important;
      background: rgba(251, 191, 36, 0.15);
    }

    .feedback-btn:hover mat-icon {
      color: #fbbf24 !important;
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
    private decisionService: DecisionService,
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

  openCreateModal(): void {
    const dialogRef = this.dialog.open(DecisionModalComponent, {
      width: '1200px',
      maxWidth: '90vw',
      height: '85vh',
      maxHeight: '90vh',
      panelClass: 'decision-modal-panel',
      data: {
        mode: 'create',
        tenant: this.userDomain
      }
    });

    dialogRef.afterClosed().subscribe((result: DecisionModalResult) => {
      if (result?.action === 'saved') {
        const targetUrl = `/${this.userDomain}`;
        // Check if we're already on the decisions list page
        if (this.router.url === targetUrl || this.router.url.startsWith(targetUrl + '?')) {
          // Notify decision-list component to refresh via service
          this.decisionService.notifyRefreshNeeded();
        } else {
          // Navigate to decisions list
          this.router.navigate([targetUrl]);
        }
      }
    });
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
      next: (response: any) => {
        if (wasMaster) {
          // Master accounts stay on app domain for superadmin login
          this.router.navigate(['/superadmin']);
        } else if (response?.redirect_url) {
          // Regular users go to marketing site (where Google/Slack OAuth is available)
          window.location.href = response.redirect_url;
        } else {
          // Fallback to root (will stay on app domain)
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
