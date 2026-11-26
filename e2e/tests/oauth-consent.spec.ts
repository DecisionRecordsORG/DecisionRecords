import { test, expect, Page, APIRequestContext } from '@playwright/test';
import { loginAsUser, fillFormUntilReady } from '../fixtures/auth';
import * as crypto from 'crypto';
import * as fs from 'fs';

/**
 * Connecting an app by OAuth (Enterprise Edition): the consent page, being
 * led back to it after sign-in, and the lists of connected apps.
 *
 * The app that asks for access is played by the test: its address
 * (client.example.org) is intercepted in the browser, and a small page stands
 * in for it that shows what it was sent back.
 *
 * Needs the Enterprise backend with the OAuth addresses set:
 *   DECISION_RECORDS_EDITION=enterprise FLASK_ENV=testing \
 *   MCP_RESOURCE_URL=http://localhost:4200/api/mcp OAUTH_ISSUER=http://localhost:4200
 * Without it (Community Edition, or the addresses missing) the tests are skipped.
 *
 * Set OAUTH_SHOTS_DIR to a folder to keep screenshots of the pages.
 */

const API_URL = 'http://localhost:5002';
const RESOURCE = 'http://localhost:4200/api/mcp';
const CLIENT_ID = 'https://client.example.org/oauth/client.json';
const CLIENT_NAME = 'Example Assistant';
const REDIRECT = 'https://client.example.org/callback';
const LOOPBACK_CLIENT_ID = 'https://desktop.example.org/oauth/client.json';
const LOOPBACK_REDIRECT = 'http://localhost:49152/callback';
// The known apps, each by the exact address of its identity document.
// Claude Code on someone's computer:
const CLAUDE_CODE_ID = 'https://claude.ai/oauth/claude-code-client-metadata';
// Claude on the web, desktop and mobile:
const CLAUDE_ID = 'https://claude.ai/oauth/mcp-oauth-client-metadata';
const CLAUDE_REDIRECT = 'https://claude.ai/api/mcp/auth_callback';
// ChatGPT, at the stable address it presents to a server that identifies its issuer:
const CHATGPT_ID = 'https://chatgpt.com/oauth/client.json';
const CHATGPT_REDIRECT = 'https://chatgpt.com/connector_platform_oauth_redirect';
// Other addresses on the same hosts. Not listed, so not known: a host serves many addresses,
// some with content its users chose. The first is a shared page; the second is what ChatGPT
// presents to a server that does not identify its issuer, different for every connection
const SAME_HOST_ID = 'https://claude.ai/share/anything.json';
const SAME_HOST_REDIRECT = 'https://claude.ai/api/mcp/auth_callback';
const CHATGPT_PER_CONNECTION_ID = 'https://chatgpt.com/oauth/abc123/client.json';
// An app on a look-alike address that gives itself Claude's name
const LOOKALIKE_ID = 'https://claude.ai.example.org/oauth/client.json';
const LOOKALIKE_REDIRECT = 'https://claude.ai.example.org/callback';
const USER = { email: 'user@test-org.com', password: 'TestPass123' };
const ADMIN = { email: 'admin@test-org.com', password: 'TestPass123' };
// A member of two organisations in the test that needs one; kept apart so the other tests see one organisation
const MEMBER_OF_TWO = { email: 'steward@test-org.com', password: 'TestPass123' };
const SHOTS = process.env.OAUTH_SHOTS_DIR;

let available = false;

function pkce() {
  const verifier = crypto.randomBytes(48).toString('base64url');
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
  return { verifier, challenge };
}

function authorizeUrl(challenge: string, options: { clientId?: string; redirect?: string; scope?: string; state?: string } = {}): string {
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: options.clientId || CLIENT_ID,
    redirect_uri: options.redirect || REDIRECT,
    code_challenge: challenge,
    code_challenge_method: 'S256',
    resource: RESOURCE,
    scope: options.scope || 'decisions:read decisions:write',
    state: options.state || 'state-from-the-app',
  });
  return `/oauth/authorize?${params.toString()}`;
}

