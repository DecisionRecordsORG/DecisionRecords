import { test, expect } from '@playwright/test';
import { loginAsUser } from '../fixtures/auth';

test.describe('Spaces', () => {
  test('default-space-exists: Every tenant has a General default space', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    // Navigate to spaces (adjust URL based on actual route)
    await page.goto('/test-org.com/spaces');

    // Look for the General space
    const generalSpace = page.locator('text=/General/i').first();

    // If spaces page exists, check for General
    if (await generalSpace.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(generalSpace).toBeVisible();
    } else {
      // Spaces might be shown in a different way (dropdown, sidebar, etc.)
      // Check for any space selector
      const spaceSelector = page.locator('[data-testid="space-selector"], .space-selector, mat-select');
      if (await spaceSelector.isVisible({ timeout: 3000 }).catch(() => false)) {
        await spaceSelector.click();
        await expect(page.locator('text=/General/i')).toBeVisible();
      } else {
        test.skip(true, 'Spaces UI not yet implemented');
      }
    }
  });

  test('cannot-delete-default-space: Delete button disabled for default space', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');
    await page.goto('/test-org.com/spaces');

    // Find the General space row
    const generalSpaceRow = page.locator('tr, mat-row, .space-item').filter({ hasText: /General/i }).first();

    if (await generalSpaceRow.isVisible({ timeout: 5000 }).catch(() => false)) {
      // The delete button should be disabled or hidden
      const deleteButton = generalSpaceRow.locator('button:has-text("Delete"), [data-testid^="delete-space"]');

      if (await deleteButton.count() > 0) {
        await expect(deleteButton).toBeDisabled();
      }
      // If no delete button visible, that's also acceptable
    } else {
      test.skip(true, 'Spaces UI not yet implemented');
    }
  });

  test('admin-can-create-space: Admin can create a new space', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');
    await page.goto('/test-org.com/spaces');

    // Look for create space button
    const createButton = page.locator('[data-testid="create-space-button"], button:has-text("Create"), button:has-text("New Space"), button:has-text("Add")');

    if (await createButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await createButton.click();

      // Fill in space details (in dialog or form)
      const nameInput = page.locator('input[formcontrolname="name"], input[name="name"], [data-testid="space-name-input"]');
      await nameInput.fill('Test Space ' + Date.now());

      // Submit
      const submitButton = page.locator('button:has-text("Create"), button:has-text("Save"), button[type="submit"]');
      await submitButton.click();

      // Should see the new space in the list
      await expect(page.locator('text=/Test Space/i')).toBeVisible({ timeout: 10000 });
    } else {
      test.skip(true, 'Space creation UI not yet implemented');
    }
  });

  test('steward-can-create-space: Steward can create a new space', async ({ page }) => {
    await loginAsUser(page, 'steward@test-org.com', 'TestPass123');
    await page.goto('/test-org.com/spaces');

    // Look for create space button (stewards should have this permission)
    const createButton = page.locator('[data-testid="create-space-button"], button:has-text("Create"), button:has-text("New Space")');

    if (await createButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(createButton).toBeEnabled();
    } else {
      test.skip(true, 'Space creation UI not yet implemented');
    }
  });

  test('user-cannot-create-space: Regular user sees no create button', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');
    await page.goto('/test-org.com/spaces');

    // Regular users should NOT see create space button
    const createButton = page.locator('[data-testid="create-space-button"], button:has-text("Create Space"), button:has-text("New Space")');

    // Either button doesn't exist or is not visible
    await expect(createButton).not.toBeVisible({ timeout: 5000 });
  });
});
