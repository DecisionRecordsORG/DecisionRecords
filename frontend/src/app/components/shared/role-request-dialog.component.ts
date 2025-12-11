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
      <mat-icon color="primary">admin_panel_settings</mat-icon>
      Request Elevated Role
    </h2>
    <mat-dialog-content>
      <p class="dialog-description">
        Request shared administration responsibilities. This request will be visible to current admins
        and logged for transparency.
      </p>

      <div class="role-selection">
        <label class="selection-label">Select the role you are requesting:</label>

        <mat-radio-group [(ngModel)]="selectedRole" class="role-radio-group">
          <div class="role-option" [class.selected]="selectedRole === 'steward'" (click)="selectedRole = 'steward'">
            <mat-radio-button value="steward">
              <div class="role-option-content">
                <div class="role-header">
                  <span class="role-name">Steward</span>
                  <mat-icon class="steward-icon">shield</mat-icon>
                </div>
                <p class="role-description">Shared governance role - can approve access requests and invite users</p>
              </div>
            </mat-radio-button>
          </div>

          <div class="role-option" [class.selected]="selectedRole === 'admin'" (click)="selectedRole = 'admin'">
            <mat-radio-button value="admin">
              <div class="role-option-content">
                <div class="role-header">
                  <span class="role-name">Administrator</span>
                  <mat-icon class="admin-icon">admin_panel_settings</mat-icon>
                </div>
                <p class="role-description">Full administrator - can manage all tenant settings and configurations</p>
              </div>
            </mat-radio-button>
          </div>
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
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button
              color="primary"
              (click)="submit()"
              [disabled]="!selectedRole || !reason.trim()">
        <mat-icon>send</mat-icon>
        Submit Request
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    :host {
      display: block;
    }

    h2[mat-dialog-title] {
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 0;
      padding: 16px 24px;
      font-size: 20px;
      font-weight: 500;
    }

    mat-dialog-content {
      padding: 0 24px 24px 24px;
      max-height: 65vh;
    }

    .dialog-description {
      color: #666;
      font-size: 14px;
      line-height: 1.5;
      margin: 0 0 20px 0;
    }

    .role-selection {
      margin-bottom: 20px;
    }

    .selection-label {
      display: block;
      font-size: 14px;
      font-weight: 500;
      color: #333;
      margin-bottom: 12px;
    }

    .role-radio-group {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .role-option {
      border: 2px solid #e0e0e0;
      border-radius: 8px;
      padding: 16px;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .role-option:hover {
      border-color: #bdbdbd;
      background-color: #fafafa;
    }

    .role-option.selected {
      border-color: #3f51b5;
      background-color: #f5f7ff;
    }

    .role-option mat-radio-button {
      width: 100%;
    }

    .role-option-content {
      padding-left: 8px;
    }

    .role-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 6px;
    }

    .role-name {
      font-size: 16px;
      font-weight: 500;
      color: #333;
    }

    .role-header mat-icon {
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
      font-size: 13px;
      color: #666;
      line-height: 1.4;
    }

    .full-width {
      width: 100%;
    }

    mat-dialog-actions {
      padding: 16px 24px;
      margin: 0;
    }

    mat-dialog-actions button {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    @media (max-width: 600px) {
      mat-dialog-content {
        min-width: auto;
      }

      .role-option {
        padding: 12px;
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
