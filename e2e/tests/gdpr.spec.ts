import { test, expect } from '@playwright/test';
import { loginAsUser, dismissOverlays } from '../fixtures/auth';

// Test credentials matching global-setup.ts
const TEST_USER_EMAIL = 'user@test-org.com';
const TEST_USER_PASSWORD = 'TestPass123';
const TEST_TENANT = 'test-org.com';

test.describe('GDPR - Profile Privacy & Data Section', () => {
  test('profile-page-shows-privacy-section: Privacy & Data card is visible with expected controls', async ({ page }) => {
    await loginAsUser(page, TEST_USER_EMAIL, TEST_USER_PASSWORD);

    // Navigate to profile page
    await page.goto(`/${TEST_TENANT}/profile`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Dismiss any overlays that might block interaction
    await dismissOverlays(page);

    // Verify "Privacy & Data" card is visible
    const privacyCard = page.locator('.privacy-card');
    await expect(privacyCard).toBeVisible({ timeout: 10000 });

    // Verify the card title
    const cardTitle = privacyCard.locator('mat-card-title:has-text("Privacy & Data")');
    await expect(cardTitle).toBeVisible();

    // Verify "Export My Data" button exists
    const exportButton = page.locator('button:has-text("Export My Data")');
    await expect(exportButton).toBeVisible();

    // Verify privacy preference toggles exist (Analytics, AI Processing, Email Notifications)
    const analyticsToggle = page.locator('mat-slide-toggle:has-text("Analytics")');
    const aiToggle = page.locator('mat-slide-toggle:has-text("AI Processing")');
    const emailToggle = page.locator('mat-slide-toggle:has-text("Email Notifications")');

    await expect(analyticsToggle).toBeVisible({ timeout: 10000 });
    await expect(aiToggle).toBeVisible();
    await expect(emailToggle).toBeVisible();
  });

  test('export-data-button-triggers-download: Clicking Export My Data starts a download', async ({ page }) => {
    await loginAsUser(page, TEST_USER_EMAIL, TEST_USER_PASSWORD);

    // Navigate to profile page
    await page.goto(`/${TEST_TENANT}/profile`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Dismiss any overlays
    await dismissOverlays(page);

    // Wait for the export button to appear
    const exportButton = page.locator('button:has-text("Export My Data")');
    await expect(exportButton).toBeVisible({ timeout: 10000 });

    // Listen for download event before clicking
    const downloadPromise = page.waitForEvent('download', { timeout: 15000 });

    await exportButton.click();

    // Verify that a download was triggered
    const download = await downloadPromise;
    const filename = download.suggestedFilename();
    expect(filename).toMatch(/^data-export-\d{4}-\d{2}-\d{2}\.json$/);

    // Verify success snackbar
    const snackbar = page.locator('simple-snack-bar:has-text("exported"), .mat-mdc-snack-bar-label:has-text("exported")').first();
    await expect(snackbar).toBeVisible({ timeout: 5000 });
  });

  test('consent-toggles-update-preferences: Toggling consent shows appropriate snackbar', async ({ page }) => {
    await loginAsUser(page, TEST_USER_EMAIL, TEST_USER_PASSWORD);

    // Navigate to profile page
    await page.goto(`/${TEST_TENANT}/profile`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Dismiss any overlays
    await dismissOverlays(page);

    // Wait for consent toggles to load (loading spinner disappears)
    const analyticsToggle = page.locator('mat-slide-toggle:has-text("Analytics")');
    await expect(analyticsToggle).toBeVisible({ timeout: 10000 });

    // Get the current state of the analytics toggle
    const isCurrentlyChecked = await analyticsToggle.locator('input[type="checkbox"]').isChecked();

    // Click the analytics toggle to change its state
    await analyticsToggle.click();

    // Verify the appropriate snackbar message appears
    const expectedMessage = isCurrentlyChecked ? 'Consent withdrawn' : 'Consent granted';
    const snackbar = page.locator(`simple-snack-bar:has-text("${expectedMessage}"), .mat-mdc-snack-bar-label:has-text("${expectedMessage}")`).first();
    await expect(snackbar).toBeVisible({ timeout: 5000 });

    // Wait for snackbar to dismiss
    await page.waitForTimeout(2500);

    // Toggle it back to restore original state
    await analyticsToggle.click();

    const revertMessage = isCurrentlyChecked ? 'Consent granted' : 'Consent withdrawn';
    const revertSnackbar = page.locator(`simple-snack-bar:has-text("${revertMessage}"), .mat-mdc-snack-bar-label:has-text("${revertMessage}")`).first();
    await expect(revertSnackbar).toBeVisible({ timeout: 5000 });
  });
});

test.describe('GDPR - Account Deletion Flow', () => {
  test('delete-account-shows-confirmation-dialog: Clicking Delete My Account opens dialog with warning', async ({ page }) => {
    await loginAsUser(page, TEST_USER_EMAIL, TEST_USER_PASSWORD);

    // Navigate to profile page
    await page.goto(`/${TEST_TENANT}/profile`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Dismiss any overlays
    await dismissOverlays(page);

    // Scroll down to find the Delete Account section
    const deleteButton = page.locator('button:has-text("Delete My Account")');
    await deleteButton.scrollIntoViewIfNeeded();
    await expect(deleteButton).toBeVisible({ timeout: 10000 });

    // Click "Delete My Account" button
    await deleteButton.click();

    // Verify confirmation dialog appears
    const dialog = page.locator('mat-dialog-container');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Verify dialog title
    const dialogTitle = dialog.locator('h2:has-text("Delete Your Account")');
    await expect(dialogTitle).toBeVisible();

    // Verify dialog contains warning text about 7-day grace period
    const dialogMessage = dialog.locator('mat-dialog-content');
    await expect(dialogMessage).toContainText('7 days');
    await expect(dialogMessage).toContainText('Former Member');

    // Verify "Keep Account" cancel button exists
    const keepAccountButton = dialog.locator('button:has-text("Keep Account")');
    await expect(keepAccountButton).toBeVisible();

    // Click "Keep Account" to cancel
    await keepAccountButton.click();

    // Verify dialog closes
    await expect(dialog).not.toBeVisible({ timeout: 5000 });
  });

  test('delete-account-request-shows-pending-banner: Confirming deletion shows pending banner', async ({ page }) => {
    await loginAsUser(page, TEST_USER_EMAIL, TEST_USER_PASSWORD);

    // Navigate to profile page
    await page.goto(`/${TEST_TENANT}/profile`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Dismiss any overlays
    await dismissOverlays(page);

    // Scroll down and click "Delete My Account"
    const deleteButton = page.locator('button:has-text("Delete My Account")');
    await deleteButton.scrollIntoViewIfNeeded();
    await expect(deleteButton).toBeVisible({ timeout: 10000 });
    await deleteButton.click();

    // Wait for confirmation dialog
    const dialog = page.locator('mat-dialog-container');
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Click "Delete My Account" confirm button in the dialog
    const confirmButton = dialog.locator('button:has-text("Delete My Account")');
    await confirmButton.click();

    // Wait for dialog to close and API to complete
    await expect(dialog).not.toBeVisible({ timeout: 10000 });

    // Verify pending deletion banner appears
    const deletionBanner = page.locator('.deletion-pending-banner');
    await expect(deletionBanner).toBeVisible({ timeout: 10000 });

    // Verify banner contains expected text
    await expect(deletionBanner).toContainText('Account deletion scheduled');
    await expect(deletionBanner).toContainText('permanently deleted');

    // Verify "Cancel Deletion" button is visible in the banner
    const cancelDeletionButton = deletionBanner.locator('button:has-text("Cancel Deletion")');
    await expect(cancelDeletionButton).toBeVisible();

    // Verify snackbar confirmation
    const snackbar = page.locator('simple-snack-bar:has-text("deletion scheduled"), .mat-mdc-snack-bar-label:has-text("deletion scheduled")').first();
    await expect(snackbar).toBeVisible({ timeout: 5000 });
  });

  test('cancel-deletion-removes-banner: Cancelling deletion restores original state', async ({ page }) => {
    // This test depends on the previous test having requested deletion.
    // We first ensure deletion is requested, then cancel it.
    await loginAsUser(page, TEST_USER_EMAIL, TEST_USER_PASSWORD);

    // Navigate to profile page
    await page.goto(`/${TEST_TENANT}/profile`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Dismiss any overlays
    await dismissOverlays(page);

    // Check if deletion is already pending (from previous test)
    const deletionBanner = page.locator('.deletion-pending-banner');
    const bannerVisible = await deletionBanner.isVisible({ timeout: 5000 }).catch(() => false);

    if (!bannerVisible) {
      // Request deletion first so we can test cancellation
      const deleteButton = page.locator('button:has-text("Delete My Account")');
      await deleteButton.scrollIntoViewIfNeeded();

      if (!(await deleteButton.isEnabled())) {
        test.skip(true, 'Delete button is not enabled');
        return;
      }

      await deleteButton.click();

      const dialog = page.locator('mat-dialog-container');
      await expect(dialog).toBeVisible({ timeout: 5000 });

      const confirmButton = dialog.locator('button:has-text("Delete My Account")');
      await confirmButton.click();

      await expect(dialog).not.toBeVisible({ timeout: 10000 });
      await expect(deletionBanner).toBeVisible({ timeout: 10000 });

      // Wait for snackbar to dismiss
      await page.waitForTimeout(3000);
    }

    // Now cancel the deletion
    const cancelButton = deletionBanner.locator('button:has-text("Cancel Deletion")');
    await expect(cancelButton).toBeVisible();
    await cancelButton.click();

    // Verify banner disappears
    await expect(deletionBanner).not.toBeVisible({ timeout: 10000 });

    // Verify cancellation snackbar
    const snackbar = page.locator('simple-snack-bar:has-text("deletion cancelled"), .mat-mdc-snack-bar-label:has-text("deletion cancelled")').first();
    await expect(snackbar).toBeVisible({ timeout: 5000 });

    // Verify "Delete My Account" button is re-enabled
    const deleteButton = page.locator('.delete-account-card button:has-text("Delete My Account")');
    await deleteButton.scrollIntoViewIfNeeded();
    await expect(deleteButton).toBeVisible();
    await expect(deleteButton).toBeEnabled();
  });
});

test.describe('GDPR - Cookie Consent Banner', () => {
  test('cookie-consent-banner-shows-for-new-visitors: Banner appears when no consent stored', async ({ page }) => {
    // Clear localStorage to simulate a new visitor
    await page.goto('/');
    await page.evaluate(() => localStorage.removeItem('dr_cookie_consent'));

    // Navigate to a page (reload after clearing)
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);

    // Verify cookie consent banner is visible
    const banner = page.locator('.cookie-consent-banner');
    await expect(banner).toBeVisible({ timeout: 5000 });

    // Verify banner contains expected text
    await expect(banner).toContainText('Cookie Notice');

    // Verify Accept and Reject buttons exist
    const acceptButton = banner.locator('button:has-text("Accept")');
    const rejectButton = banner.locator('button:has-text("Reject")');
    await expect(acceptButton).toBeVisible();
    await expect(rejectButton).toBeVisible();
  });

  test('accepting-cookies-hides-banner: Clicking Accept hides banner and stores consent', async ({ page }) => {
    // Clear localStorage to simulate a new visitor
    await page.goto('/');
    await page.evaluate(() => localStorage.removeItem('dr_cookie_consent'));

    // Reload to show banner
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);

    // Verify banner is visible
    const banner = page.locator('.cookie-consent-banner');
    await expect(banner).toBeVisible({ timeout: 5000 });

    // Click Accept
    const acceptButton = banner.locator('button:has-text("Accept")');
    await acceptButton.click();

    // Verify banner disappears
    await expect(banner).not.toBeVisible({ timeout: 5000 });

    // Verify localStorage has consent=accepted
    const consentValue = await page.evaluate(() => localStorage.getItem('dr_cookie_consent'));
    expect(consentValue).toBe('accepted');
  });

  test('rejecting-cookies-hides-banner: Clicking Reject hides banner and stores rejection', async ({ page }) => {
    // Clear localStorage to simulate a new visitor
    await page.goto('/');
    await page.evaluate(() => localStorage.removeItem('dr_cookie_consent'));

    // Reload to show banner
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);

    // Verify banner is visible
    const banner = page.locator('.cookie-consent-banner');
    await expect(banner).toBeVisible({ timeout: 5000 });

    // Click Reject
    const rejectButton = banner.locator('button:has-text("Reject")');
    await rejectButton.click();

    // Verify banner disappears
    await expect(banner).not.toBeVisible({ timeout: 5000 });

    // Verify localStorage has consent=rejected
    const consentValue = await page.evaluate(() => localStorage.getItem('dr_cookie_consent'));
    expect(consentValue).toBe('rejected');
  });

  test('cookie-consent-banner-hidden-when-already-accepted: Banner does not show if consent exists', async ({ page }) => {
    // Set consent in localStorage before navigating
    await page.goto('/');
    await page.evaluate(() => localStorage.setItem('dr_cookie_consent', 'accepted'));

    // Reload the page
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);

    // Verify banner is NOT visible
    const banner = page.locator('.cookie-consent-banner');
    await expect(banner).not.toBeVisible({ timeout: 3000 });
  });
});
