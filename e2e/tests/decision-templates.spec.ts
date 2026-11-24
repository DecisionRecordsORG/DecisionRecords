import { test, expect, APIRequestContext, Locator, Page } from '@playwright/test';
import { loginAsUser } from '../fixtures/auth';

// E2E tests use port 5002 to avoid conflicts with development backend on 5001
const API_URL = 'http://localhost:5002';
const PASSWORD = 'TestPass123';

/**
 * Decision templates: an admin chooses a template in organisation settings,
 * the headings change on the form and on an existing decision, a decision gets
 * a type, existing decisions get a type in bulk, and switching back restores
 * the original headings. The text of a decision never changes.
 *
 * Each test creates its own tenant so one tenant's template does not leak into another.
 */

const GUARANTEE =
  'Changing the template changes headings and prompts only. Your decisions are not altered, and you can change back at any time.';
const CREDIT = 'Industry sections: NACE Rev. 2.1, Eurostat, CC BY 4.0';
const GENERAL_HEADINGS = ['Context', 'Decision', 'Consequences'];
const GOVERNANCE_HEADINGS = ['Matter and background', 'Decision and reasons', 'Alternatives, interests and implications'];

let counter = 0;

async function createAdmin(request: APIRequestContext, label: string): Promise<{ email: string; domain: string }> {
  counter += 1;
  const domain = `${label}-${Date.now()}-${counter}.test`;
  const email = `admin@${domain}`;
  const response = await request.post(`${API_URL}/api/test/create-user`, {
    data: { email, password: PASSWORD, name: 'Template Admin', role: 'admin', domain },
  });
  expect(response.ok()).toBeTruthy();
  return { email, domain };
}

function onboardingDialog(page: Page): Locator {
  return page.locator('mat-dialog-container', { hasText: 'Provisional Admin' });
}

function decisionModal(page: Page): Locator {
  return page.locator('mat-dialog-container', { has: page.locator('input[formcontrolname="title"]') });
}

async function tenantTemplate(page: Page) {
  const response = await page.request.get('/api/tenant/decision-template');
  expect(response.status()).toBe(200);
  return response.json();
}

/** Sign in as a new admin and close the first-admin dialog without answering anything. */
async function signInAndSkipOnboarding(page: Page, admin: { email: string; domain: string }): Promise<void> {
  await loginAsUser(page, admin.email, PASSWORD);
  const dialog = onboardingDialog(page);
  await expect(dialog).toBeVisible({ timeout: 10000 });
  await expect(dialog.locator('[data-testid="onboarding-decision-template"]')).toBeVisible();
  await dialog.locator('[data-testid="onboarding-dismiss"]').click();
  await expect(dialog).toBeHidden();
}

async function openTemplateTab(page: Page, domain: string): Promise<void> {
  await page.goto(`/${domain}/admin`);
  await expect(page.locator('h1')).toContainText('Organization Settings');
  await page.locator('div.mat-mdc-tab', { hasText: 'Decision template' }).click();
  await expect(page.locator('[data-testid="decision-template-card"]')).toBeVisible();
  await expect(page.locator('[data-testid="decision-template-save"]')).toBeVisible();
}

async function previewHeadings(page: Page): Promise<string[]> {
  const headings = await page.locator('[data-testid="decision-template-preview-heading"]').allTextContents();
  return headings.map(heading => heading.trim());
}

async function chooseTemplate(page: Page, templateId: string): Promise<void> {
  await page.locator(`[data-testid="decision-template-option-${templateId}"] input[type="radio"]`).check();
  const saved = page.waitForResponse(response =>
    response.url().includes('/api/tenant/decision-template') && response.request().method() === 'PUT');
  await page.locator('[data-testid="decision-template-save"]').click();
  expect((await saved).status()).toBe(200);
}

/** The labels of the three text sections of the open decision modal. */
async function sectionLabels(modal: Locator): Promise<string[]> {
  const labels: string[] = [];
  for (const control of ['context', 'decision', 'consequences']) {
    const field = modal.locator('mat-form-field', { has: modal.page().locator(`textarea[formcontrolname="${control}"]`) });
    labels.push(((await field.locator('mat-label').first().textContent()) || '').trim());
  }
  return labels;
}

async function openList(page: Page, domain: string): Promise<void> {
  await page.goto(`/${domain}`);
  await expect(page.locator('h1')).toContainText('Decision Records');
}

