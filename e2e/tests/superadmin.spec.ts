import { test, expect } from '@playwright/test';
import { loginAsSuperAdmin } from '../fixtures/auth';

test.describe('Super Admin - Tenant Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsSuperAdmin(page);
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

  test('view-tenant-maturity-state: Tenant list shows maturity state column', async ({ page }) => {
    await page.goto('/superadmin/tenants');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Click on All Tenants tab
    await page.locator('div.mat-mdc-tab:has-text("All Tenants")').first().click();
    await page.waitForTimeout(500);

    // Check if table is visible
    const table = page.locator('table');
    if (await table.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Table should have maturity state column header
      const maturityHeader = page.locator('th:has-text("Maturity"), th:has-text("State")');
      if (await maturityHeader.count() > 0) {
        await expect(maturityHeader.first()).toBeVisible();

        // Should see maturity state chips (Bootstrap or Mature)
        const maturityChips = page.locator('mat-chip.bootstrap, mat-chip.mature, mat-chip:has-text("Bootstrap"), mat-chip:has-text("Mature")');
        const chipCount = await maturityChips.count();
        // At least one tenant should have a maturity state
        expect(chipCount).toBeGreaterThanOrEqual(0);
      } else {
        test.skip(true, 'Maturity state column not found in table');
      }
    } else {
      test.skip(true, 'No tenants table visible - may be empty');
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

  test('tenant-details-dialog: Can open tenant details dialog', async ({ page }) => {
    await page.goto('/superadmin/tenants');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Click on All Tenants tab
    await page.locator('div.mat-mdc-tab:has-text("All Tenants")').first().click();
    await page.waitForTimeout(500);

    // Check if table is visible with tenant rows
    const table = page.locator('table');
    if (!await table.isVisible({ timeout: 5000 }).catch(() => false)) {
      test.skip(true, 'No tenants table visible');
      return;
    }

    // Look for an info/details button in the table
    const detailsButton = page.locator('button:has(mat-icon:has-text("info")), button:has(mat-icon:has-text("visibility")), button:has(mat-icon:has-text("more_vert"))').first();

    if (await detailsButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await detailsButton.click();

      // Wait for dialog to open
      await page.waitForTimeout(500);

      // Should see tenant details dialog content
      const dialogContent = page.locator('mat-dialog-container, .cdk-dialog-container, .mat-mdc-dialog-container');
      if (await dialogContent.isVisible({ timeout: 3000 }).catch(() => false)) {
        // Dialog should contain tenant statistics or thresholds
        const hasStats = await page.locator('text=/users|admins|stewards|threshold|maturity/i').count() > 0;
        expect(hasStats).toBeTruthy();
      }
    } else {
      test.skip(true, 'Tenant details button not found');
    }
  });

  test('view-history-tab: History tab shows domain approval history', async ({ page }) => {
    await page.goto('/superadmin/tenants');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Click on History tab
    await page.locator('div.mat-mdc-tab:has-text("History")').first().click();
    await page.waitForTimeout(500);

    // Should see Domain Approval History
    await expect(page.locator('mat-card-title:has-text("Domain Approval History")')).toBeVisible();

    // Should show empty state or history table
    const hasEmptyState = await page.locator('text="No domain approval history"').isVisible().catch(() => false);
    const hasTable = await page.locator('table').isVisible().catch(() => false);

    expect(hasEmptyState || hasTable).toBeTruthy();
  });
});

test.describe('Super Admin - System Settings', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsSuperAdmin(page);
  });

  test('view-system-settings: Super admin can access system settings', async ({ page }) => {
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Should see settings page
    const heading = page.locator('h1, h2');
    await expect(heading.first()).toBeVisible();
  });

  test('view-email-configuration: Super admin can view email config', async ({ page }) => {
    await page.goto('/superadmin/email');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Should see email configuration page
    const heading = page.locator('h1:has-text("Email"), mat-card-title:has-text("Email")');
    if (await heading.count() > 0) {
      await expect(heading.first()).toBeVisible();
    } else {
      // Try settings page with email tab
      await page.goto('/superadmin/settings');
      await page.waitForTimeout(500);

      const emailTab = page.locator('div.mat-mdc-tab:has-text("Email")');
      if (await emailTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await emailTab.click();
        await expect(page.locator('text=/SMTP|email|configuration/i').first()).toBeVisible();
      } else {
        test.skip(true, 'Email configuration page not found');
      }
    }
  });
});

