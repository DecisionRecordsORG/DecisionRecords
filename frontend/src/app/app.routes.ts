import { Routes } from '@angular/router';
import { authGuard, adminGuard, masterGuard, guestGuard, tenantGuard } from './guards/auth.guard';

/**
 * Application Routes
 *
 * Route Architecture:
 * - Core routes are defined here (available in all editions)
 * - Enterprise Edition routes are defined in ee/frontend/routes/ee-routes.ts
 * - EE routes are loaded dynamically at runtime if the ee/ directory exists
 *
 * Security Model:
 * - Frontend routes use lazy loading - components are only loaded when visited
 * - Backend APIs enforce edition checks via decorators (@require_slack, @require_teams)
 * - Feature flags service provides runtime visibility control
 *
 * Marketing/Public Pages:
 * - Marketing pages (blog, faq, about, integrations, pricing, etc.) are served
 *   from a separate marketing site at decisionrecords.org
 * - This app (app.decisionrecords.org) handles only authenticated tenant access
 *
 * In Community Edition builds (Dockerfile.community):
 * - The ee/ directory is physically excluded
 * - EE component imports will fail gracefully
 * - Backend returns 503 for EE API endpoints
 */

export const routes: Routes = [
  // ============================================================================
  // SYSTEM SETUP ROUTES (Community Edition)
  // ============================================================================

  // License acceptance page (shown on first-time setup)
  {
    path: 'license',
    loadComponent: () => import('./components/license-acceptance/license-acceptance.component').then(m => m.LicenseAcceptanceComponent)
  },
  // Setup wizard for Community Edition first-time setup
  {
    path: 'setup',
    loadComponent: () => import('./components/setup-wizard/setup-wizard.component').then(m => m.SetupWizardComponent)
  },

  // ============================================================================
  // LANDING PAGE
  // ============================================================================
  // Community Edition: Shows setup/signin based on system state
  // Enterprise Edition: Shows domain input for tenant discovery
  {
    path: '',
    loadComponent: () =>
      import('@ee/pages/landing/landing.component')
        .then(m => m.LandingComponent)
        .catch(() => import('./components/landing/landing.component').then(m => m.LandingComponent))
  },

  // ============================================================================
  // SUPER ADMIN ROUTES
  // ============================================================================
  {
    path: 'superadmin',
    loadComponent: () => import('./components/superadmin-login/superadmin-login.component').then(m => m.SuperadminLoginComponent),
    canActivate: [guestGuard]
  },
  {
    path: 'superadmin/dashboard',
    loadComponent: () => import('./components/master-profile/master-profile.component').then(m => m.MasterProfileComponent),
    canActivate: [masterGuard]
  },
  {
    path: 'superadmin/tenants',
    loadComponent: () => import('./components/superadmin-tenants/superadmin-tenants.component').then(m => m.SuperadminTenantsComponent),
    canActivate: [masterGuard]
  },
  {
    path: 'superadmin/email',
    loadComponent: () => import('./components/superadmin-email/superadmin-email.component').then(m => m.SuperadminEmailComponent),
    canActivate: [masterGuard]
  },
  {
    path: 'superadmin/settings',
    loadComponent: () => import('./components/superadmin-settings/superadmin-settings.component').then(m => m.SuperadminSettingsComponent),
    canActivate: [masterGuard]
  },

  // ============================================================================
  // ENTERPRISE EDITION ROUTES
  // These routes load EE components with graceful fallback if unavailable
  // ============================================================================

  // AI/MCP admin configuration (Enterprise Edition)
  {
    path: 'superadmin/ai',
    loadComponent: () =>
      import('@ee/components/ai-api/ai-api-admin/ai-api-admin.component')
        .then(m => m.AiApiAdminComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent)),
    canActivate: [masterGuard]
  },
  {
    path: 'superadmin/mcp',
    loadComponent: () =>
      import('@ee/components/mcp/mcp-admin/mcp-admin.component')
        .then(m => m.McpAdminComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent)),
    canActivate: [masterGuard]
  },

  // Slack integration (Enterprise Edition)
  {
    path: 'slack/installed',
    loadComponent: () =>
      import('@ee/components/slack/slack-installed/slack-installed.component')
        .then(m => m.SlackInstalledComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent))
  },
  {
    path: ':tenant/admin/slack',
    loadComponent: () =>
      import('@ee/components/slack/slack-admin/slack-admin.component')
        .then(m => m.SlackAdminComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent)),
    canActivate: [adminGuard, tenantGuard]
  },
  {
    path: ':tenant/slack/link',
    loadComponent: () =>
      import('@ee/components/slack/slack-link-account/slack-link-account.component')
        .then(m => m.SlackLinkAccountComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent)),
    canActivate: [authGuard]
  },

  // Teams integration (Enterprise Edition)
  {
    path: 'teams/installed',
    loadComponent: () =>
      import('@ee/components/teams/teams-installed/teams-installed.component')
        .then(m => m.TeamsInstalledComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent))
  },
  {
    path: ':tenant/admin/teams',
    loadComponent: () =>
      import('@ee/components/teams/teams-admin/teams-admin.component')
        .then(m => m.TeamsAdminComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent)),
    canActivate: [adminGuard, tenantGuard]
  },
  {
    path: ':tenant/teams/link',
    loadComponent: () =>
      import('@ee/components/teams/teams-link-account/teams-link-account.component')
        .then(m => m.TeamsLinkAccountComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent)),
    canActivate: [authGuard]
  },

  // ============================================================================
  // TENANT-SPECIFIC ROUTES
  // ============================================================================
  // NOTE: Order matters! More specific routes must come BEFORE less specific ones.
  // The ':tenant' route must be LAST among tenant routes because it matches any single segment.
  {
    path: ':tenant/login',
    loadComponent: () => import('./components/tenant-login/tenant-login.component').then(m => m.TenantLoginComponent),
    canActivate: [guestGuard]
  },
  {
    path: ':tenant/admin',
    loadComponent: () => import('./components/settings/settings.component').then(m => m.SettingsComponent),
    canActivate: [adminGuard, tenantGuard]
  },
  {
    path: ':tenant/pending',
    loadComponent: () => import('./components/pending-approval/pending-approval.component').then(m => m.PendingApprovalComponent),
    canActivate: [authGuard]  // Only require auth, not tenant guard (domain may be pending)
  },
  {
    path: ':tenant/setup',
    loadComponent: () => import('./components/account-setup/account-setup.component').then(m => m.AccountSetupComponent)
    // No guards - accessed via setup token
  },
  {
    path: ':tenant/profile',
    loadComponent: () => import('./components/profile/profile.component').then(m => m.ProfileComponent),
    canActivate: [authGuard, tenantGuard]
  },
  {
    path: ':tenant/decision/new',
    loadComponent: () => import('./components/decision-detail/decision-detail.component').then(m => m.DecisionDetailComponent),
    canActivate: [authGuard, tenantGuard]
  },
  {
    path: ':tenant/decision/:id',
    loadComponent: () => import('./components/decision-detail/decision-detail.component').then(m => m.DecisionDetailComponent),
    canActivate: [authGuard, tenantGuard]
  },
  // This must be LAST among tenant routes - it matches any single segment
  {
    path: ':tenant',
    loadComponent: () => import('./components/decision-list/decision-list.component').then(m => m.DecisionListComponent),
    canActivate: [authGuard, tenantGuard]
  },

  // ============================================================================
  // CATCH-ALL
  // ============================================================================
  // Redirect unknown routes to landing page
  {
    path: '**',
    redirectTo: ''
  }
];
