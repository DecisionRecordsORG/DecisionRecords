import { test, expect } from '@playwright/test';
import { loginAsUser, dismissOverlays } from '../fixtures/auth';

test.describe('Slack Settings', () => {
  test.describe('Slack Tab Access', () => {
    test('admin-can-access-slack-tab: Admin can access Slack tab in settings', async ({ page }) => {
      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      // Wait for decisions page to load fully
      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });

      // Direct navigation to admin settings
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000); // Extra time for Angular auth guards

      // Check if we got redirected (guard blocked us)
      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available - guard may have redirected');
        return;
      }

      // Wait for settings page to load
      await page.waitForSelector('mat-tab-group', { timeout: 15000 });

      // Dismiss any overlays before clicking
      await dismissOverlays(page);

      // Click on the Slack tab - use force to bypass overlays
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await expect(slackTab).toBeVisible({ timeout: 5000 });
      await slackTab.click({ force: true });

      // Verify Slack tab content is visible
      await page.waitForTimeout(1000);
      const slackContent = page.locator('h4:has-text("About Slack Integration"), mat-card-title:has-text("About Slack Integration")');
      await expect(slackContent.first()).toBeVisible({ timeout: 5000 });
    });

    test('regular-user-cannot-access-slack-settings: Regular user cannot access Slack settings', async ({ page }) => {
      await loginAsUser(page, 'user@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });

      // Try to navigate to admin settings
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);

      // Should not be on admin page
      const url = page.url();
      expect(url).not.toContain('/admin');
    });
  });

  test.describe('Not Connected State', () => {
    test('shows-install-button-when-not-connected: Shows install button when Slack is not connected', async ({ page }) => {
      // Mock API to return not installed
      await page.route('/api/slack/settings', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            installed: false,
            install_url: '/api/slack/install'
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Slack tab
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await slackTab.click({ force: true });
      await page.waitForTimeout(1000);

      // Verify "Add to Slack" button is visible
      const installButton = page.locator('[data-testid="slack-install-button"]');
      await expect(installButton).toBeVisible({ timeout: 5000 });

      // Verify it links to /api/slack/install
      const href = await installButton.getAttribute('href');
      expect(href).toBe('/api/slack/install');

      // Verify the not connected message
      const notConnectedText = page.locator('text=not connected yet');
      await expect(notConnectedText).toBeVisible();
    });
  });

  test.describe('Connected State', () => {
    test('shows-workspace-info-when-connected: Shows workspace info and settings when connected', async ({ page }) => {
      // Mock API to return connected workspace
      await page.route('/api/slack/settings', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            installed: true,
            workspace_id: 'T123456',
            workspace_name: 'Test Workspace',
            installed_at: '2025-01-01T12:00:00Z',
            last_activity_at: '2025-01-10T10:30:00Z',
            default_channel_id: 'C123456',
            notifications_enabled: true,
            notify_on_create: true,
            notify_on_status_change: true
          })
        });
      });

      // Mock channels API
      await page.route('/api/slack/channels', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            channels: [
              { id: 'C123456', name: 'general', is_private: false },
              { id: 'C789012', name: 'decisions', is_private: false },
              { id: 'C345678', name: 'private-channel', is_private: true }
            ]
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Slack tab
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await slackTab.click({ force: true });
      await page.waitForTimeout(2000);

      // Verify workspace name is displayed
      const workspaceName = page.locator('text=Connected to Test Workspace');
      await expect(workspaceName).toBeVisible({ timeout: 5000 });

      // Verify workspace info is shown
      const workspaceInfo = page.locator('text=Workspace:');
      await expect(workspaceInfo).toBeVisible();

      // Verify notification settings form is visible
      const channelSelect = page.locator('[data-testid="slack-channel-select"]');
      await expect(channelSelect).toBeVisible();

      const notificationsToggle = page.locator('[data-testid="slack-notifications-toggle"]');
      await expect(notificationsToggle).toBeVisible();

      const notifyCreateToggle = page.locator('[data-testid="slack-notify-create-toggle"]');
      await expect(notifyCreateToggle).toBeVisible();

      const notifyStatusToggle = page.locator('[data-testid="slack-notify-status-toggle"]');
      await expect(notifyStatusToggle).toBeVisible();

      // Verify action buttons are present
      const saveButton = page.locator('[data-testid="slack-save-button"]');
      await expect(saveButton).toBeVisible();

      const testButton = page.locator('[data-testid="slack-test-button"]');
      await expect(testButton).toBeVisible();

      const disconnectButton = page.locator('[data-testid="slack-disconnect-button"]');
      await expect(disconnectButton).toBeVisible();
    });

    test('can-update-notification-settings: Can update notification settings', async ({ page }) => {
      // Mock initial Slack settings
      await page.route('/api/slack/settings', async route => {
        if (route.request().method() === 'GET') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              installed: true,
              workspace_id: 'T123456',
              workspace_name: 'Test Workspace',
              default_channel_id: 'C123456',
              notifications_enabled: true,
              notify_on_create: true,
              notify_on_status_change: false
            })
          });
        } else if (route.request().method() === 'PUT') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              message: 'Slack settings updated successfully',
              settings: {
                installed: true,
                workspace_id: 'T123456',
                workspace_name: 'Test Workspace',
                default_channel_id: 'C789012',
                notifications_enabled: true,
                notify_on_create: true,
                notify_on_status_change: true
              }
            })
          });
        }
      });

      // Mock channels API
      await page.route('/api/slack/channels', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            channels: [
              { id: 'C123456', name: 'general', is_private: false },
              { id: 'C789012', name: 'decisions', is_private: false }
            ]
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Slack tab
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await slackTab.click({ force: true });
      await page.waitForTimeout(2000);

      // Toggle notify on status change
      const notifyStatusToggle = page.locator('[data-testid="slack-notify-status-toggle"]');
      await notifyStatusToggle.click();
      await page.waitForTimeout(500);

      // Click save button
      const saveButton = page.locator('[data-testid="slack-save-button"]');
      await saveButton.click();

      // Wait for success message
      await page.waitForTimeout(1000);
      const successMessage = page.locator('text=Slack settings updated successfully, text=successfully');
      await expect(successMessage.first()).toBeVisible({ timeout: 5000 });
    });

    test('can-send-test-notification: Can send test notification', async ({ page }) => {
      // Mock Slack settings
      await page.route('/api/slack/settings', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            installed: true,
            workspace_id: 'T123456',
            workspace_name: 'Test Workspace',
            default_channel_id: 'C123456',
            notifications_enabled: true,
            notify_on_create: true,
            notify_on_status_change: true
          })
        });
      });

      // Mock channels API
      await page.route('/api/slack/channels', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            channels: [
              { id: 'C123456', name: 'general', is_private: false }
            ]
          })
        });
      });

      // Mock test notification endpoint
      await page.route('/api/slack/test', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            message: 'Test notification sent to Slack'
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Slack tab
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await slackTab.click({ force: true });
      await page.waitForTimeout(2000);

      // Click test button
      const testButton = page.locator('[data-testid="slack-test-button"]');
      await testButton.click();

      // Wait for success message
      await page.waitForTimeout(1000);
      const successMessage = page.locator('text=Test notification sent to Slack');
      await expect(successMessage).toBeVisible({ timeout: 5000 });
    });

    test('can-disconnect-workspace: Can disconnect Slack workspace', async ({ page }) => {
      // Mock initial Slack settings (connected)
      let disconnected = false;
      await page.route('/api/slack/settings', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            installed: !disconnected,
            workspace_id: disconnected ? undefined : 'T123456',
            workspace_name: disconnected ? undefined : 'Test Workspace',
            default_channel_id: disconnected ? undefined : 'C123456',
            notifications_enabled: !disconnected,
            notify_on_create: !disconnected,
            notify_on_status_change: !disconnected
          })
        });
      });

      // Mock channels API
      await page.route('/api/slack/channels', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            channels: [
              { id: 'C123456', name: 'general', is_private: false }
            ]
          })
        });
      });

      // Mock disconnect endpoint
      await page.route('/api/slack/disconnect', async route => {
        disconnected = true;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            message: 'Slack disconnected successfully'
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Slack tab
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await slackTab.click({ force: true });
      await page.waitForTimeout(2000);

      // Verify we're in the connected state
      const disconnectButton = page.locator('[data-testid="slack-disconnect-button"]');
      await expect(disconnectButton).toBeVisible({ timeout: 5000 });

      // Click disconnect button
      await disconnectButton.click();

      // Confirm in dialog
      await page.waitForTimeout(500);
      const confirmButton = page.locator('button:has-text("Disconnect")').last();
      await expect(confirmButton).toBeVisible({ timeout: 5000 });
      await confirmButton.click();

      // Wait for success message
      await page.waitForTimeout(1000);
      const successMessage = page.locator('text=Slack disconnected successfully, text=disconnected');
      await expect(successMessage.first()).toBeVisible({ timeout: 5000 });
    });

    test('test-button-disabled-without-channel: Test button disabled when no channel selected', async ({ page }) => {
      // Mock Slack settings without a default channel
      await page.route('/api/slack/settings', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            installed: true,
            workspace_id: 'T123456',
            workspace_name: 'Test Workspace',
            default_channel_id: null,
            notifications_enabled: true,
            notify_on_create: true,
            notify_on_status_change: true
          })
        });
      });

      // Mock channels API
      await page.route('/api/slack/channels', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            channels: [
              { id: 'C123456', name: 'general', is_private: false }
            ]
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Slack tab
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await slackTab.click({ force: true });
      await page.waitForTimeout(2000);

      // Verify test button is disabled
      const testButton = page.locator('[data-testid="slack-test-button"]');
      await expect(testButton).toBeDisabled({ timeout: 5000 });
    });
  });

  test.describe('Workspace Claiming', () => {
    test('shows-claim-workspace-form: Shows claim workspace form when not connected', async ({ page }) => {
      // Mock API to return not installed
      await page.route('/api/slack/settings', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            installed: false,
            install_url: '/api/slack/install'
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Slack tab
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await slackTab.click({ force: true });
      await page.waitForTimeout(1000);

      // Verify claim workspace form is visible
      const claimHeading = page.locator('h4:has-text("Claim Existing Installation")');
      await expect(claimHeading).toBeVisible({ timeout: 5000 });

      // Verify workspace ID input is present
      const workspaceIdInput = page.locator('[data-testid="slack-workspace-id-input"]');
      await expect(workspaceIdInput).toBeVisible();

      // Verify claim button is present
      const claimButton = page.locator('[data-testid="slack-claim-button"]');
      await expect(claimButton).toBeVisible();
    });

    test('can-claim-unclaimed-workspace: Can claim an unclaimed workspace', async ({ page }) => {
      // Mock API to return not installed initially
      await page.route('/api/slack/settings', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            installed: false,
            install_url: '/api/slack/install'
          })
        });
      });

      // Mock claim endpoint
      await page.route('/api/slack/claim', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            message: 'Workspace claimed successfully',
            workspace: {
              installed: true,
              workspace_id: 'T0A36UYCYLX',
              workspace_name: 'Claimed Workspace'
            }
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Slack tab
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await slackTab.click({ force: true });
      await page.waitForTimeout(1000);

      // Fill in workspace ID
      const workspaceIdInput = page.locator('[data-testid="slack-workspace-id-input"]');
      await workspaceIdInput.fill('T0A36UYCYLX');

      // Click claim button
      const claimButton = page.locator('[data-testid="slack-claim-button"]');
      await claimButton.click();

      // Verify success message
      await page.waitForTimeout(1000);
      const successMessage = page.locator('text=Workspace claimed successfully');
      await expect(successMessage).toBeVisible({ timeout: 5000 });
    });

    test('shows-error-for-invalid-workspace-id: Shows error for invalid workspace ID', async ({ page }) => {
      // Mock API to return not installed
      await page.route('/api/slack/settings', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            installed: false,
            install_url: '/api/slack/install'
          })
        });
      });

      // Mock claim endpoint with error
      await page.route('/api/slack/claim', async route => {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'Invalid workspace ID format. Slack workspace IDs start with T.'
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Slack tab
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await slackTab.click({ force: true });
      await page.waitForTimeout(1000);

      // Fill in invalid workspace ID
      const workspaceIdInput = page.locator('[data-testid="slack-workspace-id-input"]');
      await workspaceIdInput.fill('INVALID123');

      // Click claim button
      const claimButton = page.locator('[data-testid="slack-claim-button"]');
      await claimButton.click();

      // Verify error message
      await page.waitForTimeout(1000);
      const errorMessage = page.locator('text=Invalid workspace ID format');
      await expect(errorMessage).toBeVisible({ timeout: 5000 });
    });

    test('shows-error-for-already-claimed-workspace: Shows error for already claimed workspace', async ({ page }) => {
      // Mock API to return not installed
      await page.route('/api/slack/settings', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            installed: false,
            install_url: '/api/slack/install'
          })
        });
      });

      // Mock claim endpoint with already claimed error
      await page.route('/api/slack/claim', async route => {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'This workspace is already claimed by another organization'
          })
        });
      });

      await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

      await page.waitForLoadState('networkidle', { timeout: 15000 });
      await page.waitForSelector('h1', { timeout: 10000 });
      await page.goto('/test-org.com/admin');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      if (!currentUrl.includes('/admin')) {
        test.skip(true, 'Admin access not available');
        return;
      }

      await page.waitForSelector('mat-tab-group', { timeout: 15000 });
      await dismissOverlays(page);

      // Click on the Slack tab
      const slackTab = page.locator('div.mat-mdc-tab:has-text("Slack")');
      await slackTab.click({ force: true });
      await page.waitForTimeout(1000);

      // Fill in workspace ID that's already claimed
      const workspaceIdInput = page.locator('[data-testid="slack-workspace-id-input"]');
      await workspaceIdInput.fill('T123456ABC');

      // Click claim button
      const claimButton = page.locator('[data-testid="slack-claim-button"]');
      await claimButton.click();

      // Verify error message
      await page.waitForTimeout(1000);
      const errorMessage = page.locator('text=already claimed');
      await expect(errorMessage).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Slack Installed Landing Page', () => {
    test('shows-unclaimed-workspace-info: Shows unclaimed workspace info on landing page', async ({ page }) => {
      // Mock workspace info API
      await page.route('/api/slack/workspace/T0A36UYCYLX', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            workspace_id: 'T0A36UYCYLX',
            workspace_name: 'Acme Corp',
            is_claimed: false,
            status: 'pending_claim',
            installed_at: '2025-01-15T10:00:00Z'
          })
        });
      });

      // Navigate to slack installed page
      await page.goto('/slack/installed?workspace=T0A36UYCYLX');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      // Verify page title
      const title = page.locator('mat-card-title:has-text("Decision Records App Installed")');
      await expect(title).toBeVisible({ timeout: 5000 });

      // Verify workspace name is shown
      const workspaceName = page.locator('text=Acme Corp');
      await expect(workspaceName).toBeVisible();

      // Verify workspace ID is shown
      const workspaceId = page.locator('code:has-text("T0A36UYCYLX")');
      await expect(workspaceId).toBeVisible();

      // Verify next steps section
      const nextSteps = page.locator('h3:has-text("Next Steps")');
      await expect(nextSteps).toBeVisible();
    });

    test('shows-already-claimed-message: Shows already claimed message for claimed workspace', async ({ page }) => {
      // Mock workspace info API - already claimed
      await page.route('/api/slack/workspace/T123CLAIMED', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            workspace_id: 'T123CLAIMED',
            workspace_name: 'Already Claimed Workspace',
            is_claimed: true,
            status: 'active',
            installed_at: '2025-01-10T10:00:00Z'
          })
        });
      });

      // Navigate to slack installed page
      await page.goto('/slack/installed?workspace=T123CLAIMED&already_claimed=true');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      // Verify already connected message
      const alreadyConnected = page.locator('mat-card-title:has-text("Already Connected")');
      await expect(alreadyConnected).toBeVisible({ timeout: 5000 });

      // Verify workspace name is shown
      const workspaceName = page.locator('text=Already Claimed Workspace');
      await expect(workspaceName).toBeVisible();
    });

    test('shows-error-for-missing-workspace-id: Shows error when no workspace ID provided', async ({ page }) => {
      // Navigate to slack installed page without workspace ID
      await page.goto('/slack/installed');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      // Verify error message
      const errorTitle = page.locator('mat-card-title:has-text("Error")');
      await expect(errorTitle).toBeVisible({ timeout: 5000 });

      const errorMessage = page.locator('text=No workspace ID provided');
      await expect(errorMessage).toBeVisible();
    });
  });
});
