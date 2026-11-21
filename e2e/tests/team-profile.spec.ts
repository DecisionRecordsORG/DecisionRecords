import { test, expect, APIRequestContext, Page } from '@playwright/test';
import { fillFormUntilReady, loginAsSuperAdmin, loginAsUser } from '../fixtures/auth';

// E2E tests use port 5002 to avoid conflicts with development backend on 5001
const API_URL = 'http://localhost:5002';
const PASSWORD = 'TestPass123';

/**
 * Team profile: the two optional questions in the first-admin onboarding
 * dialog ("What does your team make decisions about?" and team size), the
 * same answers in organisation settings, and where the super admin sees them.
 *
 * Each test creates its own tenant so the answers of one do not leak into another.
 */

let counter = 0;

async function createAdmin(request: APIRequestContext, label: string): Promise<{ email: string; domain: string }> {
  counter += 1;
  const domain = `${label}-${Date.now()}-${counter}.test`;
  const email = `admin@${domain}`;
  const response = await request.post(`${API_URL}/api/test/create-user`, {
    data: { email, password: PASSWORD, name: 'Profile Admin', role: 'admin', domain },
  });
  expect(response.ok()).toBeTruthy();
  return { email, domain };
}

function onboardingDialog(page: Page) {
  return page.locator('mat-dialog-container', { hasText: 'Provisional Admin' });
}

async function teamProfile(page: Page) {
  const response = await page.request.get('/api/tenant/team-profile');
  expect(response.status()).toBe(200);
  return response.json();
}

async function openTeamProfileTab(page: Page, domain: string) {
  await page.goto(`/${domain}/admin`);
  await expect(page.locator('h1')).toContainText('Organization Settings');
  await page.locator('div.mat-mdc-tab', { hasText: 'Team profile' }).click();
  await expect(page.locator('[data-testid="team-profile-card"]')).toBeVisible();
  await expect(page.locator('[data-testid="team-profile-focus"]')).toBeVisible();
}

