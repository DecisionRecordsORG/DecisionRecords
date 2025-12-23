import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterModule, Router, NavigationEnd } from '@angular/router';
import { NavbarComponent } from './components/shared/navbar.component';
import { SiteNavComponent } from './components/shared/site-nav/site-nav.component';
import { SiteFooterComponent } from './components/shared/site-footer/site-footer.component';
import { AuthService } from './services/auth.service';
import { VersionService } from './services/version.service';
import { filter } from 'rxjs/operators';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterModule, NavbarComponent, SiteNavComponent, SiteFooterComponent],
  template: `
    @if (showSiteNav) {
      <app-site-nav [darkBackground]="siteNavDarkBg" [lightTopBackground]="siteNavLightTopBg"></app-site-nav>
    }
    @if (authService.isAuthenticated && showAppNavbar) {
      <app-navbar></app-navbar>
    }
    <main>
      <router-outlet></router-outlet>
    </main>
    @if (showSiteFooter) {
      <app-site-footer></app-site-footer>
    }
    <footer class="app-footer" [class.hidden]="showSiteFooter">
      <div class="footer-content">
        <small>
          Decision Records
          <span class="separator">|</span>
          <a routerLink="/about">About</a>
          <span class="separator">|</span>
          <span class="version" [title]="versionTooltip">{{ versionService.versionString }}</span>
        </small>
        <img src="/assets/made-sweden-label.jpg.png" alt="Made in Sweden" class="sweden-badge" />
      </div>
    </footer>
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

    .app-footer .sweden-badge {
      height: 20px;
      width: auto;
      opacity: 0.8;
    }

    .app-footer.hidden {
      display: none;
    }
  `]
})
export class AppComponent implements OnInit {
  showAppNavbar = false;
  showSiteNav = false;
  showSiteFooter = false;
  siteNavDarkBg = false;
  siteNavLightTopBg = false;

  // Marketing/public pages that should show the site nav
  private publicRoutes = [
    '/',
    '/about',
    '/blog',
    '/solutions',
    '/integrations',
    '/faq',
    '/terms',
    '/security',
    '/security-features',
    '/dpa',
    '/sla',
    '/licensing'
  ];

  // Routes that need dark background on site nav
  private darkBgRoutes = ['/', '/integrations/slack'];

  // Routes that need light top background on site nav
  private lightTopBgRoutes = ['/blog'];

  constructor(
    public authService: AuthService,
    public versionService: VersionService,
    private router: Router
  ) {}

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

    // Check if current path is a public/marketing route
    const isPublicRoute = this.publicRoutes.some(route => {
      if (route === '/') {
        return path === '/';
      }
      return path === route || path.startsWith(route + '/');
    });

    // Show site nav and footer on public pages
    this.showSiteNav = isPublicRoute;
    this.showSiteFooter = isPublicRoute;

    // Show app navbar only on tenant routes (not public pages)
    this.showAppNavbar = !isPublicRoute;

    // Determine site nav background style
    this.siteNavDarkBg = this.darkBgRoutes.some(route => {
      if (route === '/') {
        return path === '/';
      }
      return path === route || path.startsWith(route + '/');
    });

    this.siteNavLightTopBg = this.lightTopBgRoutes.some(route => {
      return path === route || path.startsWith(route + '/');
    });
  }

  get versionTooltip(): string {
    const info = this.versionService.currentVersion;
    if (!info) return '';
    return `Build: ${info.build_date}\nCommit: ${info.git_commit}\nEnvironment: ${info.environment}`;
  }
}
