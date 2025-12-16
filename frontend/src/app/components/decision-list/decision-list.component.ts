import { Component, OnInit, TemplateRef, ViewChild } from '@angular/core';
import { CommonModule, TitleCasePipe } from '@angular/common';
import { RouterModule, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatDialogModule, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { FormsModule } from '@angular/forms';
import { DecisionService } from '../../services/decision.service';
import { AuthService } from '../../services/auth.service';
import { SpaceService } from '../../services/space.service';
import { Decision, User, Space } from '../../models/decision.model';

@Component({
  selector: 'app-decision-list',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatChipsModule,
    MatTooltipModule,
    MatProgressSpinnerModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule,
    MatDialogModule
  ],
  template: `
    <div class="decision-list-container">
      <div class="header">
        <div class="header-content">
          <h1>Decision Records</h1>
          <p class="subtitle">Track and manage your decision records</p>
        </div>
        @if (!authService.isMasterAccount && userDomain) {
          <button mat-flat-button color="primary" class="new-decision-btn" [routerLink]="['/' + userDomain + '/decision/new']">
            <mat-icon>add</mat-icon>
            New Decision
          </button>
        }
      </div>

      <mat-card class="filter-card" appearance="outlined">
        <mat-card-content>
          <div class="filter-row">
            <div class="search-wrapper">
              <mat-icon class="search-icon">search</mat-icon>
              <input
                class="search-input"
                [(ngModel)]="searchTerm"
                (input)="filterDecisions()"
                placeholder="Search decisions..."
                type="text"
              >
              @if (searchTerm) {
                <button class="clear-btn" (click)="searchTerm = ''; filterDecisions()">
                  <mat-icon>close</mat-icon>
                </button>
              }
            </div>

            <div class="results-badge">
              <span class="count">{{ filteredDecisions.length }}</span>
              <span class="label">of {{ decisions.length }} records</span>
            </div>
          </div>

          <div class="status-filters">
            <span class="filter-label">Filter by status:</span>
            <mat-chip-set aria-label="Status filter">
              <mat-chip
                [highlighted]="statusFilter === ''"
                (click)="filterByStatus('')"
                class="filter-chip">
                All
              </mat-chip>
              <mat-chip
                [highlighted]="statusFilter === 'proposed'"
                (click)="filterByStatus('proposed')"
                class="filter-chip status-proposed-chip">
                <mat-icon matChipAvatar>schedule</mat-icon>
                Proposed
              </mat-chip>
              <mat-chip
                [highlighted]="statusFilter === 'accepted'"
                (click)="filterByStatus('accepted')"
                class="filter-chip status-accepted-chip">
                <mat-icon matChipAvatar>check_circle</mat-icon>
                Accepted
              </mat-chip>
              <mat-chip
                [highlighted]="statusFilter === 'deprecated'"
                (click)="filterByStatus('deprecated')"
                class="filter-chip status-deprecated-chip">
                <mat-icon matChipAvatar>warning</mat-icon>
                Deprecated
              </mat-chip>
              <mat-chip
                [highlighted]="statusFilter === 'superseded'"
                (click)="filterByStatus('superseded')"
                class="filter-chip status-superseded-chip">
                <mat-icon matChipAvatar>swap_horiz</mat-icon>
                Superseded
              </mat-chip>
            </mat-chip-set>
          </div>

          @if (spaces.length > 1) {
            <div class="space-filter">
              <mat-form-field appearance="outline" class="space-select">
                <mat-label>Filter by Space</mat-label>
                <mat-select [(ngModel)]="spaceFilter" (selectionChange)="filterDecisions()">
                  <mat-option [value]="null">All Spaces</mat-option>
                  @for (space of spaces; track space.id) {
                    <mat-option [value]="space.id">
                      {{ space.name }}
                      @if (space.is_default) {
                        <span class="default-badge">(Default)</span>
                      }
                    </mat-option>
                  }
                </mat-select>
                <mat-icon matPrefix>folder</mat-icon>
              </mat-form-field>
            </div>
          }
        </mat-card-content>
      </mat-card>

      @if (isLoading) {
        <div class="loading-container">
          <mat-spinner diameter="48"></mat-spinner>
          <p class="loading-text">Loading decisions...</p>
        </div>
      } @else if (filteredDecisions.length === 0) {
        <mat-card class="empty-state" appearance="outlined">
          <mat-card-content>
            <div class="empty-icon-container">
              <mat-icon>{{ searchTerm || statusFilter ? 'search_off' : 'architecture' }}</mat-icon>
            </div>
            <h2>{{ searchTerm || statusFilter ? 'No matching decisions' : 'No decisions yet' }}</h2>
            <p>{{ searchTerm || statusFilter ? 'Try adjusting your search or filters' : 'Create your first architecture decision to start documenting your technical choices' }}</p>
            @if (!searchTerm && !statusFilter && !authService.isMasterAccount && userDomain) {
              <button mat-flat-button color="primary" class="create-btn" [routerLink]="['/' + userDomain + '/decision/new']">
                <mat-icon>add</mat-icon>
                Create Your First Decision
              </button>
            }
            @if (searchTerm || statusFilter) {
              <button mat-stroked-button color="primary" (click)="clearFilters()">
                <mat-icon>clear_all</mat-icon>
                Clear Filters
              </button>
            }
          </mat-card-content>
        </mat-card>
      } @else {
        <div class="decisions-grid">
          @for (decision of filteredDecisions; track decision.id) {
            <mat-card class="decision-card" appearance="outlined" [routerLink]="['/' + userDomain + '/decision', decision.id]">
              <mat-card-header>
                <div class="card-header-content">
                  <div class="decision-id-badge" [ngClass]="'status-badge-' + decision.status">
                    {{ decision.display_id || 'ADR-' + decision.id }}
                  </div>
                  <mat-card-title>{{ decision.title }}</mat-card-title>
                </div>
              </mat-card-header>
              <mat-card-content>
                <p class="context-preview">{{ decision.context | slice:0:150 }}{{ decision.context.length > 150 ? '...' : '' }}</p>
                @if (decision.infrastructure && decision.infrastructure.length > 0) {
                  <div class="infrastructure-tags">
                    @for (infra of decision.infrastructure.slice(0, 3); track infra.id) {
                      <span class="infra-tag" [attr.data-type]="infra.type">
                        <mat-icon class="infra-icon">{{ getInfraIcon(infra.type) }}</mat-icon>
                        {{ infra.name }}
                      </span>
                    }
                    @if (decision.infrastructure.length > 3) {
                      <span class="infra-more">+{{ decision.infrastructure.length - 3 }} more</span>
                    }
                  </div>
                }
              </mat-card-content>
              <mat-card-footer>
                <div class="card-footer">
                  <div class="status-chip" [ngClass]="'status-' + decision.status">
                    <mat-icon class="status-icon">{{ getStatusIcon(decision.status) }}</mat-icon>
                    {{ decision.status | titlecase }}
                  </div>
                  <div class="card-meta">
                    @if (decision.created_by) {
                      <span class="author">{{ decision.created_by.name || decision.created_by.email }}</span>
                    }
                    <span class="date">{{ decision.created_at | date:'MMM d, y' }}</span>
                  </div>
                </div>
              </mat-card-footer>
            </mat-card>
          }
        </div>
      }

      <!-- Admin Onboarding Modal -->
      <ng-template #adminOnboardingDialog>
        <div class="onboarding-dialog">
          <div class="onboarding-header">
            <mat-icon class="onboarding-icon">admin_panel_settings</mat-icon>
            <h2>You're a Provisional Admin</h2>
          </div>

          <p class="onboarding-intro">
            You are currently a provisional administrator for <strong>{{ userDomain }}</strong>.
            Some settings will unlock once others from your organisation join.
          </p>

          <div class="onboarding-tip">
            <mat-icon>lightbulb</mat-icon>
            <div>
              <strong>Tip: Shared administration</strong>
              <p>
                Administration is shared. Consider assigning this role to people who can represent organisational continuity.
              </p>
            </div>
          </div>

          <div class="onboarding-features">
            <h3>As a steward, you can:</h3>
            <ul>
              <li>
                <mat-icon>person_add</mat-icon>
                <span>Invite colleagues using their &#64;{{ userDomain }} email address</span>
              </li>
              <li>
                <mat-icon>settings</mat-icon>
                <span>Configure authentication and security settings</span>
              </li>
              <li>
                <mat-icon>group</mat-icon>
                <span>Manage users and share administrative responsibilities</span>
              </li>
            </ul>
          </div>

          <div class="onboarding-actions">
            <button mat-stroked-button (click)="dismissOnboarding()">
              Got it
            </button>
            <button mat-raised-button color="primary" [routerLink]="['/' + userDomain + '/admin']" (click)="dismissOnboarding()">
              <mat-icon>settings</mat-icon>
              Go to Settings
            </button>
          </div>
        </div>
      </ng-template>
    </div>
  `,
  styles: [`
    .decision-list-container {
      padding: 32px;
      max-width: 1400px;
      margin: 0 auto;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 32px;
    }

    .header-content h1 {
      margin: 0 0 4px 0;
      font-size: 32px;
      font-weight: 400;
      color: #1a1a1a;
    }

    .subtitle {
      margin: 0;
      color: #666;
      font-size: 14px;
    }

    .new-decision-btn {
      padding: 0 24px;
      height: 40px;
      font-weight: 500;
      letter-spacing: 0.25px;
    }

    .new-decision-btn mat-icon {
      margin-right: 8px;
    }

    .filter-card {
      margin-bottom: 24px;
      border-radius: 12px;
    }

    .filter-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }

    .search-wrapper {
      flex: 1;
      max-width: 400px;
      min-width: 250px;
      display: flex;
      align-items: center;
      position: relative;
      background: #f8f9fa;
      border: 2px solid #e9ecef;
      border-radius: 12px;
      padding: 0 16px;
      height: 48px;
      transition: all 0.2s ease;
    }

    .search-wrapper:focus-within {
      border-color: #1976d2;
      background: #fff;
      box-shadow: 0 0 0 4px rgba(25, 118, 210, 0.1);
    }

    .search-icon {
      color: #9e9e9e;
      margin-right: 12px;
      font-size: 22px;
    }

    .search-wrapper:focus-within .search-icon {
      color: #1976d2;
    }

    .search-input {
      flex: 1;
      border: none;
      background: transparent;
      font-size: 15px;
      color: #333;
      outline: none;
      height: 100%;
    }

    .search-input::placeholder {
      color: #9e9e9e;
    }

    .clear-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      background: #e0e0e0;
      border: none;
      border-radius: 50%;
      width: 24px;
      height: 24px;
      cursor: pointer;
      padding: 0;
      transition: all 0.2s ease;
    }

    .clear-btn:hover {
      background: #bdbdbd;
    }

    .clear-btn mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      color: #666;
    }

    .results-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
      border-radius: 24px;
      white-space: nowrap;
    }

    .results-badge .count {
      font-size: 18px;
      font-weight: 600;
      color: #1565c0;
    }

    .results-badge .label {
      font-size: 13px;
      color: #5c8bc7;
    }

    .status-filters {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 16px;
      flex-wrap: wrap;
    }

    .filter-label {
      font-size: 14px;
      color: #666;
      font-weight: 500;
    }

    .filter-chip {
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .filter-chip:hover {
      transform: scale(1.02);
    }

    .filter-chip mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .space-filter {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid #eee;
    }

    .space-select {
      min-width: 200px;
    }

    .default-badge {
      font-size: 11px;
      color: #888;
      margin-left: 4px;
    }

    .loading-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 80px 24px;
    }

    .loading-text {
      margin-top: 16px;
      color: #666;
      font-size: 14px;
    }

    .empty-state {
      text-align: center;
      padding: 64px 24px;
      border-radius: 12px;
      max-width: 480px;
      margin: 48px auto;
    }

    .empty-icon-container {
      width: 80px;
      height: 80px;
      border-radius: 50%;
      background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 24px;
    }

    .empty-icon-container mat-icon {
      font-size: 40px;
      width: 40px;
      height: 40px;
      color: #1565c0;
    }

    .empty-state h2 {
      margin: 0 0 8px 0;
      font-size: 24px;
      font-weight: 500;
      color: #1a1a1a;
    }

    .empty-state p {
      margin: 0 0 24px 0;
      color: #666;
      font-size: 14px;
      line-height: 1.6;
    }

    .create-btn {
      padding: 0 24px;
      height: 44px;
      font-weight: 500;
    }

    .create-btn mat-icon {
      margin-right: 8px;
    }

    .decisions-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 20px;
    }

    .decision-card {
      cursor: pointer;
      transition: all 0.2s ease;
      border-radius: 12px;
      overflow: hidden;
    }

    .decision-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    }

    .card-header-content {
      width: 100%;
    }

    .decision-id-badge {
      display: inline-block;
      font-size: 12px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 6px;
      margin-bottom: 8px;
      letter-spacing: 0.5px;
    }

    .status-badge-proposed { background: #fff3e0; color: #e65100; }
    .status-badge-accepted { background: #e8f5e9; color: #2e7d32; }
    .status-badge-deprecated { background: #ffebee; color: #c62828; }
    .status-badge-superseded { background: #e3f2fd; color: #1565c0; }

    mat-card-title {
      font-size: 18px !important;
      font-weight: 500 !important;
      line-height: 1.4 !important;
      color: #1a1a1a;
    }

    .context-preview {
      color: #555;
      line-height: 1.6;
      font-size: 14px;
      min-height: 48px;
      margin: 8px 0 16px 0;
    }

    .infrastructure-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 16px 0;
    }

    .infra-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 16px;
      background: #f5f5f5;
      color: #424242;
      border: 1px solid #e0e0e0;
    }

    .infra-tag .infra-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
      color: #757575;
    }

    .infra-more {
      font-size: 12px;
      color: #888;
      padding: 4px 10px;
    }

    mat-card-footer {
      padding: 0 16px 16px 16px;
    }

    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 12px;
      border-top: 1px solid #f0f0f0;
    }

    .status-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 500;
      padding: 6px 12px;
      border-radius: 20px;
    }

    .status-chip .status-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    .status-proposed { background: #fff3e0; color: #e65100; }
    .status-accepted { background: #e8f5e9; color: #2e7d32; }
    .status-deprecated { background: #ffebee; color: #c62828; }
    .status-superseded { background: #e3f2fd; color: #1565c0; }

    .card-meta {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 2px;
    }

    .card-meta .author {
      font-size: 12px;
      color: #666;
      max-width: 150px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .card-meta .date {
      font-size: 11px;
      color: #999;
    }

    /* Admin Onboarding Modal */
    .onboarding-dialog {
      padding: 32px;
      max-width: 480px;
    }

    .onboarding-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }

    .onboarding-header h2 {
      margin: 0;
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
    }

    .onboarding-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      color: #2563eb;
    }

    .onboarding-intro {
      color: #475569;
      font-size: 1rem;
      line-height: 1.6;
      margin: 0 0 20px;
    }

    .onboarding-intro strong {
      color: #1e40af;
    }

    .onboarding-tip {
      display: flex;
      gap: 12px;
      padding: 16px;
      background: #fef3c7;
      border-radius: 8px;
      margin-bottom: 20px;
    }

    .onboarding-tip mat-icon {
      color: #d97706;
      flex-shrink: 0;
    }

    .onboarding-tip strong {
      display: block;
      color: #92400e;
      margin-bottom: 4px;
    }

    .onboarding-tip p {
      margin: 0;
      font-size: 0.9rem;
      color: #78350f;
      line-height: 1.5;
    }

    .onboarding-features h3 {
      font-size: 0.95rem;
      font-weight: 600;
      color: #374151;
      margin: 0 0 12px;
    }

    .onboarding-features ul {
      list-style: none;
      padding: 0;
      margin: 0 0 24px;
    }

    .onboarding-features li {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 0;
      border-bottom: 1px solid #f1f5f9;
    }

    .onboarding-features li:last-child {
      border-bottom: none;
    }

    .onboarding-features li mat-icon {
      color: #2563eb;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .onboarding-features li span {
      color: #475569;
      font-size: 0.9rem;
    }

    .onboarding-actions {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      padding-top: 16px;
      border-top: 1px solid #e2e8f0;
    }

    /* Responsive adjustments */
    @media (max-width: 768px) {
      .decision-list-container {
        padding: 16px;
      }

      .header {
        flex-direction: column;
        gap: 16px;
      }

      .new-decision-btn {
        width: 100%;
      }

      .decisions-grid {
        grid-template-columns: 1fr;
      }

      .filter-row {
        flex-direction: column;
        align-items: stretch;
      }

      .search-wrapper {
        max-width: none;
      }

      .results-badge {
        justify-content: center;
      }
    }
  `]
})
export class DecisionListComponent implements OnInit {
  @ViewChild('adminOnboardingDialog') adminOnboardingDialog!: TemplateRef<any>;

