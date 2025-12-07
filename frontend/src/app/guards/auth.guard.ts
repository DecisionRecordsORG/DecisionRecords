import { inject } from '@angular/core';
import { Router, CanActivateFn, ActivatedRouteSnapshot } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../services/auth.service';
import { map, take, filter, switchMap, catchError } from 'rxjs/operators';
import { of } from 'rxjs';
import { User } from '../models/decision.model';

interface DomainStatus {
  domain: string;
  status: 'pending' | 'approved' | 'rejected' | 'unknown';
  message: string;
}

export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.isLoading$.pipe(
    filter(isLoading => !isLoading),
    take(1),
    map(() => {
      if (authService.isAuthenticated) {
        return true;
      }
      // Redirect to landing page
      router.navigate(['/']);
      return false;
    })
  );
};

export const adminGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.isLoading$.pipe(
    filter(isLoading => !isLoading),
    take(1),
    map(() => {
      if (authService.isAdmin) {
        return true;
      }
      // Redirect to tenant dashboard if authenticated
      if (authService.isAuthenticated && !authService.isMasterAccount) {
        const user = authService.currentUser?.user as User;
        router.navigate([`/${user.sso_domain}`]);
      } else {
        router.navigate(['/']);
      }
      return false;
    })
  );
};

export const masterGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.isLoading$.pipe(
    filter(isLoading => !isLoading),
    take(1),
    map(() => {
      if (authService.isMasterAccount) {
        return true;
      }
      router.navigate(['/superadmin']);
      return false;
    })
  );
};

export const guestGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.isLoading$.pipe(
    filter(isLoading => !isLoading),
    take(1),
    map(() => {
      if (!authService.isAuthenticated) {
        return true;
      }
      // Redirect authenticated users to their appropriate dashboard
      if (authService.isMasterAccount) {
        router.navigate(['/superadmin/dashboard']);
      } else {
        const user = authService.currentUser?.user as User;
        router.navigate([`/${user.sso_domain}`]);
      }
      return false;
    })
  );
};

export const tenantGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const http = inject(HttpClient);
  const tenant = route.paramMap.get('tenant');

  return authService.isLoading$.pipe(
    filter(isLoading => !isLoading),
    take(1),
    switchMap(() => {
      // SECURITY: Master/Super admin accounts should NOT access tenant data
      // This prevents a compromised super admin account from accessing tenant data
      // Super admin should only manage tenants through the admin dashboard
      if (authService.isMasterAccount) {
        router.navigate(['/superadmin/dashboard']);
        return of(false);
      }

      // Check if user belongs to this tenant
      if (authService.isAuthenticated) {
        const user = authService.currentUser?.user as User;
        if (user.sso_domain !== tenant) {
          // User doesn't belong to this tenant, redirect to their tenant
          router.navigate([`/${user.sso_domain}`]);
          return of(false);
        }

        // User belongs to this tenant - check domain approval status
        return http.get<DomainStatus>(`/api/domains/check/${tenant}`).pipe(
          map(domainStatus => {
            if (domainStatus.status === 'approved') {
              return true;
            } else if (domainStatus.status === 'pending') {
              // Redirect to pending page
              router.navigate([`/${tenant}/pending`]);
              return false;
            } else if (domainStatus.status === 'rejected') {
              // Redirect to pending page (will show rejection message)
              router.navigate([`/${tenant}/pending`]);
              return false;
            }
            // Unknown status - allow access (legacy tenants without approval record)
            return true;
          }),
          catchError(() => {
            // API error - allow access (might be legacy tenant)
            return of(true);
          })
        );
      }

      // Not authenticated, redirect to tenant login
      router.navigate([`/${tenant}/login`]);
      return of(false);
    })
  );
};
