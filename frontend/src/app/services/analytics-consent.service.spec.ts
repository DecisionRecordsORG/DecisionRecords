import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { BehaviorSubject } from 'rxjs';
import { ANALYTICS_CHOICE_KEY, AnalyticsConsentService } from './analytics-consent.service';
import { AuthService, CurrentUser } from './auth.service';
import { FeatureFlagsService } from './feature-flags.service';
import { PostHogService } from './posthog.service';

/**
 * When may this browser send analytics? Only when the notice was accepted
 * here and, for a signed-in person, the "Analytics" switch on their profile
 * is on. Either one off: nothing is sent.
 */
describe('AnalyticsConsentService', () => {
  let service: AnalyticsConsentService;
  let http: HttpTestingController;
  let postHog: jasmine.SpyObj<PostHogService>;
  let loading: BehaviorSubject<boolean>;
  let current: BehaviorSubject<CurrentUser | null>;
  let flags: BehaviorSubject<unknown>;
  let analyticsEnabled: boolean;

  const MEMBER = { user: { id: 7, email: 'pat@acme.test' }, isMaster: false } as unknown as CurrentUser;
  const OTHER = { user: { id: 8, email: 'sam@acme.test' }, isMaster: false } as unknown as CurrentUser;
  const MASTER = { user: { id: 1, username: 'root' }, isMaster: true } as unknown as CurrentUser;

  function create(choice: 'accepted' | 'rejected' | null): void {
    localStorage.removeItem(ANALYTICS_CHOICE_KEY);
    if (choice) {
      localStorage.setItem(ANALYTICS_CHOICE_KEY, choice);
    }
    loading = new BehaviorSubject<boolean>(true);
    current = new BehaviorSubject<CurrentUser | null>(null);
    flags = new BehaviorSubject<unknown>({});
    analyticsEnabled = true;
    postHog = jasmine.createSpyObj<PostHogService>('PostHogService', ['enable', 'disable']);
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { isLoading$: loading, currentUser$: current } },
        { provide: FeatureFlagsService, useValue: { flags$: flags, get analyticsEnabled() { return analyticsEnabled; } } },
        { provide: PostHogService, useValue: postHog }
      ]
    });
    service = TestBed.inject(AnalyticsConsentService);
    http = TestBed.inject(HttpTestingController);
    service.start();
  }

  function signedIn(who: CurrentUser | null): void {
    current.next(who);
    loading.next(false);
  }

  function answerConsents(analytics: { granted: boolean; updated_at?: string }): void {
    http.expectOne({ method: 'GET', url: '/api/user/consents' }).flush({ analytics });
  }

  afterEach(() => {
    http.verify();
    localStorage.removeItem(ANALYTICS_CHOICE_KEY);
  });

  it('starts nothing before it knows who is signed in', () => {
    create('accepted');

    expect(postHog.enable).not.toHaveBeenCalled();
    expect(service.allowed).toBeFalse();
  });

  it('sends for a signed-out visitor who accepted the notice', () => {
    create('accepted');
    signedIn(null);

    expect(postHog.enable).toHaveBeenCalled();
    expect(service.allowed).toBeTrue();
  });

  it('sends nothing for a visitor who rejected or has not answered', () => {
    create('rejected');
    signedIn(null);
    expect(postHog.enable).not.toHaveBeenCalled();

    TestBed.resetTestingModule();
    create(null);
    signedIn(null);
    expect(postHog.enable).not.toHaveBeenCalled();
  });

  it('sends nothing in an edition without analytics, whatever was answered', () => {
    create('accepted');
    analyticsEnabled = false;
    signedIn(null);

    expect(postHog.enable).not.toHaveBeenCalled();
  });

  it('waits for the account before sending for a signed-in person', () => {
    create('accepted');
    signedIn(MEMBER);

    expect(postHog.enable).not.toHaveBeenCalled();

    answerConsents({ granted: true, updated_at: '2026-11-26T10:00:00' });

    expect(postHog.enable).toHaveBeenCalled();
  });

  it('sends nothing when the account switch is off, and this browser follows', () => {
    create('accepted');
    signedIn(MEMBER);

    answerConsents({ granted: false, updated_at: '2026-11-26T10:00:00' });

    expect(postHog.enable).not.toHaveBeenCalled();
    expect(postHog.disable).toHaveBeenCalled();
    expect(localStorage.getItem(ANALYTICS_CHOICE_KEY)).toBe('rejected');
    expect(service.choice).toBe('rejected');
  });

  it('sends nothing when the account switch is on but this browser rejected the notice', () => {
    create('rejected');
    signedIn(MEMBER);

    answerConsents({ granted: true, updated_at: '2026-11-26T10:00:00' });

    expect(postHog.enable).not.toHaveBeenCalled();
  });

  it('stores this browser\'s answer on an account that has no choice yet', () => {
    create('accepted');
    signedIn(MEMBER);

    answerConsents({ granted: false });

    const saved = http.expectOne({ method: 'POST', url: '/api/user/consents' });
    expect(saved.request.body).toEqual({ consent_type: 'analytics', granted: true });
    saved.flush({});
    expect(postHog.enable).toHaveBeenCalled();
  });

  it('stores a rejection on an account that has no choice yet', () => {
    create('rejected');
    signedIn(MEMBER);

    answerConsents({ granted: false });

    const saved = http.expectOne({ method: 'POST', url: '/api/user/consents' });
    expect(saved.request.body).toEqual({ consent_type: 'analytics', granted: false });
    saved.flush({});
    expect(postHog.enable).not.toHaveBeenCalled();
  });

  it('stores nothing on the account while the notice is unanswered', () => {
    create(null);
    signedIn(MEMBER);

    answerConsents({ granted: false });

    http.expectNone({ method: 'POST', url: '/api/user/consents' });
    expect(postHog.enable).not.toHaveBeenCalled();
  });

  it('answering the notice while signed in sets the account switch too', () => {
    create(null);
    signedIn(MEMBER);
    answerConsents({ granted: false });

    service.answerNotice('accepted');

    const saved = http.expectOne({ method: 'POST', url: '/api/user/consents' });
    expect(saved.request.body).toEqual({ consent_type: 'analytics', granted: true });
    saved.flush({});
    expect(postHog.enable).toHaveBeenCalled();
    expect(localStorage.getItem(ANALYTICS_CHOICE_KEY)).toBe('accepted');
  });

  it('rejecting the notice while signed in switches the account off and stops at once', () => {
    create('accepted');
    signedIn(MEMBER);
    answerConsents({ granted: true, updated_at: '2026-11-26T10:00:00' });
    postHog.disable.calls.reset();

    service.answerNotice('rejected');

    expect(postHog.disable).toHaveBeenCalled();
    const saved = http.expectOne({ method: 'POST', url: '/api/user/consents' });
    expect(saved.request.body).toEqual({ consent_type: 'analytics', granted: false });
    saved.flush({});
  });

  it('answering the notice while signed out touches no account', () => {
    create(null);
    signedIn(null);

    service.answerNotice('accepted');

    http.expectNone('/api/user/consents');
    expect(postHog.enable).toHaveBeenCalled();
  });

  it('switching the profile switch off stops this browser at once', () => {
    create('accepted');
    signedIn(MEMBER);
    answerConsents({ granted: true, updated_at: '2026-11-26T10:00:00' });
    postHog.disable.calls.reset();

    service.accountSwitchChanged(false);

    expect(postHog.disable).toHaveBeenCalled();
    expect(service.allowed).toBeFalse();
    expect(localStorage.getItem(ANALYTICS_CHOICE_KEY)).toBe('rejected');
  });

  it('switching the profile switch on starts this browser and answers the notice', () => {
    create(null);
    signedIn(MEMBER);
    answerConsents({ granted: false });

    service.accountSwitchChanged(true);

    expect(postHog.enable).toHaveBeenCalled();
    expect(service.choice).toBe('accepted');
  });

  it('stays off when the account cannot be read', () => {
    create('accepted');
    signedIn(MEMBER);

    http.expectOne('/api/user/consents').flush('down', { status: 500, statusText: 'Server Error' });

    expect(postHog.enable).not.toHaveBeenCalled();
  });

  it('stays off when an acceptance could not be saved to the account', () => {
    create('accepted');
    signedIn(MEMBER);
    answerConsents({ granted: false });

    http.expectOne({ method: 'POST', url: '/api/user/consents' })
      .flush('down', { status: 500, statusText: 'Server Error' });

    expect(service.allowed).toBeFalse();
    expect(postHog.disable).toHaveBeenCalled();
  });

  it('asks again for the next person who signs in on this browser', () => {
    create('accepted');
    signedIn(MEMBER);
    answerConsents({ granted: true, updated_at: '2026-11-26T10:00:00' });
    postHog.enable.calls.reset();

    current.next(OTHER);
    expect(service.allowed).toBeFalse();
    answerConsents({ granted: false, updated_at: '2026-11-26T10:00:00' });

    expect(postHog.enable).not.toHaveBeenCalled();
    expect(service.allowed).toBeFalse();
  });

  it('treats a super admin like a signed-out visitor: the notice alone decides', () => {
    create('accepted');
    signedIn(MASTER);

    http.expectNone('/api/user/consents');
    expect(postHog.enable).toHaveBeenCalled();
  });

  it('asks the server nothing in an edition without analytics', () => {
    create('accepted');
    analyticsEnabled = false;
    signedIn(MEMBER);
    flags.next({});

    http.expectNone('/api/user/consents');
    expect(postHog.enable).not.toHaveBeenCalled();
  });

  it('asks for the account once the flags say the edition has analytics', () => {
    create('accepted');
    analyticsEnabled = false;
    signedIn(MEMBER);
    http.expectNone('/api/user/consents');

    analyticsEnabled = true;
    flags.next({});
    flags.next({});

    answerConsents({ granted: true, updated_at: '2026-11-26T10:00:00' });
    expect(postHog.enable).toHaveBeenCalled();
  });

  it('applies the edition\'s flags when they arrive after sign-in is known', () => {
    create('accepted');
    analyticsEnabled = false;
    signedIn(null);
    expect(postHog.enable).not.toHaveBeenCalled();

    analyticsEnabled = true;
    flags.next({});

    expect(postHog.enable).toHaveBeenCalled();
  });
});
