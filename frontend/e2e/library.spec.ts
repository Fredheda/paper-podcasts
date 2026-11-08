import { expect, test } from '@playwright/test';
import {
  audio,
  backendOnline,
  badge,
  card,
  queueSelected,
  resultsCounter,
  searchBox,
  searchSubmit,
  selectBox,
  summaryHeading,
  summaryScripts,
  tab
} from './selectors';
import { resetBackend, watchPageErrors } from './support';

let pageErrors: () => string[];

test.beforeEach(async ({ page, request }) => {
  await resetBackend(request);
  pageErrors = watchPageErrors(page);
});

test.afterEach(() => {
  expect(pageErrors()).toEqual([]);
});

test('search, queue, process, read and play a paper', async ({ page, request }) => {
  await page.goto('/');
  await expect(backendOnline(page)).toBeVisible();

  await searchBox(page).fill('rag');
  await searchSubmit(page).click();
  await expect(resultsCounter(page, 4)).toBeVisible();
  await selectBox(card(page, 'Scripted Paper One')).check();
  await queueSelected(page).click();

  await expect(badge(card(page, 'Scripted Paper One'), 'Completed')).toBeVisible({
    timeout: 30_000
  });

  await tab(page, 'Library').click();
  const item = card(page, 'Scripted Paper One');
  await expect(badge(item, 'completed')).toBeVisible();
  await expect(summaryHeading(item, 'Scripted summary')).toBeVisible();
  await expect(summaryScripts(item)).toHaveCount(0);

  // The audio element points at the proxied route and the browser can load it.
  const media = audio(item);
  await expect(media).toHaveAttribute('src', '/api/library/2501.00001/audio');
  await media.evaluate((element: HTMLAudioElement) => element.load());
  await expect
    .poll(() => media.evaluate((element: HTMLAudioElement) => element.readyState))
    .toBeGreaterThanOrEqual(1);
  expect(await media.evaluate((element: HTMLAudioElement) => element.duration)).toBeGreaterThan(0);

  // A Range request through server.js is answered with a partial response.
  const ranged = await request.get('/api/library/2501.00001/audio', {
    headers: { Range: 'bytes=0-99' }
  });
  expect(ranged.status()).toBe(206);
  expect(ranged.headers()['content-range']).toMatch(/^bytes 0-99\//);
});
