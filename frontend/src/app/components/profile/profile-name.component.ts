import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';
import { User } from '../../models/decision.model';

export const NAME_MAX_LENGTH = 100;

/**
 * A person's own name on the profile page, with a way to correct it.
 *
 * Only the name can be changed here. The email address is the account's
 * identity and decides which organisation the account belongs to; changing
 * it is a request to support.
 */
@Component({
  selector: 'app-profile-name',
  standalone: true,
  imports: [CommonModule, FormsModule, MatButtonModule, MatFormFieldModule, MatIconModule, MatInputModule, MatTooltipModule],
  template: `
    @if (!editing) {
      <span class="name-line">
        <span data-testid="profile-name">{{ user?.name || 'Not set' }}</span>
        <button mat-icon-button class="edit-name" type="button" (click)="startEditing()"
                aria-label="Edit your name" matTooltip="Edit your name" data-testid="profile-name-edit">
          <mat-icon>edit</mat-icon>
        </button>
      </span>
    } @else {
      <form class="name-form" (ngSubmit)="save()" data-testid="profile-name-form">
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>First name</mat-label>
          <input matInput name="firstName" [(ngModel)]="firstName" [maxlength]="maxLength"
                 autocomplete="given-name" data-testid="profile-first-name">
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Last name</mat-label>
          <input matInput name="lastName" [(ngModel)]="lastName" [maxlength]="maxLength"
                 autocomplete="family-name" data-testid="profile-last-name">
        </mat-form-field>
        @if (error) {
          <p class="name-error" role="alert" data-testid="profile-name-error">{{ error }}</p>
        }
        <div class="name-actions">
          <button mat-button type="button" (click)="cancel()" [disabled]="saving" data-testid="profile-name-cancel">Cancel</button>
          <button mat-flat-button color="primary" type="submit" [disabled]="saving" data-testid="profile-name-save">
            {{ saving ? 'Saving' : 'Save' }}
          </button>
        </div>
      </form>
    }
  `,
  styles: [`
    .name-line { display: inline-flex; align-items: center; gap: 4px; }
    .edit-name { width: 32px; height: 32px; padding: 4px; }
    .edit-name mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .name-form { display: flex; flex-direction: column; gap: 8px; max-width: 320px; margin-top: 4px; }
    .name-actions { display: flex; justify-content: flex-end; gap: 8px; }
    .name-error { margin: 0; color: #c62828; font-size: 13px; }
  `]
})
export class ProfileNameComponent {
  @Input() user: User | null = null;
  /** The account as the server returned it after the change. */
  @Output() saved = new EventEmitter<User>();

  readonly maxLength = NAME_MAX_LENGTH;
  editing = false;
  saving = false;
  error: string | null = null;
  firstName = '';
  lastName = '';

  constructor(private http: HttpClient) {}

  startEditing(): void {
    const user = this.user;
    if (user?.first_name || user?.last_name) {
      this.firstName = user.first_name || '';
      this.lastName = user.last_name || '';
    } else {
      // An older account has one name field: split it at the first space
      const parts = (user?.name || '').trim().split(/\s+/);
      this.firstName = parts[0] || '';
      this.lastName = parts.slice(1).join(' ');
    }
    this.error = null;
    this.editing = true;
  }

  cancel(): void {
    this.editing = false;
    this.error = null;
  }

  save(): void {
    const firstName = this.firstName.trim();
    const lastName = this.lastName.trim();
    if (!firstName && !lastName) {
      this.error = 'Enter your name.';
      return;
    }
    this.saving = true;
    this.error = null;
    this.http.put<{ message: string; user: User }>('/api/user/profile', {
      first_name: firstName,
      last_name: lastName
    }).subscribe({
      next: (response) => {
        this.saving = false;
        this.editing = false;
        this.saved.emit(response.user);
      },
      error: (failure) => {
        this.saving = false;
        this.error = failure?.error?.error || 'Your name could not be saved. Try again.';
      }
    });
  }
}
