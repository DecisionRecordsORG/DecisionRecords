import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

export interface ConfirmDialogData {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDanger?: boolean;
  showInput?: boolean;
  inputLabel?: string;
  inputPlaceholder?: string;
  inputRequired?: boolean;
}

export interface ConfirmDialogResult {
  confirmed: boolean;
  inputValue?: string;
}

@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule
  ],
  template: `
    <div class="dialog-header" [class.danger]="data.isDanger">
      <mat-icon>{{ data.isDanger ? 'warning' : 'help_outline' }}</mat-icon>
      <h2 mat-dialog-title>{{ data.title }}</h2>
    </div>
    <mat-dialog-content>
      <p>{{ data.message }}</p>
      @if (data.showInput) {
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>{{ data.inputLabel || 'Input' }}</mat-label>
          <textarea matInput
                    [(ngModel)]="inputValue"
                    [placeholder]="data.inputPlaceholder || ''"
                    rows="3"></textarea>
        </mat-form-field>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-stroked-button (click)="cancel()">
        {{ data.cancelText || 'Cancel' }}
      </button>
      <button mat-flat-button
              [color]="data.isDanger ? 'warn' : 'primary'"
              (click)="confirm()"
              [disabled]="data.showInput && data.inputRequired && !inputValue.trim()">
        {{ data.confirmText || 'Confirm' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 20px 24px 0;
    }

    .dialog-header mat-icon {
      font-size: 28px;
      width: 28px;
      height: 28px;
      color: #3b82f6;
    }

    .dialog-header.danger mat-icon {
      color: #ef4444;
    }

    .dialog-header h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
      color: #1a1a1a;
      font-family: 'Plus Jakarta Sans', sans-serif;
    }

    mat-dialog-content {
      padding: 16px 24px 24px !important;
    }

    mat-dialog-content p {
      margin: 0;
      font-size: 15px;
      line-height: 1.6;
      color: #374151;
    }

    .full-width {
      width: 100%;
      margin-top: 16px;
    }

    mat-dialog-actions {
      padding: 16px 24px !important;
      gap: 12px;
      border-top: 1px solid #e5e7eb;
      background: #f9fafb;
    }
  `]
})
export class ConfirmDialogComponent {
  inputValue = '';

  constructor(
    public dialogRef: MatDialogRef<ConfirmDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: ConfirmDialogData
  ) {}

  cancel(): void {
    this.dialogRef.close(false);
  }

  confirm(): void {
    if (this.data.showInput) {
      this.dialogRef.close({ confirmed: true, inputValue: this.inputValue });
    } else {
      this.dialogRef.close(true);
    }
  }
}
