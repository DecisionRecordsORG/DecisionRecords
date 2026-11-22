import { test, expect, Page } from '@playwright/test';
import { fillFormUntilReady } from '../fixtures/auth';

/**
 * Help for people who cannot sign in.
 *
 * The sign-in page links to the public support page. Whether there is a
 * support page depends on the installation, which the app learns from
 * /api/features, so each test answers that request the way the hosted service
 * or a self-hosted installation would.
 */
async function answerFeatures(page: Page, overrides: Record<string, unknown>): Promise<void> {
  await page.route('**/api/features', async route => {
    const response = await route.fetch();
    const flags = await response.json();
    await route.fulfill({ response, json: { ...flags, ...overrides } });
  });
}

test.describe('Help for people who cannot sign in', () => {
  test('signin-help-link: the sign-in page links to support with the email and organisation', async ({ page }) => {
    await answerFeatures(page, { marketing_pages: true });
    await page.goto('/test-org.com/login', { waitUntil: 'domcontentloaded' });

    const link = page.locator('[data-testid="support-link"]');
    await expect(link).toHaveText("Can't sign in? Get help");
    await expect(link).toHaveAttribute('target', '_blank');
    await expect(link).toHaveAttribute('href', 'https://decisionrecords.org/support?topic=signin&org=test-org.com');

    await fillFormUntilReady(
      [[page.locator('[data-testid="email-input"]'), 'admin@test-org.com']],
      page.locator('[data-testid="continue-button"]')
    );

    await expect(link).toHaveAttribute(
      'href',
      'https://decisionrecords.org/support?topic=signin&email=admin%40test-org.com&org=test-org.com'
    );
  });

  test('signin-help-link-configured: a self-hosted installation links to the support page it configured', async ({ page }) => {
    await answerFeatures(page, { marketing_pages: false, support_url: 'https://help.example.org/it' });
    await page.goto('/test-org.com/login', { waitUntil: 'domcontentloaded' });

    await expect(page.locator('[data-testid="support-link"]')).toHaveAttribute(
      'href',
      'https://help.example.org/it?topic=signin&org=test-org.com'
    );
  });

  test('signin-help-link-hidden: a self-hosted installation with no support page shows no link', async ({ page }) => {
    await answerFeatures(page, { marketing_pages: false, support_url: undefined });
    await page.goto('/test-org.com/login', { waitUntil: 'domcontentloaded' });

    // The continue button is enabled only by the running app, so the page is ready here.
    await fillFormUntilReady(
      [[page.locator('[data-testid="email-input"]'), 'admin@test-org.com']],
      page.locator('[data-testid="continue-button"]')
    );
    await expect(page.locator('[data-testid="support-link"]')).toHaveCount(0);
  });
});
