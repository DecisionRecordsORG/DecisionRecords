import { Injectable, Inject, PLATFORM_ID, NgZone } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import posthog from 'posthog-js';

@Injectable({
  providedIn: 'root'
})
export class PostHogService {
  private initialized = false;

  constructor(
    @Inject(PLATFORM_ID) private platformId: object,
    private ngZone: NgZone
  ) {}

  /**
   * Initialize PostHog analytics.
   * Only runs on client-side (browser) to avoid SSR issues.
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
        posthog.init('phc_c3dvhlzjwriryAY7FBaEJ6vV6DigrM5zIqaXowbB2OQ', {
          api_host: 'https://e.decisionrecords.org',
          ui_host: 'https://eu.i.posthog.com',
          // Set defaults date - enables automatic pageview tracking
          defaults: '2025-11-30',
          // Track when users leave pages (for engagement metrics)
          capture_pageleave: true,
          // Privacy-friendly defaults
          persistence: 'localStorage',
          // Disable session recording for MVP (reduces overhead, can enable later)
          disable_session_recording: true,
          // Respect Do Not Track browser setting
          respect_dnt: true,
          // Enable autocapture for clicks and form submissions
          autocapture: true,
          // Don't capture text input values for privacy
          mask_all_text: false,
          mask_all_element_attributes: false,
          // Disable debug mode in production
          debug: false
        });
      });

      this.initialized = true;
    } catch (error) {
      // PostHog initialization failed - log but don't break the app
      console.warn('PostHog initialization failed:', error);
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
