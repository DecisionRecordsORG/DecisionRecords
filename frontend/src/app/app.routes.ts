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
 * Public Pages:
 * - The Community Edition homepage and legal/security pages are public and
 *   indexable for decisionrecords.org
 * - App, setup, admin, tenant, and integration routes are noindex
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
    loadComponent: () => import('./components/license-acceptance/license-acceptance.component').then(m => m.LicenseAcceptanceComponent),
    data: {
      seo: {
        title: 'Accept License - Decision Records',
        description: 'Accept the Decision Records Community Edition license before completing setup.',
        robots: 'noindex, nofollow'
      }
    }
  },
  // Setup wizard for Community Edition first-time setup
  {
    path: 'setup',
    loadComponent: () => import('./components/setup-wizard/setup-wizard.component').then(m => m.SetupWizardComponent),
    data: {
      seo: {
        title: 'Setup - Decision Records',
        description: 'Set up a self-hosted Decision Records Community Edition instance.',
        robots: 'noindex, nofollow'
      }
    }
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
        .catch(() => import('./components/landing/landing.component').then(m => m.LandingComponent)),
    data: {
      seo: {
        title: 'Decision Records - Open Source Architecture Decision Records',
        description: 'Decision Records is an open source platform for capturing and preserving the reasoning behind important architecture decisions.',
        canonicalPath: '/',
        index: true
      }
    }
  },
  {
    path: 'security-features',
    loadComponent: () => import('./components/security/security.component').then(m => m.SecurityComponent),
    data: {
      seo: {
        title: 'Security Features - Decision Records',
        description: 'Explore Decision Records security features including passkeys, SSO, role-based access, tenant isolation, and audit logging.',
        canonicalPath: '/security-features',
        index: true
      }
    }
  },
  {
    path: 'security',
    loadComponent: () => import('./components/security-policy/security-policy.component').then(m => m.SecurityPolicyComponent),
    data: {
      seo: {
        title: 'Security Overview - Decision Records',
        description: 'Read how Decision Records approaches hosted service security, access control, data protection, operations, and incident response.',
        canonicalPath: '/security',
        index: true
      }
    }
  },
  {
    path: 'terms',
    loadComponent: () => import('./components/terms-of-service/terms-of-service.component').then(m => m.TermsOfServiceComponent),
    data: {
      seo: {
        title: 'Terms of Service - Decision Records',
        description: 'Terms for using the Decision Records hosted cloud service and self-hosted Community Edition.',
        canonicalPath: '/terms',
        index: true
      }
    }
  },
  {
    path: 'dpa',
    loadComponent: () => import('./components/data-processing-agreement/data-processing-agreement.component').then(m => m.DataProcessingAgreementComponent),
    data: {
      seo: {
        title: 'Data Processing Addendum - Decision Records',
        description: 'A public summary of Decision Records hosted service data processing roles, categories, security measures, and data handling.',
        canonicalPath: '/dpa',
        index: true
      }
    }
  },
  {
    path: 'sla',
    loadComponent: () => import('./components/service-level-agreement/service-level-agreement.component').then(m => m.ServiceLevelAgreementComponent),
    data: {
      seo: {
        title: 'Service Level Agreement - Decision Records',
        description: 'Availability and support commitments for Decision Records paid hosted service plans.',
        canonicalPath: '/sla',
        index: true
      }
    }
  },

  // ============================================================================
  // SUPER ADMIN ROUTES
  // ============================================================================
  {
    path: 'superadmin',
    loadComponent: () => import('./components/superadmin-login/superadmin-login.component').then(m => m.SuperadminLoginComponent),
    canActivate: [guestGuard],
    data: {
      seo: {
        title: 'Super Admin Sign In - Decision Records',
        description: 'Decision Records super admin sign in.',
        robots: 'noindex, nofollow'
      }
    }
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
  // Teams Tab (embedded in Microsoft Teams - no auth guard, Teams SDK handles auth)
  {
    path: 'teams/tab',
    loadComponent: () =>
      import('@ee/components/teams-tab/teams-tab.component')
        .then(m => m.TeamsTabComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent))
  },
  // Teams Tab Configuration (for configuring team/channel tabs)
  {
    path: 'teams/tab/config',
    loadComponent: () =>
      import('@ee/components/teams-tab/teams-tab-config.component')
        .then(m => m.TeamsTabConfigComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent))
  },
  // Teams Decision Detail Dialog (opened from Kanban board cards)
  {
    path: 'teams/decision/:id',
    loadComponent: () =>
      import('@ee/components/teams-tab/teams-decision-detail.component')
        .then(m => m.TeamsDecisionDetailComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent))
  },
  // Teams Create Decision Dialog (opened from Tab create button)
  {
    path: 'teams/create',
    loadComponent: () =>
      import('@ee/components/teams-tab/teams-create-decision.component')
        .then(m => m.TeamsCreateDecisionComponent)
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
