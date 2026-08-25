const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const OUT = path.resolve('docs/assets/screenshots');
fs.mkdirSync(OUT, { recursive: true });

async function signIn(page) {
  await page.goto('/login');
  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill('admin');
  await page.getByRole('button', { name: /sign in/i }).click();

  if (page.url().includes('/change-password')) {
    await page.getByLabel('New password').fill('PlaywrightTutor123!');
    await page.getByLabel('Confirm').fill('PlaywrightTutor123!');
    await page.getByRole('button', { name: /save password/i }).click();
  }
  await expect(page).toHaveURL(/dashboard/);
}

async function shot(page, route, filename) {
  await page.goto(route);
  await page.waitForLoadState('networkidle');
  await page.screenshot({
    path: path.join(OUT, filename),
    fullPage: true
  });
}

test('capture polished repository screenshots', async ({ page }) => {
  await signIn(page);

  await shot(page, '/dashboard', '01-dashboard.png');
  await shot(page, '/lesson/3', '02-limited-rendering-lesson.png');
  await shot(page, '/experiments', '03-experiment-lab.png');
  await shot(page, '/library', '04-library.png');
  await shot(page, '/chapter/1', '05-primary-source-reader.png');
  await shot(page, '/argument-builder/3', '06-argument-builder.png');
  await shot(page, '/mastery', '07-mastery-dashboard.png');
});