  decisions: Decision[] = [];
  filteredDecisions: Decision[] = [];
  isLoading = true;
  searchTerm = '';
  statusFilter = '';
  spaceFilter: number | null = null;
  spaces: Space[] = [];
  userDomain = '';
  onboardingDialogRef: MatDialogRef<any> | null = null;

  constructor(
    private decisionService: DecisionService,
    public authService: AuthService,
    private spaceService: SpaceService,
    private route: ActivatedRoute,
    private http: HttpClient,
    private dialog: MatDialog
  ) {}

  ngOnInit(): void {
    this.loadDecisions();
    this.loadSpaces();
    // Get tenant from route params - this is the reliable source
    this.userDomain = this.route.snapshot.paramMap.get('tenant') || '';
    console.log('[DecisionList] userDomain from route:', this.userDomain);

    // Check if admin needs to see onboarding modal
    this.checkAdminOnboarding();
  }

  loadSpaces(): void {
    this.spaceService.getSpaces().subscribe({
      next: (spaces) => {
        this.spaces = spaces;
      },
      error: (err) => {
        console.error('Failed to load spaces', err);
      }
    });
  }

  private checkAdminOnboarding(): void {
    const currentUser = this.authService.currentUser;
    if (!currentUser || currentUser.isMaster) return;

    const user = currentUser.user as User;
    if (user && user.is_admin && !user.has_seen_admin_onboarding) {
      // Small delay to ensure the view is ready
      setTimeout(() => {
        this.showAdminOnboarding();
      }, 500);
    }
  }

