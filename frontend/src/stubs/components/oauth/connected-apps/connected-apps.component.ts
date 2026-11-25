import { Component, Input } from '@angular/core';

/**
 * Community Edition: connecting apps by OAuth is an Enterprise feature, so the
 * card that lists connected apps shows nothing. Same selector and inputs as the
 * Enterprise component it stands in for.
 */
@Component({
  selector: 'app-connected-apps',
  standalone: true,
  template: '',
})
export class ConnectedAppsComponent {
  @Input() mode: 'user' | 'tenant' = 'user';
}
