import { expect, test, type Page } from '@playwright/test';
import {
  addToChat,
  badge,
  card,
  chatAnswer,
  chatError,
  chatInput,
  chatSend,
  openChat,
  tab
} from './selectors';
import { fakeRequests, queueByApi, releaseGate, resetBackend, watchPageErrors } from './support';

let pageErrors: () => string[];

test.beforeEach(async ({ page, request }) => {
  await resetBackend(request);
  pageErrors = watchPageErrors(page);
});

test.afterEach(async ({ request }) => {
  await releaseGate(request);
  expect(pageErrors()).toEqual([]);
});

async function openChatOnProcessedPaper(page: Page): Promise<void> {
  await page.goto('/');
  await tab(page, 'Library').click();
  const item = card(page, 'Scripted Paper One');
  await expect(badge(item, 'completed')).toBeVisible({ timeout: 30_000 });
  await addToChat(item).check();
  await openChat(page).click();
}

async function ask(page: Page, question: string): Promise<void> {
  await chatInput(page).fill(question);
  await chatSend(page).click();
}

test('chat streams through the proxy and is grounded in the stored extract', async ({
  page,
  request
}) => {
  await queueByApi(request, 'Scripted Paper One');
  await openChatOnProcessedPaper(page);

  await ask(page, 'slow question');
  // The first chunk is on screen while the stream is still held open.
  await expect(chatAnswer(page, 'First chunk.')).toBeVisible();
  await expect(chatAnswer(page, 'Second chunk.')).toHaveCount(0);

  await releaseGate(request);
  await expect(chatAnswer(page, 'Third chunk.')).toBeVisible();

  const chat = (await fakeRequests(request)).find((entry) => entry.kind === 'chat');
  expect(chat, 'the chat call reached the fake').toBeDefined();
  const system = String(chat?.system);
  expect(system).toContain('=== Paper: Scripted Paper One (2501.00001) ===');
  expect(system).toContain('Body text of the fixture.');
});

test('a broken stream shows an error and the next question works', async ({ page, request }) => {
  await queueByApi(request, 'Scripted Paper One');
  await openChatOnProcessedPaper(page);

  await ask(page, 'boom');
  await expect(chatError(page, 'scripted stream failure')).toBeVisible();

  await ask(page, 'again');
  await expect(chatAnswer(page, 'Third chunk.')).toBeVisible();
  await expect(chatError(page, 'scripted stream failure')).toHaveCount(0);
});
