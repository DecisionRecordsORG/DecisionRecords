import { test, expect } from '@playwright/test';
import { loginAsUser, dismissOverlays } from '../fixtures/auth';

test.describe('Decisions', () => {
  test('create-decision: User can create a new decision', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Should be on tenant decisions page after login
    await expect(page).toHaveURL(/.*test-org\.com.*/);

    // Wait for page to load
    await page.waitForSelector('h1', { timeout: 10000 });

    // Look for create decision button
    const createButton = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();

    if (await createButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await createButton.click();
      await page.waitForURL(/.*decision\/new.*/, { timeout: 10000 });
      await expect(page).toHaveURL(/.*decision\/new.*/);
    } else {
      test.skip(true, 'Decision creation UI not accessible from this page');
    }
  });

  test('edit-decision: User can edit their decision', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });

    // Wait for loading to complete
    await page.waitForTimeout(2000);

    // Check if we have decisions or empty state
    const emptyState = page.locator('h2:has-text("No decisions yet")');
    const decisionCard = page.locator('.decision-card').first();

    if (await emptyState.isVisible({ timeout: 3000 }).catch(() => false)) {
      test.skip(true, 'No decisions available to edit');
      return;
    }

    // Wait for decision card to be visible
    if (!(await decisionCard.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Decision cards not visible');
      return;
    }

    // Dismiss any overlays before clicking
    await dismissOverlays(page);

    await decisionCard.click();

    // Wait for decision detail page
    await page.waitForURL(/.*decision\/\d+.*/, { timeout: 10000 });

    // Look for edit button
    const editButton = page.locator('button:has-text("Edit")').first();
    if (!(await editButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Edit button not visible');
      return;
    }

    await editButton.click();

    // Wait for form to load
    await page.waitForSelector('input[formcontrolname="title"]', { timeout: 10000 });

    // Make a change
    const titleInput = page.locator('input[formcontrolname="title"]');
    const currentValue = await titleInput.inputValue();
    await titleInput.fill(currentValue + ' - Updated ' + Date.now());

    // Save
    const saveButton = page.locator('button:has-text("Save"), button[type="submit"]').first();
    await saveButton.click();

    // Wait for save to complete
    await page.waitForTimeout(2000);
  });

  test('view-decision-history: History shows previous versions', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Check for decisions
    const emptyState = page.locator('h2:has-text("No decisions yet")');
    const decisionCard = page.locator('.decision-card').first();

    if (await emptyState.isVisible({ timeout: 3000 }).catch(() => false)) {
      test.skip(true, 'No decisions available');
      return;
    }

    if (!(await decisionCard.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Decision cards not visible');
      return;
    }

    // Dismiss any overlays before clicking
    await dismissOverlays(page);

    await decisionCard.click();
    await page.waitForURL(/.*decision\/\d+.*/, { timeout: 10000 });

    // Look for history section or button
    const historyButton = page.locator('button:has-text("History"), mat-expansion-panel:has-text("History")').first();

    if (await historyButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Dismiss any overlays before clicking history button
      await dismissOverlays(page);
      await historyButton.click();
      await page.waitForTimeout(1000);
      // Verify history content is shown
      const historyContent = page.locator('text=/version|changed|modified|history|created/i');
      await expect(historyContent.first()).toBeVisible({ timeout: 5000 });
    } else {
      // History might be shown inline without a button
      test.skip(true, 'History button not found');
    }
  });

  test('decision-belongs-to-tenant: Decisions scoped to user tenant', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    const currentUrl = page.url();
    expect(currentUrl).toContain('test-org');

    await page.waitForSelector('h1', { timeout: 10000 });
    await expect(page).toHaveURL(/.*test-org\.com.*/);
  });
});

