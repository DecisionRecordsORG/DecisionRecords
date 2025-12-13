import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterModule } from '@angular/router';

interface SessionSettings {
  admin_session_timeout_hours: number;
  user_session_timeout_hours: number;
  defaults: {
    admin_session_timeout_hours: number;
    user_session_timeout_hours: number;
  };
}

interface LicensingSettings {
  max_users_per_tenant: number;
  defaults: {
    max_users_per_tenant: number;
  };
}

interface EndpointCategory {
  name: string;
  icon: string;
  endpoints: string[];
}

interface AnalyticsSettings {
  enabled: boolean;
  host: string;
  person_profiling: boolean;
  exception_capture: boolean;
  api_key_configured: boolean;
  event_mappings: { [key: string]: string };
  categories: { [key: string]: EndpointCategory };
}

interface CloudflareSettings {
  origin_check_enabled: boolean;
  access_enabled: boolean;
  access_team_domain: string;
  access_aud_configured: boolean;
  protected_paths: string[];
}

interface LogForwardingSettings {
  enabled: boolean;
  endpoint_url: string;
  auth_type: 'api_key' | 'bearer' | 'header' | 'none';
  auth_header_name: string;
  has_api_key: boolean;
  log_level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  service_name: string;
  environment: string;
  custom_headers: string;
}

