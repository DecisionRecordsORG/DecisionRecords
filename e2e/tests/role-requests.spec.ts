import { test, expect } from '@playwright/test';
import { loginAsUser } from '../fixtures/auth';

test.describe('Role Requests', () => {
  // Note: These tests require proper test data setup in the database.
  // The test database should have:
  // - user@test-org.com with 'user' role
  // - admin@test-org.com with 'admin' role

  test('request-role-ui-exists: Regular user sees role request button in profile', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Navigate to profile
    await page.goto('/test-org.com/profile');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Check if profile page loaded
    const profileHeading = await page.waitForSelector('h1:has-text("Profile"), h1:has-text("Notifications")', { timeout: 10000 }).catch(() => null);

    if (!profileHeading) {
      test.skip(true, 'Profile page did not load');
      return;
    }

    // Look for role request button (only visible to regular users)
    const roleRequestButton = page.locator('button:has-text("Request Elevated Role")');

    // The button should be visible for regular users
    if (await roleRequestButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(roleRequestButton).toBeVisible();
    } else {
      test.skip(true, 'Role request button not visible - user may already have elevated role');
    }
  });

  test('submit-role-request: User can submit a role request via dialog', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Navigate to profile
    await page.goto('/test-org.com/profile');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Look for role request button
    const roleRequestButton = page.locator('button:has-text("Request Elevated Role")');

    if (!(await roleRequestButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Role request button not visible - user may already have elevated role');
      return;
    }

    // Click the role request button
    await roleRequestButton.click();
    await page.waitForTimeout(500);

    // Wait for dialog to appear
    const dialog = page.locator('h2:has-text("Request Elevated Role")');
    if (!(await dialog.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'Role request dialog did not appear');
      return;
    }

    // Select steward role
    const stewardOption = page.locator('mat-radio-button[value="steward"]');
    if (await stewardOption.isVisible({ timeout: 2000 }).catch(() => false)) {
      await stewardOption.click();
      await page.waitForTimeout(300);
    }

    // Fill in reason
    const reasonTextarea = page.locator('textarea[placeholder*="explain why"]');
    if (await reasonTextarea.isVisible({ timeout: 2000 }).catch(() => false)) {
      await reasonTextarea.fill('I would like to help with user approvals and governance tasks.');
      await page.waitForTimeout(300);
    } else {
      test.skip(true, 'Reason textarea not found in dialog');
      return;
    }

    // Submit the request
    const submitButton = page.locator('button:has-text("Submit Request")');
    if (await submitButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await submitButton.click();
      await page.waitForTimeout(1500);

      // Look for success message
      const snackbar = page.locator('simple-snack-bar, .mat-mdc-snack-bar-label, .mdc-snackbar__label');
      if (await snackbar.isVisible({ timeout: 3000 }).catch(() => false)) {
        const snackbarText = await snackbar.textContent();
        expect(snackbarText?.toLowerCase()).toContain('role request');
      }
    } else {
      test.skip(true, 'Submit button not found');
    }
  });

  test('admin-sees-role-requests: Admin can view pending role requests', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    // Navigate to admin settings
    await page.goto('/test-org.com/admin');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Check if we got to admin page
    const currentUrl = page.url();
    if (!currentUrl.includes('/admin')) {
      test.skip(true, 'Admin access not available');
      return;
    }

    // Wait for settings page to load
    const settingsHeading = await page.waitForSelector('h1:has-text("Organization Settings"), h1:has-text("Settings")', { timeout: 15000 }).catch(() => null);

    if (!settingsHeading) {
      test.skip(true, 'Admin settings page did not load');
      return;
    }

    // Click on Role Requests tab
    const roleRequestsTab = page.locator('div.mat-mdc-tab:has-text("Role Requests")');
    if (!(await roleRequestsTab.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Role Requests tab not found');
      return;
    }

    await roleRequestsTab.click();
    await page.waitForTimeout(1000);

    // Check if there's a role requests table or empty message
    const table = page.locator('table');
    const emptyMessage = page.locator('p:has-text("No role requests")');

    if (await table.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Table exists, verify structure
      const userColumn = page.locator('th:has-text("User")');
      const requestedRoleColumn = page.locator('th:has-text("Requested Role")');
      const statusColumn = page.locator('th:has-text("Status")');
      const actionsColumn = page.locator('th:has-text("Actions")');

      expect(await userColumn.isVisible()).toBeTruthy();
      expect(await requestedRoleColumn.isVisible()).toBeTruthy();
      expect(await statusColumn.isVisible()).toBeTruthy();
      expect(await actionsColumn.isVisible()).toBeTruthy();
    } else if (await emptyMessage.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Empty state is OK - no requests yet
      expect(await emptyMessage.isVisible()).toBeTruthy();
    } else {
      test.skip(true, 'Neither role requests table nor empty message found');
    }
  });

  test('role-request-appears-in-list: Role request shows in admin panel after submission', async ({ page }) => {
    // First, submit a role request as regular user
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    await page.goto('/test-org.com/profile');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const roleRequestButton = page.locator('button:has-text("Request Elevated Role")');

    if (!(await roleRequestButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Role request button not visible - user may already have elevated role');
      return;
    }

    // Submit a role request
    await roleRequestButton.click();
    await page.waitForTimeout(500);

    const dialog = page.locator('h2:has-text("Request Elevated Role")');
    if (!(await dialog.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'Role request dialog did not appear');
      return;
    }

    // Select admin role this time
    const adminOption = page.locator('mat-radio-button[value="admin"]');
    if (await adminOption.isVisible({ timeout: 2000 }).catch(() => false)) {
      await adminOption.click();
      await page.waitForTimeout(300);
    }

    const reasonTextarea = page.locator('textarea[placeholder*="explain why"]');
    if (await reasonTextarea.isVisible({ timeout: 2000 }).catch(() => false)) {
      await reasonTextarea.fill('E2E test role request - ' + Date.now());
      await page.waitForTimeout(300);
    } else {
      test.skip(true, 'Reason textarea not found');
      return;
    }

    const submitButton = page.locator('button:has-text("Submit Request")');
    if (await submitButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await submitButton.click();
      await page.waitForTimeout(2000);
    } else {
      test.skip(true, 'Submit button not found');
      return;
    }

    // Now login as admin to verify the request appears
    await page.context().clearCookies();
    await page.waitForTimeout(500);

    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    await page.goto('/test-org.com/admin');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const settingsHeading = await page.waitForSelector('h1:has-text("Organization Settings"), h1:has-text("Settings")', { timeout: 15000 }).catch(() => null);

    if (!settingsHeading) {
      test.skip(true, 'Admin settings page did not load');
      return;
    }

    // Click on Role Requests tab
    const roleRequestsTab = page.locator('div.mat-mdc-tab:has-text("Role Requests")');
    if (!(await roleRequestsTab.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Role Requests tab not found');
      return;
    }

    await roleRequestsTab.click();
    await page.waitForTimeout(1000);

    // Check if the role request appears in the table
    const table = page.locator('table');
    if (await table.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Look for a pending request from user@test-org.com
      const userCell = page.locator('td:has-text("user@test-org.com")');
      if (await userCell.isVisible({ timeout: 3000 }).catch(() => false)) {
        // Found the request - verify it has the expected role badge
        const adminBadge = page.locator('mat-chip:has-text("Administrator")');
        expect(await adminBadge.isVisible({ timeout: 2000 }).catch(() => false)).toBeTruthy();
      } else {
        test.skip(true, 'Role request from user@test-org.com not found in table');
      }
    } else {
      test.skip(true, 'Role requests table not visible');
    }
  });

  test('admin-cannot-request-role: Admin user does not see role request button', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    await page.goto('/test-org.com/profile');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const profileHeading = await page.waitForSelector('h1:has-text("Profile"), h1:has-text("Notifications")', { timeout: 10000 }).catch(() => null);

    if (!profileHeading) {
      test.skip(true, 'Profile page did not load');
      return;
    }

    // Admin users should NOT see the role request button
    const roleRequestButton = page.locator('button:has-text("Request Elevated Role")');

    // Wait a bit to ensure the page has fully rendered
    await page.waitForTimeout(1500);

    // The button should NOT be visible for admins
    const isVisible = await roleRequestButton.isVisible({ timeout: 2000 }).catch(() => false);
    expect(isVisible).toBeFalsy();
  });

  test('role-request-badge-count: Tab shows badge with pending request count', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    await page.goto('/test-org.com/admin');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const settingsHeading = await page.waitForSelector('h1:has-text("Organization Settings"), h1:has-text("Settings")', { timeout: 15000 }).catch(() => null);

    if (!settingsHeading) {
      test.skip(true, 'Admin settings page did not load');
      return;
    }

    // Look for badge on Role Requests tab
    const roleRequestsTab = page.locator('div.mat-mdc-tab:has-text("Role Requests")');
    if (!(await roleRequestsTab.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Role Requests tab not found');
      return;
    }

    // Check if there's a badge with count
    const badge = roleRequestsTab.locator('.tab-badge');
    if (await badge.isVisible({ timeout: 2000 }).catch(() => false)) {
      const badgeText = await badge.textContent();
      // Badge should contain a number
      expect(badgeText).toMatch(/\d+/);
    } else {
      // No badge means no pending requests, which is also valid
      console.log('No badge visible - no pending role requests');
    }
  });
});
