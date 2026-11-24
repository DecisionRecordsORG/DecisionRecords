import { Component, EventEmitter, OnInit, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatRadioModule } from '@angular/material/radio';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { concatMap, forkJoin, from, toArray } from 'rxjs';
import { DecisionService } from '../../services/decision.service';
import { Decision, DecisionStatus } from '../../models/decision.model';
import {
  BULK_DECISION_TYPE_MAX,
  DecisionTemplate,
  DecisionTemplateCatalog,
  DecisionTemplateService,
  IndustrySection,
  TenantDecisionTemplate
} from '../../services/decision-template.service';

/** Filter value for "decisions that have no type". */
const NO_TYPE = '__none__';

/**
 * Organisation settings, tab "Decision template".
 *
 * Card 1: choose the template (with a preview of its headings), the optional
 * industry that suggests one, and whether to switch on the suggested
 * relationship packs. Card 2: give existing decisions a type in bulk.
 *
 * Neither card reads or changes the text of a decision.
 */
@Component({
  selector: 'app-decision-template-settings',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatRadioModule,
    MatCheckboxModule,
    MatProgressSpinnerModule,
    MatSnackBarModule
  ],
  template: `
    @if (loading) {
      <div class="template-loading">
        <mat-spinner diameter="40"></mat-spinner>
      </div>
    } @else if (!catalog || !tenantTemplate) {
      <mat-card class="template-card" data-testid="decision-template-card">
        <mat-card-content>
          <p class="template-error">Decision templates could not be loaded. Reload the page to try again.</p>
        </mat-card-content>
      </mat-card>
    } @else {
      <mat-card class="template-card" data-testid="decision-template-card">
        <mat-card-header>
          <mat-card-title>
            <mat-icon>dashboard_customize</mat-icon>
            Decision template
          </mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <p class="template-intro">
            A template sets the three headings and the prompts shown on your decisions, the example titles,
            and the decision types people can pick. Choose the one closest to how your organisation records decisions.
          </p>
          <p class="template-guarantee" data-testid="decision-template-guarantee">
            <mat-icon>verified_user</mat-icon>
            <span>{{ catalog.guarantee }}</span>
          </p>

          <mat-form-field appearance="outline" class="industry-field">
            <mat-label>Industry (optional)</mat-label>
            <mat-select data-testid="decision-template-industry"
                        [(ngModel)]="selectedIndustry" (selectionChange)="onIndustryChange()">
              <mat-option [value]="null">Not chosen</mat-option>
              @for (industry of catalog.industries; track industry.code) {
                <mat-option [value]="industry.code">{{ industry.title }}</mat-option>
              }
            </mat-select>
            <mat-hint>Your industry only suggests a template. You can pick any template below.</mat-hint>
          </mat-form-field>
          <p class="industry-credit" data-testid="decision-template-credit">{{ catalog.industry_credit }}</p>

          <mat-radio-group class="template-options" aria-label="Decision template"
                           [(ngModel)]="selectedTemplateId" (change)="enablePacks = false">
            @for (template of catalog.templates; track template.id) {
              <label class="template-option" [class.selected]="template.id === selectedTemplateId"
                     [attr.data-testid]="'decision-template-option-' + template.id">
                <mat-radio-button [value]="template.id">
                  <span class="template-option-label">{{ template.label }}</span>
                  @if (template.id === suggestedTemplateId && selectedIndustry) {
                    <span class="template-badge" data-testid="decision-template-suggested">Suggested for your industry</span>
                  }
                  @if (template.is_default) {
                    <span class="template-badge neutral">Default</span>
                  }
                </mat-radio-button>
                <p>{{ template.description }}</p>
              </label>
            }
          </mat-radio-group>

          @if (selectedTemplate; as template) {
            <div class="template-preview" data-testid="decision-template-preview">
              <h3>How a decision looks with {{ template.label }}</h3>
              <div class="preview-sections">
                @for (section of previewSections(template); track section.label) {
                  <div class="preview-section">
                    <div class="preview-heading" data-testid="decision-template-preview-heading">{{ section.label }}</div>
                    <div class="preview-hint">{{ section.hint }}</div>
                  </div>
                }
              </div>
              <div class="preview-row">
                <span class="preview-row-label">Decision types</span>
                <span class="preview-chips">
                  @for (type of template.decision_types; track type) {
                    <span class="preview-chip">{{ type }}</span>
                  }
                </span>
              </div>
              <div class="preview-row">
                <span class="preview-row-label">Example titles</span>
                <span class="preview-examples">
                  @for (title of template.example_titles; track title) {
                    <span>{{ title }}</span>
                  }
                </span>
              </div>
              @if (template.caution) {
                <p class="template-caution" data-testid="decision-template-caution">
                  <mat-icon>info</mat-icon>
                  <span>{{ template.caution }}</span>
                </p>
              }
            </div>

            <mat-checkbox data-testid="decision-template-enable-packs" [(ngModel)]="enablePacks">
              Also switch on the suggested relationship packs ({{ packLabels(template) }})
            </mat-checkbox>
            <p class="packs-hint">Packs are only ever added. Packs you already use stay on.</p>
          }
        </mat-card-content>
        <mat-card-actions>
          <button mat-flat-button color="primary" data-testid="decision-template-save"
                  (click)="save()" [disabled]="saving">
            @if (saving) {
              <mat-spinner diameter="20"></mat-spinner>
            } @else {
              <mat-icon>save</mat-icon>
            }
            <span>Save decision template</span>
          </button>
          @if (hasUnsavedChoice) {
            <span class="unsaved-note">Not saved yet</span>
          }
        </mat-card-actions>
      </mat-card>

      <mat-card class="template-card" data-testid="bulk-type-card">
        <mat-card-header>
          <mat-card-title>
            <mat-icon>label</mat-icon>
            Decision types for existing decisions
          </mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <p class="template-intro">
            A type is optional. Tick the decisions that belong together and set their type in one go.
            Only the type changes: titles, text and status stay exactly as they are.
            A decision keeps its type if you change the template later.
          </p>

          <div class="bulk-filters">
            <mat-form-field appearance="outline" class="bulk-search" subscriptSizing="dynamic">
              <mat-label>Search</mat-label>
              <input matInput data-testid="bulk-type-search" [(ngModel)]="searchTerm" (input)="applyFilters()">
              <mat-icon matPrefix>search</mat-icon>
            </mat-form-field>
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Status</mat-label>
              <mat-select data-testid="bulk-type-status" [(ngModel)]="statusFilter" (selectionChange)="applyFilters()">
                <mat-option value="">All</mat-option>
                @for (status of statuses; track status) {
                  <mat-option [value]="status">{{ status | titlecase }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Current type</mat-label>
              <mat-select data-testid="bulk-type-current" [(ngModel)]="typeFilter" (selectionChange)="applyFilters()">
                <mat-option value="">All</mat-option>
                <mat-option [value]="noType">No type</mat-option>
                @for (type of typesInUse; track type) {
                  <mat-option [value]="type">{{ type }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
          </div>

          @if (loadingDecisions) {
            <div class="template-loading">
              <mat-spinner diameter="32"></mat-spinner>
            </div>
          } @else if (decisions.length === 0) {
            <p class="bulk-empty" data-testid="bulk-type-empty">There are no decisions yet.</p>
          } @else {
            <div class="bulk-list" role="group" aria-label="Decisions">
              <div class="bulk-row bulk-row-head">
                <mat-checkbox data-testid="bulk-type-select-all"
                              [checked]="allShownSelected" [indeterminate]="someShownSelected"
                              (change)="toggleAllShown($event.checked)">
                  Select all {{ shown.length }} shown
                </mat-checkbox>
                <span class="bulk-count" data-testid="bulk-type-count">{{ selectedIds.size }} selected</span>
              </div>
              @for (decision of shown; track decision.id) {
                <label class="bulk-row" data-testid="bulk-type-row">
                  <mat-checkbox [checked]="selectedIds.has(decision.id)"
                                (change)="toggle(decision.id, $event.checked)"></mat-checkbox>
                  <span class="bulk-id">{{ decision.display_id || 'ADR-' + decision.id }}</span>
                  <span class="bulk-title">{{ decision.title }}</span>
                  <span class="bulk-status">{{ decision.status | titlecase }}</span>
                  <span class="bulk-type" data-testid="bulk-type-row-type" [class.none]="!decision.decision_type">
                    {{ decision.decision_type || 'No type' }}
                  </span>
                </label>
              }
              @if (shown.length === 0) {
                <p class="bulk-empty">No decisions match these filters.</p>
              }
            </div>

            <div class="bulk-actions">
              <mat-form-field appearance="outline" class="bulk-type-field" subscriptSizing="dynamic">
                <mat-label>Type</mat-label>
                <mat-select data-testid="bulk-type-select" [(ngModel)]="bulkType">
                  @for (type of tenantTemplate.template.decision_types; track type) {
                    <mat-option [value]="type">{{ type }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
              <button mat-flat-button color="primary" data-testid="bulk-type-set"
                      (click)="applyType(bulkType)" [disabled]="applying || selectedIds.size === 0 || !bulkType">
                Set type
              </button>
              <button mat-stroked-button data-testid="bulk-type-clear"
                      (click)="applyType(null)" [disabled]="applying || selectedIds.size === 0">
                Clear type
              </button>
            </div>
            <p class="packs-hint">
              The types offered are those of the saved template ({{ tenantTemplate.template.label }}).
            </p>
          }
        </mat-card-content>
      </mat-card>
    }
  `,
  styles: [`
    .template-card {
      margin-bottom: 24px;
    }

    .template-card mat-card-title {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 18px;
    }

    .template-card mat-card-content {
      padding-top: 12px;
    }

    .template-loading {
      display: flex;
      justify-content: center;
      padding: 32px;
    }

    .template-intro {
      margin: 0 0 12px;
      color: #475569;
      line-height: 1.6;
      max-width: 760px;
    }

    .template-guarantee,
    .template-caution {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      margin: 0 0 20px;
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 14px;
      line-height: 1.5;
    }

    .template-guarantee {
      background: #ecfdf5;
      border: 1px solid #a7f3d0;
      color: #065f46;
    }

    .template-caution {
      margin: 12px 0 0;
      background: #fffbeb;
      border: 1px solid #fde68a;
      color: #78350f;
    }

    .template-guarantee mat-icon,
    .template-caution mat-icon {
      flex: 0 0 auto;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .industry-field {
      display: block;
      max-width: 760px;
    }

    .industry-credit {
      margin: 4px 0 20px;
      font-size: 12px;
      color: #64748b;
    }

    .template-options {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }

    .template-option {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 12px 14px;
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      background: #fafafa;
      cursor: pointer;
    }

    .template-option.selected {
      border-color: #3b82f6;
      background: #eff6ff;
    }

    .template-option p {
      margin: 0 0 0 8px;
      font-size: 13px;
      color: #666;
      line-height: 1.5;
    }

    .template-option-label {
      font-weight: 600;
    }

    .template-badge {
      margin-left: 8px;
      padding: 2px 8px;
      border-radius: 10px;
      background: #fef3c7;
      color: #92400e;
      font-size: 11px;
      font-weight: 600;
      white-space: nowrap;
    }

    .template-badge.neutral {
      background: #e2e8f0;
      color: #475569;
    }

    .template-preview {
      margin-bottom: 20px;
      padding: 16px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #fff;
    }

    .template-preview h3 {
      margin: 0 0 12px;
      font-size: 15px;
      font-weight: 600;
      color: #1e293b;
    }

    .preview-sections {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }

    .preview-section {
      padding: 10px 12px;
      border-left: 3px solid #3b82f6;
      background: #f8fafc;
    }

    .preview-heading {
      font-weight: 600;
      color: #1e3a8a;
    }

    .preview-hint {
      margin-top: 4px;
      font-size: 13px;
      color: #475569;
      line-height: 1.45;
    }

    .preview-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
      margin-top: 10px;
      font-size: 13px;
    }

    .preview-row-label {
      flex: 0 0 110px;
      color: #64748b;
      font-weight: 500;
    }

    .preview-chips,
    .preview-examples {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      flex: 1 1 300px;
    }

    .preview-examples {
      flex-direction: column;
      color: #334155;
    }

    .preview-chip {
      padding: 3px 10px;
      border-radius: 12px;
      background: #eef2ff;
      color: #3730a3;
    }

    .packs-hint {
      margin: 4px 0 0;
      font-size: 12px;
      color: #64748b;
    }

    mat-card-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 8px 16px 16px;
    }

    mat-card-actions button mat-spinner {
      display: inline-block;
      margin-right: 8px;
    }

    .unsaved-note {
      font-size: 13px;
      color: #92400e;
    }

    .template-error,
    .bulk-empty {
      margin: 12px 0;
      color: #64748b;
    }

    .bulk-filters {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;
    }

    .bulk-search {
      flex: 1 1 240px;
    }

    .bulk-list {
      max-height: 420px;
      overflow-y: auto;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
    }

    .bulk-row {
      display: grid;
      grid-template-columns: 40px 90px minmax(0, 1fr) 100px minmax(120px, 220px);
      align-items: center;
      gap: 8px;
      padding: 4px 12px;
      border-top: 1px solid #f1f5f9;
      font-size: 14px;
      cursor: pointer;
    }

    .bulk-row-head {
      display: flex;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 1;
      border-top: none;
      background: #f8fafc;
      cursor: default;
    }

    .bulk-id,
    .bulk-status,
    .bulk-count {
      color: #64748b;
      font-size: 13px;
    }

    .bulk-title {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .bulk-type {
      color: #3730a3;
      font-size: 13px;
    }

    .bulk-type.none {
      color: #94a3b8;
      font-style: italic;
    }

    .bulk-actions {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      margin-top: 16px;
    }

    .bulk-type-field {
      flex: 0 1 320px;
    }

    @media (max-width: 700px) {
      .bulk-row {
        grid-template-columns: 40px minmax(0, 1fr);
      }

      .bulk-id,
      .bulk-status {
        display: none;
      }

      .bulk-type {
        grid-column: 2;
      }
    }
  `]
})
export class DecisionTemplateSettingsComponent implements OnInit {
  /** Emitted after suggested relationship packs were switched on, so the packs tab can reload. */
  @Output() packsChanged = new EventEmitter<string[]>();

