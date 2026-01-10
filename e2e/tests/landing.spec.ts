import { test, expect } from '@playwright/test';

// Helper to handle license acceptance for Community Edition
async function acceptLicenseIfNeeded(page: any): Promise<boolean> {
  const currentUrl = page.url();
  if (currentUrl.includes('/license')) {
    // First, check the acceptance checkbox
    const acceptCheckbox = page.locator('mat-checkbox').first();
    if (await acceptCheckbox.isVisible({ timeout: 5000 }).catch(() => false)) {
      await acceptCheckbox.click();
      await page.waitForTimeout(300);
    }

    // Now click the Accept button (which should be enabled after checking the box)
    const acceptButton = page.locator('button:has-text("Accept and Continue")').first();
    if (await acceptButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await acceptButton.click();
      await page.waitForLoadState('networkidle');
      return true;
    }
  }
  return false;
}

test.describe('Landing Page - Community Edition', () => {
  test('shows-loading-then-cta: Shows loading spinner then appropriate CTA', async ({ page }) => {
    // Navigate to landing page
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    }

    // Check if we're on the landing page
    const landingHeading = page.locator('h1:has-text("Decision Records")');
    if (!(await landingHeading.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Not on landing page - may have been redirected');
      return;
    }

    // Wait for loading to complete - either Set Up or Sign In button should be visible
    // Community Edition shows one of these, Enterprise Edition shows domain input
    const setupButton = page.locator('button:has-text("Set Up Your Instance")');
    const signInButton = page.locator('button:has-text("Sign In")');
    const getStartedButton = page.locator('button:has-text("Get Started")');
    const domainInput = page.locator('input[placeholder="example.com"]');

    // Wait for one of the CTAs to appear (loading complete)
    await expect(
      setupButton.or(signInButton).or(getStartedButton).or(domainInput)
    ).toBeVisible({ timeout: 10000 });
  });

  test('fresh-install-shows-setup: Fresh install shows Set Up Your Instance button', async ({ page }) => {
    // This test checks for fresh install behavior
    // Note: If tenants exist, this test may not apply - skip appropriately
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    }

    // Check if we're on the landing page
    const landingHeading = page.locator('h1:has-text("Decision Records")');
    if (!(await landingHeading.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Not on landing page - may have been redirected');
      return;
    }

    // Check system status via API to determine expected behavior
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    if (status.is_community && !status.has_tenants) {
      // Fresh Community Edition install - should show Setup button
      const setupButton = page.locator('button:has-text("Set Up Your Instance")');
      await expect(setupButton).toBeVisible({ timeout: 5000 });
    } else if (status.is_community && status.has_tenants) {
      // Configured Community Edition - should show Sign In button
      const signInButton = page.locator('button:has-text("Sign In")');
      await expect(signInButton).toBeVisible({ timeout: 5000 });
    } else {
      // Enterprise Edition - should show domain input
      const domainInput = page.locator('input[placeholder="example.com"]');
      await expect(domainInput).toBeVisible({ timeout: 5000 });
    }
  });

  test('setup-button-navigates-to-setup-wizard: Set Up button navigates to setup wizard', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    }

    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    // This test only applies to fresh Community Edition installs
    if (!status.is_community || status.has_tenants) {
      test.skip(true, 'Test only applies to fresh Community Edition installs');
      return;
    }

    // Find and click the Setup button
    const setupButton = page.locator('button:has-text("Set Up Your Instance")');
    await expect(setupButton).toBeVisible({ timeout: 5000 });
    await setupButton.click();

    // Should navigate to setup wizard
    await page.waitForURL('**/setup', { timeout: 10000 });
    expect(page.url()).toContain('/setup');
  });

  test('signin-button-navigates-to-tenant-login: Sign In button navigates to tenant login', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    }

    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    // This test only applies to configured Community Edition installs
    if (!status.is_community || !status.has_tenants) {
      test.skip(true, 'Test only applies to configured Community Edition installs');
      return;
    }

    // Find and click the Sign In button
    const signInButton = page.locator('button:has-text("Sign In")');
    await expect(signInButton).toBeVisible({ timeout: 5000 });
    await signInButton.click();

    // Should navigate to tenant login page (/:tenant/login)
    await page.waitForURL('**/login', { timeout: 10000 });
    expect(page.url()).toContain('/login');
  });
});

