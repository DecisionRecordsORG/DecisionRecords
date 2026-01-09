import { Routes } from '@angular/router';
import { authGuard, adminGuard, masterGuard, guestGuard, tenantGuard } from './guards/auth.guard';

export const routes: Routes = [
  // Public landing page (Community Edition)
  // For Enterprise Edition with marketing pages, this would be replaced
  {
    path: '',
    loadComponent: () => import('./components/landing/landing.component').then(m => m.LandingComponent)
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
  // NOTE: Slack and Teams routes are Enterprise Edition features
  // They are available when running with DECISION_RECORDS_EDITION=enterprise
  // For Community Edition, these routes are disabled
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
