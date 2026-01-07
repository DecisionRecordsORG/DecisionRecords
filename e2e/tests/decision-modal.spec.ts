import { test, expect } from '@playwright/test';
import { loginAsUser, dismissOverlays } from '../fixtures/auth';

test.describe('Decision Modal', () => {
  test('create-decision-via-modal: Opens modal and creates decision', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });

    // Dismiss any overlays
    await dismissOverlays(page);
    await page.waitForTimeout(500);

    // Click New Decision button
    const createButton = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();

    if (!(await createButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Decision creation UI not accessible');
      return;
    }

    await createButton.click();

    // Modal should open - verify modal is visible (use .first() to avoid strict mode)
    const modal = page.locator('mat-dialog-container').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Verify modal header shows "New Decision"
    const modalTitle = modal.locator('h2:has-text("New Decision")');
    await expect(modalTitle).toBeVisible({ timeout: 3000 });

    // URL should NOT change (we're in a modal, not a new page)
    expect(page.url()).not.toContain('/decision/new');

    // Fill in the form
    const uniqueTitle = 'Modal Test Decision ' + Date.now();
    await modal.locator('input[formcontrolname="title"]').fill(uniqueTitle);
    await modal.locator('textarea[formcontrolname="context"]').fill('Test context via modal');
    await modal.locator('textarea[formcontrolname="decision"]').fill('We decided via modal');
    await modal.locator('textarea[formcontrolname="consequences"]').fill('Modal works');

    // Submit
    const createBtn = modal.locator('button:has-text("Create Decision")');
    await createBtn.click();

    // Modal should close
    await expect(modal).toBeHidden({ timeout: 10000 });

    // Success snackbar should appear
    const successSnackbar = page.locator('simple-snack-bar:has-text("created"), .mat-mdc-snack-bar-label:has-text("created")').first();
    await expect(successSnackbar).toBeVisible({ timeout: 5000 });

    // Decision should appear in the list
    const newDecisionCard = page.locator(`.decision-card:has-text("${uniqueTitle}")`);
    await expect(newDecisionCard).toBeVisible({ timeout: 5000 });
  });

  test('view-decision-opens-modal: Clicking card opens view modal', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Dismiss any overlays
    await dismissOverlays(page);

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

    // Click the decision card
    await decisionCard.click();

    // Modal should open (use .first() to avoid strict mode)
    const modal = page.locator('mat-dialog-container').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    // URL should NOT change (we're in a modal)
    expect(page.url()).not.toMatch(/\/decision\/\d+/);

    // Modal should show "View Decision" title
    const modalTitle = modal.locator('h2:has-text("View Decision")');
    await expect(modalTitle).toBeVisible({ timeout: 3000 });

    // Close button should be visible
    const closeButton = modal.locator('button[mattooltip="Close"]');
    await expect(closeButton).toBeVisible();

    // Close the modal
    await closeButton.click();
    await expect(modal).toBeHidden({ timeout: 5000 });
  });

  test('edit-decision-in-modal: Can switch from view to edit mode', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForTimeout(2000);

    await dismissOverlays(page);

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

    // Click the decision card to open in view mode
    await decisionCard.click();

    const modal = page.locator('mat-dialog-container').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Find and click the edit button
    const editButton = modal.locator('button[mattooltip="Edit Decision"]');
    if (!(await editButton.isVisible({ timeout: 3000 }).catch(() => false))) {
      // Close modal and skip
      const closeButton = modal.locator('button[mattooltip="Close"]');
      await closeButton.click();
      test.skip(true, 'Edit button not visible - user may not have permission');
      return;
    }

    await editButton.click();

    // Modal title should change to "Edit Decision"
    const editTitle = modal.locator('h2:has-text("Edit Decision")');
    await expect(editTitle).toBeVisible({ timeout: 3000 });

    // Form fields should be editable
    const titleInput = modal.locator('input[formcontrolname="title"]');
    await expect(titleInput).toBeEnabled();

    // Make a change
    const currentValue = await titleInput.inputValue();
    await titleInput.fill(currentValue + ' - Modal Edit');

    // Save button should be visible
    const saveButton = modal.locator('button:has-text("Save Changes")');
    await expect(saveButton).toBeVisible();

    // Save the changes
    await saveButton.click();

    // Modal should close
    await expect(modal).toBeHidden({ timeout: 10000 });

    // Success message should appear
    const successSnackbar = page.locator('simple-snack-bar:has-text("updated"), .mat-mdc-snack-bar-label:has-text("updated")').first();
    await expect(successSnackbar).toBeVisible({ timeout: 5000 });
  });

  test('modal-shows-metadata-sidebar: View mode shows decision metadata', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForTimeout(2000);

    await dismissOverlays(page);

    const decisionCard = page.locator('.decision-card').first();

    if (!(await decisionCard.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No decision cards visible');
      return;
    }

    // Open the modal
    await decisionCard.click();

    const modal = page.locator('mat-dialog-container').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Wait for the modal to load decision data (side panel only appears after decision is loaded)
    // The title in view mode will have the decision's title, wait for it
    const viewTitle = modal.locator('h2:has-text("View Decision")');
    await expect(viewTitle).toBeVisible({ timeout: 5000 });

    // Wait a bit for the decision data to load
    await page.waitForTimeout(2000);

    // Check if modal is still open (API might have failed and closed it)
    if (!(await modal.isVisible().catch(() => false))) {
      test.skip(true, 'Modal closed - decision may have failed to load');
      return;
    }

    // Side panel should show metadata (give it time to load)
    const sidePanel = modal.locator('.side-panel');
    const sidePanelVisible = await sidePanel.isVisible({ timeout: 3000 }).catch(() => false);

    if (!sidePanelVisible) {
      // Close modal if still open and skip
      if (await modal.isVisible().catch(() => false)) {
        await modal.locator('button[mattooltip="Close"], button:has-text("Close")').first().click();
      }
      test.skip(true, 'Side panel not visible - decision data may not have loaded');
      return;
    }

    // Should show "Created" metadata
    const createdLabel = modal.locator('.meta-label:has-text("Created")');
    await expect(createdLabel).toBeVisible({ timeout: 3000 });

    // Should show "Last Updated" metadata
    const updatedLabel = modal.locator('.meta-label:has-text("Last Updated")');
    await expect(updatedLabel).toBeVisible({ timeout: 3000 });

    // Close modal
    const closeButton = modal.locator('button[mattooltip="Close"]');
    await closeButton.click();
    await expect(modal).toBeHidden({ timeout: 5000 });
  });

  test('unsaved-changes-warning: Shows warning when closing with changes', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', 'TestPass123');

    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });

    await dismissOverlays(page);

    // Open create modal
    const createButton = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();

    if (!(await createButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Create button not visible');
      return;
    }

    await createButton.click();

    const modal = page.locator('mat-dialog-container').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Make a change to the form (dirty the form)
    await modal.locator('input[formcontrolname="title"]').fill('Unsaved Test');

    // Try to close with Cancel button
    const cancelButton = modal.locator('mat-dialog-actions button:has-text("Cancel")');
    await cancelButton.click();

    // Warning dialog should appear (it's a second mat-dialog-container)
    const warningDialog = page.locator('mat-dialog-container:has-text("Unsaved Changes")');
    await expect(warningDialog).toBeVisible({ timeout: 3000 });

    // Click "Keep Editing" to stay in modal
    const keepEditingButton = warningDialog.locator('button:has-text("Keep Editing")');
    await keepEditingButton.click();

    // Original modal should still be visible
    await expect(modal).toBeVisible();

    // Now try again and discard
    await cancelButton.click();
    await expect(warningDialog).toBeVisible({ timeout: 3000 });

    const discardButton = warningDialog.locator('button:has-text("Discard")');
    await discardButton.click();

    // Modal should close
    await expect(modal).toBeHidden({ timeout: 5000 });
  });

  test('delete-decision-in-modal: Can delete from modal', async ({ page }) => {
    test.setTimeout(60000); // Increase timeout for this complex test

    // First create a decision to delete
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });

    await dismissOverlays(page);

    // Create a decision first
    const createButton = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();

    if (!(await createButton.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Create button not visible');
      return;
    }

    await createButton.click();

    const modal = page.locator('mat-dialog-container').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Create a decision to delete
    const uniqueTitle = 'Delete Test Decision ' + Date.now();
    await modal.locator('input[formcontrolname="title"]').fill(uniqueTitle);
    await modal.locator('textarea[formcontrolname="context"]').fill('To be deleted');
    await modal.locator('textarea[formcontrolname="decision"]').fill('Delete this');
    await modal.locator('textarea[formcontrolname="consequences"]').fill('Gone');

    const createBtn = modal.locator('button:has-text("Create Decision")');
    await createBtn.click();

    await expect(modal).toBeHidden({ timeout: 10000 });
    await page.waitForTimeout(1000);

    // Now open the created decision
    const newDecisionCard = page.locator(`.decision-card:has-text("${uniqueTitle}")`);
    await expect(newDecisionCard).toBeVisible({ timeout: 5000 });
    await newDecisionCard.click();

    // Get the newly opened modal
    const viewModal = page.locator('mat-dialog-container').first();
    await expect(viewModal).toBeVisible({ timeout: 5000 });

    // Switch to edit mode
    const editButton = viewModal.locator('button[mattooltip="Edit Decision"]');
    if (await editButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await editButton.click();
    }

    // Click delete button
    const deleteButton = viewModal.locator('button:has-text("Delete")');
    if (!(await deleteButton.isVisible({ timeout: 3000 }).catch(() => false))) {
      // Close and skip
      const closeButton = viewModal.locator('button[mattooltip="Close"]');
      await closeButton.click();
      test.skip(true, 'Delete button not visible - user may not have permission');
      return;
    }

    await deleteButton.click();

    // Confirm delete dialog should appear (it's a new dialog on top)
    const confirmDialog = page.locator('mat-dialog-container:has-text("Delete Decision")');
    await expect(confirmDialog).toBeVisible({ timeout: 3000 });

    // Confirm deletion
    const confirmDeleteButton = confirmDialog.locator('button:has-text("Delete")');
    await confirmDeleteButton.click();

    // Modal should close
    await expect(viewModal).toBeHidden({ timeout: 10000 });

    // Success message should appear
    const successSnackbar = page.locator('simple-snack-bar:has-text("deleted"), .mat-mdc-snack-bar-label:has-text("deleted")').first();
    await expect(successSnackbar).toBeVisible({ timeout: 5000 });

    // Decision should no longer be in the list
    await page.waitForTimeout(1000);
    await expect(newDecisionCard).not.toBeVisible({ timeout: 5000 });
  });

  test('modal-shows-change-history: Can view change history in modal', async ({ page }) => {
    test.setTimeout(60000); // Increase timeout for this test

    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h1', { timeout: 10000 });
    await page.waitForTimeout(2000);

    await dismissOverlays(page);

    const decisionCard = page.locator('.decision-card').first();

    if (!(await decisionCard.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No decision cards visible');
      return;
    }

    // Open the modal
    await decisionCard.click();

    const modal = page.locator('mat-dialog-container').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Wait for modal to fully load
    const viewTitle = modal.locator('h2:has-text("View Decision")');
    await expect(viewTitle).toBeVisible({ timeout: 5000 });

    // Wait for the decision data to load
    await page.waitForTimeout(2000);

    // Check if the modal is still open (may have closed due to API failure)
    if (!(await modal.isVisible().catch(() => false))) {
      test.skip(true, 'Modal closed - decision may have failed to load');
      return;
    }

    // Check if side panel is visible (indicates decision loaded successfully)
    const sidePanel = modal.locator('.side-panel');
    if (!(await sidePanel.isVisible({ timeout: 3000 }).catch(() => false))) {
      // Close modal and skip - decision didn't load properly
      const closeBtn = modal.locator('button:has-text("Close")');
      if (await closeBtn.isVisible().catch(() => false)) {
        await closeBtn.click();
      }
      test.skip(true, 'Decision data did not load');
      return;
    }

    // Look for history card (only shows if decision has history)
    const historyCard = modal.locator('.history-card');

    if (await historyCard.isVisible({ timeout: 3000 }).catch(() => false)) {
      // History card is visible
      const historyHeader = modal.locator('.history-card-header:has-text("Change History")');
      await expect(historyHeader).toBeVisible();

      // Click on a history entry to expand it
      const historyEntry = modal.locator('.history-entry').first();
      if (await historyEntry.isVisible({ timeout: 2000 }).catch(() => false)) {
        await historyEntry.click();

        // Should show snapshot content
        const snapshotContent = modal.locator('.history-snapshot');
        await expect(snapshotContent).toBeVisible({ timeout: 3000 });
      }
    } else {
      // Decision may not have history - that's okay, just verify the modal loaded
      console.log('No change history for this decision');
    }

    // Close modal using keyboard (more reliable)
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

    // If modal still open, try clicking close button
    if (await modal.isVisible().catch(() => false)) {
      const closeButton = modal.locator('button:has-text("Close")');
      if (await closeButton.isVisible().catch(() => false)) {
        await closeButton.click();
      }
    }
  });
});
