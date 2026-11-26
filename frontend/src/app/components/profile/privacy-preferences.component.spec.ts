import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { AnalyticsConsentService } from '../../services/analytics-consent.service';
import { FeatureFlagsService } from '../../services/feature-flags.service';
import { PrivacyPreferencesComponent } from './privacy-preferences.component';

/** The privacy switches on the profile page: each one does what it says. */
describe('PrivacyPreferencesComponent', () => {
  let fixture: ComponentFixture<PrivacyPreferencesComponent>;
  let http: HttpTestingController;
  let analyticsConsent: jasmine.SpyObj<AnalyticsConsentService>;

  async function open(
    edition: { analytics: boolean; ai: boolean },
    consents: Record<string, { granted: boolean }>
  ): Promise<void> {
    analyticsConsent = jasmine.createSpyObj<AnalyticsConsentService>('AnalyticsConsentService', ['accountSwitchChanged']);
    await TestBed.configureTestingModule({
      imports: [PrivacyPreferencesComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AnalyticsConsentService, useValue: analyticsConsent },
        { provide: FeatureFlagsService, useValue: { analyticsEnabled: edition.analytics, aiEnabled: edition.ai } }
      ]
    }).compileComponents();
    fixture = TestBed.createComponent(PrivacyPreferencesComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne({ method: 'GET', url: '/api/user/consents' }).flush(consents);
    fixture.detectChanges();
  }

  function element(testId: string): HTMLElement | null {
    return fixture.nativeElement.querySelector(`[data-testid="${testId}"]`);
  }

  function isOn(testId: string): boolean {
    return element(testId)!.querySelector('button')!.getAttribute('aria-checked') === 'true';
  }

  function flip(testId: string): void {
    element(testId)!.querySelector('button')!.click();
    fixture.detectChanges();
  }

  const ENTERPRISE = { analytics: true, ai: true };
  const COMMUNITY = { analytics: false, ai: false };
  const DEFAULTS = {
    analytics: { granted: false }, ai_processing: { granted: false }, email_notifications: { granted: true }
  };

  afterEach(() => http.verify());

  it('shows the three switches as the account has them', async () => {
    await open(ENTERPRISE, DEFAULTS);

    expect(isOn('preference-analytics')).toBeFalse();
    expect(isOn('preference-ai')).toBeFalse();
    expect(isOn('preference-email')).toBeTrue();
  });

  it('says what each switch really does', async () => {
    await open(ENTERPRISE, DEFAULTS);

    const analytics = element('preference-analytics-hint')!.textContent!.replace(/\s+/g, ' ').trim();
    expect(analytics).toContain('When this is off, this browser sends nothing to our analytics service');
    expect(analytics).toContain('are not linked to you');
    const email = element('preference-email-hint')!.textContent!.replace(/\s+/g, ' ').trim();
    expect(email).toContain('the notifications you chose above, and a message when you are made the owner');
    expect(email).toContain('Emails about your account, such as sign-in and set-up links, are always sent.');
  });

  it('hides the switches for features the installation does not have', async () => {
    await open(COMMUNITY, DEFAULTS);

    expect(element('preference-analytics')).toBeNull();
    expect(element('preference-ai')).toBeNull();
    expect(element('preference-email')).not.toBeNull();
  });

  it('treats a missing email answer as on, and a stored refusal as off', async () => {
    await open(COMMUNITY, {});
    expect(isOn('preference-email')).toBeTrue();

    TestBed.resetTestingModule();
    await open(COMMUNITY, { email_notifications: { granted: false } });
    expect(isOn('preference-email')).toBeFalse();
  });

  it('switching analytics off stops this browser before the server has answered', async () => {
    await open(ENTERPRISE, { ...DEFAULTS, analytics: { granted: true } });

    flip('preference-analytics');

    expect(analyticsConsent.accountSwitchChanged).toHaveBeenCalledOnceWith(false);
    const request = http.expectOne({ method: 'POST', url: '/api/user/consents' });
    expect(request.request.body).toEqual({ consent_type: 'analytics', granted: false });
    request.flush({});
    expect(isOn('preference-analytics')).toBeFalse();
  });

  it('switching analytics on starts this browser only once the account has it', async () => {
    await open(ENTERPRISE, DEFAULTS);

    flip('preference-analytics');

    expect(analyticsConsent.accountSwitchChanged).not.toHaveBeenCalled();
    http.expectOne({ method: 'POST', url: '/api/user/consents' }).flush({});
    expect(analyticsConsent.accountSwitchChanged).toHaveBeenCalledOnceWith(true);
  });

  it('a switch-on that could not be saved goes back to off and starts nothing', async () => {
    await open(ENTERPRISE, DEFAULTS);

    flip('preference-analytics');
    http.expectOne('/api/user/consents').flush('down', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();

    expect(analyticsConsent.accountSwitchChanged).not.toHaveBeenCalled();
    expect(fixture.componentInstance.consents.analytics).toBeFalse();
  });

  it('switching email notifications off saves that and touches nothing else', async () => {
    await open(ENTERPRISE, DEFAULTS);

    flip('preference-email');

    const request = http.expectOne({ method: 'POST', url: '/api/user/consents' });
    expect(request.request.body).toEqual({ consent_type: 'email_notifications', granted: false });
    request.flush({});
    expect(analyticsConsent.accountSwitchChanged).not.toHaveBeenCalled();
    expect(isOn('preference-email')).toBeFalse();
  });
});
