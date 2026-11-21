import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialog, MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';

export type InquirySource = 'contact' | 'sponsorship' | 'feedback';

export interface Inquiry {
  id: number;
  source: InquirySource;
  name: string | null;
  email: string | null;
  organisation: string | null;
  area_of_interest: string | null;
  message: string | null;
  team_focus: string | null;
  team_size: string | null;
  team_size_label: string | null;
  contact_consent: boolean | null;
  user_id: number | null;
  tenant_domain: string | null;
  created_at: string | null;
  email_sent: boolean;
  handled: boolean;
  handled_at: string | null;
  handled_by: string | null;
  redacted: boolean;
  redacted_at: string | null;
}

export interface InquiryListResponse {
  total: number;
  limit: number;
  offset: number;
  unhandled_total: number;
  items: Inquiry[];
}

export interface TeamSizeCount {
  code: string | null;
  label: string;
  count: number;
}

export interface InterestSummary {
  tenants: {
    total: number;
    with_team_focus: number;
    by_team_size: TeamSizeCount[];
  };
  inquiries: {
    total: number;
    unhandled: number;
    not_emailed: number;
    by_source: { source: InquirySource; count: number }[];
    by_team_size: TeamSizeCount[];
  };
  team_focus_answers: { text: string; tenants: number; inquiries: number }[];
}

export const INQUIRY_SOURCE_LABELS: Record<InquirySource, string> = {
  contact: 'Contact form',
  sponsorship: 'Get in touch',
  feedback: 'Feedback'
};

export function inquirySourceLabel(source: string): string {
  return INQUIRY_SOURCE_LABELS[source as InquirySource] || source;
}

