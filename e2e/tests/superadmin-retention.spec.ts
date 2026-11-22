import { test, expect, APIRequestContext, Page } from '@playwright/test';
import { loginAsSuperAdmin } from '../fixtures/auth';

// E2E tests use port 5002 to avoid conflicts with development backend on 5001
const API_URL = 'http://localhost:5002';

/**
 * Super admin > Data retention: what is waiting to be erased, what the
 * automatic run held back, running a category deliberately, the limits and
 * the run history.
 *
 * The test backend does not start the automatic run, so nothing here is
 * erased unless a test does it. Other specs share the database, so counts are
 * read from the page instead of being assumed.
 */

interface Backlog {
  tenants: string[];
  old_logins: number;
}

async function seedBacklog(
  request: APIRequestContext,
  data: { tenants?: number; old_logins?: number; expired_days_ago?: number; prefix: string }
): Promise<Backlog> {
  const response = await request.post(`${API_URL}/api/test/retention-backlog`, { data });
  expect(response.status()).toBe(200);
  return await response.json();
}

function uniquePrefix(name: string): string {
  return `${name}${Date.now().toString(36)}`;
}

async function openRetention(page: Page) {
  await page.goto('/superadmin/retention');
  await expect(page.locator('h1')).toContainText('Data retention');
  await expect(page.locator('[data-testid="retention-waiting"]')).toBeVisible();
}

function category(page: Page, name: string) {
  return page.locator(`[data-testid="retention-category-${name}"]`);
}

async function waitingCount(page: Page, name: string): Promise<number> {
  const text = await page.locator(`[data-testid="retention-waiting-${name}"]`).textContent();
  return parseInt(text || '0', 10);
}

async function setTenantLimit(page: Page, value: string) {
  const input = page.locator('[data-testid="retention-limit-input-tenants"]');
  await input.fill(value);
  await page.locator('[data-testid="retention-limits-save"]').click();
  await expect(page.locator('[data-testid="retention-limit-tenants"]')).toHaveText(`Limit ${value}`);
}

