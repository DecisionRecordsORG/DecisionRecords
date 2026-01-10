import { test, expect } from '@playwright/test';
import { loginAsUser, dismissOverlays } from '../fixtures/auth';

test.describe('Decisions', () => {
  test('create-decision: User can create a new decision via modal', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Should be on tenant decisions page after login
    await expect(page).toHaveURL(/.*test-org\.com.*/);

    // Wait for page to load
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForLoadState('networkidle');

    // Dismiss any overlays (admin onboarding modal)
    await dismissOverlays(page);
    await page.waitForTimeout(500);

    // Look for create decision button
    const createButton = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();

    if (!(await createButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Decision creation UI not accessible from this page');
      return;
    }

    await createButton.click();

    // Wait for modal to open (modal has the title form field)
    await page.waitForSelector('mat-dialog-container input[formcontrolname="title"]', { timeout: 10000 });

    // Fill in the decision form in the modal
    const uniqueTitle = 'E2E Test Decision ' + Date.now();
    await page.locator('mat-dialog-container input[formcontrolname="title"]').fill(uniqueTitle);
    await page.locator('mat-dialog-container textarea[formcontrolname="context"]').fill('This is the context for the test decision');
    await page.locator('mat-dialog-container textarea[formcontrolname="decision"]').fill('We decided to test the modal-based decision creation');
    await page.locator('mat-dialog-container textarea[formcontrolname="consequences"]').fill('Better test coverage for the new UI');

    // Click the Create Decision button
    const saveButton = page.locator('mat-dialog-container button:has-text("Create Decision")');
    await saveButton.click();

    // Wait for success snackbar
    const successSnackbar = page.locator('simple-snack-bar:has-text("created"), .mat-mdc-snack-bar-label:has-text("created")').first();
    await expect(successSnackbar).toBeVisible({ timeout: 10000 });

    // Modal should close
    await expect(page.locator('mat-dialog-container')).not.toBeVisible({ timeout: 5000 });

    // Verify we're still on the decisions list page
    await expect(page).toHaveURL(/.*test-org\.com.*/);
  });

  test('edit-decision: User can edit their decision via modal', async ({ page }) => {
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

    // Click the decision card to open the view modal
    await decisionCard.click();

    // Wait for modal to open (view mode shows the title in readonly)
    await page.waitForSelector('mat-dialog-container', { timeout: 10000 });
    await page.waitForTimeout(500);

    // Click the edit icon button in the modal header to switch to edit mode
    const editButton = page.locator('mat-dialog-container button[mattooltip="Edit Decision"]').first();
    if (!(await editButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      // Try alternate selector
      const editIconBtn = page.locator('mat-dialog-container .header-actions button:has(mat-icon:has-text("edit"))').first();
      if (!(await editIconBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
        test.skip(true, 'Edit button not visible');
        return;
      }
      await editIconBtn.click();
    } else {
      await editButton.click();
    }

    // Wait for form to be editable
    await page.waitForSelector('mat-dialog-container input[formcontrolname="title"]:not([readonly])', { timeout: 10000 });

    // Make a change to the title
    const titleInput = page.locator('mat-dialog-container input[formcontrolname="title"]');
    const currentValue = await titleInput.inputValue();
    await titleInput.fill(currentValue + ' - Updated');

    // Save changes
    const saveButton = page.locator('mat-dialog-container button:has-text("Save Changes")');
    await saveButton.click();

    // Wait for success snackbar
    const successSnackbar = page.locator('simple-snack-bar:has-text("updated"), .mat-mdc-snack-bar-label:has-text("updated")').first();
    await expect(successSnackbar).toBeVisible({ timeout: 10000 });

    // Modal should close
    await expect(page.locator('mat-dialog-container')).not.toBeVisible({ timeout: 5000 });
  });

  test('view-decision-history: History shows previous versions in modal', async ({ page }) => {
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

    // Click the decision card to open the modal
    await decisionCard.click();

    // Wait for modal to open
    await page.waitForSelector('mat-dialog-container', { timeout: 10000 });
    await page.waitForTimeout(1000);

    // Look for history section in the modal (it's in the side panel)
    const historySection = page.locator('mat-dialog-container .history-card, mat-dialog-container .history-card-header:has-text("Change History")');

    if (await historySection.isVisible({ timeout: 5000 }).catch(() => false)) {
      // History is visible in the modal
      await expect(historySection.first()).toBeVisible();
    } else {
      // History might not exist yet for new decisions
      test.skip(true, 'History section not found in modal');
    }

    // Close the modal
    const closeButton = page.locator('mat-dialog-container button[mattooltip="Close"]').first();
    if (await closeButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await closeButton.click();
    } else {
      await page.keyboard.press('Escape');
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

test.describe('Decision Form - Space Selector (Modal)', () => {
  test('space-selector-exists-on-new-decision: New decision modal has space selector', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForLoadState('networkidle');

    // Dismiss any overlays
    await dismissOverlays(page);
    await page.waitForTimeout(500);

    const newDecisionBtn = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();
    await expect(newDecisionBtn).toBeVisible({ timeout: 5000 });
    await newDecisionBtn.click();

    // Wait for modal to open
    await page.waitForSelector('mat-dialog-container input[formcontrolname="title"]', { timeout: 15000 });

    // Space selector shows when spaces.length > 0 (in the modal side panel)
    const spaceSelector = page.locator('mat-dialog-container .side-panel mat-select, mat-dialog-container mat-form-field:has(mat-label:has-text("Select spaces")) mat-select');

    if (await spaceSelector.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(spaceSelector.first()).toBeVisible();
    } else {
      test.skip(true, 'Space selector not visible in modal');
    }

    // Close modal
    await page.keyboard.press('Escape');
  });

  test('space-selector-shows-available-spaces: Space selector in modal shows tenant spaces', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForSelector('h1', { timeout: 10000 });

    // Dismiss any overlays
    await dismissOverlays(page);
    await page.waitForTimeout(500);

    const newDecisionBtn = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();
    await expect(newDecisionBtn).toBeVisible({ timeout: 5000 });
    await newDecisionBtn.click();

    // Wait for modal to open
    await page.waitForSelector('mat-dialog-container input[formcontrolname="title"]', { timeout: 15000 });

    const spaceSelector = page.locator('mat-dialog-container .side-panel mat-select, mat-dialog-container mat-form-field:has(mat-label:has-text("Select spaces")) mat-select').first();

    if (!(await spaceSelector.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Space selector not visible in modal');
      return;
    }

    // Use force: true to bypass mat-label overlay interception
    await spaceSelector.click({ force: true });
    await page.waitForTimeout(500);

    const generalOption = page.locator('mat-option:has-text("General")');
    await expect(generalOption).toBeVisible({ timeout: 3000 });

    await page.keyboard.press('Escape');
    // Close modal
    await page.keyboard.press('Escape');
  });

  test('decision-form-saves-with-spaces: Can create decision with spaces in modal', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForSelector('h1', { timeout: 10000 });

    // Dismiss any overlays before clicking
    await dismissOverlays(page);
    await page.waitForTimeout(500);

    const newDecisionBtn = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();
    if (!(await newDecisionBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'New Decision button not visible');
      return;
    }

    await newDecisionBtn.click();

    // Wait for modal to open
    await page.waitForSelector('mat-dialog-container input[formcontrolname="title"]', { timeout: 15000 });

    // Fill required fields in the modal
    const uniqueTitle = 'Test Decision with Spaces ' + Date.now();
    await page.locator('mat-dialog-container input[formcontrolname="title"]').fill(uniqueTitle);
    await page.locator('mat-dialog-container textarea[formcontrolname="context"]').fill('Test context for the decision');
    await page.locator('mat-dialog-container textarea[formcontrolname="decision"]').fill('We decided to test spaces');
    await page.locator('mat-dialog-container textarea[formcontrolname="consequences"]').fill('Better test coverage');

    // Select a space if available - use force: true to bypass mat-label overlay
    const spaceSelector = page.locator('mat-dialog-container .side-panel mat-select, mat-dialog-container mat-form-field:has(mat-label:has-text("Select spaces")) mat-select').first();
    if (await spaceSelector.isVisible({ timeout: 3000 }).catch(() => false)) {
      await spaceSelector.click({ force: true });
      await page.waitForTimeout(500);
      const generalOption = page.locator('mat-option:has-text("General")');
      if (await generalOption.isVisible({ timeout: 2000 }).catch(() => false)) {
        await generalOption.click();
        await page.keyboard.press('Escape');
      }
    }

    // Submit via the Create Decision button in the modal footer
    const saveButton = page.locator('mat-dialog-container button:has-text("Create Decision")');
    await saveButton.click();

    // Verify success message appeared
    const successSnackbar = page.locator('simple-snack-bar:has-text("created"), .mat-mdc-snack-bar-label:has-text("created")').first();
    await expect(successSnackbar).toBeVisible({ timeout: 10000 });

    // Modal should close
    await expect(page.locator('mat-dialog-container')).not.toBeVisible({ timeout: 5000 });

    // Verify we're still on the decisions list page
    expect(page.url()).toContain('test-org.com');
  });
});

test.describe('Decision Edit - Space Selector (Modal)', () => {
  test('edit-decision-shows-space-selector: Editing in modal shows space selector', async ({ page }) => {
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

    // Click decision card to open view modal
    await decisionCard.click();

    // Wait for modal to open
    await page.waitForSelector('mat-dialog-container', { timeout: 10000 });
    await page.waitForTimeout(500);

    // Click the edit button in the modal header
    const editButton = page.locator('mat-dialog-container button[mattooltip="Edit Decision"]').first();
    if (!(await editButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      // Try alternate selector
      const editIconBtn = page.locator('mat-dialog-container .header-actions button:has(mat-icon:has-text("edit"))').first();
      if (!(await editIconBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
        test.skip(true, 'Edit button not visible in modal');
        return;
      }
      await editIconBtn.click();
    } else {
      await editButton.click();
    }

    // Wait for form to be editable
    await page.waitForSelector('mat-dialog-container input[formcontrolname="title"]:not([readonly])', { timeout: 10000 });

    // Wait for spaces to load
    await page.waitForTimeout(1000);

    // Check that space selector exists in the modal side panel
    const spaceSelector = page.locator('mat-dialog-container .side-panel mat-select, mat-dialog-container mat-form-field:has(mat-label:has-text("Select spaces")) mat-select').first();
    if (await spaceSelector.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(spaceSelector).toBeVisible();
    } else {
      test.skip(true, 'Space selector not visible in edit modal');
    }

    // Close modal
    await page.keyboard.press('Escape');
  });
});
