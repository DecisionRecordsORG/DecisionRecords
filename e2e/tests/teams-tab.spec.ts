import { test, expect, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

/**
 * The Teams tab and its two dialogs (Enterprise Edition), outside Teams.
 *
 * Teams is played by the test: a stand-in for the Microsoft Teams JavaScript
 * SDK is put on the page before the app starts, and the tab's API calls are
 * answered here. So these tests cover what the pages do with what Teams and
 * the server tell them; they say nothing about a real Teams client, a real
 * Microsoft sign-in or the real server (the server's side is covered by
 * tests/test_teams_store_v1.py and tests/test_teams_tab_auth.py).
 *
 * Needs the app built with the Enterprise components. In a Community build
 * the tab is not there and the tests are skipped.
 *
 * Set TEAMS_SHOTS_DIR to a folder to keep 1366x768 screenshots of the tab,
 * the decision dialog and the create form, light and dark.
 */

const SHOTS = process.env.TEAMS_SHOTS_DIR;
const APP_HOST = 'https://app.decisionrecords.org';
const TENANT = 'northwind.example';
const USER = { id: 7, email: 'megan@northwind.example', name: 'Megan Bowen' };
const SESSION = { valid: true, user: USER, tenant_domain: TENANT, tab_auth_token: 'tab-token-1' };
const MS_TENANT = 'dddddddd-0000-4000-8000-000000000004';

function decision(id: number, status: string, title: string, context: string, owner = 'Megan Bowen') {
  return {
    id,
    decision_number: id,
    display_id: `NW-${String(id).padStart(3, '0')}`,
    title,
    status,
    context,
    decision: 'We will do this from the first of next month, and review it after two quarters.',
    consequences: 'The team calendar changes. Suppliers are told two weeks ahead.',
    created_at: '2026-11-0' + ((id % 9) + 1) + 'T09:30:00',
    owner_name: owner,
    web_url: `${APP_HOST}/${TENANT}/decision/${id}`,
    spaces: [{ id: 1, name: 'General' }],
  };
}

const DECISIONS = [
  decision(7, 'proposed', 'Review suppliers every quarter instead of every year', 'Two suppliers missed delivery dates this year and we noticed late.'),
  decision(6, 'proposed', 'Hold the planning meeting on Mondays', 'Friday planning leaves the week half decided.', 'Alex Wilber'),
  decision(5, 'accepted', 'Answer customer email within one working day', 'Customers told us that waiting three days is why they call instead.'),
  decision(4, 'accepted', 'Use one shared calendar for site visits', 'Visits were double-booked twice in the spring.', 'Lee Gu'),
  decision(3, 'accepted', 'Keep signed contracts in the document library', 'Contracts were spread over mailboxes.'),
  decision(2, 'archived', 'Print the weekly rota', 'Replaced by the shared calendar.', 'Lee Gu'),
  decision(1, 'superseded', 'Review suppliers once a year', 'The original rule, from when we had four suppliers.'),
];

interface TeamsScenario {
  /** What getAuthToken does: a token, or the error text it rejects with. */
  sso?: { token?: string; error?: string };
  /** What the sign-in window does: the JSON it resolves with, or the error text it rejects with. */
  window?: { result?: string; error?: string };
  theme?: 'default' | 'dark' | 'contrast';
  /** When false there is no SDK at all (the page was opened outside Teams). */
  present?: boolean;
}

/** Put a stand-in for the Teams SDK on the page. Calls made to it are kept in window.__teamsCalls. */
async function playTeams(page: Page, scenario: TeamsScenario = {}) {
  await page.route('**/assets/MicrosoftTeams.min.js', route =>
    route.fulfill({ contentType: 'application/javascript', body: '/* not in Teams */' }));
  if (scenario.present === false) {
    return;
  }
  await page.addInitScript(({ scenario, tenantId, user }) => {
    const calls: { name: string; args: any }[] = [];
    (window as any).__teamsCalls = calls;
    const record = (name: string, args?: any) => { calls.push({ name, args }); };
    (window as any).microsoftTeams = {
      app: {
        initialize: () => { record('app.initialize'); return Promise.resolve(); },
        getContext: () => Promise.resolve({
          app: { theme: scenario.theme || 'default' },
          user: { id: 'object-id-1', userPrincipalName: user.email, loginHint: user.email, tenant: { id: tenantId } },
        }),
        notifySuccess: () => record('app.notifySuccess'),
        registerOnThemeChangeHandler: (handler: any) => { (window as any).__teamsTheme = handler; },
        openLink: (url: string) => { record('app.openLink', url); return Promise.resolve(); },
      },
      authentication: {
        getAuthToken: (options: any) => {
          record('authentication.getAuthToken', options);
          const sso = scenario.sso || { token: 'sso-token' };
          return sso.error ? Promise.reject(new Error(sso.error)) : Promise.resolve(sso.token);
        },
        authenticate: (options: any) => {
          record('authentication.authenticate', options);
          const answer = scenario.window || {};
          return answer.error ? Promise.reject(new Error(answer.error)) : Promise.resolve(answer.result);
        },
      },
      dialog: {
        url: {
          open: (info: any, handler: any) => {
            record('dialog.url.open', info);
            (window as any).__teamsDialogSubmit = handler;
          },
          submit: (result: any) => record('dialog.url.submit', result),
        },
      },
    };
  }, { scenario, tenantId: MS_TENANT, user: USER });
}

interface ServerScenario {
  /** Answer of POST /api/teams/sso/validate. */
  signIn?: { status: number; body: any };
  decisions?: any[];
  /** Tab tokens the server accepts. Any other gets 401. */
  acceptedTokens?: string[];
}

/** Answer the tab's API calls. Requests are kept in the returned list. */
async function playServer(page: Page, scenario: ServerScenario = {}) {
  const requests: { method: string; path: string; authorization: string | null; body: any }[] = [];
  const accepted = scenario.acceptedTokens || ['tab-token-1'];
  const decisions = scenario.decisions || DECISIONS;

  await page.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const authorization = request.headers()['authorization'] || null;
    if (!url.pathname.startsWith('/api/teams/')) {
      // The app shell's own calls (version, features, session): nothing is signed in on the web
      return route.fulfill({ status: 401, contentType: 'application/json', body: '{"error":"Authentication required"}' });
    }
    requests.push({ method: request.method(), path: url.pathname + url.search, authorization, body: request.postDataJSON?.() });
    const json = (status: number, body: any) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    if (url.pathname === '/api/teams/sso/validate') {
      const answer = scenario.signIn || { status: 200, body: SESSION };
      return json(answer.status, answer.body);
    }
    if (!authorization || !accepted.includes(authorization.replace('TabAuth ', ''))) {
      return json(401, { error: 'Authentication required' });
    }
    if (url.pathname === '/api/teams/tab/decisions' && request.method() === 'GET') {
      return json(200, decisions);
    }
    if (url.pathname === '/api/teams/tab/decisions' && request.method() === 'POST') {
      return json(201, { decision: decision(8, 'proposed', request.postDataJSON().title, '') });
    }
    if (url.pathname === '/api/teams/tab/spaces') {
      return json(200, { spaces: [{ id: 1, name: 'General', is_default: true }, { id: 2, name: 'Operations', is_default: false }] });
    }
    const detail = url.pathname.match(/^\/api\/teams\/tab\/decisions\/(\d+)$/);
    if (detail) {
      const found = decisions.find(d => d.id === Number(detail[1]));
      return found ? json(200, found) : json(404, { error: 'Decision not found' });
    }
    return json(404, { error: 'Not found' });
  });
  return requests;
}

