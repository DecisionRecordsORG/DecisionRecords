import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatRadioModule } from '@angular/material/radio';

export interface RoleRequestDialogData {
  currentRole?: string;
}

export interface RoleRequestDialogResult {
  role: string;
  reason: string;
}

@Component({
  selector: 'app-role-request-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatRadioModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon>admin_panel_settings</mat-icon>
      Request shared administration responsibilities
    </h2>
    <mat-dialog-content>
      <p class="dialog-subtext">(visible to current admins and logged for transparency)</p>

      <div class="role-selection">
        <h3>Select the role you are requesting:</h3>

        <mat-radio-group [(ngModel)]="selectedRole" class="role-radio-group">
          <mat-radio-button value="steward" class="role-option">
            <div class="role-option-content">
              <div class="role-header">
                <strong>Steward</strong>
                <mat-icon class="role-icon steward-icon">shield</mat-icon>
              </div>
              <p class="role-description">Shared governance role - can approve requests and invite users</p>
            </div>
          </mat-radio-button>

          <mat-radio-button value="admin" class="role-option">
            <div class="role-option-content">
              <div class="role-header">
                <strong>Admin</strong>
                <mat-icon class="role-icon admin-icon">admin_panel_settings</mat-icon>
              </div>
              <p class="role-description">Full administrator - can manage all tenant settings</p>
            </div>
          </mat-radio-button>
        </mat-radio-group>
      </div>

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Reason / Justification</mat-label>
        <textarea matInput
                  [(ngModel)]="reason"
                  placeholder="Please explain why you need this role..."
                  rows="4"></textarea>
        <mat-hint>This will be visible to all current admins and stewards</mat-hint>
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="cancel()">
        Cancel
      </button>
      <button mat-raised-button
              color="primary"
              (click)="submit()"
              [disabled]="!selectedRole || !reason.trim()">
        <mat-icon>send</mat-icon>
        Submit Request
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    h2 {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #3f51b5;
    }

    .dialog-subtext {
      color: #666;
      font-size: 13px;
      margin: -8px 0 16px 0;
      font-style: italic;
    }

    .role-selection {
      margin-bottom: 24px;
    }

    .role-selection h3 {
      font-size: 15px;
      font-weight: 500;
      margin: 0 0 12px 0;
      color: #333;
    }

    .role-radio-group {
      display: flex;
      flex-direction: column;
      gap: 12px;
      width: 100%;
    }

    .role-option {
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 16px;
      margin: 0;
      width: 100%;
    }

    .role-option.mat-mdc-radio-checked {
      border-color: #3f51b5;
      background-color: #f5f7ff;
    }

    .role-option-content {
      width: 100%;
      margin-left: 8px;
    }

    .role-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 4px;
    }

    .role-header strong {
      font-size: 16px;
      color: #333;
    }

    .role-icon {
      font-size: 24px;
      width: 24px;
      height: 24px;
    }

    .steward-icon {
      color: #7b1fa2;
    }

    .admin-icon {
      color: #1565c0;
    }

    .role-description {
      margin: 0;
      font-size: 14px;
      color: #666;
      line-height: 1.4;
    }

    .full-width {
      width: 100%;
    }

    mat-dialog-content {
      padding-top: 8px;
      min-width: 500px;
    }

    mat-dialog-actions button {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    @media (max-width: 600px) {
      mat-dialog-content {
        min-width: auto;
      }
    }
  `]
})
export class RoleRequestDialogComponent {
  selectedRole = '';
  reason = '';

  constructor(
    public dialogRef: MatDialogRef<RoleRequestDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: RoleRequestDialogData
  ) {}

  cancel(): void {
    this.dialogRef.close(null);
  }

  submit(): void {
    if (this.selectedRole && this.reason.trim()) {
      this.dialogRef.close({
        role: this.selectedRole,
        reason: this.reason.trim()
      });
    }
  }
}
