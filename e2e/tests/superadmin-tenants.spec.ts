import { test, expect } from '@playwright/test';
import { loginAsSuperAdmin, dismissOverlays } from '../fixtures/auth';

test.describe('Super Admin - Tenant Management', () => {
  test.describe('View Tenant Details', () => {
    test('can-view-tenant-details: Clicking info icon opens tenant details dialog', async ({ page }) => {
      // Login as master account
      await loginAsSuperAdmin(page);

      // Navigate to tenants page
      await page.goto('/superadmin/tenants');
      await page.waitForLoadState('networkidle');

      // Click on "All Tenants" tab
      const allTenantsTab = page.locator('div.mat-mdc-tab:has-text("All Tenants")');
      await expect(allTenantsTab).toBeVisible({ timeout: 5000 });
      await allTenantsTab.click();

      // Wait for tenants table to load
      await page.waitForTimeout(2000);

      // Check if there are any tenants
      const tenantRow = page.locator('table mat-row, table tr.mat-mdc-row').first();
      if (!(await tenantRow.isVisible({ timeout: 5000 }).catch(() => false))) {
        test.skip(true, 'No tenants available to test');
        return;
      }

      // Find the info button (mat-icon with "info" text) in the first tenant row
      const infoButton = page.locator('button:has(mat-icon:has-text("info"))').first();
      await expect(infoButton).toBeVisible({ timeout: 5000 });

      // Click the info icon
      await dismissOverlays(page);
      await infoButton.click();

      // Wait for dialog to open
      await page.waitForSelector('h2[mat-dialog-title]', { timeout: 5000 });

      // Verify dialog contains tenant details
      const dialogTitle = page.locator('h2[mat-dialog-title]');
      await expect(dialogTitle).toContainText('Tenant Details');

      // Verify statistics section exists
      const statsSection = page.locator('.details-section:has(h3:has-text("Statistics"))');
      await expect(statsSection).toBeVisible();

      // Verify key elements in the dialog
      await expect(page.locator('.stat:has(label:has-text("Total Users"))')).toBeVisible();
      await expect(page.locator('.stat:has(label:has-text("Admins"))')).toBeVisible();
      await expect(page.locator('.stat:has(label:has-text("Stewards"))')).toBeVisible();
      await expect(page.locator('.stat:has(label:has-text("Age (days)"))')).toBeVisible();
      await expect(page.locator('.stat:has(label:has-text("Maturity State"))')).toBeVisible();

      // Verify maturity state chip is visible
      const maturityChip = page.locator('.stat mat-chip');
      await expect(maturityChip.first()).toBeVisible();

      // Verify Delete Tenant button is visible
      const deleteButton = page.locator('button:has-text("Delete Tenant")');
      await expect(deleteButton).toBeVisible();

      // Close the dialog
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);
    });

    test('tenant-details-shows-maturity-thresholds: Dialog displays maturity threshold fields', async ({ page }) => {
      await loginAsSuperAdmin(page);

      await page.goto('/superadmin/tenants');
      await page.waitForLoadState('networkidle');

      // Click on "All Tenants" tab
      const allTenantsTab = page.locator('div.mat-mdc-tab:has-text("All Tenants")');
      await allTenantsTab.click();
      await page.waitForTimeout(2000);

      // Check if there are any tenants
      const tenantRow = page.locator('table mat-row, table tr.mat-mdc-row').first();
      if (!(await tenantRow.isVisible({ timeout: 5000 }).catch(() => false))) {
        test.skip(true, 'No tenants available to test');
        return;
      }

      // Click info button
      const infoButton = page.locator('button:has(mat-icon:has-text("info"))').first();
      await dismissOverlays(page);
      await infoButton.click();

      // Wait for dialog to open
      await page.waitForSelector('h2[mat-dialog-title]', { timeout: 5000 });

      // Verify Maturity Thresholds section exists
      const thresholdsSection = page.locator('.details-section:has(h3:has-text("Maturity Thresholds"))');
      await expect(thresholdsSection).toBeVisible();

      // Verify threshold input fields
      const ageDaysField = page.locator('mat-form-field:has(mat-label:has-text("Age Days Threshold"))');
      const userThresholdField = page.locator('mat-form-field:has(mat-label:has-text("User Threshold"))');
      const adminThresholdField = page.locator('mat-form-field:has(mat-label:has-text("Admin Threshold"))');

      await expect(ageDaysField).toBeVisible();
      await expect(userThresholdField).toBeVisible();
      await expect(adminThresholdField).toBeVisible();

      // Verify Update Thresholds button exists
      const updateButton = page.locator('button:has-text("Update Thresholds")');
      await expect(updateButton).toBeVisible();

      await page.keyboard.press('Escape');
    });
  });

  test.describe('Delete Tenant Flow', () => {
    test('delete-requires-confirmation: Cannot delete without typing domain', async ({ page }) => {
      await loginAsSuperAdmin(page);

      await page.goto('/superadmin/tenants');
      await page.waitForLoadState('networkidle');

      // Click on "All Tenants" tab
      const allTenantsTab = page.locator('div.mat-mdc-tab:has-text("All Tenants")');
      await allTenantsTab.click();
      await page.waitForTimeout(2000);

      // Check if there are any tenants
      const tenantRow = page.locator('table mat-row, table tr.mat-mdc-row').first();
      if (!(await tenantRow.isVisible({ timeout: 5000 }).catch(() => false))) {
        test.skip(true, 'No tenants available to test');
        return;
      }

      // Click info button
      const infoButton = page.locator('button:has(mat-icon:has-text("info"))').first();
      await dismissOverlays(page);
      await infoButton.click();

      // Wait for dialog
      await page.waitForSelector('h2[mat-dialog-title]', { timeout: 5000 });

      // Click Delete Tenant button
      const deleteButton = page.locator('button:has-text("Delete Tenant")');
      await deleteButton.click();

      // Wait for confirmation dialog
      await page.waitForSelector('h2[mat-dialog-title]:has-text("Delete Tenant")', { timeout: 5000 });

      // Verify warning message
      const warningBox = page.locator('.warning-box');
      await expect(warningBox).toBeVisible();
      await expect(warningBox).toContainText('This action is permanent and cannot be undone');

      // Verify domain input field is present
      const domainInput = page.locator('input[placeholder*="Type domain name"]');
      await expect(domainInput).toBeVisible();

      // Verify delete button is disabled without typing domain
      const confirmDeleteButton = page.locator('button:has-text("Delete Tenant"):visible').last();
      await expect(confirmDeleteButton).toBeDisabled();

      // Try typing wrong domain
      await domainInput.fill('wrong-domain.com');
      await page.waitForTimeout(300);
      await expect(confirmDeleteButton).toBeDisabled();

      // Close the dialogs
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);
      await page.keyboard.press('Escape');
    });

    test('can-delete-tenant: Super admin can delete a tenant with correct confirmation', async ({ page }) => {
      await loginAsSuperAdmin(page);

      await page.goto('/superadmin/tenants');
      await page.waitForLoadState('networkidle');

      // Click on "All Tenants" tab
      const allTenantsTab = page.locator('div.mat-mdc-tab:has-text("All Tenants")');
      await allTenantsTab.click();
      await page.waitForTimeout(2000);

      // Look for new-org.com (bootstrap tenant) which we can safely delete
      // If it doesn't exist, skip the test
      const newOrgRow = page.locator('tr:has-text("new-org.com")').first();
      if (!(await newOrgRow.isVisible({ timeout: 3000 }).catch(() => false))) {
        test.skip(true, 'new-org.com tenant not available for deletion test');
        return;
      }

      // Click info button for new-org.com
      const infoButton = newOrgRow.locator('button:has(mat-icon:has-text("info"))');
      await dismissOverlays(page);
      await infoButton.click();

      // Wait for dialog
      await page.waitForSelector('h2[mat-dialog-title]', { timeout: 5000 });

      // Scroll to the Danger Zone section
      const dangerZone = page.locator('.danger-zone');
      await expect(dangerZone).toBeVisible();

      // Click Delete Tenant button
      const deleteButton = page.locator('button:has-text("Delete Tenant")');
      await deleteButton.click();

      // Wait for confirmation dialog
      await page.waitForSelector('h2[mat-dialog-title]:has-text("Delete Tenant")', { timeout: 5000 });

      // Verify the domain name is shown in the dialog
      const confirmDialog = page.locator('h2[mat-dialog-title]:has-text("new-org.com")');
      await expect(confirmDialog).toBeVisible();

      // Type the correct domain name
      const domainInput = page.locator('input[placeholder*="Type domain name"]');
      await domainInput.fill('new-org.com');
      await page.waitForTimeout(300);

      // Verify delete button is now enabled
      const confirmDeleteButton = page.locator('button:has-text("Delete Tenant"):visible').last();
      await expect(confirmDeleteButton).toBeEnabled();

      // Click Delete to confirm
      await confirmDeleteButton.click();

      // Wait for deletion to complete and dialogs to close
      await page.waitForTimeout(2000);

      // Verify success message (snackbar)
      const successSnackbar = page.locator('simple-snack-bar:has-text("deleted"), .mat-mdc-snack-bar-label:has-text("deleted")').first();
      await expect(successSnackbar).toBeVisible({ timeout: 5000 });

      // Verify tenant is removed from the list (or wait for list to refresh)
      await page.waitForTimeout(1000);
      const deletedTenantRow = page.locator('tr:has-text("new-org.com")');
      await expect(deletedTenantRow).not.toBeVisible({ timeout: 3000 });
    });
  });

  test.describe('Maturity Threshold Editing', () => {
    test('can-edit-maturity-thresholds: Can update maturity thresholds for bootstrap tenant', async ({ page }) => {
      await loginAsSuperAdmin(page);

      await page.goto('/superadmin/tenants');
      await page.waitForLoadState('networkidle');

      // Click on "All Tenants" tab
      const allTenantsTab = page.locator('div.mat-mdc-tab:has-text("All Tenants")');
      await allTenantsTab.click();
      await page.waitForTimeout(2000);

      // Look for a bootstrap tenant (check for bootstrap chip)
      const bootstrapTenantRow = page.locator('tr:has(mat-chip.bootstrap)').first();
      if (!(await bootstrapTenantRow.isVisible({ timeout: 3000 }).catch(() => false))) {
        test.skip(true, 'No bootstrap tenants available for threshold editing test');
        return;
      }

      // Click info button
      const infoButton = bootstrapTenantRow.locator('button:has(mat-icon:has-text("info"))');
      await dismissOverlays(page);
      await infoButton.click();

      // Wait for dialog
      await page.waitForSelector('h2[mat-dialog-title]', { timeout: 5000 });

      // Find threshold input fields
      const ageDaysInput = page.locator('input[type="number"]').filter({ has: page.locator('mat-label:has-text("Age Days")') }).first();
      const userThresholdInput = page.locator('mat-form-field:has(mat-label:has-text("User Threshold")) input').first();

      // Get current values
      const currentAgeDays = await ageDaysInput.inputValue();
      const currentUserThreshold = await userThresholdInput.inputValue();

      // Update values to something different
      const newAgeDays = currentAgeDays === '14' ? '30' : '14';
      const newUserThreshold = currentUserThreshold === '5' ? '10' : '5';

      await ageDaysInput.fill(newAgeDays);
      await userThresholdInput.fill(newUserThreshold);

      // Click Update Thresholds button
      const updateButton = page.locator('button:has-text("Update Thresholds")');
      await expect(updateButton).toBeEnabled();
      await updateButton.click();

      // Wait for update to complete
      await page.waitForTimeout(2000);

      // Verify success message
      const successSnackbar = page.locator('simple-snack-bar:has-text("updated"), .mat-mdc-snack-bar-label:has-text("updated")').first();
      await expect(successSnackbar).toBeVisible({ timeout: 5000 });

      // Dialog should close automatically after successful update
      await page.waitForTimeout(1000);
      const dialogTitle = page.locator('h2[mat-dialog-title]:has-text("Tenant Details")');
      await expect(dialogTitle).not.toBeVisible({ timeout: 3000 });
    });

    test('threshold-validation: Invalid threshold values are rejected', async ({ page }) => {
      await loginAsSuperAdmin(page);

      await page.goto('/superadmin/tenants');
      await page.waitForLoadState('networkidle');

      // Click on "All Tenants" tab
      const allTenantsTab = page.locator('div.mat-mdc-tab:has-text("All Tenants")');
      await allTenantsTab.click();
      await page.waitForTimeout(2000);

      // Check if there are any tenants
      const tenantRow = page.locator('table mat-row, table tr.mat-mdc-row').first();
      if (!(await tenantRow.isVisible({ timeout: 5000 }).catch(() => false))) {
        test.skip(true, 'No tenants available to test');
        return;
      }

      // Click info button
      const infoButton = page.locator('button:has(mat-icon:has-text("info"))').first();
      await dismissOverlays(page);
      await infoButton.click();

      // Wait for dialog
      await page.waitForSelector('h2[mat-dialog-title]', { timeout: 5000 });

      // Try to set invalid values (negative numbers should be rejected by the input)
      const ageDaysInput = page.locator('mat-form-field:has(mat-label:has-text("Age Days Threshold")) input').first();

      // Clear and set invalid value
      await ageDaysInput.fill('-10');

      // Click Update Thresholds
      const updateButton = page.locator('button:has-text("Update Thresholds")');
      await updateButton.click();

      // Wait for potential error or response
      await page.waitForTimeout(2000);

      // Should either show an error message or reject the input
      // The backend validates: age_days must be between 0 and 365
      const errorSnackbar = page.locator('simple-snack-bar:has-text("error"), simple-snack-bar:has-text("failed"), .mat-mdc-snack-bar-label:has-text("error"), .mat-mdc-snack-bar-label:has-text("failed")').first();

      // Either error shown or button stays enabled (validation prevents update)
      const hasError = await errorSnackbar.isVisible({ timeout: 2000 }).catch(() => false);
      expect(hasError).toBe(true);

      await page.keyboard.press('Escape');
    });
  });

  test.describe('Force Upgrade to Mature', () => {
    test('can-force-upgrade-maturity: Can force tenant to mature state', async ({ page }) => {
      await loginAsSuperAdmin(page);

      await page.goto('/superadmin/tenants');
      await page.waitForLoadState('networkidle');

      // Click on "All Tenants" tab
      const allTenantsTab = page.locator('div.mat-mdc-tab:has-text("All Tenants")');
      await allTenantsTab.click();
      await page.waitForTimeout(2000);

      // Look for a bootstrap tenant
      const bootstrapTenantRow = page.locator('tr:has(mat-chip.bootstrap)').first();
      if (!(await bootstrapTenantRow.isVisible({ timeout: 3000 }).catch(() => false))) {
        test.skip(true, 'No bootstrap tenants available for force upgrade test');
        return;
      }

      // Click info button
      const infoButton = bootstrapTenantRow.locator('button:has(mat-icon:has-text("info"))');
      await dismissOverlays(page);
      await infoButton.click();

      // Wait for dialog
      await page.waitForSelector('h2[mat-dialog-title]', { timeout: 5000 });

      // Verify Maturity Actions section is visible for bootstrap tenants
      const maturityActionsSection = page.locator('.details-section:has(h3:has-text("Maturity Actions"))');
      await expect(maturityActionsSection).toBeVisible();

      // Verify Force Upgrade button is present
      const forceUpgradeButton = page.locator('button:has-text("Force Upgrade to Mature")');
      await expect(forceUpgradeButton).toBeVisible();

      // Click Force Upgrade button
      await forceUpgradeButton.click();

      // Wait for confirmation dialog
      await page.waitForSelector('h2[mat-dialog-title]:has-text("Force Maturity Upgrade")', { timeout: 5000 });

      // Verify confirmation message mentions the domain
      const confirmMessage = page.locator('mat-dialog-content p');
      await expect(confirmMessage.first()).toBeVisible();

      // Confirm the upgrade
      const confirmButton = page.locator('button:has-text("Force Upgrade")').last();
      await confirmButton.click();

      // Wait for upgrade to complete
      await page.waitForTimeout(2000);

      // Verify success message
      const successSnackbar = page.locator('simple-snack-bar:has-text("upgraded"), simple-snack-bar:has-text("Mature"), .mat-mdc-snack-bar-label:has-text("upgraded"), .mat-mdc-snack-bar-label:has-text("Mature")').first();
      await expect(successSnackbar).toBeVisible({ timeout: 5000 });

      // Dialog should close after successful upgrade
      await page.waitForTimeout(1000);
      const dialogTitle = page.locator('h2[mat-dialog-title]:has-text("Tenant Details")');
      await expect(dialogTitle).not.toBeVisible({ timeout: 3000 });
    });

    test('force-upgrade-not-shown-for-mature: Mature tenants do not show force upgrade option', async ({ page }) => {
      await loginAsSuperAdmin(page);

      await page.goto('/superadmin/tenants');
      await page.waitForLoadState('networkidle');

      // Click on "All Tenants" tab
      const allTenantsTab = page.locator('div.mat-mdc-tab:has-text("All Tenants")');
      await allTenantsTab.click();
      await page.waitForTimeout(2000);

      // Look for a mature tenant
      const matureTenantRow = page.locator('tr:has(mat-chip.mature)').first();
      if (!(await matureTenantRow.isVisible({ timeout: 3000 }).catch(() => false))) {
        test.skip(true, 'No mature tenants available to verify UI behavior');
        return;
      }

      // Click info button
      const infoButton = matureTenantRow.locator('button:has(mat-icon:has-text("info"))');
      await dismissOverlays(page);
      await infoButton.click();

      // Wait for dialog
      await page.waitForSelector('h2[mat-dialog-title]', { timeout: 5000 });

      // Verify Maturity Actions section is NOT visible for mature tenants
      const maturityActionsSection = page.locator('.details-section:has(h3:has-text("Maturity Actions"))');
      await expect(maturityActionsSection).not.toBeVisible();

      // Verify Force Upgrade button is NOT present
      const forceUpgradeButton = page.locator('button:has-text("Force Upgrade to Mature")');
      await expect(forceUpgradeButton).not.toBeVisible();

      await page.keyboard.press('Escape');
    });
  });

  test.describe('Tenant List Display', () => {
    test('tenant-list-shows-key-info: All Tenants tab displays important tenant information', async ({ page }) => {
      await loginAsSuperAdmin(page);

      await page.goto('/superadmin/tenants');
      await page.waitForLoadState('networkidle');

      // Click on "All Tenants" tab
      const allTenantsTab = page.locator('div.mat-mdc-tab:has-text("All Tenants")');
      await allTenantsTab.click();
      await page.waitForTimeout(2000);

      // Check if there are any tenants
      const tenantRow = page.locator('table mat-row, table tr.mat-mdc-row').first();
      if (!(await tenantRow.isVisible({ timeout: 5000 }).catch(() => false))) {
        test.skip(true, 'No tenants available to test');
        return;
      }

      // Verify table headers are present
      const domainHeader = page.locator('th:has-text("Domain"), mat-header-cell:has-text("Domain")');
      const loginUrlHeader = page.locator('th:has-text("Login URL"), mat-header-cell:has-text("Login URL")');
      const maturityHeader = page.locator('th:has-text("Maturity"), mat-header-cell:has-text("Maturity")');
      const usersHeader = page.locator('th:has-text("Users"), mat-header-cell:has-text("Users")');
      const adminsHeader = page.locator('th:has-text("Admins"), mat-header-cell:has-text("Admins")');
      const stewardsHeader = page.locator('th:has-text("Stewards"), mat-header-cell:has-text("Stewards")');
      const ageHeader = page.locator('th:has-text("Age"), mat-header-cell:has-text("Age")');
      const ssoHeader = page.locator('th:has-text("SSO"), mat-header-cell:has-text("SSO")');
      const actionsHeader = page.locator('th:has-text("Actions"), mat-header-cell:has-text("Actions")');

      await expect(domainHeader).toBeVisible();
      await expect(loginUrlHeader).toBeVisible();
      await expect(maturityHeader).toBeVisible();
      await expect(usersHeader).toBeVisible();
      await expect(adminsHeader).toBeVisible();
      await expect(stewardsHeader).toBeVisible();
      await expect(ageHeader).toBeVisible();
      await expect(ssoHeader).toBeVisible();
      await expect(actionsHeader).toBeVisible();

      // Verify first row has data
      const firstDomainCell = tenantRow.locator('td strong, mat-cell strong').first();
      await expect(firstDomainCell).toBeVisible();
      const domainText = await firstDomainCell.textContent();
      expect(domainText).toBeTruthy();
      expect(domainText?.length).toBeGreaterThan(0);
    });

    test('login-url-copy-functionality: Can copy tenant login URL to clipboard', async ({ page }) => {
      await loginAsSuperAdmin(page);

      await page.goto('/superadmin/tenants');
      await page.waitForLoadState('networkidle');

      // Click on "All Tenants" tab
      const allTenantsTab = page.locator('div.mat-mdc-tab:has-text("All Tenants")');
      await allTenantsTab.click();
      await page.waitForTimeout(2000);

      // Check if there are any tenants
      const tenantRow = page.locator('table mat-row, table tr.mat-mdc-row').first();
      if (!(await tenantRow.isVisible({ timeout: 5000 }).catch(() => false))) {
        test.skip(true, 'No tenants available to test');
        return;
      }

      // Find the copy button (mat-icon with "content_copy" text)
      const copyButton = page.locator('button:has(mat-icon:has-text("content_copy"))').first();
      await expect(copyButton).toBeVisible();

      // Click the copy button
      await dismissOverlays(page);
      await copyButton.click();

      // Verify success message appears
      const successSnackbar = page.locator('simple-snack-bar:has-text("copied"), .mat-mdc-snack-bar-label:has-text("copied")').first();
      await expect(successSnackbar).toBeVisible({ timeout: 3000 });
    });
  });
});