async function teamsCalls(page: Page, name: string): Promise<any[]> {
  return page.evaluate(wanted => ((window as any).__teamsCalls || [])
    .filter((call: any) => call.name === wanted).map((call: any) => call.args), name);
}

async function openTab(page: Page) {
  await page.goto('/teams/tab');
  await expect(page.locator('[data-testid="teams-tab-starting"]')).toHaveCount(0, { timeout: 20000 });
}

async function shot(page: Page, name: string) {
  if (!SHOTS) return;
  fs.mkdirSync(SHOTS, { recursive: true });
  // Let the form labels and the theme finish moving
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SHOTS, name) });
}

let available = false;

test.beforeAll(async ({ browser }, testInfo) => {
  // The tab exists only in a build with the Enterprise components
  const page = await browser.newPage({ baseURL: testInfo.project.use.baseURL });
  await playTeams(page);
  await playServer(page);
  await page.goto('/teams/tab');
  try {
    await page.locator('app-teams-tab').waitFor({ state: 'attached', timeout: 20000 });
    available = true;
  } catch {
    available = false;
  }
  await page.close();
});

test.beforeEach(async ({ page }) => {
  test.skip(!available, 'The Teams tab is an Enterprise Edition component; this build does not have it');
  await page.setViewportSize({ width: 1366, height: 768 });
});

