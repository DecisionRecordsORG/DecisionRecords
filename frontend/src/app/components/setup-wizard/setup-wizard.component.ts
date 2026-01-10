import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatStepperModule } from '@angular/material/stepper';

interface SetupResponse {
  message: string;
  tenant: {
    domain: string;
    name: string;
  };
  admin: {
    email: string;
  };
  next_step: string;
  error?: string;
}

@Component({
  selector: 'app-setup-wizard',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    ReactiveFormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatStepperModule
  ],
  template: `
    <div class="setup-container">
      <mat-card class="setup-card">
        <mat-card-header>
          <mat-card-title>
            <mat-icon>rocket_launch</mat-icon>
            Set Up Your Instance
          </mat-card-title>
          <mat-card-subtitle>Configure your Decision Records instance in a few easy steps</mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          <!-- Success State -->
          <div class="success-state" *ngIf="setupComplete">
            <mat-icon class="success-icon">check_circle</mat-icon>
            <h2>Setup Complete!</h2>
            <p>Your Decision Records instance is ready to use.</p>
            <div class="setup-summary">
              <p><strong>Organization:</strong> {{ organizationName }}</p>
              <p><strong>Domain:</strong> {{ domain }}</p>
              <p><strong>Admin Email:</strong> {{ adminEmail }}</p>
            </div>
            <button mat-raised-button class="primary-button" (click)="goToLogin()">
              <mat-icon>login</mat-icon>
              Sign In Now
            </button>
          </div>

          <!-- Setup Form -->
          <form [formGroup]="setupForm" (ngSubmit)="onSubmit()" *ngIf="!setupComplete">
            <mat-stepper linear #stepper>
              <!-- Step 1: Organization -->
              <mat-step [stepControl]="orgFormGroup">
                <ng-template matStepLabel>Organization</ng-template>
                <div class="step-content">
                  <p class="step-description">Enter your organization details</p>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Organization Name</mat-label>
                    <input matInput formControlName="organizationName" placeholder="Acme Corporation">
                    <mat-hint>The name of your company or team</mat-hint>
                    <mat-error *ngIf="setupForm.get('organizationName')?.hasError('required')">
                      Organization name is required
                    </mat-error>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Domain</mat-label>
                    <input matInput formControlName="domain" placeholder="acme.com">
                    <mat-hint>Your company domain (e.g., acme.com)</mat-hint>
                    <mat-error *ngIf="setupForm.get('domain')?.hasError('required')">
                      Domain is required
                    </mat-error>
                  </mat-form-field>

                  <div class="step-actions">
                    <button mat-raised-button class="primary-button" matStepperNext
                            [disabled]="!setupForm.get('organizationName')?.valid || !setupForm.get('domain')?.valid">
                      Next
                      <mat-icon>arrow_forward</mat-icon>
                    </button>
                  </div>
                </div>
              </mat-step>

              <!-- Step 2: Admin Account -->
              <mat-step [stepControl]="adminFormGroup">
                <ng-template matStepLabel>Admin Account</ng-template>
                <div class="step-content">
                  <p class="step-description">Create your administrator account</p>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Admin Name</mat-label>
                    <input matInput formControlName="adminName" placeholder="John Doe">
                    <mat-hint>Your full name (optional)</mat-hint>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Admin Email</mat-label>
                    <input matInput type="email" formControlName="adminEmail" placeholder="john@acme.com">
                    <mat-hint>You'll use this email to sign in</mat-hint>
                    <mat-error *ngIf="setupForm.get('adminEmail')?.hasError('required')">
                      Email is required
                    </mat-error>
                    <mat-error *ngIf="setupForm.get('adminEmail')?.hasError('email')">
                      Please enter a valid email address
                    </mat-error>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Password</mat-label>
                    <input matInput [type]="hidePassword ? 'password' : 'text'" formControlName="adminPassword">
                    <button mat-icon-button matSuffix type="button" (click)="hidePassword = !hidePassword">
                      <mat-icon>{{ hidePassword ? 'visibility_off' : 'visibility' }}</mat-icon>
                    </button>
                    <mat-hint>At least 8 characters</mat-hint>
                    <mat-error *ngIf="setupForm.get('adminPassword')?.hasError('required')">
                      Password is required
                    </mat-error>
                    <mat-error *ngIf="setupForm.get('adminPassword')?.hasError('minlength')">
                      Password must be at least 8 characters
                    </mat-error>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Confirm Password</mat-label>
                    <input matInput [type]="hideConfirmPassword ? 'password' : 'text'" formControlName="confirmPassword">
                    <button mat-icon-button matSuffix type="button" (click)="hideConfirmPassword = !hideConfirmPassword">
                      <mat-icon>{{ hideConfirmPassword ? 'visibility_off' : 'visibility' }}</mat-icon>
                    </button>
                    <mat-error *ngIf="setupForm.get('confirmPassword')?.hasError('required')">
                      Please confirm your password
                    </mat-error>
                    <mat-error *ngIf="setupForm.get('confirmPassword')?.hasError('passwordMismatch')">
                      Passwords do not match
                    </mat-error>
                  </mat-form-field>

                  <div class="step-actions">
                    <button mat-button matStepperPrevious type="button">
                      <mat-icon>arrow_back</mat-icon>
                      Back
                    </button>
                    <button mat-raised-button class="primary-button" matStepperNext
                            [disabled]="!setupForm.get('adminEmail')?.valid || !setupForm.get('adminPassword')?.valid || !setupForm.get('confirmPassword')?.valid">
                      Next
                      <mat-icon>arrow_forward</mat-icon>
                    </button>
                  </div>
                </div>
              </mat-step>

              <!-- Step 3: Review & Complete -->
              <mat-step>
                <ng-template matStepLabel>Complete Setup</ng-template>
                <div class="step-content">
                  <p class="step-description">Review your settings and complete setup</p>

                  <div class="review-section">
                    <h3>Organization</h3>
                    <p><strong>Name:</strong> {{ setupForm.get('organizationName')?.value }}</p>
                    <p><strong>Domain:</strong> {{ setupForm.get('domain')?.value }}</p>
                  </div>

                  <div class="review-section">
                    <h3>Administrator</h3>
                    <p><strong>Name:</strong> {{ setupForm.get('adminName')?.value || '(Not provided)' }}</p>
                    <p><strong>Email:</strong> {{ setupForm.get('adminEmail')?.value }}</p>
                  </div>

                  <div class="error-message" *ngIf="errorMessage">
                    <mat-icon>error</mat-icon>
                    {{ errorMessage }}
                  </div>

                  <div class="step-actions">
                    <button mat-button matStepperPrevious type="button" [disabled]="isSubmitting">
                      <mat-icon>arrow_back</mat-icon>
                      Back
                    </button>
                    <button mat-raised-button class="primary-button" type="submit"
                            [disabled]="!setupForm.valid || isSubmitting">
                      <mat-spinner *ngIf="isSubmitting" diameter="20"></mat-spinner>
                      <ng-container *ngIf="!isSubmitting">
                        <mat-icon>check</mat-icon>
                        Complete Setup
                      </ng-container>
                    </button>
                  </div>
                </div>
              </mat-step>
            </mat-stepper>
          </form>
        </mat-card-content>
      </mat-card>

      <div class="back-link">
        <a routerLink="/">
          <mat-icon>arrow_back</mat-icon>
          Back to Home
        </a>
      </div>
    </div>
  `,
  styles: [`
    .setup-container {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px 20px;
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #1e40af 100%);
    }

    .setup-card {
      max-width: 600px;
      width: 100%;
      border-radius: 16px !important;
    }

    mat-card-header {
      padding: 24px 24px 0;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 12px;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 1.5rem;
      color: #1e293b;
    }

    mat-card-title mat-icon {
      color: #3b82f6;
      font-size: 32px;
      width: 32px;
      height: 32px;
    }

    mat-card-subtitle {
      font-family: 'Inter', sans-serif;
      margin-top: 8px !important;
    }

    mat-card-content {
      padding: 24px;
    }

    .step-content {
      padding: 24px 0;
    }

    .step-description {
      font-family: 'Inter', sans-serif;
      color: #64748b;
      margin-bottom: 24px;
    }

    .full-width {
      width: 100%;
      margin-bottom: 16px;
    }

    .step-actions {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      margin-top: 24px;
    }

    .primary-button {
      background: #3b82f6 !important;
      color: white !important;
      border-radius: 8px !important;
      font-weight: 500 !important;
      text-transform: none !important;
      letter-spacing: 0 !important;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .primary-button:hover:not(:disabled) {
      background: #2563eb !important;
    }

    .primary-button:disabled {
      background: #94a3b8 !important;
    }

    .primary-button mat-spinner {
      margin-right: 8px;
    }

    ::ng-deep .primary-button mat-spinner circle {
      stroke: white !important;
    }

    .review-section {
      background: #f8fafc;
      padding: 16px;
      border-radius: 8px;
      margin-bottom: 16px;
    }

    .review-section h3 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 0.9rem;
      font-weight: 600;
      color: #64748b;
      margin: 0 0 8px 0;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .review-section p {
      font-family: 'Inter', sans-serif;
      margin: 4px 0;
      color: #1e293b;
    }

    .error-message {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      background: #fef2f2;
      border: 1px solid #fee2e2;
      border-radius: 8px;
      color: #dc2626;
      font-family: 'Inter', sans-serif;
      margin-bottom: 16px;
    }

    .error-message mat-icon {
      color: #dc2626;
    }

    .success-state {
      text-align: center;
      padding: 40px 20px;
    }

    .success-icon {
      font-size: 72px;
      width: 72px;
      height: 72px;
      color: #22c55e;
      margin-bottom: 16px;
    }

    .success-state h2 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      color: #1e293b;
      margin-bottom: 8px;
    }

    .success-state p {
      font-family: 'Inter', sans-serif;
      color: #64748b;
    }

    .setup-summary {
      background: #f8fafc;
      padding: 16px 24px;
      border-radius: 8px;
      margin: 24px 0;
      text-align: left;
    }

    .setup-summary p {
      margin: 8px 0;
    }

    .back-link {
      margin-top: 24px;
    }

    .back-link a {
      display: flex;
      align-items: center;
      gap: 8px;
      color: white;
      text-decoration: none;
      font-family: 'Inter', sans-serif;
      opacity: 0.9;
      transition: opacity 0.2s;
    }

    .back-link a:hover {
      opacity: 1;
    }

    .back-link mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    /* Stepper styling */
    ::ng-deep .mat-step-header .mat-step-icon {
      background-color: #3b82f6;
    }

    ::ng-deep .mat-step-header .mat-step-icon-selected {
      background-color: #3b82f6;
    }

    @media (max-width: 600px) {
      .setup-container {
        padding: 20px;
      }

      .step-actions {
        flex-direction: column;
      }

      .step-actions button {
        width: 100%;
      }
    }
  `]
})
export class SetupWizardComponent {
  private router = inject(Router);
  private http = inject(HttpClient);
  private fb = inject(FormBuilder);

