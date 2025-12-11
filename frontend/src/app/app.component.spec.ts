import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { AppComponent } from './app.component';
import { AuthService } from './services/auth.service';

describe('AppComponent', () => {
  let httpMock: HttpTestingController;

  const mockUser = {
    id: 1,
    email: 'test@example.com',
    name: 'Test User',
    sso_domain: 'example.com',
    is_admin: false,
    created_at: '2024-01-01T00:00:00Z',
    last_login: '2024-01-01T00:00:00Z'
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        AuthService
      ]
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;

    // Handle AuthService's initial load
    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });

    expect(app).toBeTruthy();
  });

  it('should show navbar when authenticated', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);

    httpMock.expectOne('/api/user/me').flush(mockUser);
    tick();
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('app-navbar')).toBeTruthy();
  }));

  it('should hide navbar when not authenticated', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);

    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    tick();
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('app-navbar')).toBeFalsy();
  }));

  it('should have router outlet', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);

    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    tick();
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('router-outlet')).toBeTruthy();
  }));

  it('should render footer with About link', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);

    httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    tick();
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const footer = compiled.querySelector('.app-footer');
    expect(footer).toBeTruthy();
    expect(footer?.textContent).toContain('About');
  }));
});
