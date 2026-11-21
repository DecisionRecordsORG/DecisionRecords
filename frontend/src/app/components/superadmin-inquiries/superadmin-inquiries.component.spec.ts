import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { of } from 'rxjs';
import {
  Inquiry,
  InterestSummary,
  SuperadminInquiriesComponent,
  answerOrigin,
  inquirySourceLabel,
  messagePreview
} from './superadmin-inquiries.component';

function inquiry(overrides: Partial<Inquiry> = {}): Inquiry {
  return {
    id: 1,
    source: 'contact',
    name: 'Ada Lovelace',
    email: 'ada@example.org',
    organisation: null,
    area_of_interest: null,
    message: 'Hello, I would like to know more.',
    team_focus: 'Hiring',
    team_size: null,
    team_size_label: null,
    contact_consent: null,
    user_id: null,
    tenant_domain: null,
    created_at: '2026-11-21T10:00:00',
    email_sent: true,
    handled: false,
    handled_at: null,
    handled_by: null,
    redacted: false,
    redacted_at: null,
    ...overrides
  };
}

const SUMMARY: InterestSummary = {
  tenants: {
    total: 3,
    with_team_focus: 1,
    by_team_size: [
      { code: '1-5', label: '1 to 5 people', count: 2 },
      { code: null, label: 'Not answered', count: 1 }
    ]
  },
  inquiries: {
    total: 2,
    unhandled: 1,
    not_emailed: 1,
    by_source: [
      { source: 'contact', count: 2 },
      { source: 'sponsorship', count: 0 },
      { source: 'feedback', count: 0 }
    ],
    by_team_size: [{ code: null, label: 'Not answered', count: 2 }]
  },
  team_focus_answers: [{ text: 'Hiring', tenants: 1, inquiries: 2 }]
};

describe('inquiry helpers', () => {
  it('names each form the way the product does', () => {
    expect(inquirySourceLabel('contact')).toBe('Contact form');
    expect(inquirySourceLabel('sponsorship')).toBe('Get in touch');
    expect(inquirySourceLabel('feedback')).toBe('Feedback');
    expect(inquirySourceLabel('something-new')).toBe('something-new');
  });

  it('shows a short message whole', () => {
    expect(messagePreview('Hello there')).toBe('Hello there');
    expect(messagePreview(null)).toBe('');
    expect(messagePreview('  spaced \n\n out  ')).toBe('spaced out');
  });

  it('cuts a long message at a word and marks the cut', () => {
    const preview = messagePreview('word '.repeat(60), 30);

    expect(preview.length).toBeLessThanOrEqual(33);
    expect(preview.endsWith('...')).toBeTrue();
    expect(preview).not.toContain('wor...');
  });

  it('cuts a long message without spaces at the limit', () => {
    expect(messagePreview('x'.repeat(200), 20)).toBe('x'.repeat(20) + '...');
  });

  it('says where a team focus answer came from', () => {
    expect(answerOrigin({ tenants: 1, inquiries: 0 })).toBe('1 tenant');
    expect(answerOrigin({ tenants: 2, inquiries: 1 })).toBe('2 tenants, 1 inquiry');
    expect(answerOrigin({ tenants: 0, inquiries: 3 })).toBe('3 inquiries');
  });
});

