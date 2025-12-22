import { Component, TemplateRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDialogModule, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-site-footer',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    MatDialogModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule
  ],
  template: `
    <footer class="site-footer">
      <div class="footer-container">
        <div class="footer-grid">
          <div class="footer-mission-col">
            <div class="footer-brand">
              <img src="/assets/decision-records-logo-official.svg" alt="Decision Records" class="footer-logo">
              <span class="footer-brand-text">Decision Records</span>
            </div>
            <p class="footer-mission">
              An open source initiative to make decision-making
              transparent, durable, and reusable across organisations.
            </p>
            <small class="footer-copyright">&copy; {{ currentYear }} DecisionRecords.org</small>
          </div>
          <div class="footer-resources-col">
            <h4>Resources</h4>
            <nav class="footer-legal-links">
              <a routerLink="/solutions">Solutions</a>
              <a routerLink="/integrations">Integrations</a>
              <a routerLink="/blog">Blog</a>
              <a routerLink="/faq">FAQ</a>
              <a routerLink="/about">About</a>
            </nav>
          </div>
          <div class="footer-legal-col">
            <h4>Legal</h4>
            <nav class="footer-legal-links">
              <a routerLink="/terms">Terms of Service</a>
              <a routerLink="/security">Security</a>
              <a routerLink="/dpa">Data Processing</a>
              <a routerLink="/sla">SLA</a>
            </nav>
          </div>
          <div class="footer-support-col">
            <h4>Get in Touch</h4>
            <p class="footer-support-text">Interested in our cloud service or have questions?</p>
            <button mat-stroked-button class="sponsorship-button" (click)="openContactDialog()">
              <mat-icon>mail</mat-icon>
              Contact Us
            </button>
          </div>
        </div>
      </div>
    </footer>

    <!-- Contact Dialog Template -->
    <ng-template #contactDialog>
      <div class="contact-dialog">
        <button mat-icon-button class="dialog-close" (click)="closeContactDialog()">
          <mat-icon>close</mat-icon>
        </button>

        <div class="contact-header">
          <mat-icon class="dialog-icon">mail</mat-icon>
          <h2>Contact Us</h2>
          <p>Have questions? We'd love to hear from you.</p>
        </div>

        @if (!contactSubmitted) {
          <form [formGroup]="contactForm" (ngSubmit)="submitContact()" class="contact-form">
            <mat-form-field appearance="outline">
              <mat-label>Your Name</mat-label>
              <input matInput formControlName="name" placeholder="John Doe">
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Email Address</mat-label>
              <input matInput type="email" formControlName="email" placeholder="you@company.com">
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Message</mat-label>
              <textarea matInput formControlName="message" rows="4" placeholder="How can we help?"></textarea>
            </mat-form-field>

            <button mat-raised-button type="submit" class="submit-button"
                    [disabled]="!contactForm.valid || contactSubmitting">
              @if (contactSubmitting) {
                <mat-spinner diameter="20"></mat-spinner>
              } @else {
                Send Message
              }
            </button>
          </form>
        } @else {
          <div class="contact-success">
            <mat-icon>check_circle</mat-icon>
            <h3>Message Sent!</h3>
            <p>Thank you for reaching out. We'll get back to you soon.</p>
          </div>
        }
      </div>
    </ng-template>
  `,
  styles: [`
    .site-footer {
      background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
      color: #94a3b8;
      padding: 64px 24px 48px;
    }

    .footer-container {
      max-width: 1200px;
      margin: 0 auto;
    }

    .footer-grid {
      display: grid;
      grid-template-columns: 2fr 1fr 1fr 1.5fr;
      gap: 32px;
      align-items: start;
      text-align: left;
    }

    .footer-brand {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 16px;
    }

    .footer-logo {
      height: 28px;
      width: auto;
    }

    .footer-brand-text {
      font-size: 1.1rem;
      font-weight: 600;
      color: #e2e8f0;
    }

    .footer-mission {
      font-size: 0.9rem;
      line-height: 1.6;
      margin: 0 0 16px;
      text-align: left;
    }

    .footer-copyright {
      color: #64748b;
    }

    .footer-resources-col h4,
    .footer-legal-col h4 {
      color: #e2e8f0;
      margin: 0 0 12px;
      font-size: 1rem;
      font-weight: 600;
    }

    .footer-legal-links {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .footer-legal-links a {
      color: #94a3b8;
      text-decoration: none;
      font-size: 0.9rem;
      transition: color 0.2s;
    }

    .footer-legal-links a:hover {
      color: #93c5fd;
    }

    .footer-support-col {
      background: rgba(255, 255, 255, 0.05);
      padding: 24px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.1);
    }

    .footer-support-col h4 {
      color: #e2e8f0;
      margin: 0 0 8px;
      font-size: 1rem;
      font-weight: 600;
    }

    .footer-support-text {
      font-size: 0.85rem;
      margin: 0 0 16px;
      line-height: 1.5;
    }

    .sponsorship-button {
      width: 100%;
      border-color: rgba(255, 255, 255, 0.3) !important;
      color: #e2e8f0 !important;
    }

    .sponsorship-button:hover {
      background: rgba(255, 255, 255, 0.1) !important;
    }

    .sponsorship-button mat-icon {
      margin-right: 8px;
    }

    /* Contact Dialog */
    .contact-dialog {
      padding: 32px;
      max-width: 400px;
      position: relative;
    }

    .dialog-close {
      position: absolute;
      top: 8px;
      right: 8px;
      color: #64748b;
    }

    .contact-header {
      text-align: center;
      margin-bottom: 24px;
    }

    .dialog-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #2563eb;
      margin-bottom: 16px;
    }

    .contact-header h2 {
      margin: 0 0 8px;
      font-size: 1.5rem;
      color: #0f172a;
    }

    .contact-header p {
      margin: 0;
      color: #64748b;
    }

    .contact-form {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .contact-form mat-form-field {
      width: 100%;
    }

    .submit-button {
      background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%) !important;
      color: white !important;
      padding: 12px 24px !important;
      font-weight: 500 !important;
    }

    .contact-success {
      text-align: center;
      padding: 24px 0;
    }

    .contact-success mat-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #10b981;
      margin-bottom: 16px;
    }

    .contact-success h3 {
      margin: 0 0 8px;
      color: #0f172a;
    }

    .contact-success p {
      margin: 0;
      color: #64748b;
    }

    @media (max-width: 900px) {
      .footer-grid {
        grid-template-columns: 1fr 1fr;
        gap: 32px;
      }

      .footer-mission-col {
        grid-column: 1 / -1;
        text-align: center;
      }

      .footer-mission {
        text-align: center;
      }
    }

    @media (max-width: 600px) {
      .site-footer {
        padding: 48px 20px 40px;
      }

      .footer-grid {
        grid-template-columns: 1fr;
        gap: 32px;
        text-align: center;
      }

      .footer-brand {
        justify-content: center;
      }

      .footer-mission {
        text-align: center;
      }

      .footer-legal-links {
        align-items: center;
      }
    }
  `]
})
export class SiteFooterComponent {
  @ViewChild('contactDialog') contactDialogTemplate!: TemplateRef<any>;

  currentYear = new Date().getFullYear();
  contactDialogRef: MatDialogRef<any> | null = null;
  contactForm: FormGroup;
  contactSubmitting = false;
  contactSubmitted = false;

  constructor(
    private dialog: MatDialog,
    private fb: FormBuilder,
    private http: HttpClient
  ) {
    this.contactForm = this.fb.group({
      name: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      message: ['', Validators.required]
    });
  }

  openContactDialog(): void {
    this.contactSubmitted = false;
    this.contactForm.reset();
    this.contactDialogRef = this.dialog.open(this.contactDialogTemplate, {
      panelClass: 'contact-dialog-panel',
      maxWidth: '90vw'
    });
  }

  closeContactDialog(): void {
    this.contactDialogRef?.close();
  }

  submitContact(): void {
    if (!this.contactForm.valid) return;

    this.contactSubmitting = true;
    const formData = this.contactForm.value;

    this.http.post('/api/contact', formData).subscribe({
      next: () => {
        this.contactSubmitting = false;
        this.contactSubmitted = true;
      },
      error: () => {
        this.contactSubmitting = false;
        this.contactSubmitted = true; // Still show success to user
      }
    });
  }
}