  readonly noType = NO_TYPE;
  readonly statuses: DecisionStatus[] = ['proposed', 'accepted', 'archived', 'superseded'];

  loading = true;
  saving = false;
  catalog: DecisionTemplateCatalog | null = null;
  tenantTemplate: TenantDecisionTemplate | null = null;

  selectedTemplateId = '';
  selectedIndustry: string | null = null;
  enablePacks = false;

  // Bulk types
  loadingDecisions = true;
  applying = false;
  decisions: Decision[] = [];
  shown: Decision[] = [];
  selectedIds = new Set<number>();
  searchTerm = '';
  statusFilter = '';
  typeFilter = '';
  bulkType: string | null = null;

  constructor(
    private templateService: DecisionTemplateService,
    private decisionService: DecisionService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    forkJoin({
      catalog: this.templateService.getCatalog(),
      tenantTemplate: this.templateService.getTenantTemplate()
    }).subscribe({
      next: ({ catalog, tenantTemplate }) => {
        this.catalog = catalog;
        this.setTenantTemplate(tenantTemplate);
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      }
    });
    this.loadDecisions();
  }

  private setTenantTemplate(tenantTemplate: TenantDecisionTemplate): void {
    this.tenantTemplate = tenantTemplate;
    this.selectedTemplateId = tenantTemplate.template_id;
    this.selectedIndustry = tenantTemplate.industry;
    this.enablePacks = false;
    if (this.bulkType && !tenantTemplate.template.decision_types.includes(this.bulkType)) {
      this.bulkType = null;
    }
  }