async function setUp(request: APIRequestContext, extra: Record<string, unknown> = {}) {
  return request.post(`${API_URL}/api/test/oauth-setup`, {
    data: {
      clients: [
        { client_id: CLIENT_ID, client_name: CLIENT_NAME, redirect_uris: [REDIRECT] },
        { client_id: LOOPBACK_CLIENT_ID, client_name: 'Desktop Helper',
          redirect_uris: ['http://localhost/callback', 'http://127.0.0.1/callback'] },
        { client_id: SAME_HOST_ID, client_name: 'Claude', redirect_uris: [SAME_HOST_REDIRECT] },
        { client_id: CLAUDE_ID, client_name: 'Claude', redirect_uris: [CLAUDE_REDIRECT] },
        { client_id: CHATGPT_ID, client_name: 'ChatGPT', redirect_uris: [CHATGPT_REDIRECT] },
        { client_id: CHATGPT_PER_CONNECTION_ID, client_name: 'ChatGPT', redirect_uris: [CHATGPT_REDIRECT] },
        { client_id: CLAUDE_CODE_ID, client_name: 'Claude Code',
          redirect_uris: ['http://localhost/callback', 'http://127.0.0.1/callback'] },
        { client_id: LOOKALIKE_ID, client_name: 'Claude (Anthropic)', redirect_uris: [LOOKALIKE_REDIRECT] },
      ],
      ai_enabled_domains: ['test-org.com'],
      ...extra,
    },
  });
}

/** The page that plays the app: shows what the browser brought back. */
async function playTheApp(page: Page) {
  const handler = async (route: any) => {
    const url = new URL(route.request().url());
    const lines = Array.from(url.searchParams.entries()).map(([name, value]) => `<li data-name="${name}">${name}: <code>${value.replace(/</g, '&lt;')}</code></li>`);
    await route.fulfill({
      contentType: 'text/html',
      body: `<html><body><h1>Example Assistant received</h1><ul>${lines.join('')}</ul></body></html>`,
    });
  };
  await page.route('https://client.example.org/callback**', handler);
  await page.route(`${SAME_HOST_REDIRECT}**`, handler);
  await page.route(`${CHATGPT_REDIRECT}**`, handler);
  await page.route(`${LOOKALIKE_REDIRECT}**`, handler);
  await page.route('http://localhost:49152/callback**', handler);
}

function broughtBack(page: Page): URLSearchParams {
  return new URL(page.url()).searchParams;
}

async function shot(page: Page, name: string) {
  if (!SHOTS) {
    return;
  }
  fs.mkdirSync(SHOTS, { recursive: true });
  // Keep the app's cookie notice and passing messages out of the picture
  await page.addStyleTag({ content: 'app-cookie-consent, .mat-mdc-snack-bar-container { display: none !important; }' });
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}

async function exchange(request: APIRequestContext, code: string, verifier: string, clientId = CLIENT_ID, redirect = REDIRECT) {
  const response = await request.post(`${API_URL}/oauth/token`, {
    form: { grant_type: 'authorization_code', code, client_id: clientId, redirect_uri: redirect, code_verifier: verifier, resource: RESOURCE },
  });
  expect(response.status(), await response.text()).toBe(200);
  return response.json();
}

async function mcpStatus(request: APIRequestContext, accessToken: string): Promise<number> {
  const response = await request.post(`${API_URL}/api/mcp`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: { jsonrpc: '2.0', id: 1, method: 'tools/list' },
  });
  return response.status();
}

/** Connect the example app for the signed-in user through the real pages; returns the tokens. */
async function connect(page: Page, request: APIRequestContext, options: { write?: boolean } = {}) {
  const { verifier, challenge } = pkce();
  await page.goto(authorizeUrl(challenge));
  await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });
  if (options.write === false) {
    await page.getByTestId('consent-write-switch').getByRole('switch').click();
  }
  await page.getByTestId('consent-allow').click();
  await page.waitForURL('https://client.example.org/callback**');
  return exchange(request, broughtBack(page).get('code')!, verifier);
}

