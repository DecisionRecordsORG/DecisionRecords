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
import { RouterModule } from '@angular/router';

interface SessionSettings {
  admin_session_timeout_hours: number;
  user_session_timeout_hours: number;
  defaults: {
    admin_session_timeout_hours: number;
    user_session_timeout_hours: number;
  };
}

@Component({
  selector: 'app-superadmin-settings',
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
    MatSnackBarModule
  ],
  template: `
    <div class="settings-container">
      <h1>
        <mat-icon>settings</mat-icon>
        System Settings
      </h1>

      <mat-card>
        <mat-card-header>
          <mat-card-title>
            <mat-icon>timer</mat-icon>
            Session Timeouts
          </mat-card-title>
          <mat-card-subtitle>
            Configure how long users stay logged in before requiring re-authentication
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          @if (loading) {
            <div class="loading">
              <mat-spinner diameter="40"></mat-spinner>
            </div>
          } @else {
            <form [formGroup]="sessionForm" (ngSubmit)="saveSettings()">
              <div class="form-section">
                <h3>Super Admin Session</h3>
                <p class="hint">For security, super admin sessions should have shorter timeouts</p>
                <mat-form-field appearance="outline">
                  <mat-label>Timeout (hours)</mat-label>
                  <input matInput type="number" formControlName="admin_session_timeout_hours" min="1" max="24">
                  <mat-hint>1-24 hours (default: {{ defaults.admin_session_timeout_hours }} hour)</mat-hint>
                </mat-form-field>
              </div>

              <div class="form-section">
                <h3>Regular User Session</h3>
                <p class="hint">For regular tenant users</p>
                <mat-form-field appearance="outline">
                  <mat-label>Timeout (hours)</mat-label>
                  <input matInput type="number" formControlName="user_session_timeout_hours" min="1" max="168">
                  <mat-hint>1-168 hours (default: {{ defaults.user_session_timeout_hours }} hours)</mat-hint>
                </mat-form-field>
              </div>

              <div class="actions">
                <button mat-raised-button color="primary" type="submit" [disabled]="saving || !sessionForm.valid">
                  <mat-spinner diameter="20" *ngIf="saving"></mat-spinner>
                  <mat-icon *ngIf="!saving">save</mat-icon>
                  <span *ngIf="!saving">Save Settings</span>
                </button>
                <button mat-button type="button" (click)="resetToDefaults()">
                  <mat-icon>restore</mat-icon>
                  Reset to Defaults
                </button>
              </div>
            </form>
          }
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .settings-container {
      max-width: 800px;
      margin: 0 auto;
      padding: 24px;
    }

    h1 {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
      color: #333;
    }

    h1 mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
    }

    mat-card {
      margin-bottom: 24px;
    }

    mat-card-header {
      margin-bottom: 16px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 40px;
    }

    .form-section {
      margin-bottom: 24px;
      padding: 16px;
      background: #f9f9f9;
      border-radius: 8px;
    }

    .form-section h3 {
      margin: 0 0 8px 0;
      color: #1976d2;
    }

    .form-section .hint {
      margin: 0 0 16px 0;
      color: #666;
      font-size: 14px;
    }

    mat-form-field {
      width: 200px;
    }

    .actions {
      display: flex;
      gap: 12px;
      margin-top: 24px;
    }

    .actions button {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .actions mat-spinner {
      margin-right: 8px;
    }
  `]
})
export class SuperadminSettingsComponent implements OnInit {
  sessionForm: FormGroup;
  loading = true;
  saving = false;
  defaults = {
    admin_session_timeout_hours: 1,
    user_session_timeout_hours: 8
  };

  constructor(
    private http: HttpClient,
    private fb: FormBuilder,
    private snackBar: MatSnackBar
  ) {
    this.sessionForm = this.fb.group({
      admin_session_timeout_hours: [1, [Validators.required, Validators.min(1), Validators.max(24)]],
      user_session_timeout_hours: [8, [Validators.required, Validators.min(1), Validators.max(168)]]
    });
  }

  ngOnInit() {
    this.loadSettings();
  }

  loadSettings() {
    this.loading = true;
    this.http.get<SessionSettings>('/api/admin/settings/session').subscribe({
      next: (settings) => {
        this.sessionForm.patchValue({
          admin_session_timeout_hours: settings.admin_session_timeout_hours,
          user_session_timeout_hours: settings.user_session_timeout_hours
        });
        this.defaults = settings.defaults;
        this.loading = false;
      },
      error: (error) => {
        this.snackBar.open('Failed to load settings', 'Close', { duration: 3000 });
        this.loading = false;
      }
    });
  }

  saveSettings() {
    if (!this.sessionForm.valid) return;

    this.saving = true;
    this.http.post('/api/admin/settings/session', this.sessionForm.value).subscribe({
      next: () => {
        this.snackBar.open('Settings saved successfully', 'Close', { duration: 3000 });
        this.saving = false;
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to save settings', 'Close', { duration: 3000 });
        this.saving = false;
      }
    });
  }

  resetToDefaults() {
    this.sessionForm.patchValue({
      admin_session_timeout_hours: this.defaults.admin_session_timeout_hours,
      user_session_timeout_hours: this.defaults.user_session_timeout_hours
    });
  }
}
