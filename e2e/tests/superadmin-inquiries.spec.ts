import { test, expect, APIRequestContext, Page } from '@playwright/test';
import { loginAsSuperAdmin, loginAsUser } from '../fixtures/auth';

// E2E tests use port 5002 to avoid conflicts with development backend on 5001
const API_URL = 'http://localhost:5002';

/**
 * Super admin > Inquiries: messages from the contact, "Get in touch" and
 * feedback forms, stored before the notification email is attempted.
 *
 * The test backend has no email configuration, so every message sent here is
 * stored and shown as "Not emailed".
 */

async function sendContact(request: APIRequestContext, overrides: Record<string, unknown> = {}) {
  const response = await request.post(`${API_URL}/api/contact`, {
    data: {
      name: 'Ada Lovelace',
      email: 'ada@example.org',
      message: 'Hello, I would like to know more about decision records for a hospital pharmacy team.',
      ...overrides,
    },
  });
  expect(response.status()).toBe(200);
}

async function sendSponsorship(request: APIRequestContext, overrides: Record<string, unknown> = {}) {
  const response = await request.post(`${API_URL}/api/sponsorship`, {
    data: {
      organisation_name: 'Analytical Engines Ltd',
      contact_email: 'grace@example.org',
      contact_name: null,
      area_of_interest: null,
      message: null,
      ...overrides,
    },
  });
  expect(response.status()).toBe(200);
}

function rowFor(page: Page, text: string) {
  return page.locator('[data-testid="inquiry-row"]', { hasText: text });
}

async function openInquiries(page: Page) {
  await page.goto('/superadmin/inquiries');
  await expect(page.locator('h1')).toContainText('Inquiries');
  await expect(page.locator('[data-testid="interest-summary"]')).toBeVisible();
}

