import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDividerModule } from '@angular/material/divider';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../../services/auth.service';
import { SSOConfig } from '../../models/decision.model';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatDividerModule,
    MatProgressSpinnerModule
  ],
  template: `
    <div class="login-container">
      <mat-card class="login-card">
        <mat-card-header>
          <mat-card-title>
            <mat-icon>architecture</mat-icon>
            Architecture Decisions
          </mat-card-title>
          <mat-card-subtitle>Sign in to continue</mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          @if (error) {
            <div class="error-message">{{ error }}</div>
          }

          <!-- SSO Login Options -->
          @if (ssoConfigs.length > 0) {
            <div class="sso-section">
              <p class="section-title">Sign in with SSO</p>
              @for (config of ssoConfigs; track config.id) {
                <a [href]="'/auth/sso/' + config.id" mat-raised-button color="primary" class="sso-button">
                  <mat-icon>login</mat-icon>
                  {{ config.provider_name }}
                </a>
              }
            </div>
            <mat-divider></mat-divider>
          }

          <!-- Local Admin Login -->
          <div class="admin-section">
            <p class="section-title">
              <mat-icon>admin_panel_settings</mat-icon>
              Administrator Login
            </p>
            <form [formGroup]="loginForm" (ngSubmit)="onSubmit()">
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Username</mat-label>
                <input matInput formControlName="username" placeholder="admin">
                <mat-icon matPrefix>person</mat-icon>
              </mat-form-field>

              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Password</mat-label>
                <input matInput [type]="hidePassword ? 'password' : 'text'" formControlName="password">
                <mat-icon matPrefix>lock</mat-icon>
                <button mat-icon-button matSuffix type="button" (click)="hidePassword = !hidePassword">
                  <mat-icon>{{ hidePassword ? 'visibility_off' : 'visibility' }}</mat-icon>
                </button>
              </mat-form-field>

              <button mat-raised-button color="primary" type="submit"
                      [disabled]="loginForm.invalid || isLoading" class="full-width">
                @if (isLoading) {
                  <mat-spinner diameter="20"></mat-spinner>
                } @else {
                  <mat-icon>login</mat-icon>
                  Sign In
                }
              </button>
            </form>

            @if (ssoConfigs.length === 0) {
              <p class="hint-text">
                Default credentials: admin / changeme
              </p>
            }
          </div>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .login-container {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      padding: 20px;
    }

    .login-card {
      width: 100%;
      max-width: 400px;
      padding: 20px;
    }

    mat-card-header {
      margin-bottom: 20px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 24px;
    }

    .error-message {
      background-color: #ffebee;
      color: #c62828;
      padding: 12px;
      border-radius: 4px;
      margin-bottom: 16px;
    }

    .section-title {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #666;
      font-size: 14px;
      margin-bottom: 16px;
    }

    .sso-section {
      margin-bottom: 20px;
    }

    .sso-button {
      width: 100%;
      margin-bottom: 8px;
    }

    .admin-section {
      margin-top: 20px;
    }

    .full-width {
      width: 100%;
    }

    mat-form-field {
      margin-bottom: 8px;
    }

    .hint-text {
      font-size: 12px;
      color: #888;
      text-align: center;
      margin-top: 16px;
    }

    mat-divider {
      margin: 20px 0;
    }
  `]
})
export class LoginComponent implements OnInit {
  loginForm: FormGroup;
  ssoConfigs: SSOConfig[] = [];
  hidePassword = true;
  isLoading = false;
  error = '';

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private router: Router,
    private authService: AuthService
  ) {
    this.loginForm = this.fb.group({
      username: ['', Validators.required],
      password: ['', Validators.required]
    });
  }

  ngOnInit(): void {
    this.loadSSOConfigs();
  }

  loadSSOConfigs(): void {
    this.http.get<SSOConfig[]>('/api/auth/sso-configs').subscribe({
      next: (configs) => this.ssoConfigs = configs,
      error: () => this.ssoConfigs = []
    });
  }

  onSubmit(): void {
    if (this.loginForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { username, password } = this.loginForm.value;

    this.http.post('/auth/local', { username, password }, { responseType: 'text' }).subscribe({
      next: () => {
        this.authService.loadCurrentUser();
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Invalid username or password';
      }
    });
  }
}
