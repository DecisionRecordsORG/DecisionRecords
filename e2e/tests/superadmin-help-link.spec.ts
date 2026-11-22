import { test, expect, Page } from '@playwright/test';
import { loginAsSuperAdmin } from '../fixtures/auth';

/**
 * The help link setting: a super admin points "Can't sign in? Get help" at
 * the installation's own support page, hides it, or goes back to the default.
 */
async function openHelpLinkCard(page: Page): Promise<void> {
  await page.goto('/superadmin/settings', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('[data-testid="support-url-input"]')).toBeVisible({ timeout: 15000 });
}

async function save(page: Page, value: string): Promise<void> {
  await page.locator('[data-testid="support-url-input"]').fill(value);
  const saved = page.waitForResponse(response =>
    response.url().includes('/api/admin/settings/support') && response.request().method() === 'POST');
  await page.locator('[data-testid="support-url-save"]').click();
  expect((await saved).ok()).toBeTruthy();
}

async function signInPageLink(page: Page) {
  await page.context().clearCookies();
  await page.goto('/test-org.com/login', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('[data-testid="email-input"]')).toBeVisible({ timeout: 15000 });
  return page.locator('[data-testid="support-link"]');
}

test.describe('Super admin help link setting', () => {
  test('help-link-setting: an address is saved, used on the sign-in page, and can be hidden or cleared', async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openHelpLinkCard(page);

    // An address of our own
    await save(page, 'https://help.example.org/support');
    await expect(page.locator('[data-testid="support-url-effective"]')).toHaveText(
      'Now: the link leads to https://help.example.org/support.'
    );
    let link = await signInPageLink(page);
    await expect(link).toHaveAttribute('href', 'https://help.example.org/support?topic=signin&org=test-org.com');

    // Hidden
    await loginAsSuperAdmin(page);
    await openHelpLinkCard(page);
    await expect(page.locator('[data-testid="support-url-input"]')).toHaveValue('https://help.example.org/support');
    await save(page, 'none');
    await expect(page.locator('[data-testid="support-url-effective"]')).toHaveText('Now: the link is hidden.');
    link = await signInPageLink(page);
    await expect(link).toHaveCount(0);

    // Cleared: back to this installation's default (Community shows no link)
    await loginAsSuperAdmin(page);
    await openHelpLinkCard(page);
    await save(page, '');
    await expect(page.locator('[data-testid="support-url-effective"]')).toHaveText(/^Now: (no link is shown|the link leads to the Decision Records support page)\.$/);
  });

  test('help-link-invalid: an address that is not http or https cannot be saved', async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openHelpLinkCard(page);

    const input = page.locator('[data-testid="support-url-input"]');
    await input.fill('javascript:alert(1)');
    await input.blur();

    await expect(page.locator('[data-testid="support-url-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="support-url-save"]')).toBeDisabled();
  });
});
