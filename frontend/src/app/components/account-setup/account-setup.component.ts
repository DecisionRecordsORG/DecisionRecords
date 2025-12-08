import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-account-setup',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    ReactiveFormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatInputModule,
    MatSnackBarModule
  ],
  template: `
    <div class="setup-container">
      <mat-card class="setup-card">
        @if (isLoading) {
          <div class="loading-container">
            <mat-spinner diameter="40"></mat-spinner>
            <p>Validating setup link...</p>
          </div>
        } @else if (error) {
          <div class="error-state">
            <mat-icon class="error-icon">error</mat-icon>
            <h2>{{ errorTitle }}</h2>
            <p>{{ error }}</p>
            @if (redirectUrl) {
              <button mat-raised-button color="primary" [routerLink]="redirectUrl">
                {{ redirectLabel }}
              </button>
            } @else {
              <button mat-raised-button color="primary" routerLink="/">
                Go to Home
              </button>
            }
          </div>
        } @else if (user) {
          <mat-card-header>
            <mat-card-title>
              <mat-icon>person_add</mat-icon>
              Set Up Your Account
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <p class="welcome-message">
              Welcome, <strong>{{ user.name }}</strong>!
            </p>
            <p class="instruction">
              Your account has been approved. Please set up your login credentials to continue.
            </p>

            <div class="setup-options">
              <div class="option-card passkey-option" (click)="setupPasskey()">
                <mat-icon>fingerprint</mat-icon>
                <h3>Use Passkey</h3>
                <p>Sign in with your device's biometrics (fingerprint, face) or security key</p>
                <span class="recommended">Recommended</span>
              </div>

              <div class="option-card password-option" (click)="showPasswordForm = true" [class.active]="showPasswordForm">
                <mat-icon>password</mat-icon>
                <h3>Use Password</h3>
                <p>Create a traditional password for your account</p>
              </div>
            </div>

            @if (showPasswordForm) {
              <form [formGroup]="passwordForm" (ngSubmit)="setupPassword()" class="password-form">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Password</mat-label>
                  <input matInput type="password" formControlName="password">
                  <mat-hint>At least 8 characters with uppercase, lowercase, and number</mat-hint>
                  @if (passwordForm.get('password')?.hasError('minlength')) {
                    <mat-error>Password must be at least 8 characters</mat-error>
                  }
                </mat-form-field>

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Confirm Password</mat-label>
                  <input matInput type="password" formControlName="confirmPassword">
                  @if (passwordForm.hasError('mismatch')) {
                    <mat-error>Passwords do not match</mat-error>
                  }
                </mat-form-field>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="passwordForm.invalid || settingUp">
                  @if (settingUp) {
                    <mat-spinner diameter="20"></mat-spinner>
                  } @else {
                    Set Password
                  }
                </button>
              </form>
            }
          </mat-card-content>
        }
      </mat-card>
    </div>
  `,
  styles: [`
    .setup-container {
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 24px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }

    .setup-card {
      max-width: 500px;
      width: 100%;
      padding: 32px;
    }

    mat-card-header {
      margin-bottom: 24px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 24px;
    }

    .loading-container {
      text-align: center;
      padding: 48px;
    }

    .loading-container p {
      margin-top: 16px;
      color: #666;
    }

    .error-state {
      text-align: center;
      padding: 24px;
    }

    .error-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #f44336;
    }

    .error-state h2 {
      margin: 16px 0 8px;
      color: #333;
    }

    .error-state p {
      color: #666;
      margin-bottom: 24px;
    }

    .welcome-message {
      font-size: 18px;
      margin-bottom: 8px;
    }

    .instruction {
      color: #666;
      margin-bottom: 24px;
    }

    .setup-options {
      display: grid;
      gap: 16px;
      margin-bottom: 24px;
    }

    .option-card {
      border: 2px solid #ddd;
      border-radius: 12px;
      padding: 20px;
      cursor: pointer;
      transition: all 0.2s;
      position: relative;
    }

    .option-card:hover {
      border-color: #3f51b5;
      background: #f5f7ff;
    }

    .option-card.active {
      border-color: #3f51b5;
      background: #f5f7ff;
    }

    .option-card mat-icon {
      font-size: 36px;
      width: 36px;
      height: 36px;
      color: #3f51b5;
      margin-bottom: 8px;
    }

    .option-card h3 {
      margin: 0 0 8px;
      font-size: 18px;
    }

    .option-card p {
      margin: 0;
      color: #666;
      font-size: 14px;
    }

    .recommended {
      position: absolute;
      top: 12px;
      right: 12px;
      background: #4caf50;
      color: white;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 500;
    }

    .password-form {
      margin-top: 16px;
      padding: 16px;
      background: #f5f5f5;
      border-radius: 8px;
    }

    .full-width {
      width: 100%;
      margin-bottom: 8px;
    }

    .password-form button {
      margin-top: 16px;
    }
  `]
})
export class AccountSetupComponent implements OnInit {
  isLoading = true;
  error: string | null = null;
  errorTitle = 'Setup Error';
  redirectUrl: string | null = null;
  redirectLabel = 'Continue';
  user: { id: number; email: string; name: string; sso_domain: string } | null = null;
  token: string | null = null;
  showPasswordForm = false;
  settingUp = false;
  passwordForm: FormGroup;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient,
    private authService: AuthService,
    private snackBar: MatSnackBar,
    private fb: FormBuilder
  ) {
    this.passwordForm = this.fb.group({
      password: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required]
    }, { validators: this.passwordMatchValidator });
  }

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token');
    if (!this.token) {
      this.error = 'No setup token provided. Please use the link sent to you by your administrator.';
      this.errorTitle = 'Missing Token';
      this.isLoading = false;
      return;
    }

    this.validateToken();
  }

  validateToken(): void {
    this.http.post<any>('/api/auth/setup-token/validate', { token: this.token }).subscribe({
      next: (response) => {
        if (response.valid) {
          this.user = response.user;
          this.isLoading = false;
        } else {
          this.handleError(response);
        }
      },
      error: (err) => {
        this.handleError(err.error);
      }
    });
  }

  handleError(response: any): void {
    this.isLoading = false;
    this.error = response.error || 'An error occurred';

    if (response.expired) {
      this.errorTitle = 'Link Expired';
      this.error = 'This setup link has expired. Please contact your administrator for a new link.';
    } else if (response.used) {
      this.errorTitle = 'Link Already Used';
      this.error = 'This setup link has already been used. Please contact your administrator if you need a new link.';
    } else if (response.already_setup) {
      this.errorTitle = 'Already Set Up';
      this.error = 'Your account is already set up. Please log in instead.';
      this.redirectUrl = response.redirect;
      this.redirectLabel = 'Go to Login';
    }
  }

  passwordMatchValidator(group: FormGroup): { mismatch: boolean } | null {
    const password = group.get('password')?.value;
    const confirmPassword = group.get('confirmPassword')?.value;
    return password === confirmPassword ? null : { mismatch: true };
  }

  async setupPasskey(): Promise<void> {
    if (!this.user || this.settingUp) return;

    this.settingUp = true;

    try {
      // Check if WebAuthn is supported
      if (!window.PublicKeyCredential) {
        this.snackBar.open('Passkeys are not supported in this browser', 'Close', { duration: 5000 });
        this.settingUp = false;
        return;
      }

      // Get registration options from server
      const optionsResponse = await this.http.post<any>('/api/webauthn/register/options', {
        device_name: 'Setup Device'
      }).toPromise();

      // Convert base64url strings to ArrayBuffer
      const options = {
        ...optionsResponse,
        challenge: this.base64urlToBuffer(optionsResponse.challenge),
        user: {
          ...optionsResponse.user,
          id: this.base64urlToBuffer(optionsResponse.user.id)
        },
        excludeCredentials: (optionsResponse.excludeCredentials || []).map((cred: any) => ({
          ...cred,
          id: this.base64urlToBuffer(cred.id)
        }))
      };

      // Create credential
      const credential = await navigator.credentials.create({
        publicKey: options
      }) as PublicKeyCredential;

      const response = credential.response as AuthenticatorAttestationResponse;

      // Register with server - wrap credential data to match backend expectation
      const result = await this.http.post<any>('/api/webauthn/register/verify', {
        credential: {
          id: credential.id,
          rawId: this.bufferToBase64url(credential.rawId),
          type: credential.type,
          response: {
            clientDataJSON: this.bufferToBase64url(response.clientDataJSON),
            attestationObject: this.bufferToBase64url(response.attestationObject)
          }
        },
        device_name: 'Setup Device'
      }).toPromise();

      // Check for successful registration (backend returns user object on success)
      if (result.user || result.message === 'Registration successful') {
        // Mark token as used
        if (this.token) {
          await this.http.post('/api/auth/setup-token/use', { token: this.token }).toPromise();
        }

        this.snackBar.open('Passkey registered successfully! Redirecting to login...', 'Close', { duration: 3000 });

        // Refresh auth state
        this.authService.loadCurrentUser().subscribe();

        // Redirect to tenant login page
        setTimeout(() => {
          this.router.navigate([`/${this.user!.sso_domain}`]);
        }, 2000);
      }
    } catch (error: any) {
      console.error('Passkey setup error:', error);
      this.snackBar.open(error.message || 'Failed to set up passkey', 'Close', { duration: 5000 });
    } finally {
      this.settingUp = false;
    }
  }

  setupPassword(): void {
    if (this.passwordForm.invalid || !this.user || this.settingUp || !this.token) return;

    this.settingUp = true;
    const password = this.passwordForm.get('password')?.value;

    // Use the setup-password endpoint which accepts token for auth
    this.http.post<any>('/api/auth/setup-password', { token: this.token, password }).subscribe({
      next: (response) => {
        this.snackBar.open('Password set successfully! Redirecting to login...', 'Close', { duration: 3000 });

        // Refresh auth state
        this.authService.loadCurrentUser().subscribe();

        // Redirect to tenant login page
        setTimeout(() => {
          this.router.navigate([`/${this.user!.sso_domain}`]);
        }, 2000);
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to set password', 'Close', { duration: 5000 });
        this.settingUp = false;
      }
    });
  }

  private base64urlToBuffer(base64url: string): ArrayBuffer {
    const padding = '='.repeat((4 - base64url.length % 4) % 4);
    const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/') + padding;
    const binary = atob(base64);
    const buffer = new ArrayBuffer(binary.length);
    const view = new Uint8Array(buffer);
    for (let i = 0; i < binary.length; i++) {
      view[i] = binary.charCodeAt(i);
    }
    return buffer;
  }

  private bufferToBase64url(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const base64 = btoa(binary);
    return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
  }
}
