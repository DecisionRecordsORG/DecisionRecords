import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

const COOKIE_CONSENT_KEY = 'dr_cookie_consent';

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
          <button mat-stroked-button (click)="reject()">Reject</button>
          <button mat-raised-button color="primary" (click)="accept()">Accept</button>
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
export class CookieConsentComponent implements OnInit {
  @Output() consentChanged = new EventEmitter<CookieConsentStatus>();

  showBanner = false;

  ngOnInit(): void {
    const stored = this.getStoredConsent();
    if (stored === null) {
      this.showBanner = true;
    } else {
      this.consentChanged.emit(stored);
    }
  }

  accept(): void {
    this.setConsent('accepted');
    this.showBanner = false;
    this.consentChanged.emit('accepted');
  }

  reject(): void {
    this.setConsent('rejected');
    this.showBanner = false;
    this.consentChanged.emit('rejected');
  }

  static getConsent(): CookieConsentStatus {
    if (typeof localStorage === 'undefined') return null;
    const value = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (value === 'accepted' || value === 'rejected') return value;
    return null;
  }

  private getStoredConsent(): CookieConsentStatus {
    return CookieConsentComponent.getConsent();
  }

  private setConsent(status: 'accepted' | 'rejected'): void {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(COOKIE_CONSENT_KEY, status);
    }
  }
}
