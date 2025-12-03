import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { DecisionService, UpdateDecisionRequest } from '../../services/decision.service';
import { AuthService } from '../../services/auth.service';
import { Decision, DecisionHistory, DecisionStatus } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';

@Component({
  selector: 'app-decision-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatExpansionModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDialogModule,
    MatTooltipModule,
    ConfirmDialogComponent
  ],
  template: `
    <div class="decision-detail-container">
      <div class="header">
        <button mat-button routerLink="/">
          <mat-icon>arrow_back</mat-icon>
          Back to Decisions
        </button>
        <h1>{{ isNew ? 'New Decision' : 'ADR-' + decision?.id }}</h1>
      </div>

      @if (isLoading) {
        <div class="loading-container">
          <mat-spinner></mat-spinner>
        </div>
      } @else {
        <div class="content-grid">
          <mat-card class="main-card">
            <mat-card-content>
              <form [formGroup]="form" (ngSubmit)="onSubmit()">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Title</mat-label>
                  <input matInput formControlName="title" placeholder="Short, descriptive title">
                  @if (form.get('title')?.hasError('required')) {
                    <mat-error>Title is required</mat-error>
                  }
                </mat-form-field>

                <mat-form-field appearance="outline" class="full-width">
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
                      @if (isSaving) {
                        <mat-spinner diameter="20"></mat-spinner>
                      } @else {
                        <mat-icon>save</mat-icon>
                        {{ isNew ? 'Create Decision' : 'Save Changes' }}
                      }
                    </button>

                    @if (!isNew) {
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
              <mat-card class="meta-card">
                <mat-card-header>
                  <mat-card-title>Details</mat-card-title>
                </mat-card-header>
                <mat-card-content>
                  <div class="meta-item">
                    <span class="label">Created</span>
                    <span class="value">{{ decision.created_at | date:'medium' }}</span>
                    @if (decision.created_by) {
                      <span class="user">by {{ decision.created_by.name || decision.created_by.email }}</span>
                    }
                  </div>
                  <div class="meta-item">
                    <span class="label">Last Updated</span>
                    <span class="value">{{ decision.updated_at | date:'medium' }}</span>
                    @if (decision.updated_by) {
                      <span class="user">by {{ decision.updated_by.name || decision.updated_by.email }}</span>
                    }
                  </div>
                  @if (decision.domain) {
                    <div class="meta-item">
                      <span class="label">Domain</span>
                      <span class="value">{{ decision.domain }}</span>
                    </div>
                  }
                </mat-card-content>
              </mat-card>

              @if (decision.history && decision.history.length > 0) {
                <mat-card class="history-card">
                  <mat-card-header>
                    <mat-card-title>
                      <mat-icon>history</mat-icon>
                      Change History
                    </mat-card-title>
                  </mat-card-header>
                  <mat-card-content>
                    <mat-accordion>
                      @for (item of decision.history; track item.id) {
                        <mat-expansion-panel>
                          <mat-expansion-panel-header>
                            <mat-panel-title>
                              {{ item.changed_at | date:'medium' }}
                            </mat-panel-title>
                            <mat-panel-description>
                              @if (item.changed_by) {
                                {{ item.changed_by.name || item.changed_by.email }}
                              }
                            </mat-panel-description>
                          </mat-expansion-panel-header>
                          @if (item.change_reason) {
                            <p class="change-reason">
                              <strong>Reason:</strong> {{ item.change_reason }}
                            </p>
                          }
                          <div class="history-content">
                            <h4>Title</h4>
                            <p>{{ item.title }}</p>
                            <h4>Status</h4>
                            <mat-chip [ngClass]="'status-' + item.status">{{ item.status }}</mat-chip>
                            <h4>Context</h4>
                            <p>{{ item.context }}</p>
                            <h4>Decision</h4>
                            <p>{{ item.decision }}</p>
                            <h4>Consequences</h4>
                            <p>{{ item.consequences }}</p>
                          </div>
                        </mat-expansion-panel>
                      }
                    </mat-accordion>
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
      padding: 24px;
    }

    .full-width {
      width: 100%;
    }

    mat-form-field {
      margin-bottom: 16px;
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
      gap: 16px;
    }

    .meta-card mat-card-content {
      padding-top: 16px;
    }

    .meta-item {
      margin-bottom: 16px;
    }

    .meta-item .label {
      display: block;
      font-size: 12px;
      color: #888;
      text-transform: uppercase;
    }

    .meta-item .value {
      display: block;
      font-weight: 500;
    }

    .meta-item .user {
      display: block;
      font-size: 12px;
      color: #666;
    }

    .history-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .change-reason {
      background: #f5f5f5;
      padding: 8px;
      border-radius: 4px;
      margin-bottom: 16px;
    }

    .history-content h4 {
      margin: 16px 0 4px 0;
      font-size: 12px;
      color: #888;
      text-transform: uppercase;
    }

    .history-content p {
      margin: 0;
      white-space: pre-wrap;
    }

    .status-proposed { background-color: #fff3e0 !important; color: #e65100 !important; }
    .status-accepted { background-color: #e8f5e9 !important; color: #2e7d32 !important; }
    .status-deprecated { background-color: #ffebee !important; color: #c62828 !important; }
    .status-superseded { background-color: #e3f2fd !important; color: #1565c0 !important; }
  `]
})
export class DecisionDetailComponent implements OnInit {
  decision: Decision | null = null;
  form: FormGroup;
  isNew = false;
  isLoading = true;
  isSaving = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private decisionService: DecisionService,
    public authService: AuthService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {
    this.form = this.fb.group({
      title: ['', Validators.required],
      status: ['proposed', Validators.required],
      context: ['', Validators.required],
      decision: ['', Validators.required],
      consequences: ['', Validators.required],
      change_reason: ['']
    });
  }

  ngOnInit(): void {
    const id = this.route.snapshot.params['id'];
    if (id === 'new') {
      this.isNew = true;
      this.isLoading = false;
      if (this.authService.isMasterAccount) {
        this.form.disable();
      }
    } else {
      this.loadDecision(+id);
    }
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
        consequences: formValue.consequences
      }).subscribe({
        next: (decision) => {
          this.snackBar.open('Decision created successfully', 'Close', { duration: 3000 });
          this.router.navigate(['/decision', decision.id]);
        },
        error: (err) => {
          this.isSaving = false;
          this.snackBar.open(err.error?.error || 'Failed to create decision', 'Close', { duration: 3000 });
        }
      });
    } else {
      const update: UpdateDecisionRequest = {
        title: formValue.title,
        context: formValue.context,
        decision: formValue.decision,
        status: formValue.status,
        consequences: formValue.consequences
      };
      if (formValue.change_reason) {
        update.change_reason = formValue.change_reason;
      }

      this.decisionService.updateDecision(this.decision!.id, update).subscribe({
        next: (decision) => {
          this.decision = decision;
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
        message: `Are you sure you want to delete ADR-${this.decision?.id}? This action cannot be undone.`,
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
