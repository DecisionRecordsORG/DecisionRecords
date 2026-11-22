import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { TermsOfServiceComponent } from './terms-of-service.component';
import { DataProcessingAgreementComponent } from '../data-processing-agreement/data-processing-agreement.component';

function render(component: any): HTMLElement {
  TestBed.configureTestingModule({ imports: [component], providers: [provideRouter([])] });
  const fixture = TestBed.createComponent(component);
  fixture.detectChanges();
  return fixture.nativeElement;
}

function text(element: HTMLElement): string {
  return (element.textContent || '').replace(/\s+/g, ' ');
}

describe('Terms of Service: your data', () => {
  it('says what messages and organisation details are used for', () => {
    const page = text(render(TermsOfServiceComponent));

    expect(page).toContain(
      'We do not sell user data or use it for advertising. We process it to operate and secure the service. ' +
      'We also use the messages you send us and the optional details about your organisation to reply to you and ' +
      'to understand which kinds of teams use Decision Records, as described in our Data Processing Agreement.'
    );
    expect(page).not.toContain('purposes unrelated to operating and securing the service');
  });

  it('refers to the Data Processing Agreement, links it, and names no separate privacy policy', () => {
    const element = render(TermsOfServiceComponent);

    expect(text(element)).toContain('Further details about data handling are described in our Data Processing Agreement.');
    expect(text(element)).not.toContain('Privacy Policy');
    const link = Array.from(element.querySelectorAll('a')).find(a => a.textContent === 'Data Processing Agreement');
    expect(link?.getAttribute('href')).toBe('/dpa');
  });
});

describe('Data processing page: contact', () => {
  it('gives the shared contact address', () => {
    const element = render(DataProcessingAgreementComponent);
    const mailLinks = Array.from(element.querySelectorAll('a[href^="mailto:"]'));

    expect(mailLinks.length).toBe(1);
    expect(mailLinks[0].getAttribute('href')).toBe('mailto:contact@decisionrecords.org');
    expect(mailLinks[0].textContent).toBe('contact@decisionrecords.org');
    expect(text(element)).not.toContain('lawrence@');
  });
});
