import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatDividerModule } from '@angular/material/divider';
import { MatBadgeModule } from '@angular/material/badge';
import { AuthService } from '../../services/auth.service';
import { AdminService } from '../../services/admin.service';
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
    MatDividerModule,
    MatBadgeModule
  ],
  template: `
    <mat-toolbar color="primary" class="navbar">
      <a [routerLink]="homeLink" class="brand">
        <mat-icon>architecture</mat-icon>
        <span class="brand-text">Architecture Decisions</span>
        @if (!authService.isMasterAccount && userDomain) {
          <span class="tenant-badge">{{ userDomain }}</span>
        }
      </a>

      <span class="spacer"></span>

      @if (authService.isAuthenticated) {
        <nav class="nav-links">
          <a mat-button [routerLink]="decisionsLink" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}">
            <mat-icon>list</mat-icon>
            Decisions
          </a>
          @if (!authService.isMasterAccount) {
            <a mat-button [routerLink]="newDecisionLink" routerLinkActive="active">
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
          @if (pendingRequestsCount > 0 && authService.isAdmin) {
            <span class="badge">{{ pendingRequestsCount }}</span>
          }
          <mat-icon>arrow_drop_down</mat-icon>
        </button>

        <mat-menu #userMenu="matMenu">
          <div class="menu-header">
            @if (authService.isMasterAccount) {
              <mat-icon>shield</mat-icon>
              <span>Super Admin</span>
            } @else {
              <mat-icon>business</mat-icon>
              <span>{{ userDomain }}</span>
            }
          </div>
          <mat-divider></mat-divider>

          @if (authService.isMasterAccount) {
            <a mat-menu-item routerLink="/superadmin/dashboard">
              <mat-icon>dashboard</mat-icon>
              Dashboard
            </a>
            <a mat-menu-item routerLink="/superadmin/settings">
              <mat-icon>settings</mat-icon>
              System Settings
            </a>
          } @else {
            <a mat-menu-item [routerLink]="profileLink">
              <mat-icon>person</mat-icon>
              Profile
            </a>
            <a mat-menu-item [routerLink]="profileLink">
              <mat-icon>notifications</mat-icon>
              Notifications
            </a>
            @if (authService.isAdmin) {
              <a mat-menu-item [routerLink]="adminLink">
                <mat-icon>settings</mat-icon>
                Admin Settings
                @if (pendingRequestsCount > 0) {
                  <span class="menu-badge">{{ pendingRequestsCount }}</span>
                }
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

    .tenant-badge {
      font-size: 12px;
      background: rgba(255, 255, 255, 0.2);
      padding: 2px 8px;
      border-radius: 4px;
      margin-left: 8px;
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

    .badge {
      background: #ff4081;
      color: white;
      border-radius: 50%;
      padding: 2px 6px;
      font-size: 11px;
      margin-left: 4px;
    }

    .menu-badge {
      background: #ff4081;
      color: white;
      border-radius: 4px;
      padding: 2px 6px;
      font-size: 11px;
      margin-left: 8px;
    }

    .menu-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      color: #666;
      font-size: 13px;
    }

    .menu-header mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    @media (max-width: 600px) {
      .nav-links {
        display: none;
      }

      .user-name {
        display: none;
      }

      .brand-text {
        display: none;
      }

      .tenant-badge {
        margin-left: 0;
      }
    }
  `]
})
export class NavbarComponent {
  pendingRequestsCount = 0;

  constructor(
    public authService: AuthService,
    private adminService: AdminService,
    private router: Router
  ) {
    // Load pending requests count for admins
    if (this.authService.isAdmin) {
      this.loadPendingRequestsCount();
    }
  }

  loadPendingRequestsCount(): void {
    this.adminService.getPendingAccessRequests().subscribe({
      next: (requests) => this.pendingRequestsCount = requests.length,
      error: () => this.pendingRequestsCount = 0
    });
  }

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
    if (this.authService.isMasterAccount) return '';
    const user = this.authService.currentUser?.user as User;
    return user?.sso_domain || '';
  }

  get homeLink(): string {
    if (this.authService.isMasterAccount) {
      return '/superadmin/dashboard';
    }
    return `/${this.userDomain}`;
  }

  get decisionsLink(): string {
    if (this.authService.isMasterAccount) {
      return '/superadmin/dashboard';
    }
    return `/${this.userDomain}`;
  }

  get newDecisionLink(): string {
    return `/${this.userDomain}/decision/new`;
  }

  get profileLink(): string {
    return `/${this.userDomain}/profile`;
  }

  get adminLink(): string {
    return `/${this.userDomain}/admin`;
  }

  logout(): void {
    // Capture master status before logout clears user state
    const wasMaster = this.authService.isMasterAccount;
    this.authService.logout().subscribe({
      next: () => {
        if (wasMaster) {
          this.router.navigate(['/superadmin']);
        } else {
          this.router.navigate(['/']);
        }
      },
      error: () => this.router.navigate(['/'])
    });
  }
}
