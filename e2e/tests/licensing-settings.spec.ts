import { test, expect } from '@playwright/test';
import { loginAsSuperAdmin } from '../fixtures/auth';

test.describe('Super Admin - Licensing Settings', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsSuperAdmin(page);
  });

  test('view-licensing-settings: Super admin can see licensing settings page', async ({ page }) => {
    // Navigate to settings page
    await page.goto('/superadmin/settings');

    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Should see the System Settings heading
    await page.waitForSelector('h1', { timeout: 10000 });
    await expect(page.locator('h1')).toContainText('System Settings');

    // Should see the Licensing & Limits card
    await expect(page.locator('mat-card-title:has-text("Licensing & Limits")')).toBeVisible();

    // Should see the Max Users Per Tenant field
    await expect(page.locator('mat-label:has-text("Max Users Per Tenant")')).toBeVisible();
  });

  test('view-default-user-limit: Default user limit is 5', async ({ page }) => {
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Find the max users input field
    const maxUsersInput = page.locator('input[formcontrolname="max_users_per_tenant"]');
    await expect(maxUsersInput).toBeVisible();

    // Check that hint shows default of 5
    await expect(page.locator('mat-hint:has-text("default: 5")')).toBeVisible();
  });

  test('update-user-limit: Can change max users per tenant', async ({ page }) => {
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Find the max users input field
    const maxUsersInput = page.locator('input[formcontrolname="max_users_per_tenant"]');
    await expect(maxUsersInput).toBeVisible();

    // Clear and enter new value
    await maxUsersInput.click();
    await maxUsersInput.fill('10');

    // Click save button
    const saveButton = page.locator('button:has-text("Save Licensing Settings")');
    await saveButton.click();

    // Wait for snackbar confirmation
    await page.waitForSelector('.mat-mdc-snack-bar-container', { timeout: 5000 });
    await expect(page.locator('.mat-mdc-snack-bar-container')).toContainText('Licensing settings saved successfully');
  });

  test('set-unlimited-users: Can set unlimited users (0)', async ({ page }) => {
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Find the max users input field
    const maxUsersInput = page.locator('input[formcontrolname="max_users_per_tenant"]');
    await expect(maxUsersInput).toBeVisible();

    // Set to 0 (unlimited)
    await maxUsersInput.click();
    await maxUsersInput.fill('0');

    // Should show "Unlimited users allowed" message
    await expect(page.locator('.limit-info .unlimited')).toContainText('Unlimited users allowed');

    // Click save button
    const saveButton = page.locator('button:has-text("Save Licensing Settings")');
    await saveButton.click();

    // Wait for snackbar confirmation
    await page.waitForSelector('.mat-mdc-snack-bar-container', { timeout: 5000 });
    await expect(page.locator('.mat-mdc-snack-bar-container')).toContainText('Licensing settings saved successfully');
  });

  test('reset-to-defaults: Can reset licensing settings to defaults', async ({ page }) => {
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // First change the value
    const maxUsersInput = page.locator('input[formcontrolname="max_users_per_tenant"]');
    await maxUsersInput.click();
    await maxUsersInput.fill('100');

    // Click reset button
    const resetButton = page.locator('button:has-text("Reset to Defaults")').first();
    await resetButton.click();

    // Value should be back to 5 (default)
    await expect(maxUsersInput).toHaveValue('5');
  });

  test('limit-info-display: Shows correct limit info based on value', async ({ page }) => {
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const maxUsersInput = page.locator('input[formcontrolname="max_users_per_tenant"]');

    // Set to 25
    await maxUsersInput.click();
    await maxUsersInput.fill('25');

    // Should show limited message with correct count
    await expect(page.locator('.limit-info .limited')).toContainText('Each tenant can have up to 25 users');

    // Set to 0
    await maxUsersInput.fill('0');

    // Should show unlimited message
    await expect(page.locator('.limit-info .unlimited')).toContainText('Unlimited users allowed');
  });

  test('validation-max-value: Cannot exceed maximum value (10000)', async ({ page }) => {
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const maxUsersInput = page.locator('input[formcontrolname="max_users_per_tenant"]');

    // Try to set invalid value
    await maxUsersInput.click();
    await maxUsersInput.fill('20000');

    // Save button should be disabled due to validation
    const saveButton = page.locator('button:has-text("Save Licensing Settings")');
    await expect(saveButton).toBeDisabled();
  });

  test('validation-negative-value: Cannot set negative value', async ({ page }) => {
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const maxUsersInput = page.locator('input[formcontrolname="max_users_per_tenant"]');

    // Try to set negative value
    await maxUsersInput.click();
    await maxUsersInput.fill('-5');

    // Save button should be disabled due to validation
    const saveButton = page.locator('button:has-text("Save Licensing Settings")');
    await expect(saveButton).toBeDisabled();
  });

  test('session-settings-still-work: Session timeout settings still visible', async ({ page }) => {
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Should see Session Timeouts card
    await expect(page.locator('mat-card-title:has-text("Session Timeouts")')).toBeVisible();

    // Should see both session timeout fields
    await expect(page.locator('h3:has-text("Super Admin Session")')).toBeVisible();
    await expect(page.locator('h3:has-text("Regular User Session")')).toBeVisible();
  });
});

test.describe('Licensing Settings - API Integration', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsSuperAdmin(page);
  });

  test('api-get-licensing-settings: GET /api/admin/settings/licensing returns correct data', async ({ page, request }) => {
    // First login to get session
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');

    // Get cookies from browser context
    const cookies = await page.context().cookies();
    const sessionCookie = cookies.find(c => c.name === 'session');

    if (sessionCookie) {
      // Make API request with session cookie
      const response = await request.get('/api/admin/settings/licensing', {
        headers: {
          'Cookie': `session=${sessionCookie.value}`
        }
      });

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('max_users_per_tenant');
      expect(data).toHaveProperty('defaults');
      expect(data.defaults).toHaveProperty('max_users_per_tenant');
      expect(data.defaults.max_users_per_tenant).toBe(5);
    }
  });

  test('api-save-licensing-settings: POST /api/admin/settings/licensing updates settings', async ({ page, request }) => {
    // First login to get session
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');

    // Get cookies from browser context
    const cookies = await page.context().cookies();
    const sessionCookie = cookies.find(c => c.name === 'session');

    if (sessionCookie) {
      // Make API request to update settings
      const response = await request.post('/api/admin/settings/licensing', {
        headers: {
          'Cookie': `session=${sessionCookie.value}`,
          'Content-Type': 'application/json'
        },
        data: {
          max_users_per_tenant: 15
        }
      });

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data.max_users_per_tenant).toBe(15);
      expect(data.message).toContain('success');
    }
  });
});
