import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';

export type RetentionCategory = 'accounts' | 'decisions' | 'tenants' | 'login_history' | 'inquiries';

export interface RetentionItem {
  id: number;
  label: string;
  due_at: string | null;
  counts?: { users: number; decisions: number; spaces: number; memberships: number };
}

export interface RetentionPreviewEntry {
  waiting: number;
  limit: number | null;
  would_hold: boolean;
  hold_reason: 'over_limit' | 'backlog' | null;
  oldest_due_at: string | null;
  cutoff: string | null;
  items: RetentionItem[];
  items_truncated: boolean;
  needs_review?: { id: number; label: string; status: string | null }[];
}

export interface RetentionCategoryResult {
  status: 'done' | 'held_back' | 'error';
  affected: number;
  waiting: number;
  limit: number | null;
  hold_reason: string | null;
  errors: { entity_id: number | null; error: string }[];
  error_count?: number;
}

export interface RetentionRun {
  id: number;
  trigger: string;
  started_by: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  categories: string[];
  results: Record<string, RetentionCategoryResult>;
  error: string | null;
}

export interface RetentionSettings {
  auto_run_enabled: boolean;
  auto_run_disabled_by_environment: boolean;
  auto_run_active: boolean;
  limits: { accounts: number; decisions: number; tenants: number };
  backlog_days: number;
}

export interface RetentionStatus {
  settings: RetentionSettings;
  automatic: {
    active: boolean;
    disabled_by: 'setting' | 'environment' | null;
    last_run: RetentionRun | null;
  };
  preview: Record<string, RetentionPreviewEntry>;
  held_back: string[];
  run_in_progress: RetentionRun | null;
  runs: RetentionRun[];
  categories: string[];
}

interface CategoryText {
  label: string;
  /** What a run does, for the confirm dialog: "Erase" or "Anonymise". */
  verb: string;
  one: string;
  many: string;
  rule: string;
}

export const RETENTION_CATEGORY_TEXT: Record<RetentionCategory, CategoryText> = {
  accounts: {
    label: 'Accounts to anonymise',
    verb: 'Anonymise',
    one: 'account',
    many: 'accounts',
    rule: 'Accounts whose owner asked for deletion more than 7 days ago'
  },
  decisions: {
    label: 'Deleted decisions to erase',
    verb: 'Erase',
    one: 'decision',
    many: 'decisions',
    rule: 'Decisions deleted more than 30 days ago'
  },
  tenants: {
    label: 'Deleted tenants to erase',
    verb: 'Erase',
    one: 'tenant',
    many: 'tenants',
    rule: 'Tenants deleted more than 30 days ago, with their users, decisions and settings'
  },
  login_history: {
    label: 'Login history to erase',
    verb: 'Erase',
    one: 'login history entry',
    many: 'login history entries',
    rule: 'Sign-in records older than 90 days'
  },
  inquiries: {
    label: 'Stored messages to erase',
    verb: 'Erase',
    one: 'stored message',
    many: 'stored messages',
    rule: 'Messages from the contact, get in touch and feedback forms older than 24 months'
  }
};

function categoryText(category: string): CategoryText {
  return RETENTION_CATEGORY_TEXT[category as RetentionCategory]
    || { label: category, verb: 'Erase', one: 'item', many: 'items', rule: '' };
}

export function retentionCategoryLabel(category: string): string {
  return categoryText(category).label;
}

/** "1 tenant", "3 accounts". */
export function retentionCount(category: string, count: number): string {
  const text = categoryText(category);
  return `${count} ${count === 1 ? text.one : text.many}`;
}

/** "Anonymised" for accounts, "Erased" for everything else. */
export function retentionDoneWord(category: string): string {
  return categoryText(category).verb === 'Anonymise' ? 'Anonymised' : 'Erased';
}

export function retentionTriggerLabel(run: { trigger: string; started_by: string | null }): string {
  if (run.trigger === 'automatic') return 'Automatic';
  if (run.trigger === 'cron') return 'Cron job';
  if (run.trigger === 'super_admin') return run.started_by ? `Super admin ${run.started_by}` : 'Super admin';
  return run.trigger;
}

