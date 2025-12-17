import { Component, OnInit, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialogModule, MatDialog, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatTabsModule } from '@angular/material/tabs';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { Clipboard } from '@angular/cdk/clipboard';
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

interface MaturityThresholds {
  age_days: number;
  user_threshold: number;
  admin_threshold: number;
}

interface Tenant {
  domain: string;
  user_count: number;
  admin_count: number;
  steward_count: number;
  has_sso: boolean;
  created_at: string;
  maturity_state: 'bootstrap' | 'mature' | null;
  age_days: number | null;
  maturity_thresholds?: MaturityThresholds;
}

interface SlackLinkedUser {
  id: number;
  name: string;
  email: string;
  slack_user_id: string;
  link_method: string;
  linked_at: string | null;
}

interface SlackClaimedBy {
  id: number;
  name: string;
  email: string;
}

interface SlackWorkspace {
  id: number;
  workspace_id: string;
  workspace_name: string;
  tenant_id: number | null;
  tenant_domain: string | null;
  is_active: boolean;
  status: string;
  installed_at: string | null;
  claimed_at: string | null;
  claimed_by: SlackClaimedBy | null;
  linked_users_count: number;
  linked_users: SlackLinkedUser[];
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
    MatTooltipModule,
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
                          <mat-spinner diameter="18" *ngIf="processingId === approval.id && processingAction === 'approve'"></mat-spinner>
                          <mat-icon *ngIf="!(processingId === approval.id && processingAction === 'approve')">check</mat-icon>
                          <span *ngIf="!(processingId === approval.id && processingAction === 'approve')">Approve</span>
                        </button>
                        <button mat-button color="warn"
                                (click)="rejectDomain(approval)"
                                [disabled]="processingId === approval.id">
                          <mat-spinner diameter="18" *ngIf="processingId === approval.id && processingAction === 'reject'"></mat-spinner>
                          <mat-icon *ngIf="!(processingId === approval.id && processingAction === 'reject')">close</mat-icon>
                          <span *ngIf="!(processingId === approval.id && processingAction === 'reject')">Reject</span>
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

                    <ng-container matColumnDef="login_url">
                      <th mat-header-cell *matHeaderCellDef>Login URL</th>
                      <td mat-cell *matCellDef="let tenant">
                        <div class="login-url-cell">
                          <code class="login-url">{{ getLoginUrl(tenant.domain) }}</code>
                          <button mat-icon-button
                                  (click)="copyLoginUrl(tenant.domain)"
                                  matTooltip="Copy login URL">
                            <mat-icon>content_copy</mat-icon>
                          </button>
                        </div>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="maturity_state">
                      <th mat-header-cell *matHeaderCellDef>Maturity</th>
                      <td mat-cell *matCellDef="let tenant">
                        @if (tenant.maturity_state) {
                          <mat-chip [class]="tenant.maturity_state">
                            {{ tenant.maturity_state | titlecase }}
                          </mat-chip>
                        } @else {
                          <span class="na-text">N/A</span>
                        }
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

                    <ng-container matColumnDef="steward_count">
                      <th mat-header-cell *matHeaderCellDef>Stewards</th>
                      <td mat-cell *matCellDef="let tenant">
                        {{ tenant.steward_count }}
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="age_days">
                      <th mat-header-cell *matHeaderCellDef>Age (days)</th>
                      <td mat-cell *matCellDef="let tenant">
                        {{ tenant.age_days !== null ? tenant.age_days : 'N/A' }}
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="has_sso">
                      <th mat-header-cell *matHeaderCellDef>SSO</th>
                      <td mat-cell *matCellDef="let tenant">
                        <mat-chip [class.configured]="tenant.has_sso">
                          {{ tenant.has_sso ? 'Yes' : 'No' }}
                        </mat-chip>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="created_at">
                      <th mat-header-cell *matHeaderCellDef>Created</th>
                      <td mat-cell *matCellDef="let tenant">
                        {{ tenant.created_at | date:'mediumDate' }}
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="actions">
                      <th mat-header-cell *matHeaderCellDef>Actions</th>
                      <td mat-cell *matCellDef="let tenant">
                        <button mat-icon-button
                                (click)="openTenantDetails(tenant)"
                                matTooltip="View details">
                          <mat-icon>info</mat-icon>
                        </button>
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