async function createDecision(page: Page, title: string, type?: string): Promise<void> {
  await page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first().click();
  const modal = decisionModal(page);
  await expect(modal).toBeVisible();
  await modal.locator('input[formcontrolname="title"]').fill(title);
  await modal.locator('textarea[formcontrolname="context"]').fill(`Context of ${title}`);
  await modal.locator('textarea[formcontrolname="decision"]').fill(`Decision of ${title}`);
  await modal.locator('textarea[formcontrolname="consequences"]').fill(`Consequences of ${title}`);
  if (type) {
    await openSelect(page, 'decision-type-select');
    await page.locator('mat-option', { hasText: new RegExp(`^\\s*${type}\\s*$`) }).click();
  }
  await modal.locator('button:has-text("Create Decision")').click();
  await expect(modal).toBeHidden({ timeout: 10000 });
  await expect(page.locator('.decision-card', { hasText: title })).toBeVisible();
}

/**
 * Open a Material select. The click goes to its form field: while the select
 * is empty its floating label lies over it and would take a click aimed at
 * the select itself.
 */
async function openSelect(page: Page, testId: string): Promise<void> {
  await page.locator('mat-form-field', { has: page.locator(`[data-testid="${testId}"]`) }).click();
  await expect(page.locator('mat-option').first()).toBeVisible();
}

function bulkRow(page: Page, title: string): Locator {
  return page.locator('[data-testid="bulk-type-row"]', { hasText: title });
}

