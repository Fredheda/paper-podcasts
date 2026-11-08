import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import tseslint from 'typescript-eslint';
import { defineConfig } from 'eslint/config';

export default defineConfig(
  // dist is build output; server.js is the production Express server (Node);
  // the Playwright folders hold generated reports.
  { ignores: ['dist', 'node_modules', 'server.js', 'playwright-report', 'test-results'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, tseslint.configs.recommended],
    plugins: { 'react-hooks': reactHooks },
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser
    },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'error'
    }
  },
  {
    // Specs never build locators: every locator lives in e2e/selectors.ts, so a
    // UI change is one edit in one file.
    files: ['e2e/**/*.spec.ts'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: "CallExpression[callee.property.name='locator']",
          message: 'Use a function from e2e/selectors.ts; specs never call .locator().'
        }
      ]
    }
  }
);
