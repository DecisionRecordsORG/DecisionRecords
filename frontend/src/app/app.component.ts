import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { NavbarComponent } from './components/shared/navbar.component';
import { AuthService } from './services/auth.service';

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
  `]
})
export class AppComponent {
  constructor(public authService: AuthService) {}
}