  get selectedTemplate(): DecisionTemplate | null {
    return this.catalog?.templates.find(template => template.id === this.selectedTemplateId) || null;
  }

  get suggestedTemplateId(): string {
    const industry = this.catalog?.industries.find((item: IndustrySection) => item.code === this.selectedIndustry);
    return industry?.suggested_template_id || this.catalog?.default_template_id || '';
  }

  get hasUnsavedChoice(): boolean {
    return !!this.tenantTemplate && (
      this.selectedTemplateId !== this.tenantTemplate.template_id ||
      this.selectedIndustry !== this.tenantTemplate.industry ||
      this.enablePacks
    );
  }

  /** Choosing an industry preselects the template it suggests; nothing is saved until Save. */
  onIndustryChange(): void {
    if (this.selectedIndustry) {
      this.selectedTemplateId = this.suggestedTemplateId;
      this.enablePacks = false;
    }
  }

  previewSections(template: DecisionTemplate) {
    return [template.sections.context, template.sections.decision, template.sections.consequences];
  }

  packLabels(template: DecisionTemplate): string {
    return template.suggested_packs.map(pack => pack.label).join(', ');
  }

  save(): void {
    if (!this.selectedTemplateId || this.saving) return;

    this.saving = true;
    this.templateService.updateTenantTemplate({
      template_id: this.selectedTemplateId,
      industry: this.selectedIndustry,
      enable_suggested_packs: this.enablePacks
    }).subscribe({
      next: (tenantTemplate) => {
        const added = tenantTemplate.added_pack_ids || [];
        this.setTenantTemplate(tenantTemplate);
        this.saving = false;
        if (added.length > 0) {
          this.packsChanged.emit(added);
        }
        this.snackBar.open(
          `Decision template saved: ${tenantTemplate.template.label}. Your decisions were not altered.`,
          'Close',
          { duration: 5000 }
        );
      },
      error: (err) => {
        this.saving = false;
        this.snackBar.open(err.error?.error || 'Failed to save the decision template', 'Close', { duration: 4000 });
      }
    });
  }

