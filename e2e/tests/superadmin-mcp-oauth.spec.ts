import { test, expect, APIRequestContext, Page } from '@playwright/test';
import { loginAsSuperAdmin } from '../fixtures/auth';
import * as fs from 'fs';

/**
 * The super admin switch "Let apps connect by signing in (OAuth)" on the MCP
 * page (Enterprise Edition).
 *
 * Needs the Enterprise backend with the OAuth addresses set, as
 * oauth-consent.spec.ts does; skipped without it.
 *
 * Set OAUTH_SHOTS_DIR to a folder to keep screenshots of the page.
 */

const API_URL = 'http://localhost:5002';
const SHOTS = process.env.OAUTH_SHOTS_DIR;

let available = false;

function setUp(request: APIRequestContext, data: Record<string, unknown>) {
  return request.post(`${API_URL}/api/test/oauth-setup`, { data });
}

async function metadataStatus(request: APIRequestContext): Promise<number> {
  return (await request.get(`${API_URL}/.well-known/oauth-protected-resource`)).status();
}

async function shot(page: Page, name: string) {
  if (!SHOTS) {
    return;
  }
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.addStyleTag({ content: 'app-cookie-consent, .mat-mdc-snack-bar-container { display: none !important; }' });
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}

async function openPage(page: Page) {
  await page.goto('/superadmin/mcp');
  await expect(page.getByTestId('mcp-oauth-toggle')).toBeVisible({ timeout: 20000 });
}