@Component({
  selector: 'app-superadmin-settings',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatSlideToggleModule,
    MatExpansionModule,
    MatTooltipModule
  ],
  template: `
    <div class="settings-container">
      <h1>
        <mat-icon>settings</mat-icon>
        System Settings
      </h1>

      <!-- Licensing Settings Card -->
      <mat-card>
        <mat-card-header>
          <mat-card-title>
            <mat-icon>business</mat-icon>
            Licensing & Limits
          </mat-card-title>
          <mat-card-subtitle>
            Configure tenant limits and licensing thresholds
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          @if (licensingLoading) {
            <div class="loading">
              <mat-spinner diameter="40"></mat-spinner>
            </div>
          } @else {
            <form [formGroup]="licensingForm" (ngSubmit)="saveLicensingSettings()">
              <div class="form-section">
                <h3>User Limits</h3>
                <p class="hint">Control the maximum number of users per tenant (0 = unlimited)</p>
                <mat-form-field appearance="outline">
                  <mat-label>Max Users Per Tenant</mat-label>
                  <input matInput type="number" formControlName="max_users_per_tenant" min="0" max="10000">
                  <mat-hint>0-10000 (default: {{ licensingDefaults.max_users_per_tenant }}, 0 = unlimited)</mat-hint>
                </mat-form-field>
                <div class="limit-info">
                  @if (licensingForm.get('max_users_per_tenant')?.value === 0) {
                    <span class="unlimited"><mat-icon>all_inclusive</mat-icon> Unlimited users allowed</span>
                  } @else {
                    <span class="limited"><mat-icon>group</mat-icon> Each tenant can have up to {{ licensingForm.get('max_users_per_tenant')?.value }} users</span>
                  }
                </div>
              </div>

              <div class="actions">
                <button mat-raised-button color="primary" type="submit" [disabled]="licensingSaving || !licensingForm.valid">
                  <mat-spinner diameter="20" *ngIf="licensingSaving"></mat-spinner>
                  <mat-icon *ngIf="!licensingSaving">save</mat-icon>
                  <span *ngIf="!licensingSaving">Save Licensing Settings</span>
                </button>
                <button mat-button type="button" (click)="resetLicensingToDefaults()">
                  <mat-icon>restore</mat-icon>
                  Reset to Defaults
                </button>
              </div>
            </form>
          }
        </mat-card-content>
      </mat-card>

      <!-- Session Settings Card -->
      <mat-card>
        <mat-card-header>
          <mat-card-title>
            <mat-icon>timer</mat-icon>
            Session Timeouts
          </mat-card-title>
          <mat-card-subtitle>
            Configure how long users stay logged in before requiring re-authentication
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          @if (loading) {
            <div class="loading">
              <mat-spinner diameter="40"></mat-spinner>
            </div>
          } @else {
            <form [formGroup]="sessionForm" (ngSubmit)="saveSettings()">
              <div class="form-section">
                <h3>Super Admin Session</h3>
                <p class="hint">For security, super admin sessions should have shorter timeouts</p>
                <mat-form-field appearance="outline">
                  <mat-label>Timeout (hours)</mat-label>
                  <input matInput type="number" formControlName="admin_session_timeout_hours" min="1" max="24">
                  <mat-hint>1-24 hours (default: {{ defaults.admin_session_timeout_hours }} hour)</mat-hint>
                </mat-form-field>
              </div>

              <div class="form-section">
                <h3>Regular User Session</h3>
                <p class="hint">For regular tenant users</p>
                <mat-form-field appearance="outline">
                  <mat-label>Timeout (hours)</mat-label>
                  <input matInput type="number" formControlName="user_session_timeout_hours" min="1" max="168">
                  <mat-hint>1-168 hours (default: {{ defaults.user_session_timeout_hours }} hours)</mat-hint>
                </mat-form-field>
              </div>

              <div class="actions">
                <button mat-raised-button color="primary" type="submit" [disabled]="saving || !sessionForm.valid">
                  <mat-spinner diameter="20" *ngIf="saving"></mat-spinner>
                  <mat-icon *ngIf="!saving">save</mat-icon>
                  <span *ngIf="!saving">Save Settings</span>
                </button>
                <button mat-button type="button" (click)="resetToDefaults()">
                  <mat-icon>restore</mat-icon>
                  Reset to Defaults
                </button>
              </div>
            </form>
          }
        </mat-card-content>
      </mat-card>

      <!-- Analytics Settings Card -->
      <mat-card>
        <mat-card-header>
          <mat-card-title>
            <mat-icon>analytics</mat-icon>
            Product Analytics
          </mat-card-title>
          <mat-card-subtitle>
            Configure PostHog analytics for tracking platform usage
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          @if (analyticsLoading) {
            <div class="loading">
              <mat-spinner diameter="40"></mat-spinner>
            </div>
          } @else {
            <div class="form-section">
              <h3>Analytics Configuration</h3>
              <p class="hint">Enable analytics to track platform usage patterns</p>

              <div class="toggle-row">
                <mat-slide-toggle
                  [(ngModel)]="analyticsEnabled"
                  (change)="saveAnalyticsSettings()"
                  color="primary">
                  Enable Analytics
                </mat-slide-toggle>
                <span class="status-badge" [class.enabled]="analyticsEnabled">
                  {{ analyticsEnabled ? 'Active' : 'Disabled' }}
                </span>
              </div>

              @if (analyticsEnabled) {
                <div class="analytics-config">
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>PostHog Host URL</mat-label>
                    <input matInput [(ngModel)]="analyticsHost" placeholder="https://eu.i.posthog.com">
                    <mat-hint>PostHog server URL (e.g., https://eu.i.posthog.com or self-hosted URL)</mat-hint>
                  </mat-form-field>

                  <div class="api-key-section">
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>API Key</mat-label>
                      <input matInput
                             [type]="showApiKey ? 'text' : 'password'"
                             [(ngModel)]="analyticsApiKey"
                             placeholder="phc_...">
                      <button mat-icon-button matSuffix
                              (click)="showApiKey = !showApiKey"
                              type="button"
                              matTooltip="{{ showApiKey ? 'Hide' : 'Show' }} API Key">
                        <mat-icon>{{ showApiKey ? 'visibility_off' : 'visibility' }}</mat-icon>
                      </button>
                      <mat-hint>
                        @if (analyticsApiKeyConfigured && !analyticsApiKey) {
                          API key is configured (hidden for security)
                        } @else {
                          Enter your PostHog project API key
                        }
                      </mat-hint>
                    </mat-form-field>
                    <button mat-stroked-button
                            (click)="saveAnalyticsApiKey()"
                            [disabled]="!analyticsApiKey || analyticsSavingKey">
                      <mat-spinner diameter="18" *ngIf="analyticsSavingKey"></mat-spinner>
                      <mat-icon *ngIf="!analyticsSavingKey">vpn_key</mat-icon>
                      Save Key
                    </button>
                  </div>

                  <div class="toggle-row">
                    <mat-slide-toggle
                      [(ngModel)]="analyticsPersonProfiling"
                      (change)="saveAnalyticsSettings()"
                      color="primary">
                      Person Profiling
                    </mat-slide-toggle>
                    <span class="privacy-hint">
                      <mat-icon>privacy_tip</mat-icon>
                      {{ analyticsPersonProfiling ? 'User profiles will be created in PostHog' : 'Privacy mode: No user profiles created' }}
                    </span>
                  </div>

                  <div class="toggle-row">
                    <mat-slide-toggle
                      [(ngModel)]="analyticsExceptionCapture"
                      (change)="saveAnalyticsSettings()"
                      color="primary">
                      Exception Capture
                    </mat-slide-toggle>
                    <span class="privacy-hint">
                      <mat-icon>{{ analyticsExceptionCapture ? 'bug_report' : 'bug_report' }}</mat-icon>
                      {{ analyticsExceptionCapture ? 'Unhandled errors sent to PostHog for monitoring' : 'Error capture disabled' }}
                    </span>
                  </div>

                  <div class="test-section">
                    <button mat-stroked-button
                            color="primary"
                            (click)="testAnalyticsConnection()"
                            [disabled]="analyticsTesting || !analyticsApiKeyConfigured">
                      <mat-spinner diameter="18" *ngIf="analyticsTesting"></mat-spinner>
                      <mat-icon *ngIf="!analyticsTesting">send</mat-icon>
                      Test Connection
                    </button>
                    @if (analyticsTestResult) {
                      <span class="test-result" [class.success]="analyticsTestSuccess">
                        <mat-icon>{{ analyticsTestSuccess ? 'check_circle' : 'error' }}</mat-icon>
                        {{ analyticsTestResult }}
                      </span>
                    }
                  </div>

                  <div class="actions">
                    <button mat-raised-button color="primary"
                            (click)="saveAnalyticsSettings()"
                            [disabled]="analyticsSaving">
                      <mat-spinner diameter="20" *ngIf="analyticsSaving"></mat-spinner>
                      <mat-icon *ngIf="!analyticsSaving">save</mat-icon>
                      <span *ngIf="!analyticsSaving">Save Analytics Settings</span>
                    </button>
                  </div>
                </div>
              }
            </div>

            @if (analyticsEnabled && analyticsCategories) {
              <div class="form-section">
                <h3>Event Mappings</h3>
                <p class="hint">Customize event names sent to PostHog by category</p>

                <mat-accordion multi>
                  @for (categoryKey of getCategoryKeys(); track categoryKey) {
                    <mat-expansion-panel>
                      <mat-expansion-panel-header>
                        <mat-panel-title>
                          <mat-icon>{{ analyticsCategories[categoryKey].icon }}</mat-icon>
                          {{ analyticsCategories[categoryKey].name }}
                        </mat-panel-title>
                        <mat-panel-description>
                          {{ analyticsCategories[categoryKey].endpoints.length }} events
                        </mat-panel-description>
                      </mat-expansion-panel-header>

                      <div class="event-list">
                        @for (endpoint of analyticsCategories[categoryKey].endpoints; track endpoint) {
                          <div class="event-item">
                            <span class="endpoint-name" matTooltip="{{ endpoint }}">{{ endpoint }}</span>
                            <mat-form-field appearance="outline" class="event-name-field">
                              <input matInput
                                     [(ngModel)]="analyticsEventMappings[endpoint]"
                                     placeholder="{{ endpoint }}">
                            </mat-form-field>
                          </div>
                        }
                      </div>

                      <div class="panel-actions">
                        <button mat-button (click)="resetCategoryMappings(categoryKey)">
                          <mat-icon>restore</mat-icon>
                          Reset Category to Defaults
                        </button>
                      </div>
                    </mat-expansion-panel>
                  }
                </mat-accordion>

                <div class="actions">
                  <button mat-raised-button color="primary"
                          (click)="saveEventMappings()"
                          [disabled]="analyticsSavingMappings">
                    <mat-spinner diameter="20" *ngIf="analyticsSavingMappings"></mat-spinner>
                    <mat-icon *ngIf="!analyticsSavingMappings">save</mat-icon>
                    <span *ngIf="!analyticsSavingMappings">Save Event Mappings</span>
                  </button>
                  <button mat-button (click)="resetAllMappings()">
                    <mat-icon>restore</mat-icon>
                    Reset All to Defaults
                  </button>
                </div>
              </div>
            }
          }
        </mat-card-content>
      </mat-card>

      <!-- Cloudflare Security Settings Card -->
      <mat-card>
        <mat-card-header>
          <mat-card-title>
            <mat-icon>security</mat-icon>
            Cloudflare Security
          </mat-card-title>
          <mat-card-subtitle>
            Configure Cloudflare origin protection and Access authentication
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          @if (cloudflareLoading) {
            <div class="loading">
              <mat-spinner diameter="40"></mat-spinner>
            </div>
          } @else {
            <div class="form-section">
              <h3>Origin Protection</h3>
              <p class="hint">Block direct access to Azure IP - only allow requests through Cloudflare</p>

              <div class="toggle-row">
                <mat-slide-toggle
                  [(ngModel)]="cfOriginCheckEnabled"
                  (change)="saveCloudflareSettings()"
                  color="primary">
                  Enable Origin Check
                </mat-slide-toggle>
                <span class="status-badge" [class.enabled]="cfOriginCheckEnabled">
                  {{ cfOriginCheckEnabled ? 'Protected' : 'Disabled' }}
                </span>
              </div>

              <div class="security-info" [class.active]="cfOriginCheckEnabled">
                <mat-icon>{{ cfOriginCheckEnabled ? 'verified_user' : 'warning' }}</mat-icon>
                @if (cfOriginCheckEnabled) {
                  <span>Direct IP access is blocked. All requests must come through Cloudflare.</span>
                } @else {
                  <span>Warning: Direct IP access is allowed. Anyone with the Azure IP can bypass Cloudflare.</span>
                }
              </div>
            </div>

            <div class="form-section">
              <h3>Cloudflare Access (Zero Trust)</h3>
              <p class="hint">Require Cloudflare Access authentication for protected paths (e.g., /superadmin)</p>

              <div class="toggle-row">
                <mat-slide-toggle
                  [(ngModel)]="cfAccessEnabled"
                  (change)="saveCloudflareSettings()"
                  color="primary">
                  Enable Cloudflare Access
                </mat-slide-toggle>
                <span class="status-badge" [class.enabled]="cfAccessEnabled">
                  {{ cfAccessEnabled ? 'Active' : 'Disabled' }}
                </span>
              </div>

              @if (cfAccessEnabled) {
                <div class="cloudflare-config">
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Team Domain</mat-label>
                    <input matInput
                           [(ngModel)]="cfAccessTeamDomain"
                           placeholder="yourteam.cloudflareaccess.com">
                    <mat-hint>Your Cloudflare Access team domain</mat-hint>
                  </mat-form-field>

                  <div class="aud-section">
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Access AUD (Audience Tag)</mat-label>
                      <input matInput
                             [type]="showAccessAud ? 'text' : 'password'"
                             [(ngModel)]="cfAccessAud"
                             placeholder="32+ character hex string">
                      <button mat-icon-button matSuffix
                              (click)="showAccessAud = !showAccessAud"
                              type="button"
                              matTooltip="{{ showAccessAud ? 'Hide' : 'Show' }} AUD">
                        <mat-icon>{{ showAccessAud ? 'visibility_off' : 'visibility' }}</mat-icon>
                      </button>
                      <mat-hint>
                        @if (cfAccessAudConfigured && !cfAccessAud) {
                          AUD is configured (hidden for security)
                        } @else {
                          Find this in your Cloudflare Access application settings
                        }
                      </mat-hint>
                    </mat-form-field>
                    <button mat-stroked-button
                            (click)="saveCloudflareAccessAud()"
                            [disabled]="!cfAccessAud || cfSavingAud">
                      <mat-spinner diameter="18" *ngIf="cfSavingAud"></mat-spinner>
                      <mat-icon *ngIf="!cfSavingAud">vpn_key</mat-icon>
                      Save AUD
                    </button>
                  </div>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Protected Paths</mat-label>
                    <input matInput
                           [(ngModel)]="cfProtectedPathsStr"
                           placeholder="/superadmin, /superadmin/*">
                    <mat-hint>Comma-separated paths that require Cloudflare Access authentication</mat-hint>
                  </mat-form-field>

                  <div class="test-section">
                    <button mat-stroked-button
                            color="primary"
                            (click)="testCloudflareConnection()"
                            [disabled]="cfTesting || !cfAccessAudConfigured">
                      <mat-spinner diameter="18" *ngIf="cfTesting"></mat-spinner>
                      <mat-icon *ngIf="!cfTesting">verified</mat-icon>
                      Test Configuration
                    </button>
                    @if (cfTestResult) {
                      <span class="test-result" [class.success]="cfTestSuccess">
                        <mat-icon>{{ cfTestSuccess ? 'check_circle' : 'error' }}</mat-icon>
                        {{ cfTestResult }}
                      </span>
                    }
                  </div>

                  <div class="actions">
                    <button mat-raised-button color="primary"
                            (click)="saveCloudflareSettings()"
                            [disabled]="cfSaving">
                      <mat-spinner diameter="20" *ngIf="cfSaving"></mat-spinner>
                      <mat-icon *ngIf="!cfSaving">save</mat-icon>
                      <span *ngIf="!cfSaving">Save Cloudflare Settings</span>
                    </button>
                  </div>
                </div>
              }
            </div>
          }
        </mat-card-content>
      </mat-card>

      <!-- Log Forwarding Settings Card -->
      <mat-card>
        <mat-card-header>
          <mat-card-title>
            <mat-icon>forward_to_inbox</mat-icon>
            Log Forwarding (OpenTelemetry)
          </mat-card-title>
          <mat-card-subtitle>
            Forward application logs to external logging services via OTLP
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          @if (logForwardingLoading) {
            <div class="loading">
              <mat-spinner diameter="40"></mat-spinner>
            </div>
          } @else {
            <div class="form-section">
              <h3>Log Forwarding Configuration</h3>
              <p class="hint">Send logs to Grafana Loki, Datadog, New Relic, or any OTLP-compatible backend</p>

              <div class="toggle-row">
                <mat-slide-toggle
                  [(ngModel)]="lfEnabled"
                  (change)="saveLogForwardingSettings()"
                  color="primary">
                  Enable Log Forwarding
                </mat-slide-toggle>
                <span class="status-badge" [class.enabled]="lfEnabled">
                  {{ lfEnabled ? 'Active' : 'Disabled' }}
                </span>
              </div>

              @if (lfEnabled) {
                <div class="log-forwarding-config">
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>OTLP Endpoint URL</mat-label>
                    <input matInput [(ngModel)]="lfEndpointUrl" placeholder="https://otlp-gateway-prod-eu-west-2.grafana.net/otlp">
                    <mat-hint>OTLP endpoint (e.g., Grafana: otlp-gateway-*.grafana.net/otlp)</mat-hint>
                  </mat-form-field>

                  <div class="form-row">
                    <mat-form-field appearance="outline">
                      <mat-label>Auth Type</mat-label>
                      <select matNativeControl [(ngModel)]="lfAuthType">
                        <option value="api_key">API Key</option>
                        <option value="bearer">Bearer Token</option>
                        <option value="header">Custom Header</option>
                        <option value="none">None</option>
                      </select>
                      <mat-hint>Authentication method</mat-hint>
                    </mat-form-field>

                    @if (lfAuthType === 'header') {
                      <mat-form-field appearance="outline">
                        <mat-label>Auth Header Name</mat-label>
                        <input matInput [(ngModel)]="lfAuthHeaderName" placeholder="Authorization">
                        <mat-hint>Custom header name for auth</mat-hint>
                      </mat-form-field>
                    }
                  </div>

                  @if (lfAuthType !== 'none') {
                    <div class="api-key-section">
                      <mat-form-field appearance="outline" class="full-width">
                        <mat-label>API Key / Token</mat-label>
                        <input matInput
                               [type]="showLfApiKey ? 'text' : 'password'"
                               [(ngModel)]="lfApiKey"
                               placeholder="Enter API key or token">
                        <button mat-icon-button matSuffix
                                (click)="showLfApiKey = !showLfApiKey"
                                type="button"
                                matTooltip="{{ showLfApiKey ? 'Hide' : 'Show' }} API Key">
                          <mat-icon>{{ showLfApiKey ? 'visibility_off' : 'visibility' }}</mat-icon>
                        </button>
                        <mat-hint>
                          @if (lfApiKeyConfigured && !lfApiKey) {
                            API key is configured (hidden for security)
                          } @else {
                            Enter your OTLP endpoint API key/token
                          }
                        </mat-hint>
                      </mat-form-field>
                      <button mat-stroked-button
                              (click)="saveLogForwardingApiKey()"
                              [disabled]="!lfApiKey || lfSavingKey">
                        <mat-spinner diameter="18" *ngIf="lfSavingKey"></mat-spinner>
                        <mat-icon *ngIf="!lfSavingKey">vpn_key</mat-icon>
                        Save Key
                      </button>
                    </div>
                  }

                  <div class="form-row">
                    <mat-form-field appearance="outline">
                      <mat-label>Log Level</mat-label>
                      <select matNativeControl [(ngModel)]="lfLogLevel">
                        <option value="DEBUG">DEBUG (All logs)</option>
                        <option value="INFO">INFO (Default)</option>
                        <option value="WARNING">WARNING</option>
                        <option value="ERROR">ERROR only</option>
                      </select>
                      <mat-hint>Minimum level to forward</mat-hint>
                    </mat-form-field>

                    <mat-form-field appearance="outline">
                      <mat-label>Service Name</mat-label>
                      <input matInput [(ngModel)]="lfServiceName" placeholder="architecture-decisions">
                      <mat-hint>Service identifier in logs</mat-hint>
                    </mat-form-field>

                    <mat-form-field appearance="outline">
                      <mat-label>Environment</mat-label>
                      <input matInput [(ngModel)]="lfEnvironment" placeholder="production">
                      <mat-hint>Environment tag</mat-hint>
                    </mat-form-field>
                  </div>

                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Custom Headers (JSON)</mat-label>
                    <textarea matInput
                              [(ngModel)]="lfCustomHeaders"
                              placeholder='{"X-Scope-OrgID": "my-org"}'
                              rows="2"></textarea>
                    <mat-hint>Additional HTTP headers as JSON object</mat-hint>
                  </mat-form-field>

                  <div class="test-section">
                    <button mat-stroked-button
                            color="primary"
                            (click)="testLogForwardingConnection()"
                            [disabled]="lfTesting || !lfEndpointUrl">
                      <mat-spinner diameter="18" *ngIf="lfTesting"></mat-spinner>
                      <mat-icon *ngIf="!lfTesting">send</mat-icon>
                      Test Connection
                    </button>
                    @if (lfTestResult) {
                      <span class="test-result" [class.success]="lfTestSuccess">
                        <mat-icon>{{ lfTestSuccess ? 'check_circle' : 'error' }}</mat-icon>
                        {{ lfTestResult }}
                      </span>
                    }
                  </div>

                  <div class="actions">
                    <button mat-raised-button color="primary"
                            (click)="saveLogForwardingSettings()"
                            [disabled]="lfSaving">
                      <mat-spinner diameter="20" *ngIf="lfSaving"></mat-spinner>
                      <mat-icon *ngIf="!lfSaving">save</mat-icon>
                      <span *ngIf="!lfSaving">Save Log Forwarding Settings</span>
                    </button>
                  </div>
                </div>
              }
            </div>
          }
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .settings-container {
      max-width: 800px;
      margin: 0 auto;
      padding: 24px;
    }

    h1 {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
      color: #333;
    }

    h1 mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
    }

    mat-card {
      margin-bottom: 24px;
    }

    mat-card-header {
      margin-bottom: 16px;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 40px;
    }

    .form-section {
      margin-bottom: 24px;
      padding: 16px;
      background: #f9f9f9;
      border-radius: 8px;
    }

    .form-section h3 {
      margin: 0 0 8px 0;
      color: #1976d2;
    }

    .form-section .hint {
      margin: 0 0 16px 0;
      color: #666;
      font-size: 14px;
    }

    mat-form-field {
      width: 200px;
    }

    .limit-info {
      margin-top: 16px;
      padding: 12px;
      background: #e3f2fd;
      border-radius: 4px;
      display: flex;
      align-items: center;
    }

    .limit-info span {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }

    .limit-info .unlimited {
      color: #2e7d32;
    }

    .limit-info .limited {
      color: #1565c0;
    }

    .limit-info mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .actions {
      display: flex;
      gap: 12px;
      margin-top: 24px;
    }

    .actions button {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .actions mat-spinner {
      margin-right: 8px;
    }

    /* Analytics styles */
    .toggle-row {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 16px;
    }

    .status-badge {
      padding: 4px 12px;
      border-radius: 16px;
      font-size: 12px;
      font-weight: 500;
      background: #f5f5f5;
      color: #666;
    }

    .status-badge.enabled {
      background: #e8f5e9;
      color: #2e7d32;
    }

    .analytics-config {
      margin-top: 16px;
    }

    .full-width {
      width: 100%;
    }

    .api-key-section {
      display: flex;
      gap: 12px;
      align-items: flex-start;
      margin: 16px 0;
    }

    .api-key-section mat-form-field {
      flex: 1;
    }

    .api-key-section button {
      margin-top: 4px;
    }

    .privacy-hint {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: #666;
    }

    .privacy-hint mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .test-section {
      display: flex;
      align-items: center;
      gap: 16px;
      margin: 16px 0;
      padding: 16px;
      background: #fff;
      border-radius: 4px;
      border: 1px solid #e0e0e0;
    }

    .test-result {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      color: #f44336;
    }

    .test-result.success {
      color: #2e7d32;
    }

    mat-accordion {
      display: block;
      margin-top: 16px;
    }

    mat-expansion-panel {
      margin-bottom: 8px;
    }

    mat-panel-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    mat-panel-title mat-icon {
      color: #1976d2;
    }

    .event-list {
      max-height: 400px;
      overflow-y: auto;
    }

    .event-item {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 8px 0;
      border-bottom: 1px solid #f0f0f0;
    }

    .event-item:last-child {
      border-bottom: none;
    }

    .endpoint-name {
      min-width: 200px;
      font-family: monospace;
      font-size: 13px;
      color: #666;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .event-name-field {
      flex: 1;
      min-width: 150px;
    }

    .event-name-field input {
      font-family: monospace;
    }

    .panel-actions {
      padding-top: 16px;
      border-top: 1px solid #e0e0e0;
      margin-top: 16px;
    }

    /* Cloudflare styles */
    .security-info {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      background: #fff3e0;
      border-radius: 4px;
      margin-top: 16px;
      color: #e65100;
    }

    .security-info.active {
      background: #e8f5e9;
      color: #2e7d32;
    }

    .security-info mat-icon {
      font-size: 24px;
      width: 24px;
      height: 24px;
    }

    .cloudflare-config {
      margin-top: 16px;
    }

    .aud-section {
      display: flex;
      gap: 12px;
      align-items: flex-start;
      margin: 16px 0;
    }

    .aud-section mat-form-field {
      flex: 1;
    }

    .aud-section button {
      margin-top: 4px;
    }

    /* Log forwarding styles */
    .log-forwarding-config {
      margin-top: 16px;
    }

    .form-row {
      display: flex;
      gap: 16px;
      margin: 16px 0;
      flex-wrap: wrap;
    }

    .form-row mat-form-field {
      flex: 1;
      min-width: 150px;
    }

    select[matNativeControl] {
      height: 24px;
    }

    textarea {
      font-family: monospace;
      font-size: 13px;
    }
  `]
})
export class SuperadminSettingsComponent implements OnInit {
  sessionForm: FormGroup;
  licensingForm: FormGroup;
  loading = true;
  saving = false;
  licensingLoading = true;
  licensingSaving = false;
  defaults = {
    admin_session_timeout_hours: 1,
    user_session_timeout_hours: 8
  };
  licensingDefaults = {
    max_users_per_tenant: 5
  };