/** The start of a message for the table, cut at a word where possible. */
export function messagePreview(message: string | null, maxLength = 90): string {
  const text = (message || '').replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  const cut = text.slice(0, maxLength);
  const lastSpace = cut.lastIndexOf(' ');
  return (lastSpace > maxLength * 0.6 ? cut.slice(0, lastSpace) : cut) + '...';
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** "2 tenants, 1 inquiry" for a team focus answer. */
export function answerOrigin(answer: { tenants: number; inquiries: number }): string {
  const parts: string[] = [];
  if (answer.tenants > 0) parts.push(plural(answer.tenants, 'tenant', 'tenants'));
  if (answer.inquiries > 0) parts.push(plural(answer.inquiries, 'inquiry', 'inquiries'));
  return parts.join(', ');
}

export interface InquiryDetailResult {
  action: 'toggle-handled' | 'delete';
}

@Component({
  selector: 'app-inquiry-detail-dialog',
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule, MatIconModule],
  template: `
    <h2 mat-dialog-title data-testid="inquiry-detail-title">
      <mat-icon>mail</mat-icon>
      {{ sourceLabel }}
    </h2>
    <mat-dialog-content data-testid="inquiry-detail">
      @if (!inquiry.email_sent) {
        <p class="notice warning" data-testid="inquiry-detail-not-emailed">
          <mat-icon>mark_email_unread</mat-icon>
          <span>This message was never emailed. It is only stored here.</span>
        </p>
      }
      @if (inquiry.redacted) {
        <p class="notice" data-testid="inquiry-detail-redacted">
          <mat-icon>person_off</mat-icon>
          <span>The sender deleted their account. Their name, email address and message were removed.</span>
        </p>
      }

      <dl class="fields">
        <dt>Received</dt>
        <dd>{{ inquiry.created_at | date:'medium' }}</dd>

        <dt>Name</dt>
        <dd data-testid="inquiry-detail-name">{{ inquiry.name || 'Not given' }}</dd>

        <dt>Email</dt>
        <dd data-testid="inquiry-detail-email">
          @if (inquiry.email) {
            <a [href]="'mailto:' + inquiry.email">{{ inquiry.email }}</a>
          } @else {
            Not given
          }
        </dd>

        @if (inquiry.source === 'sponsorship' || inquiry.organisation) {
          <dt>Organisation</dt>
          <dd>{{ inquiry.organisation || 'Not given' }}</dd>
        }

        @if (inquiry.source === 'sponsorship' || inquiry.area_of_interest) {
          <dt>Area of interest</dt>
          <dd>{{ inquiry.area_of_interest || 'Not given' }}</dd>
        }

        <dt>Team makes decisions about</dt>
        <dd data-testid="inquiry-detail-team-focus">{{ inquiry.team_focus || 'Not given' }}</dd>

        @if (inquiry.team_size_label) {
          <dt>Team size</dt>
          <dd>{{ inquiry.team_size_label }}</dd>
        }

        @if (inquiry.tenant_domain) {
          <dt>Signed in from</dt>
          <dd>{{ inquiry.tenant_domain }}</dd>
        }

        @if (inquiry.source === 'feedback') {
          <dt>May we reply</dt>
          <dd>{{ inquiry.contact_consent ? 'Yes' : 'No' }}</dd>
        }

        <dt>Status</dt>
        <dd data-testid="inquiry-detail-status">
          @if (inquiry.handled) {
            Handled{{ inquiry.handled_by ? ' by ' + inquiry.handled_by : '' }}
            @if (inquiry.handled_at) {
              on {{ inquiry.handled_at | date:'medium' }}
            }
          } @else {
            Not handled
          }
        </dd>
      </dl>

      <h3>Message</h3>
      <p class="message" data-testid="inquiry-detail-message">{{ inquiry.message || 'No message' }}</p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button color="warn" data-testid="inquiry-detail-delete" (click)="close('delete')">
        Delete
      </button>
      <button mat-stroked-button data-testid="inquiry-detail-toggle-handled" (click)="close('toggle-handled')">
        {{ inquiry.handled ? 'Mark as not handled' : 'Mark as handled' }}
      </button>
      <button mat-flat-button color="primary" data-testid="inquiry-detail-close" (click)="close()">Close</button>
    </mat-dialog-actions>
  `,
  styles: [`
    h2 {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    mat-dialog-content {
      min-width: min(520px, 80vw);
    }

    .notice {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 10px 12px;
      border-radius: 6px;
      background: #f1f5f9;
      color: #334155;
      margin: 0 0 12px;
      font-size: 14px;
    }

    .notice.warning {
      background: #fff7ed;
      color: #9a3412;
    }

    .fields {
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 6px 16px;
      margin: 0 0 16px;
    }

    .fields dt {
      color: #64748b;
      font-size: 13px;
    }

    .fields dd {
      margin: 0;
      overflow-wrap: anywhere;
    }

    h3 {
      font-size: 14px;
      color: #64748b;
      margin: 0 0 6px;
    }

    .message {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #f8fafc;
      border-left: 3px solid #3f51b5;
      padding: 12px;
      margin: 0;
    }
  `]
})
export class InquiryDetailDialogComponent {
  inquiry: Inquiry;

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: { inquiry: Inquiry },
    private dialogRef: MatDialogRef<InquiryDetailDialogComponent, InquiryDetailResult | undefined>
  ) {
    this.inquiry = data.inquiry;
  }

  get sourceLabel(): string {
    return inquirySourceLabel(this.inquiry.source);
  }

  close(action?: InquiryDetailResult['action']): void {
    this.dialogRef.close(action ? { action } : undefined);
  }
}

