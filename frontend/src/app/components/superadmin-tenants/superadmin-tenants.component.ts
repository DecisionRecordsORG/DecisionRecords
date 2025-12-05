import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatTabsModule } from '@angular/material/tabs';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';

interface DomainApproval {
  id: number;
  domain: string;
  status: 'pending' | 'approved' | 'rejected';
  requested_by_email: string;
  requested_by_name: string;
  rejection_reason: string | null;
  created_at: string;
  reviewed_at: string | null;
}

interface Tenant {
  domain: string;
  user_count: number;
  admin_count: number;
  has_sso: boolean;
  created_at: string;
}

@Component({
  selector: 'app-superadmin-tenants',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTableModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDialogModule,
    MatTabsModule,
    MatFormFieldModule,
    MatInputModule,
    ConfirmDialogComponent
  ],
  template: `
    <div class="tenants-container">
      <h1>
        <mat-icon>business</mat-icon>
        Tenant Management
      </h1>

      <mat-tab-group>
        <!-- Pending Approvals Tab -->
        <mat-tab>
          <ng-template mat-tab-label>
            <mat-icon class="tab-icon">pending_actions</mat-icon>
            Pending Approvals
            @if (pendingApprovals.length > 0) {
              <span class="badge">{{ pendingApprovals.length }}</span>
            }
          </ng-template>
          <div class="tab-content">
            <mat-card>
              <mat-card-header>
                <mat-card-title>Domain Approval Requests</mat-card-title>
                <mat-card-subtitle>
                  New organizations requesting access to the system
                </mat-card-subtitle>
              </mat-card-header>
              <mat-card-content>
                @if (isLoading) {
                  <div class="loading">
                    <mat-spinner diameter="40"></mat-spinner>
                    <span>Loading pending approvals...</span>
                  </div>
                } @else if (pendingApprovals.length === 0) {
                  <div class="empty-state">
                    <mat-icon>check_circle</mat-icon>
                    <p>No pending domain approvals</p>
                  </div>
                } @else {
                  <table mat-table [dataSource]="pendingApprovals" class="full-width">
                    <ng-container matColumnDef="domain">
                      <th mat-header-cell *matHeaderCellDef>Domain</th>
                      <td mat-cell *matCellDef="let approval">
                        <strong>{{ approval.domain }}</strong>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="requested_by">
                      <th mat-header-cell *matHeaderCellDef>Requested By</th>
                      <td mat-cell *matCellDef="let approval">
                        <div>{{ approval.requested_by_name }}</div>
                        <small class="email">{{ approval.requested_by_email }}</small>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="created_at">
                      <th mat-header-cell *matHeaderCellDef>Requested</th>
                      <td mat-cell *matCellDef="let approval">
                        {{ approval.created_at | date:'medium' }}
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="actions">
                      <th mat-header-cell *matHeaderCellDef>Actions</th>
                      <td mat-cell *matCellDef="let approval">
                        <button mat-raised-button color="primary"
                                (click)="approveDomain(approval)"
                                [disabled]="processingId === approval.id">
                          @if (processingId === approval.id && processingAction === 'approve') {
                            <mat-spinner diameter="18"></mat-spinner>
                          } @else {
                            <mat-icon>check</mat-icon>
                            Approve
                          }
                        </button>
                        <button mat-button color="warn"
                                (click)="rejectDomain(approval)"
                                [disabled]="processingId === approval.id">
                          @if (processingId === approval.id && processingAction === 'reject') {
                            <mat-spinner diameter="18"></mat-spinner>
                          } @else {
                            <mat-icon>close</mat-icon>
                            Reject
                          }
                        </button>
                      </td>
                    </ng-container>

                    <tr mat-header-row *matHeaderRowDef="pendingColumns"></tr>
                    <tr mat-row *matRowDef="let row; columns: pendingColumns;"></tr>
                  </table>
                }
              </mat-card-content>
            </mat-card>
          </div>
        </mat-tab>

        <!-- All Tenants Tab -->
        <mat-tab>
          <ng-template mat-tab-label>
            <mat-icon class="tab-icon">domain</mat-icon>
            All Tenants
          </ng-template>
          <div class="tab-content">
            <mat-card>
              <mat-card-header>
                <mat-card-title>Registered Tenants</mat-card-title>
                <mat-card-subtitle>
                  All organizations with approved domains
                </mat-card-subtitle>
              </mat-card-header>
              <mat-card-content>
                @if (isLoadingTenants) {
                  <div class="loading">
                    <mat-spinner diameter="40"></mat-spinner>
                    <span>Loading tenants...</span>
                  </div>
                } @else if (tenants.length === 0) {
                  <div class="empty-state">
                    <mat-icon>business</mat-icon>
                    <p>No registered tenants yet</p>
                  </div>
                } @else {
                  <table mat-table [dataSource]="tenants" class="full-width">
                    <ng-container matColumnDef="domain">
                      <th mat-header-cell *matHeaderCellDef>Domain</th>
                      <td mat-cell *matCellDef="let tenant">
                        <strong>{{ tenant.domain }}</strong>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="user_count">
                      <th mat-header-cell *matHeaderCellDef>Users</th>
                      <td mat-cell *matCellDef="let tenant">
                        {{ tenant.user_count }}
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="admin_count">
                      <th mat-header-cell *matHeaderCellDef>Admins</th>
                      <td mat-cell *matCellDef="let tenant">
                        {{ tenant.admin_count }}
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="has_sso">
                      <th mat-header-cell *matHeaderCellDef>SSO</th>
                      <td mat-cell *matCellDef="let tenant">
                        <mat-chip [class.configured]="tenant.has_sso">
                          {{ tenant.has_sso ? 'Configured' : 'Not configured' }}
                        </mat-chip>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="created_at">
                      <th mat-header-cell *matHeaderCellDef>Created</th>
                      <td mat-cell *matCellDef="let tenant">
                        {{ tenant.created_at | date:'mediumDate' }}
                      </td>
                    </ng-container>

                    <tr mat-header-row *matHeaderRowDef="tenantColumns"></tr>
                    <tr mat-row *matRowDef="let row; columns: tenantColumns;"></tr>
                  </table>
                }
              </mat-card-content>
            </mat-card>
          </div>
        </mat-tab>

        <!-- Domain History Tab -->
        <mat-tab>
          <ng-template mat-tab-label>
            <mat-icon class="tab-icon">history</mat-icon>
            History
          </ng-template>
          <div class="tab-content">
            <mat-card>
              <mat-card-header>
                <mat-card-title>Domain Approval History</mat-card-title>
                <mat-card-subtitle>
                  All domain approval requests and their outcomes
                </mat-card-subtitle>
              </mat-card-header>
              <mat-card-content>
                @if (isLoadingHistory) {
                  <div class="loading">
                    <mat-spinner diameter="40"></mat-spinner>
                    <span>Loading history...</span>
                  </div>
                } @else if (allApprovals.length === 0) {
                  <div class="empty-state">
                    <mat-icon>history</mat-icon>
                    <p>No domain approval history</p>
                  </div>
                } @else {
                  <table mat-table [dataSource]="allApprovals" class="full-width">
                    <ng-container matColumnDef="domain">
                      <th mat-header-cell *matHeaderCellDef>Domain</th>
                      <td mat-cell *matCellDef="let approval">
                        <strong>{{ approval.domain }}</strong>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="status">
                      <th mat-header-cell *matHeaderCellDef>Status</th>
                      <td mat-cell *matCellDef="let approval">
                        <mat-chip [class]="approval.status">
                          {{ approval.status | titlecase }}
                        </mat-chip>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="requested_by">
                      <th mat-header-cell *matHeaderCellDef>Requested By</th>
                      <td mat-cell *matCellDef="let approval">
                        {{ approval.requested_by_email }}
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="created_at">
                      <th mat-header-cell *matHeaderCellDef>Requested</th>
                      <td mat-cell *matCellDef="let approval">
                        {{ approval.created_at | date:'medium' }}
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="reviewed_at">
                      <th mat-header-cell *matHeaderCellDef>Reviewed</th>
                      <td mat-cell *matCellDef="let approval">
                        {{ approval.reviewed_at ? (approval.reviewed_at | date:'medium') : '-' }}
                      </td>
                    </ng-container>

                    <tr mat-header-row *matHeaderRowDef="historyColumns"></tr>
                    <tr mat-row *matRowDef="let row; columns: historyColumns;"></tr>
                  </table>
                }
              </mat-card-content>
            </mat-card>
          </div>
        </mat-tab>
      </mat-tab-group>
    </div>
  `,
  styles: [`
    .tenants-container {
      padding: 24px;
      max-width: 1200px;
      margin: 0 auto;
    }

    h1 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 24px;
    }

    .tab-icon {
      margin-right: 8px;
    }

    .badge {
      background: #f44336;
      color: white;
      border-radius: 50%;
      padding: 2px 8px;
      font-size: 12px;
      margin-left: 8px;
    }

    .tab-content {
      padding: 24px 0;
    }

    .full-width {
      width: 100%;
    }

    .loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 48px;
      gap: 16px;
      color: #666;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 48px;
      color: #888;
    }

    .empty-state mat-icon {
      font-size: 48px;
      height: 48px;
      width: 48px;
      margin-bottom: 16px;
      color: #ccc;
    }

    table {
      margin-top: 16px;
    }

    .email {
      color: #666;
    }

    mat-chip {
      font-size: 12px;
    }

    mat-chip.pending {
      background: #fff3e0 !important;
      color: #e65100 !important;
    }

    mat-chip.approved, mat-chip.configured {
      background: #e8f5e9 !important;
      color: #2e7d32 !important;
    }

    mat-chip.rejected {
      background: #ffebee !important;
      color: #c62828 !important;
    }

    td button {
      margin-right: 8px;
    }

    td button mat-icon {
      margin-right: 4px;
    }
  `]
})
export class SuperadminTenantsComponent implements OnInit {
  pendingApprovals: DomainApproval[] = [];
  allApprovals: DomainApproval[] = [];
  tenants: Tenant[] = [];

