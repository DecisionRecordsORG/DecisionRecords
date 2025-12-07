import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { NavbarComponent } from './components/shared/navbar.component';
import { AuthService } from './services/auth.service';
import { VersionService } from './services/version.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, NavbarComponent],
  template: `
    @if (authService.isAuthenticated) {
      <app-navbar></app-navbar>
    }
    <main>
      <router-outlet></router-outlet>
    </main>
    <footer class="app-footer">
      <small>
        Architecture Decision Records - Based on
        <a href="https://docs.arc42.org/section-9/" target="_blank" rel="noopener">arc42 Section 9</a>
        <span class="separator">|</span>
        Created by Lawrance Nyakiso
        <span class="separator">|</span>
        <span class="version" [title]="versionTooltip">{{ versionService.versionString }}</span>
      </small>
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
      text-align: center;
      background: #fafafa;
      border-top: 1px solid #eee;
      color: #888;
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
export class AppComponent {
  constructor(
    public authService: AuthService,
    public versionService: VersionService
  ) {}

  get versionTooltip(): string {
    const info = this.versionService.currentVersion;
    if (!info) return '';
    return `Build: ${info.build_date}\nCommit: ${info.git_commit}\nEnvironment: ${info.environment}`;
  }
}