  showAdminOnboarding(): void {
    this.onboardingDialogRef = this.dialog.open(this.adminOnboardingDialog, {
      width: '520px',
      disableClose: false,
      panelClass: 'admin-onboarding-dialog'
    });
  }

  dismissOnboarding(): void {
    // Call API to mark onboarding as seen
    this.http.post('/api/user/dismiss-admin-onboarding', {}).subscribe({
      next: (response: any) => {
        // Update local user state
        const currentUser = this.authService.currentUser;
        if (currentUser && !currentUser.isMaster) {
          const user = currentUser.user as User;
          if (user) {
            user.has_seen_admin_onboarding = true;
          }
        }
      },
      error: (err) => {
        console.error('Failed to dismiss onboarding:', err);
      }
    });

    // Close the dialog
    if (this.onboardingDialogRef) {
      this.onboardingDialogRef.close();
      this.onboardingDialogRef = null;
    }
  }

  loadDecisions(): void {
    this.isLoading = true;
    this.decisionService.getDecisions().subscribe({
      next: (decisions) => {
        this.decisions = decisions;
        this.filterDecisions();
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  filterDecisions(): void {
    this.filteredDecisions = this.decisions.filter(d => {
      const matchesSearch = !this.searchTerm ||
        d.title.toLowerCase().includes(this.searchTerm.toLowerCase()) ||
        d.context.toLowerCase().includes(this.searchTerm.toLowerCase()) ||
        d.decision.toLowerCase().includes(this.searchTerm.toLowerCase());

      const matchesStatus = !this.statusFilter || d.status === this.statusFilter;

      const matchesSpace = this.spaceFilter === null ||
        (d.spaces && d.spaces.some(s => s.id === this.spaceFilter));

      return matchesSearch && matchesStatus && matchesSpace;
    });
  }

  filterByStatus(status: string): void {
    this.statusFilter = status;
    this.filterDecisions();
  }

  getInfraIcon(type: string): string {
    const icons: Record<string, string> = {
      'application': 'apps',
      'network': 'router',
      'database': 'storage',
      'server': 'dns',
      'service': 'settings_ethernet',
      'api': 'api',
      'storage': 'cloud_queue',
      'cloud': 'cloud',
      'container': 'view_in_ar',
      'other': 'category'
    };
    return icons[type] || 'category';
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

  clearFilters(): void {
    this.searchTerm = '';
    this.statusFilter = '';
    this.spaceFilter = null;
    this.filterDecisions();
  }

  hasActiveFilters(): boolean {
    return !!this.searchTerm || !!this.statusFilter || this.spaceFilter !== null;
  }
}
