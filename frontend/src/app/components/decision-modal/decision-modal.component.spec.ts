import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';

import { DecisionModalComponent } from './decision-modal.component';
import { DecisionService } from '../../services/decision.service';
import { SpaceService } from '../../services/space.service';
import { AdminService } from '../../services/admin.service';
import { AuthService } from '../../services/auth.service';
import { Decision, DecisionRelationshipCatalog, Space, User } from '../../models/decision.model';

describe('DecisionModalComponent', () => {
  let component: DecisionModalComponent;
  let fixture: ComponentFixture<DecisionModalComponent>;
  let decisionService: jasmine.SpyObj<DecisionService>;
  let spaceService: jasmine.SpyObj<SpaceService>;
  let adminService: jasmine.SpyObj<AdminService>;
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
      'createDecision',
      'updateDecision',
      'deleteDecision'
    ]);
    spaceService = jasmine.createSpyObj<SpaceService>('SpaceService', ['getSpaces']);
    adminService = jasmine.createSpyObj<AdminService>('AdminService', ['getUsers']);
    dialogRef = jasmine.createSpyObj<MatDialogRef<DecisionModalComponent>>('MatDialogRef', ['close']);
    snackBar = jasmine.createSpyObj<MatSnackBar>('MatSnackBar', ['open']);

    await TestBed.configureTestingModule({
      imports: [DecisionModalComponent, NoopAnimationsModule],
      providers: [
        { provide: DecisionService, useValue: decisionService },
        { provide: SpaceService, useValue: spaceService },
        { provide: AdminService, useValue: adminService },
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
    adminService.getUsers.and.returnValue(of([] as User[]));
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
});
