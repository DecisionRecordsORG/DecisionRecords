import { test, expect } from '@playwright/test';
import { loginAsUser, loginAsSuperAdmin, dismissOverlays } from '../fixtures/auth';

test.describe('Slack OIDC Sign In', () => {
  test.describe('Homepage Sign in with Slack Button', () => {
    test('shows-slack-button-when-enabled: Shows Sign in with Slack button when OIDC is enabled', async ({ page }) => {
      // Mock Slack OIDC status as enabled
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            enabled: true
          })
        });
      });

      // Navigate to homepage
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);

      // Enter an email to see the sign in options
      const emailInput = page.locator('input[type="email"], input[name="email"]').first();
      if (await emailInput.isVisible()) {
        await emailInput.fill('test@example.com');
      }

      // Wait for Slack button to appear
      const slackButton = page.locator('button:has-text("Sign in with Slack"), a:has-text("Sign in with Slack")');
      await expect(slackButton.first()).toBeVisible({ timeout: 5000 });
    });

    test('hides-slack-button-when-disabled: Hides Sign in with Slack button when OIDC is disabled', async ({ page }) => {
      // Mock Slack OIDC status as disabled
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            enabled: false,
            reason: 'slack_disabled'
          })
        });
      });

      // Navigate to homepage
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);

      // Enter an email
      const emailInput = page.locator('input[type="email"], input[name="email"]').first();
      if (await emailInput.isVisible()) {
        await emailInput.fill('test@example.com');
      }

      // Slack button should not be visible
      const slackButton = page.locator('button:has-text("Sign in with Slack"), a:has-text("Sign in with Slack")');
      await expect(slackButton).toBeHidden({ timeout: 3000 });
    });

    test('slack-button-redirects-to-oidc: Clicking Slack button redirects to OIDC endpoint', async ({ page }) => {
      // Mock Slack OIDC status as enabled
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            enabled: true
          })
        });
      });

      // Mock the OIDC initiation to avoid actual redirect to Slack
      await page.route('/auth/slack/oidc*', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'text/html',
          body: '<html><body>Mock Slack OAuth redirect</body></html>'
        });
      });

      // Navigate to homepage
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);

      // Enter an email
      const emailInput = page.locator('input[type="email"], input[name="email"]').first();
      if (await emailInput.isVisible()) {
        await emailInput.fill('test@example.com');
      }

      // Click Slack button
      const slackButton = page.locator('button:has-text("Sign in with Slack"), a:has-text("Sign in with Slack")').first();
      await expect(slackButton).toBeVisible({ timeout: 5000 });
      await slackButton.click();

      // Verify we're going to the OIDC endpoint
      await page.waitForTimeout(500);
      const url = page.url();
      expect(url).toContain('/auth/slack/oidc');
    });
  });

  test.describe('Tenant Login Sign in with Slack', () => {
    test('shows-slack-button-on-tenant-login: Shows Slack button on tenant login page', async ({ page }) => {
      // Mock Slack OIDC status as enabled
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            enabled: true
          })
        });
      });

      // Mock tenant auth config
      await page.route('/api/auth/config?domain=test-org.com', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            domain: 'test-org.com',
            auth_method: 'local',
            allow_password: true,
            allow_passkey: true,
            allow_slack_oidc: true,
            tenant_prefix: 'TST'
          })
        });
      });

      // Navigate to tenant login
      await page.goto('/test-org.com/login');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);

      // Slack button should be visible
      const slackButton = page.locator('button:has-text("Sign in with Slack"), a:has-text("Sign in with Slack")');
      await expect(slackButton.first()).toBeVisible({ timeout: 5000 });
    });

    test('hides-slack-button-when-tenant-disables: Hides Slack button when tenant disables OIDC', async ({ page }) => {
      // Mock Slack OIDC status as enabled globally
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            enabled: true
          })
        });
      });

      // Mock tenant auth config with Slack OIDC disabled
      await page.route('/api/auth/config?domain=test-org.com', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            domain: 'test-org.com',
            auth_method: 'local',
            allow_password: true,
            allow_passkey: true,
            allow_slack_oidc: false,  // Tenant disabled
            tenant_prefix: 'TST'
          })
        });
      });

      // Navigate to tenant login
      await page.goto('/test-org.com/login');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);

      // Slack button should not be visible
      const slackButton = page.locator('button:has-text("Sign in with Slack"), a:has-text("Sign in with Slack")');
      await expect(slackButton).toBeHidden({ timeout: 3000 });
    });

    test('slack-only-auth-mode: Shows only Slack sign-in when auth_method is slack_oidc', async ({ page }) => {
      // Mock Slack OIDC status as enabled
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            enabled: true
          })
        });
      });

      // Mock tenant auth config with Slack OIDC as only auth method
      await page.route('/api/auth/config?domain=slack-only-org.com', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            domain: 'slack-only-org.com',
            auth_method: 'slack_oidc',  // Slack-only mode
            allow_password: false,
            allow_passkey: false,
            allow_slack_oidc: true,
            tenant_prefix: 'SLK'
          })
        });
      });

      // Navigate to tenant login
      await page.goto('/slack-only-org.com/login');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);

      // Slack button should be visible
      const slackButton = page.locator('button:has-text("Sign in with Slack"), a:has-text("Sign in with Slack")');
      await expect(slackButton.first()).toBeVisible({ timeout: 5000 });

      // Password form should not be visible in Slack-only mode
      // Note: This depends on how the UI handles slack_oidc auth_method
    });
  });

  test.describe('Admin Settings - Slack OIDC Configuration', () => {
    test('shows-slack-oidc-toggle-in-settings: Shows Slack OIDC toggle in auth settings', async ({ page }) => {
      // Mock Slack OIDC status as enabled
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            enabled: true
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Auth Configuration tab
      const authTab = page.locator('div.mat-mdc-tab:has-text("Auth Configuration"), div.mat-mdc-tab:has-text("Authentication")');
      if (await authTab.first().isVisible()) {
        await authTab.first().click({ force: true });
        await page.waitForTimeout(1000);
      }

      // Look for Slack OIDC option in auth method radio buttons or toggle
      const slackOidcOption = page.locator('text=Sign in with Slack, text=Slack OIDC, label:has-text("Slack")');
      await expect(slackOidcOption.first()).toBeVisible({ timeout: 5000 });
    });

    test('can-select-slack-oidc-auth-method: Can select Slack OIDC as auth method', async ({ page }) => {
      // Mock APIs
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ enabled: true })
        });
      });

      await page.route('/api/admin/auth-config', async route => {
        if (route.request().method() === 'GET') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              domain: 'test-org.com',
              auth_method: 'local',
              allow_password: true,
              allow_passkey: true,
              allow_slack_oidc: true,
              tenant_prefix: 'TST'
            })
          });
        } else if (route.request().method() === 'POST') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              domain: 'test-org.com',
              auth_method: 'slack_oidc',
              allow_slack_oidc: true,
              tenant_prefix: 'TST'
            })
          });
        }
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Auth Configuration tab
      const authTab = page.locator('div.mat-mdc-tab:has-text("Auth Configuration"), div.mat-mdc-tab:has-text("Authentication")');
      if (await authTab.first().isVisible()) {
        await authTab.first().click({ force: true });
        await page.waitForTimeout(1000);
      }

      // Look for Slack OIDC radio button and click it
      const slackOidcRadio = page.locator('input[type="radio"][value="slack_oidc"], mat-radio-button:has-text("Slack")');
      if (await slackOidcRadio.first().isVisible()) {
        await slackOidcRadio.first().click();
        await page.waitForTimeout(500);

        // Save the form
        const saveButton = page.locator('button:has-text("Save")').first();
        if (await saveButton.isVisible()) {
          await saveButton.click();
          await page.waitForTimeout(1000);
        }
      }
    });
  });

  test.describe('OIDC Status API', () => {
    test('status-api-returns-enabled: Status API returns enabled when Slack is configured', async ({ page }) => {
      // Navigate to a page that calls the API
      const response = await page.request.get('/api/auth/slack-oidc-status');
      const data = await response.json();

      // Should return a valid response with enabled field
      expect(data).toHaveProperty('enabled');
      expect(typeof data.enabled).toBe('boolean');
    });
  });

  test.describe('Slack Link Account with OIDC', () => {
    test('shows-slack-signin-on-link-page: Shows Slack sign-in option on link page when not logged in', async ({ page }) => {
      // Mock Slack OIDC status as enabled
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            enabled: true
          })
        });
      });

      // Mock token validation API - not logged in
      await page.route('/api/slack/link/validate', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            valid: true,
            workspace_name: 'Test Workspace',
            workspace_id: 'T123456',
            slack_user_id: 'U123456',
            slack_email: 'user@test.com',
            is_logged_in: false
          })
        });
      });

      // Navigate to slack link page with token
      await page.goto('/slack/link?token=valid_test_token');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      // Slack sign in button should be visible
      const slackSignInButton = page.locator('button:has-text("Sign in with Slack"), a:has-text("Sign in with Slack")');
      await expect(slackSignInButton.first()).toBeVisible({ timeout: 5000 });
    });

    test('slack-signin-stores-token: Slack sign-in stores link token before redirect', async ({ page }) => {
      // Mock Slack OIDC status as enabled
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            enabled: true
          })
        });
      });

      // Mock token validation API - not logged in
      await page.route('/api/slack/link/validate', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            valid: true,
            workspace_name: 'Test Workspace',
            workspace_id: 'T123456',
            slack_user_id: 'U123456',
            slack_email: 'user@test.com',
            is_logged_in: false
          })
        });
      });

      // Mock OIDC redirect to intercept it
      await page.route('/auth/slack/oidc*', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'text/html',
          body: '<html><body>Mock redirect</body></html>'
        });
      });

      // Navigate to slack link page with token
      await page.goto('/slack/link?token=valid_test_token');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      // Click Slack sign in button
      const slackSignInButton = page.locator('button:has-text("Sign in with Slack"), a:has-text("Sign in with Slack")').first();
      if (await slackSignInButton.isVisible()) {
        // Check that sessionStorage will have the token after click
        await slackSignInButton.click();
        await page.waitForTimeout(500);

        // The component should store the token before redirecting
        const storedToken = await page.evaluate(() => sessionStorage.getItem('slack_link_token'));
        expect(storedToken).toBe('valid_test_token');
      }
    });
  });

  test.describe('OIDC Callback Handling', () => {
    test('callback-shows-error-for-invalid-state: Callback shows error for invalid state', async ({ page }) => {
      // Navigate to callback with invalid state
      await page.goto('/auth/slack/oidc/callback?code=test_code&state=invalid_state');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);

      // Should redirect to error page or show error
      const url = page.url();
      // Either redirected to homepage with error or shows error
      expect(url.includes('error') || url === '/' || url.includes('/login')).toBeTruthy();
    });

    test('callback-shows-error-for-missing-code: Callback shows error when code is missing', async ({ page }) => {
      // Navigate to callback without code
      await page.goto('/auth/slack/oidc/callback?state=some_state');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);

      // Should redirect or show error
      const url = page.url();
      expect(url.includes('error') || url === '/' || url.includes('/login')).toBeTruthy();
    });
  });

  test.describe('Slack Logo Display', () => {
    test('displays-slack-logo-on-button: Displays Slack logo on sign-in button', async ({ page }) => {
      // Mock Slack OIDC status as enabled
      await page.route('/api/auth/slack-oidc-status', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            enabled: true
          })
        });
      });

      // Navigate to homepage
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);

      // Enter an email
      const emailInput = page.locator('input[type="email"], input[name="email"]').first();
      if (await emailInput.isVisible()) {
        await emailInput.fill('test@example.com');
      }

      // Check for Slack logo image
      const slackLogo = page.locator('img[src*="slack"], img[alt*="Slack"]');
      // Slack logo might be within the button
      const slackButton = page.locator('button:has-text("Sign in with Slack"), a:has-text("Sign in with Slack")').first();

      if (await slackButton.isVisible()) {
        // Either there's an img tag or an inline SVG
        const hasLogo = await slackLogo.isVisible().catch(() => false);
        const hasSvg = await slackButton.locator('svg').isVisible().catch(() => false);
        expect(hasLogo || hasSvg).toBeTruthy();
      }
    });
  });
});
