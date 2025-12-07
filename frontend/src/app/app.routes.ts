import { Routes } from '@angular/router';
import { authGuard, adminGuard, masterGuard, guestGuard, tenantGuard } from './guards/auth.guard';

export const routes: Routes = [
  // Main landing/signup page
  {
    path: '',
    loadComponent: () => import('./components/landing/landing.component').then(m => m.LandingComponent),
    canActivate: [guestGuard]
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
  // Tenant-specific routes
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
    path: ':tenant',
    loadComponent: () => import('./components/decision-list/decision-list.component').then(m => m.DecisionListComponent),
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
  {
    path: ':tenant/profile',
    loadComponent: () => import('./components/profile/profile.component').then(m => m.ProfileComponent),
    canActivate: [authGuard, tenantGuard]
  },
  // Catch-all redirect to landing
  {
    path: '**',
    redirectTo: ''
  }
];
