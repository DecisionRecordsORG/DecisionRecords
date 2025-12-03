import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, catchError, of, BehaviorSubject } from 'rxjs';
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
    this.loadCurrentUser();
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

  loadCurrentUser(): void {
    this.isLoadingSubject.next(true);
    this.http.get<User | MasterAccount>(`${this.apiUrl}/user/me`).pipe(
      tap(user => {
        // Check if it's a master account (has username instead of email)
        const isMaster = 'username' in user && !('email' in user);
        this.currentUserSubject.next({ user, isMaster });
        this.isLoadingSubject.next(false);
      }),
      catchError(() => {
        this.currentUserSubject.next(null);
        this.isLoadingSubject.next(false);
        return of(null);
      })
    ).subscribe();
  }

  getSSOConfigs(): Observable<SSOConfig[]> {
    return this.http.get<SSOConfig[]>(`${this.apiUrl}/auth/sso-configs`);
  }

  loginLocal(username: string, password: string): Observable<any> {
    return this.http.post(`/auth/local`, { username, password }).pipe(
      tap(() => this.loadCurrentUser())
    );
  }

  logout(): Observable<any> {
    return this.http.get('/logout').pipe(
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
