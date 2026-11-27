import { test, expect } from '@playwright/test';
import * as fs from 'fs';
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

    // "Email notifications" is in every edition. "Analytics" and "AI Processing"
    // are shown only where the installation has the feature (Enterprise).
    const emailToggle = page.locator('[data-testid="preference-email"]');
    await expect(emailToggle).toBeVisible({ timeout: 10000 });

    const features = await (await page.request.get('/api/features')).json();
    const analyticsToggle = page.locator('[data-testid="preference-analytics"]');
    const aiToggle = page.locator('[data-testid="preference-ai"]');
    if (features.posthog_analytics) {
      await expect(analyticsToggle).toBeVisible();
    } else {
      await expect(analyticsToggle).toHaveCount(0);
    }
    if (features.ai_features) {
      await expect(aiToggle).toBeVisible();
    } else {
      await expect(aiToggle).toHaveCount(0);
    }
  });

  test('can-correct-own-name: A person corrects their own name on the profile page', async ({ page }) => {
    await loginAsUser(page, TEST_USER_EMAIL, TEST_USER_PASSWORD);
    await page.goto(`/${TEST_TENANT}/profile`);
    await page.waitForLoadState('networkidle');
    await dismissOverlays(page);

    const before = (await page.locator('[data-testid="profile-name"]').textContent())?.trim() || '';
    const [firstBefore, ...restBefore] = before.split(' ');

    await page.click('[data-testid="profile-name-edit"]');
    await page.fill('[data-testid="profile-first-name"]', 'Corrected');
    await page.fill('[data-testid="profile-last-name"]', 'Name');
    await page.click('[data-testid="profile-name-save"]');

    await expect(page.locator('[data-testid="profile-name"]')).toHaveText('Corrected Name', { timeout: 10000 });
    const me = await (await page.request.get('/api/user/me')).json();
    expect(me.name).toBe('Corrected Name');
    expect(me.email).toBe(TEST_USER_EMAIL);

    // An empty name is refused in the form
    await page.click('[data-testid="profile-name-edit"]');
    await page.fill('[data-testid="profile-first-name"]', '');
    await page.fill('[data-testid="profile-last-name"]', '');
    await page.click('[data-testid="profile-name-save"]');
    await expect(page.locator('[data-testid="profile-name-error"]')).toHaveText('Enter your name.');
    await page.click('[data-testid="profile-name-cancel"]');

    // Put the name back for the tests that follow
    await page.click('[data-testid="profile-name-edit"]');
    await page.fill('[data-testid="profile-first-name"]', firstBefore || 'Test');
    await page.fill('[data-testid="profile-last-name"]', restBefore.join(' ') || 'User');
    await page.click('[data-testid="profile-name-save"]');
    await expect(page.locator('[data-testid="profile-name"]')).toHaveText(before || 'Test User', { timeout: 10000 });
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

  test('export-file-holds-what-is-published: the downloaded file has account details, decisions, comments, activity and consents', async ({ page }) => {
    await loginAsUser(page, TEST_USER_EMAIL, TEST_USER_PASSWORD);
    await page.goto(`/${TEST_TENANT}/profile`);
    await dismissOverlays(page);

    const exportButton = page.locator('button:has-text("Export My Data")');
    await expect(exportButton).toBeVisible({ timeout: 15000 });
    const downloadPromise = page.waitForEvent('download', { timeout: 15000 });
    await exportButton.click();
    const download = await downloadPromise;

    const path = await download.path();
    const data = JSON.parse(fs.readFileSync(path, 'utf-8'));

    // What the published text lists
    expect(data.data_subject.email).toBe(TEST_USER_EMAIL);
    for (const section of ['decisions_authored', 'comments', 'audit_trail', 'login_history', 'consents', 'inquiries']) {
      expect(Array.isArray(data[section]), section).toBeTruthy();
    }
    // The person signed in a moment ago, so their activity is there
    expect(data.login_history.length).toBeGreaterThan(0);
    // Nobody else's account is in the file
    const text = JSON.stringify(data);
    expect(text).not.toContain('admin@test-org.com');
    expect(text).not.toContain('steward@test-org.com');
    // Nothing that signs in
    expect(text).not.toContain('password_hash');
    expect(text).not.toContain('public_key');
  });

  test('consent-toggles-update-preferences: Switching a privacy preference stores it and says so', async ({ page }) => {
    await loginAsUser(page, TEST_USER_EMAIL, TEST_USER_PASSWORD);

    // Navigate to profile page
    await page.goto(`/${TEST_TENANT}/profile`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Dismiss any overlays
    await dismissOverlays(page);

    // "Email notifications" is the switch every edition has
    const emailSwitch = page.locator('[data-testid="preference-email"] button[role="switch"]');
    await expect(emailSwitch).toBeVisible({ timeout: 10000 });

    const wasOn = (await emailSwitch.getAttribute('aria-checked')) === 'true';

    await emailSwitch.click();

    const expectedMessage = wasOn ? 'Switched off' : 'Switched on';
    const snackbar = page.locator(`simple-snack-bar:has-text("${expectedMessage}"), .mat-mdc-snack-bar-label:has-text("${expectedMessage}")`).first();
    await expect(snackbar).toBeVisible({ timeout: 5000 });
    await expect(emailSwitch).toHaveAttribute('aria-checked', wasOn ? 'false' : 'true');

    // The choice is stored on the account
    const stored = await (await page.request.get('/api/user/consents')).json();
    expect(stored.email_notifications.granted).toBe(!wasOn);

    // Wait for snackbar to dismiss
    await page.waitForTimeout(2500);

    // Put it back
    await emailSwitch.click();

    const revertMessage = wasOn ? 'Switched on' : 'Switched off';
    const revertSnackbar = page.locator(`simple-snack-bar:has-text("${revertMessage}"), .mat-mdc-snack-bar-label:has-text("${revertMessage}")`).first();
    await expect(revertSnackbar).toBeVisible({ timeout: 5000 });
  });
});

test.describe('GDPR - Organisation data export', () => {
  test('organisation-export-downloads-a-zip: An administrator downloads the organisation export from Organisation settings', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');
    await page.goto(`/${TEST_TENANT}/admin?tab=data-export`);
    await page.waitForLoadState('networkidle');
    await dismissOverlays(page);

    const card = page.locator('[data-testid="organisation-export-card"]');
    await expect(card).toBeVisible({ timeout: 10000 });
    await expect(card).toContainText('Only administrators can export.');

    const downloadPromise = page.waitForEvent('download', { timeout: 15000 });
    await page.click('[data-testid="organisation-export-button"]');
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(new RegExp(`^decision-records-${TEST_TENANT.replace('.', '\\.')}-\\d{8}\\.zip$`));
    const path = await download.path();
    // A ZIP file starts with "PK"
    expect(fs.readFileSync(path!).subarray(0, 2).toString()).toBe('PK');
  });

  test('organisation-export-refused-for-members: A member who is not an administrator is refused', async ({ page }) => {
    await loginAsUser(page, TEST_USER_EMAIL, TEST_USER_PASSWORD);
    const csrf = (await (await page.request.get('/api/auth/csrf-token')).json()).csrf_token;
    const response = await page.request.post('/api/tenant/export', { headers: { 'X-CSRF-Token': csrf } });
    expect(response.status()).toBe(403);
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
    await expect(banner).toContainText('Usage statistics');
    await expect(banner).toContainText('never the text you clicked or typed');
    await expect(banner.locator('[data-testid="analytics-notice-privacy"]'))
      .toHaveAttribute('href', 'https://decisionrecords.org/privacy');

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
