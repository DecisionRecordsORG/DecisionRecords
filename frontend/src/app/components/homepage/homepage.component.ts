import { Component, OnInit, TemplateRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterModule, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialogModule, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { TenantStatus, EmailVerificationResponse } from '../../models/decision.model';
import { AuthService } from '../../services/auth.service';

type ViewState = 'email' | 'signup' | 'verification_sent' | 'access_request' | 'join_organization' | 'account_created';

@Component({
  selector: 'app-homepage',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatDialogModule,
    MatSelectModule,
    MatCheckboxModule
  ],
  template: `
    <div class="homepage">
      <!-- Hero Section -->
      <section class="hero">
        <div class="hero-container">
          <div class="hero-content-centered">
            <div class="hero-logo-container">
              <img src="/assets/decision-records-logo-white.svg" alt="Decision Records" class="hero-logo">
            </div>
            <h1><span class="typewriter-text">{{ displayedDecisionType }}</span> <span class="highlight">Records</span></h1>
            <p class="hero-tagline">
              Long-term decision memory for organisations
            </p>
            <p class="hero-subtitle">
              Organisations make decisions every day. Most are forgotten. The important ones deserve better.
            </p>
            <div class="hero-cta">
              <button mat-raised-button class="cta-button" (click)="openGetStartedDialog()">
                <span>Get Started. It's FREE!</span>
                <mat-icon>arrow_forward</mat-icon>
              </button>
              <button mat-stroked-button class="cta-button-secondary" (click)="openSignInDialog()">
                <mat-icon>login</mat-icon>
                <span>Sign In</span>
              </button>
            </div>

            <!-- Limited Preview Notice -->
            <div class="preview-notice">
              <div class="preview-badge">
                <mat-icon>new_releases</mat-icon>
                <span>Limited Preview</span>
              </div>
              <p class="preview-text">
                Free for early users while we stabilise features and grow the community.
              </p>
            </div>
          </div>

          <!-- Screenshot inside hero - glass pane with cutoff at section bottom -->
          <div class="hero-screenshot-wrapper">
            <div class="hero-screenshot-glass">
              <div class="browser-frame">
                <div class="browser-header">
                  <div class="browser-dots">
                    <span class="dot red"></span>
                    <span class="dot yellow"></span>
                    <span class="dot green"></span>
                  </div>
                  <div class="browser-address">
                    <span>decisionrecords.org/brandnewcorp.com</span>
                  </div>
                </div>
                <div class="browser-content">
                  <img src="/assets/homepage-decisions-dash.png" alt="Decision Records Dashboard" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Get Started Dialog Template -->
      <ng-template #getStartedDialog>
        <div class="dialog-container">
          <button mat-icon-button class="dialog-close" (click)="closeDialog()">
            <mat-icon>close</mat-icon>
          </button>
          <div class="dialog-header">
            <h2 mat-dialog-title>
              @if (currentView === 'verification_sent') {
                Check Your Email
              } @else if (currentView === 'access_request') {
                Request Access
              } @else if (currentView === 'join_organization') {
                Join Your Organization
              } @else if (currentView === 'account_created') {
                Account Created
              } @else if (isSignInMode) {
                Welcome Back
              } @else {
                Get Started
              }
            </h2>
            <p class="dialog-subtitle">
              @if (currentView === 'email') {
                @if (isSignInMode) {
                  Enter your work email to sign in to your account
                } @else {
                  Enter your work email to sign up or sign in
                }
              } @else if (currentView === 'signup') {
                Create your account
              } @else if (currentView === 'verification_sent') {
                We've sent you a verification link
              } @else if (currentView === 'access_request') {
                Request admin approval to join your organization
              } @else if (currentView === 'join_organization') {
                Verify your email to join your organization
              } @else if (currentView === 'account_created') {
                Check your email to complete setup
              }
            </p>
          </div>

          <mat-dialog-content>
            @if (error) {
              <div class="error-message">{{ error }}</div>
            }

            @if (success) {
              <div class="success-message">{{ success }}</div>
            }

            <!-- Email Entry View -->
            @if (currentView === 'email') {
              <form [formGroup]="emailForm" (ngSubmit)="checkEmail()">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Work Email</mat-label>
                  <input matInput formControlName="email" type="email" placeholder="you@company.com">
                  <mat-icon matPrefix>email</mat-icon>
                  <mat-hint>We'll use your email domain to set up your organization</mat-hint>
                </mat-form-field>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="emailForm.invalid || isLoading" class="full-width submit-btn">
                  <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                  <span *ngIf="!isLoading">Continue</span>
                  <mat-icon *ngIf="!isLoading">arrow_forward</mat-icon>
                </button>
              </form>

              <!-- Social Sign-in Options -->
              @if (slackOidcEnabled || googleOauthEnabled) {
                <div class="social-divider">
                  <span>or</span>
                </div>
                @if (slackOidcEnabled) {
                  <button mat-stroked-button class="slack-signin-btn full-width" (click)="signInWithSlack()">
                    <img src="/assets/slack-logo.svg" alt="Slack" class="slack-logo">
                    <span>Sign in with Slack</span>
                  </button>
                }
                @if (googleOauthEnabled) {
                  <button mat-stroked-button class="google-signin-btn full-width" (click)="signInWithGoogle()">
                    <img src="/assets/google-logo.svg" alt="Google" class="google-logo">
                    <span>Sign in with Google</span>
                  </button>
                }
              }
            }

            <!-- Signup View (first user for domain) -->
            @if (currentView === 'signup') {
              <div class="tenant-info">
                <mat-icon>domain</mat-icon>
                <span>Setting up <strong>{{ tenantDomain }}</strong></span>
              </div>

              <!-- Limited Preview Info Card -->
              <div class="preview-info-card">
                <div class="preview-info-header">
                  <mat-icon>celebration</mat-icon>
                  <span>Limited Preview</span>
                </div>
                <ul class="preview-features">
                  <li><mat-icon>group</mat-icon> Up to 5 users</li>
                  <li><mat-icon>check_circle</mat-icon> All features</li>
                  <li><mat-icon>lock_open</mat-icon> Free to use</li>
                  <li><mat-icon>verified</mat-icon> Your data forever</li>
                </ul>
                <p class="preview-reach-out">
                  Need more users? <a href="javascript:void(0)" (click)="closeDialog(); openSponsorshipDialog()">Get in touch</a>
                </p>
              </div>

              <form [formGroup]="signupForm" (ngSubmit)="sendVerification()">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Email</mat-label>
                  <input matInput formControlName="email" type="email" readonly>
                  <mat-icon matPrefix>email</mat-icon>
                </mat-form-field>

                <div class="name-row">
                  <mat-form-field appearance="outline" class="half-width">
                    <mat-label>First Name</mat-label>
                    <input matInput formControlName="first_name" placeholder="First name">
                    <mat-icon matPrefix>person</mat-icon>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="half-width">
                    <mat-label>Last Name</mat-label>
                    <input matInput formControlName="last_name" placeholder="Last name">
                  </mat-form-field>
                </div>

                @if (tenantStatus?.email_verification_required === false && usePasswordSignup) {
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Password</mat-label>
                    <input matInput formControlName="password" type="password" placeholder="Min 8 characters">
                    <mat-icon matPrefix>lock</mat-icon>
                  </mat-form-field>
                }

                <p class="info-text">
                  <mat-icon>info</mat-icon>
                  <span>
                    You're helping bootstrap a shared space for <strong>{{ tenantDomain }}</strong>. Others from your organisation can join automatically.
                    @if (tenantStatus?.email_verification_required === false) {
                      @if (!usePasswordSignup) {
                        After creating your account, you'll set up a passkey for secure passwordless login.
                      } @else {
                        Your account will be created with password login.
                      }
                    } @else {
                      We'll send a verification email to confirm your identity.
                    }
                  </span>
                </p>

                <div class="tos-checkbox">
                  <mat-checkbox formControlName="acceptTos" color="primary">
                    I agree to the <a routerLink="/terms" target="_blank">Terms of Service</a> and <a routerLink="/dpa" target="_blank">Data Processing Agreement</a>
                  </mat-checkbox>
                </div>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="signupForm.invalid || isLoading || (tenantStatus?.email_verification_required === false && usePasswordSignup && signupForm.get('password')?.value?.length < 8)" class="full-width submit-btn">
                  <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                  <ng-container *ngIf="!isLoading">
                    <mat-icon *ngIf="tenantStatus?.email_verification_required === false">person_add</mat-icon>
                    <mat-icon *ngIf="tenantStatus?.email_verification_required !== false">mail</mat-icon>
                    <span *ngIf="tenantStatus?.email_verification_required === false">Create Account</span>
                    <span *ngIf="tenantStatus?.email_verification_required !== false">Send Verification Email</span>
                  </ng-container>
                </button>

                @if (tenantStatus?.email_verification_required === false) {
                  <button mat-button type="button" class="password-toggle" (click)="togglePasswordSignup()">
                    <mat-icon *ngIf="!usePasswordSignup">password</mat-icon>
                    <mat-icon *ngIf="usePasswordSignup">fingerprint</mat-icon>
                    <span *ngIf="!usePasswordSignup">I prefer to use a password</span>
                    <span *ngIf="usePasswordSignup">Use passkey instead (recommended)</span>
                  </button>
                }
              </form>

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Back
              </button>
            }

            <!-- Verification Email Sent View -->
            @if (currentView === 'verification_sent') {
              <div class="verification-sent">
                <div class="verification-icon">
                  <mat-icon>mark_email_read</mat-icon>
                </div>
                <p>
                  We've sent a verification link to <strong>{{ verificationEmail }}</strong>
                </p>
                <p class="small-text">
                  Click the link in your email to verify your identity. The link expires in 24 hours.
                </p>

                <div class="verification-actions">
                  <button mat-stroked-button (click)="resendVerification()" [disabled]="isLoading || resendCooldown > 0">
                    <span *ngIf="resendCooldown > 0">Resend in {{ resendCooldown }}s</span>
                    <mat-spinner diameter="16" *ngIf="resendCooldown === 0 && isLoading"></mat-spinner>
                    <mat-icon *ngIf="resendCooldown === 0 && !isLoading">refresh</mat-icon>
                    <span *ngIf="resendCooldown === 0 && !isLoading">Resend Email</span>
                  </button>
                </div>
              </div>

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Try Different Email
              </button>
            }

            <!-- Access Request View -->
            @if (currentView === 'access_request') {
              <div class="tenant-info">
                <mat-icon>business</mat-icon>
                <span><strong>{{ tenantDomain }}</strong> already has users</span>
              </div>

              <form [formGroup]="accessRequestForm" (ngSubmit)="sendAccessRequestVerification()">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Email</mat-label>
                  <input matInput formControlName="email" type="email" readonly>
                  <mat-icon matPrefix>email</mat-icon>
                </mat-form-field>

                <div class="name-row">
                  <mat-form-field appearance="outline" class="half-width">
                    <mat-label>First Name</mat-label>
                    <input matInput formControlName="first_name" placeholder="First name">
                    <mat-icon matPrefix>person</mat-icon>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="half-width">
                    <mat-label>Last Name</mat-label>
                    <input matInput formControlName="last_name" placeholder="Last name">
                  </mat-form-field>
                </div>

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Reason for Access (Optional)</mat-label>
                  <textarea matInput formControlName="reason" placeholder="Why do you need access?" rows="2"></textarea>
                  <mat-icon matPrefix>note</mat-icon>
                </mat-form-field>

                <p class="info-text warning">
                  <mat-icon>security</mat-icon>
                  <span>Your organization admin must approve your access request.</span>
                </p>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="accessRequestForm.invalid || isLoading" class="full-width submit-btn">
                  <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                  <mat-icon *ngIf="!isLoading">mail</mat-icon>
                  <span *ngIf="!isLoading">Verify & Request Access</span>
                </button>
              </form>

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Back
              </button>
            }

            <!-- Join Organization View -->
            @if (currentView === 'join_organization') {
              <div class="tenant-info">
                <mat-icon>business</mat-icon>
                <span>Join <strong>{{ tenantDomain }}</strong></span>
              </div>

              <form [formGroup]="accessRequestForm" (ngSubmit)="submitJoinOrganization()">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Email</mat-label>
                  <input matInput formControlName="email" type="email" readonly>
                  <mat-icon matPrefix>email</mat-icon>
                </mat-form-field>

                <div class="name-row">
                  <mat-form-field appearance="outline" class="half-width">
                    <mat-label>First Name</mat-label>
                    <input matInput formControlName="first_name" placeholder="First name">
                    <mat-icon matPrefix>person</mat-icon>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="half-width">
                    <mat-label>Last Name</mat-label>
                    <input matInput formControlName="last_name" placeholder="Last name">
                  </mat-form-field>
                </div>

                <p class="info-text">
                  <mat-icon>verified_user</mat-icon>
                  <span>We'll verify your email and create your account.</span>
                </p>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="accessRequestForm.get('email')?.invalid || accessRequestForm.get('first_name')?.invalid || accessRequestForm.get('last_name')?.invalid || isLoading" class="full-width submit-btn">
                  <mat-spinner diameter="20" *ngIf="isLoading"></mat-spinner>
                  <mat-icon *ngIf="!isLoading">person_add</mat-icon>
                  <span *ngIf="!isLoading">Join Organization</span>
                </button>
              </form>

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Back
              </button>
            }

            <!-- Account Created View -->
            @if (currentView === 'account_created') {
              <div class="verification-sent">
                <div class="verification-icon success">
                  <mat-icon>check_circle</mat-icon>
                </div>
                <p>
                  Your account for <strong>{{ tenantDomain }}</strong> has been created!
                </p>
                <p class="small-text">
                  Check your email at <strong>{{ verificationEmail }}</strong> to complete setup.
                </p>
              </div>

              <button mat-button class="back-button" (click)="goBack()">
                <mat-icon>arrow_back</mat-icon>
                Start Over
              </button>
            }
          </mat-dialog-content>
        </div>
      </ng-template>

      <!-- Problem Statement -->
      <section class="section problem-section">
        <div class="container">
          <div class="problem-layout">
            <div class="problem-illustration">
              <img src="/assets/doubt-blue.svg" alt="Decisions without memory" class="doubt-svg" />
            </div>
            <div class="problem-content">
              <h2>Decisions Without Memory</h2>
              <p class="problem-lead">
                Every organisation runs on decisions. But most are never written down. When questions arise later — "Why did we do this?" — the answers have walked out the door.
              </p>
              <ul class="problem-list">
                <li>Agreed in meetings, lost in inboxes</li>
                <li>Made for reasons that no longer apply</li>
                <li>Repeated because no one remembers the last attempt</li>
              </ul>
              <p class="problem-conclusion">Over time, organisations don't just lose documents — they lose judgement.</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Sample Decision Records Carousel -->
      <section class="section examples-section">
        <div class="container">
          <h2>Simple format. Any decision.</h2>
          <p class="section-intro">
            Context. Decision. Consequences. That's it. Here's what real records look like:
          </p>

          <div class="carousel-container">
            <button class="carousel-btn prev" (click)="prevSlide()" [disabled]="currentSlide === 0">
              <mat-icon>chevron_left</mat-icon>
            </button>

            <div class="carousel-track" [style.transform]="'translateX(-' + (currentSlide * 50) + '%)'">
              <!-- Decision Record 1: Technology -->
              <div class="decision-record-card">
                <div class="card-inner">
                  <span class="example-ribbon">Example</span>
                  <div class="card-header">
                    <div class="card-meta">
                      <span class="card-category">Technology</span>
                      <span class="card-id">DR-042</span>
                    </div>
                    <span class="card-status accepted">Accepted</span>
                  </div>
                  <h3>Use PostgreSQL as the primary database</h3>
                  <div class="card-section">
                    <h4>Context</h4>
                    <p>We need a database that can handle our expected growth over the next five years while keeping operational complexity manageable for a small team.</p>
                  </div>
                  <div class="card-section">
                    <h4>Decision</h4>
                    <p>We will use PostgreSQL for all structured data storage. Cloud-managed options like Azure Database for PostgreSQL or AWS RDS will be preferred.</p>
                  </div>
                  <div class="card-footer">
                    <div class="card-author">
                      <div class="author-avatar" style="background: linear-gradient(135deg, #6366f1, #8b5cf6);">MK</div>
                      <div class="author-info">
                        <span class="author-name">Marcus Kim</span>
                        <span class="author-date">15 Nov 2024</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Decision Record 2: Operations -->
              <div class="decision-record-card">
                <div class="card-inner">
                  <span class="example-ribbon">Example</span>
                  <div class="card-header">
                    <div class="card-meta">
                      <span class="card-category">Operations</span>
                      <span class="card-id">DR-038</span>
                    </div>
                    <span class="card-status accepted">Accepted</span>
                  </div>
                  <h3>Shift to four-day work week for support teams</h3>
                  <div class="card-section">
                    <h4>Context</h4>
                    <p>Support team burnout has increased over the past year. Exit interviews cite work-life balance as a primary concern.</p>
                  </div>
                  <div class="card-section">
                    <h4>Decision</h4>
                    <p>Support staff will work four ten-hour days instead of five eight-hour days. Teams will stagger schedules to maintain coverage.</p>
                  </div>
                  <div class="card-footer">
                    <div class="card-author">
                      <div class="author-avatar" style="background: linear-gradient(135deg, #10b981, #059669);">SR</div>
                      <div class="author-info">
                        <span class="author-name">Sarah Roberts</span>
                        <span class="author-date">3 Oct 2024</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Decision Record 3: Retail -->
              <div class="decision-record-card">
                <div class="card-inner">
                  <span class="example-ribbon">Example</span>
                  <div class="card-header">
                    <div class="card-meta">
                      <span class="card-category">Retail</span>
                      <span class="card-id">DR-019</span>
                    </div>
                    <span class="card-status superseded">Superseded</span>
                  </div>
                  <h3>Accept returns without receipt for loyalty members</h3>
                  <div class="card-section">
                    <h4>Context</h4>
                    <p>Loyalty members account for 70% of revenue but cite our strict return policy as a top frustration.</p>
                  </div>
                  <div class="card-section">
                    <h4>Decision</h4>
                    <p>Loyalty members can return items without a receipt within 60 days. The system will match purchases to their account.</p>
                  </div>
                  <div class="card-footer">
                    <div class="card-author">
                      <div class="author-avatar" style="background: linear-gradient(135deg, #f59e0b, #d97706);">JT</div>
                      <div class="author-info">
                        <span class="author-name">James Thompson</span>
                        <span class="author-date">22 Jun 2024</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Decision Record 4: Governance -->
              <div class="decision-record-card">
                <div class="card-inner">
                  <span class="example-ribbon">Example</span>
                  <div class="card-header">
                    <div class="card-meta">
                      <span class="card-category">Governance</span>
                      <span class="card-id">DR-051</span>
                    </div>
                    <span class="card-status accepted">Accepted</span>
                  </div>
                  <h3>Require two approvals for vendor contracts over £50k</h3>
                  <div class="card-section">
                    <h4>Context</h4>
                    <p>Recent audit flagged inconsistent approval processes for vendor contracts. Some high-value agreements had only one approver.</p>
                  </div>
                  <div class="card-section">
                    <h4>Decision</h4>
                    <p>All vendor contracts exceeding £50,000 require sign-off from both the budget owner and the procurement lead.</p>
                  </div>
                  <div class="card-footer">
                    <div class="card-author">
                      <div class="author-avatar" style="background: linear-gradient(135deg, #ec4899, #db2777);">LP</div>
                      <div class="author-info">
                        <span class="author-name">Lisa Patel</span>
                        <span class="author-date">8 Dec 2024</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <button class="carousel-btn next" (click)="nextSlide()" [disabled]="currentSlide >= 2">
              <mat-icon>chevron_right</mat-icon>
            </button>
          </div>

          <div class="carousel-dots">
            <span class="dot" [class.active]="currentSlide === 0" (click)="goToSlide(0)"></span>
            <span class="dot" [class.active]="currentSlide === 1" (click)="goToSlide(1)"></span>
            <span class="dot" [class.active]="currentSlide === 2" (click)="goToSlide(2)"></span>
          </div>
        </div>
      </section>

      <!-- In Practice -->
      <section class="section usage-section">
        <div class="container">
          <h2>In practice</h2>
          <div class="usage-timeline">
            <div class="usage-item">
              <span class="usage-trigger">After the meeting</span>
              <span class="usage-outcome">One person writes it down before everyone forgets.</span>
            </div>
            <div class="usage-item">
              <span class="usage-trigger">Someone new joins</span>
              <span class="usage-outcome">Three records. Six months of context.</span>
            </div>
            <div class="usage-item">
              <span class="usage-trigger">Priorities shift</span>
              <span class="usage-outcome">Old decisions get marked superseded. The reasoning stays.</span>
            </div>
            <div class="usage-item">
              <span class="usage-trigger">Auditors ask "why"</span>
              <span class="usage-outcome">You show them the record, not a search through emails.</span>
            </div>
          </div>
          <p class="usage-note">Most teams add 2-3 records a month. Enough to matter. Not enough to slow down.</p>
        </div>
      </section>

      <!-- Slack Integration Section -->
      <section class="section slack-section">
        <div class="slack-bg-gradient">
          <div class="container slack-container">
            <div class="slack-content">
              <div class="slack-badge">
                <mat-icon>flash_on</mat-icon>
                <span>New Integration</span>
              </div>
              <h2>Capture decisions where your team already works</h2>
              <p class="slack-tagline">
                Create and manage decision records directly from Slack.
                No context switching. No forgotten conversations.
              </p>
              <div class="slack-features">
                <div class="slack-feature">
                  <mat-icon>bolt</mat-icon>
                  <span>Type <code>/decision</code> to get started</span>
                </div>
                <div class="slack-feature">
                  <mat-icon>touch_app</mat-icon>
                  <span>Create from any message with one click</span>
                </div>
                <div class="slack-feature">
                  <mat-icon>notifications_active</mat-icon>
                  <span>Get notified when decisions change</span>
                </div>
              </div>
              <a href="https://slack.com/apps" target="_blank" class="slack-cta">
                <img src="/assets/slack-logo.svg" alt="Slack" class="slack-logo-btn">
                <span>Add to Slack</span>
              </a>
            </div>
            <div class="slack-visual">
              <img src="/assets/decisionrecords-with-slack-transpatent.png" alt="Decision Records + Slack" class="slack-hero-image">
              <div class="slack-screenshot-wrapper">
                <img src="/assets/slackscreenshot-decisionrecords.png" alt="Create Decision modal in Slack" class="slack-screenshot">
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Security, Trust & Governance -->
      <section class="section trust-section">
        <div class="container">
          <div class="trust-grid">
            <div class="trust-intro">
              <h2>Security, Trust & Governance</h2>
              <p class="trust-statement">
                Decision Records is <strong>open source and independent</strong>. No single organisation owns or controls the platform.
              </p>
              <p class="trust-subtext">
                Your decision records may contain sensitive strategic information. We take security seriously and operate with full transparency.
              </p>
            </div>
            <div class="trust-features">
              <div class="trust-item">
                <mat-icon>apartment</mat-icon>
                <div>
                  <strong>Tenant Isolation</strong>
                  <span>Complete data separation between organizations</span>
                </div>
              </div>
              <div class="trust-item">
                <mat-icon>lock</mat-icon>
                <div>
                  <strong>Encryption at Rest</strong>
                  <span>All data encrypted using industry standards</span>
                </div>
              </div>
              <div class="trust-item">
                <mat-icon>fingerprint</mat-icon>
                <div>
                  <strong>Passwordless Auth</strong>
                  <span>WebAuthn/Passkeys for phishing-resistant login</span>
                </div>
              </div>
              <div class="trust-item">
                <img src="/assets/european-union-europe-svgrepo-com.svg" alt="EU" class="eu-icon" />
                <div>
                  <strong>EU Data Residency</strong>
                  <span>Data stored in European Azure datacenters</span>
                </div>
              </div>
              <div class="trust-item">
                <mat-icon>person</mat-icon>
                <div>
                  <strong>Users own their data</strong>
                  <span>You retain ownership of all decision records and content you create</span>
                </div>
              </div>
              <div class="trust-item">
                <mat-icon>block</mat-icon>
                <div>
                  <strong>No data sales, no advertising</strong>
                  <span>We do not sell user data, analytics, or insights — now or in the future</span>
                </div>
              </div>
              <div class="trust-item">
                <mat-icon>code</mat-icon>
                <div>
                  <strong>Open source, self-hostable</strong>
                  <span>Run the platform on your own infrastructure or use our managed cloud service</span>
                </div>
              </div>
              <div class="trust-item">
                <mat-icon>balance</mat-icon>
                <div>
                  <strong>Neutral by design</strong>
                  <span>Not tied to any vendor, consultancy, framework, or certification scheme</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Who Is This For -->
      <section class="section audience-section">
        <div class="container">
          <div class="audience-header">
            <h2>Sound Familiar?</h2>
            <p class="audience-intro">If any of these resonate, you're in the right place.</p>
          </div>

          <div class="needs-grid">
            <div class="need-card need-card-1">
              <div class="need-icon">
                <mat-icon>help_outline</mat-icon>
              </div>
              <div class="need-content">
                <h3>"Why did we decide this?"</h3>
                <p>Teams tired of rehashing old debates — from boardrooms to project standups.</p>
              </div>
            </div>

            <div class="need-card need-card-2">
              <div class="need-icon">
                <mat-icon>directions_walk</mat-icon>
              </div>
              <div class="need-content">
                <h3>Knowledge walks out the door</h3>
                <p>Organizations losing context when people move on — especially growing teams.</p>
              </div>
            </div>

            <div class="need-card need-card-3">
              <div class="need-icon">
                <mat-icon>description</mat-icon>
              </div>
              <div class="need-content">
                <h3>Decisions need a paper trail</h3>
                <p>Regulated industries and client work requiring audit trails and accountability.</p>
              </div>
            </div>

            <div class="need-card need-card-4">
              <div class="need-icon">
                <mat-icon>public</mat-icon>
              </div>
              <div class="need-content">
                <h3>Alignment across distance</h3>
                <p>Distributed teams and async collaborators staying in sync on what matters.</p>
              </div>
            </div>
          </div>

          <div class="audience-cta">
            <img src="/assets/brain-memory.svg" alt="Connected thinking" class="floating-brain" />
            <p>Decision records give your team a shared memory that outlasts any individual.</p>
          </div>
        </div>
      </section>

      <!-- Footer -->
      <footer class="homepage-footer">
        <div class="container">
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
            <div class="footer-legal-col">
              <h4>Legal</h4>
              <nav class="footer-legal-links">
                <a routerLink="/terms">Terms of Service</a>
                <a routerLink="/security">Security</a>
                <a routerLink="/dpa">Data Processing</a>
                <a routerLink="/sla">SLA</a>
                <a routerLink="/licensing">License Model</a>
              </nav>
            </div>
            <div class="footer-support-col">
              <h4>Get in Touch</h4>
              <p class="footer-support-text">Interested in our cloud service or have questions?</p>
              <button mat-stroked-button class="sponsorship-button" (click)="openSponsorshipDialog()">
                <mat-icon>mail</mat-icon>
                Contact Us
              </button>
            </div>
          </div>
        </div>
      </footer>

      <!-- Sponsorship Dialog Template -->
      <ng-template #sponsorshipDialog>
        <div class="sponsorship-dialog">
          <button mat-icon-button class="dialog-close" (click)="closeSponsorshipDialog()">
            <mat-icon>close</mat-icon>
          </button>

          <div class="sponsorship-header">
            <mat-icon class="dialog-icon">volunteer_activism</mat-icon>
            <h2>Support the Project</h2>
          </div>

          @if (sponsorshipSuccess) {
            <div class="verification-sent">
              <div class="verification-icon success">
                <mat-icon>check_circle</mat-icon>
              </div>
              <p>{{ sponsorshipSuccess }}</p>
            </div>
          } @else {
            <div class="sponsorship-content">
              <div class="sponsorship-text">
                <p>
                  Decision Records is <strong>open source</strong> and can be self-hosted for free.
                  Our managed cloud service offers a hassle-free experience with professional support.
                </p>
                <p>
                  Use this form to <strong>inquire about pricing</strong> for our hosted service,
                  <strong>discuss enterprise features</strong>, or <strong>explore partnership opportunities</strong>.
                </p>
                <p>
                  We'd love to hear from you and will respond directly.
                </p>
              </div>

              <div class="sponsorship-form">
                <form [formGroup]="sponsorshipForm" (ngSubmit)="submitSponsorship()">
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Organisation Name</mat-label>
                    <input matInput formControlName="organisation_name" placeholder="Acme Corporation">
                    <mat-icon matPrefix>business</mat-icon>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Contact Email</mat-label>
                    <input matInput formControlName="contact_email" type="email" placeholder="contact@acme.com">
                    <mat-icon matPrefix>email</mat-icon>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Contact Name</mat-label>
                    <input matInput formControlName="contact_name" placeholder="Jane Smith">
                    <mat-icon matPrefix>person</mat-icon>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Area of Interest</mat-label>
                    <mat-select formControlName="area_of_interest">
                      <mat-option value="">Select an option...</mat-option>
                      <mat-option value="Cloud pricing inquiry">Cloud pricing inquiry</mat-option>
                      <mat-option value="Enterprise features">Enterprise features</mat-option>
                      <mat-option value="Self-hosting support">Self-hosting support</mat-option>
                      <mat-option value="Partnership opportunity">Partnership opportunity</mat-option>
                      <mat-option value="Public sector use">Public sector use</mat-option>
                      <mat-option value="Research / Academia">Research / Academia</mat-option>
                      <mat-option value="Other">Other</mat-option>
                    </mat-select>
                    <mat-icon matPrefix>category</mat-icon>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Message (optional)</mat-label>
                    <textarea matInput formControlName="message" rows="2"
                              placeholder="Tell us about your interest..."></textarea>
                  </mat-form-field>

                  @if (sponsorshipError) {
                    <p class="error-message">{{ sponsorshipError }}</p>
                  }

                  <button mat-raised-button color="primary" type="submit"
                          [disabled]="sponsorshipForm.invalid || sponsorshipLoading" class="full-width submit-btn">
                    <mat-spinner diameter="20" *ngIf="sponsorshipLoading"></mat-spinner>
                    <ng-container *ngIf="!sponsorshipLoading">
                      <mat-icon>send</mat-icon>
                      <span>Submit Inquiry</span>
                    </ng-container>
                  </button>
                </form>
              </div>
            </div>
          }
        </div>
      </ng-template>
    </div>
  `,
  styles: [`
    .homepage {
      min-height: 100vh;
      background: #f8fafc;
      font-family: 'Inter', sans-serif;
    }

    /* Hero Section - Salient rich blue gradient */
    .hero {
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #1e40af 100%);
      color: white;
      padding: 100px 24px 80px;
      position: relative;
      overflow: hidden;
    }

    .hero::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background:
        radial-gradient(ellipse 80% 50% at 20% 20%, rgba(96, 165, 250, 0.3) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 40%, rgba(147, 197, 253, 0.2) 0%, transparent 50%);
      pointer-events: none;
    }

    .hero-container {
      max-width: 1200px;
      margin: 0 auto;
      position: relative;
      z-index: 1;
    }

    .hero-content-centered {
      text-align: center;
      max-width: 1000px;
      margin: 0 auto;
    }

    .hero-content-centered h1 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 4.5rem;
      font-weight: 700;
      margin: 0 0 24px;
      letter-spacing: -0.03em;
      line-height: 1.05;
      color: white;
    }

    .hero-content-centered h1 .highlight {
      color: #93c5fd;
      position: relative;
    }

    .hero-tagline {
      font-family: 'Inter', sans-serif;
      font-size: 1.75rem;
      font-weight: 400;
      margin: 0 0 20px;
      color: #e0f2fe;
      line-height: 1.5;
    }

    .hero-subtitle {
      font-family: 'Inter', sans-serif;
      font-size: 1.25rem;
      color: #bfdbfe;
      line-height: 1.7;
      margin: 0 0 32px;
      max-width: 600px;
      margin-left: auto;
      margin-right: auto;
    }

    /* Typewriter animation */
    .typewriter-text {
      display: inline-block;
      min-width: 200px;
      text-align: right;
    }

    .typewriter-text::after {
      content: '|';
      animation: blink 0.7s infinite;
      margin-left: 2px;
      color: #93c5fd;
    }

    @keyframes blink {
      0%, 50% { opacity: 1; }
      51%, 100% { opacity: 0; }
    }

    .hero-cta {
      display: flex;
      gap: 16px;
      justify-content: center;
      margin-top: 32px;
    }

    .cta-button {
      padding: 14px 32px !important;
      font-size: 16px !important;
      font-weight: 500 !important;
      border-radius: 8px !important;
      background: white !important;
      color: #1e40af !important;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15) !important;
      transition: all 0.2s ease !important;
      min-height: 48px !important;
    }

    .cta-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2) !important;
    }

    .cta-button span,
    .cta-button mat-icon {
      color: #1e40af !important;
    }

    .cta-button-secondary {
      padding: 14px 32px !important;
      font-size: 16px !important;
      font-weight: 500 !important;
      border-radius: 8px !important;
      border-color: rgba(255, 255, 255, 0.4) !important;
      color: white !important;
      min-height: 48px !important;
    }

    .cta-button-secondary:hover {
      background: rgba(255, 255, 255, 0.1) !important;
      border-color: rgba(255, 255, 255, 0.6) !important;
    }

    .cta-button-secondary span,
    .cta-button-secondary mat-icon {
      color: white !important;
    }

    /* Limited Preview Notice - Hero */
    .preview-notice {
      margin-top: 32px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      animation: fadeInUp 0.6s ease-out 0.3s both;
    }

    @keyframes fadeInUp {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .preview-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      background: linear-gradient(135deg, rgba(251, 191, 36, 0.2) 0%, rgba(245, 158, 11, 0.15) 100%);
      border: 1px solid rgba(251, 191, 36, 0.4);
      border-radius: 100px;
      backdrop-filter: blur(8px);
    }

    .preview-badge mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #fbbf24;
    }

    .preview-badge span {
      font-size: 0.85rem;
      font-weight: 600;
      color: #fef3c7;
      letter-spacing: 0.5px;
    }

    .preview-text {
      font-size: 0.9rem;
      color: rgba(191, 219, 254, 0.8);
      margin: 0;
    }

    /* Preview Info Card - Signup Dialog */
    .preview-info-card {
      background: linear-gradient(135deg, #fefce8 0%, #fef9c3 100%);
      border: 1px solid #fde047;
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 20px;
    }

    .preview-info-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
    }

    .preview-info-header mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
      color: #ca8a04;
    }

    .preview-info-header span {
      font-size: 0.9rem;
      font-weight: 600;
      color: #854d0e;
    }

    .preview-features {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .preview-features li {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8rem;
      color: #713f12;
    }

    .preview-features li mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      color: #a16207;
    }

    .preview-reach-out {
      margin: 12px 0 0;
      padding-top: 12px;
      border-top: 1px solid rgba(202, 138, 4, 0.2);
      font-size: 0.8rem;
      color: #92400e;
      text-align: center;
    }

    .preview-reach-out a {
      color: #b45309;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
    }

    .preview-reach-out a:hover {
      text-decoration: underline;
    }

    @media (max-width: 400px) {
      .preview-features {
        grid-template-columns: 1fr;
      }
    }

    .hero-logo-container {
      display: flex;
      justify-content: center;
      margin-bottom: 24px;
    }

    .hero-logo {
      width: 150px;
      height: 150px;
      filter: drop-shadow(0 4px 12px rgba(255, 255, 255, 0.3));
    }

    /* Dialog Styles - Style Guide Aligned */
    .dialog-container {
      padding: 32px 32px 24px;
      min-width: 320px;
      max-width: 420px;
      position: relative;
      font-family: 'Inter', sans-serif;
    }

    @media (max-width: 480px) {
      .dialog-container {
        min-width: auto;
        max-width: 100%;
        padding: 24px 20px 20px;
      }
    }

    .dialog-close {
      position: absolute;
      top: 12px;
      right: 12px;
      color: #94a3b8;
      z-index: 10;
      transition: all 0.2s ease;
    }

    .dialog-close:hover {
      color: #3b82f6;
      background: #eff6ff;
    }

    .dialog-header {
      margin-bottom: 24px;
      padding-right: 32px;
    }

    .dialog-header h2 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
      padding: 0;
      letter-spacing: -0.01em;
    }

    .dialog-subtitle {
      font-family: 'Inter', sans-serif;
      color: #64748b;
      font-size: 0.95rem;
      margin: 0;
      line-height: 1.5;
    }

    ::ng-deep .mat-mdc-dialog-container {
      border-radius: 16px !important;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25) !important;
    }

    ::ng-deep .mat-mdc-dialog-surface {
      padding: 0 !important;
      background: #ffffff !important;
      border: 1px solid #e2e8f0 !important;
    }

    ::ng-deep mat-dialog-content {
      padding: 0 !important;
      margin: 0 !important;
      max-height: none !important;
      overflow: visible !important;
    }

    /* Signup Card - Style Guide */
    .signup-card {
      padding: 32px;
      border-radius: 16px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
      border: 1px solid #e2e8f0;
      font-family: 'Inter', sans-serif;
    }

    mat-card-header {
      margin-bottom: 24px;
    }

    mat-card-title {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      letter-spacing: -0.01em;
    }

    mat-card-subtitle {
      font-family: 'Inter', sans-serif;
      color: #64748b;
      font-size: 0.95rem;
      line-height: 1.5;
    }

    .error-message {
      background-color: #fef2f2;
      color: #ef4444;
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 16px;
      font-size: 14px;
      font-weight: 500;
      border: 1px solid rgba(239, 68, 68, 0.2);
    }

    .success-message {
      background-color: #f0fdf4;
      color: #22c55e;
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 16px;
      font-size: 14px;
      font-weight: 500;
      border: 1px solid rgba(34, 197, 94, 0.2);
    }

    .full-width {
      width: 100%;
    }

    .name-row {
      display: flex;
      gap: 12px;
      width: 100%;
    }

    .half-width {
      flex: 1;
      min-width: 0;
    }

    mat-form-field {
      margin-bottom: 8px;
      font-family: 'Inter', sans-serif;
    }

    ::ng-deep .mat-mdc-form-field .mdc-text-field {
      border-radius: 8px !important;
    }

    ::ng-deep .mat-mdc-form-field .mdc-text-field--outlined .mdc-notched-outline .mdc-notched-outline__leading,
    ::ng-deep .mat-mdc-form-field .mdc-text-field--outlined .mdc-notched-outline .mdc-notched-outline__notch,
    ::ng-deep .mat-mdc-form-field .mdc-text-field--outlined .mdc-notched-outline .mdc-notched-outline__trailing {
      border-color: #e2e8f0 !important;
    }

    ::ng-deep .mat-mdc-form-field.mat-focused .mdc-text-field--outlined .mdc-notched-outline .mdc-notched-outline__leading,
    ::ng-deep .mat-mdc-form-field.mat-focused .mdc-text-field--outlined .mdc-notched-outline .mdc-notched-outline__notch,
    ::ng-deep .mat-mdc-form-field.mat-focused .mdc-text-field--outlined .mdc-notched-outline .mdc-notched-outline__trailing {
      border-color: #3b82f6 !important;
    }

    ::ng-deep .mat-mdc-form-field .mdc-floating-label {
      font-family: 'Inter', sans-serif !important;
    }

    .submit-btn {
      margin-top: 16px;
      padding: 14px 32px;
      font-family: 'Inter', sans-serif;
      font-size: 16px;
      font-weight: 500;
      border-radius: 8px;
      background: #3b82f6 !important;
      letter-spacing: 0;
      color: #ffffff !important;
      min-height: 48px !important;
      box-shadow: 0 4px 14px rgba(59, 130, 246, 0.3);
      transition: all 0.2s ease;
    }

    .submit-btn span,
    .submit-btn mat-icon {
      color: #ffffff !important;
    }

    .submit-btn .mdc-button__label {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }

    ::ng-deep .submit-btn .mdc-button__label {
      display: inline-flex !important;
      align-items: center !important;
      gap: 8px !important;
    }

    .submit-btn:hover {
      background: #2563eb !important;
      box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
      transform: translateY(-2px);
    }

    .submit-btn:disabled {
      background: #94a3b8 !important;
      color: rgba(255, 255, 255, 0.7) !important;
      box-shadow: none;
      transform: none;
    }

    /* Slack Sign-in Button Styles */
    .social-divider {
      display: flex;
      align-items: center;
      gap: 16px;
      margin: 24px 0;
      color: #94a3b8;
      font-family: 'Inter', sans-serif;
      font-size: 13px;
      text-transform: lowercase;
    }

    .social-divider::before,
    .social-divider::after {
      content: '';
      flex: 1;
      height: 1px;
      background: #e2e8f0;
    }

    .slack-signin-btn {
      display: inline-flex !important;
      align-items: center;
      justify-content: center;
      gap: 10px;
      padding: 14px 32px !important;
      border: none !important;
      border-radius: 8px !important;
      background: #4A154B !important;
      color: white !important;
      font-family: 'Inter', sans-serif !important;
      font-weight: 500 !important;
      font-size: 16px !important;
      transition: all 0.2s ease !important;
      height: auto !important;
      min-height: 48px;
      box-shadow: 0 4px 14px rgba(74, 21, 75, 0.25);
    }

    .slack-signin-btn:hover {
      background: #611f69 !important;
      box-shadow: 0 6px 20px rgba(74, 21, 75, 0.35);
      transform: translateY(-2px);
    }

    .slack-signin-btn .slack-logo {
      width: 20px;
      height: 20px;
      flex-shrink: 0;
    }

    .slack-signin-btn span {
      color: white !important;
    }

    ::ng-deep .slack-signin-btn .mdc-button__label {
      display: inline-flex !important;
      align-items: center !important;
      gap: 10px !important;
    }

    /* Google Sign-in Button - follows Google brand guidelines */
    .google-signin-btn {
      display: inline-flex !important;
      align-items: center;
      justify-content: center;
      gap: 10px;
      padding: 14px 32px !important;
      border: 1px solid #e2e8f0 !important;
      border-radius: 8px !important;
      background: white !important;
      color: #334155 !important;
      font-family: 'Inter', sans-serif !important;
      font-weight: 500 !important;
      font-size: 16px !important;
      transition: all 0.2s ease !important;
      height: auto !important;
      min-height: 48px;
      margin-top: 8px;
    }

    .google-signin-btn:hover {
      background: #f8fafc !important;
      border-color: #94a3b8 !important;
      box-shadow: 0 1px 3px rgba(60, 64, 67, 0.15);
    }

    .google-signin-btn .google-logo {
      width: 20px;
      height: 20px;
      flex-shrink: 0;
    }

    .google-signin-btn span {
      color: #3c4043 !important;
    }

    ::ng-deep .google-signin-btn .mdc-button__label {
      display: inline-flex !important;
      align-items: center !important;
      gap: 10px !important;
    }

    .tenant-info {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 16px;
      background: #f1f5f9;
      border-radius: 8px;
      margin-bottom: 20px;
      color: #475569;
      font-size: 14px;
      font-weight: 500;
    }

    .tenant-info mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
      color: #2563eb;
    }

    .info-text {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      font-size: 13px;
      color: #64748b;
      margin: 16px 0;
      padding: 12px 16px;
      background: #f8fafc;
      border-radius: 8px;
      line-height: 1.5;
    }

    .info-text.warning {
      background: #fffbeb;
    }

    .info-text.warning mat-icon {
      color: #d97706;
    }

    .info-text mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #2563eb;
      flex-shrink: 0;
      margin-top: 1px;
    }

    .tos-checkbox {
      margin: 16px 0;
      padding: 12px 16px;
      background: #f8fafc;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
    }

    .tos-checkbox mat-checkbox {
      font-size: 14px;
      color: #475569;
    }

    .tos-checkbox a {
      color: #2563eb;
      text-decoration: none;
      font-weight: 500;
    }

    .tos-checkbox a:hover {
      text-decoration: underline;
    }

    .back-button {
      margin-top: 16px;
      color: #64748b;
      font-weight: 500;
    }

    .password-toggle {
      margin-top: 12px;
      color: #64748b;
      font-size: 14px;
    }

    .verification-sent {
      text-align: center;
      padding: 16px 0;
    }

    .verification-icon mat-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #16a34a;
    }

    .verification-icon.success mat-icon {
      color: #16a34a;
    }

    .verification-sent p {
      margin: 16px 0;
      font-size: 15px;
      color: #334155;
    }

    .small-text {
      font-size: 14px !important;
      color: #64748b;
    }

    .verification-actions {
      margin: 24px 0;
    }

    /* Hero Screenshot - glass pane with cutoff at bottom */
    .hero-screenshot-wrapper {
      max-width: 1100px;
      margin: 24px auto 0;
      padding: 0 24px;
      position: relative;
      z-index: 5;
    }

    .hero-screenshot-glass {
      background: rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-bottom: none;
      border-radius: 20px 20px 0 0;
      padding: 16px;
      padding-bottom: 0;
      box-shadow: 0 30px 80px rgba(0, 0, 0, 0.4);
      transform: translateY(80px);
    }

    .browser-frame {
      border-radius: 16px 16px 0 0;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.1);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-bottom: none;
      box-shadow: 0 0 60px rgba(59, 130, 246, 0.15);
    }

    .browser-header {
      background: rgba(255, 255, 255, 0.15);
      backdrop-filter: blur(8px);
      padding: 12px 16px;
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .browser-dots {
      display: flex;
      gap: 8px;
    }

    .browser-dots .dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }

    .browser-dots .dot.red { background: #ef4444; }
    .browser-dots .dot.yellow { background: #eab308; }
    .browser-dots .dot.green { background: #22c55e; }

    .browser-address {
      flex: 1;
      background: rgba(30, 41, 59, 0.6);
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 13px;
      color: #cbd5e1;
      font-family: monospace;
    }

    .browser-content {
      background: #fff;
    }

    .browser-content img {
      width: 100%;
      display: block;
    }

    /* Sections */
    .section {
      padding: 100px 24px;
    }

    .container {
      max-width: 1100px;
      margin: 0 auto;
    }

    h2 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 2.25rem;
      font-weight: 700;
      color: #0f172a;
      margin: 0 0 16px;
      letter-spacing: -0.02em;
    }

    .section-intro {
      font-size: 1.125rem;
      color: #64748b;
      max-width: 700px;
      margin: 0 auto 48px;
      line-height: 1.7;
      text-align: center;
    }

    /* Problem Section */
    .problem-section {
      background: #f8fafc;
    }

    .problem-layout {
      display: grid;
      grid-template-columns: 1fr 1.2fr;
      gap: 64px;
      align-items: center;
    }

    .problem-illustration {
      display: flex;
      justify-content: center;
      align-items: center;
    }

    .doubt-svg {
      max-width: 240px;
      width: 100%;
      height: auto;
      opacity: 0.9;
    }

    .problem-content {
      text-align: left;
    }

    .problem-content h2 {
      text-align: left;
      margin-bottom: 24px;
    }

    .problem-lead {
      font-size: 1.1rem;
      color: #475569;
      line-height: 1.7;
      margin-bottom: 28px;
    }

    .problem-list {
      list-style: none;
      padding: 0;
      margin: 0 0 28px;
    }

    .problem-list li {
      position: relative;
      padding-left: 24px;
      margin-bottom: 12px;
      color: #64748b;
      font-size: 1rem;
      line-height: 1.5;
    }

    .problem-list li::before {
      content: '';
      position: absolute;
      left: 0;
      top: 10px;
      width: 8px;
      height: 2px;
      background: #94a3b8;
    }

    .problem-conclusion {
      font-size: 1.05rem;
      color: #1e293b;
      font-weight: 500;
      font-style: italic;
      margin: 0;
    }

    /* Examples Section - Decision Records Carousel */
    .examples-section {
      background: linear-gradient(180deg, #eef2ff 0%, #e0e7ff 100%);
      text-align: center;
      border-top: 1px solid #c7d2fe;
      border-bottom: 1px solid #c7d2fe;
    }

    .carousel-container {
      position: relative;
      overflow: hidden;
      margin: 0 auto;
      max-width: 900px;
      padding: 0 50px;
    }

    .carousel-track {
      display: flex;
      transition: transform 0.4s ease-out;
    }

    .decision-record-card {
      flex: 0 0 50%;
      padding: 0 12px;
      box-sizing: border-box;
      text-align: left;
    }

    .card-inner {
      position: relative;
      background: white;
      border-radius: 16px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08), 0 2px 8px rgba(0, 0, 0, 0.04);
      border: 1px solid #e2e8f0;
      transition: all 0.3s ease;
      overflow: hidden;
    }

    .example-ribbon {
      position: absolute;
      top: 12px;
      right: -32px;
      background: linear-gradient(135deg, #6366f1, #4f46e5);
      color: white;
      font-size: 0.7rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 4px 40px;
      transform: rotate(45deg);
      box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
      z-index: 10;
    }

    .card-inner:hover {
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12), 0 4px 12px rgba(0, 0, 0, 0.06);
      transform: translateY(-4px);
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 20px;
      border-bottom: 1px solid #e2e8f0;
      background: #fafbfc;
    }

    .card-meta {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .card-category {
      font-size: 0.75rem;
      font-weight: 600;
      color: #1e40af;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      background: #dbeafe;
      padding: 4px 10px;
      border-radius: 6px;
    }

    .card-id {
      font-size: 0.7rem;
      font-weight: 500;
      color: #94a3b8;
      font-family: monospace;
    }

    .card-status {
      font-size: 0.7rem;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 12px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }

    .card-status.accepted {
      background: #dcfce7;
      color: #166534;
    }

    .card-status.superseded {
      background: #fef3c7;
      color: #92400e;
    }

    .decision-record-card h3 {
      font-size: 1rem;
      font-weight: 600;
      color: #1e293b;
      margin: 0;
      padding: 16px 20px 12px;
      line-height: 1.4;
    }

    .card-section {
      padding: 0 20px 12px;
    }

    .card-section h4 {
      font-size: 0.7rem;
      font-weight: 600;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin: 0 0 6px;
    }

    .card-section p {
      font-size: 0.85rem;
      color: #475569;
      line-height: 1.5;
      margin: 0;
    }

    .card-footer {
      padding: 16px 20px;
      border-top: 1px solid #e2e8f0;
      background: #fafbfc;
    }

    .card-author {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .author-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.5px;
    }

    .author-info {
      display: flex;
      flex-direction: column;
    }

    .author-name {
      font-size: 0.85rem;
      font-weight: 500;
      color: #1e293b;
    }

    .author-date {
      font-size: 0.75rem;
      color: #94a3b8;
    }

    .carousel-btn {
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: white;
      border: 1px solid #e2e8f0;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      cursor: pointer;
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .carousel-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }

    .carousel-btn.prev {
      left: 0;
    }

    .carousel-btn.next {
      right: 0;
    }

    .carousel-btn mat-icon {
      color: #64748b;
    }

    .carousel-dots {
      display: flex;
      justify-content: center;
      gap: 8px;
      margin-top: 24px;
    }

    .carousel-dots .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #cbd5e1;
      cursor: pointer;
      transition: background 0.2s;
    }

    .carousel-dots .dot.active {
      background: #2563eb;
    }

    /* Usage Section */
    .usage-section {
      background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    }

    .usage-section h2 {
      text-align: center;
      margin-bottom: 48px;
    }

    .usage-timeline {
      max-width: 680px;
      margin: 0 auto 48px;
      position: relative;
      padding-left: 0;
    }

    .usage-timeline::before {
      content: '';
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
      top: 12px;
      bottom: 12px;
      width: 1px;
      background: #cbd5e1;
    }

    .usage-item {
      display: flex;
      align-items: baseline;
      padding: 18px 0;
    }

    .usage-trigger {
      width: 50%;
      text-align: right;
      font-weight: 600;
      color: #1e293b;
      font-size: 0.95rem;
      padding-right: 32px;
    }

    .usage-outcome {
      width: 50%;
      color: #64748b;
      font-size: 0.95rem;
      line-height: 1.5;
      padding-left: 32px;
    }

    .usage-note {
      font-size: 1rem;
      color: #475569;
      text-align: center;
      max-width: 600px;
      margin: 0 auto;
      line-height: 1.6;
      font-weight: 500;
    }

    /* Trust Section */
    .trust-section {
      background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
      color: white;
    }

    .trust-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 60px;
      align-items: start;
    }

    .trust-intro h2 {
      color: white;
      margin-bottom: 20px;
    }

    .trust-statement {
      font-size: 1.2rem;
      line-height: 1.6;
      color: rgba(255, 255, 255, 0.95);
      margin-bottom: 16px;
    }

    .trust-subtext {
      font-size: 1rem;
      color: rgba(255, 255, 255, 0.7);
      line-height: 1.6;
    }

    .trust-features {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }

    .trust-item {
      display: flex;
      align-items: flex-start;
      gap: 12px;
    }

    .trust-item mat-icon {
      color: #60a5fa;
      font-size: 22px;
      width: 22px;
      height: 22px;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .trust-item .eu-icon {
      width: 22px;
      height: 22px;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .trust-item div {
      display: flex;
      flex-direction: column;
    }

    .trust-item strong {
      color: white;
      font-size: 0.9rem;
      font-weight: 600;
      margin-bottom: 2px;
    }

    .trust-item span {
      color: rgba(255, 255, 255, 0.6);
      font-size: 0.8rem;
      line-height: 1.4;
    }

    /* Legacy styles kept for compatibility */
    .core-section {
      background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
      color: white;
      position: relative;
    }

    .core-section::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: radial-gradient(ellipse at center, rgba(37, 99, 235, 0.08) 0%, transparent 60%);
      pointer-events: none;
    }

    .core-section h2 {
      color: white;
      text-align: center;
    }

    .core-idea {
      text-align: center;
      max-width: 700px;
      margin: 0 auto;
    }

    .big-statement {
      font-size: 1.5rem;
      margin: 32px 0;
      line-height: 1.6;
      color: #e2e8f0;
    }

    .big-statement strong {
      color: #60a5fa;
    }

    .core-section p {
      color: #94a3b8;
      line-height: 1.7;
      font-size: 1.05rem;
    }

    .core-section blockquote {
      font-size: 1.25rem;
      font-style: italic;
      color: #cbd5e1;
      margin: 40px 0 0;
      padding: 24px 32px;
      border-left: 4px solid #2563eb;
      text-align: left;
      background: rgba(255, 255, 255, 0.05);
      border-radius: 0 8px 8px 0;
    }

    .core-section-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 80px;
      align-items: start;
    }

    .security-commitment {
      text-align: left;
    }

    .security-commitment h2 {
      text-align: left;
      margin-bottom: 16px;
    }

    .security-intro {
      color: #94a3b8;
      font-size: 1rem;
      margin-bottom: 32px;
      line-height: 1.6;
    }

    .security-features {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .security-item {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      padding: 16px 20px;
      background: rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.1);
    }

    .security-item mat-icon {
      font-size: 24px;
      width: 24px;
      height: 24px;
      color: #60a5fa;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .security-item .eu-icon {
      width: 24px;
      height: 24px;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .security-item div {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .security-item strong {
      color: #e2e8f0;
      font-size: 0.95rem;
      font-weight: 600;
    }

    .security-item span {
      color: #94a3b8;
      font-size: 0.85rem;
      line-height: 1.4;
    }

    /* Audience Section */
    .audience-section {
      background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
      padding-bottom: 80px;
    }

    .audience-header {
      text-align: center;
      margin-bottom: 48px;
    }

    .audience-header h2 {
      margin-bottom: 12px;
    }

    .audience-intro {
      font-size: 1.1rem;
      color: #64748b;
    }

    .needs-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      max-width: 900px;
      margin: 0 auto;
    }

    .need-card {
      display: flex;
      align-items: flex-start;
      gap: 20px;
      padding: 28px;
      background: white;
      border-radius: 16px;
      border: 1px solid #e2e8f0;
      transition: all 0.3s ease;
      position: relative;
      overflow: hidden;
    }

    .need-card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 4px;
      height: 100%;
      transition: width 0.3s ease;
    }

    .need-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.1);
    }

    .need-card:hover::before {
      width: 6px;
    }

    .need-card-1::before { background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%); }
    .need-card-2::before { background: linear-gradient(180deg, #8b5cf6 0%, #7c3aed 100%); }
    .need-card-3::before { background: linear-gradient(180deg, #06b6d4 0%, #0891b2 100%); }
    .need-card-4::before { background: linear-gradient(180deg, #10b981 0%, #059669 100%); }

    .need-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .need-card-1 .need-icon { background: #eff6ff; }
    .need-card-2 .need-icon { background: #f5f3ff; }
    .need-card-3 .need-icon { background: #ecfeff; }
    .need-card-4 .need-icon { background: #ecfdf5; }

    .need-card-1 .need-icon mat-icon { color: #2563eb; }
    .need-card-2 .need-icon mat-icon { color: #7c3aed; }
    .need-card-3 .need-icon mat-icon { color: #0891b2; }
    .need-card-4 .need-icon mat-icon { color: #059669; }

    .need-icon mat-icon {
      font-size: 24px;
      width: 24px;
      height: 24px;
    }

    .need-content h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 8px;
      line-height: 1.4;
    }

    .need-content p {
      font-size: 0.95rem;
      color: #64748b;
      line-height: 1.6;
      margin: 0;
    }

    .audience-cta {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 24px;
      margin-top: 48px;
      padding: 32px;
      background: linear-gradient(135deg, #eff6ff 0%, #f5f3ff 100%);
      border-radius: 16px;
      max-width: 700px;
      margin-left: auto;
      margin-right: auto;
    }

    .floating-brain {
      width: 80px;
      height: 80px;
      flex-shrink: 0;
      animation: float 3s ease-in-out infinite;
    }

    @keyframes float {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-8px); }
    }

    .audience-cta p {
      font-size: 1.1rem;
      color: #1e293b;
      line-height: 1.6;
      margin: 0;
      font-weight: 500;
    }

    /* Governance Section */
    .governance-section {
      background: #f8fafc;
      padding-top: 60px;
    }

    .governance-content {
      display: grid;
      grid-template-columns: 1fr 1.5fr;
      gap: 80px;
      align-items: center;
    }

    .governance-illustration {
      display: flex;
      justify-content: center;
      align-items: center;
    }

    .governance-svg {
      width: 100%;
      max-width: 320px;
      height: auto;
      filter: invert(36%) sepia(85%) saturate(1352%) hue-rotate(206deg) brightness(97%) contrast(91%);
      opacity: 0.85;
    }

    .governance-text h2 {
      margin-bottom: 16px;
    }

    .governance-intro {
      font-size: 1.15rem;
      color: #475569;
      line-height: 1.7;
      margin-bottom: 32px;
    }

    .governance-intro strong {
      color: #1e40af;
    }

    .governance-list {
      display: flex;
      flex-direction: column;
      gap: 20px;
      margin-bottom: 32px;
    }

    .governance-item {
      display: flex;
      align-items: flex-start;
      gap: 16px;
    }

    .governance-item mat-icon {
      color: #2563eb;
      font-size: 24px;
      width: 24px;
      height: 24px;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .governance-item div {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .governance-item strong {
      color: #0f172a;
      font-size: 1rem;
      font-weight: 600;
    }

    .governance-item span {
      color: #64748b;
      font-size: 0.95rem;
      line-height: 1.5;
    }

    .governance-goal {
      font-size: 1rem;
      color: #475569;
      line-height: 1.7;
      padding: 20px 24px;
      background: #f8fafc;
      border-left: 4px solid #2563eb;
      border-radius: 0 8px 8px 0;
      font-style: italic;
    }

    /* Slack Integration Section - Inspired by ClickUp */
    .slack-section {
      padding: 0;
      overflow: hidden;
    }

    .slack-bg-gradient {
      /* Match the edge colors of decisionrecords-and-slack.png */
      background: linear-gradient(135deg, #0822B5 0%, #0C3EDC 30%, #1436D9 50%, #1E5CF4 70%, #0A22C7 100%);
      padding: 80px 24px 0;
      position: relative;
      overflow: hidden;
    }

    .slack-bg-gradient::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background:
        radial-gradient(ellipse 70% 50% at 30% 20%, rgba(30, 92, 244, 0.4) 0%, transparent 60%),
        radial-gradient(ellipse 50% 40% at 70% 60%, rgba(20, 54, 217, 0.3) 0%, transparent 50%);
      pointer-events: none;
    }

    .slack-container {
      display: grid;
      grid-template-columns: 1fr 1.2fr;
      gap: 48px;
      align-items: center;
      position: relative;
      z-index: 1;
    }

    .slack-content {
      color: white;
    }

    .slack-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      background: linear-gradient(135deg, rgba(251, 191, 36, 0.25) 0%, rgba(245, 158, 11, 0.2) 100%);
      border: 1px solid rgba(251, 191, 36, 0.5);
      border-radius: 100px;
      backdrop-filter: blur(8px);
      font-size: 0.85rem;
      font-weight: 600;
      color: #fef3c7;
      margin-bottom: 24px;
    }

    .slack-badge mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #fbbf24;
    }

    .slack-content h2 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 2.75rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      line-height: 1.15;
      margin: 0 0 20px;
      color: white;
    }

    .slack-tagline {
      font-family: 'Inter', sans-serif;
      font-size: 1.25rem;
      color: #bfdbfe;
      line-height: 1.6;
      margin: 0 0 32px;
    }

    .slack-features {
      display: flex;
      flex-direction: column;
      gap: 16px;
      margin-bottom: 32px;
    }

    .slack-feature {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 1rem;
      color: #e0f2fe;
    }

    .slack-feature mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
      color: #60a5fa;
    }

    .slack-feature code {
      background: rgba(255, 255, 255, 0.15);
      padding: 2px 8px;
      border-radius: 4px;
      font-family: 'SF Mono', Monaco, monospace;
      font-size: 0.9em;
    }

    .slack-cta {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      padding: 14px 28px;
      background: white;
      color: #1e40af;
      font-weight: 600;
      font-size: 1rem;
      border-radius: 8px;
      text-decoration: none;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
      transition: all 0.2s ease;
    }

    .slack-cta:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    }

    .slack-logo-btn {
      width: 22px;
      height: 22px;
    }

    .slack-visual {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
    }

    .slack-hero-image {
      width: 100%;
      max-width: 480px;
      height: auto;
      margin-bottom: -30px;
      /* No border-radius or shadow - let the image blend naturally with background */
    }

    .slack-screenshot-wrapper {
      position: relative;
      width: 100%;
      max-width: 420px;
      background: rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 20px;
      padding: 16px;
      box-shadow: 0 30px 80px rgba(0, 0, 0, 0.4);
      transform: translateY(80px);
    }

    .slack-screenshot {
      width: 100%;
      height: auto;
      border-radius: 12px;
      display: block;
    }

    /* Footer - Salient dark theme */
    .homepage-footer {
      background: #0f172a;
      color: white;
      padding: 64px 24px;
      text-align: center;
    }

    .footer-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }

    .footer-logo {
      width: 40px;
      height: 40px;
    }

    .footer-brand-text {
      font-size: 1.1rem;
      font-weight: 600;
      color: #e2e8f0;
    }

    .footer-mission {
      max-width: 600px;
      margin: 0 auto 20px;
      color: #94a3b8;
      line-height: 1.7;
      font-size: 1rem;
    }

    .homepage-footer small {
      color: #475569;
    }

    .footer-grid {
      display: grid;
      grid-template-columns: 1.5fr 1fr 1fr;
      gap: 40px;
      align-items: start;
      text-align: left;
    }

    .footer-mission-col .footer-mission {
      margin: 0 0 16px;
      text-align: left;
    }

    .footer-copyright {
      color: #64748b;
    }

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
      color: #94a3b8;
      font-size: 0.9rem;
      line-height: 1.5;
      margin: 0 0 16px;
    }

    .sponsorship-button {
      border-color: rgba(255, 255, 255, 0.3) !important;
      color: #e2e8f0 !important;
      min-height: 48px !important;
      padding: 12px 24px !important;
      border-radius: 8px !important;
    }

    .sponsorship-button:hover {
      background: rgba(255, 255, 255, 0.1) !important;
    }

    .sponsorship-button mat-icon {
      margin-right: 8px;
    }

    /* Dialog icon - Style Guide */
    .dialog-icon {
      color: #3b82f6;
      font-size: 32px;
      width: 32px;
      height: 32px;
    }

    /* Sponsorship Dialog - Two Column Layout - Style Guide */
    .sponsorship-dialog {
      padding: 32px;
      position: relative;
      min-width: 700px;
      max-width: 800px;
      font-family: 'Inter', sans-serif;
    }

    .sponsorship-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
      padding-right: 32px;
    }

    .sponsorship-header h2 {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0;
      letter-spacing: -0.01em;
    }

    .sponsorship-content {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 32px;
    }

    .sponsorship-text {
      padding-right: 16px;
      border-right: 1px solid #e2e8f0;
    }

    .sponsorship-text p {
      font-family: 'Inter', sans-serif;
      color: #334155;
      font-size: 0.95rem;
      line-height: 1.7;
      margin: 0 0 16px;
    }

    .sponsorship-text p:last-child {
      margin-bottom: 0;
    }

    .sponsorship-text strong {
      color: #3b82f6;
      font-weight: 600;
    }

    .sponsorship-form {
      padding-left: 8px;
    }

    .sponsorship-form mat-form-field {
      margin-bottom: 4px;
      font-family: 'Inter', sans-serif;
    }

    @media (max-width: 768px) {
      .sponsorship-dialog {
        min-width: auto;
        max-width: 100%;
        padding: 24px;
      }

      .sponsorship-content {
        grid-template-columns: 1fr;
        gap: 24px;
      }

      .sponsorship-text {
        padding-right: 0;
        border-right: none;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 20px;
      }

      .sponsorship-form {
        padding-left: 0;
      }
    }

    /* Responsive */
    @media (max-width: 900px) {
      .hero-grid {
        grid-template-columns: 1fr;
        gap: 48px;
      }

      .hero-content {
        text-align: center;
      }

      .hero-content h1,
      .hero-content-centered h1 {
        font-size: 3rem;
      }

      .hero-tagline {
        font-size: 1.35rem;
      }

      .decisions-content {
        grid-template-columns: 1fr;
        gap: 48px;
      }

      .core-section-grid {
        grid-template-columns: 1fr;
        gap: 48px;
      }

      .security-commitment h2,
      .core-idea {
        text-align: center;
      }

      .governance-content {
        grid-template-columns: 1fr;
        gap: 48px;
      }

      .governance-illustration {
        order: -1;
      }

      .governance-svg {
        max-width: 240px;
      }

      .footer-grid {
        grid-template-columns: 1fr;
        gap: 32px;
        text-align: center;
      }

      .footer-mission-col .footer-mission {
        text-align: center;
      }

      .footer-legal-links {
        align-items: center;
      }

      .browser-frame {
        margin: 0 -8px;
        border-radius: 12px;
      }

      .usage-timeline {
        max-width: 100%;
      }

      .problem-layout {
        grid-template-columns: 1fr;
        gap: 0;
      }

      .problem-illustration {
        display: none;
      }

      .problem-content {
        text-align: center;
      }

      .problem-content h2 {
        text-align: center;
      }

      .problem-list {
        text-align: left;
        max-width: 400px;
        margin: 0 auto 28px;
      }

      .needs-grid {
        grid-template-columns: 1fr;
        gap: 16px;
      }

      .need-card {
        padding: 24px;
      }

      .audience-cta {
        flex-direction: column;
        text-align: center;
      }

      .slack-container {
        grid-template-columns: 1fr;
        gap: 32px;
        text-align: center;
      }

      .slack-content {
        text-align: center;
      }

      .slack-content h2 {
        font-size: 2rem;
      }

      .slack-badge {
        justify-content: center;
      }

      .slack-features {
        align-items: center;
      }

      .slack-cta {
        justify-content: center;
      }

      .slack-visual {
        order: -1;
      }

      .slack-hero-image {
        max-width: 320px;
        margin-bottom: -20px;
      }

      .slack-screenshot-wrapper {
        max-width: 300px;
        transform: translateY(40px);
      }
    }

    @media (max-width: 600px) {
      .usage-timeline::before {
        display: none;
      }

      .usage-item {
        flex-direction: column;
        gap: 6px;
        padding: 16px 0;
        border-bottom: 1px solid #e2e8f0;
      }

      .usage-item:last-child {
        border-bottom: none;
      }

      .usage-trigger {
        width: 100%;
        text-align: left;
        padding-right: 0;
      }

      .usage-outcome {
        width: 100%;
        padding-left: 0;
      }
      .hero {
        padding: 60px 16px 40px;
      }

      .hero-content-centered h1 {
        font-size: 2.25rem;
      }

      .hero-tagline {
        font-size: 1.15rem;
      }

      .hero-subtitle {
        font-size: 1rem;
      }

      .hero-cta {
        flex-direction: column;
        gap: 12px;
      }

      .cta-button,
      .cta-button-secondary {
        width: 100%;
        justify-content: center;
      }

      .hero-screenshot-wrapper {
        margin: 40px auto 0;
        padding: 0 8px;
      }

      .hero-screenshot-glass {
        transform: translateY(40px);
        padding: 8px;
        padding-bottom: 0;
        border-radius: 12px 12px 0 0;
      }

      .hero-screenshot-wrapper .browser-frame {
        border-radius: 8px 8px 0 0;
      }

      .browser-header {
        padding: 8px 12px;
        gap: 12px;
      }

      .browser-dots .dot {
        width: 8px;
        height: 8px;
      }

      .browser-address {
        padding: 6px 10px;
        font-size: 10px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .screenshot-section {
        padding: 0 16px 80px;
      }

      .section {
        padding: 60px 16px;
      }

      h2 {
        font-size: 1.75rem;
      }

      .hero-content h1 {
        font-size: 2.25rem;
      }

      .need-card {
        padding: 20px;
        gap: 16px;
      }

      .need-icon {
        width: 40px;
        height: 40px;
      }

      .need-content h3 {
        font-size: 1rem;
      }

      .floating-brain {
        width: 60px;
        height: 60px;
      }

      .audience-cta {
        padding: 24px;
      }

      .audience-cta p {
        font-size: 1rem;
      }

      .problem-grid {
        grid-template-columns: 1fr;
      }

      .problem-illustration {
        display: none;
      }

      .problem-content {
        text-align: center;
      }

      .problem-content h2 {
        text-align: center;
      }

      .problem-lead {
        font-size: 1rem;
      }

      .problem-list {
        text-align: left;
        max-width: 100%;
        padding: 0 8px;
      }

      .problem-conclusion {
        font-size: 0.95rem;
      }

      .signup-card {
        padding: 24px;
      }
    }
  `]
})
export class HomepageComponent implements OnInit {
  @ViewChild('getStartedDialog') getStartedDialog!: TemplateRef<any>;
  @ViewChild('sponsorshipDialog') sponsorshipDialogTemplate!: TemplateRef<any>;
  dialogRef: MatDialogRef<any> | null = null;
  sponsorshipDialogRef: MatDialogRef<any> | null = null;

