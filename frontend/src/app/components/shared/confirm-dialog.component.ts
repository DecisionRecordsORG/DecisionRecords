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
    <h2 mat-dialog-title>
      <mat-icon [color]="data.isDanger ? 'warn' : 'primary'">
        {{ data.isDanger ? 'warning' : 'help_outline' }}
      </mat-icon>
      {{ data.title }}
    </h2>
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
      <button mat-button (click)="cancel()">
        {{ data.cancelText || 'Cancel' }}
      </button>
      <button mat-raised-button
              [color]="data.isDanger ? 'warn' : 'primary'"
              (click)="confirm()"
              [disabled]="data.showInput && data.inputRequired && !inputValue?.trim()">
        {{ data.confirmText || 'Confirm' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    h2 {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    mat-dialog-content p {
      font-size: 16px;
      line-height: 1.5;
    }

    .full-width {
      width: 100%;
      margin-top: 16px;
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
