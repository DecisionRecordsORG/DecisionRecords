import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';

import { DecisionModalComponent } from './decision-modal.component';
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
    dialogRef = jasmine.createSpyObj<MatDialogRef<DecisionModalComponent>>('MatDialogRef', ['close']);
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
        {
          provide: MAT_DIALOG_DATA,
          useValue: {
            mode: 'view',
            decisionId: 42,
            tenant: 'example.com'
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(DecisionModalComponent);
    component = fixture.componentInstance;
  });

  it('keeps the modal open when spaces fail to load but the decision request succeeds', fakeAsync(() => {
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
});
