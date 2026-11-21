import { expect, test, type Page } from '@playwright/test';
import {
  addToChat,
  badge,
  card,
  queueMessage,
  queueSelected,
  searchBox,
  searchSubmit,
  selectBox,
  tab,
  text
} from './selectors';
import { releaseGate, resetBackend, watchPageErrors } from './support';

let pageErrors: () => string[];

test.beforeEach(async ({ page, request }) => {
  await resetBackend(request);
  pageErrors = watchPageErrors(page);
});

test.afterEach(async ({ request }) => {
  await releaseGate(request);
  expect(pageErrors()).toEqual([]);
});

async function searchAndQueue(page: Page, title: string): Promise<void> {
  await searchBox(page).fill('rag');
  await searchSubmit(page).click();
  await selectBox(card(page, title)).check();
  await queueSelected(page).click();
}

test('a failed job is visible and does not block the queue', async ({ page }) => {
  const failing = 'FAIL Scripted Paper Three';
  await page.goto('/');
  await searchAndQueue(page, failing);

  const job = card(page, failing);
  await expect(badge(job, 'Failed')).toBeVisible({ timeout: 30_000 });
  await expect(text(job, 'Processing failed. Check server logs for details.')).toBeVisible();

  // It is listed in the library as failed, with nothing to play or chat about.
  await tab(page, 'Library').click();
  const item = card(page, failing);
  await expect(badge(item, 'failed')).toBeVisible();
  await expect(text(item, 'Audio not yet generated.')).toBeVisible();
  await expect(addToChat(item)).toHaveCount(0);

  // The next paper still completes.
  await tab(page, 'Search').click();
  await selectBox(card(page, 'Scripted Paper One')).check();
  await queueSelected(page).click();
  await expect(badge(card(page, 'Scripted Paper One'), 'Completed')).toBeVisible({
    timeout: 30_000
  });
});

test('queueing a paper that is already active is skipped', async ({ page, request }) => {
  const held = 'HOLD Scripted Paper Four';
  await page.goto('/');
  await searchAndQueue(page, held);
  // The scripted summary waits for the gate, so the job stays active.
  await expect(badge(card(page, held), 'Summarizing')).toBeVisible();

  await tab(page, 'Search').click();
  await selectBox(card(page, held)).check();
  await queueSelected(page).click();
  await tab(page, 'Search').click();
  await expect(queueMessage(page, 'Queued 0, skipped 1 already active/queued.')).toBeVisible();

  // Let the held job finish inside this test, so no worker outlives it (the
  // reset race is also covered by a pytest, but a single-file run or a CI retry
  // must not depend on file order).
  await releaseGate(request);
  await tab(page, 'Queue').click();
  await expect(badge(card(page, held), 'Completed')).toBeVisible({ timeout: 30_000 });
});
