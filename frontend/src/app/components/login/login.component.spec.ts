import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { LoginComponent } from './login.component';
import { AuthService } from '../../services/auth.service';
import { WebAuthnService } from '../../services/webauthn.service';

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
        AuthService,
        WebAuthnService
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

  it('should have empty forms initially', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    expect(component.emailForm.get('email')?.value).toBe('');
    expect(component.adminForm.get('username')?.value).toBe('');
    expect(component.adminForm.get('password')?.value).toBe('');
  }));

  it('should show validation errors for empty admin form', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    expect(component.adminForm.valid).toBeFalse();
  }));

  it('should be valid when admin form is filled', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    component.adminForm.setValue({
      username: 'admin',
      password: 'changeme'
    });

    expect(component.adminForm.valid).toBeTrue();
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

  it('should set error message on admin login failure', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    component.adminForm.setValue({
      username: 'admin',
      password: 'wrongpassword'
    });

    component.adminLogin();

    const loginReq = httpMock.expectOne('/auth/local');
    loginReq.flush({ error: 'Invalid username or password' }, { status: 401, statusText: 'Unauthorized' });
    tick();

    expect(component.error).toBeTruthy();
    expect(component.isLoading).toBeFalse();
  }));

  it('should not submit admin login if form is invalid', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    component.adminLogin();

    // No HTTP request should be made
    httpMock.expectNone('/auth/local');
    expect(component.isLoading).toBeFalse();
  }));

  it('should start in initial view', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    expect(component.currentView).toBe('initial');
  }));

  it('should check WebAuthn support on init', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    // webAuthnSupported should be defined (true or false depending on browser)
    expect(component.webAuthnSupported).toBeDefined();
  }));

  it('should have goBack method that resets to initial view', fakeAsync(() => {
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    httpMock.expectOne('/api/auth/sso-configs').flush([]);
    tick();

    component.currentView = 'webauthn';
    component.currentEmail = 'test@example.com';
    component.error = 'Some error';

    component.goBack();

    expect(component.currentView).toBe('initial');
    expect(component.currentEmail).toBe('');
    expect(component.error).toBe('');
  }));
});
