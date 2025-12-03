import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { DecisionService, CreateDecisionRequest } from './decision.service';
import { Decision, DecisionHistory } from '../models/decision.model';

describe('DecisionService', () => {
  let service: DecisionService;
  let httpMock: HttpTestingController;

  const mockDecision: Decision = {
    id: 1,
    title: 'Test Decision',
    context: 'Test context',
    decision: 'Test decision content',
    status: 'proposed',
    consequences: 'Test consequences',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    domain: 'example.com'
  };

  const mockDecisions: Decision[] = [
    mockDecision,
    { ...mockDecision, id: 2, title: 'Decision 2', status: 'accepted' }
  ];

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        DecisionService,
        provideHttpClient(),
        provideHttpClientTesting()
      ]
    });

    service = TestBed.inject(DecisionService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('getDecisions', () => {
    it('should return a list of decisions', () => {
      service.getDecisions().subscribe(decisions => {
        expect(decisions).toEqual(mockDecisions);
        expect(decisions.length).toBe(2);
      });

      const req = httpMock.expectOne('/api/decisions');
      expect(req.request.method).toBe('GET');
      req.flush(mockDecisions);
    });

    it('should handle empty list', () => {
      service.getDecisions().subscribe(decisions => {
        expect(decisions).toEqual([]);
        expect(decisions.length).toBe(0);
      });

      const req = httpMock.expectOne('/api/decisions');
      req.flush([]);
    });
  });

  describe('getDecision', () => {
    it('should return a single decision by id', () => {
      service.getDecision(1).subscribe(decision => {
        expect(decision).toEqual(mockDecision);
        expect(decision.id).toBe(1);
      });

      const req = httpMock.expectOne('/api/decisions/1');
      expect(req.request.method).toBe('GET');
      req.flush(mockDecision);
    });

    it('should handle 404 error', () => {
      service.getDecision(999).subscribe({
        next: () => fail('should have failed'),
        error: (error) => {
          expect(error.status).toBe(404);
        }
      });

      const req = httpMock.expectOne('/api/decisions/999');
      req.flush({ error: 'Not found' }, { status: 404, statusText: 'Not Found' });
    });
  });

  describe('createDecision', () => {
    it('should create a new decision', () => {
      const newDecision: CreateDecisionRequest = {
        title: 'New Decision',
        context: 'New context',
        decision: 'New decision content',
        status: 'proposed',
        consequences: 'New consequences'
      };

      service.createDecision(newDecision).subscribe(decision => {
        expect(decision.title).toBe('New Decision');
        expect(decision.id).toBe(3);
      });

      const req = httpMock.expectOne('/api/decisions');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(newDecision);
      req.flush({ ...mockDecision, id: 3, ...newDecision });
    });

    it('should handle validation error', () => {
      const invalidDecision: CreateDecisionRequest = {
        title: '',
        context: '',
        decision: '',
        status: 'proposed',
        consequences: ''
      };

      service.createDecision(invalidDecision).subscribe({
        next: () => fail('should have failed'),
        error: (error) => {
          expect(error.status).toBe(400);
        }
      });

      const req = httpMock.expectOne('/api/decisions');
      req.flush({ error: 'Missing required field: title' }, { status: 400, statusText: 'Bad Request' });
    });
  });

  describe('updateDecision', () => {
    it('should update an existing decision', () => {
      const update = { title: 'Updated Title', change_reason: 'Updated for clarity' };

      service.updateDecision(1, update).subscribe(decision => {
        expect(decision.title).toBe('Updated Title');
      });

      const req = httpMock.expectOne('/api/decisions/1');
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual(update);
      req.flush({ ...mockDecision, title: 'Updated Title' });
    });
  });

  describe('deleteDecision', () => {
    it('should delete a decision', () => {
      service.deleteDecision(1).subscribe(() => {
        expect(true).toBe(true); // Request completed successfully
      });

      const req = httpMock.expectOne('/api/decisions/1');
      expect(req.request.method).toBe('DELETE');
      req.flush({});
    });

    it('should handle deletion of non-existent decision', () => {
      service.deleteDecision(999).subscribe({
        next: () => fail('should have failed'),
        error: (error) => {
          expect(error.status).toBe(404);
        }
      });

      const req = httpMock.expectOne('/api/decisions/999');
      req.flush({ error: 'Not found' }, { status: 404, statusText: 'Not Found' });
    });
  });

  describe('getDecisionHistory', () => {
    it('should return decision history', () => {
      const mockHistory: DecisionHistory[] = [
        {
          id: 1,
          decision_id: 1,
          title: 'Old Title',
          context: 'Old context',
          decision: 'Old decision',
          status: 'proposed' as const,
          consequences: 'Old consequences',
          changed_at: '2024-01-01T00:00:00Z',
          change_reason: 'Initial version'
        }
      ];

      service.getDecisionHistory(1).subscribe(history => {
        expect(history).toEqual(mockHistory);
        expect(history.length).toBe(1);
      });

      const req = httpMock.expectOne('/api/decisions/1/history');
      expect(req.request.method).toBe('GET');
      req.flush(mockHistory);
    });
  });
});