  // ----- Bulk types -----

  loadDecisions(): void {
    this.loadingDecisions = true;
    this.decisionService.getDecisions().subscribe({
      next: (decisions) => {
        this.decisions = decisions;
        const liveIds = new Set(decisions.map(decision => decision.id));
        this.selectedIds = new Set([...this.selectedIds].filter(id => liveIds.has(id)));
        this.applyFilters();
        this.loadingDecisions = false;
      },
      error: () => {
        this.decisions = [];
        this.shown = [];
        this.loadingDecisions = false;
      }
    });
  }

  get typesInUse(): string[] {
    return Array.from(
      new Set(this.decisions.map(decision => decision.decision_type).filter((type): type is string => !!type))
    ).sort((a, b) => a.localeCompare(b));
  }

  applyFilters(): void {
    const term = this.searchTerm.trim().toLowerCase();
    this.shown = this.decisions.filter(decision => {
      const matchesSearch = !term ||
        decision.title.toLowerCase().includes(term) ||
        (decision.display_id || '').toLowerCase().includes(term) ||
        (decision.context || '').toLowerCase().includes(term) ||
        (decision.decision || '').toLowerCase().includes(term);
      const matchesStatus = !this.statusFilter || decision.status === this.statusFilter;
      const matchesType = !this.typeFilter ||
        (this.typeFilter === NO_TYPE ? !decision.decision_type : decision.decision_type === this.typeFilter);
      return matchesSearch && matchesStatus && matchesType;
    });
  }

