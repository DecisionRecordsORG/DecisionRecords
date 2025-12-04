import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { MasterAccount } from '../../models/decision.model';

@Component({
  selector: 'app-master-profile',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatSlideToggleModule
  ],
  template: `
    <div class="master-profile-container">
      <h1>
        <mat-icon>admin_panel_settings</mat-icon>
        Master Account Settings
      </h1>

      @if (master) {
        <mat-card class="info-card">
          <mat-card-header>
            <mat-card-title>Account Information</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <div class="info-grid">
              <div class="info-item">
                <span class="label">Username</span>
                <span class="value">{{ master.username }}</span>
              </div>
              <div class="info-item">
                <span class="label">Name</span>
                <span class="value">{{ master.name }}</span>
              </div>
              <div class="info-item">
                <span class="label">Created</span>
                <span class="value">{{ master.created_at | date:'medium' }}</span>
              </div>
              <div class="info-item">
                <span class="label">Last Login</span>
                <span class="value">{{ master.last_login ? (master.last_login | date:'medium') : 'Never' }}</span>
              </div>
            </div>
          </mat-card-content>
        </mat-card>

        <mat-card class="password-card">
          <mat-card-header>
            <mat-card-title>
              <mat-icon>lock</mat-icon>
              Change Password
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            @if (successMessage) {
              <div class="success-message">{{ successMessage }}</div>
            }
            @if (errorMessage) {
              <div class="error-message">{{ errorMessage }}</div>
            }

            <form [formGroup]="passwordForm" (ngSubmit)="changePassword()">
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Current Password</mat-label>
                <input matInput type="password" formControlName="currentPassword">
                @if (passwordForm.get('currentPassword')?.hasError('required')) {
                  <mat-error>Current password is required</mat-error>
                }
              </mat-form-field>

              <mat-form-field appearance="outline" class="full-width">
                <mat-label>New Password</mat-label>
                <input matInput type="password" formControlName="newPassword">
                @if (passwordForm.get('newPassword')?.hasError('required')) {
                  <mat-error>New password is required</mat-error>
                }
                @if (passwordForm.get('newPassword')?.hasError('minlength')) {
                  <mat-error>Password must be at least 8 characters</mat-error>
                }
              </mat-form-field>

              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Confirm New Password</mat-label>
                <input matInput type="password" formControlName="confirmPassword">
                @if (passwordForm.get('confirmPassword')?.hasError('required')) {
                  <mat-error>Please confirm your password</mat-error>
                }
                @if (passwordForm.get('confirmPassword')?.hasError('passwordMismatch')) {
                  <mat-error>Passwords do not match</mat-error>
                }
              </mat-form-field>

              <button mat-raised-button color="primary" type="submit"
                      [disabled]="passwordForm.invalid || isChangingPassword">
                @if (isChangingPassword) {
                  <mat-spinner diameter="20"></mat-spinner>
                } @else {
                  <mat-icon>save</mat-icon>
                  Change Password
                }
              </button>
            </form>
          </mat-card-content>
        </mat-card>

        <mat-card class="system-settings-card">
          <mat-card-header>
            <mat-card-title>
              <mat-icon>settings</mat-icon>
              System Settings
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <div class="setting-item">
              <div class="setting-info">
                <h4>Email Verification</h4>
                <p>Require users to verify their email address before accessing tenant login pages.</p>
              </div>
              <mat-slide-toggle
                [checked]="emailVerificationRequired"
                (change)="toggleEmailVerification($event.checked)"
                [disabled]="isTogglingEmailVerification">
              </mat-slide-toggle>
            </div>
            @if (emailVerificationMessage) {
              <div class="setting-message" [class.success]="emailVerificationSuccess">
                {{ emailVerificationMessage }}
              </div>
            }
          </mat-card-content>
        </mat-card>

        <mat-card class="info-notice">
          <mat-card-content>
            <div class="notice-content">
              <mat-icon>info</mat-icon>
              <div>
                <h3>Master Account Notes</h3>
                <ul>
                  <li>The master account is used for system administration only.</li>
                  <li>Configure SSO providers and email settings in <a routerLink="/settings">System Settings</a>.</li>
                  <li>Master accounts can view all decisions across all domains but cannot create, edit, or delete them.</li>
                  <li>For full functionality, log in with an SSO account after configuring your organization's SSO.</li>
                </ul>
              </div>
            </div>
          </mat-card-content>
        </mat-card>
      }
    </div>
  `,
  styles: [`
    .master-profile-container {
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

    .info-card, .password-card, .info-notice {
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

    .password-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .password-card form {
      padding-top: 16px;
    }

    .full-width {
      width: 100%;
    }

    .success-message {
      background-color: #e8f5e9;
      color: #2e7d32;
      padding: 12px;
      border-radius: 4px;
      margin-bottom: 16px;
    }

    .error-message {
      background-color: #ffebee;
      color: #c62828;
      padding: 12px;
      border-radius: 4px;
      margin-bottom: 16px;
    }

    .info-notice {
      background: #fff3e0;
    }

    .notice-content {
      display: flex;
      gap: 16px;
    }

    .notice-content mat-icon {
      color: #e65100;
    }

    .notice-content h3 {
      margin: 0 0 8px 0;
      font-size: 16px;
    }

    .notice-content ul {
      margin: 0;
      padding-left: 20px;
      color: #666;
    }

    .notice-content li {
      margin-bottom: 4px;
    }

    .notice-content a {
      color: #3f51b5;
    }

    .system-settings-card {
      margin-bottom: 24px;
    }

    .system-settings-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .setting-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 0;
      border-bottom: 1px solid #eee;
    }

    .setting-item:last-child {
      border-bottom: none;
    }

    .setting-info h4 {
      margin: 0 0 4px 0;
      font-size: 16px;
    }

    .setting-info p {
      margin: 0;
      font-size: 13px;
      color: #666;
    }

    .setting-message {
      margin-top: 16px;
      padding: 12px;
      border-radius: 4px;
      background: #ffebee;
      color: #c62828;
    }

    .setting-message.success {
      background: #e8f5e9;
      color: #2e7d32;
    }
  `]
})
export class MasterProfileComponent implements OnInit {
  master: MasterAccount | null = null;
  passwordForm: FormGroup;
  isChangingPassword = false;
  successMessage = '';
  errorMessage = '';