test.describe('Connecting an app (OAuth consent)', () => {
  test.beforeAll(async ({ request }) => {
    const response = await setUp(request).catch(() => null);
    available = !!response && response.ok();
    if (!available) {
      console.log('OAuth end-to-end tests skipped: Enterprise backend with OAuth addresses not available',
        response ? `(${response.status()} ${await response.text()})` : '');
    }
  });

  test.beforeEach(async ({ page, request }) => {
    test.skip(!available, 'Needs the Enterprise backend with MCP_RESOURCE_URL and OAUTH_ISSUER set');
    await setUp(request, {
      ai_enabled_domains: ['test-org.com', 'new-org.com'],
    });
    await playTheApp(page);
  });

  test('a signed-in person sees who is asking and can allow it', async ({ page, request }) => {
    await loginAsUser(page, USER.email, USER.password);
    const { verifier, challenge } = pkce();

    await page.goto(authorizeUrl(challenge));

    await expect(page).toHaveURL(/\/oauth\/consent\?request=/);
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });
    // The host is the identity; the name is the app's own claim, beside it
    await expect(page.getByTestId('consent-app-host')).toHaveText('client.example.org');
    await expect(page.getByTestId('consent-claimed-name')).toHaveText(CLIENT_NAME);
    await expect(page.getByTestId('consent-unverified')).toContainText('Unverified app');
    await expect(page.getByTestId('consent-redirect-host')).toHaveText('client.example.org');
    await expect(page.getByTestId('consent-loopback-warning')).toHaveCount(0);
    await expect(page.getByTestId('consent-account')).toContainText('Test User');
    await expect(page.getByTestId('consent-not-you')).toBeVisible();
    await expect(page.getByTestId('consent-organisation')).toContainText('test-org.com');
    await expect(page.getByTestId('consent-read')).toContainText('Search and read');
    await expect(page.getByTestId('consent-write-switch').getByRole('switch')).toBeChecked();
    // No navigation bar and no cookie notice: one question on the page
    await expect(page.locator('app-navbar')).toHaveCount(0);
    await expect(page.locator('app-cookie-consent')).toHaveCount(0);
    // Words a person reads, not the protocol's
    const text = (await page.getByTestId('oauth-consent').innerText()).toLowerCase();
    for (const jargon of ['scope', 'grant', 'oauth', 'token', 'client_id', 'redirect']) {
      expect(text, `the page says "${jargon}"`).not.toContain(jargon);
    }
    await shot(page, 'consent-single-organisation');

    await page.getByTestId('consent-allow').click();

    await page.waitForURL('https://client.example.org/callback**');
    const back = broughtBack(page);
    expect(back.get('state')).toBe('state-from-the-app');
    expect(back.get('iss')).toBe('http://localhost:4200');
    expect(back.get('code')).toMatch(/^dro_ac_/);
    const tokens = await exchange(request, back.get('code')!, verifier);
    expect(tokens.scope).toBe('decisions:read decisions:write');
    expect(await mcpStatus(request, tokens.access_token)).toBe(200);
  });

  test('the heading has focus and everything can be reached with the keyboard', async ({ page }) => {
    await loginAsUser(page, USER.email, USER.password);
    await page.goto(authorizeUrl(pkce().challenge));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });

    await expect(page.getByTestId('consent-heading')).toBeFocused();
    const reached: string[] = [];
    for (let presses = 0; presses < 8; presses++) {
      await page.keyboard.press('Tab');
      const id = await page.evaluate(() => {
        const element = document.activeElement as HTMLElement | null;
        return element?.closest('[data-testid]')?.getAttribute('data-testid') || element?.tagName || '';
      });
      reached.push(id);
    }
    expect(reached).toEqual(expect.arrayContaining(['consent-not-you', 'consent-write-switch', 'consent-cancel', 'consent-allow']));
    // Cancel comes before Allow, and Enter on Cancel refuses
    expect(reached.indexOf('consent-cancel')).toBeLessThan(reached.indexOf('consent-allow'));
    await page.getByTestId('consent-cancel').focus();
    await page.keyboard.press('Enter');
    await page.waitForURL('https://client.example.org/callback**');
    expect(broughtBack(page).get('error')).toBe('access_denied');
  });

  test('cancelling tells the app and connects nothing', async ({ page, request }) => {
    await loginAsUser(page, USER.email, USER.password);
    await page.goto(authorizeUrl(pkce().challenge));
    await expect(page.getByTestId('consent-cancel')).toBeEnabled({ timeout: 20000 });

    await page.getByTestId('consent-cancel').click();

    await page.waitForURL('https://client.example.org/callback**');
    const back = broughtBack(page);
    expect(back.get('error')).toBe('access_denied');
    expect(back.get('state')).toBe('state-from-the-app');
    expect(back.get('code')).toBeNull();
  });

  test('switching off changes means the app can only read', async ({ page, request }) => {
    await loginAsUser(page, USER.email, USER.password);
    const tokens = await connect(page, request, { write: false });
    expect(tokens.scope).toBe('decisions:read');
    const response = await request.post(`${API_URL}/api/mcp`, {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
      data: { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'create_decision', arguments: {
        title: 'T', context: 'c', decision: 'd', consequences: 'q' } } },
    });
    expect(response.status()).toBe(403);
  });

  test('someone who is not signed in is asked to sign in and led back afterwards', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto(authorizeUrl(pkce().challenge));

    await expect(page.getByTestId('consent-signed-out')).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId('consent-heading')).toHaveText('Sign in to connect an app');
    await expect(page.getByTestId('consent-allow')).toHaveCount(0);
    const consentUrl = page.url();

    // Sign in the ordinary way, without clearing the cookie that remembers the request
    await page.goto('/test-org.com/login', { waitUntil: 'domcontentloaded' });
    const emailInput = page.locator('[data-testid="email-input"]');
    const continueButton = page.locator('[data-testid="continue-button"]');
    await fillFormUntilReady([[emailInput, USER.email]], continueButton);
    await continueButton.click();
    await page.waitForSelector('[data-testid="login-view"], [data-testid="password-form"]', { timeout: 10000 });
    await page.locator('[data-testid="password-input"]').fill(USER.password);
    await page.locator('[data-testid="login-button"]').click();

    // Led back to the same request, by a page load
    await page.waitForURL(/\/oauth\/consent\?request=/, { timeout: 30000 });
    expect(new URL(page.url()).searchParams.get('request')).toBe(new URL(consentUrl).searchParams.get('request'));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });
    await expect(page.getByTestId('consent-app-host')).toHaveText('client.example.org');

    // Once only: going elsewhere afterwards does not bring the page back
    await page.goto('/test-org.com');
    await page.waitForTimeout(1500);
    expect(page.url()).not.toContain('/oauth/consent');
  });

  test('with several organisations the person chooses, and sees why one cannot be chosen', async ({ page, request }) => {
    await setUp(request, {
      memberships: [{ email: MEMBER_OF_TWO.email, domain: 'new-org.com' }],
      ai_enabled_domains: ['test-org.com'],
      ai_disabled_domains: ['new-org.com'],
    });
    await loginAsUser(page, MEMBER_OF_TWO.email, MEMBER_OF_TWO.password);
    await page.goto(authorizeUrl(pkce().challenge));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });

    const available = page.getByTestId('consent-organisation-test-org.com').getByRole('radio');
    const unavailable = page.getByTestId('consent-organisation-new-org.com').getByRole('radio');
    await expect(available).toBeChecked();
    await expect(unavailable).toBeDisabled();
    await expect(page.getByTestId('consent-reason-new-org.com')).toContainText('AI features are switched off');
    await shot(page, 'consent-several-organisations');

    await page.getByTestId('consent-allow').click();
    await page.waitForURL('https://client.example.org/callback**');
    expect(broughtBack(page).get('code')).toMatch(/^dro_ac_/);
  });

  test('an organisation with AI switched off cannot be connected, only cancelled', async ({ page, request }) => {
    await setUp(request, { ai_enabled_domains: [], ai_disabled_domains: ['test-org.com'] });
    await loginAsUser(page, USER.email, USER.password);
    await page.goto(authorizeUrl(pkce().challenge));

    await expect(page.getByTestId('consent-organisation-reason')).toContainText('AI features are switched off', { timeout: 20000 });
    await expect(page.getByTestId('consent-allow')).toBeDisabled();
    await expect(page.getByTestId('consent-cannot-allow')).toBeVisible();
    await shot(page, 'consent-ai-switched-off');

    await page.getByTestId('consent-cancel').click();
    await page.waitForURL('https://client.example.org/callback**');
    expect(broughtBack(page).get('error')).toBe('access_denied');
  });

  test('an organisation with outside access switched off says so', async ({ page, request }) => {
    await setUp(request, { ai_enabled_domains: [], external_access_disabled_domains: ['test-org.com'] });
    await loginAsUser(page, USER.email, USER.password);
    await page.goto(authorizeUrl(pkce().challenge));

    await expect(page.getByTestId('consent-organisation-reason')).toContainText('External AI access', { timeout: 20000 });
    await expect(page.getByTestId('consent-allow')).toBeDisabled();
  });

  test('with outside access switched off for the whole installation, the page says so', async ({ page, request }) => {
    await setUp(request, { system_external_api: false });
    try {
      await loginAsUser(page, USER.email, USER.password);
      await page.goto(authorizeUrl(pkce().challenge));

      await expect(page.getByTestId('consent-organisation-reason'))
        .toContainText('switched off for this installation', { timeout: 20000 });
      await expect(page.getByTestId('consent-allow')).toBeDisabled();
    } finally {
      await setUp(request);
    }
  });

  test('an app on this computer gets a warning instead of a website to return to', async ({ page, request }) => {
    await loginAsUser(page, USER.email, USER.password);
    const { verifier, challenge } = pkce();
    await page.goto(authorizeUrl(challenge, { clientId: LOOPBACK_CLIENT_ID, redirect: LOOPBACK_REDIRECT }));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });

    const warning = page.getByTestId('consent-loopback-warning');
    await expect(warning).toBeVisible();
    await expect(warning).toContainText('runs on your own computer');
    await expect(warning).toContainText('localhost');
    await expect(warning).toContainText('Any program on this computer');
    await expect(page.getByTestId('consent-redirect')).toHaveCount(0);
    await expect(page.getByTestId('consent-app-host')).toHaveText('desktop.example.org');
    await shot(page, 'consent-loopback-app');

    await page.getByTestId('consent-allow').click();
    await page.waitForURL('http://localhost:49152/callback**');
    const tokens = await exchange(request, broughtBack(page).get('code')!, verifier, LOOPBACK_CLIENT_ID, LOOPBACK_REDIRECT);
    expect(await mcpStatus(request, tokens.access_token)).toBe(200);
  });

  test('a known app is shown by its listed name, with a neutral label', async ({ page, request }) => {
    await loginAsUser(page, USER.email, USER.password);
    const { verifier, challenge } = pkce();
    await page.goto(authorizeUrl(challenge, { clientId: CLAUDE_CODE_ID, redirect: LOOPBACK_REDIRECT }));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });

    await expect(page.getByTestId('consent-known-name')).toHaveText('Claude Code (Anthropic)');
    await expect(page.getByTestId('consent-known')).toContainText('Known app');
    await expect(page.getByTestId('consent-app-host')).toHaveText('claude.ai');
    await expect(page.getByTestId('consent-unverified')).toHaveCount(0);
    await expect(page.getByTestId('consent-claimed-name')).toHaveCount(0);
    await expect(page.getByTestId('oauth-consent')).not.toContainText('It calls itself');
    await shot(page, 'consent-known-app');

    await page.getByTestId('consent-allow').click();
    await page.waitForURL('http://localhost:49152/callback**');
    const tokens = await exchange(request, broughtBack(page).get('code')!, verifier, CLAUDE_CODE_ID, LOOPBACK_REDIRECT);
    expect(await mcpStatus(request, tokens.access_token)).toBe(200);
  });

  test('a known app on this computer still gets the warning', async ({ page }) => {
    await loginAsUser(page, USER.email, USER.password);
    await page.goto(authorizeUrl(pkce().challenge, { clientId: CLAUDE_CODE_ID, redirect: LOOPBACK_REDIRECT }));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });

    await expect(page.getByTestId('consent-known-name')).toHaveText('Claude Code (Anthropic)');
    await expect(page.getByTestId('consent-known')).toBeVisible();
    const warning = page.getByTestId('consent-loopback-warning');
    await expect(warning).toBeVisible();
    await expect(warning).toContainText('Any program on this computer');
    await expect(page.getByTestId('consent-redirect')).toHaveCount(0);
    await shot(page, 'consent-known-app-on-this-computer');
  });

  for (const app of [
    { id: CLAUDE_ID, redirect: CLAUDE_REDIRECT, name: 'Claude (Anthropic)', host: 'claude.ai', shot: 'consent-known-app-claude' },
    { id: CHATGPT_ID, redirect: CHATGPT_REDIRECT, name: 'ChatGPT (OpenAI)', host: 'chatgpt.com', shot: 'consent-known-app-chatgpt' },
  ]) {
    test(`${app.name} is a known app, with a website to return to and no warning`, async ({ page, request }) => {
      await playTheApp(page);
      await loginAsUser(page, USER.email, USER.password);
      const { verifier, challenge } = pkce();
      await page.goto(authorizeUrl(challenge, { clientId: app.id, redirect: app.redirect }));
      await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });

      await expect(page.getByTestId('consent-known-name')).toHaveText(app.name);
      await expect(page.getByTestId('consent-known')).toContainText('Known app');
      await expect(page.getByTestId('consent-app-host')).toHaveText(app.host);
      await expect(page.getByTestId('consent-unverified')).toHaveCount(0);
      await expect(page.getByTestId('consent-claimed-name')).toHaveCount(0);
      await expect(page.getByTestId('consent-loopback-warning')).toHaveCount(0);
      await expect(page.getByTestId('consent-redirect-host')).toHaveText(app.host);
      await shot(page, app.shot);

      await page.getByTestId('consent-allow').click();
      await page.waitForURL(`${app.redirect}**`);
      // The app is told who answered: the issuer, on the way back
      expect(broughtBack(page).get('iss')).toBeTruthy();
      const tokens = await exchange(request, broughtBack(page).get('code')!, verifier, app.id, app.redirect);
      expect(await mcpStatus(request, tokens.access_token)).toBe(200);
    });
  }

  test('the address ChatGPT presents without issuer identification is an unverified app', async ({ page }) => {
    await loginAsUser(page, USER.email, USER.password);
    await page.goto(authorizeUrl(pkce().challenge, { clientId: CHATGPT_PER_CONNECTION_ID, redirect: CHATGPT_REDIRECT }));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });

    await expect(page.getByTestId('consent-app-host')).toHaveText('chatgpt.com');
    await expect(page.getByTestId('consent-unverified')).toContainText('Unverified app');
    await expect(page.getByTestId('consent-claimed-name')).toHaveText('ChatGPT');
    await expect(page.getByTestId('consent-known')).toHaveCount(0);
    await expect(page.getByTestId('consent-known-name')).toHaveCount(0);
  });

  test('another address on a known app\'s host is an unverified app', async ({ page }) => {
    await loginAsUser(page, USER.email, USER.password);
    await page.goto(authorizeUrl(pkce().challenge, { clientId: SAME_HOST_ID, redirect: SAME_HOST_REDIRECT }));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });

    await expect(page.getByTestId('consent-app-host')).toHaveText('claude.ai');
    await expect(page.getByTestId('consent-unverified')).toContainText('Unverified app');
    await expect(page.getByTestId('consent-claimed-name')).toHaveText('Claude');
    await expect(page.getByTestId('consent-known')).toHaveCount(0);
    await expect(page.getByTestId('consent-known-name')).toHaveCount(0);
    await expect(page.getByTestId('consent-redirect-host')).toHaveText('claude.ai');
    await shot(page, 'consent-same-host-not-known');
  });

  test('an app on a look-alike address that calls itself Claude stays unverified', async ({ page }) => {
    await loginAsUser(page, USER.email, USER.password);
    await page.goto(authorizeUrl(pkce().challenge, { clientId: LOOKALIKE_ID, redirect: LOOKALIKE_REDIRECT }));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });

    await expect(page.getByTestId('consent-app-host')).toHaveText('claude.ai.example.org');
    await expect(page.getByTestId('consent-unverified')).toContainText('Unverified app');
    await expect(page.getByTestId('consent-claimed-name')).toHaveText('Claude (Anthropic)');
    await expect(page.getByTestId('consent-known')).toHaveCount(0);
    await expect(page.getByTestId('consent-known-name')).toHaveCount(0);
    await shot(page, 'consent-look-alike-app');
  });

  test('the page fits a narrow screen', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 760 });
    await loginAsUser(page, USER.email, USER.password);
    await page.goto(authorizeUrl(pkce().challenge));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    for (const id of ['consent-app-host', 'consent-unverified', 'consent-cancel', 'consent-allow']) {
      const box = await page.getByTestId(id).boundingBox();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(360);
    }
    await shot(page, 'consent-narrow-screen');
  });

  test('the page shows nothing inside a frame of another page', async ({ page }) => {
    await loginAsUser(page, USER.email, USER.password);
    // The server redirects to the consent page; take the address without loading it at the top
    const started = await page.request.get(authorizeUrl(pkce().challenge), { maxRedirects: 0 });
    const consentPath = new URL(started.headers()['location']).pathname + new URL(started.headers()['location']).search;

    await page.route('**/framing-page.html', route => route.fulfill({
      contentType: 'text/html',
      body: `<html><body><h1>Win a prize</h1><iframe id="hidden" src="${consentPath}" style="width:600px;height:700px"></iframe></body></html>`,
    }));
    await page.goto('/framing-page.html');

    const frame = page.frameLocator('#hidden');
    await expect(frame.getByTestId('consent-framed')).toBeVisible({ timeout: 20000 });
    await expect(frame.getByTestId('consent-allow')).toHaveCount(0);
    await expect(frame.getByTestId('consent-cancel')).toHaveCount(0);
    await expect(frame.getByTestId('consent-app-host')).toHaveCount(0);
  });

  test('"Not you?" signs out so another account can sign in', async ({ page }) => {
    await loginAsUser(page, USER.email, USER.password);
    await page.goto(authorizeUrl(pkce().challenge));
    await expect(page.getByTestId('consent-not-you')).toBeEnabled({ timeout: 20000 });

    await page.getByTestId('consent-not-you').click();

    await page.waitForURL(url => !url.pathname.startsWith('/oauth/'), { timeout: 20000 });
    const me = await page.request.get('/api/user/me');
    expect(me.status()).toBe(401);
  });

  test('a request that has expired or is unknown says so and offers nothing to click', async ({ page }) => {
    await loginAsUser(page, USER.email, USER.password);
    await page.goto('/oauth/consent?request=no-such-request');

    await expect(page.getByTestId('consent-problem')).toContainText('expired', { timeout: 20000 });
    await expect(page.getByTestId('consent-allow')).toHaveCount(0);
    await expect(page.getByTestId('consent-heading')).toBeFocused();
  });
});