test.describe('Team profile', () => {
  test('onboarding-asks-team-profile: the first-admin dialog asks the two optional questions and says why', async ({ page, request }) => {
    const admin = await createAdmin(request, 'ask');
    await loginAsUser(page, admin.email, PASSWORD);

    const dialog = onboardingDialog(page);
    await expect(dialog).toBeVisible({ timeout: 10000 });

    const section = dialog.locator('[data-testid="onboarding-team-profile"]');
    await expect(section).toContainText('Two optional questions');
    await expect(section).toContainText('It helps us build for teams like yours.');
    await expect(section).toContainText('You can skip this and answer later in organisation settings.');
    await expect(section).toContainText('What does your team make decisions about?');
    await expect(section).toContainText('Team size');

    // Opening the dialog does not put the cursor in the optional field
    const focusedTestId = await page.evaluate(() => document.activeElement?.getAttribute('data-testid'));
    expect(focusedTestId).not.toBe('onboarding-team-focus');
  });

  test('onboarding-skip: the dialog can be dismissed without answering and nothing is stored', async ({ page, request }) => {
    const admin = await createAdmin(request, 'skip');
    await loginAsUser(page, admin.email, PASSWORD);

    const dialog = onboardingDialog(page);
    await expect(dialog).toBeVisible({ timeout: 10000 });
    await dialog.locator('[data-testid="onboarding-dismiss"]').click();
    await expect(dialog).toBeHidden();

    const profile = await teamProfile(page);
    expect(profile.team_focus).toBeNull();
    expect(profile.team_size).toBeNull();
    expect(profile.answered_at).toBeNull();
  });

  test('onboarding-answer: answers given in the dialog are saved and shown in organisation settings', async ({ page, request }) => {
    const admin = await createAdmin(request, 'answer');
    await loginAsUser(page, admin.email, PASSWORD);

    const dialog = onboardingDialog(page);
    await expect(dialog).toBeVisible({ timeout: 10000 });
    await dialog.locator('[data-testid="onboarding-team-focus"]').fill('Hiring & supplier contracts');
    await dialog.locator('[data-testid="onboarding-team-size"]').click();
    await page.locator('mat-option', { hasText: '6 to 25 people' }).click();

    const saved = page.waitForResponse(response =>
      response.url().includes('/api/tenant/team-profile') && response.request().method() === 'PUT');
    await dialog.locator('[data-testid="onboarding-dismiss"]').click();
    expect((await saved).status()).toBe(200);
    await expect(dialog).toBeHidden();

    const profile = await teamProfile(page);
    expect(profile.team_focus).toBe('Hiring & supplier contracts');
    expect(profile.team_size).toBe('6-25');
    expect(profile.answered_by).toBe('Profile Admin');

    await openTeamProfileTab(page, admin.domain);
    await expect(page.locator('[data-testid="team-profile-focus"]')).toHaveValue('Hiring & supplier contracts');
    await expect(page.locator('[data-testid="team-profile-size"]')).toContainText('6 to 25 people');
    await expect(page.locator('[data-testid="team-profile-answered"]')).toContainText('Last answered by Profile Admin');
  });

  test('onboarding-not-over-decision: the dialog waits while a decision is being written and keeps out of the way', async ({ page, request }) => {
    const admin = await createAdmin(request, 'typing');

    // The dialog normally opens half a second after the list loads. Once the
    // sign-in form is filled in, stretch that delay so the decision dialog is
    // reliably open first.
    await page.addInitScript(() => {
      const originalSetTimeout = window.setTimeout;
      (window as any).setTimeout = (handler: TimerHandler, timeout?: number, ...args: any[]) =>
        originalSetTimeout(handler, (window as any).__stretchOnboardingDelay && timeout === 500 ? 2500 : timeout, ...args);
    });

    await page.context().clearCookies();
    await page.goto(`/${admin.domain}/login`, { waitUntil: 'domcontentloaded' });
    const continueButton = page.locator('[data-testid="continue-button"]');
    await fillFormUntilReady([[page.locator('[data-testid="email-input"]'), admin.email]], continueButton);
    await continueButton.click();
    await page.locator('[data-testid="password-input"]').fill(PASSWORD);
    await page.evaluate(() => { (window as any).__stretchOnboardingDelay = true; });
    await page.locator('[data-testid="login-button"]').click();

    // Start a decision straight away, before the onboarding dialog is due
    const newDecision = page.locator('button:has-text("New Decision"), button:has-text("Create Your First Decision")').first();
    await newDecision.click({ timeout: 20000 });

    const decisionDialog = page.locator('mat-dialog-container', { hasText: 'New Decision' });
    await expect(decisionDialog).toBeVisible();
    const title = decisionDialog.locator('input[formcontrolname="title"]');
    await title.click();
    await page.keyboard.type('Adopt a four day ');

    // Well past the (stretched) delay: the onboarding dialog must not have opened
    await page.waitForTimeout(4000);
    await expect(onboardingDialog(page)).toHaveCount(0);
    await expect(page.locator('mat-dialog-container')).toHaveCount(1);

    // Typing carries on in the same field: focus was never taken away
    await page.keyboard.type('week');
    await expect(title).toHaveValue('Adopt a four day week');
    await expect(title).toBeFocused();

    await decisionDialog.locator('textarea[formcontrolname="context"]').fill('The team asked for it.');
    await decisionDialog.locator('textarea[formcontrolname="decision"]').fill('We will trial it for a quarter.');
    await decisionDialog.locator('textarea[formcontrolname="consequences"]').fill('Support cover needs a rota.');
    await decisionDialog.locator('button:has-text("Create Decision")').click();
    await expect(decisionDialog).toBeHidden({ timeout: 10000 });

    // Once the decision is saved the onboarding dialog appears
    await expect(onboardingDialog(page)).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.decision-card', { hasText: 'Adopt a four day week' })).toHaveCount(1);
  });

  test('settings-edit-team-profile: a tenant admin can change and clear the answers later', async ({ page, request }) => {
    const admin = await createAdmin(request, 'edit');
    await loginAsUser(page, admin.email, PASSWORD);
    const dialog = onboardingDialog(page);
    await expect(dialog).toBeVisible({ timeout: 10000 });
    await dialog.locator('[data-testid="onboarding-dismiss"]').click();
    await expect(dialog).toBeHidden();

    await openTeamProfileTab(page, admin.domain);
    const card = page.locator('[data-testid="team-profile-card"]');
    await expect(card).toContainText('It helps us build for teams like yours.');
    await expect(card).toContainText('You can leave either one blank.');
    await expect(page.locator('[data-testid="team-profile-focus"]')).toHaveValue('');

    await page.locator('[data-testid="team-profile-focus"]').fill('Clinical protocols');
    await page.locator('[data-testid="team-profile-size"]').click();
    await page.locator('mat-option', { hasText: '101 to 500 people' }).click();
    await page.locator('[data-testid="team-profile-save"]').click();
    await expect(page.locator('simple-snack-bar', { hasText: 'Team profile saved' })).toBeVisible();

    let profile = await teamProfile(page);
    expect(profile.team_focus).toBe('Clinical protocols');
    expect(profile.team_size).toBe('101-500');

    // Survives a reload
    await openTeamProfileTab(page, admin.domain);
    await expect(page.locator('[data-testid="team-profile-focus"]')).toHaveValue('Clinical protocols');
    await expect(page.locator('[data-testid="team-profile-size"]')).toContainText('101 to 500 people');

    // Clear both again
    await page.locator('[data-testid="team-profile-focus"]').fill('');
    await page.locator('[data-testid="team-profile-size"]').click();
    await page.locator('mat-option', { hasText: 'Prefer not to say' }).click();
    await page.locator('[data-testid="team-profile-save"]').click();
    await expect(page.locator('simple-snack-bar', { hasText: 'Team profile saved' })).toBeVisible();

    profile = await teamProfile(page);
    expect(profile.team_focus).toBeNull();
    expect(profile.team_size).toBeNull();
    await expect(page.locator('[data-testid="team-profile-answered"]')).toHaveCount(0);
  });

  test('settings-team-focus-limit: the answer cannot be longer than 200 characters', async ({ page, request }) => {
    const admin = await createAdmin(request, 'limit');
    await loginAsUser(page, admin.email, PASSWORD);
    await openTeamProfileTab(page, admin.domain);

    const field = page.locator('[data-testid="team-profile-focus"]');
    await field.fill('x'.repeat(260));

    expect((await field.inputValue()).length).toBe(200);
    await expect(page.locator('[data-testid="team-profile-card"]')).toContainText('200 / 200');

    // The server enforces the same limit for callers that skip the form
    const response = await page.request.put('/api/tenant/team-profile', {
      data: { team_focus: 'x'.repeat(201) },
      headers: { 'X-CSRF-Token': (await (await page.request.get('/api/auth/csrf-token')).json()).csrf_token },
    });
    expect(response.status()).toBe(400);
    expect((await response.json()).error).toBe('Team focus must be 200 characters or fewer');
  });

  test('team-profile-members-refused: an ordinary member cannot read or change the team profile', async ({ page }) => {
    await loginAsUser(page, 'user@test-org.com', PASSWORD);

    const read = await page.request.get('/api/tenant/team-profile');
    expect(read.status()).toBe(403);

    const write = await page.request.put('/api/tenant/team-profile', {
      data: { team_size: '1-5' },
      headers: { 'X-CSRF-Token': (await (await page.request.get('/api/auth/csrf-token')).json()).csrf_token },
    });
    expect(write.status()).toBe(403);
  });

  test('superadmin-sees-team-profile: the tenant detail view and the interest summary show the answers', async ({ page, request }) => {
    const admin = await createAdmin(request, 'seen');
    const focus = `Fleet purchases ${Date.now()}`;
    await loginAsUser(page, admin.email, PASSWORD);
    const saved = await page.request.put('/api/tenant/team-profile', {
      data: { team_focus: focus, team_size: '26-100' },
      headers: { 'X-CSRF-Token': (await (await page.request.get('/api/auth/csrf-token')).json()).csrf_token },
    });
    expect(saved.status()).toBe(200);

    await loginAsSuperAdmin(page);
    await page.goto('/superadmin/tenants');
    await expect(page.locator('h1')).toContainText('Tenant Management');
    await page.locator('div.mat-mdc-tab', { hasText: 'All Tenants' }).first().click();

    const row = page.locator('tr.mat-mdc-row', { hasText: admin.domain });
    await expect(row).toBeVisible({ timeout: 10000 });
    await row.locator('button[mattooltip="View details"]').click();

    const profile = page.locator('[data-testid="tenant-team-profile"]');
    await expect(profile).toBeVisible();
    await expect(profile.locator('[data-testid="tenant-team-focus"]')).toHaveText(focus);
    await expect(profile.locator('[data-testid="tenant-team-size"]')).toHaveText('26 to 100 people');
    await page.locator('mat-dialog-container button', { hasText: 'Close' }).click();

    await page.goto('/superadmin/inquiries');
    const answers = page.locator('[data-testid="interest-team-focus"]');
    await expect(answers.locator('li', { hasText: focus })).toContainText('1 tenant');
  });

  test('superadmin-tenant-without-answers: a tenant that has not answered says so', async ({ page, request }) => {
    const admin = await createAdmin(request, 'blank');

    await loginAsSuperAdmin(page);
    await page.goto('/superadmin/tenants');
    await page.locator('div.mat-mdc-tab', { hasText: 'All Tenants' }).first().click();
    const row = page.locator('tr.mat-mdc-row', { hasText: admin.domain });
    await expect(row).toBeVisible({ timeout: 10000 });
    await row.locator('button[mattooltip="View details"]').click();

    await expect(page.locator('[data-testid="tenant-team-profile-empty"]'))
      .toHaveText('This team has not answered the team profile questions.');
  });
});