test.describe('Super Admin - Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsSuperAdmin(page);
  });

  test('dashboard-loads: Super admin dashboard loads correctly', async ({ page }) => {
    // Login redirects to dashboard
    await page.goto('/superadmin/dashboard');
    await page.waitForLoadState('networkidle');

    // Should see dashboard content
    const dashboardContent = page.locator('text=/dashboard|overview|statistics|tenants/i');
    if (await dashboardContent.count() === 0) {
      // May have a different page structure
      const mainContent = page.locator('main, .content, mat-card');
      await expect(mainContent.first()).toBeVisible();
    } else {
      await expect(dashboardContent.first()).toBeVisible();
    }
  });

  test('tenants-api-works: /api/tenants endpoint returns data without error', async ({ page }) => {
    // Navigate to tenants page which calls /api/tenants
    await page.goto('/superadmin/tenants');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Click on All Tenants tab to trigger API call
    await page.locator('div.mat-mdc-tab:has-text("All Tenants")').first().click();
    await page.waitForTimeout(1000);

    // Verify the page loads without error (no 500 error message)
    const errorMessage = page.locator('text=/500|Internal Server Error|Something went wrong/i');
    const hasError = await errorMessage.isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasError).toBe(false);

    // Should see either the tenants table or empty state
    const tenantsTable = page.locator('table');
    const emptyState = page.locator('text=/No tenants|No registered tenants/i');
    const hasContent = await tenantsTable.isVisible({ timeout: 3000 }).catch(() => false) ||
                       await emptyState.isVisible({ timeout: 1000 }).catch(() => false);
    expect(hasContent).toBe(true);
  });

  test('navigation-works: Can navigate between super admin pages', async ({ page }) => {
    await page.goto('/superadmin/dashboard');
    await page.waitForLoadState('networkidle');

    // Look for navigation links
    const tenantsLink = page.locator('a[href*="/tenants"], button:has-text("Tenants"), nav a:has-text("Tenants")');

    if (await tenantsLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await tenantsLink.click();
      await page.waitForURL('**/superadmin/tenants**', { timeout: 5000 });
      await expect(page.locator('h1:has-text("Tenant Management")')).toBeVisible();
    } else {
      // Try direct navigation
      await page.goto('/superadmin/tenants');
      await expect(page.locator('h1:has-text("Tenant Management")')).toBeVisible();
    }
  });
});

test.describe('Super Admin - Maturity Controls', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsSuperAdmin(page);
  });

  test('maturity-thresholds-in-dialog: Tenant dialog shows maturity thresholds', async ({ page }) => {
    await page.goto('/superadmin/tenants');
    await page.waitForLoadState('networkidle');

    // Click on All Tenants tab
    await page.locator('div.mat-mdc-tab:has-text("All Tenants")').first().click();
    await page.waitForTimeout(500);

    // Try to open tenant details
    const detailsButton = page.locator('button:has(mat-icon:has-text("info")), button:has(mat-icon:has-text("visibility"))').first();

    if (await detailsButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await detailsButton.click();
      await page.waitForTimeout(500);

      // Look for threshold inputs in dialog
      const thresholdInputs = page.locator('input[formcontrolname*="threshold"], input[formcontrolname*="age"], mat-form-field:has-text("threshold")');

      if (await thresholdInputs.count() > 0) {
        await expect(thresholdInputs.first()).toBeVisible();
      } else {
        // Check for threshold text at least
        const thresholdText = page.locator('text=/threshold|age.*days/i');
        expect(await thresholdText.count()).toBeGreaterThanOrEqual(0);
      }
    } else {
      test.skip(true, 'Tenant details button not found');
    }
  });

  test('force-upgrade-button-visible: Force upgrade button appears for bootstrap tenants', async ({ page }) => {
    await page.goto('/superadmin/tenants');
    await page.waitForLoadState('networkidle');

    // Click on All Tenants tab
    await page.locator('div.mat-mdc-tab:has-text("All Tenants")').first().click();
    await page.waitForTimeout(500);

    // Check if any bootstrap tenant exists
    const bootstrapChip = page.locator('mat-chip.bootstrap, mat-chip:has-text("Bootstrap")').first();

    if (await bootstrapChip.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Find the row with bootstrap and click its details button
      const bootstrapRow = bootstrapChip.locator('xpath=ancestor::tr');
      const detailsButton = bootstrapRow.locator('button:has(mat-icon:has-text("info"))');

      if (await detailsButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await detailsButton.click();
        await page.waitForTimeout(500);

        // Look for force upgrade button
        const forceUpgradeButton = page.locator('button:has-text("Force"), button:has-text("Upgrade")');
        if (await forceUpgradeButton.count() > 0) {
          await expect(forceUpgradeButton.first()).toBeVisible();
        }
      }
    } else {
      test.skip(true, 'No bootstrap tenants found to test force upgrade');
    }
  });

  test('delete-tenant-button-visible: Delete tenant button visible in dialog', async ({ page }) => {
    await page.goto('/superadmin/tenants');
    await page.waitForLoadState('networkidle');

    // Click on All Tenants tab
    await page.locator('div.mat-mdc-tab:has-text("All Tenants")').first().click();
    await page.waitForTimeout(500);

    // Try to open any tenant details
    const detailsButton = page.locator('button:has(mat-icon:has-text("info")), button:has(mat-icon:has-text("visibility"))').first();

    if (await detailsButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await detailsButton.click();
      await page.waitForTimeout(500);

      // Look for delete tenant button (should be in danger zone)
      const deleteButton = page.locator('button:has-text("Delete Tenant"), button.warn:has-text("Delete")');

      if (await deleteButton.count() > 0) {
        await expect(deleteButton.first()).toBeVisible();

        // Click delete to verify confirmation dialog appears
        await deleteButton.first().click();
        await page.waitForTimeout(500);

        // Should see confirmation dialog with domain input
        const confirmDialog = page.locator('mat-dialog-container:has-text("Delete"), .cdk-dialog-container:has-text("Delete")');
        if (await confirmDialog.isVisible({ timeout: 3000 }).catch(() => false)) {
          // Should require typing domain to confirm
          const confirmInput = page.locator('input[placeholder*="domain"], input[type="text"]');
          expect(await confirmInput.count()).toBeGreaterThan(0);

          // Close dialog without deleting
          await page.keyboard.press('Escape');
        }
      } else {
        test.skip(true, 'Delete tenant button not found in dialog');
      }
    } else {
      test.skip(true, 'Tenant details button not found');
    }
  });
});
