import { Component, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-site-nav',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <nav class="site-nav" [class.scrolled]="scrolled" [class.dark-bg]="darkBackground" [class.light-top]="lightTopBackground">
      <div class="nav-container">
        <a routerLink="/" class="nav-logo">
          <img [src]="(scrolled && !darkBackground) || lightTopBackground ? '/assets/decision-records-logo-official.svg' : '/assets/decision-records-logo-white.svg'" alt="Decision Records" />
        </a>
        <div class="nav-links">
          <a routerLink="/solutions">Solutions</a>
          <a routerLink="/integrations">Integrations</a>
          <a routerLink="/blog">Blog</a>
          <a routerLink="/faq">FAQ</a>
          <a routerLink="/about">About</a>
        </div>
        <div class="nav-actions">
          <a *ngIf="!isAuthenticated" (click)="signIn()" class="nav-signin">Sign In</a>
          <a *ngIf="isAuthenticated" (click)="goToTenant()" class="nav-signin">Your Decisions</a>
        </div>
        <button class="nav-mobile-toggle" (click)="toggleMobileMenu()">
          <mat-icon>{{ mobileMenuOpen ? 'close' : 'menu' }}</mat-icon>
        </button>
      </div>
      <!-- Mobile Menu -->
      <div class="nav-mobile-menu" [class.open]="mobileMenuOpen">
        <a routerLink="/solutions" (click)="mobileMenuOpen = false">Solutions</a>
        <a routerLink="/integrations" (click)="mobileMenuOpen = false">Integrations</a>
        <a routerLink="/blog" (click)="mobileMenuOpen = false">Blog</a>
        <a routerLink="/faq" (click)="mobileMenuOpen = false">FAQ</a>
        <a routerLink="/about" (click)="mobileMenuOpen = false">About</a>
        <a *ngIf="!isAuthenticated" (click)="signIn()" class="nav-signin-mobile">Sign In</a>
        <a *ngIf="isAuthenticated" (click)="goToTenant()" class="nav-signin-mobile">Your Decisions</a>
      </div>
    </nav>
  `,
  styles: [`
    .site-nav {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 1000;
      padding: 16px 0;
      transition: all 0.3s ease;
    }

    .site-nav.scrolled {
      background: white;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      padding: 12px 0;
    }

    .site-nav.scrolled.dark-bg {
      background: rgba(30, 58, 138, 0.98);
    }

    .nav-container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .nav-logo {
      display: flex;
      align-items: center;
    }

    .nav-logo img {
      height: 28px;
      width: auto;
    }

    .nav-links {
      display: flex;
      align-items: center;
      gap: 32px;
    }

    .nav-links a {
      color: rgba(255, 255, 255, 0.9);
      text-decoration: none;
      font-size: 0.95rem;
      font-weight: 500;
      transition: color 0.2s;
    }

    .site-nav.scrolled:not(.dark-bg) .nav-links a {
      color: #475569;
    }

    .nav-links a:hover {
      color: white;
    }

    .site-nav.scrolled:not(.dark-bg) .nav-links a:hover {
      color: #1e40af;
    }

    /* Light top background (for pages with light headers like blog posts) */
    .site-nav.light-top:not(.scrolled) .nav-links a {
      color: #475569;
    }

    .site-nav.light-top:not(.scrolled) .nav-links a:hover {
      color: #1e40af;
    }

    .nav-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .nav-signin {
      color: white;
      border: 1px solid rgba(255, 255, 255, 0.5);
      border-radius: 100px;
      padding: 8px 20px;
      font-weight: 500;
      font-size: 0.9rem;
      text-decoration: none;
      transition: all 0.2s;
      cursor: pointer;
    }

    .nav-signin:hover {
      border-color: white;
      background: rgba(255, 255, 255, 0.1);
    }

    .site-nav.scrolled:not(.dark-bg) .nav-signin {
      color: #1e40af;
      border-color: #1e40af;
    }

    .site-nav.scrolled:not(.dark-bg) .nav-signin:hover {
      background: rgba(30, 64, 175, 0.08);
    }

    .site-nav.light-top:not(.scrolled) .nav-signin {
      color: #1e40af;
      border-color: #1e40af;
    }

    .site-nav.light-top:not(.scrolled) .nav-signin:hover {
      background: rgba(30, 64, 175, 0.08);
    }

    .nav-mobile-toggle {
      display: none;
      background: none;
      border: none;
      color: white;
      cursor: pointer;
      padding: 8px;
    }

    .site-nav.scrolled:not(.dark-bg) .nav-mobile-toggle {
      color: #475569;
    }

    .site-nav.light-top:not(.scrolled) .nav-mobile-toggle {
      color: #475569;
    }

    .nav-mobile-toggle mat-icon {
      font-size: 28px;
      width: 28px;
      height: 28px;
    }

    .nav-mobile-menu {
      display: none;
      flex-direction: column;
      background: rgba(30, 58, 138, 0.98);
      padding: 20px 24px;
      gap: 4px;
    }

    .site-nav.scrolled:not(.dark-bg) .nav-mobile-menu {
      background: white;
      border-top: 1px solid #e2e8f0;
    }

    .nav-mobile-menu.open {
      display: flex;
    }

    .nav-mobile-menu a {
      color: rgba(255, 255, 255, 0.9);
      text-decoration: none;
      font-size: 1rem;
      font-weight: 500;
      padding: 14px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }

    .site-nav.scrolled:not(.dark-bg) .nav-mobile-menu a {
      color: #475569;
      border-bottom-color: #e2e8f0;
    }

    .nav-mobile-menu a:hover {
      color: white;
    }

    .site-nav.scrolled:not(.dark-bg) .nav-mobile-menu a:hover {
      color: #1e40af;
    }

    .nav-signin-mobile {
      margin-top: 8px;
      text-align: center;
      border: 1px solid rgba(255, 255, 255, 0.5) !important;
      border-radius: 100px !important;
      padding: 14px 24px !important;
    }

    .site-nav.scrolled:not(.dark-bg) .nav-signin-mobile {
      border-color: #1e40af !important;
      color: #1e40af !important;
    }

    @media (max-width: 768px) {
      .nav-links,
      .nav-actions {
        display: none;
      }

      .nav-mobile-toggle {
        display: block;
      }
    }
  `],
  host: {
    '(window:scroll)': 'onScroll()'
  }
})
export class SiteNavComponent implements OnInit {
  @Input() darkBackground = false;
  @Input() lightTopBackground = false;

  mobileMenuOpen = false;
  scrolled = false;
  isAuthenticated = false;
  userDomain: string | null = null;

  constructor(
    private router: Router,
    private authService: AuthService
  ) {}

  ngOnInit(): void {
    // Check auth state
    this.authService.currentUser$.subscribe(currentUser => {
      this.isAuthenticated = !!currentUser?.user;
      // Access sso_domain from the nested user object
      const user = currentUser?.user as { sso_domain?: string } | null;
      this.userDomain = user?.sso_domain || null;
    });
  }

  toggleMobileMenu(): void {
    this.mobileMenuOpen = !this.mobileMenuOpen;
  }

  signIn(): void {
    this.mobileMenuOpen = false;
    this.router.navigate(['/'], { queryParams: { signin: 'true' } });
  }

  goToTenant(): void {
    this.mobileMenuOpen = false;
    if (this.userDomain) {
      this.router.navigate(['/', this.userDomain]);
    } else {
      // Fallback to homepage with signin if no domain
      this.router.navigate(['/'], { queryParams: { signin: 'true' } });
    }
  }

  onScroll(): void {
    this.scrolled = window.scrollY > 50;
    if (this.scrolled) {
      this.mobileMenuOpen = false;
    }
  }
}
