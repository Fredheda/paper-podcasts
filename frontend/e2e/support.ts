import { expect, type APIRequestContext, type Page } from '@playwright/test';

const backend = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT ?? '8100'}`;

// Test routes live on the backend itself (not behind server.js), so these calls
// go to it directly.
export async function resetBackend(request: APIRequestContext): Promise<void> {
  const response = await request.post(`${backend}/__reset`);
  expect(response.ok()).toBeTruthy();
}

export async function releaseGate(request: APIRequestContext): Promise<void> {
  const response = await request.post(`${backend}/__gate/release`);
  expect(response.ok()).toBeTruthy();
}

export type FakeRequest = { kind: string } & Record<string, unknown>;

export async function fakeRequests(request: APIRequestContext): Promise<FakeRequest[]> {
  const response = await request.get(`${backend}/__requests`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as FakeRequest[];
}

// Console errors that are expected and harmless. Starts empty; add an entry only
// with a comment saying why.
const ALLOWED_CONSOLE_ERRORS: RegExp[] = [];

// Every test fails on a page error or a console.error. Call once per test and
// assert the returned list is empty in afterEach.
export function watchPageErrors(page: Page): () => string[] {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    const value = message.text();
    if (ALLOWED_CONSOLE_ERRORS.some((pattern) => pattern.test(value))) return;
    errors.push(`console.error: ${value}`);
  });
  return () => errors;
}

// Setup through the API the UI itself uses (via server.js, the baseURL), so tests
// that are about something else skip the search and queue clicks.
export async function queueByApi(request: APIRequestContext, title: string): Promise<void> {
  const search = await request.post('/api/search', {
    data: { query: 'rag', exact_match: true, max_results: 5 }
  });
  const { papers } = (await search.json()) as { papers: { title: string }[] };
  const paper = papers.find((candidate) => candidate.title === title);
  expect(paper, `scripted paper "${title}"`).toBeDefined();
  const queued = await request.post('/api/jobs/enqueue', { data: { papers: [paper] } });
  expect(queued.ok()).toBeTruthy();
}
