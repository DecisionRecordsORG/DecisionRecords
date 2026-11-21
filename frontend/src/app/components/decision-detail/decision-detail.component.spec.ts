import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable, Subject, isObservable, of, throwError } from 'rxjs';

import { DecisionDetailComponent } from './decision-detail.component';
import { DecisionService } from '../../services/decision.service';
import { SpaceService } from '../../services/space.service';
import { AuthService } from '../../services/auth.service';
import { Decision, Space, TenantMember } from '../../models/decision.model';

describe('DecisionDetailComponent', () => {
  let component: DecisionDetailComponent;
  let fixture: ComponentFixture<DecisionDetailComponent>;
  let decisionService: jasmine.SpyObj<DecisionService>;
  let spaceService: jasmine.SpyObj<SpaceService>;
  let router: Router;
  let spaces$: Subject<Space[]>;
  let authState: { isMasterAccount: boolean; canDeleteDecisions: boolean };

  const mockSpaces: Space[] = [
    {
      id: 10,
      tenant_id: 1,
      name: 'Default Space',
      description: null,
      is_default: true,
      visibility_policy: 'tenant_visible',
      created_by_id: 1,
      created_at: '2026-01-01T00:00:00Z'
    }
  ];

  const mockDecision: Decision = {
    id: 42,
    display_id: 'DR-42',
    title: 'Use event sourcing',
    context: 'Need stronger auditability',
    decision: 'Adopt append-only event storage',
    status: 'accepted',
    consequences: 'More complex read models',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
    spaces: mockSpaces,
    outgoing_relationships: []
  };

  const members: TenantMember[] = [{ id: 7, name: 'Ada Lovelace' }, { id: 8, name: 'Grace Hopper' }];

  /**
   * Create the page for `/example.com/decision/new` (no id) or `/example.com/decision/<id>`.
   * Spaces arrive after the page has initialised, as they do over HTTP.
   */
  function createPage(id?: string, spacesArrive = true): void {
    const params: Record<string, string> = id ? { tenant: 'example.com', id } : { tenant: 'example.com' };
    TestBed.overrideProvider(ActivatedRoute, {
      useValue: { snapshot: { params, paramMap: convertToParamMap(params) } }
    });
    fixture = TestBed.createComponent(DecisionDetailComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    spyOn(router, 'navigate').and.resolveTo(true);
    spyOn((component as any).snackBar, 'open');
    fixture.detectChanges();
    if (spacesArrive) {
      spaces$.next(mockSpaces);
    }
  }

  /** Spy on the confirm dialog the component opens; `result` is what the user picks. */
  function spyOnConfirm(result: boolean | undefined): jasmine.Spy {
    return spyOn((component as any).dialog, 'open').and.returnValue({ afterClosed: () => of(result) });
  }

  function resolveLeave(): boolean {
    const answer = component.confirmDiscardChanges();
    if (!isObservable(answer)) {
      return answer;
    }
    let value: boolean | undefined;
    (answer as Observable<boolean>).subscribe(result => (value = result));
    return value as boolean;
  }

  function beforeUnloadPrevented(): boolean {
    const event = new Event('beforeunload', { cancelable: true }) as BeforeUnloadEvent;
    component.onBeforeUnload(event);
    return event.defaultPrevented;
  }

  beforeEach(async () => {
    decisionService = jasmine.createSpyObj<DecisionService>('DecisionService', [
      'getDecision',
      'getDecisionRelationshipCatalog',
      'getDecisionReferences',
      'getTenantMembers',
      'createDecision',
      'updateDecision',
      'deleteDecision'
    ]);
    spaceService = jasmine.createSpyObj<SpaceService>('SpaceService', ['getSpaces']);
    authState = { isMasterAccount: false, canDeleteDecisions: true };

    decisionService.getDecision.and.returnValue(of(mockDecision));
    decisionService.getDecisionRelationshipCatalog.and.returnValue(of({ packs: [], types: [] }));
    decisionService.getDecisionReferences.and.returnValue(of([]));
    decisionService.getTenantMembers.and.returnValue(of(members));
    spaces$ = new Subject<Space[]>();
    spaceService.getSpaces.and.returnValue(spaces$);

    await TestBed.configureTestingModule({
      imports: [DecisionDetailComponent, NoopAnimationsModule],
      providers: [
        provideRouter([]),
        { provide: DecisionService, useValue: decisionService },
        { provide: SpaceService, useValue: spaceService },
        { provide: AuthService, useValue: authState }
      ]
    }).compileComponents();
  });

  describe('owner picker', () => {
    it('loads members from the tenant members endpoint and lists them by name only', () => {
      createPage();

      expect(decisionService.getTenantMembers).toHaveBeenCalledTimes(1);
      expect(component.tenantMembers).toEqual(members);
    });

    it('keeps the form usable when the members request fails', () => {
      decisionService.getTenantMembers.and.returnValue(
        throwError(() => new HttpErrorResponse({ status: 500, statusText: 'Server Error' }))
      );
      spyOn(console, 'error');

      createPage();

      expect(component.tenantMembers).toEqual([]);
      expect(component.isLoading).toBeFalse();
    });
  });

  describe('delete confirmation', () => {
    it('describes the soft delete truthfully', () => {
      createPage('42');
      const confirm = spyOnConfirm(false);

      component.confirmDelete();

      const message: string = (confirm.calls.mostRecent().args[1] as any).data.message;
      expect(message).toContain('DR-42');
      expect(message).toContain('permanently erased after 30 days');
      expect(message).toContain('no restore option');
      expect(message).not.toContain('cannot be undone');
      expect(decisionService.deleteDecision).not.toHaveBeenCalled();
    });
  });

  describe('unsaved changes on a new decision', () => {
    it('lets the user leave without asking when nothing was entered', () => {
      createPage();
      const confirm = spyOnConfirm(true);

      // The preselected default space is not user input
      expect(component.selectedSpaceIds).toEqual([10]);
      expect(component.hasUnsavedChanges()).toBeFalse();
      expect(resolveLeave()).toBeTrue();
      expect(beforeUnloadPrevented()).toBeFalse();
      expect(confirm).not.toHaveBeenCalled();
    });

    it('asks before leaving when a field was typed, and stays on Keep Editing', () => {
      createPage();
      const confirm = spyOnConfirm(false);
      component.form.patchValue({ title: 'Draft title' });

      expect(resolveLeave()).toBeFalse();
      expect(confirm).toHaveBeenCalledTimes(1);
      expect((confirm.calls.mostRecent().args[1] as any).data.title).toBe('Unsaved Changes');
      expect(component.form.value.title).toBe('Draft title');
    });

    it('leaves on Discard, and treats dismissing the confirm as Keep Editing', () => {
      createPage();
      component.form.patchValue({ title: 'Draft title' });

      const confirm = spyOnConfirm(true);
      expect(resolveLeave()).toBeTrue();

      confirm.and.returnValue({ afterClosed: () => of(undefined) });
      expect(resolveLeave()).toBeFalse();
    });

    it('notices owner, external owner email, spaces and relationships, which are not in the reactive form', () => {
      createPage();

      component.selectedOwnerId = 7;
      expect(component.form.dirty).toBeFalse();
      expect(component.hasUnsavedChanges()).toBeTrue();
      component.selectedOwnerId = null;
      expect(component.hasUnsavedChanges()).toBeFalse();

      component.ownerEmail = 'someone@external.com';
      expect(component.hasUnsavedChanges()).toBeTrue();
      component.ownerEmail = '';

      component.selectedSpaceIds = [];
      expect(component.hasUnsavedChanges()).toBeTrue();
      component.selectedSpaceIds = [10];

      component.addRelationship();
      expect(component.hasUnsavedChanges()).toBeFalse();
      component.editableRelationships[0].target_decision_id = 5;
      expect(component.hasUnsavedChanges()).toBeTrue();
    });

    it('warns before the browser unloads the page when there is unsaved input', () => {
      createPage();
      component.ownerEmail = 'someone@external.com';

      expect(beforeUnloadPrevented()).toBeTrue();
    });

    it('keeps input typed before the default space arrived as unsaved', () => {
      createPage(undefined, false);

      component.form.patchValue({ title: 'Typed early' });
      spaces$.next(mockSpaces);

      expect(component.selectedSpaceIds).toEqual([10]);
      expect(component.hasUnsavedChanges()).toBeTrue();
    });

    it('does not ask when navigating to the decision after a successful create', () => {
      createPage();
      const confirm = spyOnConfirm(true);
      decisionService.createDecision.and.returnValue(of({ ...mockDecision, id: 99 }));
      component.form.patchValue({ title: 'Draft title' });
      component.selectedOwnerId = 7;

      component.onSubmit();

      expect(router.navigate).toHaveBeenCalledWith(['/', 'example.com', 'decision', 99]);
      expect(resolveLeave()).toBeTrue();
      expect(beforeUnloadPrevented()).toBeFalse();
      expect(confirm).not.toHaveBeenCalled();
    });

    it('still asks after a failed create, because the input is still unsaved', () => {
      createPage();
      spyOnConfirm(false);
      decisionService.createDecision.and.returnValue(
        throwError(() => new HttpErrorResponse({ status: 500, statusText: 'Server Error' }))
      );
      component.form.patchValue({ title: 'Draft title' });

      component.onSubmit();

      expect(component.hasUnsavedChanges()).toBeTrue();
      expect(resolveLeave()).toBeFalse();
    });

    it('never asks a master account, which cannot edit', () => {
      authState.isMasterAccount = true;
      createPage();
      const confirm = spyOnConfirm(true);

      expect(resolveLeave()).toBeTrue();
      expect(confirm).not.toHaveBeenCalled();
    });
  });

  describe('unsaved changes on an existing decision', () => {
    it('does not ask for a decision that was opened and not changed', () => {
      createPage('42');
      const confirm = spyOnConfirm(true);

      expect(component.hasUnsavedChanges()).toBeFalse();
      expect(resolveLeave()).toBeTrue();
      expect(beforeUnloadPrevented()).toBeFalse();
      expect(confirm).not.toHaveBeenCalled();
    });

    it('does not ask while the decision is still loading', () => {
      decisionService.getDecision.and.returnValue(new Subject<Decision>());
      createPage('42');

      expect(component.hasUnsavedChanges()).toBeFalse();
    });

    it('asks after an edit and stops asking once the change is saved', () => {
      createPage('42');
      spyOnConfirm(false);
      decisionService.updateDecision.and.returnValue(of({ ...mockDecision, title: 'Use event sourcing everywhere' }));

      component.form.patchValue({ title: 'Use event sourcing everywhere', change_reason: 'Scope' });
      component.selectedOwnerId = 8;
      expect(resolveLeave()).toBeFalse();

      component.onSubmit();

      expect(component.hasUnsavedChanges()).toBeFalse();
      expect(resolveLeave()).toBeTrue();

      // A later edit is unsaved again
      component.form.patchValue({ context: 'New context' });
      expect(component.hasUnsavedChanges()).toBeTrue();
    });

    it('does not ask when navigating away after deleting the decision', () => {
      createPage('42');
      decisionService.deleteDecision.and.returnValue(of(undefined as any));
      component.form.patchValue({ title: 'Edited before deleting' });

      component.deleteDecision();

      expect(router.navigate).toHaveBeenCalledWith(['/']);
      expect(resolveLeave()).toBeTrue();
    });
  });
});
