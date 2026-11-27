import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { HttpHeaders, provideHttpClient } from '@angular/common/http';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { ORGANISATION_EXPORT_URL, OrganisationExportComponent } from './organisation-export.component';

/** The button in Organisation settings that downloads the organisation's export. */
describe('OrganisationExportComponent', () => {
  let fixture: ComponentFixture<OrganisationExportComponent>;
  let component: OrganisationExportComponent;
  let http: HttpTestingController;
  let save: jasmine.Spy;
  let snackBarOpen: jasmine.Spy;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OrganisationExportComponent, NoopAnimationsModule],
      providers: [provideHttpClient(), provideHttpClientTesting()]
    }).compileComponents();
    fixture = TestBed.createComponent(OrganisationExportComponent);
    component = fixture.componentInstance;
    http = TestBed.inject(HttpTestingController);
    save = spyOn(component, 'save');
    snackBarOpen = spyOn((component as any).snackBar, 'open');
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function element(testId: string): HTMLElement | null {
    return fixture.nativeElement.querySelector(`[data-testid="${testId}"]`);
  }

  function text(testId: string): string {
    return (element(testId)?.textContent || '').replace(/\s+/g, ' ').trim();
  }

  /** The refusal's body is read from a Blob, which resolves outside Angular's fake clock. */
  async function settled(): Promise<void> {
    for (let attempt = 0; attempt < 50 && component.error === null; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    fixture.detectChanges();
  }

  function press(): void {
    (element('organisation-export-button') as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  it('says what the file holds and what it leaves out', () => {
    expect(text('organisation-export-intro')).toContain('decisions, as JSON and as one Markdown file per decision');
    expect(text('organisation-export-intro')).toContain('Only administrators can export.');
    expect(text('organisation-export-left-out')).toContain("people's sign-in history");
    expect(text('organisation-export-left-out')).toContain('API keys');
    expect(text('organisation-export-button')).toContain('Download export (ZIP)');
    expect(element('organisation-export-error')).toBeNull();
  });

  it('asks the server with a POST and saves the ZIP under the name the server gives', () => {
    press();

    const request = http.expectOne(ORGANISATION_EXPORT_URL);
    expect(request.request.method).toBe('POST');
    expect(request.request.responseType).toBe('blob');
    expect((element('organisation-export-button') as HTMLButtonElement).disabled).toBeTrue();
    expect(text('organisation-export-button')).toContain('Preparing export...');

    const zip = new Blob(['PK'], { type: 'application/zip' });
    request.flush(zip, {
      headers: new HttpHeaders({ 'Content-Disposition': 'attachment; filename="decision-records-acme.test-20261127.zip"' })
    });
    fixture.detectChanges();

    expect(save).toHaveBeenCalledOnceWith(zip, 'decision-records-acme.test-20261127.zip');
    expect(snackBarOpen).toHaveBeenCalledWith('Export downloaded', 'Close', { duration: 3000 });
    expect((element('organisation-export-button') as HTMLButtonElement).disabled).toBeFalse();
  });

  it('uses a dated name when the server gives none', () => {
    press();
    http.expectOne(ORGANISATION_EXPORT_URL).flush(new Blob(['PK']));

    expect(save.calls.mostRecent().args[1]).toMatch(/^decision-records-export-\d{4}-\d{2}-\d{2}\.zip$/);
  });

  it("shows the server's reason when it refuses, for example to someone who is not an administrator", async () => {
    press();
    const refusal = new Blob([JSON.stringify({ error: 'Only administrators of this organisation can export its data' })],
      { type: 'application/json' });
    http.expectOne(ORGANISATION_EXPORT_URL).flush(refusal, { status: 403, statusText: 'Forbidden' });
    await settled();

    expect(text('organisation-export-error')).toBe('Only administrators of this organisation can export its data');
    expect(save).not.toHaveBeenCalled();
    expect((element('organisation-export-button') as HTMLButtonElement).disabled).toBeFalse();
  });

  it('shows a general message when the refusal has no reason', async () => {
    press();
    http.expectOne(ORGANISATION_EXPORT_URL).flush(new Blob(['<html>']), { status: 502, statusText: 'Bad Gateway' });
    await settled();

    expect(text('organisation-export-error')).toBe('The export could not be made. Try again later.');
  });

  it('clears an earlier error when asked again', () => {
    component.error = 'Earlier';
    fixture.detectChanges();
    press();

    expect(element('organisation-export-error')).toBeNull();
    http.expectOne(ORGANISATION_EXPORT_URL).flush(new Blob(['PK']));
  });
});