  // Analytics settings
  analyticsLoading = true;
  analyticsSaving = false;
  analyticsSavingKey = false;
  analyticsSavingMappings = false;
  analyticsTesting = false;
  analyticsEnabled = false;
  analyticsHost = 'https://eu.i.posthog.com';
  analyticsApiKey = '';
  analyticsApiKeyConfigured = false;
  analyticsPersonProfiling = false;
  analyticsExceptionCapture = false;
  showApiKey = false;
  analyticsTestResult = '';
  analyticsTestSuccess = false;
  analyticsEventMappings: { [key: string]: string } = {};
  analyticsCategories: { [key: string]: EndpointCategory } | null = null;
  analyticsDefaultMappings: { [key: string]: string } = {};

  // Cloudflare settings
  cloudflareLoading = true;
  cfSaving = false;
  cfSavingAud = false;
  cfTesting = false;
  cfOriginCheckEnabled = true;
  cfAccessEnabled = false;
  cfAccessTeamDomain = '';
  cfAccessAud = '';
  cfAccessAudConfigured = false;
  cfProtectedPathsStr = '/superadmin, /superadmin/*';
  showAccessAud = false;
  cfTestResult = '';
  cfTestSuccess = false;

  // Log forwarding settings
  logForwardingLoading = true;
  lfSaving = false;
  lfSavingKey = false;
  lfTesting = false;
  lfEnabled = false;
  lfEndpointUrl = '';
  lfAuthType: 'api_key' | 'bearer' | 'header' | 'none' = 'api_key';
  lfAuthHeaderName = 'Authorization';
  lfApiKey = '';
  lfApiKeyConfigured = false;
  showLfApiKey = false;
  lfLogLevel: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' = 'INFO';
  lfServiceName = 'architecture-decisions';
  lfEnvironment = 'production';
  lfCustomHeaders = '{}';
  lfTestResult = '';
  lfTestSuccess = false;

