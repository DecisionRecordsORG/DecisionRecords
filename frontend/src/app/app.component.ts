import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterModule, Router, NavigationEnd } from '@angular/router';
import { NavbarComponent } from './components/shared/navbar.component';
import { AuthService } from './services/auth.service';
import { VersionService } from './services/version.service';
import { PostHogService } from './services/posthog.service';
import { FeatureFlagsService } from './services/feature-flags.service';
import { filter } from 'rxjs/operators';

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
  imports: [CommonModule, RouterOutlet, RouterModule, NavbarComponent],
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
    '/setup'
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
    private postHogService: PostHogService
  ) {
    // Initialize PostHog analytics (only if enabled)
    if (this.featureFlags.analyticsEnabled) {
      this.postHogService.init();
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
}
