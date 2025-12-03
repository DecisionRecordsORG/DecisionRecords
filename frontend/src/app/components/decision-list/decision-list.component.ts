import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
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
        <h1>Architecture Decisions</h1>
        @if (!authService.isMasterAccount) {
          <button mat-raised-button color="primary" routerLink="/decision/new">
            <mat-icon>add</mat-icon>
            New Decision
          </button>
        }
      </div>

      <mat-card class="filter-card">
        <mat-form-field appearance="outline" class="search-field">
          <mat-label>Search decisions</mat-label>
          <input matInput [(ngModel)]="searchTerm" (input)="filterDecisions()" placeholder="Search by title, context, or decision...">
          <mat-icon matPrefix>search</mat-icon>
        </mat-form-field>

        <div class="status-filters">
          <mat-chip-set>
            <mat-chip [class.selected]="statusFilter === ''" (click)="filterByStatus('')">
              All ({{ decisions.length }})
            </mat-chip>
            <mat-chip [class.selected]="statusFilter === 'proposed'" (click)="filterByStatus('proposed')">
              <mat-icon>pending</mat-icon>
              Proposed
            </mat-chip>
            <mat-chip [class.selected]="statusFilter === 'accepted'" (click)="filterByStatus('accepted')">
              <mat-icon>check_circle</mat-icon>
              Accepted
            </mat-chip>
            <mat-chip [class.selected]="statusFilter === 'deprecated'" (click)="filterByStatus('deprecated')">
              <mat-icon>warning</mat-icon>
              Deprecated
            </mat-chip>
            <mat-chip [class.selected]="statusFilter === 'superseded'" (click)="filterByStatus('superseded')">
              <mat-icon>swap_horiz</mat-icon>
              Superseded
            </mat-chip>
          </mat-chip-set>
        </div>
      </mat-card>

      @if (isLoading) {
        <div class="loading-container">
          <mat-spinner></mat-spinner>
        </div>
      } @else if (filteredDecisions.length === 0) {
        <mat-card class="empty-state">
          <mat-icon>folder_open</mat-icon>
          <h2>No decisions found</h2>
          <p>{{ searchTerm || statusFilter ? 'Try adjusting your filters' : 'Create your first architecture decision to get started' }}</p>
          @if (!searchTerm && !statusFilter && !authService.isMasterAccount) {
            <button mat-raised-button color="primary" routerLink="/decision/new">
              <mat-icon>add</mat-icon>
              Create Decision
            </button>
          }
        </mat-card>
      } @else {
        <div class="decisions-grid">
          @for (decision of filteredDecisions; track decision.id) {
            <mat-card class="decision-card" [routerLink]="['/decision', decision.id]">
              <mat-card-header>
                <mat-card-title>
                  <span class="decision-id">ADR-{{ decision.id }}</span>
                  {{ decision.title }}
                </mat-card-title>
                <mat-card-subtitle>
                  @if (decision.created_by) {
                    Created by {{ decision.created_by.name || decision.created_by.email }}
                  }
                  <span class="date">{{ decision.created_at | date:'mediumDate' }}</span>
                </mat-card-subtitle>
              </mat-card-header>
              <mat-card-content>
                <p class="context-preview">{{ decision.context | slice:0:150 }}{{ decision.context.length > 150 ? '...' : '' }}</p>
                <div class="card-footer">
                  <mat-chip [ngClass]="'status-' + decision.status">
                    {{ decision.status }}
                  </mat-chip>
                  @if (decision.domain) {
                    <span class="domain-badge">{{ decision.domain }}</span>
                  }
                </div>
              </mat-card-content>
            </mat-card>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .decision-list-container {
      padding: 24px;
      max-width: 1400px;
      margin: 0 auto;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
    }

    h1 {
      margin: 0;
      font-size: 28px;
      font-weight: 500;
    }

    .filter-card {
      padding: 16px;
      margin-bottom: 24px;
    }

    .search-field {
      width: 100%;
      max-width: 400px;
    }

    .status-filters {
      margin-top: 12px;
    }

    mat-chip {
      cursor: pointer;
    }

    mat-chip.selected {
      background-color: #3f51b5 !important;
      color: white !important;
    }

    .loading-container {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .empty-state {
      text-align: center;
      padding: 48px;
    }

    .empty-state mat-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #ccc;
    }

    .decisions-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 16px;
    }

    .decision-card {
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    }

    .decision-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    }

    .decision-id {
      color: #3f51b5;
      font-weight: 600;
      margin-right: 8px;
    }

    .date {
      margin-left: 8px;
      color: #888;
    }

    .context-preview {
      color: #666;
      line-height: 1.5;
      min-height: 60px;
    }

    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 12px;
    }

    .status-proposed { background-color: #fff3e0 !important; color: #e65100 !important; }
    .status-accepted { background-color: #e8f5e9 !important; color: #2e7d32 !important; }
    .status-deprecated { background-color: #ffebee !important; color: #c62828 !important; }
    .status-superseded { background-color: #e3f2fd !important; color: #1565c0 !important; }

    .domain-badge {
      font-size: 12px;
      color: #888;
      background: #f5f5f5;
      padding: 4px 8px;
      border-radius: 4px;
    }
  `]
})
export class DecisionListComponent implements OnInit {
  decisions: Decision[] = [];
  filteredDecisions: Decision[] = [];
  isLoading = true;
  searchTerm = '';
  statusFilter = '';

  constructor(
    private decisionService: DecisionService,
    public authService: AuthService
  ) {}

  ngOnInit(): void {
    this.loadDecisions();
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
}