test.describe('Connected apps', () => {
  test.beforeAll(async ({ request }) => {
    const response = await setUp(request).catch(() => null);
    available = !!response && response.ok();
  });

  test.beforeEach(async ({ page, request }) => {
    test.skip(!available, 'Needs the Enterprise backend with MCP_RESOURCE_URL and OAUTH_ISSUER set');
    await setUp(request, { ai_enabled_domains: ['test-org.com', 'new-org.com'] });
    await playTheApp(page);
  });

  async function disconnectEverything(page: Page) {
    const grants = await (await page.request.get('/api/user/oauth/grants')).json();
    const csrf = (await page.request.get('/api/auth/csrf-token')).headers()['x-csrf-token'];
    for (const grant of grants) {
      await page.request.delete(`/api/user/oauth/grants/${grant.id}`, { headers: { 'X-CSRF-Token': csrf } });
    }
  }

  test('a person sees the apps they connected and can disconnect one', async ({ page, request }) => {
    await loginAsUser(page, USER.email, USER.password);
    await disconnectEverything(page);
    const tokens = await connect(page, request);
    expect(await mcpStatus(request, tokens.access_token)).toBe(200);

    await page.goto('/test-org.com/profile');
    const card = page.getByTestId('connected-apps-user');
    await expect(card).toBeVisible({ timeout: 20000 });
    const row = card.getByTestId('connected-app');
    await expect(row).toHaveCount(1);
    await expect(row.getByTestId('connected-app-host')).toHaveText('client.example.org');
    await expect(row).toContainText(CLIENT_NAME);
    await expect(row.getByTestId('connected-app-permission')).toHaveText('Can read and change records');
    await expect(row).toContainText('Connected');
    await expect(row).toContainText('Last used');
    await expect(row).toContainText('Asks again');
    await card.scrollIntoViewIfNeeded();
    await shot(page, 'connected-apps-profile');

    const button = row.getByTestId('connected-app-disconnect');
    await expect(button).toHaveAccessibleName('Disconnect client.example.org');
    await button.click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toContainText('Disconnect client.example.org?');
    await expect(dialog).toContainText('stop working with decision records at once');
    // Cancelling the question changes nothing
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(row).toHaveCount(1);
    expect(await mcpStatus(request, tokens.access_token)).toBe(200);

    await button.click();
    await page.getByRole('dialog').getByRole('button', { name: 'Disconnect' }).click();

    await expect(card.getByTestId('connected-apps-empty')).toBeVisible();
    expect(await mcpStatus(request, tokens.access_token)).toBe(401);
  });

  test('an administrator sees members\' connected apps and can disconnect one', async ({ page, request }) => {
    await loginAsUser(page, USER.email, USER.password);
    await disconnectEverything(page);
    const tokens = await connect(page, request, { write: false });

    await loginAsUser(page, ADMIN.email, ADMIN.password);
    const card = page.getByTestId('connected-apps-tenant');
    // The settings page asks for a dozen things at once, and the test backend's
    // in-memory database sometimes fails one of them; load the page again if so.
    await expect(async () => {
      await page.goto('/test-org.com/admin');
      await page.getByRole('tab', { name: 'AI & API' }).click();
      await expect(card).toBeVisible({ timeout: 8000 });
    }).toPass({ timeout: 60000 });
    const row = card.getByTestId('connected-app');
    await expect(row).toHaveCount(1);
    await expect(row.getByTestId('connected-app-host')).toHaveText('client.example.org');
    await expect(row.getByTestId('connected-app-unverified')).toHaveText('Unverified app');
    await expect(row.getByTestId('connected-app-user')).toHaveText('Test User');
    await expect(row.getByTestId('connected-app-permission')).toHaveText('Can read records');
    // People are named, not shown by address
    await expect(card).not.toContainText(USER.email);
    await card.scrollIntoViewIfNeeded();
    await shot(page, 'connected-apps-organisation');

    await row.getByTestId('connected-app-disconnect').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toContainText('Test User will have to connect it again');
    await dialog.getByRole('button', { name: 'Disconnect' }).click();

    await expect(card.getByTestId('connected-apps-empty')).toBeVisible();
    expect(await mcpStatus(request, tokens.access_token)).toBe(401);
  });

  test('a known app is listed by its name, an unverified one by its address', async ({ page, request }) => {
    await loginAsUser(page, USER.email, USER.password);
    await disconnectEverything(page);
    await connect(page, request);
    const { verifier, challenge } = pkce();
    await page.goto(authorizeUrl(challenge, { clientId: CLAUDE_CODE_ID, redirect: LOOPBACK_REDIRECT }));
    await expect(page.getByTestId('consent-allow')).toBeEnabled({ timeout: 20000 });
    await page.getByTestId('consent-allow').click();
    await page.waitForURL('http://localhost:49152/callback**');
    await exchange(request, broughtBack(page).get('code')!, verifier, CLAUDE_CODE_ID, LOOPBACK_REDIRECT);

    await page.goto('/test-org.com/profile');
    const card = page.getByTestId('connected-apps-user');
    await expect(card.getByTestId('connected-app')).toHaveCount(2, { timeout: 20000 });
    const known = card.getByTestId('connected-app').filter({ has: page.getByTestId('connected-app-known') });
    await expect(known).toHaveCount(1);
    await expect(known.getByTestId('connected-app-known-name')).toHaveText('Claude Code (Anthropic)');
    await expect(known.getByTestId('connected-app-host')).toHaveText('claude.ai');
    await expect(known).not.toContainText('calls itself');
    await expect(known.getByTestId('connected-app-disconnect')).toHaveAccessibleName('Disconnect Claude Code (Anthropic)');
    const other = card.getByTestId('connected-app').filter({ has: page.getByTestId('connected-app-unverified') });
    await expect(other).toHaveCount(1);
    await expect(other.getByTestId('connected-app-host')).toHaveText('client.example.org');
    await card.scrollIntoViewIfNeeded();
    await shot(page, 'connected-apps-known-and-unverified');
    await disconnectEverything(page);
  });

  test('organisation settings say that outside access covers apps that sign in', async ({ page }) => {
    await loginAsUser(page, ADMIN.email, ADMIN.password);
    const description = page.getByTestId('ai-external-access-description');
    await expect(async () => {
      await page.goto('/test-org.com/admin');
      await page.getByRole('tab', { name: 'AI & API' }).click();
      await expect(description).toBeVisible({ timeout: 8000 });
    }).toPass({ timeout: 60000 });
    await expect(description).toContainText('by signing in from the app');
    await expect(description).toContainText('Switching this off stops both');
    const summary = page.getByTestId('api-access-summary');
    await expect(summary).toContainText('only what the member who connected it can do');
    // The list the text points to is on the same tab, framed like the cards above it
    const card = page.getByTestId('connected-apps-tenant');
    await expect(card).toBeVisible({ timeout: 20000 });
    await expect(card).toHaveCSS('border-radius', '12px');
    await expect(card).toHaveCSS('border-top-color', 'rgb(226, 232, 240)');
    await card.scrollIntoViewIfNeeded();
    await shot(page, 'organisation-settings-api-access');
  });

  test('a member who is not an administrator does not see the organisation list', async ({ page }) => {
    await loginAsUser(page, USER.email, USER.password);
    const response = await page.request.get('/api/tenant/oauth/grants');
    expect(response.status()).toBe(403);
  });
});