  constructor(
    private http: HttpClient,
    private fb: FormBuilder,
    private snackBar: MatSnackBar
  ) {
    this.sessionForm = this.fb.group({
      admin_session_timeout_hours: [1, [Validators.required, Validators.min(1), Validators.max(24)]],
      user_session_timeout_hours: [8, [Validators.required, Validators.min(1), Validators.max(168)]]
    });
    this.licensingForm = this.fb.group({
      max_users_per_tenant: [5, [Validators.required, Validators.min(0), Validators.max(10000)]]
    });
  }

  ngOnInit() {
    this.loadSettings();
    this.loadLicensingSettings();
    this.loadAnalyticsSettings();
    this.loadCloudflareSettings();
    this.loadLogForwardingSettings();
  }

  loadSettings() {
    this.loading = true;
    this.http.get<SessionSettings>('/api/admin/settings/session').subscribe({
      next: (settings) => {
        this.sessionForm.patchValue({
          admin_session_timeout_hours: settings.admin_session_timeout_hours,
          user_session_timeout_hours: settings.user_session_timeout_hours
        });
        this.defaults = settings.defaults;
        this.loading = false;
      },
      error: (error) => {
        this.snackBar.open('Failed to load settings', 'Close', { duration: 3000 });
        this.loading = false;
      }
    });
  }

