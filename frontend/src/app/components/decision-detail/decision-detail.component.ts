import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { FormBuilder, FormGroup, FormControl, Validators, ReactiveFormsModule, FormsModule } from '@angular/forms';
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
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatListModule } from '@angular/material/list';
import { DecisionService, UpdateDecisionRequest } from '../../services/decision.service';
import { AuthService } from '../../services/auth.service';
import { InfrastructureService } from '../../services/infrastructure.service';
import { SpaceService } from '../../services/space.service';
import { Decision, DecisionHistory, DecisionStatus, ITInfrastructure, InfrastructureType, Space } from '../../models/decision.model';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';
import { Observable, map, startWith } from 'rxjs';

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
    MatChipsModule,
    MatExpansionModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDialogModule,
    MatTooltipModule,
    MatAutocompleteModule,
    MatListModule,
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

                <!-- Infrastructure Section -->
                <div class="infrastructure-section">
                  <h3>
                    <mat-icon>dns</mat-icon>
                    Related IT Infrastructure
                  </h3>

                  @if (selectedInfrastructure.length > 0) {
                    <div class="selected-infrastructure">
                      @for (infra of selectedInfrastructure; track infra.id) {
                        <mat-chip [removable]="!authService.isMasterAccount" (removed)="removeInfrastructure(infra)">
                          <mat-icon class="infra-icon">{{ getInfraIcon(infra.type) }}</mat-icon>
                          {{ infra.name }}
                          <span class="infra-type">({{ infra.type }})</span>
                          @if (!authService.isMasterAccount) {
                            <mat-icon matChipRemove>cancel</mat-icon>
                          }
                        </mat-chip>
                      }
                    </div>
                  }

                  @if (!authService.isMasterAccount) {
                    <div class="infrastructure-input">
                      <mat-form-field appearance="outline" class="full-width">
                        <mat-label>Search or add infrastructure</mat-label>
                        <input matInput
                               [formControl]="infraSearchControl"
                               [matAutocomplete]="autoInfra"
                               placeholder="Type to search...">
                        <mat-autocomplete #autoInfra="matAutocomplete"
                                          (optionSelected)="selectInfrastructure($event.option.value)">
                          @for (infra of filteredInfrastructure$ | async; track infra.id) {
                            <mat-option [value]="infra">
                              <mat-icon>{{ getInfraIcon(infra.type) }}</mat-icon>
                              {{ infra.name }}
                              <span class="option-type">({{ infra.type }})</span>
                            </mat-option>
                          }
                          @if ((filteredInfrastructure$ | async)?.length === 0 && infraSearchControl.value) {
                            <mat-option disabled>
                              No matches found
                            </mat-option>
                          }
                        </mat-autocomplete>
                      </mat-form-field>

                      <button mat-stroked-button type="button" (click)="showCreateInfraForm = !showCreateInfraForm">
                        <mat-icon>add</mat-icon>
                        New Infrastructure
                      </button>
                    </div>

                    @if (showCreateInfraForm) {
                      <mat-card class="new-infra-card">
                        <mat-card-content>
                          <h4>Create New Infrastructure</h4>
                          <div class="new-infra-form">
                            <mat-form-field appearance="outline">
                              <mat-label>Name</mat-label>
                              <input matInput [(ngModel)]="newInfra.name" [ngModelOptions]="{standalone: true}">
                            </mat-form-field>

                            <mat-form-field appearance="outline">
                              <mat-label>Type</mat-label>
                              <mat-select [(ngModel)]="newInfra.type" [ngModelOptions]="{standalone: true}">
                                @for (type of infrastructureTypes; track type) {
                                  <mat-option [value]="type">
                                    <mat-icon>{{ getInfraIcon(type) }}</mat-icon>
                                    {{ type | titlecase }}
                                  </mat-option>
                                }
                              </mat-select>
                            </mat-form-field>

                            <mat-form-field appearance="outline" class="full-width">
                              <mat-label>Description (optional)</mat-label>
                              <textarea matInput [(ngModel)]="newInfra.description" [ngModelOptions]="{standalone: true}" rows="2"></textarea>
                            </mat-form-field>

                            <div class="new-infra-actions">
                              <button mat-raised-button color="primary" type="button"
                                      (click)="createInfrastructure()" [disabled]="!newInfra.name || !newInfra.type">
                                Create & Add
                              </button>
                              <button mat-button type="button" (click)="showCreateInfraForm = false">Cancel</button>
                            </div>
                          </div>
                        </mat-card-content>
                      </mat-card>
                    }
                  }
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

    /* Infrastructure Section Styles */
    .infrastructure-section {
      margin: 24px 0;
      padding: 16px;
      background: #fafafa;
      border-radius: 8px;
      border: 1px solid #e0e0e0;
    }

    .infrastructure-section h3 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 16px 0;
      color: #424242;
      font-size: 16px;
    }

    .selected-infrastructure {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
    }

    .selected-infrastructure mat-chip {
      background: #e3f2fd;
    }

    .selected-infrastructure .infra-icon {
      font-size: 18px;
      margin-right: 4px;
    }

    .selected-infrastructure .infra-type {
      font-size: 11px;
      color: #666;
      margin-left: 4px;
    }

    .infrastructure-input {
      display: flex;
      gap: 12px;
      align-items: flex-start;
    }

    .infrastructure-input mat-form-field {
      flex: 1;
    }

    .infrastructure-input button {
      margin-top: 4px;
    }

    .option-type {
      font-size: 12px;
      color: #888;
      margin-left: 8px;
    }

    .new-infra-card {
      margin-top: 16px;
      background: white;
    }

    .new-infra-card h4 {
      margin: 0 0 16px 0;
      color: #424242;
    }

    .new-infra-form {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }

    .new-infra-form mat-form-field {
      min-width: 200px;
    }

    .new-infra-actions {
      display: flex;
      gap: 8px;
      width: 100%;
      margin-top: 8px;
    }

    .default-space-badge {
      font-size: 11px;
      color: #888;
      margin-left: 4px;
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

  // Spaces
  spaces: Space[] = [];
  selectedSpaceIds: number[] = [];

  // Infrastructure
  allInfrastructure: ITInfrastructure[] = [];
  selectedInfrastructure: ITInfrastructure[] = [];
  infraSearchControl = new FormControl('');
  filteredInfrastructure$!: Observable<ITInfrastructure[]>;
  showCreateInfraForm = false;
  newInfra = { name: '', type: '' as InfrastructureType, description: '' };
  infrastructureTypes: InfrastructureType[] = ['application', 'network', 'database', 'server', 'service', 'api', 'storage', 'cloud', 'container', 'other'];

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private decisionService: DecisionService,
    public authService: AuthService,
    private infrastructureService: InfrastructureService,
    private spaceService: SpaceService,
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
    // Get tenant from route params
    this.tenant = this.route.snapshot.paramMap.get('tenant') || '';

    // Load infrastructure items
    this.loadInfrastructure();

    // Load spaces
    this.loadSpaces();

    // Set up infrastructure filter
    this.filteredInfrastructure$ = this.infraSearchControl.valueChanges.pipe(
      startWith(''),
      map(value => this.filterInfrastructure(value || ''))
    );

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

  loadInfrastructure(): void {
    this.infrastructureService.getInfrastructure().subscribe({
      next: (items) => {
        this.allInfrastructure = items;
      },
      error: (err) => {
        console.error('Failed to load infrastructure', err);
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

  filterInfrastructure(value: string | ITInfrastructure): ITInfrastructure[] {
    const filterValue = typeof value === 'string' ? value.toLowerCase() : value.name.toLowerCase();
    return this.allInfrastructure.filter(infra =>
      !this.selectedInfrastructure.some(s => s.id === infra.id) &&
      (infra.name.toLowerCase().includes(filterValue) || infra.type.toLowerCase().includes(filterValue))
    );
  }

  selectInfrastructure(infra: ITInfrastructure): void {
    if (!this.selectedInfrastructure.some(s => s.id === infra.id)) {
      this.selectedInfrastructure.push(infra);
    }
    this.infraSearchControl.setValue('');
  }

  removeInfrastructure(infra: ITInfrastructure): void {
    this.selectedInfrastructure = this.selectedInfrastructure.filter(s => s.id !== infra.id);
  }

  createInfrastructure(): void {
    if (!this.newInfra.name || !this.newInfra.type) return;

    this.infrastructureService.createInfrastructure({
      name: this.newInfra.name,
      type: this.newInfra.type,
      description: this.newInfra.description
    }).subscribe({
      next: (infra) => {
        this.allInfrastructure.push(infra);
        this.selectedInfrastructure.push(infra);
        this.newInfra = { name: '', type: '' as InfrastructureType, description: '' };
        this.showCreateInfraForm = false;
        this.snackBar.open('Infrastructure created and added', 'Close', { duration: 3000 });
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Failed to create infrastructure', 'Close', { duration: 3000 });
      }
    });
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
        // Load decision's infrastructure
        if (decision.infrastructure && decision.infrastructure.length > 0) {
          this.selectedInfrastructure = [...decision.infrastructure];
        }
        // Load decision's spaces
        if (decision.spaces && decision.spaces.length > 0) {
          this.selectedSpaceIds = decision.spaces.map(s => s.id);
        }
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
    const infrastructureIds = this.selectedInfrastructure.map(i => i.id);

    if (this.isNew) {
      this.decisionService.createDecision({
        title: formValue.title,
        context: formValue.context,
        decision: formValue.decision,
        status: formValue.status,
        consequences: formValue.consequences,
        infrastructure_ids: infrastructureIds,
        space_ids: this.selectedSpaceIds
      }).subscribe({
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
      const update: UpdateDecisionRequest = {
        title: formValue.title,
        context: formValue.context,
        decision: formValue.decision,
        status: formValue.status,
        consequences: formValue.consequences,
        infrastructure_ids: infrastructureIds,
        space_ids: this.selectedSpaceIds
      };
      if (formValue.change_reason) {
        update.change_reason = formValue.change_reason;
      }

      this.decisionService.updateDecision(this.decision!.id, update).subscribe({
        next: (decision) => {
          this.decision = decision;
          this.selectedInfrastructure = decision.infrastructure || [];
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
