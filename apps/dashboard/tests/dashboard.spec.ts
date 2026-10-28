import {test, expect} from '@playwright/test';

test.beforeEach(async ({page}) => {
  await page.goto('/login');
  await page.getByRole('button', {name: 'Use demo credentials'}).click();
  await page.getByRole('button', {name: 'Sign in to workspace'}).click();
  await expect(page.getByRole('heading', {name: 'Overview', exact: true})).toBeVisible();
  await expect(page.getByText('Connecting to your workspace…')).toBeHidden();
});

test('all dashboard pages load without browser errors', async ({page}) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  for (const [path, title] of [['/customers', 'Customers'], ['/logs', 'Request logs'], ['/plans', 'Plans & budgets'], ['/aliases', 'Model routing'], ['/keys', 'API keys'], ['/providers', 'Providers'], ['/playground', 'Playground'], ['/settings', 'Settings & setup']]) {
    await page.goto(path);
    await expect(page.getByRole('heading', {name: title, exact: true})).toBeVisible();
    await expect(page.getByText('Connecting to your workspace…')).toBeHidden();
    await expect(page.locator('.error-banner')).toHaveCount(0);
  }
  expect(errors).toEqual([]);
});

test('search and edit a customer budget', async ({page}) => {
  await page.goto('/customers');
  await page.getByRole('textbox', {name: 'Search records'}).fill('Acme');
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await page.getByRole('button', {name: 'Edit Acme Inc.'}).click();
  await page.getByRole('spinbutton', {name: 'Custom monthly budget (USD)'}).fill('75');
  await page.getByRole('button', {name: 'Save changes'}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('status')).toContainText('Changes saved');
  await expect(page.locator('tbody')).toContainText('$75');
  // Restore the demo fixture after exercising persistence.
  await page.getByRole('button', {name: 'Edit Acme Inc.'}).click();
  await page.getByRole('spinbutton', {name: 'Custom monthly budget (USD)'}).fill('');
  await page.getByRole('button', {name: 'Save changes'}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('create a key shown once, then revoke it', async ({page}) => {
  await page.goto('/keys');
  await page.getByRole('button', {name: 'Create API key', exact: true}).click();
  const name = `Browser test ${Date.now()}`;
  await page.getByRole('textbox', {name: 'Name', exact: true}).fill(name);
  await page.getByRole('dialog').getByRole('button', {name: 'Create API key'}).click();
  await expect(page.locator('.secret-key')).toContainText('tg_live_');
  await page.getByRole('button', {name: 'I’ve saved my key'}).click();
  const row = page.getByRole('row').filter({hasText: name});
  await row.getByRole('button', {name: 'Revoke'}).click();
  await page.getByRole('button', {name: 'Revoke key', exact: true}).click();
  await expect(row).toContainText('Revoked');
});

test('playground previews protection and restores streaming PII', async ({page}) => {
  await page.goto('/playground');
  await page.getByRole('button', {name: 'Preview redaction'}).click();
  await expect(page.locator('.redaction-preview')).toContainText('[EMAIL_1]');
  await expect(page.locator('.redaction-preview pre')).not.toContainText('ali@example.com');
  await page.getByRole('button', {name: 'Send request'}).click();
  await expect(page.locator('.response-body')).toContainText('ali@example.com');
  await expect(page.getByRole('button', {name: 'Send request'})).toBeVisible();
  await expect(page.locator('.response-body')).not.toContainText('[EMAIL_');
});

test('mobile navigation works without horizontal overflow', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await expect(page.getByRole('heading', {name: 'Overview', exact: true})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.getByRole('button', {name: 'Open navigation'}).click();
  await page.getByRole('navigation').getByRole('link', {name: 'Customers'}).click();
  await expect(page.getByRole('heading', {name: 'Customers', exact: true})).toBeVisible();
  await expect(page.locator('.sidebar')).not.toHaveClass(/is-open/);
});
