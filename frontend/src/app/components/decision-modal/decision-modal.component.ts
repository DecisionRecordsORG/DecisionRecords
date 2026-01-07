import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef, MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { DecisionService } from '../../services/decision.service';
import { AuthService } from '../../services/auth.service';
import { SpaceService } from '../../services/space.service';
import { AdminService } from '../../services/admin.service';
import { Decision, Space } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

// Modal mode types
export type DecisionModalMode = 'create' | 'view' | 'edit';

// Input data interface
export interface DecisionModalData {
  mode: DecisionModalMode;
  decisionId?: number;
  tenant: string;
}

// Output result interface
export interface DecisionModalResult {
  action: 'saved' | 'deleted' | 'cancelled';
  decision?: Decision;
}

@Component({
  selector: 'app-decision-modal',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatTooltipModule,
    ConfirmDialogComponent
  ],
  template: `
    <!-- Modal Header -->
    <div class="modal-header">
      <div class="header-left">
        <mat-icon class="header-icon">{{ getModeIcon() }}</mat-icon>
        <h2 mat-dialog-title>{{ getHeaderTitle() }}</h2>
        @if (!isCreate && decision) {
          <span class="decision-id-badge" [ngClass]="'status-badge-' + decision.status">
            {{ decision.display_id || 'ADR-' + decision.id }}
          </span>
        }
      </div>
      <div class="header-actions">
        @if (mode === 'view' && !authService.isMasterAccount) {
          <button mat-icon-button (click)="switchToEdit()" matTooltip="Edit Decision">
            <mat-icon>edit</mat-icon>
          </button>
        }
        <button mat-icon-button (click)="close()" matTooltip="Close">
          <mat-icon>close</mat-icon>
        </button>
      </div>
    </div>

    <!-- Modal Content -->
    <mat-dialog-content class="modal-content">
      @if (isLoading) {
        <div class="loading-container">
          <mat-spinner diameter="48"></mat-spinner>
          <p>Loading decision...</p>
        </div>
      } @else {
        <div class="content-grid" [class.create-mode]="isCreate">
          <!-- Left Column: Form -->
          <div class="form-column">
            <form [formGroup]="form">
              <!-- Title + Status Row -->
              <div class="form-row">
                <mat-form-field appearance="outline" class="title-field">
                  <mat-label>Title</mat-label>
                  <input matInput formControlName="title"
                         [readonly]="mode === 'view'"
                         placeholder="Short, descriptive title">
                  @if (form.get('title')?.hasError('required') && form.get('title')?.touched) {
                    <mat-error>Title is required</mat-error>
                  }
                </mat-form-field>

                <mat-form-field appearance="outline" class="status-field">
                  <mat-label>Status</mat-label>
                  <mat-select formControlName="status" [disabled]="mode === 'view'">
                    <mat-option value="proposed">
                      <mat-icon>pending</mat-icon> Proposed
                    </mat-option>
                    <mat-option value="accepted">
                      <mat-icon>check_circle</mat-icon> Accepted
                    </mat-option>
                    <mat-option value="archived">
                      <mat-icon>archive</mat-icon> Archived
                    </mat-option>
                    <mat-option value="superseded">
                      <mat-icon>swap_horiz</mat-icon> Superseded
                    </mat-option>
                  </mat-select>
                </mat-form-field>
              </div>

              <!-- Context -->
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Context</mat-label>
                <textarea matInput formControlName="context" rows="5"
                          [readonly]="mode === 'view'"
                          placeholder="Describe the issue and context that motivates this decision..."></textarea>
              </mat-form-field>

              <!-- Decision -->
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Decision</mat-label>
                <textarea matInput formControlName="decision" rows="5"
                          [readonly]="mode === 'view'"
                          placeholder="Describe the change or solution being implemented..."></textarea>
              </mat-form-field>

              <!-- Consequences -->
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Consequences</mat-label>
                <textarea matInput formControlName="consequences" rows="5"
                          [readonly]="mode === 'view'"
                          placeholder="Describe the resulting context and tradeoffs..."></textarea>
              </mat-form-field>

              <!-- Change Reason (edit mode only) -->
              @if (mode === 'edit') {
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Change Reason (optional)</mat-label>
                  <input matInput formControlName="change_reason"
                         placeholder="Why are you making this change?">
                </mat-form-field>
              }

              <!-- Master Account Notice -->
              @if (authService.isMasterAccount) {
                <div class="read-only-notice">
                  <mat-icon>info</mat-icon>
                  Master accounts can view but not modify decisions
                </div>
              }
            </form>
          </div>

          <!-- Right Column: Metadata & Settings -->
          <div class="side-panel">
            <!-- Spaces Card -->
            @if (spaces.length > 0) {
              <div class="meta-card">
                <div class="meta-card-header">
                  <mat-icon>folder</mat-icon>
                  <span>Spaces</span>
                </div>
                <div class="meta-card-content spaces-content">
                  @if (mode === 'view') {
                    <div class="spaces-list">
                      @for (spaceId of selectedSpaceIds; track spaceId) {
                        <span class="space-chip">{{ getSpaceName(spaceId) }}</span>
                      }
                      @if (selectedSpaceIds.length === 0) {
                        <span class="no-spaces">No spaces assigned</span>
                      }
                    </div>
                  } @else {
                    <mat-form-field appearance="outline" class="full-width compact-field">
                      <mat-select [(ngModel)]="selectedSpaceIds" [ngModelOptions]="{standalone: true}"
                                  multiple [disabled]="authService.isMasterAccount"
                                  placeholder="Select spaces">
                        @for (space of spaces; track space.id) {
                          <mat-option [value]="space.id">
                            {{ space.name }}
                            @if (space.is_default) {
                              <span class="default-badge">(Default)</span>
                            }
                          </mat-option>
                        }
                      </mat-select>
                    </mat-form-field>
                    <p class="field-hint">Organize this decision in one or more spaces</p>
                  }
                </div>
              </div>
            }

            <!-- Decision Owner Card -->
            <div class="meta-card">
              <div class="meta-card-header">
                <mat-icon>person_outline</mat-icon>
                <span>Decision Owner</span>
              </div>
              <div class="meta-card-content">
                @if (mode === 'view') {
                  @if (decision?.owner || decision?.owner_email) {
                    <div class="owner-display">
                      <mat-icon>person</mat-icon>
                      <span>{{ decision?.owner?.name || decision?.owner?.email || decision?.owner_email }}</span>
                    </div>
                  } @else {
                    <span class="no-owner">No owner assigned</span>
                  }
                } @else {
                  <mat-form-field appearance="outline" class="full-width compact-field">
                    <mat-label>Team member</mat-label>
                    <mat-select [(ngModel)]="selectedOwnerId" [ngModelOptions]="{standalone: true}"
                                [disabled]="authService.isMasterAccount">
                      <mat-option [value]="null">-- None --</mat-option>
                      @for (member of tenantMembers; track member.id) {
                        <mat-option [value]="member.id">
                          {{ member.name }} ({{ member.email }})
                        </mat-option>
                      }
                    </mat-select>
                  </mat-form-field>
                  <div class="or-divider-row">
                    <span class="or-line"></span>
                    <span class="or-text">or</span>
                    <span class="or-line"></span>
                  </div>
                  <mat-form-field appearance="outline" class="full-width compact-field">
                    <mat-label>External email</mat-label>
                    <input matInput [(ngModel)]="ownerEmail" [ngModelOptions]="{standalone: true}"
                           placeholder="someone@external.com" type="email"
                           [disabled]="authService.isMasterAccount">
                  </mat-form-field>
                  <p class="field-hint">The person who made this decision (may differ from who logged it)</p>
                }
              </div>
            </div>

            <!-- Details Card (view/edit only) -->
            @if (!isCreate && decision) {
              <div class="meta-card">
                <div class="meta-card-header">
                  <mat-icon>info</mat-icon>
                  <span>Details</span>
                </div>
                <div class="meta-card-content">
                  <div class="meta-item">
                    <div class="meta-icon-row">
                      <mat-icon class="meta-icon">calendar_today</mat-icon>
                      <span class="meta-label">Created</span>
                    </div>
                    <span class="meta-value">{{ decision.created_at | date:'MMM d, yyyy' }}</span>
                    <span class="meta-time">{{ decision.created_at | date:'h:mm a' }}</span>
                    @if (decision.created_by) {
                      <div class="meta-user">
                        <mat-icon>person</mat-icon>
                        {{ decision.created_by.name || decision.created_by.email }}
                      </div>
                    }
                  </div>

                  <div class="meta-item">
                    <div class="meta-icon-row">
                      <mat-icon class="meta-icon">update</mat-icon>
                      <span class="meta-label">Last Updated</span>
                    </div>
                    <span class="meta-value">{{ decision.updated_at | date:'MMM d, yyyy' }}</span>
                    <span class="meta-time">{{ decision.updated_at | date:'h:mm a' }}</span>
                    @if (decision.updated_by) {
                      <div class="meta-user">
                        <mat-icon>person</mat-icon>
                        {{ decision.updated_by.name || decision.updated_by.email }}
                      </div>
                    }
                  </div>

                  @if (decision.domain) {
                    <div class="meta-item">
                      <div class="meta-icon-row">
                        <mat-icon class="meta-icon">domain</mat-icon>
                        <span class="meta-label">Domain</span>
                      </div>
                      <span class="meta-value">{{ decision.domain }}</span>
                    </div>
                  }
                </div>
              </div>

              <!-- Change History Card -->
              @if (decision.history && decision.history.length > 0) {
                <div class="history-card">
                  <div class="history-card-header">
                    <mat-icon>history</mat-icon>
                    <span>Change History</span>
                    <span class="history-count">{{ decision.history.length }}</span>
                  </div>
                  <div class="history-list">
                    @for (item of decision.history; track item.id; let i = $index) {
                      <div class="history-entry" [class.expanded]="expandedHistoryIndex === i"
                           (click)="toggleHistoryEntry(i)">
                        <div class="history-entry-header">
                          <div class="history-entry-date">
                            <span class="date-primary">{{ item.changed_at | date:'MMM d, yyyy' }}</span>
                            <span class="date-secondary">{{ item.changed_at | date:'h:mm a' }}</span>
                          </div>
                          <div class="history-entry-meta">
                            @if (item.changed_by) {
                              <span class="history-entry-user">
                                <mat-icon>person</mat-icon>
                                {{ item.changed_by.name || item.changed_by.email }}
                              </span>
                            }
                            <mat-icon class="expand-icon">
                              {{ expandedHistoryIndex === i ? 'expand_less' : 'expand_more' }}
                            </mat-icon>
                          </div>
                        </div>
                        @if (expandedHistoryIndex === i) {
                          <div class="history-entry-content">
                            @if (item.change_reason) {
                              <div class="change-reason">
                                <mat-icon>comment</mat-icon>
                                <span>{{ item.change_reason }}</span>
                              </div>
                            }
                            <div class="history-snapshot">
                              <div class="snapshot-header">
                                <h4 class="snapshot-title">{{ item.title }}</h4>
                                <div class="status-chip" [ngClass]="'status-' + item.status">
                                  <mat-icon class="status-icon">{{ getStatusIcon(item.status) }}</mat-icon>
                                  {{ item.status | titlecase }}
                                </div>
                              </div>

                              <div class="snapshot-field">
                                <div class="snapshot-label">
                                  <mat-icon>description</mat-icon>
                                  Context
                                </div>
                                <div class="snapshot-value">{{ item.context || '(empty)' }}</div>
                              </div>

                              <div class="snapshot-field">
                                <div class="snapshot-label">
                                  <mat-icon>gavel</mat-icon>
                                  Decision
                                </div>
                                <div class="snapshot-value">{{ item.decision || '(empty)' }}</div>
                              </div>

                              <div class="snapshot-field">
                                <div class="snapshot-label">
                                  <mat-icon>trending_up</mat-icon>
                                  Consequences
                                </div>
                                <div class="snapshot-value">{{ item.consequences || '(empty)' }}</div>
                              </div>
                            </div>
                          </div>
                        }
                      </div>
                    }
                  </div>
                </div>
              }
            }
          </div>
        </div>
      }
    </mat-dialog-content>

    <!-- Modal Footer Actions -->
    <mat-dialog-actions align="end">
      @if (mode === 'view') {
        <button mat-button (click)="close()">Close</button>
      } @else {
        <button mat-button (click)="close()">Cancel</button>

        @if (!isCreate && authService.canDeleteDecisions && !authService.isMasterAccount) {
          <button mat-button color="warn" (click)="confirmDelete()">
            <mat-icon>delete</mat-icon>
            Delete
          </button>
        }

        @if (!authService.isMasterAccount) {
          <button mat-flat-button color="primary"
                  (click)="onSubmit()"
                  [disabled]="form.invalid || isSaving">
            @if (isSaving) {
              <mat-spinner diameter="18"></mat-spinner>
              Saving...
            } @else {
              <mat-icon>{{ isCreate ? 'add' : 'save' }}</mat-icon>
              {{ isCreate ? 'Create Decision' : 'Save Changes' }}
            }
          </button>
        }
      }
    </mat-dialog-actions>
  `,
  styles: [`
    /* Modal Header */
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 24px;
      border-bottom: 1px solid #e0e0e0;
      background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .header-icon {
      color: #3b82f6;
      display: flex;
    }

    h2[mat-dialog-title] {
      margin: 0;
      padding: 0;
      font-size: 20px;
      font-weight: 600;
      color: #1a1a1a;
      font-family: 'Plus Jakarta Sans', sans-serif;
    }

    :host ::ng-deep .mat-mdc-dialog-title {
      padding: 0 0 18px 0 !important;
      margin: 0 !important;
    }

    .decision-id-badge {
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
    }

    .status-badge-proposed { background: #fff3e0; color: #e65100; }
    .status-badge-accepted { background: #e8f5e9; color: #2e7d32; }
    .status-badge-archived { background: #eceff1; color: #546e7a; }
    .status-badge-superseded { background: #e3f2fd; color: #1565c0; }

    .header-actions {
      display: flex;
      gap: 4px;
    }

    /* Modal Content */
    .modal-content {
      padding: 0 !important;
      max-height: calc(85vh - 140px);
      overflow-y: auto;
    }

    .loading-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 64px;
      gap: 16px;
      color: #666;
    }

    .content-grid {
      display: grid;
      grid-template-columns: 1fr 320px;
      gap: 0;
      min-height: 100%;
    }

    @media (max-width: 900px) {
      .content-grid {
        grid-template-columns: 1fr;
      }
      .side-panel {
        border-left: none;
        border-top: 1px solid #e0e0e0;
      }
    }

    /* Form Column */
    .form-column {
      padding: 24px;
      overflow-y: auto;
    }

    .form-row {
      display: flex;
      gap: 16px;
      align-items: flex-start;
    }

    .title-field {
      flex: 1;
    }

    .status-field {
      width: 180px;
      flex-shrink: 0;
    }

    .full-width {
      width: 100%;
    }

    mat-form-field {
      margin-bottom: 12px;
    }

    .default-badge {
      font-size: 11px;
      color: #888;
      margin-left: 4px;
    }

    /* Textarea in view mode - improve text contrast */
    textarea[readonly] {
      color: #1a1a1a !important;
      -webkit-text-fill-color: #1a1a1a !important;
    }

    input[readonly] {
      color: #1a1a1a !important;
      -webkit-text-fill-color: #1a1a1a !important;
    }

    /* Disabled inputs should still be readable */
    :host ::ng-deep .mat-mdc-form-field-disabled .mdc-text-field__input {
      color: #1a1a1a !important;
      -webkit-text-fill-color: #1a1a1a !important;
    }

    .read-only-notice {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 16px;
      background: #fff3e0;
      color: #e65100;
      border-radius: 8px;
      margin-top: 16px;
    }

    /* Side Panel */
    .side-panel {
      background: #f8f9fa;
      border-left: 1px solid #e0e0e0;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 20px;
      overflow-y: auto;
    }

    /* Meta Card */
    .meta-card {
      background: white;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }

    .meta-card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 16px;
      background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
      border-bottom: 1px solid #e9ecef;
      font-size: 14px;
      font-weight: 600;
      color: #1a1a1a;
    }

    .meta-card-header mat-icon {
      color: #3b82f6;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .meta-card-content {
      padding: 16px;
    }

    .meta-item {
      padding: 14px;
      background: #f8f9fa;
      border-radius: 10px;
      margin-bottom: 12px;
    }

    .meta-item:last-child {
      margin-bottom: 0;
    }

    .meta-icon-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }

    .meta-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      color: #757575;
    }

    .meta-label {
      font-size: 11px;
      font-weight: 600;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .meta-value {
      display: block;
      font-size: 14px;
      font-weight: 600;
      color: #1a1a1a;
      margin-bottom: 2px;
    }

    .meta-time {
      display: block;
      font-size: 12px;
      color: #888;
    }

    .meta-user {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #555;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid #e9ecef;
    }

    .meta-user mat-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
      color: #888;
    }

    /* History Card */
    .history-card {
      background: white;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }

    .history-card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 16px;
      background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
      border-bottom: 1px solid #e9ecef;
      font-size: 14px;
      font-weight: 600;
      color: #1a1a1a;
    }

    .history-card-header mat-icon {
      color: #3b82f6;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .history-count {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 22px;
      height: 22px;
      padding: 0 6px;
      background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
      border-radius: 11px;
      font-size: 12px;
      font-weight: 600;
      color: #1565c0;
      margin-left: auto;
    }

    .history-list {
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 400px;
      overflow-y: auto;
    }

    .history-entry {
      background: #f8f9fa;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s ease;
      border: 2px solid transparent;
    }

    .history-entry:hover {
      background: #f0f4f8;
      border-color: #e3f2fd;
    }

    .history-entry.expanded {
      background: #fff;
      border-color: #3b82f6;
      box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
    }

    .history-entry-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 14px;
    }

    .history-entry-date {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .date-primary {
      font-size: 13px;
      font-weight: 600;
      color: #1a1a1a;
    }

    .date-secondary {
      font-size: 11px;
      color: #888;
    }

    .history-entry-meta {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .history-entry-user {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: #555;
    }

    .history-entry-user mat-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
      color: #888;
    }

    .expand-icon {
      color: #9e9e9e;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .history-entry.expanded .expand-icon {
      color: #3b82f6;
    }

    .history-entry-content {
      padding: 0 14px 14px 14px;
      border-top: 1px solid #e9ecef;
    }

    .change-reason {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
      padding: 10px 12px;
      border-radius: 6px;
      margin: 12px 0;
      border-left: 3px solid #ffc107;
    }

    .change-reason mat-icon {
      color: #f57c00;
      font-size: 18px;
      width: 18px;
      height: 18px;
      flex-shrink: 0;
    }

    .change-reason span {
      font-size: 13px;
      color: #5d4037;
      line-height: 1.4;
    }

    .history-snapshot {
      padding-top: 12px;
    }

    .snapshot-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 12px;
      padding-bottom: 10px;
      border-bottom: 1px solid #eee;
    }

    .snapshot-title {
      margin: 0;
      font-size: 14px;
      font-weight: 600;
      color: #1a1a1a;
      flex: 1;
    }

    .status-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 11px;
      font-weight: 500;
      padding: 4px 10px;
      border-radius: 16px;
      flex-shrink: 0;
    }

    .status-chip .status-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
    }

    .status-proposed { background: #fff3e0 !important; color: #e65100 !important; }
    .status-accepted { background: #e8f5e9 !important; color: #2e7d32 !important; }
    .status-archived { background: #eceff1 !important; color: #546e7a !important; }
    .status-superseded { background: #e3f2fd !important; color: #1565c0 !important; }

    .snapshot-field {
      margin-bottom: 10px;
      background: #f8f9fa;
      border-radius: 6px;
      padding: 10px 12px;
    }

    .snapshot-field:last-child {
      margin-bottom: 0;
    }

    .snapshot-label {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 10px;
      font-weight: 600;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }

    .snapshot-label mat-icon {
      font-size: 12px;
      width: 12px;
      height: 12px;
      color: #9e9e9e;
    }

    .snapshot-value {
      font-size: 12px;
      color: #333;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 80px;
      overflow-y: auto;
    }

    /* Right Panel New Styles */
    .compact-field {
      margin-bottom: 8px !important;
    }

    .field-hint {
      margin: 0;
      font-size: 12px;
      color: #666;
      line-height: 1.4;
    }

    .spaces-content {
      padding: 12px 16px 16px;
    }

    .spaces-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .space-chip {
      display: inline-flex;
      align-items: center;
      padding: 6px 12px;
      background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
      border-radius: 16px;
      font-size: 13px;
      font-weight: 500;
      color: #1565c0;
    }

    .no-spaces, .no-owner {
      font-size: 13px;
      color: #888;
      font-style: italic;
    }

    .owner-display {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      font-weight: 500;
      color: #1a1a1a;
    }

    .owner-display mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #666;
    }

    .or-divider-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 8px 0;
    }

    .or-line {
      flex: 1;
      height: 1px;
      background: #e0e0e0;
    }

    .or-text {
      font-size: 12px;
      color: #888;
      font-style: italic;
    }

    /* Modal Footer */
    mat-dialog-actions {
      padding: 16px 24px !important;
      border-top: 1px solid #e0e0e0;
      background: #fafafa;
      gap: 12px;
    }

    /* Fix icon alignment in buttons */
    :host ::ng-deep mat-dialog-actions .mdc-button__label {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }

    :host ::ng-deep mat-dialog-actions button mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    :host ::ng-deep mat-dialog-actions button mat-spinner {
      margin-right: 4px;
    }
  `]
})
export class DecisionModalComponent implements OnInit {
  mode: DecisionModalMode;
  decision: Decision | null = null;
  form: FormGroup;
  isLoading = false;
  isSaving = false;
  expandedHistoryIndex: number | null = null;

