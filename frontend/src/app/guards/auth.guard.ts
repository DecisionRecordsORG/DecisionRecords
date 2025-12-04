import { inject } from '@angular/core';
import { Router, CanActivateFn, ActivatedRouteSnapshot } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { map, take, filter } from 'rxjs/operators';
import { User } from '../models/decision.model';

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
  const tenant = route.paramMap.get('tenant');

  return authService.isLoading$.pipe(
    filter(isLoading => !isLoading),
    take(1),
    map(() => {
      // Master account can access any tenant
      if (authService.isMasterAccount) {
        return true;
      }

      // Check if user belongs to this tenant
      if (authService.isAuthenticated) {
        const user = authService.currentUser?.user as User;
        if (user.sso_domain === tenant) {
          return true;
        }
        // User doesn't belong to this tenant, redirect to their tenant
        router.navigate([`/${user.sso_domain}`]);
        return false;
      }

      // Not authenticated, redirect to tenant login
      router.navigate([`/${tenant}/login`]);
      return false;
    })
  );
};
