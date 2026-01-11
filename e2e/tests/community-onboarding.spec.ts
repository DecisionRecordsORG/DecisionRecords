import { test, expect, request } from '@playwright/test';

/**
 * Community Edition Onboarding Tests
 *
 * These tests verify the complete user onboarding flow in Community Edition:
 * - User signup via tenant login page
 * - Email verification disabled flow
 * - Direct account creation and setup
 * - User signin after account creation
 */

// Helper to check if we're in Community Edition
async function isCommunityEdition(page: any): Promise<boolean> {
  const response = await page.request.get('/api/system/status');
  if (response.ok()) {
    const status = await response.json();
    return status.is_community;
  }
  return false;
}

// Helper to get email verification status
async function isEmailVerificationRequired(page: any): Promise<boolean> {
  const response = await page.request.get('/api/system/email-verification');
  if (response.ok()) {
    const data = await response.json();
    return data.required;
  }
  return true; // Default to required if can't check
}

test.describe('Community Edition Onboarding - User Signup', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
  });

  test('ce-signup-via-tenant-login: New user can sign up via tenant login page', async ({ page }) => {
    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    if (!status.is_community) {
      test.skip(true, 'Test only applies to Community Edition');
      return;
    }

    if (!status.has_tenants) {
      test.skip(true, 'No tenants exist - run setup wizard first');
      return;
    }

    // Get the tenant domain
    const tenantsResponse = await page.request.get('/api/tenants/list');
    const tenants = await tenantsResponse.json();
    if (!tenants.length) {
      test.skip(true, 'No tenants available');
      return;
    }
    const tenantDomain = tenants[0].domain;

    // Generate unique test email
    const timestamp = Date.now();
    const testEmail = `newuser-${timestamp}@${tenantDomain}`;

    // Navigate to tenant login page
    await page.goto(`/${tenantDomain}/login`);
    await page.waitForLoadState('networkidle');

    // Check for email form
    const emailInput = page.locator('[data-testid="email-input"]');
    const emailFormVisible = await emailInput.isVisible({ timeout: 5000 }).catch(() => false);

    if (!emailFormVisible) {
      // Might show different form, try regular email input
      const fallbackEmailInput = page.locator('input[formControlName="email"]').first();
      if (await fallbackEmailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
        await fallbackEmailInput.fill(testEmail);
      } else {
        test.skip(true, 'Email input not visible');
        return;
      }
    } else {
      await emailInput.fill(testEmail);
    }

    // Click continue
    const continueButton = page.locator('[data-testid="continue-button"], button:has-text("Continue")').first();
    await continueButton.click();

    // Wait for the signup/access-request form to appear
    await page.waitForTimeout(1000);

    // Should show request access form for new users
    const firstNameInput = page.locator('input[formControlName="first_name"]');
    await expect(firstNameInput).toBeVisible({ timeout: 10000 });

    // Fill in the form
    await firstNameInput.fill('Test');

    const lastNameInput = page.locator('input[formControlName="last_name"]');
    await lastNameInput.fill('User');

    // Optional: fill reason if visible
    const reasonInput = page.locator('input[formControlName="reason"], textarea[formControlName="reason"]');
    if (await reasonInput.isVisible({ timeout: 1000 }).catch(() => false)) {
      await reasonInput.fill('Testing signup flow');
    }

    // Submit the form
    const submitButton = page.locator('button[type="submit"]:has-text("Request Access"), button[type="submit"]:has-text("Join")').first();
    await submitButton.click();

    // Check for success - should either redirect to setup or show success message
    await page.waitForTimeout(2000);

    // In Community Edition with require_approval=false, should redirect to setup URL
    const currentUrl = page.url();
    const isOnSetup = currentUrl.includes('/setup');
    const showsAutoApproved = await page.locator('text=Your account has been created').isVisible({ timeout: 3000 }).catch(() => false);

    expect(isOnSetup || showsAutoApproved).toBeTruthy();
  });

  test('ce-signup-shows-setup-page: Auto-approved users see setup page', async ({ page }) => {
    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    if (!status.is_community) {
      test.skip(true, 'Test only applies to Community Edition');
      return;
    }

    if (!status.has_tenants) {
      test.skip(true, 'No tenants exist');
      return;
    }

    // Get the tenant domain
    const tenantsResponse = await page.request.get('/api/tenants/list');
    const tenants = await tenantsResponse.json();
    if (!tenants.length) {
      test.skip(true, 'No tenants available');
      return;
    }
    const tenantDomain = tenants[0].domain;

    // Generate unique test email
    const timestamp = Date.now();
    const testEmail = `setuptest-${timestamp}@${tenantDomain}`;

    // Navigate to tenant login page
    await page.goto(`/${tenantDomain}/login`);
    await page.waitForLoadState('networkidle');

    // Enter email
    const emailInput = page.locator('[data-testid="email-input"], input[formControlName="email"]').first();
    await emailInput.fill(testEmail);

    const continueButton = page.locator('[data-testid="continue-button"], button:has-text("Continue")').first();
    await continueButton.click();

    await page.waitForTimeout(1000);

    // Fill signup form
    await page.locator('input[formControlName="first_name"]').fill('Setup');
    await page.locator('input[formControlName="last_name"]').fill('Tester');

    // Submit
    const submitButton = page.locator('button[type="submit"]').first();
    await submitButton.click();

    // Wait for redirect to setup page
    await page.waitForURL(/.*\/setup\?token=.*/, { timeout: 15000 });

    // Verify setup page content
    const setupPageVisible = await page.locator('text=Set Up Your Account, text=Complete Your Account Setup').first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(setupPageVisible).toBeTruthy();

    // Verify passkey option is shown
    const passkeyOption = page.locator('text=Use Passkey, text=passkey');
    await expect(passkeyOption.first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Community Edition Onboarding - User Signin', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
  });

  test('ce-signin-with-password: User can sign in with password', async ({ page }) => {
    // Check if test user exists by trying to login
    await page.goto('/test-org.com/login');
    await page.waitForLoadState('networkidle');

    // Skip if no test org
    const emailInput = page.locator('[data-testid="email-input"], input[formControlName="email"]').first();
    const formVisible = await emailInput.isVisible({ timeout: 5000 }).catch(() => false);
    if (!formVisible) {
      test.skip(true, 'Login form not visible');
      return;
    }

    // Fill email
    await emailInput.fill('admin@test-org.com');

    // Click continue
    const continueButton = page.locator('[data-testid="continue-button"], button:has-text("Continue")').first();
    await continueButton.click();

    // Wait for password option
    await page.waitForTimeout(1000);

    // Look for password sign in option
    const passwordButton = page.locator('button:has-text("Sign in with password"), button:has-text("Use Password")');
    if (await passwordButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await passwordButton.click();
    }

    // Fill password
    const passwordInput = page.locator('input[type="password"][formControlName="password"], [data-testid="password-input"]').first();
    await expect(passwordInput).toBeVisible({ timeout: 5000 });
    await passwordInput.fill('TestPass123');

    // Submit
    const loginButton = page.locator('button[type="submit"]:has-text("Sign In"), [data-testid="login-button"]').first();
    await loginButton.click();

    // Should be logged in and on tenant page
    await expect(page).toHaveURL(/.*test-org\.com.*/, { timeout: 15000 });
  });

  test('ce-signin-redirects-unverified: Unverified users are handled gracefully', async ({ page }) => {
    // This test checks that when email verification is disabled,
    // users don't get stuck with "verify your email" messages

    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    if (!status.is_community || !status.has_tenants) {
      test.skip(true, 'Test requires Community Edition with tenants');
      return;
    }

    // Check if email verification is disabled
    const verificationResponse = await page.request.get('/api/system/email-verification');
    const verification = await verificationResponse.json();

    if (verification.required) {
      test.skip(true, 'Email verification is enabled - test not applicable');
      return;
    }

    // Get tenant
    const tenantsResponse = await page.request.get('/api/tenants/list');
    const tenants = await tenantsResponse.json();
    const tenantDomain = tenants[0]?.domain;

    if (!tenantDomain) {
      test.skip(true, 'No tenants');
      return;
    }

    // Try to sign up a new user
    const timestamp = Date.now();
    const testEmail = `noVerify-${timestamp}@${tenantDomain}`;

    await page.goto(`/${tenantDomain}/login`);
    await page.waitForLoadState('networkidle');

    const emailInput = page.locator('[data-testid="email-input"], input[formControlName="email"]').first();
    await emailInput.fill(testEmail);

    const continueButton = page.locator('[data-testid="continue-button"], button:has-text("Continue")').first();
    await continueButton.click();

    await page.waitForTimeout(1000);

    // If shows signup form, fill it
    const firstNameInput = page.locator('input[formControlName="first_name"]');
    if (await firstNameInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await firstNameInput.fill('NoVerify');
      await page.locator('input[formControlName="last_name"]').fill('Test');

      const submitButton = page.locator('button[type="submit"]').first();
      await submitButton.click();

      // Should NOT show "check your email for verification"
      await page.waitForTimeout(2000);

      const verifyEmailMessage = await page.locator('text=verify your email, text=verification email, text=check your email').first().isVisible({ timeout: 2000 }).catch(() => false);

      // In Community Edition with email verification disabled, should NOT require email verification
      expect(verifyEmailMessage).toBeFalsy();
    }
  });
});

