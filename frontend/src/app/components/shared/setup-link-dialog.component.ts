import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AdminService } from '../../services/admin.service';

export interface SetupLinkDialogData {
  userId: number;
  userName: string;
  userEmail: string;
  setupUrl: string;
  expiresInHours: number;
}

@Component({
  selector: 'app-setup-link-dialog',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatSnackBarModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon>link</mat-icon>
      Setup Link Generated
    </h2>
    <mat-dialog-content>
      <p class="success-message">
        <mat-icon class="success-icon">check_circle</mat-icon>
        Account approved for <strong>{{ data.userName }}</strong> ({{ data.userEmail }})
      </p>

      <p class="instruction">
        Share this setup link with the user so they can set up their login credentials.
        The link expires in <strong>{{ data.expiresInHours }} hours</strong>.
      </p>

      <div class="link-container">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Setup Link</mat-label>
          <input matInput [value]="data.setupUrl" readonly #linkInput>
        </mat-form-field>
        <button mat-icon-button color="primary" (click)="copyLink()" matTooltip="Copy to clipboard">
          <mat-icon>content_copy</mat-icon>
        </button>
      </div>

      <div class="action-buttons">
        <button mat-raised-button color="primary" (click)="sendEmail()" [disabled]="sendingEmail">
          @if (sendingEmail) {
            <mat-spinner diameter="20"></mat-spinner>
          } @else {
            <mat-icon>send</mat-icon>
          }
          Send Email
        </button>
        <button mat-raised-button (click)="copyLink()">
          <mat-icon>content_copy</mat-icon>
          Copy Link
        </button>
      </div>

      @if (emailSent) {
        <p class="email-sent-message">
          <mat-icon>check_circle</mat-icon>
          Email sent successfully to {{ data.userEmail }}
        </p>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button [mat-dialog-close]="true">Done</button>
    </mat-dialog-actions>
  `,
  styles: [`
    h2 {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .success-message {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px;
      background: #e8f5e9;
      border-radius: 8px;
      color: #2e7d32;
      margin-bottom: 16px;
    }

    .success-icon {
      color: #2e7d32;
    }

    .instruction {
      color: #666;
      margin-bottom: 16px;
    }

    .link-container {
      display: flex;
      gap: 8px;
      align-items: flex-start;
    }

    .full-width {
      flex: 1;
    }

    .action-buttons {
      display: flex;
      gap: 8px;
      margin-top: 16px;
    }

    .action-buttons button mat-icon {
      margin-right: 4px;
    }

    .email-sent-message {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 16px;
      padding: 12px;
      background: #e3f2fd;
      border-radius: 8px;
      color: #1565c0;
    }

    .email-sent-message mat-icon {
      color: #1565c0;
    }

    mat-dialog-content {
      min-width: 400px;
    }

    mat-spinner {
      display: inline-block;
      margin-right: 8px;
    }
  `]
})
export class SetupLinkDialogComponent {
  sendingEmail = false;
  emailSent = false;

  constructor(
    public dialogRef: MatDialogRef<SetupLinkDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: SetupLinkDialogData,
    private snackBar: MatSnackBar,
    private adminService: AdminService
  ) {}

  copyLink(): void {
    navigator.clipboard.writeText(this.data.setupUrl).then(() => {
      this.snackBar.open('Setup link copied to clipboard!', 'Close', { duration: 3000 });
    });
  }

  sendEmail(): void {
    if (!this.data.userId || this.sendingEmail) return;

    this.sendingEmail = true;
    this.adminService.sendSetupEmail(this.data.userId).subscribe({
      next: (response) => {
        this.sendingEmail = false;
        this.emailSent = true;
        this.snackBar.open(`Setup email sent to ${this.data.userEmail}`, 'Close', { duration: 3000 });
      },
      error: (err) => {
        this.sendingEmail = false;
        const errorMsg = err.error?.error || 'Failed to send email';
        this.snackBar.open(errorMsg, 'Close', { duration: 5000 });

        // If there's a setup URL in the error response, it means token was generated but email failed
        if (err.error?.setup_url) {
          this.data.setupUrl = err.error.setup_url;
        }
      }
    });
  }
}
