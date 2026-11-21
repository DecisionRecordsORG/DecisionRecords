import { test, expect, Page } from '@playwright/test';
import { loginAsUser, dismissOverlays } from '../fixtures/auth';

/**
 * Decision relationship packs in organization settings.
 *
 * Packs for non-technical teams are offered beside the original ones. Only
 * Core is selected until an administrator turns another pack on.
 */
const NEW_PACKS = ['People & Policy', 'Finance & Procurement', 'Product & Customer'];
const ORIGINAL_PACKS = ['Core', 'Software Delivery', 'Data & Analytics', 'Security & Risk', 'Operations & Service'];

async function openRelationshipSettings(page: Page): Promise<void> {
  await loginAsUser(page, 'admin@test-org.com', 'TestPass123');
  await page.goto('/test-org.com/admin');
  await page.waitForLoadState('networkidle');
  await dismissOverlays(page);
  await page.getByRole('tab', { name: 'Decision Relationships' }).click();
  await expect(page.locator('mat-card-title', { hasText: 'Relationship Packs' })).toBeVisible({ timeout: 10000 });
}

function packCard(page: Page, label: string) {
  return page.locator('.relationship-pack-card', {
    has: page.locator('mat-checkbox', { hasText: new RegExp(`^\\s*${label}\\s*$`) })
  });
}

test.describe('Decision relationship packs', () => {
  test('packs-listed: Settings offer packs for non-technical teams beside the original ones', async ({ page }) => {
    await openRelationshipSettings(page);

    for (const label of [...ORIGINAL_PACKS, ...NEW_PACKS]) {
      await expect(packCard(page, label)).toBeVisible();
    }
    await expect(packCard(page, 'Core')).toContainText('Default relationship classes that fit any kind of decision.');
    await expect(packCard(page, 'Finance & Procurement')).toContainText(
      'Useful for budget, spending, supplier, and contract decisions.'
    );
    await expect(page.locator('.relationship-pack-grid')).not.toContainText(/architecture/i);
  });

  test('packs-not-auto-enabled: New packs are off until an administrator selects them', async ({ page }) => {
    await openRelationshipSettings(page);

    for (const label of NEW_PACKS) {
      await expect(packCard(page, label).locator('input[type="checkbox"]')).not.toBeChecked();
    }
    await expect(page.locator('.relationship-type-label', { hasText: /^Funds$/ })).toHaveCount(0);
  });

  test('pack-select: Selecting Finance & Procurement lists its relationship classes', async ({ page }) => {
    await openRelationshipSettings(page);

    await packCard(page, 'Finance & Procurement').locator('input[type="checkbox"]').check();

    for (const label of ['Funds', 'Approves', 'Constrains', 'Exception to']) {
      await expect(page.locator('.relationship-type-label', { hasText: new RegExp(`^${label}$`) })).toBeVisible();
    }
    // Not saved: leave the tenant's stored settings as they were
  });
});