export function retentionRunStatusLabel(status: string): string {
  switch (status) {
    case 'completed': return 'Finished';
    case 'held_back': return 'Finished, some held back';
    case 'completed_with_errors': return 'Finished with errors';
    case 'running': return 'Still running';
    case 'interrupted': return 'Stopped before it finished';
    default: return status;
  }
}

export function retentionHoldReason(reason: string | null, limit: number | null, backlogDays: number): string {
  if (reason === 'over_limit') {
    return `More are waiting than the limit of ${limit ?? 0} for one automatic run.`;
  }
  if (reason === 'backlog') {
    return `The oldest has been waiting more than ${backlogDays} ${backlogDays === 1 ? 'day' : 'days'}.`;
  }
  return '';
}

export function retentionDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '';
  if (ms < 1000) return `${ms} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;
}

@Component({
  selector: 'app-superadmin-retention',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDialogModule,
    ConfirmDialogComponent
  ],
  template: `
    <div class="retention-container">
      <a routerLink="/superadmin/dashboard" class="back-link">
        <mat-icon>arrow_back</mat-icon>
        Dashboard
      </a>

      <h1>
        <mat-icon>auto_delete</mat-icon>
        Data retention
        @if (status && status.held_back.length > 0) {
          <span class="badge" data-testid="retention-held-back-count">{{ status.held_back.length }} held back</span>
        }
      </h1>
      <p class="page-intro">
        Once a day the application anonymises accounts 7 days after their owner asked for deletion, erases
        deleted decisions and tenants after 30 days, login history after 90 days and stored messages after 24 months.
      </p>

      <p class="irreversible" data-testid="retention-irreversible">
        <mat-icon>warning</mat-icon>
        <span>Erasing cannot be undone. A database backup is the only way to get erased data back.</span>
      </p>

      @if (isLoading && !status) {
        <div class="loading" data-testid="retention-loading">
          <mat-spinner diameter="40"></mat-spinner>
          <span>Loading data retention...</span>
        </div>
      } @else if (loadError && !status) {
        <div class="empty-state" data-testid="retention-error">
          <mat-icon>error_outline</mat-icon>
          <p>{{ loadError }}</p>
        </div>
      } @else if (status) {
        @if (status.held_back.length > 0) {
          <p class="held-banner" data-testid="retention-held-banner">
            <mat-icon>pan_tool</mat-icon>
            <span>
              Held back: {{ heldBackNames }}. The automatic run did not touch
              {{ status.held_back.length === 1 ? 'this category' : 'these categories' }}.
              Check the list below, then run {{ status.held_back.length === 1 ? 'it' : 'each one' }} yourself.
            </span>
          </p>
        }

        @if (status.run_in_progress) {
          <p class="notice" data-testid="retention-in-progress">
            <mat-icon>hourglass_top</mat-icon>
            <span>A run started {{ status.run_in_progress.started_at | date:'medium' }} is still going.</span>
          </p>
        }

        <mat-card data-testid="retention-automatic">
          <mat-card-header>
            <mat-card-title>
              <mat-icon>schedule</mat-icon>
              Automatic run
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <p class="state-line">
              @if (status.automatic.active) {
                <span class="chip on" data-testid="retention-auto-state">On</span>
                <span>Runs once a day.</span>
              } @else {
                <span class="chip off" data-testid="retention-auto-state">Off</span>
                @if (status.automatic.disabled_by === 'environment') {
                  <span data-testid="retention-auto-reason">
                    Turned off by the RETENTION_AUTO_RUN environment variable. This page cannot change that.
                  </span>
                } @else {
                  <span data-testid="retention-auto-reason">Turned off here. Nothing is erased until someone runs it.</span>
                }
              }
            </p>
            <p class="muted" data-testid="retention-auto-last-run">
              @if (status.automatic.last_run) {
                Last automatic run: {{ status.automatic.last_run.started_at | date:'medium' }},
                {{ runStatus(status.automatic.last_run.status) | lowercase }}.
              } @else {
                No automatic run yet.
              }
            </p>
            <button mat-stroked-button data-testid="retention-auto-toggle"
                    [disabled]="isSavingAuto || status.settings.auto_run_disabled_by_environment"
                    (click)="toggleAutomatic()">
              {{ status.settings.auto_run_enabled ? 'Turn off the automatic run' : 'Turn on the automatic run' }}
            </button>
          </mat-card-content>
        </mat-card>

        <mat-card data-testid="retention-waiting">
          <mat-card-header>
            <mat-card-title>
              <mat-icon>pending_actions</mat-icon>
              Waiting now
            </mat-card-title>
            <mat-card-subtitle>What a run would anonymise or erase if it started now</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            @for (category of status.categories; track category) {
              @if (status.preview[category]; as entry) {
                <section class="category" [attr.data-testid]="'retention-category-' + category"
                         [class.is-held]="entry.would_hold">
                  <div class="category-head">
                    <div>
                      <h3>{{ label(category) }}</h3>
                      <p class="muted">{{ rule(category) }}</p>
                    </div>
                    <div class="numbers">
                      <span><strong [attr.data-testid]="'retention-waiting-' + category">{{ entry.waiting }}</strong> waiting</span>
                      <span class="muted" [attr.data-testid]="'retention-limit-' + category">
                        {{ entry.limit === null ? 'No limit' : 'Limit ' + entry.limit }}
                      </span>
                    </div>
                  </div>

                  <p class="state-line" [attr.data-testid]="'retention-state-' + category">
                    @if (entry.waiting === 0) {
                      <span class="chip">Nothing waiting</span>
                    } @else if (entry.would_hold) {
                      <span class="chip held">Held back</span>
                      <span>{{ holdReason(entry) }}</span>
                    } @else if (status.automatic.active) {
                      <span class="chip on">Next automatic run</span>
                      <span>Will be done by the next automatic run.</span>
                    } @else {
                      <span class="chip off">Waiting</span>
                      <span>The automatic run is off.</span>
                    }
                  </p>

                  @if (entry.items.length > 0) {
                    <ul class="item-list" [attr.data-testid]="'retention-items-' + category">
                      @for (item of entry.items; track item.id) {
                        <li data-testid="retention-item">
                          <span class="item-label">{{ item.label }}</span>
                          @if (item.counts) {
                            <span class="muted">
                              users: {{ item.counts.users }}, decisions: {{ item.counts.decisions }},
                              spaces: {{ item.counts.spaces }}, memberships: {{ item.counts.memberships }}
                            </span>
                          }
                          <span class="muted nowrap">due {{ item.due_at | date:'mediumDate' }}</span>
                        </li>
                      }
                    </ul>
                    @if (entry.items_truncated) {
                      <p class="muted" [attr.data-testid]="'retention-truncated-' + category">
                        Showing the first {{ entry.items.length }} of {{ entry.waiting }}, oldest first.
                      </p>
                    }
                  } @else if (entry.cutoff && entry.waiting > 0) {
                    <p class="muted">Everything created before {{ entry.cutoff | date:'mediumDate' }}.</p>
                  }

                  @if (entry.needs_review && entry.needs_review.length > 0) {
                    <div class="review" data-testid="retention-needs-review">
                      <p>
                        <mat-icon>help_outline</mat-icon>
                        <span>
                          Never erased automatically: these tenants have a deletion date in the past but their
                          status is not "deleted". They need a decision from you: nothing here will erase them.
                        </span>
                      </p>
                      <ul class="item-list">
                        @for (tenant of entry.needs_review; track tenant.id) {
                          <li>
                            <span class="item-label">{{ tenant.label }}</span>
                            <span class="muted">status: {{ tenant.status || 'not set' }}</span>
                          </li>
                        }
                      </ul>
                    </div>
                  }

                  @if (entry.waiting > 0) {
                    <button mat-stroked-button color="warn" [attr.data-testid]="'retention-run-' + category"
                            [disabled]="runningCategory !== null" (click)="runCategory(category)">
                      {{ runningCategory === category ? 'Running...' : 'Run this category now' }}
                    </button>
                  }
                </section>
              }
            }
          </mat-card-content>
        </mat-card>

        <mat-card data-testid="retention-limits">
          <mat-card-header>
            <mat-card-title>
              <mat-icon>tune</mat-icon>
              Limits for the automatic run
            </mat-card-title>
            <mat-card-subtitle>
              When more are waiting than a limit, the automatic run leaves that category alone until a super admin runs it.
              A limit of 0 always holds the category back.
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <div class="limits-grid">
              <mat-form-field appearance="outline">
                <mat-label>Accounts</mat-label>
                <input matInput type="number" min="0" step="1" data-testid="retention-limit-input-accounts"
                       [(ngModel)]="limits.accounts">
                <mat-hint>Most accounts anonymised in one run</mat-hint>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Decisions</mat-label>
                <input matInput type="number" min="0" step="1" data-testid="retention-limit-input-decisions"
                       [(ngModel)]="limits.decisions">
                <mat-hint>Most decisions erased in one run</mat-hint>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Tenants</mat-label>
                <input matInput type="number" min="0" step="1" data-testid="retention-limit-input-tenants"
                       [(ngModel)]="limits.tenants">
                <mat-hint>Most tenants erased in one run</mat-hint>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Days overdue</mat-label>
                <input matInput type="number" min="0" step="1" data-testid="retention-backlog-days-input"
                       [(ngModel)]="backlogDays">
                <mat-hint>Hold back when the oldest has waited longer. 0 turns this check off</mat-hint>
              </mat-form-field>
            </div>
            <p class="muted">Login history and stored messages are erased by age alone and have no limit.</p>
            <button mat-flat-button color="primary" data-testid="retention-limits-save"
                    [disabled]="isSavingLimits" (click)="saveLimits()">
              Save limits
            </button>
          </mat-card-content>
        </mat-card>

        <mat-card data-testid="retention-runs">
          <mat-card-header>
            <mat-card-title>
              <mat-icon>history</mat-icon>
              Last runs
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            @if (status.runs.length === 0) {
              <p class="muted" data-testid="retention-runs-empty">No runs yet.</p>
            } @else {
              <div class="table-wrapper">
                <table class="runs-table">
                  <thead>
                    <tr>
                      <th>Started</th>
                      <th>Started by</th>
                      <th>Result</th>
                      <th>Done</th>
                      <th>Held back</th>
                      <th>Errors</th>
                      <th>Took</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (run of status.runs; track run.id) {
                      <tr data-testid="retention-run-row">
                        <td class="nowrap">{{ run.started_at | date:'short' }}</td>
                        <td>{{ trigger(run) }}</td>
                        <td>
                          <span class="chip" [class]="'run-' + run.status">{{ runStatus(run.status) }}</span>
                        </td>
                        <td>{{ runDone(run) }}</td>
                        <td>{{ runHeld(run) }}</td>
                        <td class="wrap">{{ runErrors(run) }}</td>
                        <td class="nowrap">{{ duration(run.duration_ms) }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            }
          </mat-card-content>
        </mat-card>
      }
    </div>
  `,
  styles: [`
    .retention-container {
      padding: 24px;
      max-width: 1100px;
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
      margin: 0 0 16px;
      max-width: 760px;
    }

    .irreversible,
    .held-banner,
    .notice {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      border-radius: 6px;
      padding: 10px 12px;
      margin: 0 0 16px;
      font-size: 14px;
    }

    .irreversible {
      background: #f1f5f9;
      color: #334155;
    }

    .held-banner {
      background: #fff7ed;
      color: #9a3412;
      border: 1px solid #fdba74;
      font-weight: 500;
    }

    .notice {
      background: #e3f2fd;
      color: #0d47a1;
    }

    mat-card {
      margin-bottom: 24px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    mat-card-content {
      padding-top: 12px;
    }

    .state-line {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      margin: 8px 0;
      font-size: 14px;
    }

    .muted {
      color: #777;
      font-size: 13px;
      margin: 4px 0;
    }

    .category {
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 12px;
    }

    .category.is-held {
      border-color: #fdba74;
      background: #fffbf5;
    }

    .category-head {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
    }

    .category h3 {
      margin: 0;
      font-size: 15px;
    }

    .numbers {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      white-space: nowrap;
      font-size: 14px;
    }

    .numbers strong {
      font-size: 20px;
      font-variant-numeric: tabular-nums;
    }

    .item-list {
      list-style: none;
      padding: 0;
      margin: 8px 0;
      max-height: 260px;
      overflow-y: auto;
    }

    .item-list li {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 4px 0;
      border-bottom: 1px solid #f0f0f0;
      font-size: 14px;
    }

    .item-label {
      overflow-wrap: anywhere;
      flex: 1;
    }

    .review {
      background: #f8fafc;
      border-radius: 6px;
      padding: 8px 12px;
      margin: 8px 0;
      font-size: 14px;
    }

    .review p {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      margin: 0;
    }

    .limits-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px 16px;
      margin-bottom: 8px;
    }

    .limits-grid mat-form-field {
      width: 100%;
      margin-bottom: 12px;
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

    .table-wrapper {
      overflow-x: auto;
    }

    .runs-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }

    .runs-table th {
      text-align: left;
      color: #64748b;
      font-weight: 500;
      padding: 8px;
      border-bottom: 1px solid #e5e7eb;
    }

    .runs-table td {
      padding: 8px;
      border-bottom: 1px solid #f0f0f0;
      vertical-align: top;
    }

    td.wrap {
      max-width: 280px;
      overflow-wrap: anywhere;
    }

    .nowrap {
      white-space: nowrap;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      border-radius: 12px;
      padding: 2px 10px;
      font-size: 12px;
      font-weight: 500;
      white-space: nowrap;
      background: #eceff1;
      color: #37474f;
    }

    .chip.on,
    .chip.run-completed {
      background: #e8f5e9;
      color: #2e7d32;
    }

    .chip.off {
      background: #eceff1;
      color: #37474f;
    }

    .chip.held,
    .chip.run-held_back {
      background: #fff3e0;
      color: #e65100;
    }

    .chip.run-completed_with_errors,
    .chip.run-interrupted {
      background: #ffebee;
      color: #c62828;
    }

    .chip.run-running {
      background: #e3f2fd;
      color: #0d47a1;
    }
  `]
})
export class SuperadminRetentionComponent implements OnInit {
  status: RetentionStatus | null = null;
  isLoading = true;
  loadError = '';
  isSavingAuto = false;
  isSavingLimits = false;
  runningCategory: string | null = null;

  limits: { accounts: number; decisions: number; tenants: number } = { accounts: 0, decisions: 0, tenants: 0 };
  backlogDays = 0;

  constructor(
    private http: HttpClient,
    private dialog: MatDialog,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.load();
  }

  get heldBackNames(): string {
    return (this.status?.held_back || []).map(category => retentionCategoryLabel(category).toLowerCase()).join(', ');
  }

  label(category: string): string {
    return retentionCategoryLabel(category);
  }

  rule(category: string): string {
    return categoryText(category).rule;
  }

  holdReason(entry: RetentionPreviewEntry): string {
    return retentionHoldReason(entry.hold_reason, entry.limit, this.status?.settings.backlog_days ?? 0);
  }

  trigger(run: RetentionRun): string {
    return retentionTriggerLabel(run);
  }

  runStatus(status: string): string {
    return retentionRunStatusLabel(status);
  }

  duration(ms: number | null): string {
    return retentionDuration(ms);
  }

  /** "2 tenants, 5 login history entries" for what a run did. */
  runDone(run: RetentionRun): string {
    const parts = Object.entries(run.results || {})
      .filter(([, result]) => result.affected > 0)
      .map(([category, result]) => retentionCount(category, result.affected));
    return parts.length ? parts.join(', ') : 'Nothing';
  }

  runHeld(run: RetentionRun): string {
    return Object.entries(run.results || {})
      .filter(([, result]) => result.status === 'held_back')
      .map(([category, result]) => retentionCount(category, result.waiting))
      .join(', ');
  }

  runErrors(run: RetentionRun): string {
    const parts = Object.entries(run.results || {})
      .filter(([, result]) => result.status === 'error')
      .map(([category, result]) => {
        const count = result.error_count ?? result.errors.length;
        const first = result.errors[0]?.error;
        return `${retentionCategoryLabel(category)}: ${count} failed${first ? ' (' + first + ')' : ''}`;
      });
    if (run.error) parts.push(run.error);
    return parts.join('; ');
  }

  load(): void {
    this.isLoading = true;
    this.loadError = '';
    this.http.get<RetentionStatus>('/api/superadmin/retention').subscribe({
      next: (status) => {
        this.status = status;
        this.limits = { ...status.settings.limits };
        this.backlogDays = status.settings.backlog_days;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.loadError = err.error?.error || 'Data retention could not be loaded. Please try again.';
        if (this.status) {
          this.snackBar.open(this.loadError, 'Close', { duration: 5000 });
        }
      }
    });
  }

  toggleAutomatic(): void {
    if (!this.status) return;
    const enable = !this.status.settings.auto_run_enabled;
    this.isSavingAuto = true;
    this.http.put<RetentionSettings>('/api/admin/settings/retention', { auto_run_enabled: enable }).subscribe({
      next: () => {
        this.isSavingAuto = false;
        this.snackBar.open(enable ? 'The automatic run is on' : 'The automatic run is off', 'Close', { duration: 3000 });
        this.load();
      },
      error: (err) => {
        this.isSavingAuto = false;
        this.snackBar.open(err.error?.error || 'Could not save the setting. Please try again.', 'Close', { duration: 5000 });
      }
    });
  }

  saveLimits(): void {
    const values = [this.limits.accounts, this.limits.decisions, this.limits.tenants, this.backlogDays];
    if (values.some(value => value === null || !Number.isInteger(Number(value)) || Number(value) < 0)) {
      this.snackBar.open('Each limit must be a whole number, 0 or more.', 'Close', { duration: 5000 });
      return;
    }
    this.isSavingLimits = true;
    this.http.put<RetentionSettings>('/api/admin/settings/retention', {
      limits: {
        accounts: Number(this.limits.accounts),
        decisions: Number(this.limits.decisions),
        tenants: Number(this.limits.tenants)
      },
      backlog_days: Number(this.backlogDays)
    }).subscribe({
      next: () => {
        this.isSavingLimits = false;
        this.snackBar.open('Limits saved', 'Close', { duration: 3000 });
        this.load();
      },
      error: (err) => {
        this.isSavingLimits = false;
        this.snackBar.open(err.error?.error || 'Could not save the limits. Please try again.', 'Close', { duration: 5000 });
      }
    });
  }

  runCategory(category: string): void {
    const entry = this.status?.preview[category];
    if (!entry || entry.waiting === 0) return;
    const count = entry.waiting;
    const text = categoryText(category);

    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: text.label,
        message: `${text.verb} ${retentionCount(category, count)} now? This cannot be undone.`,
        confirmText: `${text.verb} ${count}`,
        cancelText: 'Cancel',
        isDanger: true
      }
    });

    dialogRef.afterClosed().subscribe((confirmed) => {
      if (!confirmed) return;
      this.runningCategory = category;
      this.http.post<{ message: string; run: RetentionRun }>('/api/superadmin/retention/run', {
        categories: [category],
        confirm_counts: { [category]: count }
      }).subscribe({
        next: (response) => {
          this.runningCategory = null;
          const result = response.run.results?.[category];
          const done = result?.affected ?? 0;
          let message = `${retentionDoneWord(category)} ${retentionCount(category, done)}.`;
          if (result?.status === 'error') {
            const failed = result.error_count ?? result.errors.length;
            message = `${retentionDoneWord(category)} ${done}, ${failed} failed. See the last runs for the error.`;
          }
          this.snackBar.open(message, 'Close', { duration: result?.status === 'error' ? 8000 : 4000 });
          this.load();
        },
        error: (err) => {
          this.runningCategory = null;
          let message = err.error?.error || 'The run could not be started. Please try again.';
          if (err.status === 409 && err.error?.waiting) {
            const now = err.error.waiting[category];
            message = `The number waiting changed from ${count} to ${now}. Nothing was done. Check the list and run it again.`;
          }
          this.snackBar.open(message, 'Close', { duration: 8000 });
          this.load();
        }
      });
    });
  }
}
