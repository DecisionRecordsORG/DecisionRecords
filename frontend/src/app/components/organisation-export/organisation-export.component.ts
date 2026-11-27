import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpErrorResponse, HttpResponse } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

export const ORGANISATION_EXPORT_URL = '/api/tenant/export';

/**
 * "Export organisation data" in Organisation settings: one ZIP file with the
 * organisation's decisions (JSON and Markdown), spaces, template, members and
 * audit log. The server decides who may export (administrators of this
 * organisation) and says why when it refuses; this card shows that message.
 */
@Component({
  selector: 'app-organisation-export',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatCardModule, MatIconModule, MatProgressSpinnerModule, MatSnackBarModule],
  template: `
    <mat-card class="config-card" data-testid="organisation-export-card">
      <mat-card-header>
        <mat-card-title>
          <mat-icon>download</mat-icon>
          Export organisation data
        </mat-card-title>
      </mat-card-header>
      <mat-card-content>
        <p data-testid="organisation-export-intro">
          Download one ZIP file with your organisation's decisions, as JSON and as one Markdown file per
          decision, with their history, comments and links. It also holds the spaces, the decision template,
          the list of members (name, email address, role, date joined) and the audit log.
          Only administrators can export.
        </p>
        <p class="export-left-out" data-testid="organisation-export-left-out">
          Not included: deleted decisions, removed comments, people's sign-in history, passwords, API keys,
          tokens and other secrets, and server logs. Each person can export their own data from their profile.
        </p>
        @if (error) {
          <p class="export-error" role="alert" data-testid="organisation-export-error">{{ error }}</p>
        }
      </mat-card-content>
      <mat-card-actions>
        <button mat-flat-button color="primary" (click)="download()" [disabled]="exporting"
                data-testid="organisation-export-button">
          @if (exporting) {
            <mat-spinner diameter="20"></mat-spinner>
            <span>Preparing export...</span>
          } @else {
            <mat-icon>download</mat-icon>
            <span>Download export (ZIP)</span>
          }
        </button>
      </mat-card-actions>
    </mat-card>
  `,
  styles: [`
    .export-left-out { font-size: 13px; color: #666; }
    .export-error { color: #c62828; }
    button mat-spinner { display: inline-block; margin-right: 8px; }
  `]
})
export class OrganisationExportComponent {
  exporting = false;
  error: string | null = null;

  constructor(private http: HttpClient, private snackBar: MatSnackBar) {}

  download(): void {
    this.exporting = true;
    this.error = null;
    this.http.post(ORGANISATION_EXPORT_URL, {}, { responseType: 'blob', observe: 'response' }).subscribe({
      next: (response) => {
        this.exporting = false;
        if (response.body) {
          this.save(response.body, OrganisationExportComponent.fileName(response));
        }
        this.snackBar.open('Export downloaded', 'Close', { duration: 3000 });
      },
      error: (failure: HttpErrorResponse) => {
        this.exporting = false;
        this.messageOf(failure).then(message => this.error = message);
      }
    });
  }

  /** The name the server gave the file, or a dated default. */
  static fileName(response: HttpResponse<Blob>): string {
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = /filename="([^"]+)"/.exec(disposition);
    return match ? match[1] : `decision-records-export-${new Date().toISOString().slice(0, 10)}.zip`;
  }

  /** Kept apart so tests can watch it without starting a real download. */
  save(blob: Blob, fileName: string): void {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.click();
    window.URL.revokeObjectURL(url);
  }

  private async messageOf(failure: HttpErrorResponse): Promise<string> {
    const fallback = 'The export could not be made. Try again later.';
    try {
      const body = failure.error instanceof Blob ? JSON.parse(await failure.error.text()) : failure.error;
      return (body && typeof body.error === 'string') ? body.error : fallback;
    } catch {
      return fallback;
    }
  }
}