  isLoading = true;
  isLoadingTenants = true;
  isLoadingHistory = true;

  processingId: number | null = null;
  processingAction: 'approve' | 'reject' | null = null;

  rejectionReason = '';

  pendingColumns = ['domain', 'requested_by', 'created_at', 'actions'];
  tenantColumns = ['domain', 'user_count', 'admin_count', 'has_sso', 'created_at'];
  historyColumns = ['domain', 'status', 'requested_by', 'created_at', 'reviewed_at'];

  constructor(
    private http: HttpClient,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {}

  ngOnInit(): void {
    this.loadPendingApprovals();
    this.loadTenants();
    this.loadAllApprovals();
  }

  loadPendingApprovals(): void {
    this.isLoading = true;
    this.http.get<DomainApproval[]>('/api/domains/pending').subscribe({
      next: (approvals) => {
        this.pendingApprovals = approvals;
        this.isLoading = false;
      },
      error: () => {
        this.snackBar.open('Failed to load pending approvals', 'Close', { duration: 3000 });
        this.isLoading = false;
      }
    });
  }

  loadTenants(): void {
    this.isLoadingTenants = true;
    this.http.get<Tenant[]>('/api/tenants').subscribe({
      next: (tenants) => {
        this.tenants = tenants;
        this.isLoadingTenants = false;
      },
      error: () => {
        this.snackBar.open('Failed to load tenants', 'Close', { duration: 3000 });
        this.isLoadingTenants = false;
      }
    });
  }

  loadAllApprovals(): void {
    this.isLoadingHistory = true;
    this.http.get<DomainApproval[]>('/api/domains').subscribe({
      next: (approvals) => {
        this.allApprovals = approvals;
        this.isLoadingHistory = false;
      },
      error: () => {
        this.snackBar.open('Failed to load history', 'Close', { duration: 3000 });
        this.isLoadingHistory = false;
      }
    });
  }

  approveDomain(approval: DomainApproval): void {
    this.processingId = approval.id;
    this.processingAction = 'approve';

    this.http.post(`/api/domains/${approval.id}/approve`, {}).subscribe({
      next: () => {
        this.snackBar.open(`Domain ${approval.domain} approved`, 'Close', { duration: 3000 });
        this.processingId = null;
        this.processingAction = null;
        this.loadPendingApprovals();
        this.loadTenants();
        this.loadAllApprovals();
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to approve domain', 'Close', { duration: 3000 });
        this.processingId = null;
        this.processingAction = null;
      }
    });
  }

  rejectDomain(approval: DomainApproval): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Reject Domain',
        message: `Are you sure you want to reject ${approval.domain}? Please provide a reason.`,
        confirmText: 'Reject',
        cancelText: 'Cancel',
        showInput: true,
        inputLabel: 'Rejection Reason'
      }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.processingId = approval.id;
        this.processingAction = 'reject';

        this.http.post(`/api/domains/${approval.id}/reject`, {
          reason: result.inputValue || 'No reason provided'
        }).subscribe({
          next: () => {
            this.snackBar.open(`Domain ${approval.domain} rejected`, 'Close', { duration: 3000 });
            this.processingId = null;
            this.processingAction = null;
            this.loadPendingApprovals();
            this.loadAllApprovals();
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to reject domain', 'Close', { duration: 3000 });
            this.processingId = null;
            this.processingAction = null;
          }
        });
      }
    });
  }
}
