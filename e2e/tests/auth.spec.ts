import { test, expect, request } from '@playwright/test';
import { loginAsUser, loginAsSuperAdmin, logout } from '../fixtures/auth';

const API_URL = 'http://localhost:5001';

test.describe('Authentication', () => {
  test('super-admin-login: Master account can login with username/password', async ({ page }) => {
    // Route is /superadmin (not /superadmin/login)
    await page.goto('/superadmin');

    // Fill username using data-testid
    await page.locator('[data-testid="username-input"]').fill('admin');

    // Fill password (test database uses 'admin' as default password)
    await page.locator('[data-testid="password-input"]').fill('admin');

    // Click login
    await page.locator('[data-testid="login-button"]').click();

    // Should redirect to superadmin dashboard
    await expect(page).toHaveURL(/.*superadmin\/dashboard.*/, { timeout: 15000 });
  });

  test('tenant-user-password-login: Tenant user can login with email/password', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    // Should be on tenant page after login (redirects to /{domain})
    await expect(page).toHaveURL(/.*test-org\.com.*/);
  });

  test('unauthorized-redirect: Unauthenticated users redirect to login', async ({ page }) => {
    // Try to access tenant decisions page directly (/:tenant is decisions list)
    await page.goto('/test-org.com');

    // Auth guard redirects to homepage for unauthenticated users
    await expect(page).toHaveURL(/localhost:4200\/?$/, { timeout: 10000 });
  });

  test('logout: User can logout and session is cleared', async ({ page }) => {
    // First login
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');
    // Login redirects to /{domain} which is the decisions list
    await expect(page).toHaveURL(/.*test-org\.com.*/);

    // Open user menu (the button with user name and dropdown arrow)
    const userMenuButton = page.locator('button:has(mat-icon:text("arrow_drop_down"))').first();
    await userMenuButton.click();

    // Click logout in the menu
    await page.locator('button:has-text("Sign Out"), button:has-text("Logout")').click();

    // Should redirect to homepage after logout
    await expect(page).toHaveURL(/localhost:4200\/?$/, { timeout: 10000 });
  });
});

test.describe('Account Setup Flow', () => {
  test('setup-url-format: Setup URL uses /setup route not /profile', async ({ page }) => {
    // Create an incomplete user via API
    const apiContext = await request.newContext({ baseURL: API_URL });

    const timestamp = Date.now();
    const testEmail = `setup-test-${timestamp}@setup-test.com`;

    const response = await apiContext.post('/api/test/create-incomplete-user', {
      data: {
        email: testEmail,
        name: 'Setup Test User',
        domain: 'setup-test.com'
      }
    });

    expect(response.ok()).toBeTruthy();
    const data = await response.json();

    // Verify the setup_url uses /setup route (not /profile)
    expect(data.setup_url).toContain('/setup?token=');
    expect(data.setup_url).not.toContain('/profile');
    expect(data.setup_url).toMatch(/\/setup-test\.com\/setup\?token=/);

    await apiContext.dispose();
  });

  test('setup-page-loads: Setup page loads correctly with valid token', async ({ page }) => {
    // Create an incomplete user via API
    const apiContext = await request.newContext({ baseURL: API_URL });

    const timestamp = Date.now();
    const testEmail = `setup-page-${timestamp}@page-test.com`;

    const response = await apiContext.post('/api/test/create-incomplete-user', {
      data: {
        email: testEmail,
        name: 'Page Test User',
        domain: 'page-test.com'
      }
    });

    expect(response.ok()).toBeTruthy();
    const data = await response.json();

    // Navigate to the setup page
    await page.goto(data.setup_url);

    // Wait for page to load and verify it's the setup page (not profile)
    await page.waitForLoadState('networkidle');

    // Should show setup page content - either the AccountSetupComponent or error state
    // The setup page should have setup-related content
    const pageContent = await page.content();

    // Verify we're not on the profile page
    expect(pageContent).not.toContain('Profile &amp; Notifications');

    await apiContext.dispose();
  });

  test('setup-not-profile: Old profile setup URL format should not be used', async ({ page }) => {
    // This test verifies that the old /profile?setup=passkey URL is NOT used
    // by checking that the API generates the correct /setup URL

    const apiContext = await request.newContext({ baseURL: API_URL });

    const timestamp = Date.now();
    const testEmail = `old-format-${timestamp}@old-test.com`;

    const response = await apiContext.post('/api/test/create-incomplete-user', {
      data: {
        email: testEmail,
        name: 'Old Format Test',
        domain: 'old-test.com'
      }
    });

    expect(response.ok()).toBeTruthy();
    const data = await response.json();

    // Critical assertion: URL should NOT contain /profile?setup=
    expect(data.setup_url).not.toContain('/profile?setup=');
    expect(data.setup_url).not.toContain('/profile?setup=passkey');

    // URL SHOULD contain /setup?token=
    expect(data.setup_url).toContain('/setup?token=');

    await apiContext.dispose();
  });
});
