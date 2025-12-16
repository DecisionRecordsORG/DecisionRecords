import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { DecisionService, UpdateDecisionRequest } from '../../services/decision.service';
import { AuthService } from '../../services/auth.service';
import { SpaceService } from '../../services/space.service';
import { AdminService } from '../../services/admin.service';
import { Decision, DecisionHistory, DecisionStatus, Space } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';
import { Observable, of } from 'rxjs';
import { map, startWith, debounceTime, switchMap, catchError } from 'rxjs/operators';

@Component({
  selector: 'app-decision-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    ReactiveFormsModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatExpansionModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDialogModule,
    MatTooltipModule,
    MatAutocompleteModule,
    ConfirmDialogComponent
  ],
  template: `
    <div class="decision-detail-container">
      <div class="header">
        <button mat-button [routerLink]="['/', tenant]">
          <mat-icon>arrow_back</mat-icon>
          Back to Decisions
        </button>
        <h1>{{ isNew ? 'New Decision' : (decision?.display_id || 'ADR-' + decision?.id) }}</h1>
      </div>

      @if (isLoading) {
        <div class="loading-container">
          <mat-spinner></mat-spinner>
        </div>
      } @else {
        <div class="content-grid">
          <mat-card class="main-card" appearance="outlined">
            <mat-card-header>
              <mat-card-title class="main-card-title">
                <mat-icon>edit_note</mat-icon>
                {{ isNew ? 'New Decision' : 'Edit Decision' }}
              </mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <form [formGroup]="form" (ngSubmit)="onSubmit()">
                <div class="form-section">
                  <div class="form-row">
                    <mat-form-field appearance="outline" class="title-field">
                      <mat-label>Title</mat-label>
                      <input matInput formControlName="title" placeholder="Short, descriptive title">
                      @if (form.get('title')?.hasError('required')) {
                        <mat-error>Title is required</mat-error>
                      }
                    </mat-form-field>

                    <mat-form-field appearance="outline" class="status-field">
                      <mat-label>Status</mat-label>
                      <mat-select formControlName="status">
                        <mat-option value="proposed">
                          <mat-icon>pending</mat-icon> Proposed
                        </mat-option>
                        <mat-option value="accepted">
                          <mat-icon>check_circle</mat-icon> Accepted
                        </mat-option>
                        <mat-option value="deprecated">
                          <mat-icon>warning</mat-icon> Deprecated
                        </mat-option>
                        <mat-option value="superseded">
                          <mat-icon>swap_horiz</mat-icon> Superseded
                        </mat-option>
                      </mat-select>
                    </mat-form-field>
                  </div>
                </div>

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Context</mat-label>
                  <textarea matInput formControlName="context" rows="6"
                            placeholder="Describe the issue and context that motivates this decision..."></textarea>
                  @if (form.get('context')?.hasError('required')) {
                    <mat-error>Context is required</mat-error>
                  }
                </mat-form-field>

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Decision</mat-label>
                  <textarea matInput formControlName="decision" rows="6"
                            placeholder="Describe the change or solution being implemented..."></textarea>
                  @if (form.get('decision')?.hasError('required')) {
                    <mat-error>Decision is required</mat-error>
                  }
                </mat-form-field>

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Consequences</mat-label>
                  <textarea matInput formControlName="consequences" rows="6"
                            placeholder="Describe the resulting context and tradeoffs..."></textarea>
                  @if (form.get('consequences')?.hasError('required')) {
                    <mat-error>Consequences is required</mat-error>
                  }
                </mat-form-field>

                <!-- Spaces Section -->
                @if (spaces.length > 0) {
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Spaces</mat-label>
                    <mat-select [(ngModel)]="selectedSpaceIds" [ngModelOptions]="{standalone: true}" multiple [disabled]="authService.isMasterAccount">
                      @for (space of spaces; track space.id) {
                        <mat-option [value]="space.id">
                          {{ space.name }}
                          @if (space.is_default) {
                            <span class="default-space-badge">(Default)</span>
                          }
                        </mat-option>
                      }
                    </mat-select>
                    <mat-icon matPrefix>folder</mat-icon>
                    <mat-hint>Select one or more spaces for this decision</mat-hint>
                  </mat-form-field>
                }

                <!-- Decision Owner Section -->
                <div class="owner-section">
                  <h4>Decision Owner</h4>
                  <p class="owner-hint">The person who made this decision (may differ from who logged it)</p>
                  <div class="owner-fields">
                    <mat-form-field appearance="outline" class="owner-select-field">
                      <mat-label>Select team member</mat-label>
                      <mat-select [(ngModel)]="selectedOwnerId" [ngModelOptions]="{standalone: true}" [disabled]="authService.isMasterAccount">
                        <mat-option [value]="null">-- None --</mat-option>
                        @for (member of tenantMembers; track member.id) {
                          <mat-option [value]="member.id">
                            {{ member.name }} ({{ member.email }})
                          </mat-option>
                        }
                      </mat-select>
                      <mat-icon matPrefix>person</mat-icon>
                    </mat-form-field>
                    <span class="or-divider">or</span>
                    <mat-form-field appearance="outline" class="owner-email-field">
                      <mat-label>External owner email</mat-label>
                      <input matInput [(ngModel)]="ownerEmail" [ngModelOptions]="{standalone: true}"
                             placeholder="someone@external.com" type="email" [disabled]="authService.isMasterAccount">
                      <mat-icon matPrefix>email</mat-icon>
                      <mat-hint>For owners outside your organization</mat-hint>
                    </mat-form-field>
                  </div>
                </div>

                @if (!isNew) {
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Change Reason (optional)</mat-label>
                    <input matInput formControlName="change_reason" placeholder="Why are you making this change?">
                  </mat-form-field>
                }

                @if (!authService.isMasterAccount) {
                  <div class="form-actions">
                    <button mat-raised-button color="primary" type="submit"
                            [disabled]="form.invalid || isSaving">
                      <mat-spinner diameter="20" *ngIf="isSaving"></mat-spinner>
                      <mat-icon *ngIf="!isSaving">save</mat-icon>
                      <span *ngIf="!isSaving">{{ isNew ? 'Create Decision' : 'Save Changes' }}</span>
                    </button>

                    @if (!isNew && authService.canDeleteDecisions) {
                      <button mat-raised-button color="warn" type="button" (click)="confirmDelete()">
                        <mat-icon>delete</mat-icon>
                        Delete
                      </button>
                    }
                  </div>
                } @else {
                  <div class="read-only-notice">
                    <mat-icon>info</mat-icon>
                    Master accounts can view but not modify decisions
                  </div>
                }
              </form>
            </mat-card-content>
          </mat-card>

          @if (!isNew && decision) {
            <div class="side-panel">
              <mat-card class="meta-card" appearance="outlined">
                <mat-card-header>
                  <mat-card-title class="meta-card-title">
                    <mat-icon>info</mat-icon>
                    Details
                  </mat-card-title>
                </mat-card-header>
                <mat-card-content>
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
                </mat-card-content>
              </mat-card>

              @if (decision.history && decision.history.length > 0) {
                <mat-card class="history-card" appearance="outlined">
                  <mat-card-header>
                    <mat-card-title class="history-card-title">
                      <mat-icon>history</mat-icon>
                      Change History
                      <span class="history-count">{{ decision.history.length }}</span>
                    </mat-card-title>
                  </mat-card-header>
                  <mat-card-content>
                    <div class="history-list">
                      @for (item of decision.history; track item.id; let i = $index) {
                        <div class="history-entry" [class.expanded]="expandedHistoryIndex === i" (click)="toggleHistoryEntry(i)">
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
                              <mat-icon class="expand-icon">{{ expandedHistoryIndex === i ? 'expand_less' : 'expand_more' }}</mat-icon>
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
                                  <div class="snapshot-value">{{ item.context }}</div>
                                </div>

                                <div class="snapshot-field">
                                  <div class="snapshot-label">
                                    <mat-icon>gavel</mat-icon>
                                    Decision
                                  </div>
                                  <div class="snapshot-value">{{ item.decision }}</div>
                                </div>

                                <div class="snapshot-field">
                                  <div class="snapshot-label">
                                    <mat-icon>trending_up</mat-icon>
                                    Consequences
                                  </div>
                                  <div class="snapshot-value">{{ item.consequences }}</div>
                                </div>
                              </div>
                            </div>
                          }
                        </div>
                      }
                    </div>
                  </mat-card-content>
                </mat-card>
              }
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .decision-detail-container {
      padding: 24px;
      max-width: 1400px;
      margin: 0 auto;
    }

    .header {
      margin-bottom: 24px;
    }

    .header h1 {
      margin: 8px 0 0 0;
      font-size: 28px;
    }

    .loading-container {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .content-grid {
      display: grid;
      grid-template-columns: 1fr 350px;
      gap: 24px;
    }

    @media (max-width: 1000px) {
      .content-grid {
        grid-template-columns: 1fr;
      }
    }

    .main-card {
      border-radius: 12px;
    }

    .main-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px !important;
      font-weight: 500 !important;
      color: #1a1a1a;
    }

    .main-card-title mat-icon {
      color: #1976d2;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .main-card mat-card-content {
      padding-top: 8px;
    }

    .form-section {
      margin-bottom: 8px;
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
      margin-bottom: 16px;
    }

    ::ng-deep .main-card .mat-mdc-form-field-subscript-wrapper {
      margin-bottom: 4px;
    }

    .form-actions {
      display: flex;
      gap: 16px;
      margin-top: 24px;
    }

    .read-only-notice {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 16px;
      background: #fff3e0;
      color: #e65100;
      border-radius: 4px;
      margin-top: 24px;
    }

    .side-panel {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    /* Meta Card Styles */
    .meta-card {
      border-radius: 12px;
    }

    .meta-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px !important;
      font-weight: 500 !important;
      color: #1a1a1a;
    }

    .meta-card-title mat-icon {
      color: #1976d2;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .meta-card mat-card-content {
      padding-top: 8px;
    }

    .meta-item {
      padding: 16px;
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
      margin-bottom: 8px;
    }

    .meta-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #757575;
    }

    .meta-label {
      font-size: 12px;
      font-weight: 600;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .meta-value {
      display: block;
      font-size: 15px;
      font-weight: 600;
      color: #1a1a1a;
      margin-bottom: 2px;
    }

    .meta-time {
      display: block;
      font-size: 13px;
      color: #888;
    }

    .meta-user {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: #555;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid #e9ecef;
    }

    .meta-user mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      color: #888;
    }

    /* History Card Styles */
    .history-card {
      border-radius: 12px;
    }

    .history-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px !important;
      font-weight: 500 !important;
      color: #1a1a1a;
    }

    .history-card-title mat-icon {
      color: #1976d2;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .history-count {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 24px;
      height: 24px;
      padding: 0 8px;
      background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
      border-radius: 12px;
      font-size: 13px;
      font-weight: 600;
      color: #1565c0;
      margin-left: auto;
    }

    .history-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .history-entry {
      background: #f8f9fa;
      border-radius: 10px;
      overflow: hidden;
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
      border-color: #1976d2;
      box-shadow: 0 4px 12px rgba(25, 118, 210, 0.15);
    }

    .history-entry-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 16px;
    }

    .history-entry-date {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .date-primary {
      font-size: 14px;
      font-weight: 600;
      color: #1a1a1a;
    }

    .date-secondary {
      font-size: 12px;
      color: #888;
    }

    .history-entry-meta {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .history-entry-user {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: #555;
    }

    .history-entry-user mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      color: #888;
    }

    .expand-icon {
      color: #9e9e9e;
      transition: transform 0.2s ease;
    }

    .history-entry.expanded .expand-icon {
      color: #1976d2;
    }

    .history-entry-content {
      padding: 0 16px 16px 16px;
      border-top: 1px solid #e9ecef;
    }

    .change-reason {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
      padding: 12px 16px;
      border-radius: 8px;
      margin: 16px 0;
      border-left: 4px solid #ffc107;
    }

    .change-reason mat-icon {
      color: #f57c00;
      font-size: 20px;
      width: 20px;
      height: 20px;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .change-reason span {
      font-size: 14px;
      color: #5d4037;
      line-height: 1.5;
    }

    .history-snapshot {
      padding-top: 16px;
    }

    .snapshot-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid #eee;
    }

    .snapshot-title {
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: #1a1a1a;
      flex: 1;
    }

    .status-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 500;
      padding: 6px 12px;
      border-radius: 20px;
      flex-shrink: 0;
    }

    .status-chip .status-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    .snapshot-field {
      margin-bottom: 12px;
      background: #f8f9fa;
      border-radius: 8px;
      padding: 12px 14px;
    }

    .snapshot-field:last-child {
      margin-bottom: 0;
    }

    .snapshot-label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 11px;
      font-weight: 600;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 6px;
    }

    .snapshot-label mat-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
      color: #9e9e9e;
    }

    .snapshot-value {
      font-size: 13px;
      color: #333;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .status-proposed { background-color: #fff3e0 !important; color: #e65100 !important; }
    .status-accepted { background-color: #e8f5e9 !important; color: #2e7d32 !important; }
    .status-deprecated { background-color: #ffebee !important; color: #c62828 !important; }
    .status-superseded { background-color: #e3f2fd !important; color: #1565c0 !important; }

    .default-space-badge {
      font-size: 11px;
      color: #888;
      margin-left: 4px;
    }

    .owner-section {
      margin-top: 16px;
      padding: 16px;
      background: #f5f5f5;
      border-radius: 8px;
    }

    .owner-section h4 {
      margin: 0 0 4px 0;
      font-size: 14px;
      font-weight: 500;
    }

    .owner-hint {
      margin: 0 0 12px 0;
      font-size: 12px;
      color: #666;
    }

    .owner-fields {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .owner-select-field {
      flex: 1;
      min-width: 200px;
    }

    .owner-email-field {
      flex: 1;
      min-width: 200px;
    }

    .or-divider {
      color: #888;
      font-size: 12px;
      font-style: italic;
    }
  `]
})
export class DecisionDetailComponent implements OnInit {
  decision: Decision | null = null;
  form: FormGroup;
  isNew = false;
  isLoading = true;
  isSaving = false;
  tenant = '';
  expandedHistoryIndex: number | null = null;