  // Email verification settings
  emailVerificationRequired = true;
  isTogglingEmailVerification = false;
  emailVerificationMessage = '';
  emailVerificationSuccess = false;

  constructor(
    private fb: FormBuilder,
    public authService: AuthService,
    private snackBar: MatSnackBar,
    private http: HttpClient
  ) {
    this.passwordForm = this.fb.group({
      currentPassword: ['', Validators.required],
      newPassword: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required]
    }, { validators: this.passwordMatchValidator });
  }

  ngOnInit(): void {
    if (this.authService.currentUser?.isMaster) {
      this.master = this.authService.currentUser.user as MasterAccount;
    }
    this.loadEmailVerificationSetting();
  }

  loadEmailVerificationSetting(): void {
    this.http.get<{ required: boolean }>('/api/system/email-verification').subscribe({
      next: (response) => {
        this.emailVerificationRequired = response.required;
      },
      error: () => {
        // Default to true if we can't load the setting
        this.emailVerificationRequired = true;
      }
    });
  }

  toggleEmailVerification(required: boolean): void {
    this.isTogglingEmailVerification = true;
    this.emailVerificationMessage = '';

    this.http.put<{ required: boolean; message: string }>('/api/system/email-verification', { required }).subscribe({
      next: (response) => {
        this.emailVerificationRequired = response.required;
        this.emailVerificationMessage = response.message;
        this.emailVerificationSuccess = true;
        this.isTogglingEmailVerification = false;
        setTimeout(() => this.emailVerificationMessage = '', 3000);
      },
      error: (err) => {
        this.emailVerificationMessage = err.error?.error || 'Failed to update setting';
        this.emailVerificationSuccess = false;
        this.isTogglingEmailVerification = false;
        // Revert the toggle
        this.emailVerificationRequired = !required;
      }
    });
  }

  passwordMatchValidator(form: FormGroup) {
    const newPassword = form.get('newPassword');
    const confirmPassword = form.get('confirmPassword');

    if (newPassword && confirmPassword && newPassword.value !== confirmPassword.value) {
      confirmPassword.setErrors({ passwordMismatch: true });
    }
    return null;
  }

  changePassword(): void {
    if (this.passwordForm.invalid) return;

    this.isChangingPassword = true;
    this.successMessage = '';
    this.errorMessage = '';

    const { currentPassword, newPassword } = this.passwordForm.value;

    this.authService.changeMasterPassword(currentPassword, newPassword).subscribe({
      next: () => {
        this.isChangingPassword = false;
        this.successMessage = 'Password changed successfully!';
        this.passwordForm.reset();
      },
      error: (err) => {
        this.isChangingPassword = false;
        this.errorMessage = err.error?.error || 'Failed to change password';
      }
    });
  }
}
