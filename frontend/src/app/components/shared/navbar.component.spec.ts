import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { NavbarComponent } from './navbar.component';
import { AuthService } from '../../services/auth.service';

/**
 * The feedback dialog says that the message is stored. Uses a stand-in
 * AuthService so the spec does not depend on session loading.
 */
describe('NavbarComponent feedback dialog', () => {
  let fixture: ComponentFixture<NavbarComponent>;
  let component: NavbarComponent;

  beforeEach(async () => {
    const user = { id: 3, email: 'ada@acme.test', name: 'Ada Lovelace', sso_domain: 'acme.test', is_admin: false };
    const authStub = {
      currentUser: { user },
      isAuthenticated: true,
      isAdmin: false,
      isMasterAccount: false
    };

    await TestBed.configureTestingModule({
      imports: [NavbarComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        provideNoopAnimations(),
        { provide: AuthService, useValue: authStub }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(NavbarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => component.closeFeedbackDialog());

  it('says above the send button that the message is stored and links to the data processing page', () => {
    component.openFeedbackDialog();
    fixture.detectChanges();

    const notice = document.querySelector('[data-testid="feedback-data-notice"]') as HTMLElement;
    expect((notice.textContent || '').replace(/\s+/g, ' ').trim())
      .toBe('We store your message so we can reply to you. How we handle your data');
    const link = notice.querySelector('a') as HTMLAnchorElement;
    expect(link.textContent).toBe('How we handle your data');
    expect(link.getAttribute('href')).toBe('/dpa');

    const button = document.querySelector('.feedback-dialog-container .submit-btn') as HTMLElement;
    expect(notice.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('is offered as help and feedback and says what happens to a message', () => {
    const entry = fixture.nativeElement.querySelector('.feedback-btn') as HTMLElement;
    expect((entry.textContent || '').replace(/\s+/g, ' ').trim()).toMatch(/Help and feedback$/);

    component.openFeedbackDialog();
    fixture.detectChanges();

    const dialog = document.querySelector('.feedback-dialog-container') as HTMLElement;
    expect(dialog.querySelector('h2')!.textContent).toBe('Help and feedback');
    expect((dialog.querySelector('.dialog-intro')!.textContent || '').replace(/\s+/g, ' ').trim()).toBe(
      'Ask for help, report a problem or tell us what you think. ' +
      'We read every message and reply by email unless you ask us not to.'
    );
    expect(dialog.textContent).not.toContain('support ticket');
    expect((dialog.querySelector('.consent-checkbox')!.textContent || '').trim()).toBe('You may reply to me by email');
    expect((dialog.querySelector('.submit-btn')!.textContent || '').replace(/\s+/g, ' ').trim()).toMatch(/Send message$/);
  });
});
