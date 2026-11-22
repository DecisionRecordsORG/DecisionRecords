import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { TenantLoginComponent } from './tenant-login.component';

describe('TenantLoginComponent access requests', () => {
  let component: TenantLoginComponent;
  let fixture: ComponentFixture<TenantLoginComponent>;
  let httpMock: HttpTestingController;

  const ADMIN_WILL_SHARE_LINK =
    'Your request has been submitted. An administrator of your organization ' +
    'will approve it and give you a link to set up your sign-in.';
  const EMAIL_ON_APPROVAL =
    'Your request has been submitted. When an administrator of your organization approves it, ' +
    'you will receive an email with a link to set up your sign-in. If the email cannot be sent, ' +
    'the administrator will give you the link.';
  const EMAIL_FAILED =
    'Your request was received, but the setup email could not be sent. ' +
    'An administrator of your organization can approve your request and give you ' +
    'a setup link. Please contact them.';

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TenantLoginComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({ tenant: 'acme.test' }),
              queryParamMap: convertToParamMap({})
            }
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(TenantLoginComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);

    // Initial page load: answer whatever the page asks for (auth config, provider status, session).
    fixture.detectChanges();
    httpMock.match(() => true).forEach(req => req.flush({}, { status: 404, statusText: 'Not Found' }));
  });

  afterEach(() => {
    httpMock.match(() => true);
  });

  function submitRequest(response: object): void {
    component.tenant = 'acme.test';
    component.currentView = 'request-access';
    component.requestForm.setValue({
      email: 'newcomer@acme.test',
      first_name: 'New',
      last_name: 'Comer',
      reason: ''
    });

    component.submitAccessRequest();

    const req = httpMock.expectOne('/api/auth/access-request');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      email: 'newcomer@acme.test',
      first_name: 'New',
      last_name: 'Comer',
      reason: '',
      domain: 'acme.test'
    });
    req.flush(response);
    fixture.detectChanges();
  }

  function text(testId: string): string | null {
    const element = fixture.nativeElement.querySelector(`[data-testid="${testId}"]`);
    return element ? element.textContent.trim() : null;
  }

  it('tells the requester an administrator will pass on the setup link when email is not configured', () => {
    submitRequest({ message: ADMIN_WILL_SHARE_LINK, auto_approved: false, email_sent: false });

    expect(component.currentView).toBe('request-sent');
    expect(text('request-sent-message')).toBe(ADMIN_WILL_SHARE_LINK);
    expect(text('request-sent-default')).toBeNull();
  });

  it('tells the requester plainly when the setup email could not be sent', () => {
    submitRequest({ message: EMAIL_FAILED, auto_approved: false, email_sent: false });

    expect(component.currentView).toBe('request-sent');
    expect(text('request-sent-message')).toBe(EMAIL_FAILED);
    expect(fixture.nativeElement.textContent).not.toContain("You'll receive an email");
  });

  it('tells the requester an email will come on approval when the server says so', () => {
    submitRequest({ message: EMAIL_ON_APPROVAL, auto_approved: false, email_sent: false, approval_email: true });

    expect(component.currentView).toBe('request-sent');
    expect(text('request-sent-message')).toBe(EMAIL_ON_APPROVAL);
    expect(text('request-sent-default')).toBeNull();
  });

  it('promises no email for a pending request when the server does not say how the link arrives', () => {
    submitRequest({ message: 'Access request submitted successfully' });

    expect(component.currentView).toBe('request-sent');
    expect(text('request-sent-message')).toBeNull();
    expect(text('request-sent-default')).toContain('Your access request has been submitted');
    expect(text('request-sent-default')).toContain('An administrator will review it.');
    expect(fixture.nativeElement.textContent).not.toContain('receive an email');
  });

  it('shows the check-your-email view when the account was created and the link emailed', () => {
    submitRequest({ auto_approved: true, email: 'newcomer@acme.test', domain: 'acme.test', message: 'Created' });

    expect(component.currentView).toBe('auto-approved');
    expect(fixture.nativeElement.textContent).toContain('Check your email');
  });

  it('never navigates to a setup link taken from the response', () => {
    // A response from an older server could still carry a link; the page must ignore it.
    submitRequest({
      auto_approved: true,
      email: 'newcomer@acme.test',
      domain: 'acme.test',
      setup_url: '/acme.test/setup?token=should-be-ignored'
    });

    expect(component.currentView).toBe('auto-approved');
    expect(fixture.nativeElement.innerHTML).not.toContain('should-be-ignored');
  });

  it('shows the server error when the request is refused', () => {
    component.tenant = 'acme.test';
    component.requestForm.setValue({ email: 'newcomer@acme.test', first_name: 'New', last_name: 'Comer', reason: '' });

    component.submitAccessRequest();
    httpMock.expectOne('/api/auth/access-request').flush(
      { error: 'You already have a pending access request' },
      { status: 400, statusText: 'Bad Request' }
    );

    expect(component.error).toBe('You already have a pending access request');
    expect(component.isLoading).toBeFalse();
  });

  it('does not submit an incomplete form', () => {
    component.requestForm.setValue({ email: 'newcomer@acme.test', first_name: '', last_name: '', reason: '' });

    component.submitAccessRequest();

    httpMock.expectNone('/api/auth/access-request');
  });
});
