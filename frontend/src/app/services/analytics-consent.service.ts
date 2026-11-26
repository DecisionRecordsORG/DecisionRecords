import { Inject, Injectable, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, combineLatest } from 'rxjs';
import { AuthService } from './auth.service';
import { FeatureFlagsService } from './feature-flags.service';
import { PostHogService } from './posthog.service';

export const ANALYTICS_CHOICE_KEY = 'dr_cookie_consent';

export type AnalyticsChoice = 'accepted' | 'rejected' | null;

interface ConsentEntry {
  granted: boolean;
  /** Present only when the person has made a choice that is stored on their account. */
  updated_at?: string;
}

/**
 * The one place that decides whether this browser may send analytics.
 *
 * There are two controls and they say the same thing:
 *
 *  - the notice at the bottom of the page (Accept / Reject), remembered in
 *    this browser;
 *  - the "Analytics" switch on the profile page, remembered on the account.
 *
 * The browser sends analytics only when the notice was accepted in this
 * browser and, for a signed-in person, the switch on their account is on.
 * Either control switched off stops it at once.
 *
 * So that the two never disagree:
 *  - answering the notice while signed in also sets the account switch;
 *  - changing the account switch also sets this browser's answer;
 *  - signing in with an account that has no choice yet stores this
 *    browser's answer on the account;
 *  - signing in with an account whose switch is off turns this browser off.
 *
 * Nothing is started until it is known who is signed in, so a person who
 * switched analytics off on another device never sends a first page view.
 */
@Injectable({
  providedIn: 'root'
})
export class AnalyticsConsentService {
  private choiceSubject = new BehaviorSubject<AnalyticsChoice>(this.readChoice());
  /** This browser's answer to the notice. null: not answered yet. */
  readonly choice$ = this.choiceSubject.asObservable();

  private started = false;
  private authKnown = false;
  private userId: number | null = null;
  /** The account's switch. undefined: not known yet; null: nobody (regular) is signed in. */
  private accountAllows: boolean | null | undefined = undefined;
  /** The account whose switch has been asked for. */
  private askedFor: number | null = null;

  constructor(
    private http: HttpClient,
    private authService: AuthService,
    private featureFlags: FeatureFlagsService,
    private postHog: PostHogService,
    @Inject(PLATFORM_ID) private platformId: object
  ) {}

  get choice(): AnalyticsChoice {
    return this.choiceSubject.value;
  }

  /** Begin following sign-in state. Called once by the app shell. */
  start(): void {
    if (this.started || !isPlatformBrowser(this.platformId)) {
      return;
    }
    this.started = true;

    combineLatest([this.authService.isLoading$, this.authService.currentUser$]).subscribe(([loading, current]) => {
      if (loading) {
        return;
      }
      this.authKnown = true;
      const user = current && !current.isMaster ? (current.user as { id?: number; setup_mode?: boolean } | null) : null;
      const userId = user && !user.setup_mode && typeof user.id === 'number' ? user.id : null;
      if (userId === this.userId && this.accountAllows !== undefined) {
        return;
      }
      this.userId = userId;
      if (userId === null) {
        this.accountAllows = null;
        this.apply();
      } else {
        this.accountAllows = undefined;
        this.askedFor = null;
        this.apply();
        this.loadAccountChoice();
      }
    });

    // The edition's feature flags arrive after start-up
    this.featureFlags.flags$.subscribe(() => {
      this.loadAccountChoice();
      this.apply();
    });
  }

  /** The person answered the notice. */
  answerNotice(choice: 'accepted' | 'rejected'): void {
    this.storeChoice(choice);
    if (this.userId !== null && this.featureFlags.analyticsEnabled) {
      this.accountAllows = choice === 'accepted';
      this.saveAccountChoice(choice === 'accepted');
    }
    this.apply();
  }

  /** The person changed the "Analytics" switch on their profile (already saved by the caller). */
  accountSwitchChanged(granted: boolean): void {
    this.accountAllows = granted;
    this.storeChoice(granted ? 'accepted' : 'rejected');
    this.apply();
  }

  /** Whether this browser may send analytics right now. */
  get allowed(): boolean {
    if (!this.featureFlags.analyticsEnabled || !this.authKnown) {
      return false;
    }
    if (this.choice !== 'accepted') {
      return false;
    }
    if (this.userId === null) {
      return this.accountAllows === null;
    }
    return this.accountAllows === true;
  }

  private apply(): void {
    if (this.allowed) {
      this.postHog.enable();
    } else {
      this.postHog.disable();
    }
  }

  /**
   * Ask for the signed-in person's switch, once per person, and only in an
   * edition that has analytics: elsewhere there is nothing to decide.
   */
  private loadAccountChoice(): void {
    const userId = this.userId;
    if (userId === null || this.askedFor === userId || !this.featureFlags.analyticsEnabled) {
      return;
    }
    this.askedFor = userId;
    this.http.get<Record<string, ConsentEntry>>('/api/user/consents').subscribe({
      next: (response) => {
        if (this.userId !== userId) {
          return;
        }
        const entry = response?.['analytics'];
        const stored = !!entry && entry.updated_at !== undefined;
        if (stored) {
          this.accountAllows = entry.granted === true;
          if (!this.accountAllows && this.choice === 'accepted') {
            // Switched off on the account (perhaps on another device): this
            // browser follows
            this.storeChoice('rejected');
          }
        } else if (this.choice !== null) {
          // No choice on the account yet: the answer given in this browser
          // becomes the account's choice
          this.accountAllows = this.choice === 'accepted';
          this.saveAccountChoice(this.accountAllows);
        } else {
          this.accountAllows = false;
        }
        this.apply();
      },
      error: () => {
        // Not knowing counts as "off"
        if (this.userId === userId) {
          this.accountAllows = false;
          this.apply();
        }
      }
    });
  }

  private saveAccountChoice(granted: boolean): void {
    this.http.post('/api/user/consents', { consent_type: 'analytics', granted }).subscribe({
      error: () => {
        // The account could not be updated. Stay on the safe side in this
        // browser: nothing is sent until the account says yes.
        if (granted) {
          this.accountAllows = false;
          this.apply();
        }
      }
    });
  }

  private readChoice(): AnalyticsChoice {
    try {
      if (typeof localStorage === 'undefined') {
        return null;
      }
      const value = localStorage.getItem(ANALYTICS_CHOICE_KEY);
      return value === 'accepted' || value === 'rejected' ? value : null;
    } catch {
      return null;
    }
  }

  private storeChoice(choice: 'accepted' | 'rejected'): void {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(ANALYTICS_CHOICE_KEY, choice);
      }
    } catch {
      // Private browsing: the answer lasts for this page only
    }
    this.choiceSubject.next(choice);
  }
}
