import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FeatureFlagsService } from '../../services/feature-flags.service';
import { SupportLinkComponent } from './support-link.component';

describe('SupportLinkComponent', () => {
  let fixture: ComponentFixture<SupportLinkComponent>;
  let flags: { marketing_pages: boolean; support_url?: string };

  beforeEach(async () => {
    flags = { marketing_pages: true };
    await TestBed.configureTestingModule({
      imports: [SupportLinkComponent],
      providers: [{ provide: FeatureFlagsService, useValue: { get flags() { return flags; } } }]
    }).compileComponents();
    fixture = TestBed.createComponent(SupportLinkComponent);
  });

  function link(): HTMLAnchorElement | null {
    fixture.detectChanges();
    return fixture.nativeElement.querySelector('[data-testid="support-link"]');
  }

  it('links to the support page in a new tab with the topic, email and organisation', () => {
    fixture.componentRef.setInput('email', 'ada@acme.test');
    fixture.componentRef.setInput('org', 'acme.test');

    const a = link()!;
    expect(a.textContent).toBe("Can't sign in? Get help");
    expect(a.getAttribute('href'))
      .toBe('https://decisionrecords.org/support?topic=signin&email=ada%40acme.test&org=acme.test');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('rel')).toBe('noopener');
  });

  it('uses the topic and label it is given', () => {
    fixture.componentRef.setInput('topic', 'email');
    fixture.componentRef.setInput('label', 'Get help');

    const a = link()!;
    expect(a.textContent).toBe('Get help');
    expect(a.getAttribute('href')).toBe('https://decisionrecords.org/support?topic=email');
  });

  it('renders nothing on a self-hosted installation with no support page configured', () => {
    flags = { marketing_pages: false };
    expect(link()).toBeNull();
  });

  it('points to the support page a self-hosted installation configured', () => {
    flags = { marketing_pages: false, support_url: 'https://help.example.org/it' };
    fixture.componentRef.setInput('org', 'acme.test');
    expect(link()!.getAttribute('href')).toBe('https://help.example.org/it?topic=signin&org=acme.test');
  });
});
