import { Page, APIRequestContext, Locator, expect } from '@playwright/test';

// E2E tests use port 5002 to avoid conflicts with development backend on 5001
const API_URL = 'http://localhost:5002';

/**
 * Fill a form and wait until its submit button is enabled.
 *
 * The Angular dev server sends server-rendered HTML, so the form's inputs are
 * in the page before the app has started in the browser. Text typed into them
 * that early is thrown away when the app starts and binds the (empty) form,
 * which left the submit button disabled and the login helpers waiting until
 * they timed out. The submit button is only enabled by the running app once
 * the form is valid, so filling again until it is enabled is a reliable sign
 * that the values were really taken.
 */
export async function fillFormUntilReady(
  fields: Array<[Locator, string]>,
  submitButton: Locator,
  timeout: number = 20000
): Promise<void> {
  await expect(async () => {
    for (const [field, value] of fields) {
      await field.fill(value);
    }
    await expect(submitButton).toBeEnabled({ timeout: 1000 });
  }).toPass({ timeout });
}

/**
 * Login as a tenant user with email/password
 */
export async function loginAsUser(page: Page, email: string, password: string): Promise<void> {
  const domain = email.split('@')[1];

  // Clear cookies to ensure clean session
  await page.context().clearCookies();

  // Add delay between login attempts to avoid rate limiting
  await page.waitForTimeout(500);

  // Navigate to tenant login page
  await page.goto(`/${domain}/login`, { waitUntil: 'domcontentloaded' });

  // Wait for email input and fill
  await page.waitForSelector('[data-testid="email-input"]', { timeout: 10000 });
  const emailInput = page.locator('[data-testid="email-input"]');
  const continueButton = page.locator('[data-testid="continue-button"]');
  await fillFormUntilReady([[emailInput, email]], continueButton);

  // Click continue/sign in to proceed
  await continueButton.click();

  // Wait for login view (tenant-login shows password form directly if user has password)
  await page.waitForSelector('[data-testid="login-view"], [data-testid="password-form"]', { timeout: 10000 });

  // Fill password
  const passwordInput = page.locator('[data-testid="password-input"]');
  await passwordInput.fill(password);

  // Click login button
  const loginButton = page.locator('[data-testid="login-button"]');
  await loginButton.click();

  // Wait for redirect to tenant page (decisions or dashboard)
  // Use retry logic to handle rate limiting errors
  try {
    await page.waitForURL(`**/${domain}/**`, { timeout: 20000 });
  } catch (error) {
    // Check if we got a rate limit error
    const errorMessage = await page.locator('.error-message, mat-error, .mat-error').textContent().catch(() => '');
    if (errorMessage?.toLowerCase().includes('rate limit') || errorMessage?.toLowerCase().includes('too many')) {
      // Wait longer and retry once
      await page.waitForTimeout(3000);
      await loginButton.click();
      await page.waitForURL(`**/${domain}/**`, { timeout: 20000 });
    } else {
      throw error;
    }
  }

  // Ensure page is fully loaded before proceeding
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(500);
}

/**
 * Login as super admin (master account)
 */
export async function loginAsSuperAdmin(page: Page, username: string = 'admin', password: string = 'changeme'): Promise<void> {
  // Clear cookies to ensure clean session
  await page.context().clearCookies();

  // Add delay between login attempts to avoid rate limiting
  await page.waitForTimeout(500);

  // Route is /superadmin (not /superadmin/login)
  await page.goto('/superadmin', { waitUntil: 'domcontentloaded' });

  // Wait for login form to be ready
  await page.waitForSelector('[data-testid="username-input"]', { timeout: 10000 });

  // Fill username and password, again if the app was not running yet the first time
  const usernameInput = page.locator('[data-testid="username-input"]');
  const passwordInput = page.locator('[data-testid="password-input"]');
  const loginButton = page.locator('[data-testid="login-button"]');
  await fillFormUntilReady([[usernameInput, username], [passwordInput, password]], loginButton);

  // Click login and wait for navigation to complete

  // Wait for both the navigation and the network to be idle
  // This ensures the login request completes and redirect happens
  await Promise.all([
    page.waitForURL('**/superadmin/dashboard**', { timeout: 30000 }),
    loginButton.click()
  ]);

  // Ensure page is fully loaded before proceeding
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(500);
}

/**
 * Logout current user
 */
export async function logout(page: Page): Promise<void> {
  // Click user menu or logout button
  const logoutButton = page.locator('button:has-text("Logout"), button:has-text("Sign Out"), [data-testid="logout-button"]').first();
  if (await logoutButton.isVisible()) {
    await logoutButton.click();
  } else {
    // Try opening user menu first
    const userMenu = page.locator('[data-testid="user-menu"], .user-menu, button:has(mat-icon:has-text("account_circle"))').first();
    await userMenu.click();
    await page.locator('button:has-text("Logout"), button:has-text("Sign Out")').click();
  }

  // Wait for redirect to login
  await page.waitForURL('**/{login,/}**', { timeout: 10000 });
}

/**
 * Create a test user via API
 */
export async function createTestUser(
  request: APIRequestContext,
  email: string,
  password: string,
  role: 'user' | 'admin' | 'steward' | 'provisional_admin',
  name?: string
): Promise<any> {
  const domain = email.split('@')[1];
  const response = await request.post(`${API_URL}/api/test/create-user`, {
    data: {
      email,
      password,
      name: name || email.split('@')[0],
      role,
      domain,
    },
  });
  return response.json();
}

/**
 * Reset test database
 */
export async function resetDatabase(request: APIRequestContext): Promise<void> {
  await request.post(`${API_URL}/api/test/reset-database`);
}

/**
 * Set tenant maturity state
 */
export async function setTenantMaturity(
  request: APIRequestContext,
  domain: string,
  state: 'bootstrap' | 'mature'
): Promise<void> {
  await request.post(`${API_URL}/api/test/set-tenant-maturity`, {
    data: { domain, state },
  });
}

/**
 * Dismiss any visible CDK overlays (snackbars, dialogs, etc.)
 * Call this before clicks that might be blocked by overlay backdrops
 */
export async function dismissOverlays(page: Page): Promise<void> {
  // Try pressing Escape to close any overlays
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);

  // Check if any overlays are still visible and click backdrop to dismiss
  const backdrop = page.locator('.cdk-overlay-backdrop');
  if (await backdrop.isVisible({ timeout: 500 }).catch(() => false)) {
    await backdrop.click({ force: true });
    await page.waitForTimeout(300);
  }
}
