# frontend guide

This file exists because it is loaded when you work under `frontend/`; the nearest CLAUDE.md wins and adds Angular rules to the root guide.

## Layout

| Path | Holds |
|------|-------|
| `src/app/features/<feature>/` | one folder per vertical slice: component, API client service, models, spec |
| `src/app/core/` | app-wide singletons: interceptors, config, auth |
| `src/app/shared/` | components or pipes used by 3+ features |

## Conventions

| Topic | Rule |
|-------|------|
| Components | standalone only (Immutable Rule 5), `changeDetection: ChangeDetectionStrategy.OnPush`, `inject()` instead of constructor injection |
| State | `signal`, `computed`, `effect` for local and shared state; a signal store service for cross-component state; no NgRx unless a need is recorded |
| Templates | built-in control flow (`@if`, `@for` with `track`, `@switch`); no `*ngIf` |
| Data states | every data view renders loading, error, empty and data states explicitly |
| API clients | one `@Injectable({ providedIn: 'root' })` service per feature using `HttpClient`; typed request and response interfaces mirroring the API DTOs; base URL from a config token, never a literal |
| TypeScript | `strict: true`; no `any` without a comment (Immutable Rule 6); prefer `unknown` plus narrowing |
| Styling | plain CSS or SCSS with design tokens as custom properties; no third-party component library unless a recorded decision adds one |
| Forms | typed reactive forms; validation messages next to the field |

## Tests

| Kind | Tool | Rule |
|------|------|------|
| Component and service | Vitest with `TestBed` and `provideHttpClientTesting` | query by role and label, not by CSS class |
| End to end | Playwright | role-based locators, one journey per spec, runs against a real API |

## Contract check

A DTO change in `src/Api/Features/**/Dtos.cs` must be mirrored in the feature's `models.ts` in the same PR; the regression reviewer checks this.

## Auth interceptor

`src/app/core/auth.interceptor.ts` adds `Authorization: Bearer <token>` to HttpClient requests for this origin or the configured `API_BASE_URL` (never to another host) when the `AUTH_TOKEN` provider returns a token. The default provider returns `null`, so no header is sent until you wire your identity provider: provide `AUTH_TOKEN` in `app.config.ts`, for example `{ provide: AUTH_TOKEN, useValue: () => session.accessToken() }`. Until then, every `/api/orders` call returns 401 by design.

## Lockfile

CI installs with `npm ci` from the committed `frontend/package-lock.json`, which resolves every package from the public npm registry. If your organisation uses a private registry, regenerate it against that registry (`cd frontend && rm package-lock.json && npm install`) and commit it. A lockfile embeds the registry URL of whoever generated it; never commit one that points at a private registry from a public repo. The CI job skips itself if the file is removed. npm 11 may print `install-scripts` warnings for esbuild during `npm ci`; they are harmless.
