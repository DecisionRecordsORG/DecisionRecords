import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { tap, catchError, map } from 'rxjs/operators';

export interface FeatureFlags {
  edition: 'community' | 'enterprise';
  is_enterprise: boolean;
  // Core features (always available)
  decisions: boolean;
  multi_tenancy: boolean;
  webauthn: boolean;
  generic_oidc: boolean;
  local_auth: boolean;
  governance: boolean;
  audit_logs: boolean;
  email_notifications: boolean;
  spaces: boolean;
  infrastructure: boolean;
  // Enterprise features
  slack_integration: boolean;
  teams_integration: boolean;
  google_oauth: boolean;
  slack_oidc: boolean;
  ai_features: boolean;
  posthog_analytics: boolean;
  azure_keyvault: boolean;
  cloudflare_security: boolean;
  marketing_pages: boolean;
}

const DEFAULT_FLAGS: FeatureFlags = {
  edition: 'community',
  is_enterprise: false,
  // Core features
  decisions: true,
  multi_tenancy: true,
  webauthn: true,
  generic_oidc: true,
  local_auth: true,
  governance: true,
  audit_logs: true,
  email_notifications: true,
  spaces: true,
  infrastructure: true,
  // Enterprise features (disabled by default)
  slack_integration: false,
  teams_integration: false,
  google_oauth: false,
  slack_oidc: false,
  ai_features: false,
  posthog_analytics: false,
  azure_keyvault: false,
  cloudflare_security: false,
  marketing_pages: false
};

@Injectable({
  providedIn: 'root'
})
export class FeatureFlagsService {
  private http = inject(HttpClient);
  private flagsSubject = new BehaviorSubject<FeatureFlags>(DEFAULT_FLAGS);
  private loaded = false;

  flags$ = this.flagsSubject.asObservable();

  get flags(): FeatureFlags {
    return this.flagsSubject.value;
  }

  get isEnterprise(): boolean {
    return this.flags.is_enterprise;
  }

  get isCommunity(): boolean {
    return !this.flags.is_enterprise;
  }

  loadFlags(): Observable<FeatureFlags> {
    if (this.loaded) {
      return of(this.flags);
    }

    return this.http.get<FeatureFlags>('/api/features').pipe(
      tap(flags => {
        this.flagsSubject.next(flags);
        this.loaded = true;
      }),
      catchError(error => {
        console.warn('Failed to load feature flags, using defaults:', error);
        return of(DEFAULT_FLAGS);
      })
    );
  }

  isEnabled(feature: keyof FeatureFlags): boolean {
    const value = this.flags[feature];
    return typeof value === 'boolean' ? value : false;
  }

  // Convenience methods for common checks
  get slackEnabled(): boolean {
    return this.isEnabled('slack_integration');
  }

  get teamsEnabled(): boolean {
    return this.isEnabled('teams_integration');
  }

  get aiEnabled(): boolean {
    return this.isEnabled('ai_features');
  }

  get analyticsEnabled(): boolean {
    return this.isEnabled('posthog_analytics');
  }

  get marketingPagesEnabled(): boolean {
    return this.isEnabled('marketing_pages');
  }
}