  // Spaces
  spaces: Space[] = [];
  selectedSpaceIds: number[] = [];

  // Decision owner
  tenantMembers: any[] = [];
  selectedOwnerId: number | null = null;
  ownerEmail: string = '';

  // Computed properties
  get isCreate(): boolean { return this.mode === 'create'; }
  get isView(): boolean { return this.mode === 'view'; }
  get isEdit(): boolean { return this.mode === 'edit'; }

  constructor(
    public dialogRef: MatDialogRef<DecisionModalComponent>,
    @Inject(MAT_DIALOG_DATA) public data: DecisionModalData,
    private fb: FormBuilder,
    private decisionService: DecisionService,
    public authService: AuthService,
    private spaceService: SpaceService,
    private adminService: AdminService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {
    this.mode = data.mode;
    this.form = this.fb.group({
      title: ['', Validators.required],
      status: ['proposed', Validators.required],
      context: [''],
      decision: [''],
      consequences: [''],
      change_reason: ['']
    });
  }

  ngOnInit(): void {
    if (this.isView) {
      this.form.disable();
    }

    if (!this.isCreate && this.data.decisionId) {
      this.loadDecision(this.data.decisionId);
    } else {
      this.loadSpacesAndMembers();
    }

    // Disable form for master account
    if (this.authService.isMasterAccount) {
      this.form.disable();
    }
  }

  loadSpacesAndMembers(): void {
    forkJoin({
      spaces: this.spaceService.getSpaces(),
      // Admin users endpoint returns 403 for non-admins, gracefully handle it
      members: this.adminService.getUsers().pipe(catchError(() => of([])))
    }).subscribe({
      next: ({ spaces, members }) => {
        this.spaces = spaces;
        this.tenantMembers = members;

        // For new decisions, pre-select the default space
        if (this.isCreate) {
          const defaultSpace = spaces.find(s => s.is_default);
          if (defaultSpace) {
            this.selectedSpaceIds = [defaultSpace.id];
          }
        }
      },
      error: (err) => {
        console.error('Failed to load spaces/members', err);
      }
    });
  }

  loadDecision(id: number): void {
    this.isLoading = true;

    forkJoin({
      decision: this.decisionService.getDecision(id),
      spaces: this.spaceService.getSpaces(),
      // Admin users endpoint returns 403 for non-admins, gracefully handle it
      members: this.adminService.getUsers().pipe(catchError(() => of([])))
    }).subscribe({
      next: ({ decision, spaces, members }) => {
        this.decision = decision;
        this.spaces = spaces;
        this.tenantMembers = members;

        this.form.patchValue({
          title: decision.title,
          status: decision.status,
          context: decision.context,
          decision: decision.decision,
          consequences: decision.consequences
        });

        // Load decision's spaces
        if (decision.spaces && decision.spaces.length > 0) {
          this.selectedSpaceIds = decision.spaces.map(s => s.id);
        }

        // Load decision's owner
        this.selectedOwnerId = decision.owner_id || null;
        this.ownerEmail = decision.owner_email || '';

        if (this.isView || this.authService.isMasterAccount) {
          this.form.disable();
        }

        this.isLoading = false;
      },
      error: (err) => {
        this.snackBar.open('Failed to load decision', 'Close', { duration: 3000 });
        this.dialogRef.close();
      }
    });
  }

  getModeIcon(): string {
    switch (this.mode) {
      case 'create': return 'add_circle';
      case 'view': return 'visibility';
      case 'edit': return 'edit_note';
      default: return 'article';
    }
  }

  getHeaderTitle(): string {
    switch (this.mode) {
      case 'create': return 'New Decision';
      case 'view': return 'View Decision';
      case 'edit': return 'Edit Decision';
      default: return 'Decision';
    }
  }

  getStatusIcon(status: string): string {
    const icons: Record<string, string> = {
      'proposed': 'schedule',
      'accepted': 'check_circle',
      'archived': 'archive',
      'superseded': 'swap_horiz'
    };
    return icons[status] || 'help';
  }

  getSpaceName(spaceId: number): string {
    const space = this.spaces.find(s => s.id === spaceId);
    return space?.name || 'Unknown';
  }

  switchToEdit(): void {
    this.mode = 'edit';
    this.form.enable();
    if (this.authService.isMasterAccount) {
      this.form.disable();
    }
  }

  toggleHistoryEntry(index: number): void {
    this.expandedHistoryIndex = this.expandedHistoryIndex === index ? null : index;
  }

  onSubmit(): void {
    if (this.form.invalid || this.authService.isMasterAccount) return;

    this.isSaving = true;
    const formValue = this.form.value;

    const payload: any = {
      title: formValue.title,
      context: formValue.context,
      decision: formValue.decision,
      status: formValue.status,
      consequences: formValue.consequences,
      space_ids: this.selectedSpaceIds,
      owner_id: this.selectedOwnerId,
      owner_email: this.ownerEmail || undefined
    };

    if (this.isEdit && formValue.change_reason) {
      payload.change_reason = formValue.change_reason;
    }

    const operation = this.isCreate
      ? this.decisionService.createDecision(payload)
      : this.decisionService.updateDecision(this.decision!.id, payload);

    operation.subscribe({
      next: (decision) => {
        this.snackBar.open(
          this.isCreate ? 'Decision created successfully' : 'Decision updated successfully',
          'Close',
          { duration: 3000 }
        );
        this.dialogRef.close({ action: 'saved', decision } as DecisionModalResult);
      },
      error: (err) => {
        this.isSaving = false;
        this.snackBar.open(err.error?.error || 'Failed to save decision', 'Close', { duration: 3000 });
      }
    });
  }

  confirmDelete(): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete Decision',
        message: `Are you sure you want to delete ${this.decision?.display_id || 'ADR-' + this.decision?.id}? This action cannot be undone.`,
        confirmText: 'Delete',
        cancelText: 'Cancel',
        isDanger: true
      }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.deleteDecision();
      }
    });
  }

  deleteDecision(): void {
    if (!this.decision) return;

    this.decisionService.deleteDecision(this.decision.id).subscribe({
      next: () => {
        this.snackBar.open('Decision deleted successfully', 'Close', { duration: 3000 });
        this.dialogRef.close({ action: 'deleted' } as DecisionModalResult);
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to delete decision', 'Close', { duration: 3000 });
      }
    });
  }

  close(): void {
    // Check for unsaved changes
    if (this.form.dirty && this.mode !== 'view') {
      const dialogRef = this.dialog.open(ConfirmDialogComponent, {
        data: {
          title: 'Unsaved Changes',
          message: 'You have unsaved changes. Are you sure you want to close?',
          confirmText: 'Discard',
          cancelText: 'Keep Editing',
          isDanger: true
        }
      });

      dialogRef.afterClosed().subscribe(result => {
        if (result) {
          this.dialogRef.close({ action: 'cancelled' } as DecisionModalResult);
        }
      });
    } else {
      this.dialogRef.close({ action: 'cancelled' } as DecisionModalResult);
    }
  }
}
