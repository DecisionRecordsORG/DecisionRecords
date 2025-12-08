import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, catchError, of, BehaviorSubject, switchMap, map } from 'rxjs';
import { User, MasterAccount, SSOConfig, Subscription } from '../models/decision.model';

export interface CurrentUser {
  user: User | MasterAccount | null;
  isMaster: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = '/api';

  private currentUserSubject = new BehaviorSubject<CurrentUser | null>(null);
  currentUser$ = this.currentUserSubject.asObservable();

  private isLoadingSubject = new BehaviorSubject<boolean>(true);
  isLoading$ = this.isLoadingSubject.asObservable();

  constructor(private http: HttpClient) {
    this.loadCurrentUser().subscribe();
  }

  get currentUser(): CurrentUser | null {
    return this.currentUserSubject.value;
  }

  get isAuthenticated(): boolean {
    return this.currentUser !== null && this.currentUser.user !== null;
  }

  get isMasterAccount(): boolean {
    return this.currentUser?.isMaster ?? false;
  }

  get isAdmin(): boolean {
    if (this.isMasterAccount) return true;
    const user = this.currentUser?.user as User;
    return user?.is_admin ?? false;
  }

  /**
   * Check if user needs to complete credential setup (no passkey and no password).
   * Users in this state should not be able to access the app.
   */
  get needsCredentialSetup(): boolean {
    if (this.isMasterAccount) return false;
    const user = this.currentUser?.user as User;
    if (!user) return false;
    return !user.has_passkey && !user.has_password;
  }

  loadCurrentUser(): Observable<CurrentUser | null> {
    this.isLoadingSubject.next(true);
    return this.http.get<User | MasterAccount>(`${this.apiUrl}/user/me`).pipe(
      map(user => {
        // Check if it's a master account (has username instead of email)
        const isMaster = 'username' in user && !('email' in user);
        const currentUser: CurrentUser = { user, isMaster };
        this.currentUserSubject.next(currentUser);
        this.isLoadingSubject.next(false);
        return currentUser;
      }),
      catchError(() => {
        this.currentUserSubject.next(null);
        this.isLoadingSubject.next(false);
        return of(null);
      })
    );
  }

  // Legacy method that fires and forgets - use loadCurrentUser() directly when you need the result
  refreshCurrentUser(): void {
    this.loadCurrentUser().subscribe();
  }

  getSSOConfigs(): Observable<SSOConfig[]> {
    return this.http.get<SSOConfig[]>(`${this.apiUrl}/auth/sso-configs`);
  }

  loginLocal(username: string, password: string): Observable<CurrentUser | null> {
    return this.http.post(`/auth/local`, { username, password }).pipe(
      switchMap(() => this.loadCurrentUser())
    );
  }

  logout(): Observable<any> {
    return this.http.post('/api/auth/logout', {}).pipe(
      tap(() => {
        this.currentUserSubject.next(null);
      })
    );
  }

  getSubscription(): Observable<Subscription> {
    return this.http.get<Subscription>(`${this.apiUrl}/user/subscription`);
  }

  updateSubscription(subscription: Subscription): Observable<Subscription> {
    return this.http.put<Subscription>(`${this.apiUrl}/user/subscription`, subscription);
  }

  changeMasterPassword(currentPassword: string, newPassword: string): Observable<any> {
    return this.http.put(`${this.apiUrl}/master/password`, {
      current_password: currentPassword,
      new_password: newPassword
    });
  }
}
