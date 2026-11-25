import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { DecisionListComponent } from './decision-list.component';
import { DecisionService } from '../../services/decision.service';
import { AuthService } from '../../services/auth.service';
import { Decision } from '../../models/decision.model';
import { tenantTemplate } from '../../services/decision-template.testing';

describe('DecisionListComponent', () => {
  let component: DecisionListComponent;
  let fixture: ComponentFixture<DecisionListComponent>;
  let httpMock: HttpTestingController;

  const mockDecisions: Decision[] = [
    {
      id: 1,
      title: 'Use Angular for Frontend',
      context: 'We need a frontend framework',
      decision: 'Use Angular with Material design',
      status: 'accepted',
      consequences: 'Team needs Angular training',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
      domain: 'example.com'
    },
    {
      id: 2,
      title: 'Use PostgreSQL',
      context: 'Database selection needed',
      decision: 'Use PostgreSQL for data storage',
      status: 'proposed',
      consequences: 'Need to set up replication',
      created_at: '2024-01-03T00:00:00Z',
      updated_at: '2024-01-03T00:00:00Z',
      domain: 'example.com'
    },
    {
      id: 3,
      title: 'Deprecated API',
      context: 'Old API needs replacement',
      decision: 'Deprecate v1 API',
      status: 'archived',
      consequences: 'Clients need migration',
      created_at: '2024-01-04T00:00:00Z',
      updated_at: '2024-01-05T00:00:00Z',
      domain: 'example.com'
    }
  ];

  const mockUser = {
    id: 1,
    email: 'test@example.com',
    name: 'Test User',
    sso_domain: 'example.com',
    is_admin: false,
    created_at: '2024-01-01T00:00:00Z',
    last_login: '2024-01-01T00:00:00Z'
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DecisionListComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        DecisionService,
        AuthService
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(DecisionListComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  /**
   * Answer everything the page asks for when it opens: who is signed in, the
   * decisions, the spaces for the space filter, and the tenant's decision
   * template. The verify() above fails a spec that leaves any of them open,
   * so a new request added to the page has to be answered here.
   */
  function loadPage(decisions: Decision[]): void {
    httpMock.expectOne('/api/user/me').flush(mockUser);
    fixture.detectChanges();
    httpMock.expectOne('/api/decisions').flush(decisions);
    httpMock.expectOne('/api/spaces').flush([]);
    httpMock.expectOne('/api/tenant/decision-template').flush(tenantTemplate());
  }

  it('should create', () => {
    loadPage(mockDecisions);

    expect(component).toBeTruthy();
  });

  it('should load decisions on init', fakeAsync(() => {
    loadPage(mockDecisions);
    tick();

    expect(component.decisions.length).toBe(3);
    expect(component.filteredDecisions.length).toBe(3);
    expect(component.isLoading).toBeFalse();
  }));

  it('should filter decisions by search term', fakeAsync(() => {
    loadPage(mockDecisions);
    tick();

    component.searchTerm = 'Angular';
    component.filterDecisions();

    expect(component.filteredDecisions.length).toBe(1);
    expect(component.filteredDecisions[0].title).toBe('Use Angular for Frontend');
  }));

  it('should filter decisions by status', fakeAsync(() => {
    loadPage(mockDecisions);
    tick();

    component.filterByStatus('accepted');

    expect(component.statusFilter).toBe('accepted');
    expect(component.filteredDecisions.length).toBe(1);
    expect(component.filteredDecisions[0].status).toBe('accepted');
  }));

  it('should clear status filter when empty string passed', fakeAsync(() => {
    loadPage(mockDecisions);
    tick();

    component.filterByStatus('accepted');
    expect(component.filteredDecisions.length).toBe(1);

    component.filterByStatus('');
    expect(component.filteredDecisions.length).toBe(3);
  }));

  it('should combine search and status filters', fakeAsync(() => {
    loadPage(mockDecisions);
    tick();

    component.searchTerm = 'Use';
    component.statusFilter = 'proposed';
    component.filterDecisions();

    expect(component.filteredDecisions.length).toBe(1);
    expect(component.filteredDecisions[0].title).toBe('Use PostgreSQL');
  }));

  it('should search in context field', fakeAsync(() => {
    loadPage(mockDecisions);
    tick();

    component.searchTerm = 'framework';
    component.filterDecisions();

    expect(component.filteredDecisions.length).toBe(1);
    expect(component.filteredDecisions[0].title).toBe('Use Angular for Frontend');
  }));

  it('should search case-insensitively', fakeAsync(() => {
    loadPage(mockDecisions);
    tick();

    component.searchTerm = 'ANGULAR';
    component.filterDecisions();

    expect(component.filteredDecisions.length).toBe(1);
  }));

  it('should show empty state when no decisions', fakeAsync(() => {
    loadPage([]);
    tick();

    expect(component.decisions.length).toBe(0);
    expect(component.filteredDecisions.length).toBe(0);
  }));

  it('should show empty filtered state when no matches', fakeAsync(() => {
    loadPage(mockDecisions);
    tick();

    component.searchTerm = 'nonexistent';
    component.filterDecisions();

    expect(component.filteredDecisions.length).toBe(0);
  }));
});