test.describe('Super Admin - Inquiries', () => {
  test('inquiries-stored-without-email: a message sent while email is not set up is listed and marked not emailed', async ({ page, request }) => {
    const marker = `Pharmacy ${Date.now()}`;
    await sendContact(request, { name: marker, team_focus: 'Formulary and protocol changes' });

    await loginAsSuperAdmin(page);
    await openInquiries(page);

    const row = rowFor(page, marker);
    await expect(row).toBeVisible();
    await expect(row).toContainText('Contact form');
    await expect(row).toContainText('ada@example.org');
    await expect(row).toContainText('Formulary and protocol changes');
    await expect(row).toContainText('Hello, I would like to know more');
    await expect(row.locator('[data-testid="inquiry-not-emailed-chip"]')).toBeVisible();
    await expect(page.locator('[data-testid="inquiries-not-emailed-banner"]')).toContainText('never emailed');
  });

  test('inquiries-newest-first: the latest message is the first row', async ({ page, request }) => {
    const older = `Older ${Date.now()}`;
    const newer = `Newer ${Date.now()}`;
    await sendContact(request, { name: older });
    await sendContact(request, { name: newer });

    await loginAsSuperAdmin(page);
    await openInquiries(page);

    await expect(page.locator('[data-testid="inquiry-row"]').first()).toContainText(newer);
  });

  test('inquiries-detail: the detail view shows the whole message and that it was not emailed', async ({ page, request }) => {
    const marker = `Detail ${Date.now()}`;
    const longMessage = 'First line of a long message. ' + 'More detail follows here. '.repeat(12) + 'THE END';
    await sendContact(request, { name: marker, message: longMessage, team_focus: 'Capital spending' });

    await loginAsSuperAdmin(page);
    await openInquiries(page);

    const row = rowFor(page, marker);
    // The table shows only the start of the message
    await expect(row).not.toContainText('THE END');
    await row.locator('[data-testid="inquiry-view"]').click();

    const detail = page.locator('[data-testid="inquiry-detail"]');
    await expect(detail).toBeVisible();
    await expect(page.locator('[data-testid="inquiry-detail-title"]')).toContainText('Contact form');
    await expect(detail.locator('[data-testid="inquiry-detail-name"]')).toHaveText(marker);
    await expect(detail.locator('[data-testid="inquiry-detail-email"]')).toContainText('ada@example.org');
    await expect(detail.locator('[data-testid="inquiry-detail-team-focus"]')).toHaveText('Capital spending');
    await expect(detail.locator('[data-testid="inquiry-detail-message"]')).toContainText('THE END');
    await expect(detail.locator('[data-testid="inquiry-detail-not-emailed"]')).toContainText('never emailed');
    await expect(detail.locator('[data-testid="inquiry-detail-status"]')).toContainText('Not handled');

    await page.locator('[data-testid="inquiry-detail-close"]').click();
    await expect(detail).toBeHidden();
  });

  test('inquiries-null-optional-fields: a "Get in touch" message with null optional fields is stored and listed', async ({ page, request }) => {
    const organisation = `Null Fields Org ${Date.now()}`;
    await sendSponsorship(request, { organisation_name: organisation });

    await loginAsSuperAdmin(page);
    await openInquiries(page);

    const row = rowFor(page, organisation);
    await expect(row).toBeVisible();
    await expect(row).toContainText('Get in touch');
    await expect(row).toContainText('grace@example.org');
  });

  test('inquiries-mark-handled: an inquiry can be marked handled and not handled again', async ({ page, request }) => {
    const marker = `Handle ${Date.now()}`;
    await sendContact(request, { name: marker });

    await loginAsSuperAdmin(page);
    await openInquiries(page);

    const row = rowFor(page, marker);
    await expect(row).toContainText('Not handled');

    await row.locator('[data-testid="inquiry-toggle-handled"]').click();
    await expect(row.locator('[data-testid="inquiry-handled-chip"]')).toBeVisible();

    // The handled filter keeps it; the not handled filter drops it
    await page.locator('[data-testid="inquiries-filter-handled"]').click();
    await page.locator('mat-option', { hasText: /^\s*Not handled\s*$/ }).click();
    await expect(rowFor(page, marker)).toHaveCount(0);

    await page.locator('[data-testid="inquiries-filter-handled"]').click();
    await page.locator('mat-option', { hasText: /^\s*Handled\s*$/ }).click();
    await expect(rowFor(page, marker)).toBeVisible();

    // The detail view says who handled it and can undo it
    await rowFor(page, marker).locator('[data-testid="inquiry-view"]').click();
    await expect(page.locator('[data-testid="inquiry-detail-status"]')).toContainText('Handled by admin');
    await page.locator('[data-testid="inquiry-detail-toggle-handled"]').click();
    await expect(rowFor(page, marker)).toHaveCount(0);

    await page.locator('[data-testid="inquiries-filter-handled"]').click();
    await page.locator('mat-option', { hasText: /^\s*All\s*$/ }).click();
    await expect(rowFor(page, marker)).toContainText('Not handled');
  });

  test('inquiries-filter-by-form: the form filter narrows the list', async ({ page, request }) => {
    const contact = `Filter Contact ${Date.now()}`;
    const organisation = `Filter Org ${Date.now()}`;
    await sendContact(request, { name: contact });
    await sendSponsorship(request, { organisation_name: organisation });

    await loginAsSuperAdmin(page);
    await openInquiries(page);
    await expect(rowFor(page, contact)).toBeVisible();
    await expect(rowFor(page, organisation)).toBeVisible();

    await page.locator('[data-testid="inquiries-filter-source"]').click();
    await page.locator('mat-option', { hasText: 'Get in touch' }).click();

    await expect(rowFor(page, organisation)).toBeVisible();
    await expect(rowFor(page, contact)).toHaveCount(0);
  });

  test('inquiries-delete-with-confirm: deleting asks first, and cancel keeps the inquiry', async ({ page, request }) => {
    const marker = `Delete ${Date.now()}`;
    await sendContact(request, { name: marker });

    await loginAsSuperAdmin(page);
    await openInquiries(page);

    const row = rowFor(page, marker);
    await row.locator('[data-testid="inquiry-delete"]').click();

    const confirm = page.locator('mat-dialog-container', { hasText: 'Delete inquiry' });
    await expect(confirm).toContainText(`Delete the message from ${marker}? This cannot be undone.`);
    await confirm.locator('button', { hasText: 'Cancel' }).click();
    await expect(confirm).toBeHidden();
    await expect(rowFor(page, marker)).toBeVisible();

    await rowFor(page, marker).locator('[data-testid="inquiry-delete"]').click();
    await page.locator('mat-dialog-container', { hasText: 'Delete inquiry' })
      .locator('button', { hasText: /^\s*Delete\s*$/ }).click();

    await expect(rowFor(page, marker)).toHaveCount(0);

    // It is gone for good, not only hidden
    await page.reload();
    await expect(page.locator('h1')).toContainText('Inquiries');
    await expect(rowFor(page, marker)).toHaveCount(0);
  });

  test('inquiries-unhandled-count: the dashboard shows how many inquiries are not handled', async ({ page, request }) => {
    await sendContact(request, { name: `Count ${Date.now()}` });

    await loginAsSuperAdmin(page);
    await page.goto('/superadmin/dashboard');

    const link = page.locator('[data-testid="nav-inquiries"]');
    await expect(link).toBeVisible();
    const count = page.locator('[data-testid="nav-inquiries-count"]');
    await expect(count).toContainText(/\d+ not handled/);
    const shown = parseInt((await count.textContent()) || '0', 10);
    expect(shown).toBeGreaterThan(0);

    await link.click();
    await expect(page).toHaveURL(/\/superadmin\/inquiries/);
    await expect(page.locator('[data-testid="inquiries-unhandled-count"]')).toContainText(`${shown} not handled`);
  });

  test('inquiries-interest-summary: the summary counts tenants and inquiries and lists team focus answers', async ({ page, request }) => {
    const focus = `Shift rotas ${Date.now()}`;
    await sendContact(request, { name: 'Summary Sender', team_focus: focus, team_size: '6-25' });

    await loginAsSuperAdmin(page);
    await openInquiries(page);

    const summary = page.locator('[data-testid="interest-summary"]');
    await expect(summary).toContainText('Interest');
    await expect(summary.locator('[data-testid="interest-tenants-by-size"]')).toContainText('1 to 5 people');
    await expect(summary.locator('[data-testid="interest-tenants-by-size"]')).toContainText('Not answered');
    await expect(summary.locator('[data-testid="interest-inquiries-by-size"]')).toContainText('6 to 25 people');
    await expect(summary.locator('[data-testid="interest-inquiries-by-source"]')).toContainText('Contact form');
    await expect(summary.locator('[data-testid="interest-inquiries-by-source"]')).toContainText('Get in touch');
    await expect(summary.locator('[data-testid="interest-inquiries-by-source"]')).toContainText('Feedback');

    const answers = summary.locator('[data-testid="interest-team-focus"]');
    await expect(answers).toContainText(focus);
    await expect(answers.locator('li', { hasText: focus })).toContainText('1 inquiry');
  });

  test('inquiries-menu-link: the super admin menu links to the page', async ({ page }) => {
    await loginAsSuperAdmin(page);

    await page.locator('button.user-button').click();
    await page.locator('[data-testid="menu-inquiries"]').click();

    await expect(page).toHaveURL(/\/superadmin\/inquiries/);
    await expect(page.locator('h1')).toContainText('Inquiries');
  });

  test('inquiries-tenant-admin-refused: a tenant admin cannot open the page or read the data', async ({ page }) => {
    await loginAsUser(page, 'admin@test-org.com', 'TestPass123');

    const response = await page.request.get('/api/superadmin/inquiries');
    expect(response.status()).toBe(403);

    await page.goto('/superadmin/inquiries');
    await expect(page).not.toHaveURL(/\/superadmin\/inquiries/);
    await expect(page.locator('[data-testid="inquiries-table"]')).toHaveCount(0);
  });

  test('inquiries-anonymous-refused: a signed-out visitor cannot read the data', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/superadmin/inquiries`);

    expect(response.status()).toBe(401);
  });
});