test.describe('Teams tab: sign-in', () => {
  test('silent-sign-in: the board opens without asking for anything', async ({ page }) => {
    await playTeams(page);
    const requests = await playServer(page);

    await openTab(page);

    await expect(page.locator('[data-testid="teams-tab-board"]')).toBeVisible();
    await expect(page.locator('[data-testid="teams-tab-card"]')).toHaveCount(DECISIONS.length);
    await expect(page.locator('[data-testid="teams-tab-column-proposed"] [data-testid="teams-tab-card"]')).toHaveCount(2);
    await expect(page.locator('[data-testid="teams-tab-column-accepted"] [data-testid="teams-tab-card"]')).toHaveCount(3);
    // Superseded decisions are shown with the archived ones
    await expect(page.locator('[data-testid="teams-tab-column-archived"] [data-testid="teams-tab-card"]')).toHaveCount(2);

    // The token Teams gave is what was sent to the server, and nothing else identifies the person
    const signIn = requests.find(r => r.path === '/api/teams/sso/validate')!;
    expect(signIn.body).toEqual({ token: 'sso-token' });
    expect(requests.find(r => r.path.startsWith('/api/teams/tab/decisions'))!.authorization).toBe('TabAuth tab-token-1');
    // Teams was told the tab is ready, and no sign-in window was opened
    expect(await teamsCalls(page, 'app.notifySuccess')).toHaveLength(1);
    expect(await teamsCalls(page, 'authentication.authenticate')).toHaveLength(0);
  });

  test('display-id: cards show the organisation\'s own prefix, never a fixed ADR prefix', async ({ page }) => {
    await playTeams(page);
    await playServer(page);

    await openTab(page);

    await expect(page.locator('.ms-card-id').first()).toHaveText('NW-007');
    await expect(page.locator('body')).not.toContainText('ADR-');
  });

  test('consent-fallback: when Teams cannot sign in silently, Sign in opens the sign-in window', async ({ page }) => {
    const session = { tabAuthToken: 'tab-token-1', tenantDomain: TENANT, user: USER };
    await playTeams(page, { sso: { error: 'consent_required' }, window: { result: JSON.stringify(session) } });
    const requests = await playServer(page);

    await openTab(page);

    // Not signed in: says why and offers one way forward. Nothing was loaded.
    await expect(page.locator('[data-testid="teams-tab-signed-out"]')).toBeVisible();
    await expect(page.locator('[data-testid="teams-tab-sign-in-message"]')).toContainText('Microsoft needs your permission');
    await expect(page.locator('[data-testid="teams-tab-board"]')).toHaveCount(0);
    expect(requests.filter(r => r.path.startsWith('/api/teams/tab/'))).toHaveLength(0);
    // The window is never opened by itself: browsers block that
    expect(await teamsCalls(page, 'authentication.authenticate')).toHaveLength(0);

    await page.locator('[data-testid="teams-tab-sign-in"]').click();

    await expect(page.locator('[data-testid="teams-tab-board"]')).toBeVisible();
    await expect(page.locator('[data-testid="teams-tab-signed-in-as"]')).toHaveText('Megan Bowen');
    const [opened] = await teamsCalls(page, 'authentication.authenticate');
    const url = new URL(opened.url);
    expect(url.origin).toBe(new URL(page.url()).origin);
    expect(url.pathname).toBe('/teams/auth-start');
    expect(url.searchParams.get('tid')).toBe(MS_TENANT);
    expect(url.searchParams.get('hint')).toBe(USER.email);
    // The session the window handed over is what the tab uses
    expect(requests.find(r => r.path.startsWith('/api/teams/tab/decisions'))!.authorization).toBe('TabAuth tab-token-1');
  });

  test('sign-in-error: a refused account is told why, in the server\'s words, and gets nothing', async ({ page }) => {
    const refusal = {
      valid: false,
      code: 'guest_account',
      error: 'Guest accounts cannot use Decision Records in this Microsoft 365 organisation. Use it from your own organisation.',
    };
    await playTeams(page, { window: { error: 'CancelledByUser' } });
    const requests = await playServer(page, { signIn: { status: 403, body: refusal } });

    await openTab(page);

    await expect(page.locator('[data-testid="teams-tab-sign-in-message"]')).toContainText('Guest accounts cannot use Decision Records');
    await expect(page.locator('[data-testid="teams-tab-board"]')).toHaveCount(0);
    expect(requests.filter(r => r.path.startsWith('/api/teams/tab/'))).toHaveLength(0);
    expect(await page.evaluate(() => localStorage.getItem('dr_teams_tab_auth'))).toBeNull();

    // Closing the sign-in window is not an error to be alarmed about, and still signs nobody in
    await page.locator('[data-testid="teams-tab-sign-in"]').click();
    await expect(page.locator('[data-testid="teams-tab-sign-in-message"]')).toContainText('Sign-in was cancelled');
    await expect(page.locator('[data-testid="teams-tab-sign-in"]')).toBeEnabled();
    await expect(page.locator('[data-testid="teams-tab-board"]')).toHaveCount(0);
  });

  test('sign-in-error: what the sign-in window reports is shown', async ({ page }) => {
    const reported = JSON.stringify({ code: 'user_limit', message: 'This organization has reached the maximum user limit of 25. Please contact your organisation administrator.' });
    await playTeams(page, { sso: { error: 'resourceDisabled' }, window: { error: reported } });
    await playServer(page);

    await openTab(page);
    await expect(page.locator('[data-testid="teams-tab-sign-in-message"]')).toContainText('could not sign you in automatically');
    await page.locator('[data-testid="teams-tab-sign-in"]').click();

    await expect(page.locator('[data-testid="teams-tab-sign-in-message"]')).toContainText('maximum user limit of 25');
  });

  test('sign-in-error: a server that rejects the token leads to the sign-in screen, not a blank page', async ({ page }) => {
    await playTeams(page, { window: { error: 'FailedToOpenWindow' } });
    await playServer(page, { signIn: { status: 401, body: { valid: false, error: 'Invalid or expired token' } } });

    await openTab(page);
    await expect(page.locator('[data-testid="teams-tab-sign-in-message"]')).toContainText('could not verify your Microsoft sign-in');

    await page.locator('[data-testid="teams-tab-sign-in"]').click();
    await expect(page.locator('[data-testid="teams-tab-sign-in-message"]')).toContainText('Allow pop-ups');
  });

  test('outside-teams: the page says where it works and offers no sign-in', async ({ page }) => {
    await playTeams(page, { present: false });
    const requests = await playServer(page);

    await openTab(page);

    await expect(page.locator('[data-testid="teams-tab-sign-in-message"]')).toContainText('only works inside Microsoft Teams');
    await expect(page.locator('[data-testid="teams-tab-sign-in"]')).toHaveCount(0);
    expect(requests).toHaveLength(0);
  });

  test('expired-session: a tab token the server no longer accepts is replaced by a new sign-in', async ({ page }) => {
    await playTeams(page);
    const requests = await playServer(page, {
      signIn: { status: 200, body: { ...SESSION, tab_auth_token: 'tab-token-2' } },
      acceptedTokens: ['tab-token-2'],
    });
    await page.addInitScript(({ user, tenant }) => {
      localStorage.setItem('dr_teams_tab_auth', JSON.stringify({
        tabAuthToken: 'tab-token-old', tenantDomain: tenant, user, cachedAt: Date.now() }));
    }, { user: USER, tenant: TENANT });

    await openTab(page);

    await expect(page.locator('[data-testid="teams-tab-card"]')).toHaveCount(DECISIONS.length);
    const used = requests.filter(r => r.path === '/api/teams/tab/decisions').map(r => r.authorization);
    expect(used).toEqual(['TabAuth tab-token-old', 'TabAuth tab-token-2']);
  });
});