  // Spaces
  spaces: Space[] = [];
  selectedSpaceIds: number[] = [];

  // Decision owner
  tenantMembers: any[] = [];
  selectedOwnerId: number | null = null;
  ownerEmail: string = '';

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private decisionService: DecisionService,
    public authService: AuthService,
    private spaceService: SpaceService,
    private adminService: AdminService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {
    this.form = this.fb.group({
      title: ['', Validators.required],
      status: ['proposed', Validators.required],
      context: [''],  // Optional - users can add details later
      decision: [''],  // Optional - users can add details later
      consequences: [''],  // Optional - users can add details later
      change_reason: ['']
    });
  }

  ngOnInit(): void {
    // Get tenant from route params
    this.tenant = this.route.snapshot.paramMap.get('tenant') || '';

    // Load spaces
    this.loadSpaces();

    // Load tenant members for owner selection
    this.loadTenantMembers();

    const id = this.route.snapshot.params['id'];
    // Check if this is a new decision - either no id param (route is /decision/new) or id is undefined
    if (!id || id === 'new') {
      this.isNew = true;
      this.isLoading = false;
      if (this.authService.isMasterAccount) {
        this.form.disable();
      }
    } else {
      this.loadDecision(+id);
    }
  }

  loadTenantMembers(): void {
    this.adminService.getUsers().subscribe({
      next: (users) => {
        this.tenantMembers = users;
      },
      error: (err) => {
        console.error('Failed to load tenant members', err);
      }
    });
  }

