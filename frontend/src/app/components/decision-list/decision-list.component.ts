import { Component, OnInit } from '@angular/core';
import { CommonModule, TitleCasePipe } from '@angular/common';
import { RouterModule, ActivatedRoute } from '@angular/router';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { FormsModule } from '@angular/forms';
import { DecisionService } from '../../services/decision.service';
import { AuthService } from '../../services/auth.service';
import { Decision } from '../../models/decision.model';

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
    MatFormFieldModule
  ],
  template: `
    <div class="decision-list-container">
      <div class="header">
        <div class="header-content">
          <h1>Architecture Decisions</h1>
          <p class="subtitle">Track and manage your architecture decision records</p>
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
            <mat-form-field appearance="outline" class="search-field">
              <mat-label>Search decisions</mat-label>
              <input matInput [(ngModel)]="searchTerm" (input)="filterDecisions()" placeholder="Search by title, context, or decision...">
              <mat-icon matPrefix>search</mat-icon>
              @if (searchTerm) {
                <button matSuffix mat-icon-button (click)="searchTerm = ''; filterDecisions()">
                  <mat-icon>close</mat-icon>
                </button>
              }
            </mat-form-field>

            <div class="results-count">
              {{ filteredDecisions.length }} of {{ decisions.length }} decisions
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

    .search-field {
      flex: 1;
      max-width: 400px;
      min-width: 250px;
    }

    .results-count {
      font-size: 14px;
      color: #666;
      white-space: nowrap;
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

      .search-field {
        max-width: none;
      }

      .results-count {
        text-align: center;
      }
    }
  `]
})
export class DecisionListComponent implements OnInit {
  decisions: Decision[] = [];
  filteredDecisions: Decision[] = [];
  isLoading = true;
  searchTerm = '';
  statusFilter = '';
  userDomain = '';

  constructor(
    private decisionService: DecisionService,
    public authService: AuthService,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.loadDecisions();
    // Get tenant from route params - this is the reliable source
    this.userDomain = this.route.snapshot.paramMap.get('tenant') || '';
    console.log('[DecisionList] userDomain from route:', this.userDomain);
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

      return matchesSearch && matchesStatus;
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
    this.filterDecisions();
  }
}