test.describe('Super Admin - Data retention', () => {
  test('retention-shows-waiting: the page lists each category with what is waiting and its limit', async ({ page, request }) => {
    await seedBacklog(request, { old_logins: 3, prefix: uniquePrefix('show') });

    await loginAsSuperAdmin(page);
    await openRetention(page);

    await expect(page.locator('[data-testid="retention-irreversible"]')).toContainText('Erasing cannot be undone');
    for (const name of ['accounts', 'login_history', 'inquiries', 'decisions', 'tenants']) {
      await expect(category(page, name)).toBeVisible();
    }
    expect(await waitingCount(page, 'login_history')).toBeGreaterThanOrEqual(3);
    await expect(page.locator('[data-testid="retention-limit-login_history"]')).toHaveText('No limit');
    await expect(page.locator('[data-testid="retention-limit-tenants"]')).toContainText('Limit');
    await expect(page.locator('[data-testid="retention-state-login_history"]'))
      .toContainText('Will be done by the next automatic run.');
    await expect(page.locator('[data-testid="retention-auto-state"]')).toHaveText('On');
  });

  test('retention-run-category: a category that is not held back can be run after confirming the count', async ({ page, request }) => {
    await seedBacklog(request, { old_logins: 2, prefix: uniquePrefix('run') });

    await loginAsSuperAdmin(page);
    await openRetention(page);
    const waiting = await waitingCount(page, 'login_history');
    expect(waiting).toBeGreaterThanOrEqual(2);

    await page.locator('[data-testid="retention-run-login_history"]').click();
    const confirm = page.locator('mat-dialog-container', { hasText: 'Login history to erase' });
    await expect(confirm).toContainText(`Erase ${waiting} login history entries now? This cannot be undone.`);

    // Cancel changes nothing
    await confirm.locator('button', { hasText: 'Cancel' }).click();
    await expect(confirm).toBeHidden();
    await expect(page.locator('[data-testid="retention-waiting-login_history"]')).toHaveText(String(waiting));

    await page.locator('[data-testid="retention-run-login_history"]').click();
    await page.locator('mat-dialog-container', { hasText: 'Login history to erase' })
      .locator('button', { hasText: `Erase ${waiting}` }).click();

    await expect(page.getByText(`Erased ${waiting} login history entries.`)).toBeVisible();
    await expect(page.locator('[data-testid="retention-waiting-login_history"]')).toHaveText('0');
    await expect(page.locator('[data-testid="retention-state-login_history"]')).toContainText('Nothing waiting');
    await expect(page.locator('[data-testid="retention-run-login_history"]')).toHaveCount(0);

    const latest = page.locator('[data-testid="retention-run-row"]').first();
    await expect(latest).toContainText('Super admin admin');
    await expect(latest).toContainText(`${waiting} login history entries`);
  });

  test('retention-held-back: more expired tenants than the limit are held back and shown on the dashboard', async ({ page, request }) => {
    const backlog = await seedBacklog(request, { tenants: 2, prefix: uniquePrefix('held') });

    await loginAsSuperAdmin(page);
    await page.goto('/superadmin/dashboard');
    const link = page.locator('[data-testid="nav-retention"]');
    await expect(link).toBeVisible();
    await expect(page.locator('[data-testid="nav-retention-count"]')).toContainText(/\d+ held back/);

    await link.click();
    await expect(page).toHaveURL(/\/superadmin\/retention/);
    await expect(page.locator('h1')).toContainText('Data retention');

    await expect(page.locator('[data-testid="retention-held-banner"]')).toContainText('deleted tenants to erase');
    await expect(page.locator('[data-testid="retention-held-back-count"]')).toContainText(/\d+ held back/);
    await expect(page.locator('[data-testid="retention-state-tenants"]')).toContainText('Held back');
    await expect(page.locator('[data-testid="retention-state-tenants"]')).toContainText('More are waiting than the limit');
    expect(await waitingCount(page, 'tenants')).toBeGreaterThanOrEqual(2);
    for (const domain of backlog.tenants) {
      const item = page.locator('[data-testid="retention-items-tenants"] [data-testid="retention-item"]', { hasText: domain });
      await expect(item).toBeVisible();
      await expect(item).toContainText('users: 1, decisions: 1, spaces: 0, memberships: 1');
    }
  });

  test('retention-release: a super admin releases held back tenants and the run is in the history', async ({ page, request }) => {
    const backlog = await seedBacklog(request, { tenants: 2, prefix: uniquePrefix('release') });

    await loginAsSuperAdmin(page);
    await openRetention(page);
    await expect(page.locator('[data-testid="retention-held-banner"]')).toBeVisible();
    const waiting = await waitingCount(page, 'tenants');
    expect(waiting).toBeGreaterThanOrEqual(2);

    await page.locator('[data-testid="retention-run-tenants"]').click();
    const confirm = page.locator('mat-dialog-container', { hasText: 'Deleted tenants to erase' });
    await expect(confirm).toContainText(`Erase ${waiting} tenants now? This cannot be undone.`);
    await confirm.locator('button', { hasText: `Erase ${waiting}` }).click();

    await expect(page.getByText(`Erased ${waiting} tenants.`)).toBeVisible();
    await expect(page.locator('[data-testid="retention-waiting-tenants"]')).toHaveText('0');
    await expect(page.locator('[data-testid="retention-state-tenants"]')).toContainText('Nothing waiting');
    for (const domain of backlog.tenants) {
      await expect(page.getByText(domain)).toHaveCount(0);
    }
    await expect(page.locator('[data-testid="retention-held-banner"]')).toHaveCount(0);

    const latest = page.locator('[data-testid="retention-run-row"]').first();
    await expect(latest).toContainText('Super admin admin');
    await expect(latest).toContainText('Finished');
    await expect(latest).toContainText(`${waiting} tenants`);

    // They are gone for good, not only hidden
    await page.reload();
    await expect(page.locator('h1')).toContainText('Data retention');
    await expect(page.locator('[data-testid="retention-waiting-tenants"]')).toHaveText('0');
    const tenants = await page.request.get('/api/tenants');
    expect(tenants.ok()).toBeTruthy();
    const body = JSON.stringify(await tenants.json());
    for (const domain of backlog.tenants) {
      expect(body).not.toContain(domain);
    }
  });

  test('retention-automatic-toggle: the automatic run can be turned off and on again', async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openRetention(page);
    const state = page.locator('[data-testid="retention-auto-state"]');
    const toggle = page.locator('[data-testid="retention-auto-toggle"]');
    await expect(state).toHaveText('On');

    await toggle.click();
    await expect(state).toHaveText('Off');
    await expect(page.locator('[data-testid="retention-auto-reason"]')).toContainText('Turned off here');
    await expect(toggle).toContainText('Turn on the automatic run');

    await page.reload();
    await expect(page.locator('[data-testid="retention-auto-state"]')).toHaveText('Off');

    await page.locator('[data-testid="retention-auto-toggle"]').click();
    await expect(page.locator('[data-testid="retention-auto-state"]')).toHaveText('On');
    await expect(page.locator('[data-testid="retention-auto-toggle"]')).toContainText('Turn off the automatic run');
  });

  test('retention-limit-change: raising the tenant limit lets a waiting pair through the automatic run', async ({ page, request }) => {
    await seedBacklog(request, { tenants: 2, prefix: uniquePrefix('limit') });

    await loginAsSuperAdmin(page);
    await openRetention(page);
    const waiting = await waitingCount(page, 'tenants');
    await expect(page.locator('[data-testid="retention-state-tenants"]')).toContainText('Held back');

    try {
      await setTenantLimit(page, String(waiting));
      await expect(page.locator('[data-testid="retention-state-tenants"]'))
        .toContainText('Will be done by the next automatic run.');
      await expect(page.locator('[data-testid="retention-held-banner"]')).toHaveCount(0);

      await page.reload();
      await expect(page.locator('[data-testid="retention-limit-tenants"]')).toHaveText(`Limit ${waiting}`);
      await expect(page.locator('[data-testid="retention-limit-input-tenants"]')).toHaveValue(String(waiting));
    } finally {
      await setTenantLimit(page, '1');
    }
    await expect(page.locator('[data-testid="retention-state-tenants"]')).toContainText('Held back');

    // Leave nothing waiting for other specs
    await page.locator('[data-testid="retention-run-tenants"]').click();
    await page.locator('mat-dialog-container', { hasText: 'Deleted tenants to erase' })
      .locator('button', { hasText: `Erase ${waiting}` }).click();
    await expect(page.locator('[data-testid="retention-waiting-tenants"]')).toHaveText('0');
  });

  test('retention-menu-link: the user menu has a Data retention entry', async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto('/superadmin/dashboard');
    await page.locator('button.user-button').click();
    await page.locator('[data-testid="menu-retention"]').click();
    await expect(page).toHaveURL(/\/superadmin\/retention/);
    await expect(page.locator('h1')).toContainText('Data retention');
  });
});
