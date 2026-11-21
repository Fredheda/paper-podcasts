import type { Locator, Page } from '@playwright/test';

// Every locator of the browser suite. Role, label, visible text or an existing
// CSS class; no test ids. Specs import from here and never call .locator().

export type TabName = 'Search' | 'Queue' | 'Library';

export const tab = (page: Page, name: TabName): Locator =>
  page.locator('.tab-btn').filter({ hasText: new RegExp(`^${name}$`) });
export const backendOnline = (page: Page): Locator => page.getByText('Backend online');

// Search tab
export const searchBox = (page: Page): Locator =>
  page.getByPlaceholder('Try: retrieval augmented generation');
export const searchSubmit = (page: Page): Locator =>
  page.locator('form').getByRole('button', { name: /^Search/ });
export const queueSelected = (page: Page): Locator =>
  page.getByRole('button', { name: 'Queue selected papers' });
export const resultsCounter = (page: Page, count: number): Locator =>
  page.getByText(`Results: ${count}`);
export const queueMessage = (page: Page, text: string): Locator => page.getByText(text);
export const selectBox = (card: Locator): Locator => card.getByRole('checkbox', { name: 'Select' });

// Cards: search results, queue jobs and library items are all <article>s with the
// paper title as heading.
export const card = (page: Page, title: string): Locator =>
  page.locator('article').filter({ has: page.getByRole('heading', { name: title, exact: true }) });
export const badge = (within: Locator, text: string): Locator =>
  within.getByText(text, { exact: true });
export const text = (within: Locator, value: string): Locator => within.getByText(value);

// Library tab
export const listenButton = (item: Locator, name: 'Mark Listened' | 'Mark Unlistened'): Locator =>
  item.getByRole('button', { name });
export const listenFilter = (page: Page): Locator => page.getByLabel('Listen status');
export const summaryHeading = (item: Locator, name: string): Locator =>
  item.getByRole('heading', { name });
export const summaryScripts = (item: Locator): Locator => item.locator('script');
export const audio = (item: Locator): Locator => item.locator('audio');
export const addToChat = (item: Locator): Locator =>
  item.getByRole('checkbox', { name: 'Add to chat' });

// Chat panel
export const openChat = (page: Page): Locator => page.getByRole('button', { name: 'Open chat' });
export const chatInput = (page: Page): Locator => page.getByPlaceholder('Ask a question…');
export const chatSend = (page: Page): Locator => page.getByRole('button', { name: 'Send' });
export const chatAnswer = (page: Page, value: string): Locator =>
  page.locator('.chat-markdown').getByText(value);
export const chatError = (page: Page, message: string): Locator => page.getByText(message);
