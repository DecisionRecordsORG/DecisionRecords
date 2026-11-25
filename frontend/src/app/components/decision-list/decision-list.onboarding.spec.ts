import { ComponentFixture, TestBed, fakeAsync, flush, tick } from '@angular/core/testing';
import { Component } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { of } from 'rxjs';
import { DecisionListComponent } from './decision-list.component';
import { AuthService } from '../../services/auth.service';
import { TEMPLATE_CATALOG, governanceTenantTemplate, tenantTemplate } from '../../services/decision-template.testing';

/**
 * The first-admin onboarding dialog: when it opens, and the optional team
 * profile questions in it.
 *
 * Kept apart from decision-list.component.spec.ts, whose specs use the real
 * AuthService; these use a stand-in so each spec can choose who is signed in.
 */

@Component({
  standalone: true,
  imports: [MatDialogModule],
  template: '<input id="other-dialog-input">'
})
class OtherDialogComponent {}

describe('DecisionListComponent onboarding dialog', () => {
  let fixture: ComponentFixture<DecisionListComponent>;
  let component: DecisionListComponent;
  let httpMock: HttpTestingController;
  let dialog: MatDialog;
  let user: any;

  function onboardingIsOpen(): boolean {
    return !!document.querySelector('.admin-onboarding-dialog');
  }

  function flushListRequests(): void {
    httpMock.match('/api/decisions').forEach(request => request.flush([]));
    httpMock.match('/api/spaces').forEach(request => request.flush([]));
  }

  function createComponent(): void {
    fixture = TestBed.createComponent(DecisionListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
    flushListRequests();
    fixture.detectChanges();
  }

  beforeEach(async () => {
    user = {
      id: 7,
      email: 'admin@acme.test',
      name: 'Grace Hopper',
      sso_domain: 'acme.test',
      is_admin: true,
      has_seen_admin_onboarding: false,
      tenant_info: { id: 1, domain: 'acme.test', name: 'Acme', maturity_state: 'bootstrap', admin_count: 1, steward_count: 0, team_profile_answered: false }
    };
    const authService = {
      currentUser: { user, isMaster: false },
      isMasterAccount: false,
      isAdmin: true,
      isAuthenticated: true,
      canDeleteDecisions: true
    };

    await TestBed.configureTestingModule({
      imports: [DecisionListComponent, OtherDialogComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: AuthService, useValue: authService },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ tenant: 'acme.test' }) }, queryParams: of({}) }
        }
      ]
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    dialog = TestBed.inject(MatDialog);
  });

  afterEach(() => {
    dialog.closeAll();
    httpMock.match(() => true);
  });

  /** Answer the two requests the list makes about the decision template. */
  function flushTemplate(answer = tenantTemplate({ can_manage: true, show_notice: true })): void {
    httpMock.expectOne('/api/tenant/decision-template').flush(answer);
    httpMock.match('/api/decision-templates/catalog').forEach(request => request.flush(TEMPLATE_CATALOG));
    fixture.detectChanges();
  }

  function notice(): HTMLElement | null {
    return fixture.nativeElement.querySelector('[data-testid="decision-template-notice"]');
  }

  describe('decision template', () => {
    it('asks the optional industry question with the official titles and the Eurostat credit', fakeAsync(() => {
      createComponent();
      flushTemplate();
      tick(500);
      fixture.detectChanges();

      const section = document.querySelector('[data-testid="onboarding-decision-template"]') as HTMLElement;
      const text = (section.textContent || '').replace(/\s+/g, ' ');
      expect(text).toContain('What kind of organisation are you?');
      expect(text).toContain('Optional.');
      expect(text).toContain('Skip it and you get the General template.');
      expect(text).toContain('Industry sections: NACE Rev. 2.1, Eurostat, CC BY 4.0');
      expect(component.industries.map(industry => industry.title)).toEqual(['Manufacturing', 'Education']);
      // The existing two questions are still there
      expect(document.querySelector('[data-testid="onboarding-team-profile"]')).not.toBeNull();
      // Not both at once: the notice waits until the dialog has been seen
      expect(notice()).toBeNull();
      flush();
    }));

    it('saves the industry with the template it suggests when the dialog is dismissed', fakeAsync(() => {
      createComponent();
      flushTemplate();
      tick(500);
      component.onboardingIndustry = 'Q';
      fixture.detectChanges();

      expect(document.querySelector('[data-testid="onboarding-template-choice"]')?.textContent)
        .toContain('Governance and committee');
      component.dismissOnboarding();

      const save = httpMock.expectOne('/api/tenant/decision-template');
      expect(save.request.method).toBe('PUT');
      expect(save.request.body).toEqual({ industry: 'Q', template_id: 'governance' });
      save.flush(governanceTenantTemplate({ industry: 'Q', can_manage: true }));
      httpMock.expectNone('/api/tenant/decision-template/dismiss-notice');
      httpMock.expectOne('/api/user/dismiss-admin-onboarding').flush({ message: 'Admin onboarding dismissed' });
      tick(500);
      fixture.detectChanges();

      expect(notice()).toBeNull();
      flush();
    }));

    it('skipping the question keeps General and ends the notice', fakeAsync(() => {
      createComponent();
      flushTemplate();
      tick(500);
      fixture.detectChanges();

      component.dismissOnboarding();

      const dismissNotice = httpMock.expectOne('/api/tenant/decision-template/dismiss-notice');
      expect(dismissNotice.request.method).toBe('POST');
      dismissNotice.flush(tenantTemplate({ can_manage: true, show_notice: false }));
      httpMock.expectOne('/api/user/dismiss-admin-onboarding').flush({ message: 'Admin onboarding dismissed' });
      tick(500);
      fixture.detectChanges();

      expect(notice()).toBeNull();
      flush();
    }));

    it('does not ask a tenant that has already chosen a template', fakeAsync(() => {
      createComponent();
      flushTemplate(governanceTenantTemplate({ can_manage: true }));
      tick(500);
      fixture.detectChanges();

      expect(onboardingIsOpen()).toBeTrue();
      expect(document.querySelector('[data-testid="onboarding-decision-template"]')).toBeNull();
      flush();
    }));

    it('shows one notice to an admin of an existing tenant, pointing at the settings card', fakeAsync(() => {
      user.has_seen_admin_onboarding = true;
      createComponent();
      flushTemplate();

      const text = (notice()?.textContent || '').replace(/\s+/g, ' ');
      expect(text).toContain('Decision templates for different kinds of organisation are now available.');
      expect(text).toContain('Your decisions are not altered.');
      const link = notice()!.querySelector('[data-testid="decision-template-notice-choose"]') as HTMLAnchorElement;
      expect(link.getAttribute('href')).toBe('/acme.test/admin?tab=decision-template');
      flush();
    }));

    it('"Not now" ends the notice for the tenant', fakeAsync(() => {
      user.has_seen_admin_onboarding = true;
      createComponent();
      flushTemplate();

      (notice()!.querySelector('[data-testid="decision-template-notice-dismiss"]') as HTMLButtonElement).click();
      fixture.detectChanges();

      expect(notice()).toBeNull();
      const dismissNotice = httpMock.expectOne('/api/tenant/decision-template/dismiss-notice');
      expect(dismissNotice.request.method).toBe('POST');
      dismissNotice.flush(tenantTemplate({ can_manage: true }));
      flush();
    }));

    it('shows no notice to a member, or once the tenant has dismissed it', fakeAsync(() => {
      user.has_seen_admin_onboarding = true;
      user.is_admin = false;
      createComponent();
      flushTemplate(tenantTemplate({ can_manage: false, show_notice: false }));

      expect(notice()).toBeNull();
      flush();
    }));

    it('filters the list by type and shows the type on a card', fakeAsync(() => {
      user.has_seen_admin_onboarding = true;
      fixture = TestBed.createComponent(DecisionListComponent);
      component = fixture.componentInstance;
      fixture.detectChanges();
      const decision = (id: number, title: string, decision_type: string | null) => ({
        id, title, context: 'c', decision: 'd', consequences: 'q', status: 'accepted', decision_type,
        created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z'
      });
      httpMock.expectOne('/api/decisions').flush([
        decision(1, 'Pay review', 'Policy'), decision(2, 'New laptop', 'Spending'), decision(3, 'Untyped', null)
      ]);
      httpMock.match('/api/spaces').forEach(request => request.flush([]));
      fixture.detectChanges();

      expect(component.typeFilterOptions).toEqual(['Policy', 'Spending']);
      const chips = Array.from(fixture.nativeElement.querySelectorAll('[data-testid="decision-card-type"]'))
        .map((chip: any) => chip.textContent.trim());
      expect(chips).toEqual(['Policy', 'Spending']);

      component.typeFilter = 'Policy';
      component.filterDecisions();
      expect(component.filteredDecisions.map(d => d.title)).toEqual(['Pay review']);

      component.typeFilter = component.noTypeFilter;
      component.filterDecisions();
      expect(component.filteredDecisions.map(d => d.title)).toEqual(['Untyped']);

      component.clearFilters();
      expect(component.filteredDecisions.length).toBe(3);
      flush();
    }));
  });

  it('opens half a second after the list loads when nothing else is open', fakeAsync(() => {
    createComponent();
    expect(onboardingIsOpen()).toBeFalse();

    tick(500);
    fixture.detectChanges();

    expect(onboardingIsOpen()).toBeTrue();
    flush();
  }));

  it('does not open for an admin who has already seen it', fakeAsync(() => {
    user.has_seen_admin_onboarding = true;
    createComponent();

    tick(2000);
    fixture.detectChanges();

    expect(onboardingIsOpen()).toBeFalse();
    flush();
  }));

  it('does not open for someone who is not an admin', fakeAsync(() => {
    user.is_admin = false;
    createComponent();

    tick(2000);
    fixture.detectChanges();

    expect(onboardingIsOpen()).toBeFalse();
    flush();
  }));

  it('waits while another dialog is open and leaves the focus where it is', fakeAsync(() => {
    createComponent();
    const other = dialog.open(OtherDialogComponent);
    fixture.detectChanges();
    tick();
    const input = document.getElementById('other-dialog-input') as HTMLInputElement;
    input.focus();
    expect(document.activeElement).toBe(input);

    tick(5000);
    fixture.detectChanges();

    expect(onboardingIsOpen()).toBeFalse();
    expect(dialog.openDialogs.length).toBe(1);
    expect(document.activeElement).toBe(input);

    other.close();
    fixture.detectChanges();
    tick(1000);
    fixture.detectChanges();

    expect(onboardingIsOpen()).toBeTrue();
    flush();
  }));

  it('does not open after the page has been left while it was waiting', fakeAsync(() => {
    createComponent();
    const other = dialog.open(OtherDialogComponent);
    fixture.detectChanges();
    tick(600);

    fixture.destroy();
    other.close();
    tick(1000);

    expect(onboardingIsOpen()).toBeFalse();
    flush();
  }));

  it('asks the two optional questions and says why and that they can be skipped', fakeAsync(() => {
    createComponent();
    tick(500);
    fixture.detectChanges();

    const section = document.querySelector('[data-testid="onboarding-team-profile"]') as HTMLElement;
    const sectionText = (section.textContent || '').replace(/\s+/g, ' ');
    expect(sectionText).toContain('Two optional questions');
    expect(sectionText).toContain('It helps us build for teams like yours.');
    expect(sectionText).toContain('You can skip this and answer later in organisation settings.');
    expect(sectionText).toContain('What does your team make decisions about?');
    expect(sectionText).toContain('Team size');

    const link = section.querySelector('[data-testid="onboarding-data-link"]') as HTMLAnchorElement;
    expect(link.textContent).toBe('How we handle your data');
    expect(link.getAttribute('href')).toBe('/dpa');
    expect(link.closest('.onboarding-team-profile-why')).not.toBeNull();
    flush();
  }));

  it('does not ask again when the team has already answered', fakeAsync(() => {
    user.tenant_info.team_profile_answered = true;
    createComponent();
    tick(500);
    fixture.detectChanges();

    expect(onboardingIsOpen()).toBeTrue();
    expect(document.querySelector('[data-testid="onboarding-team-profile"]')).toBeNull();
    flush();
  }));

  it('dismisses without answers and saves no team profile', fakeAsync(() => {
    createComponent();
    tick(500);
    fixture.detectChanges();

    component.dismissOnboarding();
    fixture.detectChanges();

    httpMock.expectNone('/api/tenant/team-profile');
    const dismiss = httpMock.expectOne('/api/user/dismiss-admin-onboarding');
    expect(dismiss.request.method).toBe('POST');
    dismiss.flush({ message: 'Admin onboarding dismissed' });
    tick(500);
    fixture.detectChanges();

    expect(onboardingIsOpen()).toBeFalse();
    expect(user.has_seen_admin_onboarding).toBeTrue();
    flush();
  }));

  it('saves the answers that were given when it is dismissed', fakeAsync(() => {
    createComponent();
    tick(500);
    fixture.detectChanges();
    component.onboardingTeamFocus = '  Hiring and pay reviews ';
    component.onboardingTeamSize = '6-25';

    component.dismissOnboarding();

    const save = httpMock.expectOne('/api/tenant/team-profile');
    expect(save.request.method).toBe('PUT');
    expect(save.request.body).toEqual({ team_focus: 'Hiring and pay reviews', team_size: '6-25' });
    save.flush({ message: 'Team profile saved' });
    httpMock.expectOne('/api/user/dismiss-admin-onboarding').flush({ message: 'Admin onboarding dismissed' });
    tick(500);

    expect(user.tenant_info.team_profile_answered).toBeTrue();
    flush();
  }));

  it('still dismisses when saving the answers fails', fakeAsync(() => {
    createComponent();
    tick(500);
    fixture.detectChanges();
    component.onboardingTeamFocus = 'Hiring';
    spyOn(console, 'error');

    component.dismissOnboarding();
    fixture.detectChanges();

    httpMock.expectOne('/api/tenant/team-profile')
      .flush({ error: 'Permission denied' }, { status: 403, statusText: 'Forbidden' });
    httpMock.expectOne('/api/user/dismiss-admin-onboarding').flush({ message: 'Admin onboarding dismissed' });
    tick(500);
    fixture.detectChanges();

    expect(onboardingIsOpen()).toBeFalse();
    expect(user.has_seen_admin_onboarding).toBeTrue();
    flush();
  }));
});