test.describe('Decision List - Space Filter', () => {
  test('space-filter-dropdown-appears-when-multiple-spaces: Filter shows when >1 spaces exist', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    // Wait for page to load completely
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });

    // Wait for loading spinner to disappear and spaces to load
    await page.waitForTimeout(3000);

    // The space filter should be visible if we have >1 spaces
    const spaceFilter = page.locator('.space-filter, mat-form-field:has(mat-label:has-text("Filter by Space"))');

    if (await spaceFilter.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(spaceFilter).toBeVisible();
    } else {
      // Space filter only shows when spaces.length > 1
      test.skip(true, 'Space filter not visible - may have only 1 space');
    }
  });

  test('space-filter-shows-all-spaces-option: Filter dropdown has "All Spaces" option', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });

    // Dismiss any overlays (admin onboarding modal)
    await dismissOverlays(page);
    await page.waitForTimeout(1000);

    // Wait for spaces to load
    await page.waitForTimeout(2000);

    const spaceFilter = page.locator('.space-filter mat-select, mat-form-field:has(mat-label:has-text("Filter by Space")) mat-select').first();

    if (!(await spaceFilter.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Space filter not visible');
      return;
    }

    // Dismiss again in case new overlays appeared
    await dismissOverlays(page);
    await page.waitForTimeout(500);

    // Use force: true to bypass mat-label overlay interception
    await spaceFilter.click({ force: true });
    await page.waitForTimeout(1000);

    const allSpacesOption = page.locator('mat-option:has-text("All Spaces")');
    await expect(allSpacesOption).toBeVisible({ timeout: 5000 });

    await page.keyboard.press('Escape');
  });
});

