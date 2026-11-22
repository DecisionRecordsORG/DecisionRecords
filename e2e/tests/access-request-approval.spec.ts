import { test, expect, Page } from '@playwright/test';
import { fillFormUntilReady, loginAsUser } from '../fixtures/auth';

/**
 * Asking to join an organisation and being approved.
 *
 * What the sign-in page tells the requester must match what approval does.
 * The test installation has no email configured, so the truthful wording is
 * that an administrator passes the setup link on, and the administrator is
 * told so when approving. The case where the link is emailed is covered by
 * answering the approval the way a server with email does.
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

// admin@test-org.com is an administrator by the role on their membership only
// (the legacy users.is_admin column is not set), like a member promoted
// through a role request. The settings page and its endpoints must agree
// that this person is an administrator.
async function openAccessRequests(page: Page): Promise<void> {
  await loginAsUser(page, `admin@${DOMAIN}`, 'TestPass123');
  await page.goto(`/${DOMAIN}/admin`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('tab', { name: /Access Requests/ }).click();
}

async function approve(page: Page, email: string): Promise<void> {
  const row = page.locator('tr', { hasText: email });
  await expect(row).toBeVisible({ timeout: 10000 });
  await row.locator('[data-testid="approve-request"]').click();
  await page.locator('mat-dialog-container button:has-text("Approve")').click();
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

  test('approve-no-email: the administrator is told to pass the link on', async ({ page }) => {
    const email = `joiner-${Date.now()}@${DOMAIN}`;
    await askToJoin(page, email);

    await openAccessRequests(page);
    await approve(page, email);

    const delivery = page.locator('[data-testid="delivery-message"]');
    await expect(delivery).toContainText(
      `Email is not set up, so no email was sent. Give this link to ${email} yourself.`,
      { timeout: 10000 }
    );
    await expect(page.locator('[data-testid="setup-link-instruction"]')).toContainText('Share this setup link with the user');
    await expect(page.locator('mat-dialog-container input[readonly]')).toHaveValue(new RegExp(`/${DOMAIN.replace('.', '\\.')}/setup\\?token=`));
    await expect(page.locator('[data-testid="send-setup-email"]')).toContainText('Send Email');
  });

  test('approve-emailed: the administrator is told the link was emailed', async ({ page }) => {
    const email = `mailed-${Date.now()}@${DOMAIN}`;
    await askToJoin(page, email);

    // Answer as a server with email configured does: the same approval, with the email sent
    await page.route('**/api/admin/access-requests/*/approve', async route => {
      const response = await route.fetch();
      const body = await response.json();
      await route.fulfill({
        response,
        json: { ...body, email_sent: true, delivery_message: `The setup link was emailed to ${email}.` },
      });
    });

    await openAccessRequests(page);
    await approve(page, email);

    await expect(page.locator('[data-testid="delivery-message"]')).toContainText(
      `The setup link was emailed to ${email}.`,
      { timeout: 10000 }
    );
    await expect(page.locator('[data-testid="setup-link-instruction"]')).toContainText(
      'You can also copy the link and send it yourself.'
    );
    await expect(page.locator('[data-testid="send-setup-email"]')).toContainText('Send again');
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
