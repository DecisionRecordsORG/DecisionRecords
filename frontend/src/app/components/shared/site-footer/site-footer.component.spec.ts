import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { CONTACT_FALLBACK_ERROR, SiteFooterComponent, contactErrorMessage } from './site-footer.component';

const FILLED = { name: 'Ada Lovelace', email: 'ada@example.org', message: 'Hello there' };

describe('contactErrorMessage', () => {
  it('uses the backend explanation for a rejected message', () => {
    expect(contactErrorMessage({ status: 400, error: { error: 'Invalid email address' } })).toBe('Invalid email address');
    expect(contactErrorMessage({ status: 429, error: { error: 'Too many requests' } })).toBe('Too many requests');
  });

  it('uses the fallback for everything else', () => {
    expect(contactErrorMessage({ status: 500, error: { error: 'Traceback ...' } })).toBe(CONTACT_FALLBACK_ERROR);
    expect(contactErrorMessage({ status: 503, error: { error: 'Email service temporarily unavailable' } }))
      .toBe(CONTACT_FALLBACK_ERROR);
    expect(contactErrorMessage({ status: 404, error: '<html>Not found</html>' })).toBe(CONTACT_FALLBACK_ERROR);
    expect(contactErrorMessage({ status: 403, error: { error: 'CSRF token missing or invalid' } })).toBe(CONTACT_FALLBACK_ERROR);
    expect(contactErrorMessage({ status: 400, error: { error: '' } })).toBe(CONTACT_FALLBACK_ERROR);
    expect(contactErrorMessage({ status: 0, error: null })).toBe(CONTACT_FALLBACK_ERROR);
    expect(contactErrorMessage(null)).toBe(CONTACT_FALLBACK_ERROR);
  });
});

describe('SiteFooterComponent contact form', () => {
  let fixture: ComponentFixture<SiteFooterComponent>;
  let component: SiteFooterComponent;
  let backend: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SiteFooterComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([]), provideNoopAnimations()]
    }).compileComponents();

    fixture = TestBed.createComponent(SiteFooterComponent);
    component = fixture.componentInstance;
    backend = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    backend.verify();
    component.closeContactDialog();
  });

  it('posts name, email and message as JSON and shows success on a 2xx', () => {
    component.contactForm.setValue(FILLED);
    component.submitContact();
    expect(component.contactSubmitting).toBeTrue();

    const req = backend.expectOne('/api/contact');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(FILLED);
    req.flush({ message: 'Thank you for your message! We will get back to you soon.' });

    expect(component.contactSubmitting).toBeFalse();
    expect(component.contactSubmitted).toBeTrue();
    expect(component.contactError).toBe('');
  });

  for (const status of [400, 403, 404, 429, 500, 502, 503]) {
    it(`shows an error, not success, and keeps the text on a ${status}`, () => {
      component.contactForm.setValue(FILLED);
      component.submitContact();
      backend.expectOne('/api/contact').flush({ error: 'Nope' }, { status, statusText: 'Error' });

      expect(component.contactSubmitted).toBeFalse();
      expect(component.contactSubmitting).toBeFalse();
      expect(component.contactError).toBeTruthy();
      expect(component.contactForm.value).toEqual(FILLED);
    });
  }

  it('shows an error and keeps the text when the network fails', () => {
    component.contactForm.setValue(FILLED);
    component.submitContact();
    backend.expectOne('/api/contact').error(new ProgressEvent('error'));

    expect(component.contactSubmitted).toBeFalse();
    expect(component.contactError).toBe(CONTACT_FALLBACK_ERROR);
    expect(component.contactForm.value).toEqual(FILLED);
  });

  it('clears the error when the visitor tries again, and succeeds on the retry', () => {
    component.contactForm.setValue(FILLED);
    component.submitContact();
    backend.expectOne('/api/contact').flush({ error: 'x' }, { status: 500, statusText: 'Error' });
    expect(component.contactError).toBe(CONTACT_FALLBACK_ERROR);

    component.submitContact();
    expect(component.contactError).toBe('');
    backend.expectOne('/api/contact').flush({ message: 'ok' });
    expect(component.contactSubmitted).toBeTrue();
  });

  it('does not submit an invalid form or submit twice while sending', () => {
    component.submitContact();
    backend.expectNone('/api/contact');

    component.contactForm.setValue(FILLED);
    component.submitContact();
    component.submitContact();
    backend.expectOne('/api/contact').flush({ message: 'ok' });
  });

  it('renders the error in the dialog and leaves the typed message in the field', () => {
    component.openContactDialog();
    fixture.detectChanges();
    component.contactForm.setValue(FILLED);
    component.submitContact();
    backend.expectOne('/api/contact').flush({ error: 'x' }, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();

    const error = document.querySelector('[data-testid="contact-error"]');
    expect(error?.textContent).toContain(CONTACT_FALLBACK_ERROR);
    expect(document.querySelector('.contact-success')).toBeNull();
    const textarea = document.querySelector('.contact-form textarea') as HTMLTextAreaElement;
    expect(textarea.value).toBe(FILLED.message);
  });

  it('starts with a clean form and no error each time the dialog is opened', () => {
    component.contactForm.setValue(FILLED);
    component.submitContact();
    backend.expectOne('/api/contact').flush({ error: 'x' }, { status: 500, statusText: 'Error' });
    expect(component.contactError).toBeTruthy();

    component.openContactDialog();

    expect(component.contactError).toBe('');
    expect(component.contactSubmitted).toBeFalse();
  });
});