  loadSpaces(): void {
    this.spaceService.getSpaces().subscribe({
      next: (spaces) => {
        this.spaces = spaces;
        // For new decisions, pre-select the default space
        if (this.isNew && this.selectedSpaceIds.length === 0) {
          const defaultSpace = spaces.find(s => s.is_default);
          if (defaultSpace) {
            this.selectedSpaceIds = [defaultSpace.id];
          }
        }
      },
      error: (err) => {
        console.error('Failed to load spaces', err);
      }
    });
  }

  getStatusIcon(status: string): string {
    const icons: Record<string, string> = {
      'proposed': 'schedule',
      'accepted': 'check_circle',
      'deprecated': 'warning',
      'superseded': 'swap_horiz'
    };
    return icons[status] || 'help';
  }

  toggleHistoryEntry(index: number): void {
    this.expandedHistoryIndex = this.expandedHistoryIndex === index ? null : index;
  }

  loadDecision(id: number): void {
    this.decisionService.getDecision(id).subscribe({
      next: (decision) => {
        this.decision = decision;
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
        this.selectedOwnerId = (decision as any).owner_id || null;
        this.ownerEmail = (decision as any).owner_email || '';
        if (this.authService.isMasterAccount) {
          this.form.disable();
        }
        this.isLoading = false;
      },
      error: () => {
        this.snackBar.open('Decision not found', 'Close', { duration: 3000 });
        this.router.navigate(['/']);
      }
    });
  }

