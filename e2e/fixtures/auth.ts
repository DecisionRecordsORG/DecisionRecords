import { Page, APIRequestContext } from '@playwright/test';

const API_URL = 'http://localhost:5001';

/**
 * Login as a tenant user with email/password
 */
export async function loginAsUser(page: Page, email: string, password: string): Promise<void> {
  const domain = email.split('@')[1];

  // Navigate to tenant login page
  await page.goto(`/${domain}/login`);

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
  await page.waitForURL(`**/${domain}/**`, { timeout: 15000 });
}

/**
 * Login as super admin (master account)
 */
export async function loginAsSuperAdmin(page: Page, username: string = 'admin', password: string = 'admin'): Promise<void> {
  // Route is /superadmin (not /superadmin/login)
  await page.goto('/superadmin');

  // Fill username using data-testid
  const usernameInput = page.locator('[data-testid="username-input"]');
  await usernameInput.fill(username);

  // Fill password
  const passwordInput = page.locator('[data-testid="password-input"]');
  await passwordInput.fill(password);

  // Click login
  const loginButton = page.locator('[data-testid="login-button"]');
  await loginButton.click();

  // Wait for redirect to superadmin dashboard
  await page.waitForURL('**/superadmin/dashboard**', { timeout: 15000 });
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
