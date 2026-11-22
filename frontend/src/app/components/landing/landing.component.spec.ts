import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of } from 'rxjs';
import { LandingComponent, signInErrorMessage } from './landing.component';
import { AuthService } from '../../services/auth.service';
import { FeatureFlagsService } from '../../services/feature-flags.service';

describe('signInErrorMessage', () => {
  it('says nothing when there is no error', () => {
    expect(signInErrorMessage(null)).toBe('');
    expect(signInErrorMessage(undefined)).toBe('');
    expect(signInErrorMessage('')).toBe('');
  });

  it('explains expired and invalid verification links', () => {
    expect(signInErrorMessage('expired_token')).toContain('verification link has expired');
    expect(signInErrorMessage('invalid_token')).toContain('verification link is not valid');
  });

  it('explains refused email addresses', () => {
    expect(signInErrorMessage('public_email')).toContain('work email address');
    expect(signInErrorMessage('disposable_email')).toContain('Disposable email addresses');
  });

  it('has a general message for any other failed sign-in', () => {
    for (const code of ['google_auth_error', 'slack_auth_error', 'microsoft_auth_error', 'invalid_state', 'something_new']) {
      expect(signInErrorMessage(code)).toBe('We could not sign you in. Please try again.');
    }
  });
});

describe('LandingComponent help link', () => {
  let fixture: ComponentFixture<LandingComponent>;
  let httpMock: HttpTestingController;
  let flags: { marketing_pages: boolean };

  async function create(query: Record<string, string>, status: object, tenants: object[] = []): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [LandingComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: AuthService, useValue: { currentUser$: of(null) } },
        { provide: FeatureFlagsService, useValue: { get flags() { return flags; } } },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap(query) } } }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(LandingComponent);
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    httpMock.expectOne('/api/system/status').flush(status);
    httpMock.match('/api/tenants/public').forEach(req => req.flush(tenants));
    fixture.detectChanges();
  }

  const hostedStatus = { is_community: false, has_tenants: true, license_accepted: true };
  const communityStatus = { is_community: true, has_tenants: true, license_accepted: true };

  beforeEach(() => {
    flags = { marketing_pages: true };
  });

  function href(): string | null {
    const link = fixture.nativeElement.querySelector('[data-testid="support-link"]');
    return link ? link.getAttribute('href') : null;
  }

  function error(): string | null {
    const element = fixture.nativeElement.querySelector('[data-testid="sign-in-error"]');
    return element ? element.textContent.trim() : null;
  }

  it('shows the link under the organisation entry on the hosted service', async () => {
    await create({}, hostedStatus);

    expect(error()).toBeNull();
    expect(href()).toBe('https://decisionrecords.org/support?topic=signin');
  });

  it('says why and shows the link when a verification link has expired', async () => {
    await create({ error: 'expired_token' }, hostedStatus);

    expect(error()).toContain('verification link has expired');
    expect(href()).toBe('https://decisionrecords.org/support?topic=signin');
  });

  it('says so and shows the link when a provider sign-in failed', async () => {
    await create({ error: 'google_auth_error', message: 'access_denied' }, hostedStatus);

    expect(error()).toBe('We could not sign you in. Please try again.');
    expect(fixture.nativeElement.textContent).not.toContain('access_denied');
    expect(href()).toBe('https://decisionrecords.org/support?topic=signin');
  });

  it('passes the organisation when the installation has a single known one and a support page', async () => {
    flags = { marketing_pages: false, support_url: 'https://help.example.org' } as any;
    await create({}, communityStatus, [{ id: 1, sso_domain: 'acme.test', company_name: 'Acme' }]);

    expect(href()).toBe('https://help.example.org/?topic=signin&org=acme.test');
  });

  it('shows the error but no link on a self-hosted installation with no support page configured', async () => {
    flags = { marketing_pages: false };
    await create({ error: 'invalid_token' }, communityStatus, [{ id: 1, sso_domain: 'acme.test', company_name: 'Acme' }]);

    expect(error()).toContain('verification link is not valid');
    expect(href()).toBeNull();
  });

  it('shows no link when the page runs without a server', async () => {
    await TestBed.configureTestingModule({
      imports: [LandingComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: AuthService, useValue: { currentUser$: of(null) } },
        { provide: FeatureFlagsService, useValue: { get flags() { return flags; } } },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap({}) } } }
      ]
    }).compileComponents();
    fixture = TestBed.createComponent(LandingComponent);
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    httpMock.expectOne('/api/system/status').flush({}, { status: 404, statusText: 'Not Found' });
    fixture.detectChanges();

    expect(href()).toBeNull();
  });
});
