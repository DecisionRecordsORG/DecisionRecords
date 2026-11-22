import { Component, Input, inject } from '@angular/core';
import { FeatureFlagsService } from '../../services/feature-flags.service';
import { buildSupportUrl, SupportTopic } from '../../services/support-link';

/**
 * A quiet "Can't sign in? Get help" link to the public support page.
 *
 * It opens in a new tab so a half-filled form on the current screen is kept.
 * It renders nothing when the installation has no support page: see
 * services/support-link.ts.
 */
@Component({
  selector: 'app-support-link',
  standalone: true,
  template: `
    @if (href; as url) {
      <a class="support-link" [href]="url" target="_blank" rel="noopener" data-testid="support-link">{{ label }}</a>
    }
  `,
  styles: [`
    :host {
      display: block;
      margin-top: 16px;
      text-align: center;
      font-size: 13px;
      line-height: 1.4;
    }

    :host:empty {
      display: none;
    }

    .support-link {
      color: inherit;
      opacity: 0.75;
      text-decoration: underline;
    }

    .support-link:hover,
    .support-link:focus-visible {
      opacity: 1;
    }
  `]
})
export class SupportLinkComponent {
  private featureFlags = inject(FeatureFlagsService);

  @Input() topic: SupportTopic = 'signin';
  @Input() email: string | null | undefined = '';
  @Input() org: string | null | undefined = '';
  @Input() label = "Can't sign in? Get help";

  get href(): string | null {
    return buildSupportUrl(this.featureFlags.flags, {
      topic: this.topic,
      email: this.email,
      org: this.org
    });
  }
}