describe('SuperadminInquiriesComponent', () => {
  let fixture: ComponentFixture<SuperadminInquiriesComponent>;
  let component: SuperadminInquiriesComponent;
  let httpMock: HttpTestingController;

  function flushInitialLoad(items: Inquiry[], unhandled = items.filter(item => !item.handled).length): void {
    httpMock.expectOne('/api/superadmin/inquiries?limit=50&offset=0').flush({
      total: items.length, limit: 50, offset: 0, unhandled_total: unhandled, items
    });
    httpMock.expectOne('/api/superadmin/inquiries/summary').flush(SUMMARY);
    fixture.detectChanges();
  }

  function text(testId: string): string {
    const element = fixture.nativeElement.querySelector(`[data-testid="${testId}"]`);
    return element ? (element.textContent as string).replace(/\s+/g, ' ').trim() : '';
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SuperadminInquiriesComponent, NoopAnimationsModule],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])]
    }).compileComponents();

    fixture = TestBed.createComponent(SuperadminInquiriesComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('lists inquiries with the form, sender, team focus and message', () => {
    flushInitialLoad([inquiry()]);

    const row = text('inquiry-row');
    expect(row).toContain('Contact form');
    expect(row).toContain('Ada Lovelace');
    expect(row).toContain('ada@example.org');
    expect(row).toContain('Hiring');
    expect(row).toContain('Hello, I would like to know more.');
    expect(row).toContain('Not handled');
  });

  it('marks a message that was never emailed and explains it above the table', () => {
    flushInitialLoad([inquiry({ email_sent: false })]);

    expect(text('inquiry-not-emailed-chip')).toContain('Not emailed');
    expect(text('inquiries-not-emailed-banner')).toContain('1 message was never emailed');
  });

  it('does not mark a message that was emailed', () => {
    flushInitialLoad([inquiry({ email_sent: true })]);

    expect(fixture.nativeElement.querySelector('[data-testid="inquiry-not-emailed-chip"]')).toBeNull();
  });

  it('shows the count of inquiries that are not handled', () => {
    flushInitialLoad([inquiry(), inquiry({ id: 2, handled: true })], 1);

    expect(text('inquiries-unhandled-count')).toBe('1 not handled');
  });

  it('says so when there are no inquiries', () => {
    flushInitialLoad([]);

    expect(text('inquiries-empty')).toContain('No inquiries yet');
  });

  it('replaces the sender with a note when the personal details were removed', () => {
    flushInitialLoad([inquiry({ name: null, email: null, message: null, redacted: true })]);

    expect(text('inquiry-row')).toContain('Personal details removed');
  });

  it('shows the interest summary', () => {
    flushInitialLoad([inquiry()]);

    // Label and count sit in adjacent elements, so there is no space between them
    expect(text('interest-tenants-by-size')).toContain('1 to 5 people2');
    expect(text('interest-tenants-by-size')).toContain('Not answered1');
    expect(text('interest-inquiries-by-source')).toContain('Get in touch0');
    expect(text('interest-team-focus')).toContain('Hiring');
    expect(text('interest-team-focus')).toContain('1 tenant, 2 inquiries');
  });

  it('sends the chosen filters and goes back to the first page', () => {
    flushInitialLoad([inquiry()]);
    component.page = 3;
    component.filter = { source: 'feedback', handled: 'false' };

    component.applyFilters();

    httpMock.expectOne('/api/superadmin/inquiries?limit=50&offset=0&source=feedback&handled=false').flush({
      total: 0, limit: 50, offset: 0, unhandled_total: 0, items: []
    });
    fixture.detectChanges();
    expect(component.page).toBe(0);
    expect(text('inquiries-empty')).toContain('No inquiries match these filters');
  });

  it('marks an inquiry handled and reloads the list and the summary', () => {
    flushInitialLoad([inquiry()]);

    component.toggleHandled(component.inquiries[0]);

    const request = httpMock.expectOne('/api/superadmin/inquiries/1/handled');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ handled: true });
    request.flush({ message: 'Inquiry marked as handled', inquiry: inquiry({ handled: true }) });
    httpMock.expectOne('/api/superadmin/inquiries?limit=50&offset=0').flush({
      total: 1, limit: 50, offset: 0, unhandled_total: 0, items: [inquiry({ handled: true })]
    });
    httpMock.expectOne('/api/superadmin/inquiries/summary').flush(SUMMARY);
    fixture.detectChanges();

    expect(text('inquiry-handled-chip')).toBe('Handled');
  });

  it('asks before deleting and deletes nothing when the answer is no', () => {
    flushInitialLoad([inquiry()]);
    const dialog = (component as any).dialog as MatDialog;
    const open = spyOn(dialog, 'open').and.returnValue({ afterClosed: () => of(false) } as any);

    component.deleteInquiry(component.inquiries[0]);

    expect(open).toHaveBeenCalled();
    expect(open.calls.mostRecent().args[1]?.data).toEqual(jasmine.objectContaining({
      title: 'Delete inquiry',
      message: 'Delete the message from Ada Lovelace? This cannot be undone.',
      confirmText: 'Delete',
      isDanger: true
    }));
    httpMock.expectNone('/api/superadmin/inquiries/1');
  });

  it('deletes after the confirmation', () => {
    flushInitialLoad([inquiry()]);
    const dialog = (component as any).dialog as MatDialog;
    spyOn(dialog, 'open').and.returnValue({ afterClosed: () => of(true) } as any);

    component.deleteInquiry(component.inquiries[0]);

    const request = httpMock.expectOne('/api/superadmin/inquiries/1');
    expect(request.request.method).toBe('DELETE');
    request.flush({ message: 'Inquiry deleted' });
    httpMock.expectOne('/api/superadmin/inquiries?limit=50&offset=0').flush({
      total: 0, limit: 50, offset: 0, unhandled_total: 0, items: []
    });
    httpMock.expectOne('/api/superadmin/inquiries/summary').flush(SUMMARY);
  });

  it('shows the error when the list cannot be loaded', () => {
    httpMock.expectOne('/api/superadmin/inquiries?limit=50&offset=0')
      .flush({ error: 'Master account access required' }, { status: 403, statusText: 'Forbidden' });
    httpMock.expectOne('/api/superadmin/inquiries/summary')
      .flush({ error: 'Master account access required' }, { status: 403, statusText: 'Forbidden' });
    fixture.detectChanges();

    expect(text('inquiries-error')).toContain('Master account access required');
    expect(text('interest-summary-error')).toContain('The summary could not be loaded.');
  });
});