test.describe('Teams tab: signed in', () => {
  test('signed-in-as-and-sign-out: shows who is signed in; signing out stays signed out until Sign in', async ({ page }) => {
    await playTeams(page);
    const requests = await playServer(page);
    await openTab(page);

    await expect(page.locator('[data-testid="teams-tab-account"]')).toContainText('Signed in as Megan Bowen (megan@northwind.example)');
    await expect(page.locator('[data-testid="teams-tab-account"]')).toContainText(TENANT);

    await page.locator('[data-testid="teams-tab-sign-out"]').click();

    // Signed out of Decision Records only, and the decisions are gone from the page
    await expect(page.locator('[data-testid="teams-tab-signed-out-note"]')).toContainText('still signed in to Microsoft Teams');
    await expect(page.locator('[data-testid="teams-tab-card"]')).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem('dr_teams_tab_auth'))).toBeNull();

    // Opening the tab again does not sign back in by itself
    const before = requests.filter(r => r.path === '/api/teams/sso/validate').length;
    await page.reload();
    await expect(page.locator('[data-testid="teams-tab-signed-out"]')).toBeVisible({ timeout: 20000 });
    expect(await teamsCalls(page, 'authentication.getAuthToken')).toHaveLength(0);
    expect(requests.filter(r => r.path === '/api/teams/sso/validate')).toHaveLength(before);

    // Sign in again: single sign-on, no window needed
    await page.locator('[data-testid="teams-tab-sign-in"]').click();
    await expect(page.locator('[data-testid="teams-tab-board"]')).toBeVisible();
    expect(await teamsCalls(page, 'authentication.authenticate')).toHaveLength(0);
    await page.reload();
    await expect(page.locator('[data-testid="teams-tab-board"]')).toBeVisible({ timeout: 20000 });
  });

  test('search-and-spaces: search narrows the board; a space is asked of the server', async ({ page }) => {
    await playTeams(page);
    const requests = await playServer(page);
    await openTab(page);

    await page.locator('[data-testid="teams-tab-search"]').fill('supplier');
    await expect(page.locator('[data-testid="teams-tab-card"]')).toHaveCount(2);
    await page.locator('[data-testid="teams-tab-search"]').fill('NW-005');
    await expect(page.locator('[data-testid="teams-tab-card"]')).toHaveCount(1);
    await page.locator('[data-testid="teams-tab-search"]').fill('');

    await page.locator('.space-filter mat-select').click();
    await page.locator('mat-option:has-text("Operations")').click();
    await expect.poll(() => requests.some(r => r.path === '/api/teams/tab/decisions?space_id=2')).toBe(true);
  });

  test('dialogs: a card opens the decision dialog and Create opens the form, both on the tab\'s own host', async ({ page }) => {
    await playTeams(page);
    const requests = await playServer(page);
    await openTab(page);
    const origin = new URL(page.url()).origin;

    await page.locator('[data-testid="teams-tab-card"]').first().locator('button').click();
    await page.locator('[data-testid="teams-tab-create"]').click();

    const opened = await teamsCalls(page, 'dialog.url.open');
    expect(opened.map(info => info.url)).toEqual([`${origin}/teams/decision/7`, `${origin}/teams/create`]);
    expect(opened[0].title).toContain('NW-007');

    // When the form reports a new decision, the board is loaded again
    const loads = requests.filter(r => r.path === '/api/teams/tab/decisions' && r.method === 'GET').length;
    await page.evaluate(() => (window as any).__teamsDialogSubmit({ result: { result: 'created' } }));
    await expect.poll(() => requests.filter(r => r.path === '/api/teams/tab/decisions' && r.method === 'GET').length).toBe(loads + 1);
  });

  test('load-failure: a server error is explained with a way to try again', async ({ page }) => {
    await playTeams(page);
    await playServer(page);
    await page.route('**/api/teams/tab/decisions', route => route.fulfill({ status: 500, body: '{}' }));

    await openTab(page);

    await expect(page.locator('[data-testid="teams-tab-error"]')).toContainText('could not be loaded');
    await page.unroute('**/api/teams/tab/decisions');
    await page.locator('[data-testid="teams-tab-error"] button').click();
    await expect(page.locator('[data-testid="teams-tab-card"]')).toHaveCount(DECISIONS.length);
  });

  test('mobile: on a phone the board is one column and nothing scrolls sideways', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 740 });
    await playTeams(page);
    await playServer(page);

    await openTab(page);

    await expect(page.locator('[data-testid="teams-tab-card"]')).toHaveCount(DECISIONS.length);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    const columns = await page.locator('.kanban-column').evaluateAll(nodes => nodes.map(n => n.getBoundingClientRect().left));
    expect(new Set(columns.map(Math.round)).size).toBe(1);
    await expect(page.locator('[data-testid="teams-tab-sign-out"]')).toBeVisible();
    await expect(page.locator('[data-testid="teams-tab-create"]')).toBeVisible();
    await shot(page, 'teams-tab-board-mobile-375.png');
  });
});