  get allShownSelected(): boolean {
    return this.shown.length > 0 && this.shown.every(decision => this.selectedIds.has(decision.id));
  }

  get someShownSelected(): boolean {
    return !this.allShownSelected && this.shown.some(decision => this.selectedIds.has(decision.id));
  }

  toggle(id: number, checked: boolean): void {
    if (checked) {
      this.selectedIds.add(id);
    } else {
      this.selectedIds.delete(id);
    }
  }

  toggleAllShown(checked: boolean): void {
    for (const decision of this.shown) {
      this.toggle(decision.id, checked);
    }
  }

  /** Set the type of the ticked decisions, or clear it with null. Sent in batches the server accepts. */
  applyType(decisionType: string | null): void {
    const ids = [...this.selectedIds];
    if (ids.length === 0 || this.applying) return;

    const batches: number[][] = [];
    for (let start = 0; start < ids.length; start += BULK_DECISION_TYPE_MAX) {
      batches.push(ids.slice(start, start + BULK_DECISION_TYPE_MAX));
    }

    this.applying = true;
    from(batches).pipe(
      concatMap(batch => this.templateService.bulkSetDecisionType(batch, decisionType)),
      toArray()
    ).subscribe({
      next: (results) => {
        const updated = results.reduce((total, result) => total + result.updated, 0);
        this.applying = false;
        this.selectedIds = new Set<number>();
        this.loadDecisions();
        const what = decisionType === null ? 'Type cleared on' : `Type set to "${decisionType}" on`;
        this.snackBar.open(`${what} ${updated} ${updated === 1 ? 'decision' : 'decisions'}.`, 'Close', { duration: 5000 });
      },
      error: (err) => {
        this.applying = false;
        // Earlier batches may have been saved: show the list as it now is
        this.loadDecisions();
        this.snackBar.open(err.error?.error || 'Failed to set the decision type', 'Close', { duration: 4000 });
      }
    });
  }
}
