import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { of } from 'rxjs';
import {
  RetentionPreviewEntry,
  RetentionRun,
  RetentionStatus,
  SuperadminRetentionComponent,
  RETENTION_CATEGORY_TEXT,
  retentionCount,
  retentionCutoffEvent,
  retentionDuration,
  retentionHoldReason,
  retentionRunStatusLabel,
  retentionTriggerLabel
} from './superadmin-retention.component';

function entry(overrides: Partial<RetentionPreviewEntry> = {}): RetentionPreviewEntry {
  return {
    waiting: 0,
    limit: null,
    would_hold: false,
    hold_reason: null,
    oldest_due_at: null,
    cutoff: null,
    items: [],
    items_truncated: false,
    ...overrides
  };
}

function run(overrides: Partial<RetentionRun> = {}): RetentionRun {
  return {
    id: 1,
    trigger: 'automatic',
    started_by: null,
    status: 'completed',
    started_at: '2026-11-22T00:05:00Z',
    finished_at: '2026-11-22T00:05:01Z',
    duration_ms: 420,
    categories: ['accounts', 'login_history', 'inquiries', 'decisions', 'tenants'],
    results: {},
    error: null,
    ...overrides
  };
}

function status(overrides: Partial<RetentionStatus> = {}): RetentionStatus {
  return {
    settings: {
      auto_run_enabled: true,
      auto_run_disabled_by_environment: false,
      auto_run_active: true,
      limits: { accounts: 10, decisions: 50, tenants: 1 },
      backlog_days: 7
    },
    automatic: { active: true, disabled_by: null, last_run: null },
    preview: {
      accounts: entry({ limit: 10 }),
      login_history: entry({ waiting: 4, cutoff: '2026-08-24T00:00:00Z' }),
      inquiries: entry(),
      decisions: entry({ limit: 50 }),
      tenants: entry({ limit: 1 })
    },
    held_back: [],
    run_in_progress: null,
    runs: [],
    categories: ['accounts', 'login_history', 'inquiries', 'decisions', 'tenants'],
    ...overrides
  };
}

function heldTenants(): RetentionStatus {
  const base = status();
  return {
    ...base,
    preview: {
      ...base.preview,
      tenants: entry({
        waiting: 2,
        limit: 1,
        would_hold: true,
        hold_reason: 'over_limit',
        items: [
          { id: 7, label: 'first.example', due_at: '2026-11-21T10:00:00Z',
            counts: { users: 3, decisions: 12, spaces: 1, memberships: 3 } },
          { id: 8, label: 'second.example', due_at: '2026-11-21T11:00:00Z',
            counts: { users: 1, decisions: 0, spaces: 1, memberships: 1 } }
        ]
      })
    },
    held_back: ['tenants']
  };
}

describe('retention helpers', () => {
  it('counts in the words of each category', () => {
    expect(retentionCount('tenants', 1)).toBe('1 tenant');
    expect(retentionCount('accounts', 3)).toBe('3 accounts');
    expect(retentionCount('login_history', 2)).toBe('2 login history entries');
    expect(retentionCount('something-new', 2)).toBe('2 items');
  });

  it('has words for the categories that are deleted by age', () => {
    expect(retentionCount('request_log', 1)).toBe('1 request log entry');
    expect(retentionCount('verification_records', 2)).toBe('2 expired records');
    expect(retentionCount('access_requests', 1)).toBe('1 access request');
    expect(retentionCount('api_keys', 3)).toBe('3 API keys');
    expect(RETENTION_CATEGORY_TEXT.request_log.rule).toContain('older than 90 days');
    expect(RETENTION_CATEGORY_TEXT.verification_records.rule).toContain('expired more than 30 days ago');
    expect(RETENTION_CATEGORY_TEXT.access_requests.rule).toContain('Pending requests stay');
    expect(RETENTION_CATEGORY_TEXT.api_keys.rule).toContain('Keys that still work stay');
  });

  it('says what the cutoff date of each age-based category counts from', () => {
    expect(retentionCutoffEvent('login_history')).toBe('was created');
    expect(retentionCutoffEvent('request_log')).toBe('was created');
    expect(retentionCutoffEvent('verification_records')).toBe('expired');
    expect(retentionCutoffEvent('access_requests')).toBe('was approved or rejected');
    expect(retentionCutoffEvent('api_keys')).toBe('was revoked or expired');
  });

  it('says who started a run', () => {
    expect(retentionTriggerLabel({ trigger: 'automatic', started_by: null })).toBe('Automatic');
    expect(retentionTriggerLabel({ trigger: 'cron', started_by: null })).toBe('Cron job');
    expect(retentionTriggerLabel({ trigger: 'super_admin', started_by: 'root' })).toBe('Super admin root');
    expect(retentionTriggerLabel({ trigger: 'super_admin', started_by: null })).toBe('Super admin');
  });

  it('words run statuses plainly', () => {
    expect(retentionRunStatusLabel('completed')).toBe('Finished');
    expect(retentionRunStatusLabel('held_back')).toBe('Finished, some held back');
    expect(retentionRunStatusLabel('completed_with_errors')).toBe('Finished with errors');
    expect(retentionRunStatusLabel('running')).toBe('Still running');
    expect(retentionRunStatusLabel('interrupted')).toBe('Stopped before it finished');
  });

  it('explains why a category is held back', () => {
    expect(retentionHoldReason('over_limit', 1, 7)).toBe('More are waiting than the limit of 1 for one automatic run.');
    expect(retentionHoldReason('backlog', 1, 7)).toBe('The oldest has been waiting more than 7 days.');
    expect(retentionHoldReason('backlog', 1, 1)).toBe('The oldest has been waiting more than 1 day.');
    expect(retentionHoldReason(null, 1, 7)).toBe('');
  });

  it('formats how long a run took', () => {
    expect(retentionDuration(420)).toBe('420 ms');
    expect(retentionDuration(2500)).toBe('2.5 s');
    expect(retentionDuration(125000)).toBe('2 min 5 s');
    expect(retentionDuration(null)).toBe('');
  });
});

