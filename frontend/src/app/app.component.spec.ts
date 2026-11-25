import { Component } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { AppComponent } from './app.component';
import { AuthService } from './services/auth.service';

@Component({ standalone: true, template: '' })
class BlankPageComponent {}

/**
 * The app shell: the navbar, the page outlet and the footer.
 *
 * The shell depends on where the visitor is. The landing page ("/") brings its
 * own header and footer, so the shell shows neither there; a page inside a
 * tenant (here "/acme.test") gets the navbar once someone is signed in, and the
 * footer with the version.
 */
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

  const unauthorized = { status: 401, statusText: 'Unauthorized' };
  const tenantPage = '/acme.test';

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([{ path: '**', component: BlankPageComponent }]),
        AuthService
      ]
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  /**
   * Open the app at an address and answer what the shell asks for when it
   * starts: the feature flags, the version shown in the footer, and who is
   * signed in (null for a visitor). The verify() above fails a spec that
   * leaves a request open, so a new start-up request has to be answered here.
   * Call inside fakeAsync.
   */
  function start(address: string, me: object | null): ComponentFixture<AppComponent> {
    TestBed.inject(Router).navigateByUrl(address);
    tick();

    const fixture = TestBed.createComponent(AppComponent);
    httpMock.expectOne('/api/features').flush({ edition: 'community', is_enterprise: false });
    httpMock.expectOne('/api/version').flush({
      version: '2.3.1',
      build_date: '2026-11-25',
      git_commit: 'abc1234',
      environment: 'test'
    });
    if (me === null) {
      httpMock.expectOne('/api/user/me').flush({}, unauthorized);
    } else {
      httpMock.expectOne('/api/user/me').flush(me);
    }
    tick();
    fixture.detectChanges();
    return fixture;
  }

  it('should create the app', fakeAsync(() => {
    const fixture = start('/', null);

    expect(fixture.componentInstance).toBeTruthy();
  }));

  it('should show navbar when authenticated', fakeAsync(() => {
    const fixture = start(tenantPage, mockUser);

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('app-navbar')).toBeTruthy();
  }));

  it('should hide navbar when not authenticated', fakeAsync(() => {
    const fixture = start(tenantPage, null);

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('app-navbar')).toBeFalsy();
  }));

  it('should hide navbar on the landing page even when authenticated', fakeAsync(() => {
    const fixture = start('/', mockUser);

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('app-navbar')).toBeFalsy();
  }));

  it('should have router outlet', fakeAsync(() => {
    const fixture = start('/', null);

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('router-outlet')).toBeTruthy();
  }));

  it('should render footer with the version on a page inside the app', fakeAsync(() => {
    const fixture = start(tenantPage, null);

    const compiled = fixture.nativeElement as HTMLElement;
    const footer = compiled.querySelector('.app-footer');
    expect(footer).toBeTruthy();
    expect(footer?.textContent).toContain('Decision Records');
    expect(footer?.textContent).toContain('v2.3.1 (abc1234)');
  }));

  it('should leave the footer to the landing page itself', fakeAsync(() => {
    const fixture = start('/', null);

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.app-footer')).toBeNull();
  }));
});
