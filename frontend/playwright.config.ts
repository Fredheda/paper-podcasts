import { defineConfig, devices } from '@playwright/test';

const backendPort = process.env.E2E_BACKEND_PORT ?? '8100';
const webPort = process.env.E2E_WEB_PORT ?? '3100';
const backendUrl = `http://127.0.0.1:${backendPort}`;
const webUrl = `http://127.0.0.1:${webPort}`;

// The real production frontend (server.js + dist) against the real backend with
// scripted arXiv and OpenAI (tests/e2e_backend). One worker: the backend holds
// state that every test resets.
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: webUrl,
    trace: 'on-first-retry'
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      name: 'Backend',
      command: 'poetry run python -m tests.e2e_backend.launcher',
      cwd: '..',
      url: `${backendUrl}/health`,
      env: { E2E_BACKEND_PORT: backendPort },
      // The pipeline logs every stage to stderr; keep that for CI failures only.
      stderr: process.env.CI ? 'pipe' : 'ignore',
      reuseExistingServer: false,
      timeout: 120_000
    },
    {
      name: 'Web',
      // Build first so the bundle under test is never stale.
      command: 'npm run build && node server.js',
      url: webUrl,
      env: { PORT: webPort, BACKEND_URL: backendUrl },
      reuseExistingServer: false,
      timeout: 180_000
    }
  ]
});