@Component({
  selector: 'app-superadmin-inquiries',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatSelectModule,
    MatTooltipModule,
    MatProgressSpinnerModule,
    MatPaginatorModule,
    MatSnackBarModule,
    MatDialogModule,
    ConfirmDialogComponent,
    InquiryDetailDialogComponent
  ],
  template: `
    <div class="inquiries-container">
      <a routerLink="/superadmin/dashboard" class="back-link">
        <mat-icon>arrow_back</mat-icon>
        Dashboard
      </a>

      <h1>
        <mat-icon>inbox</mat-icon>
        Inquiries
        @if (unhandledTotal > 0) {
          <span class="badge" data-testid="inquiries-unhandled-count">{{ unhandledTotal }} not handled</span>
        }
      </h1>
      <p class="page-intro">
        Messages from the website contact form, the "Get in touch" dialog and the in-app feedback dialog.
        Each one is stored here before the notification email is sent, and deleted after 24 months.
      </p>

      <mat-card class="interest-card" data-testid="interest-summary">
        <mat-card-header>
          <mat-card-title>
            <mat-icon>insights</mat-icon>
            Interest
          </mat-card-title>
          <mat-card-subtitle>
            Who is interested and what kind of team they are, from tenant team profiles and stored inquiries
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          @if (isLoadingSummary) {
            <div class="loading">
              <mat-spinner diameter="32"></mat-spinner>
              <span>Loading summary...</span>
            </div>
          } @else if (!summary) {
            <p class="empty-text" data-testid="interest-summary-error">The summary could not be loaded.</p>
          } @else {
            <div class="summary-grid">
              <section data-testid="interest-tenants-by-size">
                <h3>Tenants by team size</h3>
                <p class="section-note">{{ summary.tenants.total }} in total</p>
                <ul class="count-list">
                  @for (row of summary.tenants.by_team_size; track row.label) {
                    <li>
                      <span>{{ row.label }}</span>
                      <strong>{{ row.count }}</strong>
                    </li>
                  }
                </ul>
              </section>

              <section data-testid="interest-inquiries-by-size">
                <h3>Inquiries by team size</h3>
                <p class="section-note">{{ summary.inquiries.total }} in total</p>
                <ul class="count-list">
                  @for (row of summary.inquiries.by_team_size; track row.label) {
                    <li>
                      <span>{{ row.label }}</span>
                      <strong>{{ row.count }}</strong>
                    </li>
                  }
                </ul>
              </section>

              <section data-testid="interest-inquiries-by-source">
                <h3>Inquiries by form</h3>
                <p class="section-note">{{ summary.inquiries.unhandled }} not handled</p>
                <ul class="count-list">
                  @for (row of summary.inquiries.by_source; track row.source) {
                    <li>
                      <span>{{ sourceLabel(row.source) }}</span>
                      <strong>{{ row.count }}</strong>
                    </li>
                  }
                </ul>
              </section>
            </div>

            <section class="answers" data-testid="interest-team-focus">
              <h3>What teams make decisions about</h3>
              @if (summary.team_focus_answers.length === 0) {
                <p class="empty-text">No answers yet.</p>
              } @else {
                <p class="section-note">Each distinct answer, as it was typed.</p>
                <ul class="answer-list">
                  @for (answer of summary.team_focus_answers; track answer.text) {
                    <li>
                      <span class="answer-text">{{ answer.text }}</span>
                      <span class="answer-origin">{{ origin(answer) }}</span>
                    </li>
                  }
                </ul>
              }
            </section>
          }
        </mat-card-content>
      </mat-card>

      <mat-card>
        <mat-card-header>
          <mat-card-title>
            <mat-icon>mail</mat-icon>
            Messages
          </mat-card-title>
        </mat-card-header>
        <mat-card-content>
          @if (summary && summary.inquiries.not_emailed > 0) {
            <p class="not-emailed-banner" data-testid="inquiries-not-emailed-banner">
              <mat-icon>mark_email_unread</mat-icon>
              <span>
                {{ summary.inquiries.not_emailed === 1
                    ? '1 message was never emailed'
                    : summary.inquiries.not_emailed + ' messages were never emailed' }}
                because email was not set up or the send failed. They are marked "Not emailed" below and are only stored here.
              </span>
            </p>
          }

          <div class="filters">
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Form</mat-label>
              <mat-select data-testid="inquiries-filter-source" [(ngModel)]="filter.source" (selectionChange)="applyFilters()">
                <mat-option value="">All forms</mat-option>
                <mat-option value="contact">Contact form</mat-option>
                <mat-option value="sponsorship">Get in touch</mat-option>
                <mat-option value="feedback">Feedback</mat-option>
              </mat-select>
            </mat-form-field>
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Status</mat-label>
              <mat-select data-testid="inquiries-filter-handled" [(ngModel)]="filter.handled" (selectionChange)="applyFilters()">
                <mat-option value="">All</mat-option>
                <mat-option value="false">Not handled</mat-option>
                <mat-option value="true">Handled</mat-option>
              </mat-select>
            </mat-form-field>
          </div>

          @if (isLoading) {
            <div class="loading">
              <mat-spinner diameter="40"></mat-spinner>
              <span>Loading inquiries...</span>
            </div>
          } @else if (loadError) {
            <div class="empty-state" data-testid="inquiries-error">
              <mat-icon>error_outline</mat-icon>
              <p>{{ loadError }}</p>
            </div>
          } @else if (inquiries.length === 0) {
            <div class="empty-state" data-testid="inquiries-empty">
              <mat-icon>inbox</mat-icon>
              <p>{{ hasFilters ? 'No inquiries match these filters' : 'No inquiries yet' }}</p>
            </div>
          } @else {
            <div class="table-wrapper">
              <table mat-table [dataSource]="inquiries" class="full-width" data-testid="inquiries-table">
                <ng-container matColumnDef="source">
                  <th mat-header-cell *matHeaderCellDef>Form</th>
                  <td mat-cell *matCellDef="let inquiry">
                    <span class="chip" [class]="'source-' + inquiry.source">{{ sourceLabel(inquiry.source) }}</span>
                  </td>
                </ng-container>

                <ng-container matColumnDef="created_at">
                  <th mat-header-cell *matHeaderCellDef>When</th>
                  <td mat-cell *matCellDef="let inquiry" class="nowrap">{{ inquiry.created_at | date:'short' }}</td>
                </ng-container>

                <ng-container matColumnDef="who">
                  <th mat-header-cell *matHeaderCellDef>Who</th>
                  <td mat-cell *matCellDef="let inquiry">
                    @if (inquiry.redacted) {
                      <span class="muted">Personal details removed</span>
                    } @else {
                      <div class="who">
                        <strong>{{ inquiry.name || 'No name' }}</strong>
                        <span class="muted">{{ inquiry.email }}</span>
                      </div>
                    }
                  </td>
                </ng-container>

                <ng-container matColumnDef="organisation">
                  <th mat-header-cell *matHeaderCellDef>Organisation</th>
                  <td mat-cell *matCellDef="let inquiry">{{ inquiry.organisation || inquiry.tenant_domain || '' }}</td>
                </ng-container>

                <ng-container matColumnDef="team_focus">
                  <th mat-header-cell *matHeaderCellDef>Team focus</th>
                  <td mat-cell *matCellDef="let inquiry" class="wrap">{{ inquiry.team_focus || '' }}</td>
                </ng-container>

                <ng-container matColumnDef="message">
                  <th mat-header-cell *matHeaderCellDef>Message</th>
                  <td mat-cell *matCellDef="let inquiry" class="wrap">{{ preview(inquiry.message) }}</td>
                </ng-container>

                <ng-container matColumnDef="status">
                  <th mat-header-cell *matHeaderCellDef>Status</th>
                  <td mat-cell *matCellDef="let inquiry">
                    <div class="status-chips">
                      @if (inquiry.handled) {
                        <span class="chip handled" data-testid="inquiry-handled-chip">Handled</span>
                      } @else {
                        <span class="chip open">Not handled</span>
                      }
                      @if (!inquiry.email_sent) {
                        <span class="chip not-emailed" data-testid="inquiry-not-emailed-chip"
                              matTooltip="No notification email was sent for this message. It is only stored here.">
                          <mat-icon>mark_email_unread</mat-icon>
                          Not emailed
                        </span>
                      }
                    </div>
                  </td>
                </ng-container>

                <ng-container matColumnDef="actions">
                  <th mat-header-cell *matHeaderCellDef>Actions</th>
                  <td mat-cell *matCellDef="let inquiry" class="nowrap">
                    <button mat-icon-button data-testid="inquiry-view" (click)="openDetail(inquiry)"
                            matTooltip="View message" aria-label="View message">
                      <mat-icon>visibility</mat-icon>
                    </button>
                    <button mat-icon-button data-testid="inquiry-toggle-handled" (click)="toggleHandled(inquiry)"
                            [disabled]="busyId === inquiry.id"
                            [matTooltip]="inquiry.handled ? 'Mark as not handled' : 'Mark as handled'"
                            [attr.aria-label]="inquiry.handled ? 'Mark as not handled' : 'Mark as handled'">
                      <mat-icon>{{ inquiry.handled ? 'undo' : 'check_circle' }}</mat-icon>
                    </button>
                    <button mat-icon-button color="warn" data-testid="inquiry-delete" (click)="deleteInquiry(inquiry)"
                            [disabled]="busyId === inquiry.id" matTooltip="Delete" aria-label="Delete">
                      <mat-icon>delete</mat-icon>
                    </button>
                  </td>
                </ng-container>

                <tr mat-header-row *matHeaderRowDef="columns"></tr>
                <tr mat-row *matRowDef="let row; columns: columns;" data-testid="inquiry-row"
                    [class.is-handled]="row.handled"></tr>
              </table>
            </div>

            <mat-paginator
              [length]="total"
              [pageSize]="pageSize"
              [pageIndex]="page"
              [pageSizeOptions]="[25, 50, 100]"
              (page)="onPage($event)">
            </mat-paginator>
          }
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .inquiries-container {
      padding: 24px;
      max-width: 1200px;
      margin: 0 auto;
    }

    .back-link {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      color: #3f51b5;
      text-decoration: none;
      font-size: 14px;
      margin-bottom: 8px;
    }

    .back-link mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    h1 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }

    .badge {
      background: #fff3e0;
      color: #e65100;
      border-radius: 12px;
      padding: 2px 10px;
      font-size: 13px;
      font-weight: 500;
    }

    .page-intro {
      color: #666;
      margin: 0 0 24px;
      max-width: 760px;
    }

    mat-card {
      margin-bottom: 24px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 24px;
      padding-top: 16px;
    }

    h3 {
      margin: 0 0 4px;
      font-size: 14px;
      color: #333;
    }

    .section-note {
      margin: 0 0 8px;
      font-size: 12px;
      color: #888;
    }

    .count-list,
    .answer-list {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .count-list li {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 4px 0;
      border-bottom: 1px solid #f0f0f0;
      font-size: 14px;
    }

    .count-list strong {
      font-variant-numeric: tabular-nums;
    }

    .answers {
      margin-top: 24px;
    }

    .answer-list li {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 6px 0;
      border-bottom: 1px solid #f0f0f0;
      font-size: 14px;
    }

    .answer-text {
      overflow-wrap: anywhere;
    }

    .answer-origin {
      color: #888;
      white-space: nowrap;
      font-size: 12px;
    }

    .empty-text {
      color: #888;
      margin: 0;
    }

    .not-emailed-banner {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      background: #fff7ed;
      color: #9a3412;
      border-radius: 6px;
      padding: 10px 12px;
      margin: 16px 0 0;
      font-size: 14px;
    }

    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin: 16px 0;
    }

    .filters mat-form-field {
      min-width: 200px;
    }

    .loading {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 24px 0;
      color: #666;
    }

    .empty-state {
      text-align: center;
      padding: 40px 0;
      color: #888;
    }

    .empty-state mat-icon {
      font-size: 40px;
      width: 40px;
      height: 40px;
    }

    .table-wrapper {
      overflow-x: auto;
    }

    .full-width {
      width: 100%;
    }

    td.wrap {
      max-width: 260px;
      overflow-wrap: anywhere;
    }

    .nowrap {
      white-space: nowrap;
    }

    .who {
      display: flex;
      flex-direction: column;
    }

    .muted {
      color: #888;
      font-size: 13px;
    }

    tr.is-handled td {
      color: #777;
    }

    .status-chips {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
      padding: 6px 0;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      border-radius: 12px;
      padding: 2px 10px;
      font-size: 12px;
      font-weight: 500;
      white-space: nowrap;
      background: #eceff1;
      color: #37474f;
    }

    .chip mat-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
    }

    .chip.source-contact {
      background: #e3f2fd;
      color: #0d47a1;
    }

    .chip.source-sponsorship {
      background: #f3e5f5;
      color: #6a1b9a;
    }

    .chip.source-feedback {
      background: #e0f2f1;
      color: #00695c;
    }

    .chip.handled {
      background: #e8f5e9;
      color: #2e7d32;
    }

    .chip.open {
      background: #fff3e0;
      color: #e65100;
    }

    .chip.not-emailed {
      background: #ffebee;
      color: #c62828;
    }
  `]
})
export class SuperadminInquiriesComponent implements OnInit {
  inquiries: Inquiry[] = [];
  summary: InterestSummary | null = null;
  total = 0;
  unhandledTotal = 0;
  page = 0;
  pageSize = 50;
  filter: { source: string; handled: string } = { source: '', handled: '' };
  isLoading = true;
  isLoadingSummary = true;
  loadError = '';
  busyId: number | null = null;

