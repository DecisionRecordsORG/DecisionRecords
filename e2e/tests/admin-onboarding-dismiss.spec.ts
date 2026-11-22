import { test, expect, request } from '@playwright/test';
import { loginAsUser } from '../fixtures/auth';

/**
 * The first-admin onboarding dialog stays dismissed.
 *
 * The administrator here has the role on their membership only (the legacy
 * users.is_admin column is not set), like a member promoted through a role
 * request. Dismissing used to be refused for them, so the dialog came back on
 * every visit.
 */
const API_URL = process.env.E2E_API_URL || 'http://localhost:5002';
const PASSWORD = 'TestPass123';

test.describe('Admin onboarding dialog', () => {
  test('onboarding-stays-dismissed: an administrator by membership dismisses the dialog once', async ({ page }) => {
    const stamp = Date.now();
    const domain = `onboard-${stamp}.com`;
    const email = `owner@${domain}`;
    const api = await request.newContext({ baseURL: API_URL });
    const created = await api.post('/api/test/create-user', {
      data: { email, password: PASSWORD, name: 'Onboard Owner', role: 'admin', domain },
    });
    expect(created.ok()).toBeTruthy();
    await api.dispose();

    await loginAsUser(page, email, PASSWORD);
    await page.waitForURL(url => url.pathname === `/${domain}`, { timeout: 20000 });

    const gotIt = page.locator('button:has-text("Got it")');
    await expect(gotIt).toBeVisible({ timeout: 15000 });
    const dismissed = page.waitForResponse(response => response.url().includes('/api/user/dismiss-admin-onboarding'));
    await gotIt.click();
    expect((await dismissed).status()).toBe(200);
    await expect(gotIt).toBeHidden({ timeout: 5000 });

    // The next visit does not show it again
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(4000);
    await expect(gotIt).toHaveCount(0);
  });
});
