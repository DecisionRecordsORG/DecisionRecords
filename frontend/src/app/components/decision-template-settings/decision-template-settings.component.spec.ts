import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';

import { DecisionTemplateSettingsComponent } from './decision-template-settings.component';
import { DecisionService } from '../../services/decision.service';
import { BULK_DECISION_TYPE_MAX, DecisionTemplateService } from '../../services/decision-template.service';
import { TEMPLATE_CATALOG, governanceTenantTemplate, tenantTemplate } from '../../services/decision-template.testing';
import { Decision } from '../../models/decision.model';

describe('DecisionTemplateSettingsComponent', () => {
  let fixture: ComponentFixture<DecisionTemplateSettingsComponent>;
  let component: DecisionTemplateSettingsComponent;
  let templateService: jasmine.SpyObj<DecisionTemplateService>;
  let decisionService: jasmine.SpyObj<DecisionService>;
  let snackBarOpen: jasmine.Spy;

  function decision(id: number, title: string, status: string, decision_type: string | null): Decision {
    return {
      id, display_id: `DR-${id}`, title, context: `Context ${id}`, decision: `Decision ${id}`,
      consequences: `Consequences ${id}`, status, decision_type,
      created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z'
    } as Decision;
  }

  const decisions: Decision[] = [
    decision(1, 'Pay review', 'accepted', null),
    decision(2, 'New laptop', 'proposed', 'Spending'),
    decision(3, 'Remote work', 'accepted', null)
  ];

  function text(testId: string): string {
    const element: HTMLElement | null = fixture.nativeElement.querySelector(`[data-testid="${testId}"]`);
    return (element?.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function create(): void {
    fixture = TestBed.createComponent(DecisionTemplateSettingsComponent);
    component = fixture.componentInstance;
    snackBarOpen = spyOn((component as any).snackBar, 'open');
    fixture.detectChanges();
  }

  beforeEach(async () => {
    templateService = jasmine.createSpyObj<DecisionTemplateService>(
      'DecisionTemplateService', ['getCatalog', 'getTenantTemplate', 'updateTenantTemplate', 'bulkSetDecisionType']
    );
    decisionService = jasmine.createSpyObj<DecisionService>('DecisionService', ['getDecisions']);
    templateService.getCatalog.and.returnValue(of(TEMPLATE_CATALOG));
    templateService.getTenantTemplate.and.returnValue(of(tenantTemplate({ can_manage: true })));
    decisionService.getDecisions.and.callFake(() => of(decisions.map(item => ({ ...item }))));

    await TestBed.configureTestingModule({
      imports: [DecisionTemplateSettingsComponent, NoopAnimationsModule],
      providers: [
        { provide: DecisionTemplateService, useValue: templateService },
        { provide: DecisionService, useValue: decisionService }
      ]
    }).compileComponents();
  });

  describe('template card', () => {
    it('shows the guarantee, the Eurostat credit and a preview of the current headings', () => {
      create();

      const guarantee: HTMLElement = fixture.nativeElement.querySelector('[data-testid="decision-template-guarantee"] span');
      expect(guarantee.textContent).toBe(
        'Changing the template changes headings and prompts only. ' +
        'Your decisions are not altered, and you can change back at any time.'
      );
      expect(text('decision-template-credit')).toBe('Industry sections: NACE Rev. 2.1, Eurostat, CC BY 4.0');
      const headings = Array.from(fixture.nativeElement.querySelectorAll('[data-testid="decision-template-preview-heading"]'))
        .map((heading: any) => heading.textContent.trim());
      expect(headings).toEqual(['Context', 'Decision', 'Consequences']);
      expect(component.selectedTemplateId).toBe('general');
      expect(component.hasUnsavedChoice).toBeFalse();
    });

    it('previews the headings and the caution of the template that is picked, before saving', () => {
      create();

      component.selectedTemplateId = 'governance';
      fixture.detectChanges();

      const headings = Array.from(fixture.nativeElement.querySelectorAll('[data-testid="decision-template-preview-heading"]'))
        .map((heading: any) => heading.textContent.trim());
      expect(headings).toEqual(['Matter and background', 'Decision and reasons', 'Alternatives, interests and implications']);
      expect(text('decision-template-caution')).toContain('Do not record decisions about identifiable patients');
      expect(component.hasUnsavedChoice).toBeTrue();
      expect(templateService.updateTenantTemplate).not.toHaveBeenCalled();
    });

    it('an industry preselects the template it suggests, and any other template can still be picked', () => {
      create();

      component.selectedIndustry = 'Q';
      component.onIndustryChange();
      fixture.detectChanges();

      expect(component.selectedTemplateId).toBe('governance');
      expect(text('decision-template-suggested')).toBe('Suggested for your industry');

      component.selectedTemplateId = 'general';
      templateService.updateTenantTemplate.and.returnValue(of(tenantTemplate({ industry: 'Q', template_chosen: true, can_manage: true })));
      component.save();

      expect(templateService.updateTenantTemplate).toHaveBeenCalledOnceWith({
        template_id: 'general', industry: 'Q', enable_suggested_packs: false
      });
    });

    it('leaves the suggested packs unticked by default and says they are only added', () => {
      create();

      expect(component.enablePacks).toBeFalse();
      expect(text('decision-template-enable-packs')).toBe(
        'Also switch on the suggested relationship packs (Core, People & Policy)'
      );
      expect(fixture.nativeElement.textContent).toContain('Packs are only ever added.');
    });

    it('saves the choice, tells the packs tab when packs were added, and says decisions were not altered', () => {
      create();
      const emitted: string[][] = [];
      component.packsChanged.subscribe(added => emitted.push(added));
      templateService.updateTenantTemplate.and.returnValue(
        of(governanceTenantTemplate({ can_manage: true, added_pack_ids: ['people', 'finance'] }))
      );
      component.selectedTemplateId = 'governance';
      component.enablePacks = true;

      component.save();
      fixture.detectChanges();

      expect(templateService.updateTenantTemplate).toHaveBeenCalledOnceWith({
        template_id: 'governance', industry: null, enable_suggested_packs: true
      });
      expect(emitted).toEqual([['people', 'finance']]);
      expect(component.enablePacks).toBeFalse();
      expect(component.hasUnsavedChoice).toBeFalse();
      expect(snackBarOpen.calls.mostRecent().args[0]).toBe(
        'Decision template saved: Governance and committee. Your decisions were not altered.'
      );
      // The bulk card now offers the new template's types
      expect(component.tenantTemplate?.template.decision_types).toEqual(['Appointment', 'Service change']);
    });

    it('shows the server message when saving fails and keeps the choice on screen', () => {
      create();
      templateService.updateTenantTemplate.and.returnValue(throwError(() => new HttpErrorResponse({
        status: 400, error: { error: 'Unknown decision template: nope' }
      })));
      component.selectedTemplateId = 'governance';

      component.save();

      expect(snackBarOpen.calls.mostRecent().args[0]).toBe('Unknown decision template: nope');
      expect(component.selectedTemplateId).toBe('governance');
      expect(component.saving).toBeFalse();
    });

    it('says so when the templates cannot be loaded', () => {
      templateService.getTenantTemplate.and.returnValue(throwError(() => new HttpErrorResponse({ status: 500 })));
      create();

      expect(text('decision-template-card')).toContain('Decision templates could not be loaded.');
      expect(fixture.nativeElement.querySelector('[data-testid="bulk-type-card"]')).toBeNull();
    });
  });

  describe('bulk types', () => {
    it('lists the decisions with their current type', () => {
      create();

      const rows = Array.from(fixture.nativeElement.querySelectorAll('[data-testid="bulk-type-row"]'))
        .map((row: any) => ['.bulk-id', '.bulk-title', '.bulk-status', '.bulk-type']
          .map(cell => row.querySelector(cell).textContent.trim()));
      expect(rows).toEqual([
        ['DR-1', 'Pay review', 'Accepted', 'No type'],
        ['DR-2', 'New laptop', 'Proposed', 'Spending'],
        ['DR-3', 'Remote work', 'Accepted', 'No type']
      ]);
      expect(text('bulk-type-count')).toBe('0 selected');
    });

    it('filters by search, status and current type', () => {
      create();

      component.searchTerm = 'laptop';
      component.applyFilters();
      expect(component.shown.map(item => item.id)).toEqual([2]);

      component.searchTerm = '';
      component.statusFilter = 'accepted';
      component.applyFilters();
      expect(component.shown.map(item => item.id)).toEqual([1, 3]);

      component.statusFilter = '';
      component.typeFilter = component.noType;
      component.applyFilters();
      expect(component.shown.map(item => item.id)).toEqual([1, 3]);

      component.typeFilter = 'Spending';
      component.applyFilters();
      expect(component.shown.map(item => item.id)).toEqual([2]);
      expect(component.typesInUse).toEqual(['Spending']);
    });

    it('"select all" ticks only the decisions that are shown', () => {
      create();
      component.typeFilter = component.noType;
      component.applyFilters();

      component.toggleAllShown(true);

      expect([...component.selectedIds]).toEqual([1, 3]);
      expect(component.allShownSelected).toBeTrue();
      component.toggle(3, false);
      expect(component.someShownSelected).toBeTrue();
    });

    it('sets the chosen type on the ticked decisions and reloads the list', () => {
      create();
      templateService.bulkSetDecisionType.and.returnValue(
        of({ message: 'Decision type set', decision_type: 'Policy', updated: 2, unchanged: 0, skipped_ids: [] })
      );
      component.toggle(1, true);
      component.toggle(3, true);
      component.bulkType = 'Policy';

      component.applyType(component.bulkType);

      expect(templateService.bulkSetDecisionType).toHaveBeenCalledOnceWith([1, 3], 'Policy');
      expect(component.selectedIds.size).toBe(0);
      expect(decisionService.getDecisions).toHaveBeenCalledTimes(2);
      expect(snackBarOpen.calls.mostRecent().args[0]).toBe('Type set to "Policy" on 2 decisions.');
    });

    it('clears the type with null', () => {
      create();
      templateService.bulkSetDecisionType.and.returnValue(
        of({ message: 'Decision type cleared', decision_type: null, updated: 1, unchanged: 0, skipped_ids: [] })
      );
      component.toggle(2, true);

      component.applyType(null);

      expect(templateService.bulkSetDecisionType).toHaveBeenCalledOnceWith([2], null);
      expect(snackBarOpen.calls.mostRecent().args[0]).toBe('Type cleared on 1 decision.');
    });

    it('does nothing when no decision is ticked', () => {
      create();

      component.applyType('Policy');

      expect(templateService.bulkSetDecisionType).not.toHaveBeenCalled();
    });

    it('sends a large selection in batches the server accepts', () => {
      create();
      templateService.bulkSetDecisionType.and.callFake((ids: number[]) =>
        of({ message: 'Decision type set', decision_type: 'Policy', updated: ids.length, unchanged: 0, skipped_ids: [] })
      );
      for (let id = 1; id <= BULK_DECISION_TYPE_MAX + 5; id++) {
        component.toggle(id, true);
      }

      component.applyType('Policy');

      const sizes = templateService.bulkSetDecisionType.calls.allArgs().map(args => (args[0] as number[]).length);
      expect(sizes).toEqual([BULK_DECISION_TYPE_MAX, 5]);
      expect(snackBarOpen.calls.mostRecent().args[0]).toBe(`Type set to "Policy" on ${BULK_DECISION_TYPE_MAX + 5} decisions.`);
    });

    it('shows the server message when it fails and reloads what was saved', () => {
      create();
      templateService.bulkSetDecisionType.and.returnValue(throwError(() => new HttpErrorResponse({
        status: 403, error: { error: 'Permission denied. Admin or Steward role required.' }
      })));
      component.toggle(1, true);

      component.applyType('Policy');

      expect(snackBarOpen.calls.mostRecent().args[0]).toBe('Permission denied. Admin or Steward role required.');
      expect(component.applying).toBeFalse();
      expect(decisionService.getDecisions).toHaveBeenCalledTimes(2);
    });

    it('offers only the types of the saved template', () => {
      templateService.getTenantTemplate.and.returnValue(of(governanceTenantTemplate({ can_manage: true })));
      create();

      expect(component.tenantTemplate?.template.decision_types).toEqual(['Appointment', 'Service change']);
      expect(fixture.nativeElement.textContent).toContain('The types offered are those of the saved template (Governance and committee).');
    });
  });
});