  columns = ['source', 'created_at', 'who', 'organisation', 'team_focus', 'message', 'status', 'actions'];

  constructor(
    private http: HttpClient,
    private dialog: MatDialog,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.loadInquiries();
    this.loadSummary();
  }

  get hasFilters(): boolean {
    return !!this.filter.source || !!this.filter.handled;
  }

  sourceLabel(source: string): string {
    return inquirySourceLabel(source);
  }

  preview(message: string | null): string {
    return messagePreview(message);
  }

  origin(answer: { tenants: number; inquiries: number }): string {
    return answerOrigin(answer);
  }

  loadInquiries(): void {
    this.isLoading = true;
    this.loadError = '';
    const offset = this.page * this.pageSize;
    let url = `/api/superadmin/inquiries?limit=${this.pageSize}&offset=${offset}`;
    if (this.filter.source) {
      url += `&source=${encodeURIComponent(this.filter.source)}`;
    }
    if (this.filter.handled) {
      url += `&handled=${encodeURIComponent(this.filter.handled)}`;
    }

    this.http.get<InquiryListResponse>(url).subscribe({
      next: (response) => {
        this.inquiries = response.items;
        this.total = response.total;
        this.unhandledTotal = response.unhandled_total;
        this.isLoading = false;
        // Deleting the last row of the last page leaves an empty page behind
        if (this.inquiries.length === 0 && this.page > 0 && this.total > 0) {
          this.page = Math.max(0, Math.ceil(this.total / this.pageSize) - 1);
          this.loadInquiries();
        }
      },
      error: (err) => {
        this.inquiries = [];
        this.total = 0;
        this.isLoading = false;
        this.loadError = err.error?.error || 'The inquiries could not be loaded. Please try again.';
      }
    });
  }