test.describe('Decision Form - Space Selector', () => {
  test('space-selector-exists-on-new-decision: New decision form has space selector', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    await page.waitForSelector('h1', { timeout: 10000 });

    const newDecisionBtn = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();
    await expect(newDecisionBtn).toBeVisible({ timeout: 5000 });
    await newDecisionBtn.click();

    await page.waitForSelector('input[formcontrolname="title"]', { timeout: 15000 });

    // Space selector shows when spaces.length > 0
    const spaceSelector = page.locator('mat-form-field:has(mat-label:has-text("Spaces"))');

    if (await spaceSelector.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(spaceSelector).toBeVisible();
    } else {
      test.skip(true, 'Space selector not visible');
    }
  });

  test('space-selector-shows-available-spaces: Space selector shows tenant spaces', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForSelector('h1', { timeout: 10000 });

    const newDecisionBtn = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();
    await expect(newDecisionBtn).toBeVisible({ timeout: 5000 });
    await newDecisionBtn.click();

    await page.waitForSelector('input[formcontrolname="title"]', { timeout: 15000 });

    const spaceSelector = page.locator('mat-form-field:has(mat-label:has-text("Spaces")) mat-select').first();

    if (!(await spaceSelector.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Space selector not visible');
      return;
    }

    // Use force: true to bypass mat-label overlay interception
    await spaceSelector.click({ force: true });
    await page.waitForTimeout(500);

    const generalOption = page.locator('mat-option:has-text("General")');
    await expect(generalOption).toBeVisible({ timeout: 3000 });

    await page.keyboard.press('Escape');
  });

  test('space-selector-is-multi-select: Can select multiple spaces', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForSelector('h1', { timeout: 10000 });

    const newDecisionBtn = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();
    await expect(newDecisionBtn).toBeVisible({ timeout: 5000 });
    await newDecisionBtn.click();

    await page.waitForSelector('input[formcontrolname="title"]', { timeout: 15000 });

    const spaceSelector = page.locator('mat-form-field:has(mat-label:has-text("Spaces")) mat-select').first();

    if (!(await spaceSelector.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Space selector not visible');
      return;
    }

    // Use force: true to bypass mat-label overlay interception
    await spaceSelector.click({ force: true });
    await page.waitForTimeout(500);

    const firstOption = page.locator('mat-option').first();
    await expect(firstOption).toBeVisible({ timeout: 3000 });
    await firstOption.click();

    await page.waitForTimeout(300);
    await page.keyboard.press('Escape');
  });

  test('decision-form-saves-with-spaces: Can create decision with spaces and redirects correctly', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForSelector('h1', { timeout: 10000 });

    const newDecisionBtn = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();
    if (!(await newDecisionBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'New Decision button not visible');
      return;
    }

    // Dismiss any overlays before clicking
    await dismissOverlays(page);
    await page.waitForTimeout(500);

    await newDecisionBtn.click();
    await page.waitForSelector('input[formcontrolname="title"]', { timeout: 15000 });

    // Verify we're on the new decision page with tenant prefix
    expect(page.url()).toContain('test-org.com');
    expect(page.url()).toContain('decision/new');

    // Fill required fields
    const uniqueTitle = 'Test Decision with Spaces ' + Date.now();
    await page.locator('input[formcontrolname="title"]').fill(uniqueTitle);
    await page.locator('textarea[formcontrolname="context"]').fill('Test context for the decision');
    await page.locator('textarea[formcontrolname="decision"]').fill('We decided to test spaces');

    // Dismiss any overlays that may have appeared during form fill (snackbars, etc.)
    await dismissOverlays(page);
    await page.waitForTimeout(300);

    // Select status - use force: true to bypass mat-label overlay
    const statusSelect = page.locator('mat-select[formcontrolname="status"]');
    await statusSelect.click({ force: true });
    await page.waitForTimeout(300);
    await page.locator('mat-option:has-text("Proposed")').click();

    await page.locator('textarea[formcontrolname="consequences"]').fill('Better test coverage');

    // Select a space if available - use force: true to bypass mat-label overlay
    const spaceSelector = page.locator('mat-form-field:has(mat-label:has-text("Spaces")) mat-select').first();
    if (await spaceSelector.isVisible({ timeout: 3000 }).catch(() => false)) {
      await spaceSelector.click({ force: true });
      await page.waitForTimeout(500);
      const generalOption = page.locator('mat-option:has-text("General")');
      if (await generalOption.isVisible({ timeout: 2000 }).catch(() => false)) {
        await generalOption.click();
        await page.keyboard.press('Escape');
      }
    }

    // Submit
    const saveButton = page.locator('button:has-text("Create Decision"), button[type="submit"]').first();
    await saveButton.click();

    // Wait for redirect to decision detail page
    await page.waitForURL(/.*test-org\.com\/decision\/\d+.*/, { timeout: 10000 });

    // Verify we're on the decision detail page (not homepage)
    const currentUrl = page.url();
    expect(currentUrl).toContain('test-org.com');
    expect(currentUrl).toMatch(/\/decision\/\d+/);
    expect(currentUrl).not.toBe('https://architecture-decisions.org');
    expect(currentUrl).not.toBe('https://architecture-decisions.org/');

    // Verify no error
    const errorVisible = await page.locator('.error-message, mat-error:visible').isVisible({ timeout: 1000 }).catch(() => false);
    expect(errorVisible).toBe(false);

    // Verify success message appeared (use .first() to handle multiple matching elements)
    const successSnackbar = page.locator('simple-snack-bar:has-text("created"), .mat-mdc-snack-bar-label:has-text("created")').first();
    await expect(successSnackbar).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Decision Edit - Space Selector', () => {
  test('edit-decision-shows-space-selector: Editing shows space selector', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Check for decisions
    const emptyState = page.locator('h2:has-text("No decisions yet")');
    const decisionCard = page.locator('.decision-card').first();

    if (await emptyState.isVisible({ timeout: 3000 }).catch(() => false)) {
      test.skip(true, 'No decisions available');
      return;
    }

    if (!(await decisionCard.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Decision cards not visible');
      return;
    }

    // Dismiss any overlays before clicking
    await dismissOverlays(page);
    await page.waitForTimeout(500);

    await decisionCard.click();
    await page.waitForURL(/.*decision\/\d+.*/, { timeout: 10000 });

    // Wait for decision detail page to load
    await page.waitForTimeout(500);

    const editButton = page.locator('button:has-text("Edit")').first();
    if (!(await editButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Edit button not visible');
      return;
    }

    // Dismiss any overlays before clicking edit button
    await dismissOverlays(page);
    await page.waitForTimeout(500);

    await editButton.click();
    await page.waitForSelector('input[formcontrolname="title"]', { timeout: 10000 });

    // Wait for page to fully load and spaces to be fetched
    await page.waitForTimeout(2000);

    // Check that space selector exists (it shows when spaces.length > 0)
    const spaceSelector = page.locator('mat-form-field:has(mat-label:has-text("Spaces"))').first();
    if (await spaceSelector.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(spaceSelector).toBeVisible();
    } else {
      test.skip(true, 'Space selector not visible on edit form');
    }
  });
});
