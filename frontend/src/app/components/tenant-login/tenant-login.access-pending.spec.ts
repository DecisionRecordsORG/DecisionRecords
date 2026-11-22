import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { TenantLoginComponent } from './tenant-login.component';

/**
 * The page a person lands on after verifying their email for an access
 * request. It says how the setup link will reach them, and promises an email
 * only when the server reports that one can be sent.
 */
describe('TenantLoginComponent access pending', () => {
  let fixture: ComponentFixture<TenantLoginComponent>;
  let httpMock: HttpTestingController;

  async function open(tenantStatus: object | null): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [TenantLoginComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({ tenant: 'acme.test' }),
              queryParamMap: convertToParamMap({ access_requested: '1' })
            }
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(TenantLoginComponent);
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    const status = httpMock.expectOne('/api/auth/tenant/acme.test');
    expect(status.request.method).toBe('GET');
    if (tenantStatus) {
      status.flush(tenantStatus);
    } else {
      status.flush({ error: 'Too many requests' }, { status: 429, statusText: 'Too Many Requests' });
    }
    httpMock.match(() => true).forEach(req => req.flush({}, { status: 404, statusText: 'Not Found' }));
    fixture.detectChanges();
  }

  function note(): string {
    return fixture.nativeElement.querySelector('[data-testid="access-pending-note"]').textContent
      .replace(/\s+/g, ' ').trim();
  }

  afterEach(() => {
    httpMock.match(() => true);
  });

  it('promises an email when one can be sent, and says what happens if it cannot', async () => {
    await open({ email_available: true });

    expect(fixture.componentInstance.currentView).toBe('access-pending');
    expect(note()).toBe(
      'An administrator will review your request. When it is approved, you will receive an email ' +
      'with a link to set up your sign-in. If the email cannot be sent, the administrator will give you the link.'
    );
  });

  it('says the administrator will give the link when email is not available', async () => {
    await open({ email_available: false });

    expect(note()).toBe(
      'An administrator will review your request. When it is approved, the administrator will give you ' +
      'a link to set up your sign-in.'
    );
    expect(note()).not.toContain('email');
  });

  it('promises nothing about email when the server does not say', async () => {
    await open({ domain: 'acme.test' });

    expect(note()).toBe('An administrator will review your request.');
  });

  it('promises nothing about email when the status cannot be read', async () => {
    await open(null);

    expect(note()).toBe('An administrator will review your request.');
  });
});