test.describe('Decision templates', () => {
  test('template-switch: headings follow the chosen template on the form and on an existing decision, and switch back', async ({ page, request }) => {
    const admin = await createAdmin(request, 'tpl-switch');
    await signInAndSkipOnboarding(page, admin);

    // Nothing chosen: the General headings, exactly as before templates existed
    await page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first().click();
    let modal = decisionModal(page);
    await expect(modal).toBeVisible();
    expect(await sectionLabels(modal)).toEqual(GENERAL_HEADINGS);
    await expect(modal.locator('[data-testid="template-caution"]')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await expect(modal).toBeHidden();
    await createDecision(page, 'Adopt the travel policy');

    // Choose a template in organisation settings
    await openTemplateTab(page, admin.domain);
    await expect(page.locator('[data-testid="decision-template-guarantee"]')).toContainText(GUARANTEE);
    await expect(page.locator('[data-testid="decision-template-credit"]')).toHaveText(CREDIT);
    expect(await previewHeadings(page)).toEqual(GENERAL_HEADINGS);
    await expect(page.locator('[data-testid="decision-template-enable-packs"] input[type="checkbox"]')).not.toBeChecked();

    // The industry list is the official one and only suggests a template
    await openSelect(page, 'decision-template-industry');
    await expect(page.locator('mat-option')).toHaveCount(23); // 22 NACE sections and "Not chosen"
    await expect(page.locator('mat-option', { hasText: 'Human health and social work activities' })).toBeVisible();
    await page.locator('mat-option', { hasText: /^\s*Education\s*$/ }).click();
    await expect(page.locator('[data-testid="decision-template-option-governance"] [data-testid="decision-template-suggested"]')).toBeVisible();
    expect(await previewHeadings(page)).toEqual(GOVERNANCE_HEADINGS);
    await expect(page.locator('[data-testid="decision-template-caution"]')).toContainText(
      'Do not record decisions about identifiable patients, pupils or service users here.');

    await chooseTemplate(page, 'governance');
    const saved = await tenantTemplate(page);
    expect(saved.template_id).toBe('governance');
    expect(saved.industry).toBe('Q');

    // The existing decision shows the new headings over its unchanged text
    await openList(page, admin.domain);
    await page.locator('.decision-card', { hasText: 'Adopt the travel policy' }).click();
    modal = decisionModal(page);
    await expect(modal).toBeVisible();
    await expect(modal.locator('textarea[formcontrolname="context"]')).toHaveValue('Context of Adopt the travel policy');
    expect(await sectionLabels(modal)).toEqual(GOVERNANCE_HEADINGS);
    await expect(modal.locator('textarea[formcontrolname="decision"]')).toHaveValue('Decision of Adopt the travel policy');
    await expect(modal.locator('textarea[formcontrolname="consequences"]')).toHaveValue('Consequences of Adopt the travel policy');
    await page.keyboard.press('Escape');
    await expect(modal).toBeHidden();

    // A new decision uses the template's headings, prompts and caution
    await page.locator('button:has-text("New Decision")').first().click();
    modal = decisionModal(page);
    await expect(modal).toBeVisible();
    expect(await sectionLabels(modal)).toEqual(GOVERNANCE_HEADINGS);
    await expect(modal.locator('input[formcontrolname="title"]')).toHaveAttribute(
      'placeholder', 'For example: Adopt the revised safeguarding policy from 1 September');
    await expect(modal.locator('[data-testid="template-caution"]')).toContainText('Do not record decisions about identifiable');
    await page.keyboard.press('Escape');
    await expect(modal).toBeHidden();

    // Switch back: the original headings return and the text is still the same
    await openTemplateTab(page, admin.domain);
    await chooseTemplate(page, 'general');
    await openList(page, admin.domain);
    await page.locator('.decision-card', { hasText: 'Adopt the travel policy' }).click();
    modal = decisionModal(page);
    await expect(modal).toBeVisible();
    await expect(modal.locator('textarea[formcontrolname="context"]')).toHaveValue('Context of Adopt the travel policy');
    expect(await sectionLabels(modal)).toEqual(GENERAL_HEADINGS);
  });

  test('decision-type: a decision gets a type from the template and keeps it when the template changes', async ({ page, request }) => {
    const admin = await createAdmin(request, 'tpl-type');
    await signInAndSkipOnboarding(page, admin);

    await createDecision(page, 'Raise the travel budget', 'Spending');
    const card = page.locator('.decision-card', { hasText: 'Raise the travel budget' });
    await expect(card.locator('[data-testid="decision-card-type"]')).toHaveText('Spending');

    await openTemplateTab(page, admin.domain);
    await chooseTemplate(page, 'governance');

    // The stored type is kept and shown as it is, although Governance does not list it
    await openList(page, admin.domain);
    await expect(card.locator('[data-testid="decision-card-type"]')).toHaveText('Spending');
    await card.click();
    const modal = decisionModal(page);
    await expect(modal).toBeVisible();
    await expect(modal.locator('[data-testid="decision-type-value"]')).toHaveText('Spending');

    // Editing offers the new template's types and still the one the decision has
    await modal.locator('button[mattooltip="Edit Decision"]').click();
    await openSelect(page, 'decision-type-select');
    await expect(page.locator('mat-option', { hasText: /^\s*Spending\s*$/ })).toBeVisible();
    await expect(page.locator('mat-option', { hasText: /^\s*Policy\s*$/ })).toHaveCount(0);
    await page.locator('mat-option', { hasText: /^\s*Appointment\s*$/ }).click();
    const updated = page.waitForResponse(response =>
      /\/api\/decisions\/\d+$/.test(response.url()) && response.request().method() === 'PUT');
    await modal.locator('button:has-text("Save Changes"), button:has-text("Update Decision"), button:has-text("Save")').first().click();
    expect((await updated).status()).toBe(200);
    await expect(modal).toBeHidden({ timeout: 10000 });
    await expect(card.locator('[data-testid="decision-card-type"]')).toHaveText('Appointment');
  });

  test('bulk-type: an admin sets and clears the type of existing decisions in bulk', async ({ page, request }) => {
    const admin = await createAdmin(request, 'tpl-bulk');
    await signInAndSkipOnboarding(page, admin);
    for (const title of ['Pay review 2027', 'Second supplier', 'Office move']) {
      await createDecision(page, title);
    }

    await openTemplateTab(page, admin.domain);
    const bulk = page.locator('[data-testid="bulk-type-card"]');
    await expect(bulk.locator('[data-testid="bulk-type-row"]')).toHaveCount(3);
    await expect(bulkRow(page, 'Pay review 2027').locator('[data-testid="bulk-type-row-type"]')).toHaveText('No type');
    await expect(bulk.locator('[data-testid="bulk-type-set"]')).toBeDisabled();

    // Filter by search, tick what is shown, set a type
    await bulk.locator('[data-testid="bulk-type-search"]').fill('supplier');
    await expect(bulk.locator('[data-testid="bulk-type-row"]')).toHaveCount(1);
    await bulk.locator('[data-testid="bulk-type-search"]').fill('');
    await bulkRow(page, 'Pay review 2027').locator('input[type="checkbox"]').check();
    await bulkRow(page, 'Office move').locator('input[type="checkbox"]').check();
    await expect(bulk.locator('[data-testid="bulk-type-count"]')).toHaveText('2 selected');
    await openSelect(page, 'bulk-type-select');
    await page.locator('mat-option', { hasText: /^\s*People and hiring\s*$/ }).click();
    let applied = page.waitForResponse(response => response.url().includes('/api/tenant/decisions/bulk-type'));
    await bulk.locator('[data-testid="bulk-type-set"]').click();
    const result = await (await applied).json();
    expect(result.updated).toBe(2);
    expect(result.skipped_ids).toEqual([]);

    await expect(bulkRow(page, 'Pay review 2027').locator('[data-testid="bulk-type-row-type"]')).toHaveText('People and hiring');
    await expect(bulkRow(page, 'Office move').locator('[data-testid="bulk-type-row-type"]')).toHaveText('People and hiring');
    await expect(bulkRow(page, 'Second supplier').locator('[data-testid="bulk-type-row-type"]')).toHaveText('No type');
    await expect(bulk.locator('[data-testid="bulk-type-count"]')).toHaveText('0 selected');

    // The text of the decisions is untouched
    const decisions = await (await page.request.get('/api/decisions')).json();
    const payReview = decisions.find((decision: any) => decision.title === 'Pay review 2027');
    expect(payReview.decision_type).toBe('People and hiring');
    expect(payReview.context).toBe('Context of Pay review 2027');
    expect(payReview.decision).toBe('Decision of Pay review 2027');
    expect(payReview.consequences).toBe('Consequences of Pay review 2027');

    // Filter by current type, select all shown, clear
    await openSelect(page, 'bulk-type-current');
    await page.locator('mat-option', { hasText: /^\s*People and hiring\s*$/ }).click();
    await expect(bulk.locator('[data-testid="bulk-type-row"]')).toHaveCount(2);
    await bulk.locator('[data-testid="bulk-type-select-all"] input[type="checkbox"]').check();
    applied = page.waitForResponse(response => response.url().includes('/api/tenant/decisions/bulk-type'));
    await bulk.locator('[data-testid="bulk-type-clear"]').click();
    expect((await (await applied).json()).updated).toBe(2);
    await openSelect(page, 'bulk-type-current');
    await page.locator('mat-option', { hasText: /^\s*All\s*$/ }).click();
    await expect(bulkRow(page, 'Pay review 2027').locator('[data-testid="bulk-type-row-type"]')).toHaveText('No type');

    // The type also filters the decision list
    await bulkRow(page, 'Second supplier').locator('input[type="checkbox"]').check();
    await openSelect(page, 'bulk-type-select');
    await page.locator('mat-option', { hasText: /^\s*Supplier or partner\s*$/ }).click();
    applied = page.waitForResponse(response => response.url().includes('/api/tenant/decisions/bulk-type'));
    await bulk.locator('[data-testid="bulk-type-set"]').click();
    expect((await applied).status()).toBe(200);
    await openList(page, admin.domain);
    await openSelect(page, 'type-filter');
    await page.locator('mat-option', { hasText: /^\s*Supplier or partner\s*$/ }).click();
    await expect(page.locator('.decision-card')).toHaveCount(1);
    await expect(page.locator('.decision-card')).toContainText('Second supplier');
  });

  test('suggested-packs: packs are added only when the box is ticked', async ({ page, request }) => {
    const admin = await createAdmin(request, 'tpl-packs');
    await signInAndSkipOnboarding(page, admin);
    await openTemplateTab(page, admin.domain);

    await chooseTemplate(page, 'governance');
    let config = await (await page.request.get('/api/tenant/decision-relationships/config')).json();
    expect(config.config.selected_pack_ids).toEqual(['core']);

    await page.locator('[data-testid="decision-template-enable-packs"] input[type="checkbox"]').check();
    const saved = page.waitForResponse(response =>
      response.url().includes('/api/tenant/decision-template') && response.request().method() === 'PUT');
    await page.locator('[data-testid="decision-template-save"]').click();
    expect((await (await saved).json()).added_pack_ids).toEqual(['people', 'finance']);
    config = await (await page.request.get('/api/tenant/decision-relationships/config')).json();
    expect(config.config.selected_pack_ids).toEqual(['core', 'people', 'finance']);
    await expect(page.locator('[data-testid="decision-template-enable-packs"] input[type="checkbox"]')).not.toBeChecked();
  });

  test('onboarding-industry: the first-admin dialog asks the optional industry question and saves the suggested template', async ({ page, request }) => {
    const admin = await createAdmin(request, 'tpl-onboard');
    await loginAsUser(page, admin.email, PASSWORD);

    const dialog = onboardingDialog(page);
    await expect(dialog).toBeVisible({ timeout: 10000 });
    const section = dialog.locator('[data-testid="onboarding-decision-template"]');
    await expect(section).toContainText('What kind of organisation are you?');
    await expect(section).toContainText('Skip it and you get the General template.');
    await expect(section).toContainText(CREDIT);

    await openSelect(page, 'onboarding-industry');
    await page.locator('mat-option', { hasText: /^\s*Manufacturing\s*$/ }).click();
    await expect(section.locator('[data-testid="onboarding-template-choice"]')).toContainText('Controlled change');

    const saved = page.waitForResponse(response =>
      response.url().includes('/api/tenant/decision-template') && response.request().method() === 'PUT');
    await dialog.locator('[data-testid="onboarding-dismiss"]').click();
    expect((await saved).status()).toBe(200);
    await expect(dialog).toBeHidden();

    const template = await tenantTemplate(page);
    expect(template.industry).toBe('C');
    expect(template.template_id).toBe('controlled_change');
    expect(template.show_notice).toBe(false);
    await expect(page.locator('[data-testid="decision-template-notice"]')).toHaveCount(0);
  });

  test('onboarding-skip: skipping the question keeps General and shows no notice afterwards', async ({ page, request }) => {
    const admin = await createAdmin(request, 'tpl-skip');
    await signInAndSkipOnboarding(page, admin);

    const template = await tenantTemplate(page);
    expect(template.template_id).toBe('general');
    expect(template.template_chosen).toBe(false);
    expect(template.industry).toBeNull();
    expect(template.show_notice).toBe(false);

    await page.reload();
    await expect(page.locator('h1')).toContainText('Decision Records');
    await expect(page.locator('[data-testid="decision-template-notice"]')).toHaveCount(0);
  });

  test('existing-tenant-notice: an admin of a tenant that never saw templates gets one dismissible notice pointing at the card', async ({ page, request }) => {
    const admin = await createAdmin(request, 'tpl-notice');

    // An existing tenant: its admin saw the onboarding dialog before templates
    // existed. Reproduce that by keeping the template request from answering
    // while the dialog is dismissed, so the question is not asked.
    await page.route('**/api/tenant/decision-template', route => route.abort());
    await loginAsUser(page, admin.email, PASSWORD);
    const dialog = onboardingDialog(page);
    await expect(dialog).toBeVisible({ timeout: 10000 });
    await expect(dialog.locator('[data-testid="onboarding-decision-template"]')).toHaveCount(0);
    const dismissed = page.waitForResponse(response => response.url().includes('/api/user/dismiss-admin-onboarding'));
    await dialog.locator('[data-testid="onboarding-dismiss"]').click();
    expect((await dismissed).status()).toBe(200);
    await page.unroute('**/api/tenant/decision-template');

    await page.reload();
    const notice = page.locator('[data-testid="decision-template-notice"]');
    await expect(notice).toBeVisible({ timeout: 10000 });
    await expect(notice).toContainText('Decision templates for different kinds of organisation are now available.');
    await expect(notice).toContainText('Your decisions are not altered.');

    // It points at the card in organisation settings, and following it ends the notice
    await notice.locator('[data-testid="decision-template-notice-choose"]').click();
    await expect(page).toHaveURL(/\/admin\?tab=decision-template/);
    await expect(page.locator('[data-testid="decision-template-card"]')).toBeVisible({ timeout: 10000 });

    await openList(page, admin.domain);
    await expect(page.locator('.decision-card, .empty-state').first()).toBeVisible();
    await expect(page.locator('[data-testid="decision-template-notice"]')).toHaveCount(0);
    expect((await tenantTemplate(page)).show_notice).toBe(false);
  });
});
