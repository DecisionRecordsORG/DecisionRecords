import { Routes } from '@angular/router';
import { authGuard, adminGuard, masterGuard, guestGuard, tenantGuard } from './guards/auth.guard';

export const routes: Routes = [
  // Public homepage with integrated signup form
  {
    path: '',
    loadComponent: () => import('./components/homepage/homepage.component').then(m => m.HomepageComponent)
  },
  // About page
  {
    path: 'about',
    loadComponent: () => import('./components/about/about.component').then(m => m.AboutComponent)
  },
  // Licensing page
  {
    path: 'licensing',
    loadComponent: () => import('./components/licensing/licensing.component').then(m => m.LicensingComponent)
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
  // Slack installation landing page (for unclaimed workspace installs)
  {
    path: 'slack/installed',
    loadComponent: () => import('./components/slack-installed/slack-installed.component').then(m => m.SlackInstalledComponent)
  },
  // Slack account linking page (when user clicks "Link Account" from Slack)
  {
    path: 'slack/link',
    loadComponent: () => import('./components/slack-link-account/slack-link-account.component').then(m => m.SlackLinkAccountComponent)
  },
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
