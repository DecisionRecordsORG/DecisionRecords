import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { AccountSetupComponent } from './account-setup.component';
import { AuthService } from '../../services/auth.service';
import { FeatureFlagsService } from '../../services/feature-flags.service';

/**
 * The setup and recovery link screen carries the help link, also when the
 * link is expired, used or missing.
 */
describe('AccountSetupComponent help link', () => {
  let fixture: ComponentFixture<AccountSetupComponent>;
  let httpMock: HttpTestingController;

  async function create(query: Record<string, string>): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [AccountSetupComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: AuthService, useValue: {} },
        { provide: FeatureFlagsService, useValue: { flags: { marketing_pages: true } } },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({ tenant: 'acme.test' }),
              queryParamMap: convertToParamMap(query)
            }
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(AccountSetupComponent);
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  }

  function href(): string | null {
    fixture.detectChanges();
    const link = fixture.nativeElement.querySelector('[data-testid="support-link"]');
    return link ? link.getAttribute('href') : null;
  }

  it('shows no link while the setup link is being checked', async () => {
    await create({ token: 'abc' });

    expect(href()).toBeNull();
    httpMock.expectOne('/api/auth/setup-token/validate').flush({ valid: false, error: 'Invalid' });
  });

  it('shows the link when the setup link has expired', async () => {
    await create({ token: 'abc' });
    httpMock.expectOne('/api/auth/setup-token/validate').flush(
      { error: 'Token has expired', expired: true },
      { status: 400, statusText: 'Bad Request' }
    );

    expect(fixture.componentInstance.errorTitle).toBe('Link Expired');
    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&org=acme.test');
  });

  it('shows the link when the setup link is not valid', async () => {
    await create({ token: 'abc' });
    httpMock.expectOne('/api/auth/setup-token/validate').flush(
      { error: 'Invalid token' },
      { status: 400, statusText: 'Bad Request' }
    );

    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&org=acme.test');
  });

  it('shows the link when the address has no token', async () => {
    await create({});

    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&org=acme.test');
  });

  it('adds the email address when the link is valid and the person is choosing how to sign in', async () => {
    await create({ token: 'abc' });
    httpMock.expectOne('/api/auth/setup-token/validate').flush({
      valid: true,
      is_recovery: true,
      user: { id: 7, email: 'ada@acme.test', name: 'Ada Lovelace', sso_domain: 'acme.test' }
    });

    expect(href()).toBe('https://decisionrecords.org/support?topic=signin&email=ada%40acme.test&org=acme.test');
  });
});
