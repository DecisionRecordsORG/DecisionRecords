import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { AuthService } from './auth.service';
import { User, MasterAccount, Subscription } from '../models/decision.model';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  const mockUser: User = {
    id: 1,
    email: 'test@example.com',
    name: 'Test User',
    sso_domain: 'example.com',
    auth_type: 'webauthn',
    is_admin: false,
    has_passkey: true,
    email_verified: true,
    created_at: '2024-01-01T00:00:00Z',
    last_login: '2024-01-01T00:00:00Z'
  };

  const mockMaster: MasterAccount = {
    id: 1,
    username: 'admin',
    name: 'System Administrator',
    created_at: '2024-01-01T00:00:00Z',
    last_login: '2024-01-01T00:00:00Z'
  };

  const mockSubscription: Subscription = {
    notify_on_create: true,
    notify_on_update: false,
    notify_on_status_change: true
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        AuthService,
        provideHttpClient(),
        provideHttpClientTesting()
      ]
    });

    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    // Handle the initial loadCurrentUser call
    httpMock.expectOne('/api/user/me').flush(mockUser);
    expect(service).toBeTruthy();
  });

  describe('loadCurrentUser', () => {
    it('should load regular user', fakeAsync(() => {
      const req = httpMock.expectOne('/api/user/me');
      req.flush(mockUser);
      tick();

      expect(service.currentUser).toBeTruthy();
      expect(service.currentUser?.isMaster).toBe(false);
      expect(service.isAuthenticated).toBe(true);
      expect(service.isMasterAccount).toBe(false);
    }));

    it('should load master account', fakeAsync(() => {
      const req = httpMock.expectOne('/api/user/me');
      req.flush(mockMaster);
      tick();

      expect(service.currentUser).toBeTruthy();
      expect(service.currentUser?.isMaster).toBe(true);
      expect(service.isAuthenticated).toBe(true);
      expect(service.isMasterAccount).toBe(true);
    }));

    it('should handle unauthenticated state', fakeAsync(() => {
      const req = httpMock.expectOne('/api/user/me');
      req.flush({ error: 'Not authenticated' }, { status: 401, statusText: 'Unauthorized' });
      tick();

      expect(service.currentUser).toBeNull();
      expect(service.isAuthenticated).toBe(false);
    }));
  });

  describe('isAdmin', () => {
    it('should return true for admin user', fakeAsync(() => {
      const adminUser = { ...mockUser, is_admin: true };
      httpMock.expectOne('/api/user/me').flush(adminUser);
      tick();

      expect(service.isAdmin).toBe(true);
    }));

    it('should return true for master account', fakeAsync(() => {
      httpMock.expectOne('/api/user/me').flush(mockMaster);
      tick();

      expect(service.isAdmin).toBe(true);
    }));

    it('should return false for regular user', fakeAsync(() => {
      httpMock.expectOne('/api/user/me').flush(mockUser);
      tick();

      expect(service.isAdmin).toBe(false);
    }));
  });

  describe('getSubscription', () => {
    it('should get subscription settings', fakeAsync(() => {
      httpMock.expectOne('/api/user/me').flush(mockUser);
      tick();

      service.getSubscription().subscribe(subscription => {
        expect(subscription).toEqual(mockSubscription);
      });

      const req = httpMock.expectOne('/api/user/subscription');
      expect(req.request.method).toBe('GET');
      req.flush(mockSubscription);
    }));
  });

  describe('updateSubscription', () => {
    it('should update subscription settings', fakeAsync(() => {
      httpMock.expectOne('/api/user/me').flush(mockUser);
      tick();

      const updatedSubscription: Subscription = {
        notify_on_create: false,
        notify_on_update: true,
        notify_on_status_change: false
      };

      service.updateSubscription(updatedSubscription).subscribe(subscription => {
        expect(subscription).toEqual(updatedSubscription);
      });

      const req = httpMock.expectOne('/api/user/subscription');
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual(updatedSubscription);
      req.flush(updatedSubscription);
    }));
  });

  describe('changeMasterPassword', () => {
    it('should change master password', fakeAsync(() => {
      httpMock.expectOne('/api/user/me').flush(mockMaster);
      tick();

      service.changeMasterPassword('oldpass', 'newpass123').subscribe(response => {
        expect(response.message).toBe('Password changed successfully');
      });

      const req = httpMock.expectOne('/api/master/password');
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual({
        current_password: 'oldpass',
        new_password: 'newpass123'
      });
      req.flush({ message: 'Password changed successfully' });
    }));

    it('should handle incorrect current password', fakeAsync(() => {
      httpMock.expectOne('/api/user/me').flush(mockMaster);
      tick();

      service.changeMasterPassword('wrongpass', 'newpass123').subscribe({
        next: () => fail('should have failed'),
        error: (error) => {
          expect(error.status).toBe(400);
        }
      });

      const req = httpMock.expectOne('/api/master/password');
      req.flush({ error: 'Current password is incorrect' }, { status: 400, statusText: 'Bad Request' });
    }));
  });

  describe('logout', () => {
    it('should clear current user on logout', fakeAsync(() => {
      httpMock.expectOne('/api/user/me').flush(mockUser);
      tick();

      expect(service.isAuthenticated).toBe(true);

      service.logout().subscribe();

      const req = httpMock.expectOne('/logout');
      expect(req.request.method).toBe('GET');
      req.flush({});
      tick();

      expect(service.currentUser).toBeNull();
      expect(service.isAuthenticated).toBe(false);
    }));
  });
});
