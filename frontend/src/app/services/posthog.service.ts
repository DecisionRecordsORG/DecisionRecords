import { Injectable, Inject, PLATFORM_ID, NgZone } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import posthog from 'posthog-js';

/**
 * What the browser sends to PostHog, and what it never sends.
 *
 * Sent after the person accepted analytics: page views and clicks, as
 * "something of this kind happened on this page". Never sent: the text of
 * what was clicked (it can be a decision's title or a colleague's name), the
 * attributes of the clicked element, anything typed into a field, and the
 * part of an address after "?" or "#" (it can hold an email address or a
 * one-time link). Sessions are not recorded.
 *
 * ANALYTICS_OPTIONS and sanitizeAnalyticsEvent are exported so the unit
 * tests can pin both halves of that promise.
 */
export const ANALYTICS_OPTIONS = {
  api_host: 'https://e.decisionrecords.org',
  ui_host: 'https://eu.i.posthog.com',
  // Enable automatic pageview tracking
  capture_pageview: true,
  // Track when users leave pages (for engagement metrics)
  capture_pageleave: true,
  // Privacy-friendly defaults
  persistence: 'localStorage' as const,
  // Sessions are not recorded; if recording is ever switched on, inputs and
  // text stay masked
  disable_session_recording: true,
  session_recording: { maskAllInputs: true, maskTextSelector: '*' },
  // Respect Do Not Track browser setting
  respect_dnt: true,
  // Clicks and form submissions are counted, without the text or the
  // attributes of the element: a list row's text is a decision title
  autocapture: true,
  mask_all_text: true,
  mask_all_element_attributes: true,
  // Disable debug mode in production
  debug: false
};

/** The public key of the analytics project (it is sent with every event; it is not a secret). */
export const ANALYTICS_PROJECT_KEY = 'phc_c3dvhlzjwriryAY7FBaEJ6vV6DigrM5zIqaXowbB2OQ';

/** Event properties that are dropped whatever they hold. */
const DROPPED_PROPERTIES = ['$el_text', 'title', '$title'];