  loadLicensingSettings() {
    this.licensingLoading = true;
    this.http.get<LicensingSettings>('/api/admin/settings/licensing').subscribe({
      next: (settings) => {
        this.licensingForm.patchValue({
          max_users_per_tenant: settings.max_users_per_tenant
        });
        this.licensingDefaults = settings.defaults;
        this.licensingLoading = false;
      },
      error: (error) => {
        this.snackBar.open('Failed to load licensing settings', 'Close', { duration: 3000 });
        this.licensingLoading = false;
      }
    });
  }

  saveSettings() {
    if (!this.sessionForm.valid) return;

    this.saving = true;
    this.http.post('/api/admin/settings/session', this.sessionForm.value).subscribe({
      next: () => {
        this.snackBar.open('Settings saved successfully', 'Close', { duration: 3000 });
        this.saving = false;
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to save settings', 'Close', { duration: 3000 });
        this.saving = false;
      }
    });
  }

  saveLicensingSettings() {
    if (!this.licensingForm.valid) return;

    this.licensingSaving = true;
    this.http.post('/api/admin/settings/licensing', this.licensingForm.value).subscribe({
      next: () => {
        this.snackBar.open('Licensing settings saved successfully', 'Close', { duration: 3000 });
        this.licensingSaving = false;
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to save licensing settings', 'Close', { duration: 3000 });
        this.licensingSaving = false;
      }
    });
  }

