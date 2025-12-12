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
    MatSelectModule
  ],
  template: `
    <div class="homepage">
      <!-- Hero Section -->
      <section class="hero">
        <div class="hero-container">
          <div class="hero-content-centered">
            <p class="hero-initiative">
              <span class="initiative-badge">Open Initiative</span>
              Architecture-Decisions.org
            </p>
            <h1>Architecture <span class="highlight">Decisions</span></h1>
            <p class="hero-tagline">
              Decisions shape systems for years — but the reasons behind them are rarely preserved.
            </p>
            <p class="hero-subtitle">
              Make your architectural decisions explicit, durable, and reusable across your organisation.
            </p>
            <div class="hero-cta">
              <button mat-raised-button class="cta-button" (click)="openGetStartedDialog()">
                <span>Get Started</span>
                <mat-icon>arrow_forward</mat-icon>
              </button>
              <button mat-stroked-button class="cta-button-secondary" (click)="openSignInDialog()">
                <mat-icon>login</mat-icon>
                <span>Sign In</span>
              </button>
            </div>
          </div>

          <!-- Screenshot inside hero -->
          <div class="hero-screenshot">
            <div class="browser-frame">
              <div class="browser-header">
                <div class="browser-dots">
                  <span class="dot red"></span>
                  <span class="dot yellow"></span>
                  <span class="dot green"></span>
                </div>
                <div class="browser-address">
                  <span>architecture-decisions.org/brandnewcorp.com</span>
                </div>
              </div>
              <div class="browser-content">
                <img src="/assets/screenshot-dashboard.png" alt="Architecture Decisions Dashboard" />
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
            }

            <!-- Signup View (first user for domain) -->
            @if (currentView === 'signup') {
              <div class="tenant-info">
                <mat-icon>domain</mat-icon>
                <span>Setting up <strong>{{ tenantDomain }}</strong></span>
              </div>

              <form [formGroup]="signupForm" (ngSubmit)="sendVerification()">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Email</mat-label>
                  <input matInput formControlName="email" type="email" readonly>
                  <mat-icon matPrefix>email</mat-icon>
                </mat-form-field>

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Full Name</mat-label>
                  <input matInput formControlName="name" placeholder="Your name">
                  <mat-icon matPrefix>person</mat-icon>
                </mat-form-field>

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

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Full Name</mat-label>
                  <input matInput formControlName="name" placeholder="Your name">
                  <mat-icon matPrefix>person</mat-icon>
                </mat-form-field>

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

                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Full Name</mat-label>
                  <input matInput formControlName="name" placeholder="Your name">
                  <mat-icon matPrefix>person</mat-icon>
                </mat-form-field>

                <p class="info-text">
                  <mat-icon>verified_user</mat-icon>
                  <span>We'll verify your email and create your account.</span>
                </p>

                <button mat-raised-button color="primary" type="submit"
                        [disabled]="accessRequestForm.get('email')?.invalid || accessRequestForm.get('name')?.invalid || isLoading" class="full-width submit-btn">
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
          <h2>The Problem: Decisions Without Memory</h2>
          <p class="section-intro">
            Anyone tasked with fixing, evolving, securing, or modernising systems suffers from the loss of decision context.
          </p>

          <div class="problem-grid">
            <div class="problem-card">
              <mat-icon>meeting_room</mat-icon>
              <h3>Made in Meetings</h3>
              <p>Critical decisions buried in emails, slide decks, or conversations</p>
            </div>
            <div class="problem-card">
              <mat-icon>hourglass_empty</mat-icon>
              <h3>Temporary Assumptions</h3>
              <p>Justified by constraints that no longer exist or were never documented</p>
            </div>
            <div class="problem-card">
              <mat-icon>psychology</mat-icon>
              <h3>Forgotten Intent</h3>
              <p>Original reasoning lost once implementation starts</p>
            </div>
            <div class="problem-card">
              <mat-icon>loop</mat-icon>
              <h3>Repeated Mistakes</h3>
              <p>Teams rediscover problems that were already solved</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Architecture Decisions Section -->
      <section class="section decisions-section">
        <div class="container">
          <div class="decisions-content">
            <div class="decisions-text">
              <h2>Architecture Decisions Across Your Organisation</h2>
              <p>
                Every organisation makes long-lasting technical and operational decisions — most of them are never written down.
                These decisions shape IT landscapes, digital platforms, cloud strategies, security postures, and integration models.
              </p>
              <p>
                These decisions often span years or decades, outlive the people who made them,
                and affect cost, risk, resilience, and compliance. Yet most are <strong>never formally recorded</strong>.
              </p>
            </div>
            <div class="decisions-list">
              <div class="decision-item">
                <mat-icon>schedule</mat-icon>
                <span>Decisions that span years or decades</span>
              </div>
              <div class="decision-item">
                <mat-icon>groups</mat-icon>
                <span>Outlive the people who made them</span>
              </div>
              <div class="decision-item">
                <mat-icon>trending_up</mat-icon>
                <span>Affect cost, risk, resilience, and compliance</span>
              </div>
              <div class="decision-item">
                <mat-icon>warning</mat-icon>
                <span>Revisited only when something breaks</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Core Idea -->
      <section class="section core-section">
        <div class="container">
          <div class="core-section-grid">
            <div class="core-idea">
              <h2>Our Core Idea</h2>
              <p class="big-statement">
                Architecture decisions should be treated as <strong>first-class records</strong>.
              </p>
              <p>
                Just like financial records, legal documents, or policies — architecture decisions
                deserve structure, traceability, and survival across personnel and technology changes.
              </p>
              <blockquote>
                "Well-documented decisions enable better future decisions."
              </blockquote>
            </div>
            <div class="security-commitment">
              <h2>Security & Trust</h2>
              <p class="security-intro">
                Your architecture decisions contain sensitive strategic information. We take security seriously.
              </p>
              <div class="security-features">
                <div class="security-item">
                  <mat-icon>apartment</mat-icon>
                  <div>
                    <strong>Tenant Isolation</strong>
                    <span>Complete data separation between organizations</span>
                  </div>
                </div>
                <div class="security-item">
                  <mat-icon>lock</mat-icon>
                  <div>
                    <strong>Encryption at Rest</strong>
                    <span>All data encrypted using industry standards</span>
                  </div>
                </div>
                <div class="security-item">
                  <mat-icon>fingerprint</mat-icon>
                  <div>
                    <strong>Passwordless Auth</strong>
                    <span>WebAuthn/Passkeys for phishing-resistant login</span>
                  </div>
                </div>
                <div class="security-item">
                  <img src="/assets/european-union-europe-svgrepo-com.svg" alt="EU" class="eu-icon" />
                  <div>
                    <strong>EU Data Residency</strong>
                    <span>Data stored in European Azure datacenters</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Who Is This For -->
      <section class="section audience-section">
        <div class="container">
          <h2>Who Is This For?</h2>

          <div class="audience-grid">
            <div class="audience-card">
              <mat-icon>architecture</mat-icon>
              <h3>Architects & Engineers</h3>
              <p>Document and evolve architectural decisions for long-lived systems</p>
            </div>

            <div class="audience-card">
              <mat-icon>business</mat-icon>
              <h3>IT Leaders</h3>
              <p>Create institutional memory for strategic technology decisions</p>
            </div>

            <div class="audience-card">
              <mat-icon>engineering</mat-icon>
              <h3>Operators & Maintainers</h3>
              <p>Understand original intent before changing systems</p>
            </div>

            <div class="audience-card">
              <mat-icon>gavel</mat-icon>
              <h3>Auditors & Regulators</h3>
              <p>Improve traceability and accountability of decisions</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Trust & Governance -->
      <section class="section governance-section">
        <div class="container">
          <div class="governance-content">
            <div class="governance-illustration">
              <img src="/assets/collaborative-combine-hand-svgrepo-com.svg" alt="Collaborative hands" class="governance-svg" />
            </div>
            <div class="governance-text">
              <h2>Trust & Governance</h2>
              <p class="governance-intro">
                Architecture Decisions is a <strong>non-profit, independent initiative</strong>.
                No organisation owns or controls the platform.
              </p>
              <div class="governance-list">
                <div class="governance-item">
                  <mat-icon>person</mat-icon>
                  <div>
                    <strong>Users own their data</strong>
                    <span>You retain ownership of all decision records and content you create.</span>
                  </div>
                </div>
                <div class="governance-item">
                  <mat-icon>block</mat-icon>
                  <div>
                    <strong>No data sales, no advertising</strong>
                    <span>We do not sell user data, analytics, or insights — now or in the future.</span>
                  </div>
                </div>
                <div class="governance-item">
                  <mat-icon>volunteer_activism</mat-icon>
                  <div>
                    <strong>Sustainable, transparent funding</strong>
                    <span>The project covers operating costs through sponsorships and community support.</span>
                  </div>
                </div>
                <div class="governance-item">
                  <mat-icon>balance</mat-icon>
                  <div>
                    <strong>Neutral by design</strong>
                    <span>Not tied to any vendor, consultancy, framework, or certification scheme.</span>
                  </div>
                </div>
              </div>
              <p class="governance-goal">
                Our goal is simple: to provide durable infrastructure for capturing and preserving
                architectural decisions — without hidden incentives.
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- Footer -->
      <footer class="homepage-footer">
        <div class="container">
          <div class="footer-grid">
            <div class="footer-mission-col">
              <p class="footer-mission">
                Architecture-Decisions.org is an open initiative to make architectural decision-making
                transparent, durable, and reusable.
              </p>
              <small class="footer-copyright">&copy; {{ currentYear }} Architecture-Decisions.org <span class="footer-separator">|</span> <a routerLink="/licensing" class="footer-link">License Model</a></small>
            </div>
            <div class="footer-support-col">
              <h4>Support the Initiative</h4>
              <p class="footer-support-text">Help us keep the platform free, independent, and sustainable.</p>
              <button mat-stroked-button class="sponsorship-button" (click)="openSponsorshipDialog()">
                <mat-icon>volunteer_activism</mat-icon>
                Sponsorship & Support
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
                  Architecture Decisions is a <strong>non-profit initiative</strong>. The platform is free to use,
                  and we do not monetise user data or sell access.
                </p>
                <p>
                  To cover infrastructure and operational costs, the project is supported through sponsorships.
                  Sponsorship does not grant control, influence over content, or preferential treatment.
                  It simply helps ensure the platform remains <strong>stable, independent, and available</strong> over the long term.
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
                      <mat-option value="General sponsorship">General sponsorship</mat-option>
                      <mat-option value="Public sector use">Public sector use</mat-option>
                      <mat-option value="Research">Research</mat-option>
                      <mat-option value="Internal adoption">Internal adoption</mat-option>
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
    }

    /* Hero Section - Salient rich blue gradient */
    .hero {
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #1e40af 100%);
      color: white;
      padding: 100px 24px 80px;
      position: relative;
      overflow: visible;
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
      max-width: 800px;
      margin: 0 auto;
    }

    .hero-content-centered h1 {
      font-size: 3.5rem;
      font-weight: 700;
      margin: 0 0 24px;
      letter-spacing: -0.02em;
      line-height: 1.1;
      color: white;
    }

    .hero-content-centered h1 .highlight {
      color: #93c5fd;
      position: relative;
    }

    .hero-tagline {
      font-size: 1.25rem;
      font-weight: 400;
      margin: 0 0 16px;
      color: #e0f2fe;
      line-height: 1.6;
    }

    .hero-subtitle {
      font-size: 1.1rem;
      color: #bfdbfe;
      line-height: 1.7;
      margin: 0 0 32px;
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
      border-radius: 100px !important;
      background: white !important;
      color: #1e40af !important;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15) !important;
      transition: all 0.2s ease !important;
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
      border-radius: 100px !important;
      border-color: rgba(255, 255, 255, 0.4) !important;
      color: white !important;
    }

    .cta-button-secondary:hover {
      background: rgba(255, 255, 255, 0.1) !important;
      border-color: rgba(255, 255, 255, 0.6) !important;
    }

    .cta-button-secondary span,
    .cta-button-secondary mat-icon {
      color: white !important;
    }

    .hero-initiative {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-bottom: 24px;
      font-size: 0.9rem;
      color: #bfdbfe;
      letter-spacing: 0.5px;
    }

    .initiative-badge {
      display: inline-block;
      padding: 6px 14px;
      background: rgba(255, 255, 255, 0.15);
      border: 1px solid rgba(255, 255, 255, 0.3);
      border-radius: 100px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: white;
    }

    /* Dialog Styles */
    .dialog-container {
      padding: 32px 32px 24px;
      min-width: 320px;
      max-width: 420px;
      position: relative;
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
      top: 8px;
      right: 8px;
      color: #94a3b8;
      z-index: 10;
    }

    .dialog-close:hover {
      color: #64748b;
      background: #f1f5f9;
    }

    .dialog-header {
      margin-bottom: 20px;
      padding-right: 32px;
    }

    .dialog-header h2 {
      font-size: 1.35rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 6px;
      padding: 0;
    }

    .dialog-subtitle {
      color: #64748b;
      font-size: 0.9rem;
      margin: 0;
      line-height: 1.4;
    }

    ::ng-deep .mat-mdc-dialog-container {
      border-radius: 16px !important;
    }

    ::ng-deep .mat-mdc-dialog-surface {
      padding: 0 !important;
    }

    ::ng-deep mat-dialog-content {
      padding: 0 !important;
      margin: 0 !important;
      max-height: none !important;
      overflow: visible !important;
    }

    /* Signup Card - Salient style */
    .signup-card {
      padding: 32px;
      border-radius: 16px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
      border: 1px solid #e2e8f0;
    }

    mat-card-header {
      margin-bottom: 20px;
    }

    mat-card-title {
      font-size: 1.5rem;
      font-weight: 600;
      color: #0f172a;
    }

    mat-card-subtitle {
      color: #64748b;
      font-size: 0.95rem;
    }

    .error-message {
      background-color: #fef2f2;
      color: #dc2626;
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 16px;
      font-size: 14px;
      font-weight: 500;
    }

    .success-message {
      background-color: #f0fdf4;
      color: #16a34a;
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 16px;
      font-size: 14px;
      font-weight: 500;
    }

    .full-width {
      width: 100%;
    }

    mat-form-field {
      margin-bottom: 8px;
    }

    .submit-btn {
      margin-top: 12px;
      padding: 12px 24px;
      font-size: 14px;
      font-weight: 500;
      border-radius: 100px;
      background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%) !important;
      letter-spacing: 0.1px;
      color: #ffffff !important;
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
      background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
    }

    .submit-btn:disabled {
      background: linear-gradient(135deg, #64748b 0%, #475569 100%) !important;
      color: rgba(255, 255, 255, 0.7) !important;
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

    /* Hero Screenshot - inside hero section */
    .hero-screenshot {
      max-width: 1100px;
      margin: 60px auto 0;
      padding: 0 24px;
      position: relative;
      z-index: 5;
    }

    .browser-frame {
      border-radius: 16px;
      overflow: hidden;
      box-shadow:
        0 25px 80px -12px rgba(0, 0, 0, 0.4),
        0 0 0 1px rgba(255, 255, 255, 0.15),
        0 0 60px rgba(59, 130, 246, 0.2);
      background: rgba(30, 41, 59, 0.6);
      backdrop-filter: blur(8px);
    }

    .browser-header {
      background: rgba(71, 85, 105, 0.5);
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
      text-align: center;
      padding-bottom: 60px;
    }

    .problem-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 24px;
    }

    .problem-card {
      padding: 28px 24px;
      border-radius: 24px;
      background: #fff;
      box-shadow: 0 1px 3px 1px rgba(0, 0, 0, 0.15), 0 1px 2px rgba(0, 0, 0, 0.3);
      transition: all 0.2s cubic-bezier(0.2, 0, 0, 1);
      border: 1px solid rgba(0, 0, 0, 0.05);
    }

    .problem-card:hover {
      box-shadow: 0 4px 8px 3px rgba(0, 0, 0, 0.15), 0 1px 3px rgba(0, 0, 0, 0.3);
      transform: translateY(-4px);
    }

    .problem-card mat-icon {
      font-size: 36px;
      width: 36px;
      height: 36px;
      color: #b3261e;
      margin-bottom: 16px;
      background: #f9dedc;
      padding: 10px;
      border-radius: 12px;
      box-sizing: content-box;
    }

    .problem-card h3 {
      margin: 0 0 12px;
      font-size: 1.125rem;
      font-weight: 600;
      color: #0f172a;
    }

    .problem-card p {
      margin: 0;
      color: #64748b;
      font-size: 0.95rem;
      line-height: 1.6;
    }

    /* Decisions Section */
    .decisions-section {
      background: #f8fafc;
      padding-top: 60px;
    }

    .decisions-content {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 80px;
      align-items: center;
    }

    .decisions-text h2 {
      margin-bottom: 24px;
    }

    .decisions-text p {
      color: #64748b;
      line-height: 1.8;
      margin: 0 0 20px;
      font-size: 1.05rem;
    }

    .decisions-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .decision-item {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px 24px;
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      border-left: 4px solid #2563eb;
    }

    .decision-item mat-icon {
      color: #2563eb;
      font-size: 24px;
      width: 24px;
      height: 24px;
    }

    .decision-item span {
      color: #334155;
      font-size: 1rem;
      font-weight: 500;
    }

    /* Core Section - Dark slate like Salient */
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
      background: #f8fafc;
      text-align: center;
      padding-bottom: 60px;
    }

    .audience-section h2 {
      margin-bottom: 48px;
    }

    .audience-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 24px;
    }

    .audience-card {
      padding: 32px 24px;
      border-radius: 28px;
      background: #fff;
      box-shadow: 0 1px 3px 1px rgba(0, 0, 0, 0.15), 0 1px 2px rgba(0, 0, 0, 0.3);
      text-align: center;
      transition: all 0.2s cubic-bezier(0.2, 0, 0, 1);
      border: 1px solid rgba(0, 0, 0, 0.05);
    }

    .audience-card:hover {
      box-shadow: 0 4px 8px 3px rgba(0, 0, 0, 0.15), 0 1px 3px rgba(0, 0, 0, 0.3);
      transform: translateY(-4px);
    }

    .audience-card mat-icon {
      font-size: 44px;
      width: 44px;
      height: 44px;
      color: #2563eb;
      margin-bottom: 16px;
      background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
      padding: 12px;
      border-radius: 16px;
      box-sizing: content-box;
    }

    .audience-card h3 {
      margin: 0 0 8px;
      color: #1c1b1f;
      font-size: 1.1rem;
      font-weight: 500;
      letter-spacing: 0.1px;
    }

    .audience-card p {
      color: #49454f;
      margin: 0;
      font-size: 0.9rem;
      line-height: 1.5;
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

    /* Footer - Salient dark theme */
    .homepage-footer {
      background: #0f172a;
      color: white;
      padding: 64px 24px;
      text-align: center;
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
      grid-template-columns: 1.5fr 1fr;
      gap: 60px;
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

    .footer-separator {
      margin: 0 8px;
      color: #475569;
    }

    .footer-link {
      color: #64748b;
      text-decoration: none;
      transition: color 0.2s;
    }

    .footer-link:hover {
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
    }

    .sponsorship-button:hover {
      background: rgba(255, 255, 255, 0.1) !important;
    }

    .sponsorship-button mat-icon {
      margin-right: 8px;
    }

    /* Dialog icon */
    .dialog-icon {
      color: #2563eb;
      font-size: 28px;
      width: 28px;
      height: 28px;
    }

    /* Sponsorship Dialog - Two Column Layout */
    .sponsorship-dialog {
      padding: 32px;
      position: relative;
      min-width: 700px;
      max-width: 800px;
    }

    .sponsorship-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
      padding-right: 32px;
    }

    .sponsorship-header h2 {
      font-size: 1.35rem;
      font-weight: 600;
      color: #0f172a;
      margin: 0;
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
      color: #475569;
      font-size: 0.95rem;
      line-height: 1.7;
      margin: 0 0 16px;
    }

    .sponsorship-text p:last-child {
      margin-bottom: 0;
    }

    .sponsorship-text strong {
      color: #1e40af;
    }

    .sponsorship-form {
      padding-left: 8px;
    }

    .sponsorship-form mat-form-field {
      margin-bottom: 4px;
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

      .hero-content h1 {
        font-size: 2.5rem;
      }

      .hero-tagline {
        font-size: 1.1rem;
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

      .browser-frame {
        margin: 0 -8px;
        border-radius: 12px;
      }
    }

    @media (max-width: 600px) {
      .hero {
        padding: 60px 16px 40px;
      }

      .hero-content-centered h1 {
        font-size: 2rem;
      }

      .hero-tagline {
        font-size: 1rem;
      }

      .hero-subtitle {
        font-size: 0.95rem;
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

      .hero-screenshot {
        margin: 40px auto 0;
        padding: 0 8px;
      }

      .browser-frame {
        border-radius: 8px;
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
        font-size: 2rem;
      }

      .audience-grid {
        grid-template-columns: repeat(2, 1fr);
      }

      .problem-grid {
        grid-template-columns: 1fr;
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
      name: ['', Validators.required],
      password: ['', [Validators.minLength(8)]]
    });

    this.accessRequestForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      name: ['', Validators.required],
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
      }
    });
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

              if (status.require_approval) {
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

    const { email, name, password } = this.signupForm.value;

    if (this.tenantStatus && !this.tenantStatus.email_verification_required) {
      this.http.post<{ message: string; redirect: string; user?: any; setup_passkey?: boolean }>('/api/auth/direct-signup', {
        email,
        name,
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
      name,
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

    const { email, name, reason } = this.accessRequestForm.value;

    this.http.post<EmailVerificationResponse>('/api/auth/send-verification', {
      email,
      name,
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
    const nameCtrl = this.accessRequestForm.get('name');
    if (emailCtrl?.invalid || nameCtrl?.invalid) return;

    this.isLoading = true;
    this.error = '';

    const email = emailCtrl?.value;
    const name = nameCtrl?.value;

    this.http.post<{ message: string; auto_approved?: boolean }>('/api/auth/access-request', {
      email,
      name
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
      name: formData.name,
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
