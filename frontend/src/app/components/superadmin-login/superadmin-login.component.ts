import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-superadmin-login',
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
    MatProgressSpinnerModule
  ],
  template: `
    <div class="login-container">
      <mat-card class="login-card">
        <mat-card-header>
          <mat-card-title>
            <mat-icon>admin_panel_settings</mat-icon>
            Super Admin
          </mat-card-title>
          <mat-card-subtitle>System Administration Login</mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          @if (error) {
            <div class="error-message">{{ error }}</div>
          }

          <form [formGroup]="loginForm" (ngSubmit)="login()">
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

          <p class="hint-text">
            Default credentials: admin / changeme
          </p>
        </mat-card-content>

        <mat-card-actions>
          <a mat-button routerLink="/">
            <mat-icon>arrow_back</mat-icon>
            Back to Home
          </a>
        </mat-card-actions>
      </mat-card>
    </div>
  `,
  styles: [`
    .login-container {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: linear-gradient(135deg, #1a237e 0%, #311b92 100%);
      padding: 20px;
    }

    .login-card {
      width: 100%;
      max-width: 400px;
      padding: 24px;
    }

    mat-card-header {
      margin-bottom: 24px;
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

    mat-card-actions {
      display: flex;
      justify-content: center;
      padding: 16px;
    }
  `]
})
export class SuperadminLoginComponent {
  loginForm: FormGroup;
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

  login(): void {
    if (this.loginForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { username, password } = this.loginForm.value;

    this.http.post('/auth/local', { username, password }, { responseType: 'text' }).subscribe({
      next: () => {
        this.authService.loadCurrentUser();
        this.router.navigate(['/superadmin/dashboard']);
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Invalid username or password';
      }
    });
  }
}
