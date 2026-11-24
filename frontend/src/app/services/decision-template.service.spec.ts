import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { DECISION_FORM_COPY } from '../components/shared/decision-form-copy';
import { DecisionTemplateService, decisionTypeOptions, formCopyFor } from './decision-template.service';
import { GENERAL_TEMPLATE, GOVERNANCE_TEMPLATE, TEMPLATE_CATALOG, tenantTemplate } from './decision-template.testing';

describe('decision template helpers', () => {
  it('falls back to the General form copy while no template has loaded', () => {
    expect(formCopyFor(null)).toBe(DECISION_FORM_COPY);
    expect(formCopyFor(undefined)).toBe(DECISION_FORM_COPY);
  });

  it('gives the General template exactly the copy the form had before templates', () => {
    expect(formCopyFor(GENERAL_TEMPLATE)).toEqual(DECISION_FORM_COPY);
  });

  it('takes headings and prompts from the template and keeps the Title label', () => {
    const copy = formCopyFor(GOVERNANCE_TEMPLATE);

    expect(copy.title.label).toBe('Title');
    expect(copy.title.placeholder).toBe(GOVERNANCE_TEMPLATE.title.placeholder);
    expect(copy.context.label).toBe('Matter and background');
    expect(copy.decision.label).toBe('Decision and reasons');
    expect(copy.consequences).toEqual(GOVERNANCE_TEMPLATE.sections.consequences);
  });

  it('offers the template types, plus a stored type the template does not list', () => {
    expect(decisionTypeOptions(GOVERNANCE_TEMPLATE, null)).toEqual(['Appointment', 'Service change']);
    expect(decisionTypeOptions(GOVERNANCE_TEMPLATE, 'Appointment')).toEqual(['Appointment', 'Service change']);
    expect(decisionTypeOptions(GOVERNANCE_TEMPLATE, 'Architecture')).toEqual(['Appointment', 'Service change', 'Architecture']);
    expect(decisionTypeOptions(null, 'Architecture')).toEqual(['Architecture']);
    expect(decisionTypeOptions(null, undefined)).toEqual([]);
  });

  it('does not change the template it reads from', () => {
    decisionTypeOptions(GOVERNANCE_TEMPLATE, 'Architecture');
    expect(GOVERNANCE_TEMPLATE.decision_types).toEqual(['Appointment', 'Service change']);
  });
});

describe('DecisionTemplateService', () => {
  let service: DecisionTemplateService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(DecisionTemplateService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('fetches the static catalogue once', () => {
    let first: unknown;
    let second: unknown;
    service.getCatalog().subscribe(catalog => (first = catalog));
    service.getCatalog().subscribe(catalog => (second = catalog));

    const request = httpMock.expectOne('/api/decision-templates/catalog');
    expect(request.request.method).toBe('GET');
    request.flush(TEMPLATE_CATALOG);

    expect(first).toEqual(TEMPLATE_CATALOG);
    expect(second).toEqual(TEMPLATE_CATALOG);
  });

  it('reads the tenant template fresh every time', () => {
    service.getTenantTemplate().subscribe();
    service.getTenantTemplate().subscribe();

    const requests = httpMock.match('/api/tenant/decision-template');
    expect(requests.length).toBe(2);
    requests.forEach(request => request.flush(tenantTemplate()));
  });

  it('tries the tenant template again before giving up, so a hiccup does not leave the General headings', fakeAsync(() => {
    let answer: unknown;
    let failed = false;
    service.getTenantTemplate().subscribe({ next: value => (answer = value), error: () => (failed = true) });

    httpMock.expectOne('/api/tenant/decision-template').flush('down', { status: 503, statusText: 'Unavailable' });
    tick(400);
    httpMock.expectOne('/api/tenant/decision-template').flush(tenantTemplate());

    expect(answer).toEqual(tenantTemplate());
    expect(failed).toBeFalse();
  }));

  it('gives up after three failed attempts', fakeAsync(() => {
    let failed = false;
    service.getTenantTemplate().subscribe({ error: () => (failed = true) });

    for (let attempt = 0; attempt < 3; attempt++) {
      httpMock.expectOne('/api/tenant/decision-template').flush('down', { status: 503, statusText: 'Unavailable' });
      tick(400);
    }

    expect(failed).toBeTrue();
  }));

  it('saves the template choice with PUT', () => {
    service.updateTenantTemplate({ template_id: 'governance', industry: 'Q', enable_suggested_packs: true }).subscribe();

    const request = httpMock.expectOne('/api/tenant/decision-template');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ template_id: 'governance', industry: 'Q', enable_suggested_packs: true });
    request.flush(tenantTemplate());
  });

  it('dismisses the notice with POST', () => {
    service.dismissNotice().subscribe();

    const request = httpMock.expectOne('/api/tenant/decision-template/dismiss-notice');
    expect(request.request.method).toBe('POST');
    request.flush(tenantTemplate());
  });

  it('sets and clears types in bulk', () => {
    service.bulkSetDecisionType([1, 2], 'Policy').subscribe();
    service.bulkSetDecisionType([3], null).subscribe();

    const requests = httpMock.match('/api/tenant/decisions/bulk-type');
    expect(requests.map(request => request.request.method)).toEqual(['POST', 'POST']);
    expect(requests[0].request.body).toEqual({ decision_ids: [1, 2], decision_type: 'Policy' });
    expect(requests[1].request.body).toEqual({ decision_ids: [3], decision_type: null });
    requests.forEach(request => request.flush({ message: 'ok', decision_type: null, updated: 0, unchanged: 0, skipped_ids: [] }));
  });
});
