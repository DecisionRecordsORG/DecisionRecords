import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatDividerModule } from '@angular/material/divider';
import { AuthService } from '../../services/auth.service';
import { User, MasterAccount } from '../../models/decision.model';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatToolbarModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatDividerModule
  ],
  template: `
    <mat-toolbar color="primary" class="navbar">
      <a routerLink="/" class="brand">
        <mat-icon>architecture</mat-icon>
        <span>Architecture Decisions</span>
      </a>

      <span class="spacer"></span>

      @if (authService.isAuthenticated) {
        <nav class="nav-links">
          <a mat-button routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}">
            <mat-icon>list</mat-icon>
            Decisions
          </a>
          @if (!authService.isMasterAccount) {
            <a mat-button routerLink="/decision/new" routerLinkActive="active">
              <mat-icon>add</mat-icon>
              New
            </a>
          }
        </nav>

        <button mat-button [matMenuTriggerFor]="userMenu" class="user-button">
          @if (authService.isMasterAccount) {
            <mat-icon>admin_panel_settings</mat-icon>
          } @else {
            <mat-icon>person</mat-icon>
          }
          <span class="user-name">{{ displayName }}</span>
          <mat-icon>arrow_drop_down</mat-icon>
        </button>

        <mat-menu #userMenu="matMenu">
          <div class="menu-header">
            @if (authService.isMasterAccount) {
              <mat-icon>shield</mat-icon>
              <span>Master Account</span>
            } @else {
              <span>{{ userDomain }}</span>
            }
          </div>
          <mat-divider></mat-divider>

          @if (authService.isMasterAccount) {
            <a mat-menu-item routerLink="/master/profile">
              <mat-icon>settings</mat-icon>
              Account Settings
            </a>
            <a mat-menu-item routerLink="/settings">
              <mat-icon>admin_panel_settings</mat-icon>
              System Settings
            </a>
          } @else {
            <a mat-menu-item routerLink="/profile">
              <mat-icon>notifications</mat-icon>
              Notifications
            </a>
            @if (authService.isAdmin) {
              <a mat-menu-item routerLink="/settings">
                <mat-icon>settings</mat-icon>
                Settings
              </a>
            }
          }

          <mat-divider></mat-divider>
          <button mat-menu-item (click)="logout()">
            <mat-icon>logout</mat-icon>
            Logout
          </button>
        </mat-menu>
      }
    </mat-toolbar>
  `,
  styles: [`
    .navbar {
      position: sticky;
      top: 0;
      z-index: 1000;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
      color: white;
      text-decoration: none;
      font-size: 18px;
      font-weight: 500;
    }

    .spacer {
      flex: 1;
    }

    .nav-links {
      display: flex;
      gap: 8px;
      margin-right: 16px;
    }

    .nav-links a {
      color: rgba(255, 255, 255, 0.9);
    }

    .nav-links a.active {
      background: rgba(255, 255, 255, 0.1);
    }

    .user-button {
      color: white;
    }

    .user-name {
      margin: 0 4px;
      max-width: 150px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .menu-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      color: #888;
      font-size: 12px;
    }

    @media (max-width: 600px) {
      .nav-links {
        display: none;
      }

      .user-name {
        display: none;
      }
    }
  `]
})
export class NavbarComponent {
  constructor(
    public authService: AuthService,
    private router: Router
  ) {}

  get displayName(): string {
    const user = this.authService.currentUser?.user;
    if (!user) return '';

    if (this.authService.isMasterAccount) {
      const master = user as MasterAccount;
      return master.name || master.username;
    } else {
      const regularUser = user as User;
      return regularUser.name || regularUser.email;
    }
  }

  get userDomain(): string {
    if (this.authService.isMasterAccount) return 'Master Account';
    const user = this.authService.currentUser?.user as User;
    return user?.sso_domain || '';
  }

  logout(): void {
    this.authService.logout().subscribe({
      next: () => this.router.navigate(['/login']),
      error: () => this.router.navigate(['/login'])
    });
  }
}
