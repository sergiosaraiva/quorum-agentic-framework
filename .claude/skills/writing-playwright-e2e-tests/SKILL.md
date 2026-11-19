---
name: writing-playwright-e2e-tests
description: Use when writing end-to-end tests for Angular user journeys with Playwright against a real running frontend and backend. Role-based locators, storageState auth, fixtures, trace-on-retry, CI sharding and axe accessibility checks. Not component tests (writing-angular-tests) and not load tests (load-and-performance-testing).
---

# Writing Playwright E2E Tests

## Quick Reference

| Topic | Rule |
|-------|------|
| Scope | Full journeys in a real browser against a real backend (dev server, Testcontainers-backed API or staging). One or two tests per critical journey (sign in, core create/read flow); edge logic belongs in unit, component and integration tests |
| Locators | `getByRole` first, then `getByLabel`, `getByText`, `getByTestId`. Never CSS class selectors |
| Waiting | Web-first assertions (`await expect(locator).toBeVisible()`) auto-retry. Never `page.waitForTimeout()` |
| Auth | Capture `storageState` once in global setup; reuse with `test.use({ storageState })`. Gitignore the auth folder: it holds real session tokens |
| Isolation | Each test gets its own browser context (default); tests never depend on another test's data. Create and clean up data through the API |
| Structure | Composable fixtures before a Page Object Model; add POM only when duplication hurts |
| Accessibility | Run an axe scan (`@axe-core/playwright`) on each key page and fail on serious or critical violations; keyboard-only path for the main flow |
| CI | `fullyParallel`, `retries: 2` in CI, `trace: 'on-first-retry'` inside `use`, shard with `--shard=i/n` |

## Decision Tree

```
One component in isolation?           -> writing-angular-tests
Journey across routes and real API?   -> Playwright
Session or guard behaviour?           -> Playwright with storageState (plus an unauthenticated project)
Pixel comparison?                     -> toHaveScreenshot() with a committed baseline, fixed viewport, animations disabled
API contract without a browser?       -> writing-integration-tests
```

## Example: journey with reused auth

```typescript
// e2e/reports.spec.ts
import { test, expect } from '@playwright/test';

test.use({ storageState: 'e2e/.auth/user.json' });

test('creates a report and shows it in the list', async ({ page }) => {
  await page.goto('/reports');
  await page.getByRole('button', { name: 'New report' }).click();
  await page.getByRole('textbox', { name: 'Title' }).fill('Q1 report');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('row', { name: /Q1 report/ })).toBeVisible();
});
```

`test.use({ storageState })` builds on the built-in `page` fixture, which inherits `baseURL` and `trace` from the config. Hand-roll `browser.newContext()` only for two auth states inside one test, and then pass `baseURL` explicitly.

## Example: global setup

```typescript
// e2e/global-setup.ts
import { chromium, type FullConfig } from '@playwright/test';

export default async function globalSetup(config: FullConfig) {
  const browser = await chromium.launch();
  const baseURL = config.projects[0].use?.baseURL;
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  await page.goto('/login');
  await page.getByLabel('Email').fill(process.env.E2E_USER ?? '');
  await page.getByLabel('Password').fill(process.env.E2E_PASSWORD ?? '');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('/dashboard');
  await context.storageState({ path: 'e2e/.auth/user.json' });   // gitignore e2e/.auth/
  await browser.close();
}
```

Credentials come from `${E2E_USER}` / `${E2E_PASSWORD}` CI secrets, never source.

## Example: accessibility and config

```typescript
import AxeBuilder from '@axe-core/playwright';

test('reports page has no serious accessibility violations', async ({ page }) => {
  await page.goto('/reports');
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag22aa']).analyze();
  expect(results.violations.filter(v => ['serious', 'critical'].includes(v.impact ?? ''))).toEqual([]);
});
```

```typescript
// playwright.config.ts (excerpt)
export default defineConfig({
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  use: { baseURL: process.env.E2E_BASE_URL, trace: 'on-first-retry' },
  globalSetup: require.resolve('./e2e/global-setup'),
});
```

Automated axe finds only part of the issues; the keyboard-path test and manual review cover the rest.

## Quality Checklist

- [ ] Locators by role/label first; no `waitForTimeout`
- [ ] Auth via `storageState`; auth folder gitignored
- [ ] Real backend, not a fully mocked API
- [ ] Tests independent; own data created and cleaned up
- [ ] Trace on retry; failures debuggable from the trace
- [ ] Axe scan and a keyboard-only pass on the key pages
- [ ] No more journeys than the critical paths

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| `waitForTimeout(2000)` | auto-retrying `expect` |
| Login through the UI in every test | `storageState` |
| `.btn-primary` locator | `getByRole('button', { name })` |
| Mocking the whole API in an "e2e" test | Real backend |
| Full POM for a small app | Fixtures first |

## Related Skills

- `writing-angular-tests`: component level
- `writing-integration-tests`: API without browser
- `load-and-performance-testing`: load, a separate concern
