// Brings the jest-dom matcher types (toBeInTheDocument, toBeEnabled, ...) into
// the type-check, which only covers src/. The runtime registration is in
// vitest.setup.ts.
import '@testing-library/jest-dom/vitest';
