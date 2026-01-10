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

test.describe('Setup Wizard - Community Edition', () => {
  test('shows-setup-wizard-page: Setup wizard page loads correctly', async ({ page }) => {
    // Navigate to setup wizard
    await page.goto('/setup');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/setup');
      await page.waitForLoadState('networkidle');
    }

    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    // This test only applies to Community Edition
    if (!status.is_community) {
      test.skip(true, 'Test only applies to Community Edition');
      return;
    }

    // Check for setup wizard heading
    const heading = page.locator('mat-card-title:has-text("Set Up Your Instance")');
    await expect(heading).toBeVisible({ timeout: 10000 });
  });

  test('setup-wizard-shows-stepper: Setup wizard shows multi-step form', async ({ page }) => {
    await page.goto('/setup');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/setup');
      await page.waitForLoadState('networkidle');
    }

    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    if (!status.is_community) {
      test.skip(true, 'Test only applies to Community Edition');
      return;
    }

    // If setup is already complete, we can't test the wizard
    if (status.has_tenants) {
      test.skip(true, 'Setup already completed - cannot test wizard');
      return;
    }

    // Check for stepper steps
    const organizationStep = page.locator('mat-step-header:has-text("Organization")');
    const adminStep = page.locator('mat-step-header:has-text("Admin Account")');
    const completeStep = page.locator('mat-step-header:has-text("Complete Setup")');

    await expect(organizationStep).toBeVisible({ timeout: 5000 });
    await expect(adminStep).toBeVisible({ timeout: 5000 });
    await expect(completeStep).toBeVisible({ timeout: 5000 });
  });

  test('setup-wizard-validates-required-fields: Setup wizard validates organization fields', async ({ page }) => {
    await page.goto('/setup');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/setup');
      await page.waitForLoadState('networkidle');
    }

    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    if (!status.is_community) {
      test.skip(true, 'Test only applies to Community Edition');
      return;
    }

    if (status.has_tenants) {
      test.skip(true, 'Setup already completed - cannot test wizard');
      return;
    }

    // Find the Next button in the first step
    const nextButton = page.locator('button:has-text("Next")').first();

    // Next button should be disabled when fields are empty
    await expect(nextButton).toBeDisabled({ timeout: 5000 });

    // Fill in organization name
    const orgNameInput = page.locator('input[formcontrolname="organizationName"]');
    await orgNameInput.fill('Test Organization');

    // Still disabled (domain is empty)
    await expect(nextButton).toBeDisabled();

    // Fill in domain
    const domainInput = page.locator('input[formcontrolname="domain"]');
    await domainInput.fill('test-org.com');

    // Wait for validation
    await page.waitForTimeout(300);

    // Now Next should be enabled
    await expect(nextButton).toBeEnabled({ timeout: 5000 });
  });

  test('setup-wizard-can-navigate-steps: Can navigate between setup wizard steps', async ({ page }) => {
    await page.goto('/setup');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/setup');
      await page.waitForLoadState('networkidle');
    }

    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    if (!status.is_community) {
      test.skip(true, 'Test only applies to Community Edition');
      return;
    }

    if (status.has_tenants) {
      test.skip(true, 'Setup already completed - cannot test wizard');
      return;
    }

    // Fill in step 1 (Organization)
    const orgNameInput = page.locator('input[formcontrolname="organizationName"]');
    await orgNameInput.fill('Test Organization');

    const domainInput = page.locator('input[formcontrolname="domain"]');
    await domainInput.fill('test-org.com');

    // Click Next
    const nextButton = page.locator('button:has-text("Next")').first();
    await nextButton.click();

    // Wait for step transition
    await page.waitForTimeout(500);

    // Should now be on step 2 (Admin Account)
    const adminEmailInput = page.locator('input[formcontrolname="adminEmail"]');
    await expect(adminEmailInput).toBeVisible({ timeout: 5000 });

    // Fill in admin details
    await page.locator('input[formcontrolname="adminName"]').fill('Test Admin');
    await adminEmailInput.fill('admin@test-org.com');
    await page.locator('input[formcontrolname="adminPassword"]').fill('Password123!');
    await page.locator('input[formcontrolname="confirmPassword"]').fill('Password123!');

    // Wait for validation
    await page.waitForTimeout(300);

    // Click Next to go to step 3
    const nextButton2 = page.locator('button:has-text("Next")').first();
    await nextButton2.click();

    // Wait for step transition
    await page.waitForTimeout(500);

    // Should now see the Complete Setup button
    const completeButton = page.locator('button:has-text("Complete Setup")');
    await expect(completeButton).toBeVisible({ timeout: 5000 });

    // Should see review information
    const reviewOrg = page.locator('text=Test Organization');
    await expect(reviewOrg).toBeVisible({ timeout: 5000 });
  });

  test('setup-wizard-back-to-home-link: Back to Home link works', async ({ page }) => {
    await page.goto('/setup');
    await page.waitForLoadState('networkidle');

    // Handle license acceptance if redirected
    if (await acceptLicenseIfNeeded(page)) {
      await page.goto('/setup');
      await page.waitForLoadState('networkidle');
    }

    // Check system status
    const statusResponse = await page.request.get('/api/system/status');
    const status = await statusResponse.json();

    if (!status.is_community) {
      test.skip(true, 'Test only applies to Community Edition');
      return;
    }

    // Find and click the Back to Home link
    const backLink = page.locator('a:has-text("Back to Home")');
    await expect(backLink).toBeVisible({ timeout: 5000 });
    await backLink.click();

    // Should navigate to home page
    await page.waitForURL('/', { timeout: 10000 });
    expect(page.url()).not.toContain('/setup');
  });
});