describe('SuperadminRetentionComponent', () => {
  let fixture: ComponentFixture<SuperadminRetentionComponent>;
  let component: SuperadminRetentionComponent;
  let httpMock: HttpTestingController;

  function flushLoad(body: RetentionStatus): void {
    httpMock.expectOne('/api/superadmin/retention').flush(body);
    fixture.detectChanges();
  }

  function element(testId: string): HTMLElement | null {
    return fixture.nativeElement.querySelector(`[data-testid="${testId}"]`);
  }

  function text(testId: string): string {
    const found = element(testId);
    return found ? (found.textContent as string).replace(/\s+/g, ' ').trim() : '';
  }

  function confirmWith(answer: boolean): jasmine.Spy {
    const dialog = (component as any).dialog as MatDialog;
    return spyOn(dialog, 'open').and.returnValue({ afterClosed: () => of(answer) } as any);
  }

  function snackSpy(): jasmine.Spy {
    return spyOn((component as any).snackBar as MatSnackBar, 'open');
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SuperadminRetentionComponent, NoopAnimationsModule],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])]
    }).compileComponents();

    fixture = TestBed.createComponent(SuperadminRetentionComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('shows what is waiting, the limits and that erasing cannot be undone', () => {
    flushLoad(status());

    expect(text('retention-irreversible')).toContain('Erasing cannot be undone');
    expect(text('retention-irreversible')).toContain('database backup');
    expect(text('retention-waiting-login_history')).toBe('4');
    expect(text('retention-limit-login_history')).toBe('No limit');
    expect(text('retention-limit-tenants')).toBe('Limit 1');
    expect(text('retention-state-login_history')).toContain('Will be done by the next automatic run.');
    expect(text('retention-state-tenants')).toContain('Nothing waiting');
    expect(element('retention-run-tenants')).toBeNull();
    expect(element('retention-run-login_history')).not.toBeNull();
    expect(element('retention-held-banner')).toBeNull();
    expect(text('retention-auto-state')).toBe('On');
    expect(text('retention-auto-last-run')).toBe('No automatic run yet.');
    expect(text('retention-runs-empty')).toBe('No runs yet.');
  });

  it('shows a held back category with its reason, its items and a banner', () => {
    flushLoad(heldTenants());

    expect(text('retention-held-banner')).toContain('Held back: deleted tenants to erase.');
    expect(text('retention-held-back-count')).toBe('1 held back');
    expect(text('retention-state-tenants')).toContain('Held back');
    expect(text('retention-state-tenants')).toContain('More are waiting than the limit of 1 for one automatic run.');
    const items = text('retention-items-tenants');
    expect(items).toContain('first.example');
    expect(items).toContain('users: 3, decisions: 12, spaces: 1, memberships: 3');
    expect(items).toContain('second.example');
  });

  it('explains a backlog hold with the number of days', () => {
    const body = heldTenants();
    body.preview['tenants'].hold_reason = 'backlog';
    flushLoad(body);

    expect(text('retention-state-tenants')).toContain('The oldest has been waiting more than 7 days.');
  });

  it('says when the item list is cut short and lists tenants that need a look', () => {
    const body = heldTenants();
    body.preview['tenants'].waiting = 150;
    body.preview['tenants'].items_truncated = true;
    body.preview['tenants'].needs_review = [{ id: 9, label: 'byhand.example', status: 'active' }];
    flushLoad(body);

    expect(text('retention-truncated-tenants')).toBe('Showing the first 2 of 150, oldest first.');
    expect(text('retention-needs-review')).toContain('Never erased automatically');
    expect(text('retention-needs-review')).toContain('byhand.example');
    expect(text('retention-needs-review')).toContain('status: active');
  });

  it('asks before running a category, states the count and sends it as the confirmed count', () => {
    flushLoad(heldTenants());
    const open = confirmWith(true);
    const snack = snackSpy();

    element('retention-run-tenants')!.click();

    const data = open.calls.mostRecent().args[1].data;
    expect(data.message).toBe('Erase 2 tenants now? This cannot be undone.');
    expect(data.confirmText).toBe('Erase 2');
    expect(data.isDanger).toBeTrue();

    const request = httpMock.expectOne('/api/superadmin/retention/run');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ categories: ['tenants'], confirm_counts: { tenants: 2 } });
    request.flush({
      message: 'Retention run finished',
      run: run({ trigger: 'super_admin', results: { tenants: {
        status: 'done', affected: 2, waiting: 2, limit: 1, hold_reason: null, errors: [], error_count: 0 } } })
    });

    expect(snack.calls.mostRecent().args[0]).toBe('Erased 2 tenants.');
    flushLoad(status());
    expect(element('retention-held-banner')).toBeNull();
  });

  it('says anonymise for accounts', () => {
    const body = status();
    body.preview['accounts'] = entry({ waiting: 1, limit: 10, items: [{ id: 3, label: 'a@example.org', due_at: null }] });
    flushLoad(body);
    const open = confirmWith(false);

    element('retention-run-accounts')!.click();

    expect(open.calls.mostRecent().args[1].data.message).toBe('Anonymise 1 account now? This cannot be undone.');
    httpMock.expectNone('/api/superadmin/retention/run');
  });

  it('does nothing when the confirm dialog is cancelled', () => {
    flushLoad(heldTenants());
    const open = confirmWith(false);

    element('retention-run-tenants')!.click();

    expect(open).toHaveBeenCalledTimes(1);
    httpMock.expectNone('/api/superadmin/retention/run');
  });

  it('says so and reloads when more are waiting than were confirmed', () => {
    flushLoad(heldTenants());
    confirmWith(true);
    const snack = snackSpy();

    element('retention-run-tenants')!.click();
    httpMock.expectOne('/api/superadmin/retention/run').flush(
      { error: 'More items are waiting now than when you confirmed. Check the list again.', waiting: { tenants: 3 } },
      { status: 409, statusText: 'Conflict' }
    );

    expect(snack.calls.mostRecent().args[0]).toBe(
      'The number waiting changed from 2 to 3. Nothing was done. Check the list and run it again.');
    flushLoad(heldTenants());
  });

  it('shows the server message when a run is already in progress', () => {
    flushLoad(heldTenants());
    confirmWith(true);
    const snack = snackSpy();

    element('retention-run-tenants')!.click();
    httpMock.expectOne('/api/superadmin/retention/run').flush(
      { error: 'A retention run is in progress. Try again when it has finished.' },
      { status: 409, statusText: 'Conflict' }
    );

    expect(snack.calls.mostRecent().args[0]).toBe('A retention run is in progress. Try again when it has finished.');
    flushLoad(heldTenants());
  });

  it('says how many were done and how many failed', () => {
    flushLoad(heldTenants());
    confirmWith(true);
    const snack = snackSpy();

    element('retention-run-tenants')!.click();
    httpMock.expectOne('/api/superadmin/retention/run').flush({
      message: 'Retention run finished',
      run: run({ status: 'completed_with_errors', results: { tenants: {
        status: 'error', affected: 1, waiting: 2, limit: 1, hold_reason: null,
        errors: [{ entity_id: 7, error: 'ForeignKeyViolation: still referenced' }], error_count: 1 } } })
    });

    expect(snack.calls.mostRecent().args[0]).toBe('Erased 1, 1 failed. See the last runs for the error.');
    flushLoad(heldTenants());
  });

  it('saves the limits and the days overdue together', () => {
    flushLoad(status());
    snackSpy();
    component.limits = { accounts: 5, decisions: 20, tenants: 0 };
    component.backlogDays = 14;

    element('retention-limits-save')!.click();

    const request = httpMock.expectOne('/api/admin/settings/retention');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ limits: { accounts: 5, decisions: 20, tenants: 0 }, backlog_days: 14 });
    request.flush({});
    flushLoad(status());
  });

  it('does not send limits that are not whole numbers', () => {
    flushLoad(status());
    const snack = snackSpy();
    component.limits = { accounts: -1, decisions: 20, tenants: 0 };

    component.saveLimits();

    httpMock.expectNone('/api/admin/settings/retention');
    expect(snack.calls.mostRecent().args[0]).toBe('Each limit must be a whole number, 0 or more.');
  });

  it('turns the automatic run off', () => {
    flushLoad(status());
    const snack = snackSpy();

    element('retention-auto-toggle')!.click();

    const request = httpMock.expectOne('/api/admin/settings/retention');
    expect(request.request.body).toEqual({ auto_run_enabled: false });
    request.flush({});
    expect(snack.calls.mostRecent().args[0]).toBe('The automatic run is off');

    const off = status();
    off.settings.auto_run_enabled = false;
    off.settings.auto_run_active = false;
    off.automatic = { active: false, disabled_by: 'setting', last_run: null };
    flushLoad(off);
    expect(text('retention-auto-state')).toBe('Off');
    expect(text('retention-auto-reason')).toContain('Turned off here');
    expect(text('retention-auto-toggle')).toBe('Turn on the automatic run');
    expect(text('retention-state-login_history')).toContain('The automatic run is off.');
  });

  it('cannot be switched from the page when the environment turns it off', () => {
    const off = status();
    off.settings.auto_run_disabled_by_environment = true;
    off.settings.auto_run_active = false;
    off.automatic = { active: false, disabled_by: 'environment', last_run: null };
    flushLoad(off);

    expect(text('retention-auto-reason')).toContain('RETENTION_AUTO_RUN environment variable');
    expect((element('retention-auto-toggle') as HTMLButtonElement).disabled).toBeTrue();
  });

  it('lists the last runs with who started them, what was done, held back and failed', () => {
    const body = status({
      runs: [
        run({ id: 3, trigger: 'super_admin', started_by: 'root', results: { tenants: {
          status: 'done', affected: 2, waiting: 2, limit: 1, hold_reason: null, errors: [] } } }),
        run({ id: 2, status: 'held_back', results: {
          login_history: { status: 'done', affected: 4, waiting: 4, limit: null, hold_reason: null, errors: [] },
          tenants: { status: 'held_back', affected: 0, waiting: 2, limit: 1, hold_reason: 'over_limit', errors: [] } } }),
        run({ id: 1, trigger: 'cron', status: 'interrupted', duration_ms: null,
          error: 'The run did not finish. The process that ran it stopped.' })
      ]
    });
    body.automatic.last_run = body.runs[1];
    flushLoad(body);

    const rows = Array.from(fixture.nativeElement.querySelectorAll('[data-testid="retention-run-row"]'))
      .map(row => ((row as HTMLElement).textContent as string).replace(/\s+/g, ' ').trim());
    expect(rows.length).toBe(3);
    expect(rows[0]).toContain('Super admin root');
    expect(rows[0]).toContain('Finished');
    expect(rows[0]).toContain('2 tenants');
    expect(rows[1]).toContain('Automatic');
    expect(rows[1]).toContain('Finished, some held back');
    expect(rows[1]).toContain('4 login history entries');
    expect(rows[2]).toContain('Cron job');
    expect(rows[2]).toContain('Stopped before it finished');
    expect(rows[2]).toContain('The run did not finish.');
    expect(text('retention-auto-last-run')).toContain('finished, some held back.');
  });

  it('shows an error when the page cannot be loaded', () => {
    httpMock.expectOne('/api/superadmin/retention').flush({ error: 'Master account access required' }, {
      status: 403, statusText: 'Forbidden'
    });
    fixture.detectChanges();

    expect(text('retention-error')).toContain('Master account access required');
  });
});