test.describe('Super admin: letting apps connect by signing in', () => {
  test.beforeAll(async ({ request }) => {
    const response = await setUp(request, { enabled: false }).catch(() => null);
    available = !!response && response.ok();
    if (!available) {
      console.log('Super admin OAuth switch tests skipped: Enterprise backend with OAuth addresses not available');
    }
  });

  test.beforeEach(async () => {
    test.skip(!available, 'Needs the Enterprise backend with MCP_RESOURCE_URL and OAUTH_ISSUER set');
  });

  test.afterAll(async ({ request }) => {
    if (available) {
      // Leave it as the other OAuth tests expect to find it
      await setUp(request, { enabled: true });
    }
  });

  test('it can be switched on and off, and says what switching off does', async ({ page, request }) => {
    await setUp(request, { enabled: false });
    await loginAsSuperAdmin(page);
    await openPage(page);

    const toggle = page.getByTestId('mcp-oauth-toggle').getByRole('switch');
    await expect(page.getByTestId('mcp-oauth-toggle')).toContainText('Let apps connect by signing in (OAuth)');
    await expect(toggle).not.toBeChecked();
    await expect(toggle).toBeEnabled();
    await expect(page.getByTestId('mcp-oauth-status')).toHaveText('Off');
    await expect(page.getByTestId('mcp-oauth-blockers')).toHaveCount(0);
    const effect = page.getByTestId('mcp-oauth-off-effect');
    await expect(effect).toContainText('stop working until it is switched on again');
    await expect(effect).toContainText('Nothing is deleted');
    await expect(page.getByTestId('mcp-oauth-resource')).toHaveText('http://localhost:4200/api/mcp');
    await expect(page.getByTestId('mcp-oauth-issuer')).toHaveText('http://localhost:4200');
    expect(await metadataStatus(request)).toBe(404);
    await shot(page, 'superadmin-switch-off');

    await toggle.click();

    await expect(page.getByTestId('mcp-oauth-status')).toHaveText('On');
    await expect(toggle).toBeChecked();
    expect(await metadataStatus(request)).toBe(200);
    await shot(page, 'superadmin-switch-on');
    // It is still on after loading the page again
    await openPage(page);
    await expect(page.getByTestId('mcp-oauth-toggle').getByRole('switch')).toBeChecked();

    await page.getByTestId('mcp-oauth-toggle').getByRole('switch').click();

    await expect(page.getByTestId('mcp-oauth-status')).toHaveText('Off');
    expect(await metadataStatus(request)).toBe(404);
  });

  test('it cannot be switched on while the MCP server is off, and says why', async ({ page, request }) => {
    await setUp(request, { system_mcp: false });
    await loginAsSuperAdmin(page);
    await openPage(page);

    const toggle = page.getByTestId('mcp-oauth-toggle').getByRole('switch');
    await expect(toggle).not.toBeChecked();
    await expect(toggle).toBeDisabled();
    const blockers = page.getByTestId('mcp-oauth-blockers');
    await expect(blockers).toContainText('It cannot be switched on yet, because:');
    await expect(page.getByTestId('mcp-oauth-blocker-mcp_off')).toHaveText('The MCP server is switched off for this installation.');
    await expect(page.getByTestId('mcp-oauth-blocker-ai_off')).toHaveCount(0);
    await expect(blockers.getByRole('link', { name: 'System settings' })).toBeVisible();
    await shot(page, 'superadmin-switch-blocked');

    // The server refuses as well, whatever the page allows
    const csrf = (await page.request.get('/api/auth/csrf-token')).headers()['x-csrf-token'];
    const response = await page.request.put('/api/admin/settings/oauth', {
      data: { enabled: true }, headers: { 'X-CSRF-Token': csrf },
    });
    expect(response.status()).toBe(409);
    expect((await response.json()).blockers[0].code).toBe('mcp_off');
  });

  test('with AI switched off as well, both reasons are listed', async ({ page, request }) => {
    await setUp(request, { system_ai: false, system_mcp: false });
    await loginAsSuperAdmin(page);
    await openPage(page);

    await expect(page.getByTestId('mcp-oauth-toggle').getByRole('switch')).toBeDisabled();
    await expect(page.getByTestId('mcp-oauth-blocker-ai_off')).toHaveText('AI features are switched off for this installation.');
    await expect(page.getByTestId('mcp-oauth-blocker-mcp_off')).toBeVisible();
  });

  test('it cannot be switched on while external API access is off for the installation', async ({ page, request }) => {
    await setUp(request, { enabled: false, system_external_api: false });
    await loginAsSuperAdmin(page);
    await openPage(page);

    const toggle = page.getByTestId('mcp-oauth-toggle').getByRole('switch');
    await expect(toggle).not.toBeChecked();
    await expect(toggle).toBeDisabled();
    const blockers = page.getByTestId('mcp-oauth-blockers');
    await expect(blockers).toContainText('It cannot be switched on yet, because:');
    await expect(page.getByTestId('mcp-oauth-blocker-external_api_off'))
      .toHaveText('External AI API access is switched off for this installation.');
    await expect(page.getByTestId('mcp-oauth-blocker-mcp_off')).toHaveCount(0);
    await expect(blockers.getByRole('link', { name: 'System settings' })).toBeVisible();
    await shot(page, 'superadmin-switch-blocked-external-api');

    const csrf = (await page.request.get('/api/auth/csrf-token')).headers()['x-csrf-token'];
    const response = await page.request.put('/api/admin/settings/oauth', {
      data: { enabled: true }, headers: { 'X-CSRF-Token': csrf },
    });
    expect(response.status()).toBe(409);
    expect((await response.json()).blockers[0].code).toBe('external_api_off');
  });

  test('switched on with external API access off, it says it is not working', async ({ page, request }) => {
    await setUp(request, { enabled: true, system_external_api: false });
    await loginAsSuperAdmin(page);
    await openPage(page);

    await expect(page.getByTestId('mcp-oauth-blockers')).toContainText('It is switched on but not working, because:');
    await expect(page.getByTestId('mcp-oauth-blocker-external_api_off')).toBeVisible();
    // Switching off is always possible
    const toggle = page.getByTestId('mcp-oauth-toggle').getByRole('switch');
    await expect(toggle).toBeChecked();
    await expect(toggle).toBeEnabled();
  });

  test('someone who is not the super admin cannot read or change the setting', async ({ request }) => {
    expect((await request.get(`${API_URL}/api/admin/settings/oauth`)).status()).toBe(401);
    expect((await request.put(`${API_URL}/api/admin/settings/oauth`, { data: { enabled: true } })).status()).toBeGreaterThanOrEqual(401);
  });
});
