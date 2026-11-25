import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterModule, Router, NavigationEnd } from '@angular/router';
import { NavbarComponent } from './components/shared/navbar.component';
import { AuthService } from './services/auth.service';
import { VersionService } from './services/version.service';
import { PostHogService } from './services/posthog.service';
import { FeatureFlagsService } from './services/feature-flags.service';
import { SeoService } from './services/seo.service';
import { HttpClient } from '@angular/common/http';
import { filter, take } from 'rxjs/operators';
import { CookieConsentComponent, CookieConsentStatus } from './components/shared/cookie-consent.component';

/**
 * Root Application Component
 *
 * Architecture:
 * - Marketing pages (homepage, blog, about, etc.) are served from a separate
 *   marketing site at decisionrecords.org
 * - This app (app.decisionrecords.org) handles authenticated tenant access
 * - The landing page handles CE setup/signin and EE tenant discovery
 *
 * Navigation:
 * - Landing page: Shows CE setup/signin or EE domain input
 * - Tenant pages: Uses NavbarComponent for authenticated navigation
 * - Super admin: Uses NavbarComponent
 */
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterModule, NavbarComponent, CookieConsentComponent],
  template: `
    @if (authService.isAuthenticated && showAppNavbar) {
      <app-navbar></app-navbar>
    }
    <main>
      <router-outlet></router-outlet>
    </main>
    @if (!isLandingPage) {
      <footer class="app-footer">
        <div class="footer-content">
          <small>
            Decision Records
            <span class="separator">|</span>
            <span class="version" [title]="versionTooltip">{{ versionService.versionString }}</span>
          </small>
        </div>
      </footer>
    }
    @if (featureFlags.analyticsEnabled) {
      <app-cookie-consent (consentChanged)="onCookieConsentChanged($event)"></app-cookie-consent>
    }
  `,
  styles: [`
    :host {
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }

    main {
      flex: 1;
      background-color: #f5f5f5;
    }

    .app-footer {
      padding: 16px;
      background: #fafafa;
      border-top: 1px solid #eee;
      color: #888;
    }

    .app-footer .footer-content {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }

    .app-footer a {
      color: #3f51b5;
    }

    .app-footer .separator {
      margin: 0 8px;
      color: #ccc;
    }

    .app-footer .version {
      font-family: monospace;
      cursor: help;
    }
  `]
})
export class AppComponent implements OnInit {
  showAppNavbar = false;
  isLandingPage = false;

  // Pages where we don't show the app navbar (landing, login, setup)
  // Note: Only exact matches for login pages, NOT all routes under them
  private noNavbarRoutes = [
    '/',
    '/license',
    '/setup',
    '/oauth'  // The consent page for connecting an app: one question, nothing else to click
  ];

  // Exact match routes (login pages only, not their sub-routes)
  private exactMatchNoNavbarRoutes = [
    '/superadmin'  // Only hide navbar on login page, not /superadmin/dashboard etc.
  ];

  constructor(
    public authService: AuthService,
    public versionService: VersionService,
    public featureFlags: FeatureFlagsService,
    private router: Router,
    private postHogService: PostHogService,
    private seoService: SeoService,
    private http: HttpClient
  ) {
    this.seoService.init();

    // Initialize PostHog analytics only if enabled AND cookie consent was given
    if (this.featureFlags.analyticsEnabled) {
      const consent = CookieConsentComponent.getConsent();
      if (consent === 'accepted') {
        this.postHogService.init();
      }
    }
    // Load feature flags on startup
    this.featureFlags.loadFlags().subscribe();
  }

  ngOnInit(): void {
    // Check initial route
    this.updateNavbarVisibility(this.router.url);

    // Listen for route changes
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: NavigationEnd) => {
      this.updateNavbarVisibility(event.urlAfterRedirects);
    });

    // Whenever someone becomes signed in (a page load with a session, or a
    // sign-in inside the app), pick up a request to connect an app that this
    // browser was in the middle of.
    this.authService.currentUser$.subscribe(current => {
      const signedInUserId = current?.user && !current.isMaster ? current.user.id : null;
      if (signedInUserId !== null && signedInUserId !== this.resumeCheckedForUserId) {
        this.resumeCheckedForUserId = signedInUserId;
        this.resumePendingAppConnection();
      } else if (signedInUserId === null) {
        this.resumeCheckedForUserId = null;
      }
    });
  }

  private resumeCheckedForUserId: number | null = null;

  /**
   * Lead a person back to the consent page they were sent away from to sign in.
   *
   * An app that wants to be connected sends the browser to the server, which
   * remembers the request in a short-lived cookie and shows the consent page.
   * Someone who was not signed in then signs in, by whichever method (password,
   * passkey, single sign-on, Google or Microsoft: all of them end with the app
   * loading for a signed-in user), and would otherwise land on their decision
   * list with the request forgotten. The server answers once per request.
   *
   * Enterprise Edition only; the Community Edition has no such requests.
   */
  private resumePendingAppConnection(): void {
    // The flags start as "community" and change once when the server has
    // answered, so in the Community Edition this never asks anything.
    this.featureFlags.flags$.pipe(
      filter(flags => flags.is_enterprise),
      take(1)
    ).subscribe(() => {
      if (!this.authService.isAuthenticated || this.authService.isMasterAccount) {
        return;
      }
      if (this.router.url.split('?')[0] === '/oauth/consent') {
        return;
      }
      this.http.get<{ request: string | null }>('/api/oauth/pending').subscribe({
        next: answer => {
          if (answer?.request) {
            // A full page load, not a route change inside the app: the server
            // sends the consent page with a header that forbids showing it in
            // a frame, and a header only applies to a document the browser
            // loads from that address.
            this.loadPage('/oauth/consent?request=' + encodeURIComponent(answer.request));
          }
        },
        error: () => { /* not offered here, or nothing pending */ }
      });
    });
  }

  /** Leave the app for another address with a full page load. Separate so tests can watch it. */
  loadPage(address: string): void {
    window.location.assign(address);
  }

  private updateNavbarVisibility(url: string): void {
    // Remove query params for comparison
    const path = url.split('?')[0];

    // Check if this is the landing page
    this.isLandingPage = path === '/';

    // Check if current path is a no-navbar route (prefix match)
    const isNoNavbarRoute = this.noNavbarRoutes.some(route => {
      if (route === '/') {
        return path === '/';
      }
      return path === route || path.startsWith(route + '/');
    });

    // Check if current path is an exact match no-navbar route (login pages only)
    const isExactNoNavbarRoute = this.exactMatchNoNavbarRoutes.some(route => path === route);

    // Also hide navbar on tenant login pages
    const isTenantLogin = path.match(/^\/[^/]+\/login$/);

    // Show app navbar only on authenticated tenant/admin routes
    this.showAppNavbar = !isNoNavbarRoute && !isExactNoNavbarRoute && !isTenantLogin;
  }

  get versionTooltip(): string {
    const info = this.versionService.currentVersion;
    if (!info) return '';
    return `Build: ${info.build_date}\nCommit: ${info.git_commit}\nEnvironment: ${info.environment}`;
  }

  onCookieConsentChanged(status: CookieConsentStatus): void {
    if (status === 'accepted' && this.featureFlags.analyticsEnabled) {
      this.postHogService.init();
    }
  }
}