  resetToDefaults() {
    this.sessionForm.patchValue({
      admin_session_timeout_hours: this.defaults.admin_session_timeout_hours,
      user_session_timeout_hours: this.defaults.user_session_timeout_hours
    });
  }

  resetLicensingToDefaults() {
    this.licensingForm.patchValue({
      max_users_per_tenant: this.licensingDefaults.max_users_per_tenant
    });
  }

  // Analytics methods
  loadAnalyticsSettings() {
    this.analyticsLoading = true;
    this.http.get<AnalyticsSettings>('/api/admin/settings/analytics').subscribe({
      next: (settings) => {
        this.analyticsEnabled = settings.enabled;
        this.analyticsHost = settings.host;
        this.analyticsPersonProfiling = settings.person_profiling;
        this.analyticsExceptionCapture = settings.exception_capture;
        this.analyticsApiKeyConfigured = settings.api_key_configured;
        this.analyticsEventMappings = { ...settings.event_mappings };
        this.analyticsDefaultMappings = { ...settings.event_mappings };
        this.analyticsCategories = settings.categories;
        this.analyticsLoading = false;
      },
      error: (error) => {
        this.snackBar.open('Failed to load analytics settings', 'Close', { duration: 3000 });
        this.analyticsLoading = false;
      }
    });
  }