test.describe('Teams tab: dialogs', () => {
  test('open-in-browser: the decision dialog links to the decision\'s page in the web app', async ({ page }) => {
    await playTeams(page);
    await playServer(page);
    await page.addInitScript(() => localStorage.setItem('dr_teams_tab_auth', JSON.stringify({
      tabAuthToken: 'tab-token-1', tenantDomain: 'northwind.example',
      user: { id: 7, email: 'megan@northwind.example', name: 'Megan Bowen' }, cachedAt: Date.now() })));

    await page.goto('/teams/decision/7');

    await expect(page.locator('[data-testid="teams-detail-id"]')).toHaveText('NW-007');
    await expect(page.locator('.decision-title')).toHaveText('Review suppliers every quarter instead of every year');
    await page.locator('[data-testid="teams-detail-open"]').click();

    // /{tenant}/decision/{id} on the app host: the route the web app has
    expect(await teamsCalls(page, 'app.openLink')).toEqual([`${APP_HOST}/${TENANT}/decision/7`]);
    await expect(page.locator('[data-testid="teams-detail-open"]')).toContainText('View in Decision Records');
  });

  test('decision-dialog-sign-in: opened without a session, the dialog signs in first', async ({ page }) => {
    await playTeams(page);
    const requests = await playServer(page);

    await page.goto('/teams/decision/5');

    await expect(page.locator('[data-testid="teams-detail-id"]')).toHaveText('NW-005');
    expect(requests.map(r => r.path)).toEqual(['/api/teams/sso/validate', '/api/teams/tab/decisions/5']);
  });

  test('decision-dialog-not-found: a decision that is not there is said to be so', async ({ page }) => {
    await playTeams(page);
    await playServer(page);

    await page.goto('/teams/decision/999');

    await expect(page.locator('.error-container')).toContainText('Decision not found');
  });

  test('create-form: a decision is created with the tab token and the dialog reports it', async ({ page }) => {
    await playTeams(page);
    const requests = await playServer(page);

    await page.goto('/teams/create');
    await expect(page.locator('.form-header')).toContainText('Record a decision for your team');
    await expect(page.locator('body')).not.toContainText(/architecture/i);
    await page.locator('input[formControlName="title"]').fill('Close the office between the holidays');
    await page.locator('textarea[formControlName="context"]').fill('Hardly anyone is in, and heating the building costs a lot.');
    await page.locator('button[type="submit"]').click();

    await expect.poll(async () => (await teamsCalls(page, 'dialog.url.submit')).length).toBe(1);
    const created = requests.find(r => r.method === 'POST' && r.path === '/api/teams/tab/decisions')!;
    expect(created.authorization).toBe('TabAuth tab-token-1');
    expect(created.body).toMatchObject({
      title: 'Close the office between the holidays', status: 'proposed', space_id: 1 });
    const [reported] = await teamsCalls(page, 'dialog.url.submit');
    expect(reported.result).toBe('created');
  });

  test('create-form-refused: without a sign-in the form says why and creates nothing', async ({ page }) => {
    await playTeams(page, { sso: { error: 'CancelledByUser' } });
    const requests = await playServer(page);

    await page.goto('/teams/create');

    await expect(page.locator('.error-container')).toContainText('Sign-in was cancelled');
    expect(requests.filter(r => r.method === 'POST' && r.path === '/api/teams/tab/decisions')).toHaveLength(0);
  });
});

