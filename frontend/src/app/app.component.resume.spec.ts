import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { AppComponent } from './app.component';

/**
 * After sign-in the app shell leads a person back to a request to connect an
 * app (OAuth consent) that this browser was in the middle of. Enterprise
 * Edition only, once per sign-in, and by a full page load: the server sends
 * the consent page with a header that forbids framing, and a header only
 * applies to a document the browser loads from that address.
 */
describe('AppComponent: resuming a request to connect an app', () => {
  let httpMock: HttpTestingController;

  const user = { id: 7, email: 'person@example.com', name: 'Pat Person', sso_domain: 'example.com', is_admin: false };
  const master = { id: 1, username: 'root', name: 'Root' };
  const enterprise = { edition: 'enterprise', is_enterprise: true };
  const community = { edition: 'community', is_enterprise: false };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent, NoopAnimationsModule],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  function start(me: object | null, flags: object) {
    const fixture = TestBed.createComponent(AppComponent);
    const loadPage = spyOn(fixture.componentInstance, 'loadPage');
    const navigate = spyOn(TestBed.inject(Router), 'navigate');
    fixture.detectChanges();
    httpMock.expectOne('/api/features').flush(flags);
    if (me === null) {
      httpMock.expectOne('/api/user/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    } else {
      httpMock.expectOne('/api/user/me').flush(me);
    }
    tick();
    return { fixture, loadPage, navigate };
  }

  it('asks once after sign-in and goes to the consent page with a page load', fakeAsync(() => {
    const { loadPage, navigate } = start(user, enterprise);

    httpMock.expectOne('/api/oauth/pending').flush({ request: 'abc 123/+' });
    tick();

    expect(loadPage).toHaveBeenCalledOnceWith('/oauth/consent?request=abc%20123%2F%2B');
    // Not a route change inside the app
    expect(navigate).not.toHaveBeenCalled();
    httpMock.expectNone('/api/oauth/pending');
  }));

  it('stays where it is when nothing is pending', fakeAsync(() => {
    const { loadPage } = start(user, enterprise);
    httpMock.expectOne('/api/oauth/pending').flush({ request: null });
    tick();
    expect(loadPage).not.toHaveBeenCalled();
  }));

  it('ignores an error from the server', fakeAsync(() => {
    const { loadPage } = start(user, enterprise);
    httpMock.expectOne('/api/oauth/pending').flush({ error: 'Not found' }, { status: 404, statusText: 'Not Found' });
    tick();
    expect(loadPage).not.toHaveBeenCalled();
  }));

  it('asks nothing in the Community Edition', fakeAsync(() => {
    const { loadPage } = start(user, community);
    httpMock.expectNone('/api/oauth/pending');
    expect(loadPage).not.toHaveBeenCalled();
  }));

  it('asks nothing for a visitor who is not signed in', fakeAsync(() => {
    start(null, enterprise);
    httpMock.expectNone('/api/oauth/pending');
  }));

  it('asks nothing for a super admin', fakeAsync(() => {
    start(master, enterprise);
    httpMock.expectNone('/api/oauth/pending');
  }));

  it('does not ask while already on the consent page', fakeAsync(() => {
    const router = TestBed.inject(Router);
    spyOnProperty(router, 'url', 'get').and.returnValue('/oauth/consent?request=abc');
    start(user, enterprise);
    httpMock.expectNone('/api/oauth/pending');
  }));

  it('shows no navigation bar on the consent page', fakeAsync(() => {
    const router = TestBed.inject(Router);
    spyOnProperty(router, 'url', 'get').and.returnValue('/oauth/consent?request=abc');
    const { fixture } = start(user, enterprise);
    fixture.componentInstance.ngOnInit();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('app-navbar')).toBeFalsy();
    expect(fixture.componentInstance.isAppConsentPage).toBeTrue();
  }));
});
