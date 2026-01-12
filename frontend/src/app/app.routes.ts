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
 * In Community Edition builds (Dockerfile.community):
 * - The ee/ directory is physically excluded
 * - EE component imports will fail gracefully
 * - Backend returns 503 for EE API endpoints
 */

export const routes: Routes = [
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
  // Signup/signin form page
  // Enterprise Edition: Load EE landing component with full signup flow
  // Community Edition: Fall back to core landing component
  {
    path: 'signup',
    loadComponent: () =>
      import('@ee/pages/landing/landing.component')
        .then(m => m.LandingComponent)
        .catch(() => import('./components/landing/landing.component').then(m => m.LandingComponent))
  },
  // Public homepage
  // Enterprise Edition: Load EE homepage with full marketing content
  // Community Edition: Fall back to core landing component (signup form)
  {
    path: '',
    loadComponent: () =>
      import('@ee/pages/homepage/homepage.component')
        .then(m => m.HomepageComponent)
        .catch(() => import('./components/landing/landing.component').then(m => m.LandingComponent))
  },
  // Blog pages (available in both editions)
  {
    path: 'blog',
    loadComponent: () => import('./components/blog/blog-list/blog-list.component').then(m => m.BlogListComponent)
  },
  {
    path: 'blog/:slug',
    loadComponent: () => import('./components/blog/blog-post/blog-post.component').then(m => m.BlogPostComponent)
  },
  // Legal pages
  {
    path: 'terms',
    loadComponent: () => import('./components/terms-of-service/terms-of-service.component').then(m => m.TermsOfServiceComponent)
  },
  {
    path: 'security',
    loadComponent: () => import('./components/security-policy/security-policy.component').then(m => m.SecurityPolicyComponent)
  },
  {
    path: 'dpa',
    loadComponent: () => import('./components/data-processing/data-processing.component').then(m => m.DataProcessingComponent)
  },
  {
    path: 'sla',
    loadComponent: () => import('./components/service-level-agreement/service-level-agreement.component').then(m => m.ServiceLevelAgreementComponent)
  },
  // Marketing pages (Enterprise Edition - these are public pages shown in site nav)
  {
    path: 'integrations',
    loadComponent: () => import('./components/integrations/integrations.component').then(m => m.IntegrationsComponent)
  },
  {
    path: 'faq',
    loadComponent: () => import('./components/faq/faq.component').then(m => m.FaqComponent)
  },
  {
    path: 'about',
    loadComponent: () => import('./components/about/about.component').then(m => m.AboutComponent)
  },
  // Security features page - alias to security policy for now
  {
    path: 'security-features',
    loadComponent: () => import('./components/security-policy/security-policy.component').then(m => m.SecurityPolicyComponent)
  },
  // Super admin login
  {
    path: 'superadmin',
    loadComponent: () => import('./components/superadmin-login/superadmin-login.component').then(m => m.SuperadminLoginComponent),
    canActivate: [guestGuard]
  },
  // Super admin profile/dashboard
  {
    path: 'superadmin/dashboard',
    loadComponent: () => import('./components/master-profile/master-profile.component').then(m => m.MasterProfileComponent),
    canActivate: [masterGuard]
  },
  // Super admin tenant management
  {
    path: 'superadmin/tenants',
    loadComponent: () => import('./components/superadmin-tenants/superadmin-tenants.component').then(m => m.SuperadminTenantsComponent),
    canActivate: [masterGuard]
  },
  // Super admin email configuration
  {
    path: 'superadmin/email',
    loadComponent: () => import('./components/superadmin-email/superadmin-email.component').then(m => m.SuperadminEmailComponent),
    canActivate: [masterGuard]
  },
  // Super admin system settings
  {
    path: 'superadmin/settings',
    loadComponent: () => import('./components/superadmin-settings/superadmin-settings.component').then(m => m.SuperadminSettingsComponent),
    canActivate: [masterGuard]
  },
  // ============================================================================
  // ENTERPRISE EDITION ROUTES
  // These routes load EE components with graceful fallback to 404 if unavailable
  // ============================================================================

  // Slack integration (Enterprise Edition)
  // Falls back to "Feature Unavailable" in Community Edition
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
      import('@ee/components/slack/slack-integration/slack-integration.component')
        .then(m => m.SlackIntegrationComponent)
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
  // Falls back to "Feature Unavailable" in Community Edition
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
      import('@ee/components/teams/teams-integration/teams-integration.component')
        .then(m => m.TeamsIntegrationComponent)
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

  // AI/MCP configuration (Enterprise Edition)
  // Falls back to "Feature Unavailable" in Community Edition
  {
    path: 'superadmin/ai',
    loadComponent: () =>
      import('@ee/components/ai-api/ai-api-integration/ai-api-integration.component')
        .then(m => m.AiApiIntegrationComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent)),
    canActivate: [masterGuard]
  },
  {
    path: 'superadmin/mcp',
    loadComponent: () =>
      import('@ee/components/mcp/mcp-integration/mcp-integration.component')
        .then(m => m.McpIntegrationComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent)),
    canActivate: [masterGuard]
  },

  // Marketing pages (Enterprise Edition)
  // Falls back to "Feature Unavailable" in Community Edition
  {
    path: 'home',
    loadComponent: () =>
      import('@ee/pages/homepage/homepage.component')
        .then(m => m.HomepageComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent))
  },
  {
    path: 'solutions',
    loadComponent: () =>
      import('@ee/pages/solutions/solutions.component')
        .then(m => m.SolutionsComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent))
  },
  {
    path: 'pricing',
    loadComponent: () =>
      import('@ee/pages/licensing/licensing.component')
        .then(m => m.LicensingComponent)
        .catch(() => import('./components/feature-unavailable/feature-unavailable.component').then(m => m.FeatureUnavailableComponent))
  },

  // ============================================================================
  // TENANT-SPECIFIC ROUTES
  // ============================================================================
  // NOTE: Order matters! More specific routes must come BEFORE less specific ones.
  // The ':tenant' route must be LAST among tenant routes because it matches any single segment.
  // Tenant-specific routes
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
  // Catch-all redirect to landing
  {
    path: '**',
    redirectTo: ''
  }
];