  onSubmit(): void {
    if (this.form.invalid || this.authService.isMasterAccount) return;

    this.isSaving = true;
    const formValue = this.form.value;

    if (this.isNew) {
      this.decisionService.createDecision({
        title: formValue.title,
        context: formValue.context,
        decision: formValue.decision,
        status: formValue.status,
        consequences: formValue.consequences,
        space_ids: this.selectedSpaceIds,
        owner_id: this.selectedOwnerId,
        owner_email: this.ownerEmail || undefined
      } as any).subscribe({
        next: (decision) => {
          this.snackBar.open('Decision created successfully', 'Close', { duration: 3000 });
          this.router.navigate(['/', this.tenant, 'decision', decision.id]);
        },
        error: (err) => {
          this.isSaving = false;
          this.snackBar.open(err.error?.error || 'Failed to create decision', 'Close', { duration: 3000 });
        }
      });
    } else {
      const update: any = {
        title: formValue.title,
        context: formValue.context,
        decision: formValue.decision,
        status: formValue.status,
        consequences: formValue.consequences,
        space_ids: this.selectedSpaceIds,
        owner_id: this.selectedOwnerId,
        owner_email: this.ownerEmail || undefined
      };
      if (formValue.change_reason) {
        update.change_reason = formValue.change_reason;
      }

      this.decisionService.updateDecision(this.decision!.id, update).subscribe({
        next: (decision) => {
          this.decision = decision;
          this.selectedSpaceIds = decision.spaces?.map(s => s.id) || [];
          this.form.get('change_reason')?.reset();
          this.isSaving = false;
          this.snackBar.open('Decision updated successfully', 'Close', { duration: 3000 });
        },
        error: (err) => {
          this.isSaving = false;
          this.snackBar.open(err.error?.error || 'Failed to update decision', 'Close', { duration: 3000 });
        }
      });
    }
  }

  confirmDelete(): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete Decision',
        message: `Are you sure you want to delete ${this.decision?.display_id || 'ADR-' + this.decision?.id}? This action cannot be undone.`,
        confirmText: 'Delete',
        cancelText: 'Cancel'
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
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to delete decision', 'Close', { duration: 3000 });
      }
    });
  }
}
