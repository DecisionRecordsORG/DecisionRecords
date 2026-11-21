import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpErrorResponse } from '@angular/common/http';
import { Subject, of, throwError } from 'rxjs';

import { DecisionModalComponent, DecisionModalData } from './decision-modal.component';
import { DecisionService } from '../../services/decision.service';
import { SpaceService } from '../../services/space.service';
import { AuthService } from '../../services/auth.service';
import { Decision, DecisionRelationshipCatalog, Space, TenantMember } from '../../models/decision.model';

describe('DecisionModalComponent', () => {
  let component: DecisionModalComponent;
  let fixture: ComponentFixture<DecisionModalComponent>;
  let decisionService: jasmine.SpyObj<DecisionService>;
  let spaceService: jasmine.SpyObj<SpaceService>;
  let dialogRef: jasmine.SpyObj<MatDialogRef<DecisionModalComponent>>;
  let snackBar: jasmine.SpyObj<MatSnackBar>;
  let backdropClicks: Subject<MouseEvent>;
  let keydowns: Subject<KeyboardEvent>;

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

  const emptyCatalog: DecisionRelationshipCatalog = {
    packs: [],
    types: []
  };

  const viewData: DecisionModalData = { mode: 'view', decisionId: 42, tenant: 'example.com' };
  const editData: DecisionModalData = { mode: 'edit', decisionId: 42, tenant: 'example.com' };
  const createData: DecisionModalData = { mode: 'create', tenant: 'example.com' };

  /** Create the modal with the given dialog data (the mode is read in the constructor). */
  function createModal(data: DecisionModalData = viewData): void {
    TestBed.overrideProvider(MAT_DIALOG_DATA, { useValue: data });
    fixture = TestBed.createComponent(DecisionModalComponent);
    component = fixture.componentInstance;
  }

  function stubSuccessfulLoads(): void {
    decisionService.getDecision.and.returnValue(of(mockDecision));
    decisionService.getDecisionRelationshipCatalog.and.returnValue(of(emptyCatalog));
    decisionService.getDecisionReferences.and.returnValue(of([]));
    decisionService.getTenantMembers.and.returnValue(of([{ id: 7, name: 'Ada Lovelace' }] as TenantMember[]));
    spaceService.getSpaces.and.returnValue(of(mockSpaces));
  }

  /** Create the modal in the given mode with every request succeeding, and let it load. */
  function openLoaded(data: DecisionModalData): void {
    stubSuccessfulLoads();
    createModal(data);
    // The component's own imports provide the real snack bar; keep it from opening
    spyOn((component as any).snackBar, 'open');
    fixture.detectChanges();
    tick();
  }

  /** Spy on the confirm dialog the component opens; `result` is what the user picks. */
  function spyOnConfirm(result: boolean | undefined): jasmine.Spy {
    return spyOn((component as any).dialog, 'open').and.returnValue({ afterClosed: () => of(result) });
  }

  function pressKey(key: string): KeyboardEvent {
    const event = new KeyboardEvent('keydown', { key, cancelable: true });
    keydowns.next(event);
    return event;
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
    backdropClicks = new Subject<MouseEvent>();
    keydowns = new Subject<KeyboardEvent>();
    dialogRef = jasmine.createSpyObj<MatDialogRef<DecisionModalComponent>>(
      'MatDialogRef', ['close', 'backdropClick', 'keydownEvents']
    );
    dialogRef.backdropClick.and.returnValue(backdropClicks);
    dialogRef.keydownEvents.and.returnValue(keydowns);
    snackBar = jasmine.createSpyObj<MatSnackBar>('MatSnackBar', ['open']);

    await TestBed.configureTestingModule({
      imports: [DecisionModalComponent, NoopAnimationsModule],
      providers: [
        { provide: DecisionService, useValue: decisionService },
        { provide: SpaceService, useValue: spaceService },
        { provide: AuthService, useValue: { isMasterAccount: false, canDeleteDecisions: true } },
        { provide: MatDialogRef, useValue: dialogRef },
        { provide: MatDialog, useValue: jasmine.createSpyObj<MatDialog>('MatDialog', ['open']) },
        { provide: MatSnackBar, useValue: snackBar },
        { provide: MAT_DIALOG_DATA, useValue: viewData }
      ]
    }).compileComponents();
  });

  it('keeps the modal open when spaces fail to load but the decision request succeeds', fakeAsync(() => {
    createModal();
    decisionService.getDecision.and.returnValue(of(mockDecision));
    decisionService.getDecisionRelationshipCatalog.and.returnValue(of(emptyCatalog));
    decisionService.getDecisionReferences.and.returnValue(of([]));
    decisionService.getTenantMembers.and.returnValue(of([] as TenantMember[]));
    spaceService.getSpaces.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 404, statusText: 'Not Found' }))
    );

    fixture.detectChanges();
    tick();

    expect(component.decision?.id).toBe(42);
    expect(component.isLoading).toBeFalse();
    expect(component.spaces).toEqual(mockSpaces);
    expect(component.selectedSpaceIds).toEqual([10]);
    expect(dialogRef.close).not.toHaveBeenCalled();
    expect(snackBar.open).not.toHaveBeenCalledWith('Failed to load decision', 'Close', { duration: 3000 });
  }));

  it('loads the owner picker from the tenant members endpoint, not the admin user list', fakeAsync(() => {
    createModal();
    const members: TenantMember[] = [{ id: 7, name: 'Ada Lovelace' }, { id: 8, name: 'Grace Hopper' }];
    decisionService.getDecision.and.returnValue(of(mockDecision));
    decisionService.getDecisionRelationshipCatalog.and.returnValue(of(emptyCatalog));
    decisionService.getDecisionReferences.and.returnValue(of([]));
    decisionService.getTenantMembers.and.returnValue(of(members));
    spaceService.getSpaces.and.returnValue(of(mockSpaces));

    fixture.detectChanges();
    tick();

    expect(decisionService.getTenantMembers).toHaveBeenCalledTimes(1);
    expect(component.tenantMembers).toEqual(members);
  }));

  it('still opens the decision when the tenant members request fails', fakeAsync(() => {
    createModal();
    decisionService.getDecision.and.returnValue(of(mockDecision));
    decisionService.getDecisionRelationshipCatalog.and.returnValue(of(emptyCatalog));
    decisionService.getDecisionReferences.and.returnValue(of([]));
    decisionService.getTenantMembers.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 500, statusText: 'Server Error' }))
    );
    spaceService.getSpaces.and.returnValue(of(mockSpaces));

    fixture.detectChanges();
    tick();

    expect(component.decision?.id).toBe(42);
    expect(component.tenantMembers).toEqual([]);
    expect(dialogRef.close).not.toHaveBeenCalled();
  }));

  it('describes the soft delete truthfully in the delete confirmation', () => {
    createModal();
    component.decision = { ...mockDecision, display_id: 'DR-42' } as Decision;
    const openSpy = spyOn((component as any).dialog, 'open').and.returnValue({ afterClosed: () => of(false) });

    component.confirmDelete();

    const message: string = (openSpy.calls.mostRecent().args[1] as any).data.message;
    expect(message).toContain('DR-42');
    expect(message).toContain('permanently erased after 30 days');
    expect(message).toContain('no restore option');
    expect(message).not.toContain('cannot be undone');
    expect(decisionService.deleteDecision).not.toHaveBeenCalled();
  });

  describe('unsaved changes', () => {
    it('takes over Esc and backdrop clicks so the dialog cannot close without going through close()', () => {
      createModal(createData);

      expect(dialogRef.disableClose).toBeTrue();
    });

    it('closes without asking when nothing was entered (X, Cancel, Esc and backdrop)', fakeAsync(() => {
      openLoaded(createData);
      const confirm = spyOnConfirm(true);

      // The preselected default space is not user input
      expect(component.selectedSpaceIds).toEqual([10]);
      expect(component.hasUnsavedChanges()).toBeFalse();

      component.close();
      pressKey('Escape');
      backdropClicks.next(new MouseEvent('click'));

      expect(confirm).not.toHaveBeenCalled();
      expect(dialogRef.close).toHaveBeenCalledTimes(3);
      expect(dialogRef.close).toHaveBeenCalledWith({ action: 'cancelled' });
    }));

    it('asks before closing on Esc when the title was typed, and stays open on Keep Editing', fakeAsync(() => {
      openLoaded(createData);
      const confirm = spyOnConfirm(false);
      component.form.patchValue({ title: 'Draft title' });

      const event = pressKey('Escape');

      expect(event.defaultPrevented).toBeTrue();
      expect(confirm).toHaveBeenCalledTimes(1);
      expect((confirm.calls.mostRecent().args[1] as any).data.title).toBe('Unsaved Changes');
      expect(dialogRef.close).not.toHaveBeenCalled();
      expect(component.form.value.title).toBe('Draft title');
    }));

    it('asks before closing on a backdrop click, and closes on Discard', fakeAsync(() => {
      openLoaded(createData);
      const confirm = spyOnConfirm(true);
      component.form.patchValue({ context: 'Some context' });

      backdropClicks.next(new MouseEvent('click'));

      expect(confirm).toHaveBeenCalledTimes(1);
      expect(dialogRef.close).toHaveBeenCalledOnceWith({ action: 'cancelled' });
    }));

    it('treats dismissing the confirm (Esc on it) as Keep Editing', fakeAsync(() => {
      openLoaded(createData);
      spyOnConfirm(undefined);
      component.form.patchValue({ title: 'Draft title' });

      component.close();

      expect(dialogRef.close).not.toHaveBeenCalled();
    }));

    it('ignores other keys', fakeAsync(() => {
      openLoaded(createData);
      const confirm = spyOnConfirm(true);
      component.form.patchValue({ title: 'Draft title' });

      pressKey('Enter');
      pressKey('a');

      expect(confirm).not.toHaveBeenCalled();
      expect(dialogRef.close).not.toHaveBeenCalled();
    }));

    it('opens only one confirm when Esc is pressed again while it is showing', fakeAsync(() => {
      openLoaded(createData);
      const answer = new Subject<boolean>();
      const confirm = spyOn((component as any).dialog, 'open').and.returnValue({ afterClosed: () => answer });
      component.form.patchValue({ title: 'Draft title' });

      pressKey('Escape');
      pressKey('Escape');
      backdropClicks.next(new MouseEvent('click'));
      expect(confirm).toHaveBeenCalledTimes(1);

      // After Keep Editing, the next attempt asks again
      answer.next(false);
      pressKey('Escape');
      expect(confirm).toHaveBeenCalledTimes(2);
      expect(dialogRef.close).not.toHaveBeenCalled();
    }));

    it('notices a changed owner, which is not part of the reactive form', fakeAsync(() => {
      openLoaded(createData);
      const confirm = spyOnConfirm(false);

      component.selectedOwnerId = 7;

      expect(component.form.dirty).toBeFalse();
      expect(component.hasUnsavedChanges()).toBeTrue();
      pressKey('Escape');
      expect(confirm).toHaveBeenCalledTimes(1);
      expect(dialogRef.close).not.toHaveBeenCalled();
    }));

    it('notices an external owner email', fakeAsync(() => {
      openLoaded(createData);

      component.ownerEmail = 'someone@external.com';

      expect(component.hasUnsavedChanges()).toBeTrue();
    }));

    it('notices a changed space selection', fakeAsync(() => {
      openLoaded(createData);

      component.selectedSpaceIds = [];

      expect(component.hasUnsavedChanges()).toBeTrue();
    }));

    it('notices a relationship row, but not a row that was added and left blank', fakeAsync(() => {
      openLoaded(createData);

      component.addRelationship();
      expect(component.hasUnsavedChanges()).toBeFalse();

      component.editableRelationships[0].notes = 'Depends on the outcome of that one';
      expect(component.hasUnsavedChanges()).toBeTrue();

      component.editableRelationships[0].notes = '';
      component.editableRelationships[0].target_decision_id = 5;
      expect(component.hasUnsavedChanges()).toBeTrue();
    }));

    it('does not ask when a change was undone again', fakeAsync(() => {
      openLoaded(createData);
      const confirm = spyOnConfirm(true);

      component.form.patchValue({ title: 'Draft title' });
      component.selectedOwnerId = 7;
      component.form.patchValue({ title: '' });
      component.selectedOwnerId = null;
      component.close();

      expect(confirm).not.toHaveBeenCalled();
      expect(dialogRef.close).toHaveBeenCalledOnceWith({ action: 'cancelled' });
    }));

    it('keeps input typed before the default space arrived as unsaved', fakeAsync(() => {
      const spaces = new Subject<Space[]>();
      stubSuccessfulLoads();
      spaceService.getSpaces.and.returnValue(spaces);
      createModal(createData);
      fixture.detectChanges();

      component.form.patchValue({ title: 'Typed early' });
      spaces.next(mockSpaces);
      spaces.complete();
      tick();

      expect(component.selectedSpaceIds).toEqual([10]);
      expect(component.hasUnsavedChanges()).toBeTrue();
    }));

    it('closes without asking after a successful save', fakeAsync(() => {
      openLoaded(createData);
      const confirm = spyOnConfirm(true);
      const saved = { ...mockDecision, id: 99, title: 'Draft title' };
      decisionService.createDecision.and.returnValue(of(saved));
      component.form.patchValue({ title: 'Draft title' });
      component.selectedOwnerId = 7;

      component.onSubmit();

      expect(confirm).not.toHaveBeenCalled();
      expect(dialogRef.close).toHaveBeenCalledOnceWith({ action: 'saved', decision: saved });
    }));

    it('still asks after a failed save, because the input is still unsaved', fakeAsync(() => {
      openLoaded(createData);
      const confirm = spyOnConfirm(false);
      decisionService.createDecision.and.returnValue(
        throwError(() => new HttpErrorResponse({ status: 500, statusText: 'Server Error' }))
      );
      component.form.patchValue({ title: 'Draft title' });

      component.onSubmit();
      pressKey('Escape');

      expect(confirm).toHaveBeenCalledTimes(1);
      expect(dialogRef.close).not.toHaveBeenCalled();
    }));

    it('closes a viewed decision on Esc without asking', fakeAsync(() => {
      openLoaded(viewData);
      const confirm = spyOnConfirm(true);

      pressKey('Escape');

      expect(confirm).not.toHaveBeenCalled();
      expect(dialogRef.close).toHaveBeenCalledOnceWith({ action: 'cancelled' });
    }));

    it('does not ask for an opened but unchanged decision, in edit mode or after switching to it', fakeAsync(() => {
      openLoaded(viewData);
      const confirm = spyOnConfirm(true);

      component.switchToEdit();
      expect(component.hasUnsavedChanges()).toBeFalse();
      backdropClicks.next(new MouseEvent('click'));

      expect(confirm).not.toHaveBeenCalled();
      expect(dialogRef.close).toHaveBeenCalledOnceWith({ action: 'cancelled' });
    }));

    it('asks when an existing decision was edited (form field, owner, spaces or relationships)', fakeAsync(() => {
      openLoaded(editData);
      expect(component.hasUnsavedChanges()).toBeFalse();

      component.form.patchValue({ change_reason: 'Typo' });
      expect(component.hasUnsavedChanges()).toBeTrue();
      component.form.patchValue({ change_reason: '' });
      expect(component.hasUnsavedChanges()).toBeFalse();

      component.ownerEmail = 'someone@external.com';
      expect(component.hasUnsavedChanges()).toBeTrue();
      component.ownerEmail = '';

      component.selectedSpaceIds = [];
      expect(component.hasUnsavedChanges()).toBeTrue();
      component.selectedSpaceIds = [10];

      component.editableRelationships.push({ target_decision_id: 5, relationship_type: 'related_to', notes: '' });
      expect(component.hasUnsavedChanges()).toBeTrue();
    }));

    it('warns before the browser unloads the page only when there is unsaved input', fakeAsync(() => {
      openLoaded(createData);

      const clean = new Event('beforeunload', { cancelable: true }) as BeforeUnloadEvent;
      component.onBeforeUnload(clean);
      expect(clean.defaultPrevented).toBeFalse();

      component.selectedOwnerId = 7;
      const dirty = new Event('beforeunload', { cancelable: true }) as BeforeUnloadEvent;
      component.onBeforeUnload(dirty);
      expect(dirty.defaultPrevented).toBeTrue();
    }));
  });
});