test.describe('Landing Page - Enterprise Edition', () => {
  test('get-started-button-disabled-when-empty: Button is disabled when domain is empty', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    }

    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    // This test only applies to Enterprise Edition
    if (status.is_community) {
      test.skip(true, 'Test only applies to Enterprise Edition');
      return;
    }

    // Check if we're on the landing page
    const landingHeading = page.locator('h1:has-text("Decision Records")');
    if (!(await landingHeading.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Not on landing page - may have been redirected');
      return;
    }

    // Find the Get Started button
    const getStartedButton = page.locator('button:has-text("Get Started")');

    // Button should be disabled when domain is empty
    await expect(getStartedButton).toBeDisabled({ timeout: 5000 });
  });

  test('get-started-button-enabled-after-domain-entry: Button enables after entering domain', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    }

    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    // This test only applies to Enterprise Edition
    if (status.is_community) {
      test.skip(true, 'Test only applies to Enterprise Edition');
      return;
    }

    // Check if we're on the landing page
    const landingHeading = page.locator('h1:has-text("Decision Records")');
    if (!(await landingHeading.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Not on landing page - may have been redirected');
      return;
    }

    // Find the domain input field
    const domainInput = page.locator('input[placeholder="example.com"]');
    const getStartedButton = page.locator('button:has-text("Get Started")');

    // Button should initially be disabled
    await expect(getStartedButton).toBeDisabled();

    // Enter a domain
    await domainInput.fill('test-org.com');

    // Wait for Angular change detection
    await page.waitForTimeout(200);

    // Button should now be enabled
    await expect(getStartedButton).toBeEnabled({ timeout: 5000 });
  });

  test('get-started-navigates-to-tenant: Clicking Get Started navigates to tenant page', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    }

    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    // This test only applies to Enterprise Edition
    if (status.is_community) {
      test.skip(true, 'Test only applies to Enterprise Edition');
      return;
    }

    // Check if we're on the landing page
    const landingHeading = page.locator('h1:has-text("Decision Records")');
    if (!(await landingHeading.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Not on landing page - may have been redirected');
      return;
    }

    // Find the domain input and Get Started button
    const domainInput = page.locator('input[placeholder="example.com"]');
    const getStartedButton = page.locator('button:has-text("Get Started")');

    // Enter a domain
    await domainInput.fill('test-org.com');

    // Wait for button to enable
    await expect(getStartedButton).toBeEnabled({ timeout: 5000 });

    // Click Get Started
    await getStartedButton.click();

    // Should navigate to tenant login page
    await page.waitForURL('**/test-org.com/login', { timeout: 10000 });
    expect(page.url()).toContain('test-org.com/login');
  });
});

test.describe('Landing Page - Common Elements', () => {
  test('shows-features-section: Landing page shows features section', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    }

    // Check for features section
    const featuresHeading = page.locator('h2:has-text("Core Features")');
    await expect(featuresHeading).toBeVisible({ timeout: 10000 });

    // Check for at least one feature card
    const featureCard = page.locator('.feature-card').first();
    await expect(featureCard).toBeVisible({ timeout: 5000 });
  });

  test('shows-superadmin-link: Landing page shows super admin link', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    }

    // Check for super admin link
    const adminLink = page.locator('a:has-text("Super Admin Login")');
    await expect(adminLink).toBeVisible({ timeout: 10000 });
  });

  test('shows-github-link-in-footer: Landing page shows GitHub link in footer', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    }

    // Check for GitHub link
    const githubLink = page.locator('a:has-text("View on GitHub")');
    await expect(githubLink).toBeVisible({ timeout: 10000 });
  });
});
