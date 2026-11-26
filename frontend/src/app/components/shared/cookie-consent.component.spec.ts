import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { BehaviorSubject } from 'rxjs';
import { AnalyticsConsentService } from '../../services/analytics-consent.service';
import { CookieConsentComponent, CookieConsentStatus, PRIVACY_POLICY_URL } from './cookie-consent.component';

/** The usage statistics notice: what it says is what the browser does. */
describe('CookieConsentComponent', () => {
  let fixture: ComponentFixture<CookieConsentComponent>;
  let choice$: BehaviorSubject<CookieConsentStatus>;
  let consent: jasmine.SpyObj<AnalyticsConsentService> & { choice$: BehaviorSubject<CookieConsentStatus>; choice: CookieConsentStatus };

  async function open(stored: CookieConsentStatus): Promise<void> {
    choice$ = new BehaviorSubject<CookieConsentStatus>(stored);
    consent = Object.assign(jasmine.createSpyObj<AnalyticsConsentService>('AnalyticsConsentService', ['answerNotice']), {
      choice$,
      get choice() { return choice$.value; }
    }) as any;
    consent.answerNotice.and.callFake((answer: 'accepted' | 'rejected') => choice$.next(answer));
    await TestBed.configureTestingModule({
      imports: [CookieConsentComponent, NoopAnimationsModule],
      providers: [{ provide: AnalyticsConsentService, useValue: consent }]
    }).compileComponents();
    fixture = TestBed.createComponent(CookieConsentComponent);
    fixture.detectChanges();
  }

  function element(testId: string): HTMLElement | null {
    return fixture.nativeElement.querySelector(`[data-testid="${testId}"]`);
  }

  function text(testId: string): string {
    return (element(testId)?.textContent || '').replace(/\s+/g, ' ').trim();
  }

  it('says exactly what is counted and that nothing is sent without an answer', async () => {
    await open(null);

    expect(text('analytics-notice-title')).toBe('Usage statistics');
    expect(text('analytics-notice-text')).toBe(
      'May we count how you use the app? If you accept, this browser tells our statistics service which pages ' +
      'you open and that you clicked something, never the text you clicked or typed, and keeps a random ' +
      'identifier in its storage for this. Nothing is sent unless you accept. You can change your answer at ' +
      'any time under Profile, Privacy & Data. Privacy policy'
    );
  });

  it('no longer makes the claims that were not true', async () => {
    await open(null);

    const all = fixture.nativeElement.textContent as string;
    expect(all).not.toContain('Cookie Notice');
    expect(all).not.toContain('analytics cookies');
    expect(all).not.toContain('No personal data is shared with third parties');
  });

  it('links to the privacy policy in a new tab', async () => {
    await open(null);

    const link = element('analytics-notice-privacy') as HTMLAnchorElement;
    expect(link.textContent!.trim()).toBe('Privacy policy');
    expect(link.getAttribute('href')).toBe('https://decisionrecords.org/privacy');
    expect(PRIVACY_POLICY_URL).toBe('https://decisionrecords.org/privacy');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
  });

  it('accepting answers the notice and hides it', async () => {
    await open(null);
    const emitted: CookieConsentStatus[] = [];
    fixture.componentInstance.consentChanged.subscribe(value => emitted.push(value));

    (element('analytics-notice-accept') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(consent.answerNotice).toHaveBeenCalledOnceWith('accepted');
    expect(emitted).toEqual(['accepted']);
    expect(element('analytics-notice-title')).toBeNull();
  });

  it('rejecting answers the notice and hides it', async () => {
    await open(null);

    (element('analytics-notice-reject') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(consent.answerNotice).toHaveBeenCalledOnceWith('rejected');
    expect(element('analytics-notice-title')).toBeNull();
  });

  it('is not shown once answered', async () => {
    await open('rejected');

    expect(element('analytics-notice-title')).toBeNull();
  });
});