function withoutQueryAndFragment(value: string): string {
  const cut = value.search(/[?#]/);
  return cut === -1 ? value : value.slice(0, cut);
}

/**
 * Last check on every event before it leaves the browser: addresses lose
 * their query string and fragment, and element text and page titles are
 * removed. Returns the same event object, changed in place.
 */
export function sanitizeAnalyticsEvent<T extends { properties?: Record<string, unknown>; $set?: Record<string, unknown>; $set_once?: Record<string, unknown> } | null>(event: T): T {
  if (!event) {
    return event;
  }
  for (const bag of [event.properties, event.$set, event.$set_once]) {
    if (!bag) {
      continue;
    }
    for (const key of DROPPED_PROPERTIES) {
      delete bag[key];
    }
    for (const key of Object.keys(bag)) {
      const value = bag[key];
      if (typeof value === 'string' && /url|referrer|href/i.test(key)) {
        bag[key] = withoutQueryAndFragment(value);
      }
    }
    // Autocapture describes the clicked element and its parents. Keep the
    // kind of element; drop text and attributes in case a build of the
    // library ignores the masking options above.
    const elements = bag['$elements'];
    if (Array.isArray(elements)) {
      bag['$elements'] = elements.map((element: Record<string, unknown>) => {
        const kept: Record<string, unknown> = {};
        for (const key of ['tag_name', 'nth_child', 'nth_of_type']) {
          if (key in element) {
            kept[key] = element[key];
          }
        }
        return kept;
      });
    }
  }
  return event;
}

@Injectable({
  providedIn: 'root'
})
export class PostHogService {
  private initialized = false;
  /**
   * Our own gate, checked for every event just before it would be sent.
   * It does not depend on how the library stores an opt-out.
   */
  private sending = false;

  constructor(
    @Inject(PLATFORM_ID) private platformId: object,
    private ngZone: NgZone
  ) {}

  /** True once the library has been started in this page. */
  get started(): boolean {
    return this.initialized;
  }

  /**
   * Initialize PostHog analytics.
   * Only runs on client-side (browser) to avoid SSR issues.
   *
   * Call `enable()` instead: it decides nothing by itself, but it also undoes
   * an earlier `disable()`.
   */
  init(): void {
    if (!isPlatformBrowser(this.platformId)) {
      return; // Skip initialization on server-side
    }

    if (this.initialized) {
      return; // Already initialized
    }

    try {
      // Run outside Angular zone to prevent performance issues
      this.ngZone.runOutsideAngular(() => {
        posthog.init(ANALYTICS_PROJECT_KEY, {
          ...ANALYTICS_OPTIONS,
          before_send: (event) => (this.sending ? sanitizeAnalyticsEvent(event) : null)
        });
      });

      this.initialized = true;
    } catch (error) {
      // PostHog initialization failed - log but don't break the app
      console.warn('PostHog initialization failed:', error);
    }
  }

  /**
   * Start sending, or resume after `disable()`. Only AnalyticsConsentService
   * calls this, once it knows the person allows analytics.
   */
  enable(): void {
    if (!isPlatformBrowser(this.platformId)) {
      return;
    }
    this.sending = true;
    this.init();
    if (!this.initialized) {
      this.sending = false;
      return;
    }
    try {
      if (posthog.has_opted_out_capturing()) {
        posthog.opt_in_capturing({ captureEventName: false });
      }
    } catch (error) {
      console.warn('PostHog could not be resumed:', error);
    }
  }

  /**
   * Stop sending. Nothing is sent from this browser until `enable()` is
   * called again, and the identifier the library kept for this browser is
   * thrown away. If the library was never started in this page, only what
   * an earlier visit stored in this browser is removed.
   */
  disable(): void {
    this.sending = false;
    if (!isPlatformBrowser(this.platformId)) {
      return;
    }
    if (!this.initialized) {
      // Not started in this page, so nothing is being sent. What an earlier
      // visit left in this browser (the library's identifier for it) goes.
      this.forgetStoredIdentifier();
      return;
    }
    try {
      // Events from the last few seconds that are still waiting to be sent
      // are thrown away. The queue is internal to the library: if a later
      // version moves it, the gate above still stops everything new.
      const queue = (posthog as unknown as { _requestQueue?: { _queue?: unknown[] } })._requestQueue;
      if (queue && Array.isArray(queue._queue)) {
        queue._queue = [];
      }
    } catch {
      // Nothing to empty
    }
    try {
      // reset() first: it forgets the browser's identifier, but it also
      // forgets a stored opt-out, so the opt-out has to come after it
      posthog.reset();
      posthog.opt_out_capturing();
    } catch (error) {
      console.warn('PostHog could not be stopped:', error);
    }
  }

  /** Remove what the library stored in this browser on an earlier visit. */
  private forgetStoredIdentifier(): void {
    try {
      if (typeof localStorage === 'undefined') {
        return;
      }
      const stored: string[] = [];
      for (let index = 0; index < localStorage.length; index++) {
        const key = localStorage.key(index);
        if (key && key.startsWith(`ph_${ANALYTICS_PROJECT_KEY}_`)) {
          stored.push(key);
        }
      }
      stored.forEach(key => localStorage.removeItem(key));
    } catch {
      // Storage is blocked: nothing is stored either
    }
  }

  /**
   * Capture a custom event.
   * @param eventName Name of the event
   * @param properties Optional properties to attach to the event
   */
  capture(eventName: string, properties?: Record<string, unknown>): void {
    if (!isPlatformBrowser(this.platformId) || !this.initialized) {
      return;
    }
    posthog.capture(eventName, properties);
  }

  /**
   * Identify a user (call after login).
   * @param userId Unique user identifier
   * @param properties Optional user properties
   */
  identify(userId: string, properties?: Record<string, unknown>): void {
    if (!isPlatformBrowser(this.platformId) || !this.initialized) {
      return;
    }
    posthog.identify(userId, properties);
  }

  /**
   * Reset user identity (call after logout).
   */
  reset(): void {
    if (!isPlatformBrowser(this.platformId) || !this.initialized) {
      return;
    }
    posthog.reset();
  }

  /**
   * Set properties for the current user.
   * @param properties User properties to set
   */
  setPersonProperties(properties: Record<string, unknown>): void {
    if (!isPlatformBrowser(this.platformId) || !this.initialized) {
      return;
    }
    posthog.setPersonProperties(properties);
  }

  /**
   * Associate user with a group (e.g., organization/tenant).
   * @param groupType Type of group (e.g., 'organization', 'tenant')
   * @param groupKey Unique identifier for the group
   * @param properties Optional group properties
   */
  group(groupType: string, groupKey: string, properties?: Record<string, unknown>): void {
    if (!isPlatformBrowser(this.platformId) || !this.initialized) {
      return;
    }
    posthog.group(groupType, groupKey, properties);
  }

  /**
   * Check if a feature flag is enabled.
   * @param flagKey The feature flag key
   * @returns true if enabled, false otherwise
   */
  isFeatureEnabled(flagKey: string): boolean {
    if (!isPlatformBrowser(this.platformId) || !this.initialized) {
      return false;
    }
    return posthog.isFeatureEnabled(flagKey) ?? false;
  }

  /**
   * Get a feature flag value.
   * @param flagKey The feature flag key
   * @returns The flag value or undefined
   */
  getFeatureFlag(flagKey: string): string | boolean | undefined {
    if (!isPlatformBrowser(this.platformId) || !this.initialized) {
      return undefined;
    }
    return posthog.getFeatureFlag(flagKey);
  }
}