  setupForm: FormGroup;
  orgFormGroup: FormGroup;
  adminFormGroup: FormGroup;

  hidePassword = true;
  hideConfirmPassword = true;
  isSubmitting = false;
  setupComplete = false;
  errorMessage = '';

  // Values for success display
  organizationName = '';
  domain = '';
  adminEmail = '';

  constructor() {
    this.setupForm = this.fb.group({
      organizationName: ['', Validators.required],
      domain: ['', Validators.required],
      adminName: [''],
      adminEmail: ['', [Validators.required, Validators.email]],
      adminPassword: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required]
    });

    // Add password match validator
    this.setupForm.get('confirmPassword')?.valueChanges.subscribe(() => {
      this.validatePasswordMatch();
    });
    this.setupForm.get('adminPassword')?.valueChanges.subscribe(() => {
      this.validatePasswordMatch();
    });

    // Create step form groups for validation
    this.orgFormGroup = this.fb.group({
      organizationName: this.setupForm.get('organizationName'),
      domain: this.setupForm.get('domain')
    });

    this.adminFormGroup = this.fb.group({
      adminName: this.setupForm.get('adminName'),
      adminEmail: this.setupForm.get('adminEmail'),
      adminPassword: this.setupForm.get('adminPassword'),
      confirmPassword: this.setupForm.get('confirmPassword')
    });
  }

  private validatePasswordMatch() {
    const password = this.setupForm.get('adminPassword')?.value;
    const confirmPassword = this.setupForm.get('confirmPassword')?.value;

    if (confirmPassword && password !== confirmPassword) {
      this.setupForm.get('confirmPassword')?.setErrors({ passwordMismatch: true });
    } else if (confirmPassword) {
      const errors = this.setupForm.get('confirmPassword')?.errors;
      if (errors) {
        delete errors['passwordMismatch'];
        if (Object.keys(errors).length === 0) {
          this.setupForm.get('confirmPassword')?.setErrors(null);
        }
      }
    }
  }

  onSubmit() {
    if (!this.setupForm.valid) {
      return;
    }

    this.isSubmitting = true;
    this.errorMessage = '';

    const payload = {
      organization_name: this.setupForm.get('organizationName')?.value,
      domain: this.setupForm.get('domain')?.value,
      admin_name: this.setupForm.get('adminName')?.value,
      admin_email: this.setupForm.get('adminEmail')?.value,
      admin_password: this.setupForm.get('adminPassword')?.value
    };

    this.http.post<SetupResponse>('/api/setup/initialize', payload).subscribe({
      next: (response) => {
        this.isSubmitting = false;
        this.setupComplete = true;
        this.organizationName = response.tenant.name;
        this.domain = response.tenant.domain;
        this.adminEmail = response.admin.email;
      },
      error: (error) => {
        this.isSubmitting = false;
        this.errorMessage = error.error?.error || 'Setup failed. Please try again.';
      }
    });
  }

  goToLogin() {
    this.router.navigate(['/', this.domain, 'login']);
  }
}
