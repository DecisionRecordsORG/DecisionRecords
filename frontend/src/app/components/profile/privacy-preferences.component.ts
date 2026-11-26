import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { AnalyticsConsentService } from '../../services/analytics-consent.service';
import { FeatureFlagsService } from '../../services/feature-flags.service';

export type PreferenceType = 'analytics' | 'ai_processing' | 'email_notifications';

/**
 * The switches under "Privacy Preferences" on the profile page.
 *
 * Each switch does what its text says, at once:
 *  - Analytics: off means this browser sends nothing to the analytics
 *    service and the server's usage events and error reports are not tied to
 *    the person. Shown only where the installation has analytics.
 *  - AI Processing: whether AI tools the person connects (API keys,
 *    applications such as Claude or ChatGPT) and the AI features in Slack may
 *    act for them. It is their membership's AI opt-out, which every AI access
 *    check reads: on unless switched off; off refuses their keys and
 *    connected applications at once. Shown only where the installation has
 *    AI features.
 *  - Email notifications: off stops the emails about decisions. Account and
 *    security emails are not affected.
 */
@Component({
  selector: 'app-privacy-preferences',
  standalone: true,
  imports: [CommonModule, MatProgressSpinnerModule, MatSlideToggleModule, MatSnackBarModule],
  template: `
    @if (loading) {
      <mat-spinner diameter="24"></mat-spinner>
    } @else {
      <div class="consent-toggles">
        @if (featureFlags.analyticsEnabled) {
          <mat-slide-toggle
            [checked]="consents.analytics"
            (change)="update('analytics', $event.checked)"
            data-testid="preference-analytics">
            Analytics
          </mat-slide-toggle>
          <p class="consent-hint" data-testid="preference-analytics-hint">
            Let us count how the product is used, including in this browser. When this is off, this browser sends
            nothing to our analytics service, and the usage counts and error reports our servers keep are not
            linked to you.
          </p>
        }

        @if (featureFlags.aiEnabled) {
          <mat-slide-toggle
            [checked]="consents.ai_processing"
            (change)="update('ai_processing', $event.checked)"
            data-testid="preference-ai">
            AI Processing
          </mat-slide-toggle>
          <p class="consent-hint" data-testid="preference-ai-hint">
            On: AI tools you connect yourself, an API key or an application such as Claude or ChatGPT, may work
            with your organisation's decisions for you, where your organisation allows it. Off: your API keys and
            connected applications are refused, and you cannot create keys or connect applications.
          </p>
        }

        <mat-slide-toggle
          [checked]="consents.email_notifications"
          (change)="update('email_notifications', $event.checked)"
          data-testid="preference-email">
          Email notifications
        </mat-slide-toggle>
        <p class="consent-hint" data-testid="preference-email-hint">
          Emails about decisions: the notifications you chose above, and a message when you are made the owner of a
          decision. When this is off you get none of them. Emails about your account, such as sign-in and
          set-up links, are always sent.
        </p>
      </div>
    }
  `,
  styles: [`
    .consent-toggles { display: flex; flex-direction: column; gap: 4px; }
    .consent-hint { margin: 0 0 12px 48px; font-size: 13px; color: #666; }
  `]
})
export class PrivacyPreferencesComponent implements OnInit {
  loading = true;
  consents: Record<PreferenceType, boolean> = {
    analytics: false,
    ai_processing: true,
    email_notifications: true
  };

  constructor(
    private http: HttpClient,
    private snackBar: MatSnackBar,
    private analyticsConsent: AnalyticsConsentService,
    public featureFlags: FeatureFlagsService
  ) {}

  ngOnInit(): void {
    this.http.get<Record<string, { granted: boolean }>>('/api/user/consents').subscribe({
      next: (response) => {
        this.consents = {
          analytics: response['analytics']?.granted === true,
          // On unless switched off: the server reports the membership's AI opt-out
          ai_processing: response['ai_processing']?.granted !== false,
          // On unless the person switched it off
          email_notifications: response['email_notifications']?.granted !== false
        };
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      }
    });
  }

  update(type: PreferenceType, granted: boolean): void {
    this.consents = { ...this.consents, [type]: granted };
    if (type === 'analytics' && !granted) {
      // Stop this browser at once, before the server has answered
      this.analyticsConsent.accountSwitchChanged(false);
    }
    this.http.post('/api/user/consents', { consent_type: type, granted }).subscribe({
      next: () => {
        if (type === 'analytics' && granted) {
          this.analyticsConsent.accountSwitchChanged(true);
        }
        this.snackBar.open(granted ? 'Switched on' : 'Switched off', 'Close', { duration: 2000 });
      },
      error: () => {
        // Put the switch back. An analytics switch-off that could not be
        // saved stays off in this browser: the safe side.
        this.consents = { ...this.consents, [type]: !granted };
        this.snackBar.open('Failed to update preference', 'Close', { duration: 3000 });
      }
    });
  }
}
