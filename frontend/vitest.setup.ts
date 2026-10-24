import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

// Explicit rather than relying on Testing Library's global-afterEach
// auto-detection, which needs `test.globals: true` (not set here: tests
// import describe/it/expect explicitly from "vitest"). Without this, render()
// output from one test leaks into the next in the same file.
afterEach(() => {
  cleanup();
});