        <!-- Slack Integrations Tab -->
        <mat-tab>
          <ng-template mat-tab-label>
            <mat-icon class="tab-icon">tag</mat-icon>
            Slack Integrations
          </ng-template>
          <div class="tab-content">
            <mat-card>
              <mat-card-header>
                <mat-card-title>Slack Workspace Connections</mat-card-title>
                <mat-card-subtitle>
                  All Slack workspaces connected to the platform
                </mat-card-subtitle>
              </mat-card-header>
              <mat-card-content>
                @if (isLoadingSlack) {
                  <div class="loading">
                    <mat-spinner diameter="40"></mat-spinner>
                    <span>Loading Slack workspaces...</span>
                  </div>
                } @else if (slackWorkspaces.length === 0) {
                  <div class="empty-state">
                    <mat-icon>tag</mat-icon>
                    <p>No Slack workspaces connected</p>
                  </div>
                } @else {
                  <table mat-table [dataSource]="slackWorkspaces" class="full-width">
                    <ng-container matColumnDef="workspace_name">
                      <th mat-header-cell *matHeaderCellDef>Workspace</th>
                      <td mat-cell *matCellDef="let ws">
                        <strong>{{ ws.workspace_name || 'Unknown' }}</strong>
                        <div class="workspace-id">{{ ws.workspace_id }}</div>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="tenant_domain">
                      <th mat-header-cell *matHeaderCellDef>Tenant</th>
                      <td mat-cell *matCellDef="let ws">
                        @if (ws.tenant_domain) {
                          <span>{{ ws.tenant_domain }}</span>
                        } @else {
                          <span class="na-text">Unassigned</span>
                        }
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="status">
                      <th mat-header-cell *matHeaderCellDef>Status</th>
                      <td mat-cell *matCellDef="let ws">
                        <mat-chip [class]="ws.is_active ? 'active' : 'disconnected'">
                          {{ ws.is_active ? 'Active' : 'Disconnected' }}
                        </mat-chip>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="claimed_by">
                      <th mat-header-cell *matHeaderCellDef>Connected By</th>
                      <td mat-cell *matCellDef="let ws">
                        @if (ws.claimed_by) {
                          <div>{{ ws.claimed_by.name }}</div>
                          <small class="email">{{ ws.claimed_by.email }}</small>
                        } @else {
                          <span class="na-text">-</span>
                        }
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="claimed_at">
                      <th mat-header-cell *matHeaderCellDef>Connected</th>
                      <td mat-cell *matCellDef="let ws">
                        {{ ws.claimed_at ? (ws.claimed_at | date:'medium') : (ws.installed_at | date:'medium') }}
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="linked_users_count">
                      <th mat-header-cell *matHeaderCellDef>Linked Users</th>
                      <td mat-cell *matCellDef="let ws">
                        <span class="linked-count"
                              [class.has-users]="ws.linked_users_count > 0"
                              (click)="ws.linked_users_count > 0 && openLinkedUsersDialog(ws)"
                              [style.cursor]="ws.linked_users_count > 0 ? 'pointer' : 'default'">
                          {{ ws.linked_users_count }}
                        </span>
                      </td>
                    </ng-container>

                    <ng-container matColumnDef="actions">
                      <th mat-header-cell *matHeaderCellDef>Actions</th>
                      <td mat-cell *matCellDef="let ws">
                        <button mat-icon-button
                                color="warn"
                                (click)="disconnectSlackWorkspace(ws)"
                                [disabled]="!ws.is_active || deletingWorkspaceId === ws.id"
                                matTooltip="Disconnect workspace">
                          @if (deletingWorkspaceId === ws.id) {
                            <mat-spinner diameter="18"></mat-spinner>
                          } @else {
                            <mat-icon>link_off</mat-icon>
                          }
                        </button>
                      </td>
                    </ng-container>

                    <tr mat-header-row *matHeaderRowDef="slackColumns"></tr>
                    <tr mat-row *matRowDef="let row; columns: slackColumns;"></tr>
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

    mat-chip.bootstrap {
      background: #fff3e0 !important;
      color: #e65100 !important;
    }

    mat-chip.mature {
      background: #e8f5e9 !important;
      color: #2e7d32 !important;
    }

    .na-text {
      color: #999;
      font-style: italic;
      font-size: 12px;
    }

    td button {
      margin-right: 8px;
    }

    td button mat-icon {
      margin-right: 4px;
    }

    .login-url-cell {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .login-url {
      font-size: 12px;
      background: #f5f5f5;
      padding: 4px 8px;
      border-radius: 4px;
      color: #1976d2;
      max-width: 200px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .login-url-cell button {
      margin-right: 0;
    }

    /* Slack tab styles */
    mat-chip.active {
      background: #e8f5e9 !important;
      color: #2e7d32 !important;
    }

    mat-chip.disconnected {
      background: #ffebee !important;
      color: #c62828 !important;
    }

    .workspace-id {
      font-size: 11px;
      color: #666;
      font-family: monospace;
    }

    .linked-count {
      display: inline-block;
      min-width: 24px;
      text-align: center;
      padding: 4px 8px;
      border-radius: 12px;
      font-weight: 500;
    }

    .linked-count.has-users {
      background: #e3f2fd;
      color: #1976d2;
      text-decoration: underline;
    }
  `]
})
export class SuperadminTenantsComponent implements OnInit {
  pendingApprovals: DomainApproval[] = [];
  allApprovals: DomainApproval[] = [];
  tenants: Tenant[] = [];
  slackWorkspaces: SlackWorkspace[] = [];

  isLoading = true;
  isLoadingTenants = true;
  isLoadingHistory = true;
  isLoadingSlack = true;

  processingId: number | null = null;
  processingAction: 'approve' | 'reject' | null = null;
  deletingWorkspaceId: number | null = null;

  rejectionReason = '';

  pendingColumns = ['domain', 'requested_by', 'created_at', 'actions'];
  tenantColumns = ['domain', 'login_url', 'maturity_state', 'user_count', 'admin_count', 'steward_count', 'age_days', 'has_sso', 'created_at', 'actions'];
  historyColumns = ['domain', 'status', 'requested_by', 'created_at', 'reviewed_at'];
  slackColumns = ['workspace_name', 'tenant_domain', 'status', 'claimed_by', 'claimed_at', 'linked_users_count', 'actions'];

  constructor(
    private http: HttpClient,
    private snackBar: MatSnackBar,
    private dialog: MatDialog,
    private clipboard: Clipboard
  ) {}

  getLoginUrl(domain: string): string {
    return `${window.location.origin}/${domain}/login`;
  }

  copyLoginUrl(domain: string): void {
    const url = this.getLoginUrl(domain);
    this.clipboard.copy(url);
    this.snackBar.open('Login URL copied to clipboard', 'Close', { duration: 2000 });
  }

  ngOnInit(): void {
    this.loadPendingApprovals();
    this.loadTenants();
    this.loadAllApprovals();
    this.loadSlackWorkspaces();
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

  openTenantDetails(tenant: Tenant): void {
    // Load full tenant details including maturity thresholds
    this.http.get<any>(`/api/tenants/${tenant.domain}/maturity`).subscribe({
      next: (details) => {
        const dialogRef = this.dialog.open(TenantDetailsDialogComponent, {
          width: '600px',
          data: {
            tenant: tenant,
            details: details
          }
        });

        dialogRef.afterClosed().subscribe(result => {
          if (result?.action === 'thresholds_updated' || result?.action === 'maturity_upgraded') {
            this.loadTenants();
          } else if (result?.action === 'tenant_deleted') {
            this.loadTenants();
            this.loadPendingApprovals();
            this.loadAllApprovals();
          }
        });
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to load tenant details', 'Close', { duration: 3000 });
      }
    });
  }

  // ==================== Slack Methods ====================

  loadSlackWorkspaces(): void {
    this.isLoadingSlack = true;
    this.http.get<SlackWorkspace[]>('/api/superadmin/slack/workspaces').subscribe({
      next: (workspaces) => {
        this.slackWorkspaces = workspaces;
        this.isLoadingSlack = false;
      },
      error: (err) => {
        // If Slack is not enabled, just show empty state
        if (err.status === 503) {
          this.slackWorkspaces = [];
        } else {
          this.snackBar.open('Failed to load Slack workspaces', 'Close', { duration: 3000 });
        }
        this.isLoadingSlack = false;
      }
    });
  }

  disconnectSlackWorkspace(workspace: SlackWorkspace): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Disconnect Slack Workspace',
        message: `Are you sure you want to disconnect the Slack workspace "${workspace.workspace_name}" from tenant "${workspace.tenant_domain}"? This will remove the connection but not delete the workspace data.`,
        confirmText: 'Disconnect',
        cancelText: 'Cancel',
        isDanger: true
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.deletingWorkspaceId = workspace.id;
        this.http.delete(`/api/superadmin/slack/workspaces/${workspace.id}`).subscribe({
          next: () => {
            this.snackBar.open(`Slack workspace "${workspace.workspace_name}" disconnected`, 'Close', { duration: 3000 });
            this.deletingWorkspaceId = null;
            this.loadSlackWorkspaces();
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to disconnect workspace', 'Close', { duration: 3000 });
            this.deletingWorkspaceId = null;
          }
        });
      }
    });
  }

  openLinkedUsersDialog(workspace: SlackWorkspace): void {
    this.dialog.open(SlackLinkedUsersDialogComponent, {
      width: '600px',
      data: {
        workspace: workspace
      }
    });
  }
}

// ==================== Slack Linked Users Dialog ====================

interface SlackLinkedUsersDialogData {
  workspace: SlackWorkspace;
}

@Component({
  selector: 'app-slack-linked-users-dialog',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatTableModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon>people</mat-icon>
      Linked Users - {{ data.workspace.workspace_name }}
    </h2>
    <mat-dialog-content>
      @if (data.workspace.linked_users.length === 0) {
        <div class="empty-state">
          <mat-icon>person_off</mat-icon>
          <p>No users have linked their accounts</p>
        </div>
      } @else {
        <table mat-table [dataSource]="data.workspace.linked_users" class="full-width">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let user">{{ user.name }}</td>
          </ng-container>

          <ng-container matColumnDef="email">
            <th mat-header-cell *matHeaderCellDef>Email</th>
            <td mat-cell *matCellDef="let user">{{ user.email }}</td>
          </ng-container>

          <ng-container matColumnDef="slack_user_id">
            <th mat-header-cell *matHeaderCellDef>Slack User ID</th>
            <td mat-cell *matCellDef="let user">
              <code>{{ user.slack_user_id }}</code>
            </td>
          </ng-container>

          <ng-container matColumnDef="link_method">
            <th mat-header-cell *matHeaderCellDef>Method</th>
            <td mat-cell *matCellDef="let user">{{ user.link_method || '-' }}</td>
          </ng-container>

          <ng-container matColumnDef="linked_at">
            <th mat-header-cell *matHeaderCellDef>Linked</th>
            <td mat-cell *matCellDef="let user">
              {{ user.linked_at ? (user.linked_at | date:'medium') : '-' }}
            </td>
          </ng-container>

          <tr mat-header-row *matHeaderRowDef="linkedUsersColumns"></tr>
          <tr mat-row *matRowDef="let row; columns: linkedUsersColumns;"></tr>
        </table>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: [`
    h2 {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .full-width {
      width: 100%;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 32px;
      color: #888;
    }

    .empty-state mat-icon {
      font-size: 48px;
      height: 48px;
      width: 48px;
      margin-bottom: 16px;
      color: #ccc;
    }

    code {
      background: #f5f5f5;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 12px;
    }
  `]
})
export class SlackLinkedUsersDialogComponent {
  linkedUsersColumns = ['name', 'email', 'slack_user_id', 'link_method', 'linked_at'];

  constructor(
    public dialogRef: MatDialogRef<SlackLinkedUsersDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: SlackLinkedUsersDialogData
  ) {}
}

// ==================== Tenant Details Dialog ====================

interface TenantDetailsDialogData {
  tenant: Tenant;
  details: any;
}

@Component({
  selector: 'app-tenant-details-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatSnackBarModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon>business</mat-icon>
      Tenant Details: {{ data.tenant.domain }}
    </h2>
    <mat-dialog-content>
      <div class="details-section">
        <h3>Statistics</h3>
        <div class="stats-grid">
          <div class="stat">
            <label>Total Users</label>
            <span>{{ data.tenant.user_count }}</span>
          </div>
          <div class="stat">
            <label>Admins</label>
            <span>{{ data.tenant.admin_count }}</span>
          </div>
          <div class="stat">
            <label>Stewards</label>
            <span>{{ data.tenant.steward_count }}</span>
          </div>
          <div class="stat">
            <label>Age (days)</label>
            <span>{{ data.tenant.age_days !== null ? data.tenant.age_days : 'N/A' }}</span>
          </div>
          <div class="stat">
            <label>Maturity State</label>
            <mat-chip [class]="data.tenant.maturity_state || 'unknown'">
              {{ (data.tenant.maturity_state || 'Unknown') | titlecase }}
            </mat-chip>
          </div>
        </div>
      </div>

      <div class="details-section">
        <h3>Maturity Thresholds</h3>
        <div class="thresholds-grid">
          <mat-form-field appearance="outline">
            <mat-label>Age Days Threshold</mat-label>
            <input matInput type="number" [(ngModel)]="thresholds.age_days" min="1">
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>User Threshold</mat-label>
            <input matInput type="number" [(ngModel)]="thresholds.user_threshold" min="1">
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Admin Threshold</mat-label>
            <input matInput type="number" [(ngModel)]="thresholds.admin_threshold" min="1">
          </mat-form-field>
        </div>
        <button mat-raised-button color="primary"
                (click)="updateThresholds()"
                [disabled]="isUpdating">
          <mat-spinner diameter="18" *ngIf="isUpdating"></mat-spinner>
          <span *ngIf="!isUpdating">Update Thresholds</span>
        </button>
      </div>

      <div class="details-section" *ngIf="data.tenant.maturity_state === 'bootstrap'">
        <h3>Maturity Actions</h3>
        <p class="warning">
          <mat-icon>info</mat-icon>
          This tenant is in Bootstrap state. You can force upgrade to Mature state.
        </p>
        <button mat-raised-button color="accent"
                (click)="forceMaturityUpgrade()"
                [disabled]="isUpgrading">
          <mat-spinner diameter="18" *ngIf="isUpgrading"></mat-spinner>
          <span *ngIf="!isUpgrading">Force Upgrade to Mature</span>
        </button>
      </div>

      <div class="details-section danger-zone">
        <h3>Danger Zone</h3>
        <p class="warning">
          <mat-icon color="warn">warning</mat-icon>
          Deleting a tenant is permanent and cannot be undone.
        </p>
        <button mat-raised-button color="warn"
                (click)="deleteTenant()"
                [disabled]="isDeleting">
          <mat-spinner diameter="18" *ngIf="isDeleting"></mat-spinner>
          <span *ngIf="!isDeleting">Delete Tenant</span>
        </button>
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="close()">Close</button>
    </mat-dialog-actions>
  `,
  styles: [`
    h2 {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .details-section {
      margin-bottom: 24px;
      padding-bottom: 24px;
      border-bottom: 1px solid #e0e0e0;
    }

    .details-section:last-child {
      border-bottom: none;
    }

    h3 {
      margin-top: 0;
      margin-bottom: 16px;
      color: #666;
      font-size: 14px;
      text-transform: uppercase;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
    }

    .stat {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .stat label {
      font-size: 12px;
      color: #666;
      font-weight: 500;
    }

    .stat span {
      font-size: 20px;
      font-weight: 600;
    }

    .thresholds-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-bottom: 16px;
    }

    mat-chip {
      font-size: 12px;
    }

    mat-chip.bootstrap {
      background: #fff3e0 !important;
      color: #e65100 !important;
    }

    mat-chip.mature {
      background: #e8f5e9 !important;
      color: #2e7d32 !important;
    }

    mat-chip.unknown {
      background: #f5f5f5 !important;
      color: #666 !important;
    }

    .warning {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px;
      background: #fff3e0;
      border-radius: 4px;
      margin-bottom: 16px;
    }

    .warning mat-icon {
      color: #e65100;
    }

    .danger-zone {
      background: #ffebee;
      padding: 16px;
      border-radius: 4px;
    }

    .danger-zone .warning {
      background: white;
    }

    button mat-spinner {
      display: inline-block;
      margin-right: 8px;
    }
  `]
})
export class TenantDetailsDialogComponent {
  thresholds: MaturityThresholds;
  isUpdating = false;
  isUpgrading = false;
  isDeleting = false;

  constructor(
    private http: HttpClient,
    private snackBar: MatSnackBar,
    private dialog: MatDialog,
    public dialogRef: MatDialogRef<TenantDetailsDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: TenantDetailsDialogData
  ) {
    this.thresholds = {
      age_days: data.details.maturity_age_days || 14,
      user_threshold: data.details.maturity_user_threshold || 5,
      admin_threshold: data.details.maturity_admin_threshold || 2
    };
  }

  updateThresholds(): void {
    this.isUpdating = true;
    this.http.put(`/api/tenants/${this.data.tenant.domain}/maturity`, this.thresholds).subscribe({
      next: () => {
        this.snackBar.open('Maturity thresholds updated', 'Close', { duration: 3000 });
        this.isUpdating = false;
        this.dialogRef.close({ action: 'thresholds_updated' });
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to update thresholds', 'Close', { duration: 3000 });
        this.isUpdating = false;
      }
    });
  }

  forceMaturityUpgrade(): void {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Force Maturity Upgrade',
        message: `Are you sure you want to force ${this.data.tenant.domain} to Mature state? This will bypass normal maturity conditions.`,
        confirmText: 'Force Upgrade',
        cancelText: 'Cancel',
        isDanger: false
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.isUpgrading = true;
        this.http.post(`/api/tenants/${this.data.tenant.domain}/maturity/force-upgrade`, {}).subscribe({
          next: () => {
            this.snackBar.open('Tenant upgraded to Mature state', 'Close', { duration: 3000 });
            this.isUpgrading = false;
            this.dialogRef.close({ action: 'maturity_upgraded' });
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to upgrade tenant', 'Close', { duration: 3000 });
            this.isUpgrading = false;
          }
        });
      }
    });
  }

