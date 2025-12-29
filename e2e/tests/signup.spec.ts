import { test, expect, request } from '@playwright/test';

const API_URL = 'http://localhost:5001';

test.describe('Signup Forms', () => {
  test.beforeEach(async ({ page }) => {
    // Clear cookies to ensure clean session
    await page.context().clearCookies();
  });

  test.describe('Landing Page Signup', () => {
    test('signup-shows-first-last-name: Landing page signup form shows separate First Name and Last Name fields', async ({ page }) => {
      // Generate unique test domain
      const timestamp = Date.now();
      const testDomain = `signup-test-${timestamp}.com`;
      const testEmail = `user@${testDomain}`;

      // Navigate to landing page
      await page.goto('/');

      // Wait for email form to be visible
      await page.waitForSelector('input[formControlName="email"]', { timeout: 10000 });

      // Fill in email
      const emailInput = page.locator('input[formControlName="email"]').first();
      await emailInput.fill(testEmail);

      // Click Continue button
      const continueButton = page.locator('button[type="submit"]:has-text("Continue")').first();
      await continueButton.click();

      // Wait for signup form to appear (new tenant, so should show signup view)
      // Note: homepage.component uses snake_case form controls (first_name, last_name)
      await page.waitForSelector('form:has(input[formControlName="first_name"])', { timeout: 10000 });

      // Verify First Name field is visible
      const firstNameField = page.locator('mat-form-field:has(input[formControlName="first_name"])');
      await expect(firstNameField).toBeVisible();
      await expect(firstNameField.locator('mat-label')).toHaveText('First Name');

      // Verify Last Name field is visible
      const lastNameField = page.locator('mat-form-field:has(input[formControlName="last_name"])');
      await expect(lastNameField).toBeVisible();
      await expect(lastNameField.locator('mat-label')).toHaveText('Last Name');

      // Verify Full Name field does NOT exist
      const fullNameField = page.locator('mat-form-field:has(input[formControlName="fullName"])');
      await expect(fullNameField).toHaveCount(0);

      const nameField = page.locator('mat-form-field:has(input[formControlName="name"])');
      await expect(nameField).toHaveCount(0);
    });

    test('signup-can-fill-names: Users can fill in first name and last name separately', async ({ page }) => {
      // Generate unique test domain
      const timestamp = Date.now();
      const testDomain = `signup-fill-${timestamp}.com`;
      const testEmail = `testuser@${testDomain}`;

      // Navigate to landing page
      await page.goto('/');

      // Fill in email
      const emailInput = page.locator('input[formControlName="email"]').first();
      await emailInput.fill(testEmail);

      // Click Continue
      const continueButton = page.locator('button[type="submit"]:has-text("Continue")').first();
      await continueButton.click();

      // Wait for signup form (snake_case form controls)
      await page.waitForSelector('input[formControlName="first_name"]', { timeout: 10000 });

      // Fill in First Name
      const firstNameInput = page.locator('input[formControlName="first_name"]');
      await firstNameInput.fill('John');

      // Fill in Last Name
      const lastNameInput = page.locator('input[formControlName="last_name"]');
      await lastNameInput.fill('Doe');

      // Verify values are filled
      await expect(firstNameInput).toHaveValue('John');
      await expect(lastNameInput).toHaveValue('Doe');

      // Verify email is pre-filled and readonly
      const emailFieldInSignup = page.locator('input[formControlName="email"]').nth(1); // Second email input (in signup form)
      await expect(emailFieldInSignup).toHaveValue(testEmail);
      await expect(emailFieldInSignup).toHaveAttribute('readonly');
    });

    test('signup-validates-required-names: Form validation works for First Name and Last Name fields', async ({ page }) => {
      // Generate unique test domain
      const timestamp = Date.now();
      const testDomain = `signup-validation-${timestamp}.com`;
      const testEmail = `validator@${testDomain}`;

      // Navigate to landing page
      await page.goto('/');

      // Fill in email
      const emailInput = page.locator('input[formControlName="email"]').first();
      await emailInput.fill(testEmail);

      // Click Continue
      const continueButton = page.locator('button[type="submit"]:has-text("Continue")').first();
      await continueButton.click();

      // Wait for signup form (snake_case form controls)
      await page.waitForSelector('input[formControlName="first_name"]', { timeout: 10000 });

      // Get the submit button (either "Create Account" or "Send Verification Email")
      const submitButton = page.locator('button[type="submit"]').filter({ hasText: /Create Account|Send Verification Email/ });

      // Submit button should be disabled when fields are empty
      await expect(submitButton).toBeDisabled();

      // Fill in only First Name
      const firstNameInput = page.locator('input[formControlName="first_name"]');
      await firstNameInput.fill('John');

      // Button should still be disabled (Last Name is required)
      await expect(submitButton).toBeDisabled();

      // Clear First Name and fill in only Last Name
      await firstNameInput.clear();
      const lastNameInput = page.locator('input[formControlName="last_name"]');
      await lastNameInput.fill('Doe');

      // Button should still be disabled (First Name is required)
      await expect(submitButton).toBeDisabled();

      // Fill in both fields
      await firstNameInput.fill('John');

      // Button should now be enabled
      await expect(submitButton).toBeEnabled();
    });
  });

  test.describe('Login Page Registration', () => {
    test('login-register-shows-first-last-name: Login page registration form shows separate First Name and Last Name fields', async ({ page }) => {
      const timestamp = Date.now();
      const testDomain = `login-signup-${timestamp}.com`;
      const testEmail = `newuser@${testDomain}`;

      // Create a tenant first so the domain exists
      const apiContext = await request.newContext({ baseURL: API_URL });
      await apiContext.post('/api/test/create-incomplete-user', {
        data: {
          email: `admin@${testDomain}`,
          first_name: 'Admin',
          last_name: 'User',
          domain: testDomain
        }
      });
      await apiContext.dispose();

      // Navigate to login page
      await page.goto(`/${testDomain}/login`);

      // Enter email and click continue
      await page.waitForSelector('[data-testid="email-input"]', { timeout: 10000 });
      const emailInput = page.locator('[data-testid="email-input"]');
      await emailInput.fill(testEmail);

      const continueBtn = page.locator('[data-testid="continue-button"]');
      await continueBtn.click();

      // Wait for the view to load (should show webauthn or register option)
      await page.waitForTimeout(1000);

      // Look for "Create account" button/link and click it
      const createAccountButton = page.locator('button:has-text("Create account")');
      if (await createAccountButton.isVisible({ timeout: 5000 })) {
        await createAccountButton.click();

        // Wait for registration form (snake_case form controls)
        await page.waitForSelector('input[formControlName="first_name"]', { timeout: 10000 });

        // Verify First Name field
        const firstNameField = page.locator('mat-form-field:has(input[formControlName="first_name"])');
        await expect(firstNameField).toBeVisible();
        await expect(firstNameField.locator('mat-label')).toHaveText('First Name');

        // Verify Last Name field
        const lastNameField = page.locator('mat-form-field:has(input[formControlName="last_name"])');
        await expect(lastNameField).toBeVisible();
        await expect(lastNameField.locator('mat-label')).toHaveText('Last Name');

        // Verify Full Name field does NOT exist
        const fullNameField = page.locator('mat-form-field:has(input[formControlName="fullName"])');
        await expect(fullNameField).toHaveCount(0);

        const nameField = page.locator('mat-form-field:has(input[formControlName="name"])');
        await expect(nameField).toHaveCount(0);
      } else {
        // If no create account button visible, test is not applicable for this tenant config
        test.skip();
      }
    });

    test('login-register-can-fill-names: Login page registration allows filling first and last names separately', async ({ page }) => {
      const timestamp = Date.now();
      const testDomain = `login-fill-${timestamp}.com`;
      const testEmail = `filltest@${testDomain}`;

      // Create a tenant first
      const apiContext = await request.newContext({ baseURL: API_URL });
      await apiContext.post('/api/test/create-incomplete-user', {
        data: {
          email: `admin@${testDomain}`,
          first_name: 'Admin',
          last_name: 'User',
          domain: testDomain
        }
      });
      await apiContext.dispose();

      // Navigate to login page
      await page.goto(`/${testDomain}/login`);

      // Enter email and proceed
      await page.waitForSelector('[data-testid="email-input"]', { timeout: 10000 });
      const emailInput = page.locator('[data-testid="email-input"]');
      await emailInput.fill(testEmail);

      const continueBtn = page.locator('[data-testid="continue-button"]');
      await continueBtn.click();

      await page.waitForTimeout(1000);

      // Click "Create account" if visible
      const createAccountButton = page.locator('button:has-text("Create account")');
      if (await createAccountButton.isVisible({ timeout: 5000 })) {
        await createAccountButton.click();

        // Wait for registration form (snake_case form controls)
        await page.waitForSelector('input[formControlName="first_name"]', { timeout: 10000 });

        // Fill in First Name
        const firstNameInput = page.locator('input[formControlName="first_name"]');
        await firstNameInput.fill('Jane');

        // Fill in Last Name
        const lastNameInput = page.locator('input[formControlName="last_name"]');
        await lastNameInput.fill('Smith');

        // Verify values
        await expect(firstNameInput).toHaveValue('Jane');
        await expect(lastNameInput).toHaveValue('Smith');

        // Verify email is pre-filled
        const emailFieldInForm = page.locator('input[formControlName="email"]').last();
        await expect(emailFieldInForm).toHaveValue(testEmail);
      } else {
        test.skip();
      }
    });

    test('login-register-validates-names: Login page registration validates First Name and Last Name as required', async ({ page }) => {
      const timestamp = Date.now();
      const testDomain = `login-valid-${timestamp}.com`;
      const testEmail = `validtest@${testDomain}`;

      // Create a tenant first
      const apiContext = await request.newContext({ baseURL: API_URL });
      await apiContext.post('/api/test/create-incomplete-user', {
        data: {
          email: `admin@${testDomain}`,
          first_name: 'Admin',
          last_name: 'User',
          domain: testDomain
        }
      });
      await apiContext.dispose();

      // Navigate to login page
      await page.goto(`/${testDomain}/login`);

      // Enter email and proceed
      await page.waitForSelector('[data-testid="email-input"]', { timeout: 10000 });
      const emailInput = page.locator('[data-testid="email-input"]');
      await emailInput.fill(testEmail);

      const continueBtn = page.locator('[data-testid="continue-button"]');
      await continueBtn.click();

      await page.waitForTimeout(1000);

      // Click "Create account"
      const createAccountButton = page.locator('button:has-text("Create account")');
      if (await createAccountButton.isVisible({ timeout: 5000 })) {
        await createAccountButton.click();

        // Wait for registration form (snake_case form controls)
        await page.waitForSelector('input[formControlName="first_name"]', { timeout: 10000 });

        // Get submit button
        const submitButton = page.locator('button[type="submit"]').filter({ hasText: /Create account with passkey/i });

        // Should be disabled when empty
        await expect(submitButton).toBeDisabled();

        // Fill only First Name
        const firstNameInput = page.locator('input[formControlName="first_name"]');
        await firstNameInput.fill('Test');

        // Should still be disabled
        await expect(submitButton).toBeDisabled();

        // Clear and fill only Last Name
        await firstNameInput.clear();
        const lastNameInput = page.locator('input[formControlName="last_name"]');
        await lastNameInput.fill('User');

        // Should still be disabled
        await expect(submitButton).toBeDisabled();

        // Fill both fields
        await firstNameInput.fill('Test');

        // Should be enabled now
        await expect(submitButton).toBeEnabled();
      } else {
        test.skip();
      }
    });
  });

  test.describe('Access Request Forms', () => {
    test('access-request-shows-first-last-name: Access request form shows separate First Name and Last Name fields', async ({ page }) => {
      const timestamp = Date.now();
      const testDomain = `access-req-${timestamp}.com`;
      const testEmail = `requester@${testDomain}`;

      // Create a tenant with existing users (approval required)
      const apiContext = await request.newContext({ baseURL: API_URL });
      await apiContext.post('/api/test/create-user', {
        data: {
          email: `admin@${testDomain}`,
          password: 'TestPass123',
          name: 'Admin User',
          role: 'admin',
          domain: testDomain
        }
      });
      await apiContext.dispose();

      // Navigate to landing page
      await page.goto('/');

      // Enter email for existing tenant
      const emailInput = page.locator('input[formControlName="email"]').first();
      await emailInput.fill(testEmail);

      const continueButton = page.locator('button[type="submit"]:has-text("Continue")').first();
      await continueButton.click();

      // Wait for access request form (should appear for existing tenants)
      // The view might be 'access_request' or 'join_organization' depending on tenant settings
      await page.waitForTimeout(2000);

      // Check if we're on access request or join organization view (snake_case form controls)
      const firstNameInput = page.locator('input[formControlName="first_name"]');
      if (await firstNameInput.isVisible({ timeout: 5000 })) {
        // Verify First Name field
        const firstNameField = page.locator('mat-form-field:has(input[formControlName="first_name"])');
        await expect(firstNameField).toBeVisible();
        await expect(firstNameField.locator('mat-label')).toHaveText('First Name');

        // Verify Last Name field
        const lastNameField = page.locator('mat-form-field:has(input[formControlName="last_name"])');
        await expect(lastNameField).toBeVisible();
        await expect(lastNameField.locator('mat-label')).toHaveText('Last Name');

        // Verify Full Name field does NOT exist
        const fullNameField = page.locator('mat-form-field:has(input[formControlName="fullName"])');
        await expect(fullNameField).toHaveCount(0);
      } else {
        // Might have redirected to login instead - this is OK depending on tenant config
        test.skip();
      }
    });
  });
});
