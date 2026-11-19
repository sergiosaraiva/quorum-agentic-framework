---
name: writing-angular-tests
description: Use when writing or reviewing Angular unit and component tests. Vitest with TestBed, provideHttpClientTesting, role/label queries, fake timers and the four async states.
---

# Writing Angular Tests

## Quick Reference

| Topic | Rule |
|-------|------|
| Runner | Vitest through the Angular unit-test builder (`ng test`); `describe`/`it`/`expect` globals. Verify builder and config against your Angular major |
| Mocks | `vi.fn()`, `vi.spyOn()`, `vi.mock()`, `vi.useFakeTimers()`. No `jest.*` or `jasmine.*` calls |
| Components | `TestBed.configureTestingModule({ imports: [Component] })`; standalone needs no wrapper module |
| HTTP | `provideHttpClient()` + `provideHttpClientTesting()` + `HttpTestingController`; no real network. `httpMock.verify()` in `afterEach` |
| Rendering | Zoneless apps: `await fixture.whenStable()` after a state change. `fixture.detectChanges()` renders once while a request is pending. With zone.js, `fakeAsync` needs the Vitest zone patch (verify) |
| Queries | By role, label, text or a dedicated `data-testid`, never styling classes. Testing Library is optional; verify Vitest compatibility first |
| Scope | Behaviour a user or caller observes: states, interactions, request shape. Not framework wiring, markup trivia or getters |
| Doubles | Real stores and pure helpers; stub only I/O (HTTP). No custom harness wrappers without 2+ current users |
| Styles | jsdom does not apply global stylesheets; `getComputedStyle` proves nothing about the shared look. Verify visuals by screenshot (e2e) |

## Decision Tree

```
Rendered output of a component? -> TestBed, settle, assert on DOM
Service with HTTP?              -> HttpTestingController: assert method/URL/body, flush a response
Signal store?                   -> instantiate directly (runInInjectionContext only if it uses inject()), assert public signals
User interaction?               -> dispatch a real DOM event, settle, assert
Time (debounce, polling)?       -> vi.useFakeTimers(), vi.advanceTimersByTime(), restore in afterEach
Full journey across routes?     -> writing-playwright-e2e-tests
```

## Example: empty and error states

```typescript
describe('ReportList', () => {
  let fixture: ComponentFixture<ReportList>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ReportList],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(ReportList);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('shows the empty state when the API returns no reports', async () => {
    fixture.detectChanges();   // request pending
    http.expectOne(r => r.url.startsWith('/api/v1/reports')).flush({ items: [], totalCount: 0 });
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain('No reports yet');
  });

  it('shows an alert when the API call fails', async () => {
    fixture.detectChanges();
    http.expectOne(r => r.url.startsWith('/api/v1/reports'))
        .flush('error', { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[role="alert"]')).toBeTruthy();
  });
});
```

Add loading and data tests the same way. `verify()` fails on a missing or unexpected request.

## Example: store and fake timers

```typescript
it('computes draftCount', () => {
  const store = new ReportsStore();   // no DI deps, so no TestBed
  store.setReports([{ id: '1', title: 'A', status: 'draft' }, { id: '2', title: 'B', status: 'published' }]);
  expect(store.draftCount()).toBe(1);
});

it('debounces the search request', () => {
  vi.useFakeTimers();
  // type, advance 299 ms -> no request; advance 1 ms -> one request
  vi.useRealTimers();
});
```

## Accessibility in component tests

Prefer queries that double as checks: `getByRole('button', { name: 'Save' })` fails when the accessible name is missing. Assert focus moves to the dialog or first error after the triggering action. Automated axe checks belong in the e2e tier.

## Quality Checklist

- [ ] `httpMock.verify()` in `afterEach`; no real network
- [ ] The 4 states each have a test
- [ ] Queries use role, label or test id
- [ ] Render settled after every state-changing action before asserting
- [ ] Fake timers restored; no sleeps
- [ ] Each test would fail if the behaviour broke

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Real `HttpClient` in a component test | `provideHttpClientTesting()` |
| Asserting a styling class | Assert role, text or test id |
| Asserting before the render settled | `await fixture.whenStable()` |
| `jest.fn()` | `vi.fn()` |
| No `verify()` | Add to `afterEach` |

## Related Skills

- `frontend`, `creating-angular-api-clients`: code under test
- `writing-playwright-e2e-tests`: journeys
- `writing-integration-tests`: backend equivalent
