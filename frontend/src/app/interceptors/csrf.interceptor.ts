import { Injectable } from '@angular/core';
import {
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpInterceptor,
  HttpResponse,
  HttpInterceptorFn,
  HttpHandlerFn
} from '@angular/common/http';
import { Observable, tap } from 'rxjs';

/**
 * CSRF Token Interceptor
 *
 * This interceptor handles CSRF protection for all API requests:
 * 1. Captures CSRF tokens from response headers (X-CSRF-Token)
 * 2. Adds the token to all state-changing requests (POST, PUT, DELETE, PATCH)
 *
 * Security Note:
 * - CSRF tokens protect against cross-site request forgery attacks
 * - Combined with SameSite cookie settings, this provides defense-in-depth
 */

// Store the current CSRF token
let csrfToken: string | null = null;

/**
 * Functional interceptor for Angular 18+
 */
export const csrfInterceptor: HttpInterceptorFn = (req: HttpRequest<unknown>, next: HttpHandlerFn): Observable<HttpEvent<unknown>> => {
  // Clone the request and add CSRF token for state-changing methods
  let modifiedReq = req;

  if (csrfToken && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(req.method)) {
    modifiedReq = req.clone({
      setHeaders: {
        'X-CSRF-Token': csrfToken
      }
    });
  }

  return next(modifiedReq).pipe(
    tap(event => {
      // Capture CSRF token from response headers
      if (event instanceof HttpResponse) {
        const newToken = event.headers.get('X-CSRF-Token');
        if (newToken) {
          csrfToken = newToken;
        }
      }
    })
  );
};

/**
 * Helper function to get current CSRF token (for debugging/testing)
 */
export function getCurrentCsrfToken(): string | null {
  return csrfToken;
}

/**
 * Helper function to clear CSRF token (called on logout)
 */
export function clearCsrfToken(): void {
  csrfToken = null;
}