  saveAnalyticsSettings() {
    this.analyticsSaving = true;
    this.http.post('/api/admin/settings/analytics', {
      enabled: this.analyticsEnabled,
      host: this.analyticsHost,
      person_profiling: this.analyticsPersonProfiling,
      exception_capture: this.analyticsExceptionCapture
    }).subscribe({
      next: () => {
        this.snackBar.open('Analytics settings saved', 'Close', { duration: 3000 });
        this.analyticsSaving = false;
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to save analytics settings', 'Close', { duration: 3000 });
        this.analyticsSaving = false;
      }
    });
  }

  saveAnalyticsApiKey() {
    if (!this.analyticsApiKey) return;

    this.analyticsSavingKey = true;
    this.http.put('/api/admin/settings/analytics/api-key', {
      api_key: this.analyticsApiKey
    }).subscribe({
      next: () => {
        this.snackBar.open('API key saved successfully', 'Close', { duration: 3000 });
        this.analyticsApiKeyConfigured = true;
        this.analyticsApiKey = ''; // Clear for security
        this.analyticsSavingKey = false;
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to save API key', 'Close', { duration: 3000 });
        this.analyticsSavingKey = false;
      }
    });
  }

  testAnalyticsConnection() {
    this.analyticsTesting = true;
    this.analyticsTestResult = '';
    this.http.post<{ message: string }>('/api/admin/settings/analytics/test', {}).subscribe({
      next: (response) => {
        this.analyticsTestResult = response.message;
        this.analyticsTestSuccess = true;
        this.analyticsTesting = false;
      },
      error: (error) => {
        this.analyticsTestResult = error.error?.error || 'Connection test failed';
        this.analyticsTestSuccess = false;
        this.analyticsTesting = false;
      }
    });
  }

  saveEventMappings() {
    this.analyticsSavingMappings = true;
    this.http.post('/api/admin/settings/analytics', {
      event_mappings: this.analyticsEventMappings
    }).subscribe({
      next: () => {
        this.snackBar.open('Event mappings saved', 'Close', { duration: 3000 });
        this.analyticsSavingMappings = false;
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to save event mappings', 'Close', { duration: 3000 });
        this.analyticsSavingMappings = false;
      }
    });
  }

  getCategoryKeys(): string[] {
    return this.analyticsCategories ? Object.keys(this.analyticsCategories) : [];
  }

  resetCategoryMappings(categoryKey: string) {
    if (!this.analyticsCategories) return;

    const category = this.analyticsCategories[categoryKey];
    for (const endpoint of category.endpoints) {
      this.analyticsEventMappings[endpoint] = this.analyticsDefaultMappings[endpoint];
    }
    this.snackBar.open(`${category.name} mappings reset to defaults`, 'Close', { duration: 2000 });
  }

  resetAllMappings() {
    this.http.post<{ message: string; event_mappings: { [key: string]: string } }>('/api/admin/settings/analytics/reset-mappings', {}).subscribe({
      next: (response) => {
        this.analyticsEventMappings = { ...response.event_mappings };
        this.analyticsDefaultMappings = { ...response.event_mappings };
        this.snackBar.open('All event mappings reset to defaults', 'Close', { duration: 3000 });
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to reset mappings', 'Close', { duration: 3000 });
      }
    });
  }