test.describe('Teams SDK loading', () => {
  test('the web app does not load the Teams SDK on its ordinary pages', async ({ page }) => {
    const sdkRequests: string[] = [];
    page.on('request', request => {
      if (request.url().includes('MicrosoftTeams')) sdkRequests.push(request.url());
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    expect(sdkRequests).toEqual([]);
    expect(await page.evaluate(() => typeof (window as any).microsoftTeams)).toBe('undefined');
  });

  test('the tab loads the copy of the SDK served with the app', async ({ page }) => {
    const sdkRequests: string[] = [];
    await playServer(page);
    await page.route('**/assets/MicrosoftTeams.min.js', route => {
      sdkRequests.push(new URL(route.request().url()).pathname);
      return route.fulfill({ contentType: 'application/javascript', body: '/* stand-in */' });
    });

    await page.goto('/teams/tab');

    await expect(page.locator('[data-testid="teams-tab-signed-out"]')).toBeVisible({ timeout: 20000 });
    expect(sdkRequests).toEqual(['/assets/MicrosoftTeams.min.js']);
  });
});

test.describe('Teams tab: screenshots', () => {
  for (const theme of ['default', 'dark', 'contrast'] as const) {
    const label = theme === 'default' ? 'light' : theme;

    test(`screenshots-${label}: board, decision and create form at 1366x768`, async ({ page }) => {
      await playTeams(page, { theme });
      await playServer(page);

      await openTab(page);
      await expect(page.locator('[data-testid="teams-tab-card"]')).toHaveCount(DECISIONS.length);
      await expect(page.locator('.teams-tab-container')).toHaveClass(
        theme === 'default' ? /teams-tab-container/ : new RegExp(`${theme}-theme`));
      await shot(page, `teams-tab-board-${label}.png`);

      await page.goto('/teams/decision/7');
      await expect(page.locator('[data-testid="teams-detail-id"]')).toHaveText('NW-007');
      await shot(page, `teams-tab-decision-${label}.png`);

      await page.goto('/teams/create');
      await expect(page.locator('input[formControlName="title"]')).toBeVisible();
      await page.locator('input[formControlName="title"]').fill('Close the office between the holidays');
      await page.locator('textarea[formControlName="context"]').fill('Hardly anyone is in during that week, and heating the building costs a lot.');
      await page.locator('input[formControlName="title"]').blur();
      await shot(page, `teams-tab-create-${label}.png`);
    });
  }
});
