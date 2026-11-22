import { test, expect, request, Page } from '@playwright/test';
import { fillFormUntilReady } from '../fixtures/auth';

/**
 * Account recovery, as a person who lost their password goes through it:
 * ask for a link on the sign-in page, open the link, choose a new password,
 * sign in with it and reach the organisation's decisions.
 *
 * The link normally arrives by email. The tests have no mailbox, so the link
 * comes from the test-only endpoint /api/test/create-setup-token, which
 * creates the same kind of token the recovery email carries.
 */
const API_URL = process.env.E2E_API_URL || 'http://localhost:5002';
const OLD_PASSWORD = 'OldPass123';
const NEW_PASSWORD = 'NewPass456';

async function createAccount(email: string): Promise<void> {
  const api = await request.newContext({ baseURL: API_URL });
  const response = await api.post('/api/test/create-user', {
    data: { email, password: OLD_PASSWORD, name: 'Recovery Tester', role: 'user', domain: email.split('@')[1] },
  });
  expect(response.ok()).toBeTruthy();
  await api.dispose();
}

async function recoveryLink(email: string): Promise<string> {
  const api = await request.newContext({ baseURL: API_URL });
  const response = await api.post('/api/test/create-setup-token', {
    data: { email, purpose: 'account_recovery' },
  });
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  await api.dispose();
  return body.setup_url;
}

async function enterEmail(page: Page, domain: string, email: string): Promise<void> {
  await page.goto(`/${domain}/login`, { waitUntil: 'domcontentloaded' });
  const continueButton = page.locator('[data-testid="continue-button"]');
  await fillFormUntilReady([[page.locator('[data-testid="email-input"]'), email]], continueButton);
  await continueButton.click();
  await expect(page.locator('[data-testid="login-view"]')).toBeVisible({ timeout: 10000 });
}

test.describe('Account recovery', () => {
  test('recovery-flow: a recovery link leads to a new password and a working sign-in', async ({ page }) => {
    const domain = 'recover-test.com';
    const email = `pat-${Date.now()}@${domain}`;
    await createAccount(email);

    // Ask for a link on the sign-in page
    await enterEmail(page, domain, email);
    await page.locator('[data-testid="forgot-credentials"]').click();
    await expect(page.locator('[data-testid="recovery-email-input"]')).toHaveValue(email);
    await page.locator('[data-testid="recovery-submit"]').click();
    await expect(page.locator('[data-testid="success-message"]')).toContainText(
      'If an account exists with this email, a recovery link has been sent.'
    );

    // Open the link: the setup page, worded for recovery, with the token intact
    const link = await recoveryLink(email);
    expect(link).toMatch(new RegExp(`^/${domain.replace('.', '\\.')}/setup\\?token=`));
    await page.goto(link, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('[data-testid="setup-title"]')).toContainText('Reset Your Credentials', { timeout: 15000 });
    expect(new URL(page.url()).pathname).toBe(`/${domain}/setup`);

    // Choose a new password
    await page.locator('[data-testid="password-option"]').click();
    const submit = page.locator('[data-testid="setup-password-submit"]');
    await fillFormUntilReady(
      [
        [page.locator('[data-testid="setup-password-input"]'), NEW_PASSWORD],
        [page.locator('[data-testid="setup-confirm-input"]'), NEW_PASSWORD],
      ],
      submit
    );
    await submit.click();
    await page.waitForURL(`**/${domain}/login`, { timeout: 15000 });

    // Sign in with the new password and reach the organisation, not a setup page
    const continueButton = page.locator('[data-testid="continue-button"]');
    await fillFormUntilReady([[page.locator('[data-testid="email-input"]'), email]], continueButton);
    await continueButton.click();
    await page.locator('[data-testid="password-input"]').fill(NEW_PASSWORD);
    await page.locator('[data-testid="login-button"]').click();
    await page.waitForURL(url => url.pathname === `/${domain}`, { timeout: 20000 });
    expect(page.url()).not.toContain('/profile');
    expect(page.url()).not.toContain('setup=');

    // The old password no longer works
    const api = await request.newContext({ baseURL: API_URL });
    const oldPassword = await api.post('/api/auth/login', { data: { email, password: OLD_PASSWORD } });
    expect(oldPassword.status()).toBe(401);
    await api.dispose();
  });

  test('recovery-link-once: a used recovery link says so', async ({ page }) => {
    const domain = 'recover-test.com';
    const email = `sam-${Date.now()}@${domain}`;
    await createAccount(email);
    const link = await recoveryLink(email);
    const token = new URL(link, 'http://localhost').searchParams.get('token');

    const api = await request.newContext({ baseURL: API_URL });
    const used = await api.post('/api/auth/setup-password', { data: { token, password: NEW_PASSWORD } });
    expect(used.ok()).toBeTruthy();
    await api.dispose();

    await page.goto(link, { waitUntil: 'domcontentloaded' });

    await expect(page.locator('[data-testid="setup-error"]')).toContainText('Link Already Used', { timeout: 15000 });
  });

  test('recovery-old-address: the address older links may carry does not show an organisation page', async ({ page }) => {
    // There is no /<domain>/recover page. Nothing links to it any more; an
    // old bookmark falls back to the landing page instead of a broken view.
    await page.goto('/recover-test.com/recover?token=abc', { waitUntil: 'domcontentloaded' });

    await page.waitForURL(url => url.pathname === '/', { timeout: 15000 });
  });
});
