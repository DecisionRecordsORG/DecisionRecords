import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatSelectModule } from '@angular/material/select';
import { RouterModule } from '@angular/router';

interface EmailConfig {
  id: number;
  domain: string;
  smtp_server: string;
  smtp_port: number;
  smtp_username: string;
  from_email: string;
  from_name: string;
  use_tls: boolean;
  enabled: boolean;
}

@Component({
  selector: 'app-superadmin-email',
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
    MatSlideToggleModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatSelectModule
  ],
  template: `
    <div class="email-config-container">
      <h1>
        <mat-icon>email</mat-icon>
        Email Configuration
      </h1>

      <mat-card>
        <mat-card-header>
          <mat-card-title>
            <mat-icon>settings</mat-icon>
            SMTP Settings
          </mat-card-title>
          <mat-card-subtitle>
            Configure the email server for sending notifications (domain approval, user notifications, etc.)
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          @if (successMessage) {
            <div class="success-message">{{ successMessage }}</div>
          }
          @if (errorMessage) {
            <div class="error-message">{{ errorMessage }}</div>
          }

          <form [formGroup]="emailForm" (ngSubmit)="saveEmailConfig()">
            <div class="form-row">
              <mat-form-field appearance="outline">
                <mat-label>SMTP Server</mat-label>
                <input matInput formControlName="smtp_server" placeholder="smtp.example.com">
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>SMTP Port</mat-label>
                <input matInput type="number" formControlName="smtp_port">
              </mat-form-field>
            </div>

            <div class="form-row">
              <mat-form-field appearance="outline">
                <mat-label>SMTP Username</mat-label>
                <input matInput formControlName="smtp_username">
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>SMTP Password</mat-label>
                <input matInput type="password" formControlName="smtp_password"
                       [placeholder]="hasExistingConfig ? 'Leave blank to keep existing' : ''">
              </mat-form-field>
            </div>

            <div class="form-row">
              <mat-form-field appearance="outline">
                <mat-label>From Email</mat-label>
                <input matInput formControlName="from_email" placeholder="noreply@example.com">
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>From Name</mat-label>
                <input matInput formControlName="from_name" placeholder="Architecture Decisions">
              </mat-form-field>
            </div>

            <div class="toggle-row">
              <mat-slide-toggle formControlName="use_tls">Use TLS</mat-slide-toggle>
              <mat-slide-toggle formControlName="enabled">Enabled</mat-slide-toggle>
            </div>

            <div class="form-actions">
              <button mat-raised-button color="primary" type="submit"
                      [disabled]="emailForm.invalid || isSaving">
                @if (isSaving) {
                  <mat-spinner diameter="20"></mat-spinner>
                } @else {
                  <mat-icon>save</mat-icon>
                  Save Configuration
                }
              </button>

              <button mat-button type="button" (click)="testEmail()"
                      [disabled]="!hasExistingConfig || isTesting">
                @if (isTesting) {
                  <mat-spinner diameter="20"></mat-spinner>
                } @else {
                  <mat-icon>send</mat-icon>
                  Send Test Email
                }
              </button>
            </div>
          </form>
        </mat-card-content>
      </mat-card>

      <mat-card class="info-card">
        <mat-card-content>
          <div class="info-content">
            <mat-icon>info</mat-icon>
            <div>
              <h3>Email Configuration Notes</h3>
              <ul>
                <li>This configuration is used for system-wide notifications.</li>
                <li>Domain approval notifications will be sent using this configuration.</li>
                <li>For AWS SES, use the SES SMTP endpoint (e.g., email-smtp.us-east-1.amazonaws.com).</li>
                <li>Test email will be sent to the super admin account.</li>
              </ul>
            </div>
          </div>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .email-config-container {
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

    mat-card {
      margin-bottom: 24px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .form-row {
      display: flex;
      gap: 16px;
      margin-bottom: 8px;
    }

    .form-row mat-form-field {
      flex: 1;
    }

    .toggle-row {
      display: flex;
      gap: 24px;
      margin: 16px 0 24px;
    }

    .form-actions {
      display: flex;
      gap: 16px;
      margin-top: 16px;
    }

    .form-actions button {
      display: flex;
      align-items: center;
      gap: 8px;
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

    .info-card {
      background: #e3f2fd;
    }

    .info-content {
      display: flex;
      gap: 16px;
    }

    .info-content mat-icon {
      color: #1565c0;
    }

    .info-content h3 {
      margin: 0 0 8px 0;
      font-size: 16px;
    }

    .info-content ul {
      margin: 0;
      padding-left: 20px;
      color: #555;
    }

    .info-content li {
      margin-bottom: 4px;
    }
  `]
})
export class SuperadminEmailComponent implements OnInit {
  emailForm: FormGroup;
  hasExistingConfig = false;
  isSaving = false;
  isTesting = false;
  successMessage = '';
  errorMessage = '';

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private snackBar: MatSnackBar
  ) {
    this.emailForm = this.fb.group({
      smtp_server: ['', Validators.required],
      smtp_port: [587, Validators.required],
      smtp_username: ['', Validators.required],
      smtp_password: [''],
      from_email: ['', [Validators.required, Validators.email]],
      from_name: ['Architecture Decisions'],
      use_tls: [true],
      enabled: [true]
    });
  }

  ngOnInit(): void {
    this.loadEmailConfig();
  }

  loadEmailConfig(): void {
    // Load system-wide email config (domain = 'system')
    this.http.get<EmailConfig>('/api/admin/email/system').subscribe({
      next: (config) => {
        if (config) {
          this.hasExistingConfig = true;
          this.emailForm.patchValue({
            smtp_server: config.smtp_server,
            smtp_port: config.smtp_port,
            smtp_username: config.smtp_username,
            from_email: config.from_email,
            from_name: config.from_name,
            use_tls: config.use_tls,
            enabled: config.enabled
          });
        }
      },
      error: () => {
        // No config exists yet
      }
    });
  }

  saveEmailConfig(): void {
    if (this.emailForm.invalid) return;

    this.isSaving = true;
    this.successMessage = '';
    this.errorMessage = '';

    const config = {
      ...this.emailForm.value,
      domain: 'system'  // System-wide config
    };

    this.http.post<EmailConfig>('/api/admin/email/system', config).subscribe({
      next: () => {
        this.isSaving = false;
        this.hasExistingConfig = true;
        this.successMessage = 'Email configuration saved successfully!';
        setTimeout(() => this.successMessage = '', 5000);
      },
      error: (err) => {
        this.isSaving = false;
        this.errorMessage = err.error?.error || 'Failed to save email configuration';
      }
    });
  }

  testEmail(): void {
    this.isTesting = true;
    this.successMessage = '';
    this.errorMessage = '';

    this.http.post<{ message: string }>('/api/admin/email/system/test', {}).subscribe({
      next: (response) => {
        this.isTesting = false;
        this.successMessage = response.message || 'Test email sent successfully!';
        setTimeout(() => this.successMessage = '', 5000);
      },
      error: (err) => {
        this.isTesting = false;
        this.errorMessage = err.error?.error || 'Failed to send test email';
      }
    });
  }
}
