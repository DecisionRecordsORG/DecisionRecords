import { test, expect, Page } from '@playwright/test';
import { fillFormUntilReady } from '../fixtures/auth';

/**
 * Asking to join an organisation and being approved.
 *
 * What the sign-in page tells the requester must match what approval does.
 * The test installation has no email configured, so the truthful wording is
 * that an administrator passes the setup link on. The wording for an
 * installation that can send email is covered by answering the status request
 * the way such a server does.
 */
const DOMAIN = 'test-org.com';

async function askToJoin(page: Page, email: string): Promise<void> {
  await page.context().clearCookies();
  await page.goto(`/${DOMAIN}/login`, { waitUntil: 'domcontentloaded' });
  const continueButton = page.locator('[data-testid="continue-button"]');
  await fillFormUntilReady([[page.locator('[data-testid="email-input"]'), email]], continueButton);
  await continueButton.click();

  await page.locator('input[formcontrolname="first_name"]').fill('New');
  await page.locator('input[formcontrolname="last_name"]').fill('Comer');
  await page.locator('button:has-text("Submit Request")').click();
  await expect(page.locator('[data-testid="request-sent-message"]')).toBeVisible({ timeout: 10000 });
}

test.describe('Access request approval', () => {
  test('request-wording-no-email: without email the requester is told the administrator gives the link', async ({ page }) => {
    const email = `newcomer-${Date.now()}@${DOMAIN}`;

    await askToJoin(page, email);

    const message = page.locator('[data-testid="request-sent-message"]');
    await expect(message).toHaveText(
      'Your request has been submitted. An administrator of your organization will approve it and give you a link to set up your sign-in.'
    );
    await expect(page.locator('body')).not.toContainText('receive an email');
  });

  test('access-pending-wording: after verifying an email address the page promises an email only when one can be sent', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto(`/${DOMAIN}/login?access_requested=1`, { waitUntil: 'domcontentloaded' });

    const note = page.locator('[data-testid="access-pending-note"]');
    await expect(note).toContainText(
      'When it is approved, the administrator will give you a link to set up your sign-in.',
      { timeout: 10000 }
    );
    await expect(note).not.toContainText('email');

    // The same page on an installation that can send email
    await page.route(`**/api/auth/tenant/${DOMAIN}`, async route => {
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...(await response.json()), email_available: true } });
    });
    await page.reload({ waitUntil: 'domcontentloaded' });

    await expect(note).toContainText(
      'When it is approved, you will receive an email with a link to set up your sign-in. If the email cannot be sent, the administrator will give you the link.',
      { timeout: 10000 }
    );
  });
});
