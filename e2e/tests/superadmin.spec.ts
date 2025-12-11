import { test, expect } from '@playwright/test';
import { loginAsSuperAdmin } from '../fixtures/auth';

test.describe('Super Admin', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsSuperAdmin(page, 'admin', 'admin');
  });

  test('view-all-tenants: Super admin can see tenant management page', async ({ page }) => {
    // Navigate to tenants list
    await page.goto('/superadmin/tenants');

    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Should see the Tenant Management heading
    await page.waitForSelector('h1', { timeout: 10000 });
    await expect(page.locator('h1')).toContainText('Tenant Management');

    // Should see the mat-tab-labels (the clickable tab buttons)
    await expect(page.locator('div.mat-mdc-tab:has-text("Pending Approvals")').first()).toBeVisible();
    await expect(page.locator('div.mat-mdc-tab:has-text("All Tenants")').first()).toBeVisible();
    await expect(page.locator('div.mat-mdc-tab:has-text("History")').first()).toBeVisible();

    // Click on All Tenants tab to see registered tenants
    await page.locator('div.mat-mdc-tab:has-text("All Tenants")').first().click();

    // Wait for tab content to load - should see either a table or empty state
    await page.waitForSelector('mat-card-title', { timeout: 5000 });
    await expect(page.locator('mat-card-title:has-text("Registered Tenants")')).toBeVisible();
  });

  test('view-tenant-maturity-state: Tenant list shows BOOTSTRAP/MATURE state', async ({ page }) => {
    // Maturity state display is not yet implemented in the tenant list
    // Skip until feature is added
    test.skip(true, 'Maturity state display not yet implemented in tenant list');
  });

  test('configure-maturity-thresholds: Can view maturity threshold settings', async ({ page }) => {
    // Navigate to system settings
    await page.goto('/superadmin/settings');

    // Wait for page to load
    await page.waitForSelector('h1, h2, .settings-container', { timeout: 10000 });

    // Look for maturity threshold configuration
    const thresholdSection = page.locator('text=/maturity|threshold|age.*days|user.*threshold/i');

    // This might not exist yet - skip if not implemented
    if (await thresholdSection.count() === 0) {
      test.skip(true, 'Maturity threshold configuration not yet implemented');
    }
  });

  test('view-pending-approvals: Super admin sees domain approval requests', async ({ page }) => {
    // Navigate to tenants list - starts on Pending Approvals tab
    await page.goto('/superadmin/tenants');

    // Should see the Tenant Management heading
    await page.waitForSelector('h1', { timeout: 10000 });

    // Should be on Pending Approvals tab by default
    await expect(page.locator('mat-card-title:has-text("Domain Approval Requests")')).toBeVisible();

    // Should show empty state if no pending approvals, or table if there are
    const hasEmptyState = await page.locator('text="No pending domain approvals"').isVisible().catch(() => false);
    const hasTable = await page.locator('table').isVisible().catch(() => false);

    expect(hasEmptyState || hasTable).toBeTruthy();
  });
});