  emailForm: FormGroup;
  signupForm: FormGroup;
  accessRequestForm: FormGroup;
  sponsorshipForm: FormGroup;

  currentView: ViewState = 'email';
  tenantDomain = '';
  tenantStatus: TenantStatus | null = null;
  verificationEmail = '';

  isLoading = false;
  error = '';
  success = '';
  resendCooldown = 0;
  usePasswordSignup = false;
  isSignInMode = false;
  currentYear = new Date().getFullYear();

  // Sponsorship form state
  sponsorshipLoading = false;
  sponsorshipError = '';
  sponsorshipSuccess = '';

  // Slack OIDC state
  slackOidcEnabled = false;

  // Google OAuth state
  googleOauthEnabled = false;

  // Carousel state
  currentSlide = 0;

  // Typewriter animation state
  decisionTypes = [
    'pricing Decision',
    'supplier Decision',
    'policy Decision',
    'technology Decision',
    'architecture Decision',
    'Decision'
  ];
  currentTypeIndex = 0;
  displayedDecisionType = '';
  private typewriterTimeout: ReturnType<typeof setTimeout> | null = null;

  private cooldownInterval: ReturnType<typeof setInterval> | null = null;

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private router: Router,
    private route: ActivatedRoute,
    private authService: AuthService,
    private dialog: MatDialog
  ) {
    this.emailForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]]
    });

    this.signupForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      password: ['', [Validators.minLength(8)]],
      acceptTos: [false, Validators.requiredTrue]
    });

    this.accessRequestForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      reason: ['']
    });

    this.sponsorshipForm = this.fb.group({
      organisation_name: ['', Validators.required],
      contact_email: ['', [Validators.required, Validators.email]],
      contact_name: [''],
      area_of_interest: [''],
      message: ['']
    });
  }

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      if (params['error'] === 'invalid_token') {
        this.error = 'Invalid verification link. Please try again.';
      } else if (params['error'] === 'expired_token') {
        this.error = 'Verification link has expired. Please request a new one.';
      } else if (params['error'] === 'slack_disabled') {
        this.error = 'Slack sign-in is currently disabled.';
      } else if (params['error'] === 'slack_not_configured') {
        this.error = 'Slack sign-in is not configured.';
      } else if (params['error'] === 'public_email') {
        this.error = params['message'] || 'Please use your work email address.';
      } else if (params['error'] === 'slack_auth_error') {
        this.error = 'Slack authentication failed. Please try again.';
      } else if (params['error'] === 'google_not_configured') {
        this.error = 'Google sign-in is not configured.';
      } else if (params['error'] === 'google_auth_error') {
        this.error = 'Google authentication failed. Please try again.';
      }
    });

    // Check if Slack OIDC sign-in is enabled
    this.checkSlackOidcStatus();

    // Check if Google OAuth sign-in is enabled
    this.checkGoogleOauthStatus();

    // Start typewriter animation
    this.startTypewriterAnimation();
  }

  private checkSlackOidcStatus(): void {
    this.http.get<{ enabled: boolean }>('/api/auth/slack-oidc-status').subscribe({
      next: (response) => {
        this.slackOidcEnabled = response.enabled;
      },
      error: () => {
        this.slackOidcEnabled = false;
      }
    });
  }

  signInWithSlack(): void {
    // Redirect to Slack OIDC initiation endpoint
    window.location.href = '/auth/slack/oidc';
  }

  private checkGoogleOauthStatus(): void {
    this.http.get<{ enabled: boolean }>('/api/auth/google-status').subscribe({
      next: (response) => {
        this.googleOauthEnabled = response.enabled;
      },
      error: () => {
        this.googleOauthEnabled = false;
      }
    });
  }

  signInWithGoogle(): void {
    // Redirect to Google OAuth initiation endpoint
    window.location.href = '/auth/google';
  }

  private startTypewriterAnimation(): void {
    this.typeNextWord();
  }

  private typeNextWord(): void {
    const currentWord = this.decisionTypes[this.currentTypeIndex];
    const isLastWord = this.currentTypeIndex === this.decisionTypes.length - 1;

    // Type each character
    let charIndex = 0;
    const typeChar = () => {
      if (charIndex <= currentWord.length) {
        this.displayedDecisionType = currentWord.substring(0, charIndex);
        charIndex++;
        this.typewriterTimeout = setTimeout(typeChar, 80);
      } else {
        // Word complete
        if (isLastWord) {
          // Final word - stop animation (stays on "Decision Records")
          return;
        } else {
          // Wait, then erase and move to next word
          this.typewriterTimeout = setTimeout(() => {
            this.eraseWord(currentWord.length);
          }, 1200);
        }
      }
    };
    typeChar();
  }

  private eraseWord(length: number): void {
    let charIndex = length;
    const eraseChar = () => {
      if (charIndex >= 0) {
        this.displayedDecisionType = this.decisionTypes[this.currentTypeIndex].substring(0, charIndex);
        charIndex--;
        this.typewriterTimeout = setTimeout(eraseChar, 40);
      } else {
        // Move to next word
        this.currentTypeIndex++;
        this.typewriterTimeout = setTimeout(() => {
          this.typeNextWord();
        }, 300);
      }
    };
    eraseChar();
  }

  checkEmail(): void {
    if (this.emailForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const email = this.emailForm.value.email.toLowerCase();
    const domain = email.split('@')[1];

    if (!domain) {
      this.error = 'Invalid email address';
      this.isLoading = false;
      return;
    }

    this.tenantDomain = domain;

    this.http.get<TenantStatus>(`/api/auth/tenant/${domain}`).subscribe({
      next: (status) => {
        this.tenantStatus = status;

        if (status.has_users) {
          // Tenant exists - check if this specific user already exists
          this.http.get<{ exists: boolean; has_passkey: boolean; has_password: boolean }>(`/api/auth/user-exists/${email}`).subscribe({
            next: (userStatus) => {
              this.isLoading = false;

              if (userStatus.exists) {
                // User already exists - redirect to tenant login
                this.closeDialog();
                this.router.navigate([`/${domain}/login`], {
                  queryParams: { email }
                });
                return;
              }

              // User doesn't exist in this tenant
              if (!status.email_verification_required) {
                // If no email verification required, still redirect to login for new user signup
                this.closeDialog();
                this.router.navigate([`/${domain}/login`], {
                  queryParams: { email }
                });
                return;
              }

              // Use effective_require_approval which accounts for:
              // - Tenant's require_approval setting
              // - Whether tenant has admins who can actually approve (not just provisional admin)
              if (status.effective_require_approval) {
                this.currentView = 'access_request';
                this.accessRequestForm.patchValue({ email });
              } else {
                this.currentView = 'join_organization';
                this.accessRequestForm.patchValue({ email });
              }
            },
            error: () => {
              this.isLoading = false;
              // If user check fails, fall back to redirecting to login
              this.closeDialog();
              this.router.navigate([`/${domain}/login`], {
                queryParams: { email }
              });
            }
          });
        } else {
          this.isLoading = false;
          this.currentView = 'signup';
          this.signupForm.patchValue({ email });
        }
      },
      error: (err) => {
        this.isLoading = false;
        if (err.error?.is_public_domain) {
          this.error = err.error.error || 'Public email domains are not allowed. Please use your work email.';
        } else if (err.error?.is_disposable_domain) {
          this.error = err.error.error || 'Disposable email addresses are not allowed.';
        } else {
          this.error = err.error?.error || 'Failed to check domain status';
        }
      }
    });
  }

  sendVerification(): void {
    if (this.signupForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { email, first_name, last_name, password } = this.signupForm.value;

    if (this.tenantStatus && !this.tenantStatus.email_verification_required) {
      this.http.post<{ message: string; redirect: string; user?: any; setup_passkey?: boolean }>('/api/auth/direct-signup', {
        email,
        first_name,
        last_name,
        password: this.usePasswordSignup ? password : null,
        auth_preference: this.usePasswordSignup ? 'password' : 'passkey'
      }).subscribe({
        next: (response) => {
          this.authService.loadCurrentUser().subscribe({
            next: () => {
              this.isLoading = false;
              this.closeDialog();
              const redirectUrl = response.redirect || `/${this.tenantDomain}`;
              const [path, queryString] = redirectUrl.split('?');
              if (queryString) {
                const queryParams: { [key: string]: string } = {};
                queryString.split('&').forEach(param => {
                  const [key, value] = param.split('=');
                  queryParams[key] = value;
                });
                this.router.navigate([path], { queryParams });
              } else {
                this.router.navigate([path]);
              }
            },
            error: () => {
              this.isLoading = false;
              this.closeDialog();
              const redirectUrl = response.redirect || `/${this.tenantDomain}`;
              this.router.navigate([redirectUrl]);
            }
          });
        },
        error: (err) => {
          this.isLoading = false;
          if (err.error?.redirect) {
            this.closeDialog();
            this.router.navigate([err.error.redirect]);
          } else if (err.error?.domain_pending) {
            this.error = err.error.message || 'Your organization domain needs approval.';
          } else if (err.error?.is_public_domain) {
            this.error = err.error.error || 'Public email domains are not allowed.';
          } else {
            this.error = err.error?.error || 'Failed to create account';
          }
        }
      });
      return;
    }

    this.http.post<EmailVerificationResponse>('/api/auth/send-verification', {
      email,
      first_name,
      last_name,
      purpose: 'signup'
    }).subscribe({
      next: (response) => {
        this.isLoading = false;
        this.verificationEmail = email;
        this.currentView = 'verification_sent';
        this.startCooldown();
      },
      error: (err) => {
        this.isLoading = false;
        if (err.error?.redirect) {
          this.closeDialog();
          this.router.navigate([err.error.redirect]);
        } else {
          this.error = err.error?.error || 'Failed to send verification email';
        }
      }
    });
  }

  sendAccessRequestVerification(): void {
    if (this.accessRequestForm.invalid) return;

    this.isLoading = true;
    this.error = '';

    const { email, first_name, last_name, reason } = this.accessRequestForm.value;

    this.http.post<EmailVerificationResponse>('/api/auth/send-verification', {
      email,
      first_name,
      last_name,
      purpose: 'access_request',
      reason
    }).subscribe({
      next: (response) => {
        this.isLoading = false;
        this.verificationEmail = email;
        this.currentView = 'verification_sent';
        this.startCooldown();
      },
      error: (err) => {
        this.isLoading = false;
        if (err.error?.redirect) {
          this.closeDialog();
          this.router.navigate([err.error.redirect]);
        } else {
          this.error = err.error?.error || 'Failed to send verification email';
        }
      }
    });
  }

  submitJoinOrganization(): void {
    const emailCtrl = this.accessRequestForm.get('email');
    const firstNameCtrl = this.accessRequestForm.get('first_name');
    const lastNameCtrl = this.accessRequestForm.get('last_name');
    if (emailCtrl?.invalid || firstNameCtrl?.invalid || lastNameCtrl?.invalid) return;

    this.isLoading = true;
    this.error = '';

    const email = emailCtrl?.value;
    const first_name = firstNameCtrl?.value;
    const last_name = lastNameCtrl?.value;

    this.http.post<{ message: string; auto_approved?: boolean }>('/api/auth/access-request', {
      email,
      first_name,
      last_name
    }).subscribe({
      next: (response) => {
        this.isLoading = false;
        this.verificationEmail = email;

        if (response.auto_approved) {
          this.currentView = 'account_created';
        } else {
          this.currentView = 'verification_sent';
          this.startCooldown();
        }
      },
      error: (err) => {
        this.isLoading = false;
        if (err.error?.redirect) {
          this.closeDialog();
          this.router.navigate([err.error.redirect]);
        } else {
          this.error = err.error?.error || 'Failed to create account';
        }
      }
    });
  }

  resendVerification(): void {
    if (this.resendCooldown > 0 || this.isLoading) return;

    this.isLoading = true;
    this.error = '';

    const formData = this.signupForm.value.email
      ? this.signupForm.value
      : this.accessRequestForm.value;

    this.http.post<EmailVerificationResponse>('/api/auth/send-verification', {
      email: formData.email,
      first_name: formData.first_name,
      last_name: formData.last_name,
      purpose: this.tenantStatus?.has_users ? 'access_request' : 'signup',
      reason: this.accessRequestForm.value.reason
    }).subscribe({
      next: () => {
        this.isLoading = false;
        this.success = 'Verification email sent!';
        this.startCooldown();
        setTimeout(() => this.success = '', 3000);
      },
      error: (err) => {
        this.isLoading = false;
        this.error = err.error?.error || 'Failed to resend verification email';
      }
    });
  }

  private startCooldown(): void {
    this.resendCooldown = 60;
    if (this.cooldownInterval) {
      clearInterval(this.cooldownInterval);
    }
    this.cooldownInterval = setInterval(() => {
      this.resendCooldown--;
      if (this.resendCooldown <= 0 && this.cooldownInterval) {
        clearInterval(this.cooldownInterval);
        this.cooldownInterval = null;
      }
    }, 1000);
  }

  togglePasswordSignup(): void {
    this.usePasswordSignup = !this.usePasswordSignup;
    if (!this.usePasswordSignup) {
      this.signupForm.patchValue({ password: '' });
    }
  }

  goBack(): void {
    this.currentView = 'email';
    this.error = '';
    this.success = '';
    this.tenantStatus = null;
    this.verificationEmail = '';
    this.usePasswordSignup = false;
  }

  // Carousel methods
  prevSlide(): void {
    if (this.currentSlide > 0) {
      this.currentSlide--;
    }
  }

  nextSlide(): void {
    if (this.currentSlide < 2) {
      this.currentSlide++;
    }
  }

  goToSlide(index: number): void {
    this.currentSlide = index;
  }

  openGetStartedDialog(): void {
    this.currentView = 'email';
    this.error = '';
    this.success = '';
    this.isSignInMode = false;
    this.dialogRef = this.dialog.open(this.getStartedDialog, {
      width: '450px',
      maxWidth: '90vw',
      panelClass: 'get-started-dialog'
    });
  }

  openSignInDialog(): void {
    this.currentView = 'email';
    this.error = '';
    this.success = '';
    this.isSignInMode = true;
    this.dialogRef = this.dialog.open(this.getStartedDialog, {
      width: '450px',
      maxWidth: '90vw',
      panelClass: 'get-started-dialog'
    });
  }

  closeDialog(): void {
    if (this.dialogRef) {
      this.dialogRef.close();
      this.dialogRef = null;
    }
  }

  // Sponsorship dialog methods
  openSponsorshipDialog(): void {
    this.sponsorshipError = '';
    this.sponsorshipSuccess = '';
    this.sponsorshipForm.reset();
    this.sponsorshipDialogRef = this.dialog.open(this.sponsorshipDialogTemplate, {
      width: '800px',
      maxWidth: '90vw',
      panelClass: 'sponsorship-dialog-panel'
    });
  }

  closeSponsorshipDialog(): void {
    if (this.sponsorshipDialogRef) {
      this.sponsorshipDialogRef.close();
      this.sponsorshipDialogRef = null;
    }
  }

  submitSponsorship(): void {
    if (this.sponsorshipForm.invalid) return;

    this.sponsorshipLoading = true;
    this.sponsorshipError = '';

    this.http.post<{ message?: string; error?: string }>('/api/sponsorship', this.sponsorshipForm.value).subscribe({
      next: (result) => {
        this.sponsorshipLoading = false;
        this.sponsorshipSuccess = result.message || 'Thank you for your interest!';
        this.sponsorshipForm.reset();
      },
      error: (err) => {
        this.sponsorshipLoading = false;
        this.sponsorshipError = err.error?.error || 'Failed to submit inquiry. Please try again.';
      }
    });
  }
}
