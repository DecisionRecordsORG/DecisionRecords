import { ApplicationConfig, provideZoneChangeDetection, APP_INITIALIZER, inject } from '@angular/core';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { firstValueFrom } from 'rxjs';

import { routes } from './app.routes';
import { csrfInterceptor } from './interceptors/csrf.interceptor';
import { provideClientHydration } from '@angular/platform-browser';
import { FeatureFlagsService } from './services/feature-flags.service';

// Load feature flags before app starts to prevent race conditions
function initializeFeatureFlags(): () => Promise<void> {
  const featureFlags = inject(FeatureFlagsService);
  return () => firstValueFrom(featureFlags.loadFlags()).then(() => {});
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(
      routes,
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'top' })
    ),
    provideHttpClient(
      withFetch(),
      withInterceptors([csrfInterceptor])  // Add CSRF protection to all HTTP requests
    ),
    provideAnimationsAsync(),
    provideClientHydration(),
    // Load feature flags before app bootstraps
    {
      provide: APP_INITIALIZER,
      useFactory: initializeFeatureFlags,
      multi: true
    }
  ]
};
