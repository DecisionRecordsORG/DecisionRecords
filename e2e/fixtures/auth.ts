import { Page, APIRequestContext } from '@playwright/test';

const API_URL = 'http://localhost:5001';

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
  await emailInput.fill(email);

  // Click continue/sign in to proceed
  const continueButton = page.locator('[data-testid="continue-button"]');
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

  // Fill username using data-testid
  const usernameInput = page.locator('[data-testid="username-input"]');
  await usernameInput.fill(username);

  // Fill password
  const passwordInput = page.locator('[data-testid="password-input"]');
  await passwordInput.fill(password);

  // Click login and wait for navigation to complete
  const loginButton = page.locator('[data-testid="login-button"]');

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