  // Cloudflare methods
  loadCloudflareSettings() {
    this.cloudflareLoading = true;
    this.http.get<CloudflareSettings>('/api/admin/settings/cloudflare').subscribe({
      next: (settings) => {
        this.cfOriginCheckEnabled = settings.origin_check_enabled;
        this.cfAccessEnabled = settings.access_enabled;
        this.cfAccessTeamDomain = settings.access_team_domain;
        this.cfAccessAudConfigured = settings.access_aud_configured;
        this.cfProtectedPathsStr = settings.protected_paths.join(', ');
        this.cloudflareLoading = false;
      },
      error: (error) => {
        this.snackBar.open('Failed to load Cloudflare settings', 'Close', { duration: 3000 });
        this.cloudflareLoading = false;
      }
    });
  }

  saveCloudflareSettings() {
    this.cfSaving = true;
    const protectedPaths = this.cfProtectedPathsStr.split(',').map(p => p.trim()).filter(p => p);

    this.http.post('/api/admin/settings/cloudflare', {
      origin_check_enabled: this.cfOriginCheckEnabled,
      access_enabled: this.cfAccessEnabled,
      access_team_domain: this.cfAccessTeamDomain,
      protected_paths: protectedPaths
    }).subscribe({
      next: () => {
        this.snackBar.open('Cloudflare settings saved', 'Close', { duration: 3000 });
        this.cfSaving = false;
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to save Cloudflare settings', 'Close', { duration: 3000 });
        this.cfSaving = false;
      }
    });
  }

  saveCloudflareAccessAud() {
    if (!this.cfAccessAud) return;

    this.cfSavingAud = true;
    this.http.put('/api/admin/settings/cloudflare/access-aud', {
      access_aud: this.cfAccessAud
    }).subscribe({
      next: () => {
        this.snackBar.open('Access AUD saved', 'Close', { duration: 3000 });
        this.cfAccessAudConfigured = true;
        this.cfAccessAud = ''; // Clear for security
        this.cfSavingAud = false;
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to save Access AUD', 'Close', { duration: 3000 });
        this.cfSavingAud = false;
      }
    });
  }

  testCloudflareConnection() {
    this.cfTesting = true;
    this.cfTestResult = '';
    this.http.post<{ success: boolean; message: string }>('/api/admin/settings/cloudflare/test', {}).subscribe({
      next: (response) => {
        this.cfTestResult = response.message;
        this.cfTestSuccess = response.success;
        this.cfTesting = false;
      },
      error: (error) => {
        this.cfTestResult = error.error?.message || 'Connection test failed';
        this.cfTestSuccess = false;
        this.cfTesting = false;
      }
    });
  }

  // Log forwarding methods
  loadLogForwardingSettings() {
    this.logForwardingLoading = true;
    this.http.get<LogForwardingSettings>('/api/admin/settings/log-forwarding').subscribe({
      next: (settings) => {
        this.lfEnabled = settings.enabled;
        this.lfEndpointUrl = settings.endpoint_url;
        this.lfAuthType = settings.auth_type;
        this.lfAuthHeaderName = settings.auth_header_name;
        this.lfApiKeyConfigured = settings.has_api_key;
        this.lfLogLevel = settings.log_level;
        this.lfServiceName = settings.service_name;
        this.lfEnvironment = settings.environment;
        this.lfCustomHeaders = settings.custom_headers;
        this.logForwardingLoading = false;
      },
      error: (error) => {
        this.snackBar.open('Failed to load log forwarding settings', 'Close', { duration: 3000 });
        this.logForwardingLoading = false;
      }
    });
  }

  saveLogForwardingSettings() {
    this.lfSaving = true;
    this.http.post('/api/admin/settings/log-forwarding', {
      enabled: this.lfEnabled,
      endpoint_url: this.lfEndpointUrl,
      auth_type: this.lfAuthType,
      auth_header_name: this.lfAuthHeaderName,
      log_level: this.lfLogLevel,
      service_name: this.lfServiceName,
      environment: this.lfEnvironment,
      custom_headers: this.lfCustomHeaders
    }).subscribe({
      next: () => {
        this.snackBar.open('Log forwarding settings saved', 'Close', { duration: 3000 });
        this.lfSaving = false;
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to save log forwarding settings', 'Close', { duration: 3000 });
        this.lfSaving = false;
      }
    });
  }

  saveLogForwardingApiKey() {
    if (!this.lfApiKey) return;

    this.lfSavingKey = true;
    this.http.put('/api/admin/settings/log-forwarding/api-key', {
      api_key: this.lfApiKey
    }).subscribe({
      next: () => {
        this.snackBar.open('API key saved successfully', 'Close', { duration: 3000 });
        this.lfApiKeyConfigured = true;
        this.lfApiKey = ''; // Clear for security
        this.lfSavingKey = false;
      },
      error: (error) => {
        this.snackBar.open(error.error?.error || 'Failed to save API key', 'Close', { duration: 3000 });
        this.lfSavingKey = false;
      }
    });
  }

  testLogForwardingConnection() {
    this.lfTesting = true;
    this.lfTestResult = '';
    this.http.post<{ success: boolean; message: string }>('/api/admin/settings/log-forwarding/test', {}).subscribe({
      next: (response) => {
        this.lfTestResult = response.message;
        this.lfTestSuccess = response.success;
        this.lfTesting = false;
      },
      error: (error) => {
        this.lfTestResult = error.error?.message || 'Connection test failed';
        this.lfTestSuccess = false;
        this.lfTesting = false;
      }
    });
  }
}
