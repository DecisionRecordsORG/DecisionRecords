import { Component, OnInit, OnDestroy, Output, EventEmitter } from '@angular/core';
import { Subscription } from 'rxjs';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AnalyticsConsentService, ANALYTICS_CHOICE_KEY } from '../../services/analytics-consent.service';

const COOKIE_CONSENT_KEY = ANALYTICS_CHOICE_KEY;

export type CookieConsentStatus = 'accepted' | 'rejected' | null;

@Component({
  selector: 'app-cookie-consent',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatIconModule],
  template: `
    @if (showBanner) {
      <div class="cookie-consent-banner">
        <div class="cookie-content">
          <mat-icon>cookie</mat-icon>
          <div class="cookie-text">
            <strong>Cookie Notice</strong>
            <p>We use analytics cookies to understand how you use our product and improve your experience.
               No personal data is shared with third parties.</p>
          </div>
        </div>
        <div class="cookie-actions">
          <button mat-stroked-button (click)="reject()" data-testid="analytics-notice-reject">Reject</button>
          <button mat-raised-button color="primary" (click)="accept()" data-testid="analytics-notice-accept">Accept</button>
        </div>
      </div>
    }
  `,
  styles: [`
    .cookie-consent-banner {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: #fff;
      border-top: 1px solid #e0e0e0;
      box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
      padding: 16px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      z-index: 1000;
    }

    .cookie-content {
      display: flex;
      align-items: flex-start;
      gap: 12px;
    }

    .cookie-content mat-icon {
      color: #ff9800;
      margin-top: 2px;
    }

    .cookie-text {
      max-width: 600px;
    }

    .cookie-text strong {
      display: block;
      margin-bottom: 4px;
    }

    .cookie-text p {
      margin: 0;
      font-size: 13px;
      color: #666;
    }

    .cookie-actions {
      display: flex;
      gap: 8px;
      flex-shrink: 0;
    }

    @media (max-width: 600px) {
      .cookie-consent-banner {
        flex-direction: column;
        align-items: stretch;
      }
      .cookie-actions {
        justify-content: flex-end;
      }
    }
  `]
})
export class CookieConsentComponent implements OnInit, OnDestroy {
  @Output() consentChanged = new EventEmitter<CookieConsentStatus>();

  showBanner = false;
  private choiceSubscription?: Subscription;

  constructor(private analyticsConsent: AnalyticsConsentService) {}

  ngOnInit(): void {
    // Follows the stored answer, so the notice also goes away when the
    // person answers through the "Analytics" switch on their profile
    this.choiceSubscription = this.analyticsConsent.choice$.subscribe(choice => {
      this.showBanner = choice === null;
    });
    const stored = this.analyticsConsent.choice;
    if (stored !== null) {
      this.consentChanged.emit(stored);
    }
  }

  ngOnDestroy(): void {
    this.choiceSubscription?.unsubscribe();
  }

  accept(): void {
    this.analyticsConsent.answerNotice('accepted');
    this.consentChanged.emit('accepted');
  }

  reject(): void {
    this.analyticsConsent.answerNotice('rejected');
    this.consentChanged.emit('rejected');
  }

  static getConsent(): CookieConsentStatus {
    try {
      if (typeof localStorage === 'undefined') return null;
      const value = localStorage.getItem(COOKIE_CONSENT_KEY);
      if (value === 'accepted' || value === 'rejected') return value;
    } catch {
      // Storage is blocked: treated as not answered
    }
    return null;
  }
}
