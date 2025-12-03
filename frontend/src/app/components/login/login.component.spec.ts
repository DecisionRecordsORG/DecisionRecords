import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { LoginComponent } from './login.component';
import { AuthService } from '../../services/auth.service';

describe('LoginComponent', () => {
  let component: LoginComponent;
  let fixture: ComponentFixture<LoginComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LoginComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        AuthService
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should create', () => {
    // Handle AuthService's initial call
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });

    fixture.detectChanges();

    // Handle component's SSO configs call
    httpMock.expectOne('/api/auth/sso-configs').flush([]);

    expect(component).toBeTruthy();
  });

  it('should have empty login form initially', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    expect(component.loginForm.get('username')?.value).toBe('');
    expect(component.loginForm.get('password')?.value).toBe('');
  }));

  it('should show validation errors for empty form', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    expect(component.loginForm.valid).toBeFalse();
  }));

  it('should be valid when form is filled', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    component.loginForm.setValue({
      username: 'admin',
      password: 'changeme'
    });

    expect(component.loginForm.valid).toBeTrue();
  }));

  it('should load SSO configs on init', fakeAsync(() => {
    const mockSSOConfigs = [
      { id: 1, domain: 'example.com', provider_name: 'Google', enabled: true }
    ];

    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush(mockSSOConfigs);
    tick();

    expect(component.ssoConfigs.length).toBe(1);
    expect(component.ssoConfigs[0].provider_name).toBe('Google');
  }));

  it('should toggle password visibility', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    expect(component.hidePassword).toBeTrue();
    component.hidePassword = !component.hidePassword;
    expect(component.hidePassword).toBeFalse();
  }));

  it('should set error message on login failure', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    component.loginForm.setValue({
      username: 'admin',
      password: 'wrongpassword'
    });

    component.onSubmit();

    const loginReq = httpMock.expectOne('/auth/local');
    loginReq.flush({ error: 'Invalid username or password' }, { status: 401, statusText: 'Unauthorized' });
    tick();

    expect(component.error).toBeTruthy();
    expect(component.isLoading).toBeFalse();
  }));

  it('should not submit if form is invalid', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    component.onSubmit();

    // No HTTP request should be made
    httpMock.expectNone('/auth/local');
    expect(component.isLoading).toBeFalse();
  }));
});