  loadSummary(): void {
    this.isLoadingSummary = true;
    this.http.get<InterestSummary>('/api/superadmin/inquiries/summary').subscribe({
      next: (summary) => {
        this.summary = summary;
        this.isLoadingSummary = false;
      },
      error: () => {
        this.summary = null;
        this.isLoadingSummary = false;
      }
    });
  }

  applyFilters(): void {
    this.page = 0;
    this.loadInquiries();
  }

  onPage(event: PageEvent): void {
    this.page = event.pageIndex;
    this.pageSize = event.pageSize;
    this.loadInquiries();
  }

  openDetail(inquiry: Inquiry): void {
    const dialogRef = this.dialog.open(InquiryDetailDialogComponent, {
      width: '640px',
      maxWidth: '95vw',
      data: { inquiry }
    });

    dialogRef.afterClosed().subscribe((result?: InquiryDetailResult) => {
      if (result?.action === 'toggle-handled') {
        this.toggleHandled(inquiry);
      } else if (result?.action === 'delete') {
        this.deleteInquiry(inquiry);
      }
    });
  }

  toggleHandled(inquiry: Inquiry): void {
    const handled = !inquiry.handled;
    this.busyId = inquiry.id;
    this.http.put<{ message: string; inquiry: Inquiry }>(
      `/api/superadmin/inquiries/${inquiry.id}/handled`, { handled }
    ).subscribe({
      next: (response) => {
        this.busyId = null;
        this.snackBar.open(response.message, 'Close', { duration: 3000 });
        this.loadInquiries();
        this.loadSummary();
      },
      error: (err) => {
        this.busyId = null;
        this.snackBar.open(err.error?.error || 'Could not update the inquiry. Please try again.', 'Close', { duration: 5000 });
      }
    });
  }

  deleteInquiry(inquiry: Inquiry): void {
    const from = inquiry.name || inquiry.email || inquiry.organisation;
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete inquiry',
        message: from
          ? `Delete the message from ${from}? This cannot be undone.`
          : 'Delete this message? This cannot be undone.',
        confirmText: 'Delete',
        cancelText: 'Cancel',
        isDanger: true
      }
    });

    dialogRef.afterClosed().subscribe((confirmed) => {
      if (!confirmed) return;
      this.busyId = inquiry.id;
      this.http.delete<{ message: string }>(`/api/superadmin/inquiries/${inquiry.id}`).subscribe({
        next: (response) => {
          this.busyId = null;
          this.snackBar.open(response.message, 'Close', { duration: 3000 });
          this.loadInquiries();
          this.loadSummary();
        },
        error: (err) => {
          this.busyId = null;
          this.snackBar.open(err.error?.error || 'Could not delete the inquiry. Please try again.', 'Close', { duration: 5000 });
        }
      });
    });
  }
}
