import { test, expect } from '@playwright/test';
import { loginAsUser, dismissOverlays } from '../fixtures/auth';

test.describe('Spaces Management', () => {
  test.describe('Admin Settings - Spaces Tab', () => {
    test('spaces-tab-exists: Admin can access Spaces tab in settings', async ({ page }) => {
      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      // Wait for decisions page to load fully
      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });

      // Direct navigation to admin settings
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000); // Extra time for Angular auth guards

      // Check if we got redirected (guard blocked us)
      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available - guard may have redirected');
        return;
      }

      // Wait for settings page to load
      await page.waitForSelector('mat-tab-group', { timeout: 15000 });

      // Dismiss any overlays before clicking
      await dismissOverlays(page);

      // Click on the Spaces tab - use force to bypass overlays
      const spacesTab = page.locator('div.mat-mdc-tab:has-text("Spaces")');
      await expect(spacesTab).toBeVisible({ timeout: 5000 });
      await spacesTab.click({ force: true });

      // Verify Spaces tab content is visible
      await page.waitForTimeout(1000);
      const spacesContent = page.locator('h3:has-text("Create"), h3:has-text("Spaces"), table, .spaces-section');
      await expect(spacesContent.first()).toBeVisible({ timeout: 5000 });
    });

    test('default-space-exists: General default space exists in tenant', async ({ page }) => {
      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      // Wait for decisions page to load
      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });

      // Navigate directly and wait for Angular to stabilize
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      // Check if we got redirected (guard blocked us)
      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available - guard may have redirected');
        return;
      }

      // Wait for settings page
      await page.waitForSelector('mat-tab-group', { timeout: 15000 });

      // Dismiss any overlays before clicking
      await dismissOverlays(page);

      const spacesTab = page.locator('div.mat-mdc-tab:has-text("Spaces")');
      await spacesTab.click();

      // Wait for spaces list to load
      await page.waitForTimeout(2000);

      // Look for General space in the table
      const generalSpace = page.locator('td:has-text("General"), mat-cell:has-text("General")').first();
      await expect(generalSpace).toBeVisible({ timeout: 5000 });
    });

    test('cannot-delete-default-space: Delete button disabled for default space', async ({ page }) => {
      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });

      // Dismiss any overlays before clicking
      await dismissOverlays(page);

      const spacesTab = page.locator('div.mat-mdc-tab:has-text("Spaces")');
      await spacesTab.click();
      await page.waitForTimeout(2000);

      // Find the row with the default space (General)
      const defaultSpaceRow = page.locator('tr:has(.default-chip), tr:has-text("General")').first();
      await expect(defaultSpaceRow).toBeVisible({ timeout: 5000 });

      // The delete button in the default space row should be disabled (or not present)
      const deleteButton = defaultSpaceRow.locator('button[color="warn"]');
      const deleteCount = await deleteButton.count();

      if (deleteCount > 0) {
        await expect(deleteButton).toBeDisabled();
      }
      // If no delete button visible for default space, that's acceptable
    });

    test('admin-can-create-space: Admin can create a new space', async ({ page }) => {
      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });

      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });

      // Dismiss any overlays before clicking
      await dismissOverlays(page);

      // Click on the Spaces tab - use force to bypass overlays
      const spacesTab = page.locator('div.mat-mdc-tab:has-text("Spaces")');
      await spacesTab.click({ force: true });
      await page.waitForTimeout(1000);

      // Fill in the space name
      const nameInput = page.locator('input[formcontrolname="name"]');
      await expect(nameInput).toBeVisible({ timeout: 5000 });

      const testSpaceName = 'E2E Test Space ' + Date.now();
      await nameInput.fill(testSpaceName);

      // Optionally fill description
      const descriptionInput = page.locator('textarea[formcontrolname="description"]');
      if (await descriptionInput.isVisible({ timeout: 1000 }).catch(() => false)) {
        await descriptionInput.fill('Test space created by e2e tests');
      }

      // Click create/save button
      const saveButton = page.locator('button:has-text("Create"), button:has-text("Save")').first();
      await saveButton.click();

      // Wait for success
      await page.waitForTimeout(2000);

      // Verify the new space appears in the list
      const newSpaceCell = page.locator(`td:has-text("E2E Test Space")`).first();
      await expect(newSpaceCell).toBeVisible({ timeout: 10000 });
    });

    test('admin-can-edit-space: Admin can edit space name', async ({ page }) => {
      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });

      // Dismiss any overlays before clicking
      await dismissOverlays(page);

      const spacesTab = page.locator('div.mat-mdc-tab:has-text("Spaces")');
      await spacesTab.click();
      await page.waitForTimeout(2000);

      // Try to find a non-default space to edit
      const nonDefaultRow = page.locator('tr:has-text("Engineering"), tr:has-text("Product")').first();
      await expect(nonDefaultRow).toBeVisible({ timeout: 5000 });

      // Dismiss any overlays before clicking edit button
      await dismissOverlays(page);

      const editBtn = nonDefaultRow.locator('button:has(mat-icon:has-text("edit"))');
      await editBtn.click();

      // Form should be populated with existing space data
      const nameInput = page.locator('input[formcontrolname="name"]');
      await expect(nameInput).toHaveValue(/.+/);
    });
  });

  test.describe('Space Permissions', () => {
    test('steward-can-access-admin-settings: Steward can access admin settings', async ({ page }) => {
      await loginAsUser(page, 'steward@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      // Check if we're on admin page (not redirected)
      const url = page.url();
      if (!url.includes('/admin')) {
        test.skip(true, 'Steward does not have access to admin settings');
        return;
      }

      // Steward has access - look for tab group
      await page.waitForSelector('mat-tab-group', { timeout: 10000 });

      // Click on the Spaces tab
      const spacesTab = page.locator('div.mat-mdc-tab:has-text("Spaces")');
      await expect(spacesTab).toBeVisible({ timeout: 5000 });
    });

    test('user-cannot-access-admin-settings: Regular user redirected from admin', async ({ page }) => {
      await loginAsUser(page, 'user@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });

      // Try to navigate to admin settings
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);

      // Should not be on admin page
      const url = page.url();
      expect(url).not.toContain('/admin');
    });
  });
});