test.describe('Setup Wizard API - Community Edition', () => {
  test('setup-api-rejects-enterprise: Setup API rejects requests in Enterprise Edition', async ({ request }) => {
    // Check system status
    const statusResponse = await request.get('/api/system/status');
    const status = await statusResponse.json();

    if (status.is_community) {
      test.skip(true, 'Test only applies to Enterprise Edition');
      return;
    }

    // Try to call setup API
    const response = await request.post('/api/setup/initialize', {
      data: {
        organization_name: 'Test Org',
        domain: 'test.com',
        admin_email: 'admin@test.com',
        admin_password: 'Password123!'
      }
    });

    expect(response.status()).toBe(403);
    const body = await response.json();
    expect(body.error).toContain('Community Edition');
  });

  test('setup-api-rejects-when-tenant-exists: Setup API rejects when tenant exists', async ({ request }) => {
    // Check system status
    const statusResponse = await request.get('/api/system/status');
    const status = await statusResponse.json();

    if (!status.is_community) {
      test.skip(true, 'Test only applies to Community Edition');
      return;
    }

    if (!status.has_tenants) {
      test.skip(true, 'Test requires existing tenant');
      return;
    }

    // Try to call setup API when tenant already exists
    const response = await request.post('/api/setup/initialize', {
      data: {
        organization_name: 'Another Org',
        domain: 'another.com',
        admin_email: 'admin@another.com',
        admin_password: 'Password123!'
      }
    });

    expect(response.status()).toBe(400);
    const body = await response.json();
    expect(body.error).toContain('already exists');
  });

  test('setup-api-validates-required-fields: Setup API validates required fields', async ({ request }) => {
    // Check system status
    const statusResponse = await request.get('/api/system/status');
    const status = await statusResponse.json();

    if (!status.is_community) {
      test.skip(true, 'Test only applies to Community Edition');
      return;
    }

    if (status.has_tenants) {
      test.skip(true, 'Setup already completed');
      return;
    }

    if (!status.license_accepted) {
      test.skip(true, 'License not accepted');
      return;
    }

    // Test missing organization_name
    const response1 = await request.post('/api/setup/initialize', {
      data: {
        domain: 'test.com',
        admin_email: 'admin@test.com',
        admin_password: 'Password123!'
      }
    });
    expect(response1.status()).toBe(400);
    const body1 = await response1.json();
    expect(body1.error).toContain('Organization name');

    // Test missing domain
    const response2 = await request.post('/api/setup/initialize', {
      data: {
        organization_name: 'Test Org',
        admin_email: 'admin@test.com',
        admin_password: 'Password123!'
      }
    });
    expect(response2.status()).toBe(400);
    const body2 = await response2.json();
    expect(body2.error).toContain('Domain');

    // Test short password
    const response3 = await request.post('/api/setup/initialize', {
      data: {
        organization_name: 'Test Org',
        domain: 'test.com',
        admin_email: 'admin@test.com',
        admin_password: 'short'
      }
    });
    expect(response3.status()).toBe(400);
    const body3 = await response3.json();
    expect(body3.error).toContain('8 characters');
  });
});