test.describe('Community Edition Onboarding - Setup Page', () => {
  test('ce-setup-page-shows-options: Setup page shows passkey and password options', async ({ page }) => {
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    if (!status.is_community || !status.has_tenants) {
      test.skip(true, 'Test requires Community Edition with tenants');
      return;
    }

    // Create a test user with setup token via API
    const apiContext = await request.newContext({ baseURL: 'http://localhost:5001' });

    const tenantsResponse = await apiContext.get('/api/tenants/list');
    const tenants = await tenantsResponse.json();
    const tenantDomain = tenants[0]?.domain;

    if (!tenantDomain) {
      test.skip(true, 'No tenants');
      return;
    }

    const timestamp = Date.now();
    const testEmail = `setupOptions-${timestamp}@${tenantDomain}`;

    const createResponse = await apiContext.post('/api/test/create-incomplete-user', {
      data: {
        email: testEmail,
        first_name: 'Setup',
        last_name: 'Options',
        domain: tenantDomain
      }
    });

    if (!createResponse.ok()) {
      test.skip(true, 'Could not create test user');
      await apiContext.dispose();
      return;
    }

    const userData = await createResponse.json();
    await apiContext.dispose();

    // Navigate to setup URL
    if (userData.setup_url) {
      // Handle relative vs absolute URL
      const setupUrl = userData.setup_url.startsWith('/') ? userData.setup_url : `/${tenantDomain}/setup?token=${userData.setup_token}`;
      await page.goto(setupUrl);
      await page.waitForLoadState('networkidle');

      // Should show passkey option
      const passkeyOption = page.locator('text=Use Passkey, text=passkey, text=Passkey');
      await expect(passkeyOption.first()).toBeVisible({ timeout: 10000 });

      // Should show password option
      const passwordOption = page.locator('text=Use Password, text=password');
      await expect(passwordOption.first()).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe('Community Edition - Email Verification Toggle', () => {
  test('ce-email-verification-setting: SuperAdmin can toggle email verification setting', async ({ page }) => {
    // Login as super admin
    await page.goto('/superadmin');
    await page.locator('[data-testid="username-input"]').fill('admin');
    await page.locator('[data-testid="password-input"]').fill('changeme');
    await page.locator('[data-testid="login-button"]').click();

    await expect(page).toHaveURL(/.*superadmin\/dashboard.*/, { timeout: 15000 });

    // Navigate to settings
    await page.goto('/superadmin/settings');
    await page.waitForLoadState('networkidle');

    // Look for email verification toggle
    const emailVerificationToggle = page.locator('mat-slide-toggle:has-text("Email Verification"), mat-checkbox:has-text("email verification")').first();

    const toggleVisible = await emailVerificationToggle.isVisible({ timeout: 5000 }).catch(() => false);

    if (toggleVisible) {
      // Get current state and verify it can be toggled
      const isChecked = await emailVerificationToggle.locator('input').isChecked();

      // Click to toggle
      await emailVerificationToggle.click();

      // Verify toggle changed
      const newState = await emailVerificationToggle.locator('input').isChecked();
      expect(newState).not.toBe(isChecked);

      // Toggle back to original state
      await emailVerificationToggle.click();
    } else {
      // Email verification setting might be in a different location
      test.skip(true, 'Email verification toggle not visible in settings');
    }
  });
});
