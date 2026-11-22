import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { TenantLoginComponent } from './tenant-login.component';
import { FeatureFlagsService } from '../../services/feature-flags.service';

/**
 * Every step of the sign-in page carries the "Can't sign in? Get help" link.
 */
describe('TenantLoginComponent help link', () => {
  let component: TenantLoginComponent;
  let fixture: ComponentFixture<TenantLoginComponent>;
  let httpMock: HttpTestingController;
  let flags: { marketing_pages: boolean };

  async function create(query: Record<string, string> = {}): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [TenantLoginComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: FeatureFlagsService, useValue: { get flags() { return flags; } } },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({ tenant: 'acme.test' }),
              queryParamMap: convertToParamMap(query)
            }
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(TenantLoginComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    httpMock.match(() => true).forEach(req => req.flush({}, { status: 404, statusText: 'Not Found' }));
    fixture.detectChanges();
  }

  beforeEach(() => {
    flags = { marketing_pages: true };
  });

  afterEach(() => {
    httpMock.match(() => true);
  });

  function links(): HTMLAnchorElement[] {
    fixture.detectChanges();
    return Array.from(fixture.nativeElement.querySelectorAll('[data-testid="support-link"]'));
  }

  function href(): string | null {
    const all = links();
    expect(all.length).toBe(1);
    return all[0].getAttribute('href');
  }

  it('shows the link with the organisation before an email address is typed', async () => {
    await create();

    const link = links()[0];
    expect(link.textContent).toBe("Can't sign in? Get help");
    expect(link.getAttribute('target')).toBe('_blank');
    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&org=acme.test');
  });

  it('adds the email address once a complete one is typed, and not while it is incomplete', async () => {
    await create();

    component.emailForm.setValue({ email: 'ada@' });
    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&org=acme.test');

    component.emailForm.setValue({ email: 'ada@acme.test' });
    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&email=ada%40acme.test&org=acme.test');
  });

  it('keeps the link and the email address on the passkey and password step', async () => {
    await create();
    component.currentEmail = 'ada@acme.test';
    component.userStatus = { exists: true, has_passkey: true, has_password: true };
    component.currentView = 'login';

    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&email=ada%40acme.test&org=acme.test');

    component.showPasswordLogin = true;
    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&email=ada%40acme.test&org=acme.test');
  });

  it('keeps the link on the request access and request sent steps', async () => {
    await create();
    component.currentEmail = 'ada@acme.test';

    for (const view of ['request-access', 'request-sent', 'access-pending'] as const) {
      component.currentView = view;
      expect(href()).toBe('https://decisionrecords.org/support?topic=signin&email=ada%40acme.test&org=acme.test');
    }
  });

  it('asks about a missing email on the steps that send one', async () => {
    await create();
    component.currentEmail = 'ada@acme.test';

    component.currentView = 'auto-approved';
    expect(href()).toBe('https://decisionrecords.org/support?topic=email&email=ada%40acme.test&org=acme.test');

    component.showRecovery();
    expect(href()).toBe('https://decisionrecords.org/support?topic=email&email=ada%40acme.test&org=acme.test');

    component.showResendVerification();
    component.resendForm.setValue({ email: 'grace@acme.test' });
    expect(href()).toBe('https://decisionrecords.org/support?topic=email&email=grace%40acme.test&org=acme.test');
  });

  it('shows the link next to the user limit message after a provider sign-in', async () => {
    await create({ error: 'user_limit' });

    expect(fixture.nativeElement.querySelector('.error-message').textContent).toContain('reached its user limit');
    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&org=acme.test');
  });

  it('shows the link next to a failed provider sign-in', async () => {
    await create({ error: 'google_auth_error' });

    expect(fixture.nativeElement.querySelector('.error-message').textContent).toContain('Google authentication failed');
    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&org=acme.test');
  });

  it('shows no link on a self-hosted installation with no support page configured', async () => {
    flags = { marketing_pages: false };
    await create();

    expect(links().length).toBe(0);
  });
});
