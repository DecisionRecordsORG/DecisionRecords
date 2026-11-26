import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { User } from '../../models/decision.model';
import { ProfileNameComponent } from './profile-name.component';

/** A person corrects their own name on the profile page. */
describe('ProfileNameComponent', () => {
  let fixture: ComponentFixture<ProfileNameComponent>;
  let http: HttpTestingController;
  let saved: User[];

  const USER = {
    id: 7, email: 'pat@acme.test', name: 'Pat Member', first_name: 'Pat', last_name: 'Member',
    sso_domain: 'acme.test'
  } as unknown as User;

  async function open(user: User | null): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [ProfileNameComponent, NoopAnimationsModule],
      providers: [provideHttpClient(), provideHttpClientTesting()]
    }).compileComponents();
    fixture = TestBed.createComponent(ProfileNameComponent);
    fixture.componentInstance.user = user;
    saved = [];
    fixture.componentInstance.saved.subscribe(value => saved.push(value));
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  }

  function element<T extends HTMLElement>(testId: string): T | null {
    return fixture.nativeElement.querySelector(`[data-testid="${testId}"]`);
  }

  async function type(testId: string, value: string): Promise<void> {
    const input = element<HTMLInputElement>(testId)!;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    await fixture.whenStable();
  }

  async function startEditing(): Promise<void> {
    element('profile-name-edit')!.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  }

  function submit(): void {
    element<HTMLFormElement>('profile-name-form')!.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  afterEach(() => http.verify());

  it('shows the name with a way to edit it', async () => {
    await open(USER);

    expect(element('profile-name')!.textContent).toBe('Pat Member');
    expect(element('profile-name-edit')!.getAttribute('aria-label')).toBe('Edit your name');
    expect(element('profile-name-form')).toBeNull();
  });

  it('says "Not set" for an account without a name', async () => {
    await open({ ...USER, name: '', first_name: undefined, last_name: undefined } as User);

    expect(element('profile-name')!.textContent).toBe('Not set');
  });

  it('opens with the current first and last name', async () => {
    await open(USER);
    await startEditing();

    expect(element<HTMLInputElement>('profile-first-name')!.value).toBe('Pat');
    expect(element<HTMLInputElement>('profile-last-name')!.value).toBe('Member');
  });

  it('splits the single name of an older account at the first space', async () => {
    await open({ ...USER, name: 'Ana Maria da Silva', first_name: undefined, last_name: undefined } as User);
    await startEditing();

    expect(element<HTMLInputElement>('profile-first-name')!.value).toBe('Ana');
    expect(element<HTMLInputElement>('profile-last-name')!.value).toBe('Maria da Silva');
  });

  it('saves the corrected name and hands back the account', async () => {
    await open(USER);
    await startEditing();
    await type('profile-first-name', '  Patricia ');
    await type('profile-last-name', 'Membre');

    submit();

    const request = http.expectOne({ method: 'PUT', url: '/api/user/profile' });
    expect(request.request.body).toEqual({ first_name: 'Patricia', last_name: 'Membre' });
    const updated = { ...USER, name: 'Patricia Membre', first_name: 'Patricia', last_name: 'Membre' } as User;
    request.flush({ message: 'Name updated', user: updated });
    fixture.detectChanges();

    expect(saved).toEqual([updated]);
    expect(element('profile-name-form')).toBeNull();
  });

  it('sends only the name: never an email address', async () => {
    await open(USER);
    await startEditing();
    submit();

    const request = http.expectOne('/api/user/profile');
    expect(Object.keys(request.request.body).sort()).toEqual(['first_name', 'last_name']);
    request.flush({ message: 'Name updated', user: USER });
  });

  it('asks for a name instead of saving an empty one', async () => {
    await open(USER);
    await startEditing();
    await type('profile-first-name', '   ');
    await type('profile-last-name', '');

    submit();

    http.expectNone('/api/user/profile');
    expect(element('profile-name-error')!.textContent).toBe('Enter your name.');
    expect(saved).toEqual([]);
  });

  it('shows the server\'s reason when the name is refused and keeps the form open', async () => {
    await open(USER);
    await startEditing();
    submit();

    http.expectOne('/api/user/profile').flush(
      { error: 'A name can be at most 100 characters' }, { status: 400, statusText: 'Bad Request' });
    fixture.detectChanges();

    expect(element('profile-name-error')!.textContent).toBe('A name can be at most 100 characters');
    expect(element('profile-name-form')).not.toBeNull();
    expect(saved).toEqual([]);
  });

  it('cancel leaves the name as it was', async () => {
    await open(USER);
    await startEditing();
    await type('profile-first-name', 'Someone');

    element('profile-name-cancel')!.click();
    fixture.detectChanges();

    http.expectNone('/api/user/profile');
    expect(element('profile-name')!.textContent).toBe('Pat Member');
  });

  it('limits each field to 100 characters', async () => {
    await open(USER);
    await startEditing();

    expect(element<HTMLInputElement>('profile-first-name')!.maxLength).toBe(100);
    expect(element<HTMLInputElement>('profile-last-name')!.maxLength).toBe(100);
  });
});