  deleteTenant(): void {
    const domain = this.data.tenant.domain;

    const dialogRef = this.dialog.open(DeleteTenantDialogComponent, {
      width: '500px',
      data: { domain }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.isDeleting = true;
        this.http.delete(`/api/tenants/${domain}`, { body: { confirm_delete: true } }).subscribe({
          next: () => {
            this.snackBar.open(`Tenant ${domain} deleted successfully`, 'Close', { duration: 3000 });
            this.isDeleting = false;
            this.dialogRef.close({ action: 'tenant_deleted' });
          },
          error: (err) => {
            this.snackBar.open(err.error?.error || 'Failed to delete tenant', 'Close', { duration: 3000 });
            this.isDeleting = false;
          }
        });
      }
    });
  }

  close(): void {
    this.dialogRef.close();
  }
}

// ==================== Delete Tenant Dialog ====================

interface DeleteTenantDialogData {
  domain: string;
}

@Component({
  selector: 'app-delete-tenant-dialog',
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
      <mat-icon color="warn">warning</mat-icon>
      Delete Tenant: {{ data.domain }}
    </h2>
    <mat-dialog-content>
      <div class="warning-box">
        <p><strong>This action is permanent and cannot be undone!</strong></p>
        <p>The following data will be permanently deleted:</p>
        <ul>
          <li>All users and their accounts</li>
          <li>All architecture decisions</li>
          <li>All decision spaces</li>
          <li>All tenant settings and configurations</li>
          <li>SSO configuration (if any)</li>
          <li>Domain approval records</li>
        </ul>
      </div>

      <p>To confirm deletion, please type the domain name: <strong>{{ data.domain }}</strong></p>

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Domain Name</mat-label>
        <input matInput [(ngModel)]="confirmDomain" placeholder="Type domain name to confirm">
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="cancel()">Cancel</button>
      <button mat-raised-button color="warn"
              (click)="confirm()"
              [disabled]="confirmDomain !== data.domain">
        Delete Tenant
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    h2 {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .warning-box {
      background: #ffebee;
      padding: 16px;
      border-radius: 4px;
      margin-bottom: 24px;
      border-left: 4px solid #c62828;
    }

    .warning-box strong {
      color: #c62828;
    }

    .warning-box ul {
      margin: 12px 0;
      padding-left: 20px;
    }

    .warning-box li {
      margin: 4px 0;
    }

    .full-width {
      width: 100%;
    }

    mat-dialog-content p {
      font-size: 16px;
      line-height: 1.5;
    }
  `]
})
export class DeleteTenantDialogComponent {
  confirmDomain = '';

  constructor(
    public dialogRef: MatDialogRef<DeleteTenantDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: DeleteTenantDialogData
  ) {}

  cancel(): void {
    this.dialogRef.close(false);
  }

  confirm(): void {
    this.dialogRef.close(true);
  }
}
