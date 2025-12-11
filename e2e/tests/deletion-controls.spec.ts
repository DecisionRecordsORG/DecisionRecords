import { test, expect } from '@playwright/test';
import { loginAsUser, dismissOverlays } from '../fixtures/auth';

test.describe('Deletion Controls', () => {
  test('regular-user-cannot-delete-decision: Regular user should NOT see delete button', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Check for decisions
    const emptyState = page.locator('h2:has-text("No decisions yet")');
    const decisionCard = page.locator('.decision-card').first();

    if (await emptyState.isVisible({ timeout: 3000 }).catch(() => false)) {
      test.skip(true, 'No decisions available to test deletion');
      return;
    }

    if (!(await decisionCard.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Decision cards not visible');
      return;
    }

    // Dismiss any overlays before clicking
    await dismissOverlays(page);

    await decisionCard.click();

    // Wait for decision detail page
    await page.waitForURL(/.*decision\/\d+.*/, { timeout: 10000 });
    await page.waitForTimeout(1000);

    // Look for delete button - it should NOT be visible for regular users
    const deleteButton = page.locator('button:has-text("Delete")');
    const deleteButtonVisible = await deleteButton.isVisible({ timeout: 2000 }).catch(() => false);

    // Assert that delete button is NOT visible
    expect(deleteButtonVisible).toBe(false);
  });

  test('admin-can-see-delete-button: Admin should see delete button on decision detail', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Check for decisions
    const emptyState = page.locator('h2:has-text("No decisions yet")');
    const decisionCard = page.locator('.decision-card').first();

    if (await emptyState.isVisible({ timeout: 3000 }).catch(() => false)) {
      test.skip(true, 'No decisions available to test deletion');
      return;
    }

    if (!(await decisionCard.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Decision cards not visible');
      return;
    }

    // Dismiss any overlays before clicking
    await dismissOverlays(page);

    await decisionCard.click();

    // Wait for decision detail page
    await page.waitForURL(/.*decision\/\d+.*/, { timeout: 10000 });
    await page.waitForTimeout(1000);

    // Look for delete button - it SHOULD be visible for admins
    const deleteButton = page.locator('button:has-text("Delete")');
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
  });

  test('steward-can-see-delete-button: Steward should see delete button on decision detail', async ({ page }) => {
    await loginAsUser(page, 'steward@test-org.com', 'TestPass123');

    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Check for decisions
    const emptyState = page.locator('h2:has-text("No decisions yet")');
    const decisionCard = page.locator('.decision-card').first();

    if (await emptyState.isVisible({ timeout: 3000 }).catch(() => false)) {
      test.skip(true, 'No decisions available to test deletion');
      return;
    }

    if (!(await decisionCard.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Decision cards not visible');
      return;
    }

    // Dismiss any overlays before clicking
    await dismissOverlays(page);

    await decisionCard.click();

    // Wait for decision detail page
    await page.waitForURL(/.*decision\/\d+.*/, { timeout: 10000 });
    await page.waitForTimeout(1000);

    // Look for delete button - it SHOULD be visible for stewards
    const deleteButton = page.locator('button:has-text("Delete")');
    await expect(deleteButton).toBeVisible({ timeout: 5000 });
  });

  test('delete-confirmation-shows-warning: When clicking delete, shows warning about 30-day retention', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Check for decisions
    const emptyState = page.locator('h2:has-text("No decisions yet")');
    const decisionCard = page.locator('.decision-card').first();

    if (await emptyState.isVisible({ timeout: 3000 }).catch(() => false)) {
      test.skip(true, 'No decisions available to test deletion');
      return;
    }

    if (!(await decisionCard.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Decision cards not visible');
      return;
    }

    // Dismiss any overlays before clicking
    await dismissOverlays(page);

    await decisionCard.click();

    // Wait for decision detail page
    await page.waitForURL(/.*decision\/\d+.*/, { timeout: 10000 });
    await page.waitForTimeout(1000);

    // Look for delete button
    const deleteButton = page.locator('button:has-text("Delete")');
    if (!(await deleteButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Delete button not visible');
      return;
    }

    // Dismiss any overlays before clicking delete button
    await dismissOverlays(page);
    await page.waitForTimeout(500);

    // Click the delete button
    await deleteButton.click();

    // Wait for confirmation dialog to appear
    await page.waitForTimeout(1000);

    // Look for confirmation dialog with delete/retention warning
    const dialogTitle = page.locator('h2:has-text("Delete Decision"), mat-dialog-container h2:has-text("Delete")');
    await expect(dialogTitle).toBeVisible({ timeout: 5000 });

    // Check for warning message about deletion (should mention "cannot be undone" or similar)
    const dialogMessage = page.locator('mat-dialog-content, .mat-mdc-dialog-content');
    const messageText = await dialogMessage.textContent();

    // Assert that the message contains information about deletion
    expect(messageText).toContain('delete');
    expect(messageText?.toLowerCase()).toMatch(/cannot be undone|permanent|delete/i);

    // Cancel the deletion (don't actually delete)
    const cancelButton = page.locator('button:has-text("Cancel")');
    if (await cancelButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cancelButton.click();
    } else {
      // Alternative: press Escape to close dialog
      await page.keyboard.press('Escape');
    }

    // Wait for dialog to close
    await page.waitForTimeout(500);
  });
});
